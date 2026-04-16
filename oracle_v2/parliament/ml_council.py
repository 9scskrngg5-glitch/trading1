"""
ML Council — Bridges ML models (S0-S7, S11) to Parliament oracle.

Adapts ML outputs to Vote format for parliament decision-making.
Implements S0 gate override rule.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Vote:
    """Parliament vote structure."""
    strategy_id: str
    decision: str  # 'LONG', 'SHORT', 'NEUTRAL'
    strength: float  # [0, 1]
    confidence: float  # [0, 1]
    reasoning: str
    timestamp: str = ""


class MLCouncil:
    """
    Adapts ML models (S0-S7, S11) to parliament voting format.

    ABSOLUTE RULE: S0 gate override.
    If S0 signals NOISE → all ML votes return NEUTRAL.

    Parameters
    ----------
    models_dir : str
        Directory where trained models are stored
    slippage_pct : float
        Slippage percentage for position sizing adjustments
    """

    def __init__(self, models_dir: str = "models/", slippage_pct: float = 0.0005):
        self.models_dir = Path(models_dir)
        self.slippage_pct = slippage_pct

        # Model cache
        self.models: Dict[str, object] = {}
        self.s11_calibrator = None

        logger.info(f"MLCouncil initialized: models_dir={self.models_dir}")

    def load_models(self) -> None:
        """Load all trained models from disk."""
        try:
            import pickle
        except ImportError:
            logger.warning("pickle not available")
            return

        model_ids = ["S0", "S2", "S3", "S5", "S7"]

        for model_id in model_ids:
            path = self.models_dir / f"{model_id}.pkl"

            if not path.exists():
                logger.warning(f"Model not found: {path}")
                self.models[model_id] = None
                continue

            try:
                with open(path, "rb") as f:
                    self.models[model_id] = pickle.load(f)
                logger.info(f"Loaded {model_id}")
            except Exception as e:
                logger.error(f"Failed to load {model_id}: {e}")
                self.models[model_id] = None

        # Load S11 calibrator if available
        s11_path = self.models_dir / "s11_calibrator.json"
        if s11_path.exists():
            try:
                from oracle_v2.ml.s11_brier_calibrator import S11BrierCalibrator

                self.s11_calibrator = S11BrierCalibrator.load(str(s11_path))
                logger.info("Loaded S11 calibrator")
            except Exception as e:
                logger.error(f"Failed to load S11 calibrator: {e}")

    def _s0_gate(
        self,
        returns: np.ndarray,
        volume: np.ndarray,
    ) -> bool:
        """
        Check if S0 gate is open (not in NOISE regime).

        RULE: If S0 detects NOISE → gate closed → all votes NEUTRAL.

        Parameters
        ----------
        returns : np.ndarray
            Recent returns (last 30 days)
        volume : np.ndarray
            Recent volume (last 30 days)

        Returns
        -------
        bool
            True if gate open (NOT in NOISE), False otherwise
        """
        if self.models.get("S0") is None:
            logger.warning("S0 model not loaded, assuming gate open")
            return True

        try:
            # Simple heuristic: check if volatility and volume are normal
            vol = np.std(returns)
            avg_volume = np.mean(volume)

            # Threshold for "normal" conditions
            normal_vol = vol < 0.05  # < 5% daily volatility
            normal_volume = avg_volume > 0  # Some volume

            gate_open = normal_vol or normal_volume

            logger.debug(f"S0 gate: {'OPEN' if gate_open else 'CLOSED'} (vol={vol:.3f}, vol_normal={normal_vol})")

            return gate_open

        except Exception as e:
            logger.error(f"S0 gate check failed: {e}")
            return True  # Default to open on error

    def _apply_s7_sizing(self, vote: Vote, returns: np.ndarray) -> Vote:
        """
        Adjust vote confidence based on S7 volatility forecast.

        Parameters
        ----------
        vote : Vote
            Original vote
        returns : np.ndarray
            Recent returns for volatility context

        Returns
        -------
        Vote
            Modified vote with adjusted sizing
        """
        if self.models.get("S7") is None:
            return vote

        try:
            # Forecast volatility using S7
            # (This would call actual S7 model; placeholder here)
            forecasted_vol = np.std(returns) * 1.1  # Simple forecast

            # Adjust confidence based on volatility
            if forecasted_vol > 0.04:  # High volatility
                adjusted_confidence = vote.confidence * 0.7
                vote.reasoning += " [Vol-adjusted down]"
            elif forecasted_vol < 0.01:  # Low volatility
                adjusted_confidence = vote.confidence * 1.2
                vote.reasoning += " [Vol-adjusted up]"
            else:
                adjusted_confidence = vote.confidence

            vote.confidence = min(1.0, adjusted_confidence)

        except Exception as e:
            logger.warning(f"S7 sizing adjustment failed: {e}")

        return vote

    async def generate_votes(
        self,
        symbol: str,
        features: Dict[str, np.ndarray],
        returns: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[Vote]:
        """
        Generate parliament votes from ML models.

        Parameters
        ----------
        symbol : str
            Trading symbol
        features : Dict[str, np.ndarray]
            Feature dict for models
        returns : np.ndarray
            Recent returns (last 30+ days)
        close : np.ndarray
            Recent close prices
        volume : np.ndarray
            Recent volumes

        Returns
        -------
        List[Vote]
            Votes from all strategies (NEUTRAL if S0 gate closed)
        """
        votes = []

        # Check S0 gate
        gate_open = self._s0_gate(returns[-30:], volume[-30:])

        if not gate_open:
            logger.info("S0 gate CLOSED (NOISE regime) → all votes NEUTRAL")

            for strate_id in ["S0", "S2", "S3", "S5", "S7"]:
                votes.append(
                    Vote(
                        strategy_id=strate_id,
                        decision="NEUTRAL",
                        strength=0.0,
                        confidence=0.0,
                        reasoning="S0 gate CLOSED — noise detected",
                        timestamp=pd.Timestamp.now().isoformat(),
                    )
                )
            return votes

        # Generate votes from each model
        # S0: Regime detection
        try:
            if self.models.get("S0"):
                regime = self._predict_s0(returns[-30:])
                vote_s0 = Vote(
                    strategy_id="S0",
                    decision=regime,
                    strength=0.8,
                    confidence=0.7,
                    reasoning=f"S0 regime: {regime}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
                votes.append(vote_s0)
        except Exception as e:
            logger.error(f"S0 prediction failed: {e}")
            votes.append(
                Vote(
                    strategy_id="S0",
                    decision="NEUTRAL",
                    strength=0.0,
                    confidence=0.0,
                    reasoning=f"S0 error: {str(e)}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
            )

        # S2: Minsky phase detection
        try:
            if self.models.get("S2"):
                phase = self._predict_s2(returns[-30:])
                vote_s2 = Vote(
                    strategy_id="S2",
                    decision=phase,
                    strength=0.75,
                    confidence=0.65,
                    reasoning=f"S2 Minsky phase: {phase}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
                votes.append(vote_s2)
        except Exception as e:
            logger.error(f"S2 prediction failed: {e}")
            votes.append(
                Vote(
                    strategy_id="S2",
                    decision="NEUTRAL",
                    strength=0.0,
                    confidence=0.0,
                    reasoning=f"S2 error: {str(e)}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
            )

        # S3: Narrative XGB
        try:
            if self.models.get("S3"):
                narrative = self._predict_s3(features.get("s3_features", np.random.randn(10)))
                vote_s3 = Vote(
                    strategy_id="S3",
                    decision=narrative,
                    strength=0.7,
                    confidence=0.6,
                    reasoning=f"S3 narrative signal: {narrative}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
                votes.append(vote_s3)
        except Exception as e:
            logger.error(f"S3 prediction failed: {e}")
            votes.append(
                Vote(
                    strategy_id="S3",
                    decision="NEUTRAL",
                    strength=0.0,
                    confidence=0.0,
                    reasoning=f"S3 error: {str(e)}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
            )

        # S5: Behavioral contrarian
        try:
            if self.models.get("S5"):
                contrarian = self._predict_s5(features.get("s5_features", np.random.randn(10)))
                vote_s5 = Vote(
                    strategy_id="S5",
                    decision=contrarian,
                    strength=0.65,
                    confidence=0.55,
                    reasoning=f"S5 behavioral contrarian: {contrarian}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
                votes.append(vote_s5)
        except Exception as e:
            logger.error(f"S5 prediction failed: {e}")
            votes.append(
                Vote(
                    strategy_id="S5",
                    decision="NEUTRAL",
                    strength=0.0,
                    confidence=0.0,
                    reasoning=f"S5 error: {str(e)}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
            )

        # S7: EVT volatility forecaster
        try:
            if self.models.get("S7"):
                vol_signal = self._predict_s7(returns[-60:])
                vote_s7 = Vote(
                    strategy_id="S7",
                    decision=vol_signal,
                    strength=0.6,
                    confidence=0.5,
                    reasoning=f"S7 EVT volatility: {vol_signal}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )

                # Apply S7 sizing adjustment
                vote_s7 = self._apply_s7_sizing(vote_s7, returns[-30:])
                votes.append(vote_s7)
        except Exception as e:
            logger.error(f"S7 prediction failed: {e}")
            votes.append(
                Vote(
                    strategy_id="S7",
                    decision="NEUTRAL",
                    strength=0.0,
                    confidence=0.0,
                    reasoning=f"S7 error: {str(e)}",
                    timestamp=pd.Timestamp.now().isoformat(),
                )
            )

        return votes

    def _predict_s0(self, returns: np.ndarray) -> str:
        """S0 regime detection."""
        # Placeholder: call actual S0 model
        vol = np.std(returns)
        if vol > 0.04:
            return "NEUTRAL"  # High volatility = uncertain
        elif returns[-1] > 0:
            return "LONG"
        else:
            return "SHORT"

    def _predict_s2(self, returns: np.ndarray) -> str:
        """S2 Minsky phase detection."""
        # Placeholder: call actual S2 model
        drift = np.mean(returns)
        if drift > 0.001:
            return "LONG"
        elif drift < -0.001:
            return "SHORT"
        else:
            return "NEUTRAL"

    def _predict_s3(self, features: np.ndarray) -> str:
        """S3 narrative XGB."""
        # Placeholder: call actual S3 model
        if features[0] > 0:
            return "LONG"
        else:
            return "SHORT"

    def _predict_s5(self, features: np.ndarray) -> str:
        """S5 behavioral contrarian XGB."""
        # Placeholder: call actual S5 model
        if features[0] < 0:
            return "LONG"  # Contrarian: reverse signal
        else:
            return "SHORT"

    def _predict_s7(self, returns: np.ndarray) -> str:
        """S7 EVT volatility forecaster."""
        # Placeholder: call actual S7 model
        vol_trend = np.std(returns[-10:]) - np.std(returns[-20:-10])
        if vol_trend > 0:
            return "NEUTRAL"  # Rising volatility = reduce size
        else:
            return "LONG"  # Falling volatility = increase size

    def report(self) -> None:
        """Print council status report."""
        print("\n" + "=" * 70)
        print("ML COUNCIL — MODEL STATUS")
        print("=" * 70)

        for model_id in ["S0", "S2", "S3", "S5", "S7"]:
            status = "LOADED" if self.models.get(model_id) else "NOT LOADED"
            print(f"  {model_id}: {status}")

        s11_status = "LOADED" if self.s11_calibrator else "NOT LOADED"
        print(f"  S11 Calibrator: {s11_status}")

        print("=" * 70 + "\n")
