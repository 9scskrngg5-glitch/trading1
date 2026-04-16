"""
Parlement ORACLE v2 — Vote pondéré Hebbian entre strates.
Chaque strate est un député dont le poids évolue selon sa performance.
"""
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.Parliament")


@dataclass
class Vote:
    strate_name: str
    direction: str        # "LONG", "SHORT", "NEUTRAL"
    confidence: float     # 0.0 - 1.0
    reasoning: str
    polymarket_signal: Optional[str] = None


@dataclass
class ParliamentDecision:
    direction: str
    strength: float       # Force du consensus 0.0 - 1.0
    votes: list
    dissenting: list
    polymarket_alignment: bool


class HebbianWeightManager:
    """Poids évolutifs par performance réelle, persistés en SQLite entre redémarrages."""

    def __init__(self, strate_names: list, db_path: str = None):
        self.weights = {s: 1.0 for s in strate_names}
        self.history = {s: [] for s in strate_names}
        self.decay = 0.92
        self.boost = 1.08
        self.min_weight = 0.1
        self.max_weight = 3.0
        self._repo = None

        if db_path:
            try:
                from db.repositories import HebbianRepository
                self._repo = HebbianRepository(db_path=db_path)
                saved = self._repo.load_all()
                for s in strate_names:
                    if s in saved:
                        self.weights[s] = saved[s]
                if saved:
                    logger.info(f"Hebbian: {len(saved)} poids restaurés depuis DB")
            except Exception as e:
                logger.warning(f"Hebbian: impossible de charger DB ({e}) — poids=1.0 par défaut")

    def update(self, strate: str, was_profitable: bool, pnl_pct: float) -> None:
        if strate not in self.weights:
            return
        self.history[strate].append(pnl_pct)
        if was_profitable:
            self.weights[strate] = min(self.max_weight, self.weights[strate] * self.boost)
        else:
            self.weights[strate] = max(self.min_weight, self.weights[strate] * self.decay)
        logger.debug(f"Hebbian update [{strate}]: {'✅' if was_profitable else '❌'} → weight={self.weights[strate]:.3f}")
        if self._repo:
            try:
                self._repo.save_weight(strate, self.weights[strate])
            except Exception as e:
                logger.debug(f"Hebbian: échec sauvegarde DB ({e})")

    def get_weight(self, strate: str) -> float:
        return self.weights.get(strate, 1.0)


class Parliament:
    def __init__(self, quorum: float = 0.6):
        self.quorum = quorum
        self.weight_manager: Optional[HebbianWeightManager] = None

    def set_weight_manager(self, wm: HebbianWeightManager) -> None:
        self.weight_manager = wm

    def deliberate(self, votes: list) -> ParliamentDecision:
        if not votes:
            return ParliamentDecision("NEUTRAL", 0.0, [], [], False)

        weighted_long = 0.0
        weighted_short = 0.0
        total_weight = 0.0

        for vote in votes:
            w = self.weight_manager.get_weight(vote.strate_name) if self.weight_manager else 1.0
            weighted_vote = vote.confidence * w
            total_weight += w

            if vote.direction == "LONG":
                weighted_long += weighted_vote
            elif vote.direction == "SHORT":
                weighted_short += weighted_vote

        if total_weight == 0:
            return ParliamentDecision("NEUTRAL", 0.0, votes, [], False)

        long_ratio = weighted_long / total_weight
        short_ratio = weighted_short / total_weight

        poly_vote = next((v for v in votes if v.strate_name == "POLYMARKET"), None)

        if long_ratio >= self.quorum:
            direction = "LONG"
            strength = long_ratio
            winning = [v for v in votes if v.direction == "LONG"]
            dissenting = [v for v in votes if v.direction != "LONG"]
            poly_alignment = poly_vote and poly_vote.direction == "LONG"
        elif short_ratio >= self.quorum:
            direction = "SHORT"
            strength = short_ratio
            winning = [v for v in votes if v.direction == "SHORT"]
            dissenting = [v for v in votes if v.direction != "SHORT"]
            poly_alignment = poly_vote and poly_vote.direction == "SHORT"
        else:
            direction = "NEUTRAL"
            strength = max(long_ratio, short_ratio)
            winning = votes
            dissenting = []
            poly_alignment = False

        logger.info(f"Parlement: {direction} ({strength:.1%}) — Quorum {'✅' if strength >= self.quorum else '❌'}")
        return ParliamentDecision(direction, strength, winning, dissenting, bool(poly_alignment))
