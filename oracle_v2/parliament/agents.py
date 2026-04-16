"""
Parliament Agents — Specialized agent definitions for the debate council.

Each agent has a distinct epistemic role in the parliament deliberation:
  - RegimeAgent      : Market regime awareness (S0-based)
  - MomentumAgent    : Price momentum and trend continuation
  - RiskAgent        : Risk / volatility / tail events (S7-based)
  - ContraryAgent    : Devil's advocate — behavioral biases (S5-based)
  - MacroAgent       : Macro cycles, Minsky phases (S2-based)
  - NarrativeAgent   : Narrative / sentiment scoring (S3-based)

All agents implement the same interface:
    agent.evaluate(context: AgentContext) -> AgentVerdict

No external LLM required — pure Python scoring with optional ML model backing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

logger = logging.getLogger("ORACLE.Parliament.Agents")


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Input context passed to every agent during deliberation.

    Fields
    ------
    symbol : str
    returns : np.ndarray         Recent log-returns (shape: [N])
    close   : np.ndarray         Recent close prices (shape: [N])
    volume  : np.ndarray         Recent volumes (shape: [N])
    rsi     : float              RSI(14) scalar
    macd    : float              MACD line scalar
    bb_pos  : float              Bollinger band position [-1, 1]
    vol_ratio: float             Volume ratio vs 20-day average
    trend   : str                "UP" | "DOWN" | "NEUTRAL"
    regime  : Optional[str]      S0 regime label if available
    minsky_phase: Optional[str]  S2 phase label if available
    features: dict               Any extra features (open-ended)
    """
    symbol: str = ""
    returns: np.ndarray = field(default_factory=lambda: np.zeros(30))
    close: np.ndarray = field(default_factory=lambda: np.zeros(30))
    volume: np.ndarray = field(default_factory=lambda: np.zeros(30))
    rsi: float = 50.0
    macd: float = 0.0
    bb_pos: float = 0.0
    vol_ratio: float = 1.0
    trend: str = "NEUTRAL"
    regime: Optional[str] = None
    minsky_phase: Optional[str] = None
    features: dict = field(default_factory=dict)


@dataclass
class AgentVerdict:
    """
    Structured verdict from a single agent.

    decision   : "LONG" | "SHORT" | "NEUTRAL"
    confidence : [0, 1]
    reasoning  : Human-readable rationale
    agent_id   : identifier
    weight     : Parliament weight assigned to this agent type
    """
    agent_id: str
    decision: str
    confidence: float
    reasoning: str
    weight: float = 1.0

    def to_parliament_vote(self):
        """Convert to the brain.parliament.Vote format."""
        try:
            from brain.parliament import Vote
            return Vote(
                self.agent_id,
                self.decision,
                self.confidence * self.weight,
                self.reasoning,
            )
        except ImportError:
            # Fallback plain tuple for tests
            return (self.agent_id, self.decision, self.confidence * self.weight, self.reasoning)


# ── Base agent ─────────────────────────────────────────────────────────────────

class BaseAgent:
    """Abstract parliament agent."""

    agent_id: str = "BASE"
    default_weight: float = 1.0

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        raise NotImplementedError

    def _verdict(self, decision: str, confidence: float, reasoning: str) -> AgentVerdict:
        return AgentVerdict(
            agent_id=self.agent_id,
            decision=decision,
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=reasoning,
            weight=self.default_weight,
        )


# ── Specialized agents ────────────────────────────────────────────────────────

class RegimeAgent(BaseAgent):
    """
    Regime gatekeeper — only bullish/bearish in non-noise regimes.
    Backed by S0 HMM when available.
    """
    agent_id = "REGIME"
    default_weight = 1.5   # High weight — regime determines context

    def __init__(self, s0_model=None):
        self._s0 = s0_model

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        # Use pre-computed regime from context if available
        if ctx.regime:
            r = ctx.regime.upper()
            if "NOISE" in r:
                return self._verdict("NEUTRAL", 0.9, "S0: NOISE regime → gate closed")
            if "TREND" in r:
                direction = "LONG" if np.mean(ctx.returns[-5:]) > 0 else "SHORT"
                return self._verdict(direction, 0.7, f"S0: TREND regime → {direction}")
            if "REVERT" in r:
                # Mean-reversion: fade recent move
                direction = "SHORT" if np.mean(ctx.returns[-3:]) > 0 else "LONG"
                return self._verdict(direction, 0.6, f"S0: REVERT regime → contrarian {direction}")

        # Heuristic fallback
        vol = float(np.std(ctx.returns[-20:])) if len(ctx.returns) >= 20 else 0.02
        if vol > 0.05:
            return self._verdict("NEUTRAL", 0.6, f"High volatility ({vol:.1%}) — uncertain regime")
        trend_returns = np.mean(ctx.returns[-5:]) if len(ctx.returns) >= 5 else 0.0
        if trend_returns > 0.002:
            return self._verdict("LONG", 0.55, f"Mild uptrend ({trend_returns:.3%}/bar)")
        if trend_returns < -0.002:
            return self._verdict("SHORT", 0.55, f"Mild downtrend ({trend_returns:.3%}/bar)")
        return self._verdict("NEUTRAL", 0.4, "Neutral regime (low signal)")


