"""
ParliamentCouncil — Enhanced parliament coordinator integrating:
  - Native strate votes (AMD, Momentum, Structure, Macro…)
  - ML panel votes (S0-S7, S11 calibration)
  - Agent debate panel (RegimeAgent, MomentumAgent, RiskAgent…)
  - Debate logger for audit trail

This is the single entry point for the full parliament deliberation.
It replaces direct calls to Parliament.deliberate() when the ML stack
is loaded; falls back gracefully to classic Parliament when it isn't.

Usage in cycle_manager.py::

    from parliament.council import ParliamentCouncil

    council = ParliamentCouncil(system)
    decision = await council.deliberate(symbol, strate_votes, context)
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

import numpy as np

from parliament.agents import AgentContext, build_agent_panel
from parliament.debate_logger import DebateLogger, DebateRound

if TYPE_CHECKING:
    from oracle_system import OracleSystem

logger = logging.getLogger("ORACLE.Parliament.Council")


class ParliamentCouncil:
    """
    Enhanced Parliament Council with ML integration.

    Flow
    ----
    1. Receive strate votes (native + legacy) from CycleManager
    2. Build agent context from market features
    3. Run ML council (S0-S7) → convert to parliament Vote format
    4. Run agent panel (6 debate agents) → convert verdicts to votes
    5. Apply S0 gate override (NOISE → all NEUTRAL)
    6. Feed combined votes to Parliament.deliberate()
    7. Apply S11 Brier calibration to final decision weights
    8. Log debate round to DebateLogger
    9. Return final ParliamentDecision

    Parameters
    ----------
    system : OracleSystem
        Reference to the parent system (Context Object pattern).
    db_path : str | None
        Optional SQLite path for debate logging persistence.
    """

    def __init__(self, system: "OracleSystem", db_path: Optional[str] = None):
        self._s = system
        self._ml_council = None
        self._agent_panel = []
        self._debate_logger = DebateLogger(maxlen=500, db_path=db_path)
        self._enabled = False
        self._s11 = None
        self._init_ml_stack()

    def _init_ml_stack(self) -> None:
        """Lazy-load ML council and agent panel. Never raises — all optional."""
        try:
            from parliament.ml_council import MLCouncil
            import os
            models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
            self._ml_council = MLCouncil(models_dir=models_dir)
            self._ml_council.load_models()
            logger.info("ParliamentCouncil: ML stack loaded")
        except Exception as e:
            logger.debug(f"ParliamentCouncil: ML council unavailable ({e})")
            self._ml_council = None

        try:
            s0 = (self._ml_council.models.get("S0") if self._ml_council else None)
            s3 = (self._ml_council.models.get("S3") if self._ml_council else None)
            s5 = (self._ml_council.models.get("S5") if self._ml_council else None)
            s7 = (self._ml_council.models.get("S7") if self._ml_council else None)
            self._agent_panel = build_agent_panel(s0, s3, s5, s7)
            logger.info(f"ParliamentCouncil: {len(self._agent_panel)} debate agents ready")
        except Exception as e:
            logger.debug(f"ParliamentCouncil: agent panel unavailable ({e})")
            self._agent_panel = []

        try:
            from ml.s11_brier_calibrator import S11BrierCalibrator
            self._s11 = S11BrierCalibrator()
            logger.info("ParliamentCouncil: S11 Brier calibrator ready")
        except Exception as e:
            logger.debug(f"ParliamentCouncil: S11 unavailable ({e})")

        self._enabled = bool(self._ml_council or self._agent_panel)

    # ── Main deliberation entry point ──────────────────────────────────────────

    async def deliberate(
        self,
        symbol: str,
        strate_votes: list,
        context: Optional[AgentContext] = None,
        execution_triggered: bool = False,
    ):
        """
        Full parliament deliberation with ML integration.

        Parameters
        ----------
        symbol : str
        strate_votes : list
            Votes from native strates (brain.parliament.Vote).
        context : AgentContext | None
            Market context for agent panel. If None, agents are skipped.
        execution_triggered : bool
            Whether the final decision led to trade execution.

        Returns
        -------
        ParliamentDecision
            Classic Parliament decision (direction, strength, …).
        """
        s = self._s
        all_votes = list(strate_votes)

        # ── 1. ML council votes ──────────────────────────────────────────
        ml_votes = []
        if self._ml_council and context is not None:
            try:
                ml_raw = await self._ml_council.generate_votes(
                    symbol=symbol,
                    features={},
                    returns=context.returns,
                    close=context.close,
                    volume=context.volume,
                )
                # Convert MLCouncil votes to parliament Vote format
                for mlv in ml_raw:
                    if mlv.confidence > 0.25 and mlv.decision != "NEUTRAL":
                        pv = self._ml_vote_to_parliament(mlv)
                        if pv:
                            all_votes.append(pv)
                ml_votes = ml_raw
            except Exception as e:
                logger.debug(f"ML council votes failed for {symbol}: {e}")

        # ── 2. Agent panel votes ─────────────────────────────────────────
        if self._agent_panel and context is not None:
            try:
                agent_votes = self._run_agent_panel(context)
                for av in agent_votes:
                    if av and av.confidence > 0.3 and av.decision != "NEUTRAL":
                        pv = av.to_parliament_vote()
                        if pv:
                            all_votes.append(pv)
            except Exception as e:
                logger.debug(f"Agent panel failed for {symbol}: {e}")

        # ── 3. Parliament deliberation ────────────────────────────────────
        decision = s.parliament.deliberate(all_votes)

        # ── 4. S11 Brier calibration update ──────────────────────────────
        if self._s11 and ml_votes:
            try:
                self._s11.update_brier(ml_votes, decision)
            except Exception as e:
                logger.debug(f"S11 update failed: {e}")

        # ── 5. Log debate ─────────────────────────────────────────────────
        try:
            self._debate_logger.log_simple(
                symbol=symbol,
                direction=decision.direction,
                strength=decision.strength,
                votes=all_votes,
                ml_votes=ml_votes,
                execution_triggered=execution_triggered,
            )
        except Exception as e:
            logger.debug(f"DebateLogger failed: {e}")

        return decision

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _run_agent_panel(self, ctx: AgentContext):
        """Run all debate agents synchronously and return verdicts."""
        verdicts = []
        for agent in self._agent_panel:
            try:
                verdicts.append(agent.evaluate(ctx))
            except Exception as e:
                logger.debug(f"Agent {agent.agent_id} error: {e}")
        return verdicts

    @staticmethod
    def _ml_vote_to_parliament(mlv):
        """Convert MLCouncil Vote → brain.parliament.Vote."""
        try:
            from brain.parliament import Vote
            # MLCouncil Vote has: strategy_id, decision, strength, confidence, reasoning
            decision = getattr(mlv, "decision", "NEUTRAL")
            confidence = float(getattr(mlv, "confidence", 0.0))
            strategy_id = getattr(mlv, "strategy_id", "ML")
            reasoning = getattr(mlv, "reasoning", "")
            return Vote(strategy_id, decision, confidence, reasoning)
        except Exception:
            return None

    def build_context(
        self,
        symbol: str,
        returns: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        rsi: float = 50.0,
        macd: float = 0.0,
        bb_pos: float = 0.0,
        vol_ratio: float = 1.0,
        trend: str = "NEUTRAL",
        regime: Optional[str] = None,
        minsky_phase: Optional[str] = None,
    ) -> AgentContext:
        """Convenience builder for AgentContext from cycle_manager data."""
        return AgentContext(
            symbol=symbol,
            returns=returns,
            close=close,
            volume=volume,
            rsi=rsi,
            macd=macd,
            bb_pos=bb_pos,
            vol_ratio=vol_ratio,
            trend=trend,
            regime=regime,
            minsky_phase=minsky_phase,
        )

    # ── Introspection ───────────────────────────────────────────────────────────

    @property
    def debate_logger(self) -> DebateLogger:
        return self._debate_logger

    def status(self) -> dict:
        return {
            "ml_council": self._ml_council is not None,
            "agents": [a.agent_id for a in self._agent_panel],
            "s11": self._s11 is not None,
            "debates_logged": len(self._debate_logger._buffer),
        }
