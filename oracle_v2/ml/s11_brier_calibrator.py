"""
S11 Brier Score Calibrator — Meta-model for parliament voting weights.

Tracks prediction accuracy of each strategy and dynamically reweights votes
based on rolling Brier Score performance.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import deque
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrierTracking:
    """Rolling Brier Score tracker for a strategy."""
    window_size: int = 30
    scores: deque = field(default_factory=lambda: deque(maxlen=30))
    weight: float = 1.0
    last_updated: str = ""

    def add_score(self, score: float) -> None:
        """Add Brier score (range [0, 1], lower is better)."""
        self.scores.append(score)

    def mean_score(self) -> float:
        """Return mean Brier score."""
        if not self.scores:
            return 0.5  # Neutral if no data
        return float(np.mean(list(self.scores)))

    def confidence(self) -> float:
        """Return confidence based on recency and consistency."""
        if len(self.scores) < 5:
            return 0.3  # Low confidence with few samples

        mean_score = self.mean_score()
        std_score = float(np.std(list(self.scores)))

        # Lower Brier = better confidence
        confidence = 1.0 - mean_score - std_score * 0.1
        return max(0.0, min(1.0, confidence))


class S11BrierCalibrator:
    """
    Meta-model for parliament voting weights using Brier Score.

    Monitors each strategy's prediction accuracy and adjusts weights dynamically.
    Lower Brier Score (better accuracy) → higher weight.

    Parameters
    ----------
    strate_ids : List[str]
        Strategy IDs to track, default ['S0', 'S2', 'S3', 'S5', 'S7']
    min_weight : float
        Minimum weight bound, default 0.1
    max_weight : float
        Maximum weight bound, default 3.0
    """

    STRATE_IDS = ["S0", "S2", "S3", "S5", "S7"]

    def __init__(
        self,
        strate_ids: List[str] = None,
        min_weight: float = 0.1,
        max_weight: float = 3.0,
    ):
        self.strate_ids = strate_ids or self.STRATE_IDS
        self.min_weight = min_weight
        self.max_weight = max_weight

        # Initialize tracking for each strategy
        self.tracking: Dict[str, BrierTracking] = {
            strate_id: BrierTracking(window_size=30) for strate_id in self.strate_ids
        }

        logger.info(f"S11BrierCalibrator initialized for {len(self.strate_ids)} strategies")

    def update(
        self,
        strate_id: str,
        prediction_proba: float,
        actual_outcome: int,
    ) -> None:
        """
        Update tracking for a strategy's prediction.

        Parameters
        ----------
        strate_id : str
            Strategy ID
        prediction_proba : float
            Predicted probability [0, 1]
        actual_outcome : int
            Actual outcome {0, 1} (binary)
        """
        if strate_id not in self.tracking:
            logger.warning(f"Unknown strategy {strate_id}")
            return

        # Compute Brier Score: (prediction - actual)^2
        brier_score = (prediction_proba - actual_outcome) ** 2

        self.tracking[strate_id].add_score(brier_score)
        self.tracking[strate_id].last_updated = pd.Timestamp.now().isoformat()

        logger.debug(f"{strate_id}: Brier={brier_score:.4f}, rolling_mean={self.tracking[strate_id].mean_score():.4f}")

        # Recompute weights after each update
        self._recompute_weights()

    def _recompute_weights(self) -> None:
        """
        Recompute voting weights based on Brier scores.

        Lower Brier Score (better accuracy) → higher weight.
        Weights are normalized and bounded.
        """
        brier_scores = {}

        for strate_id, tracking in self.tracking.items():
            score = tracking.mean_score()
            brier_scores[strate_id] = score

        if not brier_scores:
            return

        # Invert Brier scores to weights (lower score = higher weight)
        # Use exponential inverse: weight ∝ exp(-brier)
        max_score = max(brier_scores.values())
        min_score = min(brier_scores.values())

        # Normalize to [0, 1]
        normalized_scores = {}
        if max_score > min_score:
            for strate_id, score in brier_scores.items():
                normalized_scores[strate_id] = (max_score - score) / (max_score - min_score)
        else:
            # All scores equal
            normalized_scores = {strate_id: 1.0 for strate_id in brier_scores}

        # Apply bounds
        for strate_id, norm_score in normalized_scores.items():
            # Scale to [min_weight, max_weight]
            weight = self.min_weight + norm_score * (self.max_weight - self.min_weight)
            self.tracking[strate_id].weight = weight

        logger.debug(f"Weights recomputed: {self.get_weights()}")

    def get_weights(self) -> Dict[str, float]:
        """Return current voting weights."""
        return {strate_id: tracking.weight for strate_id, tracking in self.tracking.items()}

    def parliament_vote(self, signals: Dict[str, float]) -> float:
        """
        Compute weighted parliament vote.

        Parameters
        ----------
        signals : Dict[str, float]
            {strate_id: signal_value} where signal ∈ [-1, 1]

        Returns
        -------
        float
            Weighted vote ∈ [-1, 1]
        """
        weights = self.get_weights()

        weighted_sum = 0.0
        weight_sum = 0.0

        for strate_id, signal in signals.items():
            if strate_id in weights:
                weight = weights[strate_id]
                weighted_sum += signal * weight
                weight_sum += weight

        if weight_sum == 0:
            return 0.0

        return weighted_sum / weight_sum

    def get_parliament_decision(
        self,
        signals: Dict[str, float],
        quorum: float = 0.6,
    ) -> Tuple[str, float, str]:
        """
        Convert weighted vote to parliament decision.

        Parameters
        ----------
        signals : Dict[str, float]
            {strate_id: signal_value}
        quorum : float
            Voting threshold (e.g., 0.6 means 60% agreement needed)

        Returns
        -------
        Tuple[str, float, str]
            (decision, strength, reasoning) where:
            - decision ∈ {'LONG', 'SHORT', 'NEUTRAL'}
            - strength ∈ [0, 1]
            - reasoning is a brief explanation
        """
        vote = self.parliament_vote(signals)
        strength = abs(vote)

        # Check quorum (fraction of weights agreeing)
        agreeing_weight = sum(
            self.tracking[s_id].weight
            for s_id, sig in signals.items()
            if s_id in self.tracking and np.sign(sig) == np.sign(vote)
        )
        total_weight = sum(t.weight for t in self.tracking.values())

        quorum_reached = agreeing_weight / total_weight >= quorum if total_weight > 0 else False

        if strength < 0.1:
            decision = "NEUTRAL"
            reasoning = "Low consensus across parliament"
        elif vote > 0:
            decision = "LONG" if quorum_reached else "NEUTRAL"
            reasoning = f"Bullish consensus {strength:.1%}" if quorum_reached else "Bullish but quorum not reached"
        else:
            decision = "SHORT" if quorum_reached else "NEUTRAL"
            reasoning = f"Bearish consensus {strength:.1%}" if quorum_reached else "Bearish but quorum not reached"

        return decision, strength, reasoning

    def save(self, filepath: str) -> None:
        """
        Save calibrator state to JSON.

        Parameters
        ----------
        filepath : str
            Path to save JSON file
        """
        state = {
            "strate_ids": self.strate_ids,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "tracking": {
                strate_id: {
                    "scores": list(tracking.scores),
                    "weight": tracking.weight,
                    "last_updated": tracking.last_updated,
                }
                for strate_id, tracking in self.tracking.items()
            },
        }

        try:
            with open(filepath, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved S11 calibrator to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save S11 calibrator: {e}")

    @classmethod
    def load(cls, filepath: str) -> "S11BrierCalibrator":
        """
        Load calibrator state from JSON.

        Parameters
        ----------
        filepath : str
            Path to load JSON file

        Returns
        -------
        S11BrierCalibrator
            Loaded calibrator
        """
        try:
            with open(filepath, "r") as f:
                state = json.load(f)

            calibrator = cls(
                strate_ids=state.get("strate_ids"),
                min_weight=state.get("min_weight", 0.1),
                max_weight=state.get("max_weight", 3.0),
            )

            # Restore tracking state
            for strate_id, tracking_data in state.get("tracking", {}).items():
                if strate_id in calibrator.tracking:
                    scores = tracking_data.get("scores", [])
                    calibrator.tracking[strate_id].scores = deque(scores, maxlen=30)
                    calibrator.tracking[strate_id].weight = tracking_data.get("weight", 1.0)
                    calibrator.tracking[strate_id].last_updated = tracking_data.get("last_updated", "")

            logger.info(f"Loaded S11 calibrator from {filepath}")
            return calibrator

        except Exception as e:
            logger.error(f"Failed to load S11 calibrator: {e}")
            return cls()

    def report(self) -> None:
        """Print formatted status report."""
        print("\n" + "=" * 70)
        print("S11 BRIER CALIBRATOR — PARLIAMENT VOTING WEIGHTS")
        print("=" * 70)

        for strate_id in self.strate_ids:
            tracking = self.tracking[strate_id]
            print(f"\n{strate_id}:")
            print(f"  Brier Score (rolling): {tracking.mean_score():.4f}")
            print(f"  Samples: {len(tracking.scores)}/{tracking.window_size}")
            print(f"  Weight: {tracking.weight:.2f}x")
            print(f"  Confidence: {tracking.confidence():.1%}")

            if tracking.last_updated:
                print(f"  Last Updated: {tracking.last_updated}")

        print("\n" + "-" * 70)
        print("VOTING WEIGHTS SUMMARY:")
        weights = self.get_weights()
        total_weight = sum(weights.values())
        for strate_id, weight in weights.items():
            pct = 100 * weight / total_weight if total_weight > 0 else 0
            print(f"  {strate_id}: {weight:.2f}x ({pct:.1f}%)")

        print("=" * 70 + "\n")

    def get_status_emojis(self) -> Dict[str, str]:
        """Return emoji status indicators."""
        emojis = {}
        for strate_id, tracking in self.tracking.items():
            confidence = tracking.confidence()
            if confidence > 0.7:
                emojis[strate_id] = "🟢"  # Good
            elif confidence > 0.4:
                emojis[strate_id] = "🟡"  # Moderate
            else:
                emojis[strate_id] = "🔴"  # Poor
        return emojis