class MomentumAgent(BaseAgent):
    """
    Momentum / trend-following agent.
    Uses RSI + MACD + Bollinger Band position.
    """
    agent_id = "MOMENTUM_ML"
    default_weight = 1.2

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        score = 0.0
        signals = []

        # RSI
        if ctx.rsi < 30:
            score += 0.3
            signals.append(f"RSI={ctx.rsi:.0f}(oversold)")
        elif ctx.rsi > 70:
            score -= 0.3
            signals.append(f"RSI={ctx.rsi:.0f}(overbought)")
        elif ctx.rsi > 55:
            score += 0.15
            signals.append(f"RSI={ctx.rsi:.0f}(bullish)")
        elif ctx.rsi < 45:
            score -= 0.15
            signals.append(f"RSI={ctx.rsi:.0f}(bearish)")

        # MACD
        if ctx.macd > 0:
            score += 0.2
            signals.append(f"MACD={ctx.macd:.4f}(+)")
        elif ctx.macd < 0:
            score -= 0.2
            signals.append(f"MACD={ctx.macd:.4f}(-)")

        # Bollinger
        if ctx.bb_pos > 0.8:
            score -= 0.1  # Overbought zone
            signals.append("BB=upper")
        elif ctx.bb_pos < -0.8:
            score += 0.1  # Oversold zone
            signals.append("BB=lower")

        # Volume confirmation
        if ctx.vol_ratio > 1.5:
            score *= 1.2  # amplify with volume
            signals.append(f"vol×{ctx.vol_ratio:.1f}")

        confidence = min(0.9, abs(score) + 0.1)
        direction = "LONG" if score > 0 else "SHORT" if score < 0 else "NEUTRAL"
        if abs(score) < 0.1:
            direction = "NEUTRAL"
            confidence = 0.2

        return self._verdict(direction, confidence, " | ".join(signals) or "no signal")


class RiskAgent(BaseAgent):
    """
    Risk / tail-event agent.
    Reduces position sizing in high-risk environments.
    """
    agent_id = "RISK_EVT"
    default_weight = 0.8

    def __init__(self, s7_model=None):
        self._s7 = s7_model

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        returns = ctx.returns
        if len(returns) < 10:
            return self._verdict("NEUTRAL", 0.3, "Insufficient data for risk assessment")

        vol_recent = float(np.std(returns[-10:]))
        vol_long = float(np.std(returns[-30:])) if len(returns) >= 30 else vol_recent
        vol_rising = vol_recent > vol_long * 1.3

        # Tail risk: max single-bar loss
        max_loss = float(np.min(returns[-20:])) if len(returns) >= 20 else -0.01

        if vol_rising and max_loss < -0.03:
            return self._verdict("NEUTRAL", 0.75, f"CRISIS: vol rising ({vol_recent:.1%}) + tail={max_loss:.1%}")
        if vol_recent > 0.04:
            return self._verdict("NEUTRAL", 0.6, f"STRESSED: vol={vol_recent:.1%}")

        # Normal regime — mild directional bias
        recent_return = float(np.sum(returns[-5:])) if len(returns) >= 5 else 0.0
        if recent_return > 0.01:
            return self._verdict("LONG", 0.45, f"CALM: positive momentum {recent_return:.2%}")
        if recent_return < -0.01:
            return self._verdict("SHORT", 0.45, f"CALM: negative momentum {recent_return:.2%}")
        return self._verdict("NEUTRAL", 0.3, f"CALM: vol={vol_recent:.1%} — no edge")


class ContraryAgent(BaseAgent):
    """
    Contrarian / behavioral bias detector.
    Fades crowded positions, anchoring, herding.
    Backed by S5 XGBoost when available.
    """
    agent_id = "CONTRARY_BEH"
    default_weight = 0.9

    def __init__(self, s5_model=None):
        self._s5 = s5_model

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        returns = ctx.returns
        if len(returns) < 20:
            return self._verdict("NEUTRAL", 0.2, "Insufficient history")

        # Disposition effect proxy: long streak of gains
        streak = 0
        for r in reversed(returns[-10:]):
            if r > 0:
                streak += 1
            else:
                break

        # Herding proxy: RSI extreme + high volume
        herding = (ctx.rsi > 75 or ctx.rsi < 25) and ctx.vol_ratio > 1.8

        if streak >= 6 and ctx.rsi > 65:
            return self._verdict("SHORT", 0.6, f"Disposition effect: {streak}-bar gain streak + RSI={ctx.rsi:.0f}")
        if streak == 0 and ctx.rsi < 35:
            # Loss streak — possible capitulation bottom
            loss_streak = sum(1 for r in returns[-10:] if r < 0)
            return self._verdict("LONG", 0.55, f"Capitulation signal: {loss_streak}-bar losses + RSI={ctx.rsi:.0f}")
        if herding:
            direction = "SHORT" if ctx.rsi > 50 else "LONG"
            return self._verdict(direction, 0.5, f"Herding detected: RSI={ctx.rsi:.0f} vol×{ctx.vol_ratio:.1f} — contrarian")

        return self._verdict("NEUTRAL", 0.25, "No strong behavioral signal")


class MacroAgent(BaseAgent):
    """
    Macro / Minsky cycle agent.
    Interprets macro cycle phase to bias direction.
    """
    agent_id = "MACRO_MINSKY"
    default_weight = 1.1

    PHASE_BIAS = {
        "DISPLACEMENT":    ("LONG",    0.65, "Displacement phase — early bull"),
        "EUPHORIA":        ("NEUTRAL",  0.55, "Euphoria — late cycle, reduce risk"),
        "MANIA":           ("SHORT",   0.50, "Mania phase — overextension"),
        "DISTRESS":        ("SHORT",   0.70, "Distress — selling pressure"),
        "PANIC":           ("LONG",    0.45, "Panic — possible capitulation bottom"),
    }

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        phase = (ctx.minsky_phase or "").upper()
        if phase in self.PHASE_BIAS:
            direction, confidence, reasoning = self.PHASE_BIAS[phase]
            return self._verdict(direction, confidence, f"Minsky: {reasoning}")

        # Fallback: trend direction
        if ctx.trend == "UP":
            return self._verdict("LONG", 0.40, "Macro: uptrend without phase info")
        if ctx.trend == "DOWN":
            return self._verdict("SHORT", 0.40, "Macro: downtrend without phase info")
        return self._verdict("NEUTRAL", 0.25, "Macro: no phase signal")


class NarrativeAgent(BaseAgent):
    """
    Narrative / sentiment agent.
    Score based on volume, price action, and optional S3 backing.
    """
    agent_id = "NARRATIVE_NLP"
    default_weight = 0.85

    def __init__(self, s3_model=None):
        self._s3 = s3_model

    def evaluate(self, ctx: AgentContext) -> AgentVerdict:
        signals = []
        score = 0.0

        # Volume surge = narrative momentum
        if ctx.vol_ratio > 2.0:
            score += 0.25 if ctx.trend == "UP" else -0.25
            signals.append(f"vol_surge×{ctx.vol_ratio:.1f}")

        # Price acceleration
        if len(ctx.returns) >= 5:
            accel = float(np.mean(ctx.returns[-3:])) - float(np.mean(ctx.returns[-10:-3]))
            if abs(accel) > 0.002:
                score += accel * 50  # scale
                signals.append(f"accel={accel:.3f}")

        # BB breakout
        if ctx.bb_pos > 0.9:
            score += 0.2
            signals.append("BB_breakout_up")
        elif ctx.bb_pos < -0.9:
            score -= 0.2
            signals.append("BB_breakout_down")

        confidence = min(0.85, abs(score) * 1.5 + 0.1)
        direction = "LONG" if score > 0.1 else "SHORT" if score < -0.1 else "NEUTRAL"

        return self._verdict(direction, confidence, " | ".join(signals) or "quiet narrative")


# ── Agent registry ─────────────────────────────────────────────────────────────

ALL_AGENTS: list[type[BaseAgent]] = [
    RegimeAgent,
    MomentumAgent,
    RiskAgent,
    ContraryAgent,
    MacroAgent,
    NarrativeAgent,
]


def build_agent_panel(
    s0_model=None,
    s3_model=None,
    s5_model=None,
    s7_model=None,
) -> list[BaseAgent]:
    """Instantiate the full panel of debate agents."""
    return [
        RegimeAgent(s0_model=s0_model),
        MomentumAgent(),
        RiskAgent(s7_model=s7_model),
        ContraryAgent(s5_model=s5_model),
        MacroAgent(),
        NarrativeAgent(s3_model=s3_model),
    ]
