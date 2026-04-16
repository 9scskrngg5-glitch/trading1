"""
Association Cortex — Corrélation cross-asset et synthèse multi-signaux.
Équivalent cortex associatif : intègre plusieurs sources pour une décision unifiée.
"""
from dataclasses import dataclass
import logging

logger = logging.getLogger("ORACLE.AssociationCortex")

CORRELATION_MAP = {
    ("BTC", "ETH"): 0.85,
    ("BTC", "BNB"): 0.75,
    ("ETH", "BNB"): 0.70,
    ("BTC", "GOLD"): -0.30,
    ("BTC", "VIX"): -0.55,
    ("GOLD", "VIX"): 0.40,
    ("NIKKEI", "USD"): -0.60,
}


@dataclass
class CrossAssetSignal:
    primary_asset: str
    supporting_assets: list
    conflicting_assets: list
    correlation_score: float   # -1.0 à +1.0
    macro_alignment: bool


class AssociationCortex:
    """
    Analyse les corrélations cross-asset et filtre les faux signaux.
    Un signal BTC LONG confirmé par ETH LONG a plus de poids.
    """

    def get_correlation(self, asset1: str, asset2: str) -> float:
        key = (asset1, asset2)
        if key in CORRELATION_MAP:
            return CORRELATION_MAP[key]
        reverse = (asset2, asset1)
        if reverse in CORRELATION_MAP:
            return CORRELATION_MAP[reverse]
        return 0.0

    def analyze_cross_asset(
        self,
        primary: str,
        primary_direction: str,
        peer_signals: dict  # {"ETH": "LONG", "VIX": "UP", ...}
    ) -> CrossAssetSignal:
        supporting = []
        conflicting = []
        score = 0.0
        count = 0

        for peer, peer_dir in peer_signals.items():
            corr = self.get_correlation(primary, peer)
            if corr == 0:
                continue
            expected_dir = primary_direction
            if corr < 0:
                expected_dir = "SHORT" if primary_direction == "LONG" else "LONG"
            if peer_dir == expected_dir:
                supporting.append(peer)
                score += abs(corr)
            else:
                conflicting.append(peer)
                score -= abs(corr)
            count += 1

        normalized_score = score / count if count > 0 else 0.0
        macro_assets = {"VIX", "DXY", "GOLD", "NIKKEI"}
        macro_alignment = all(a in supporting for a in macro_assets if a in peer_signals)

        return CrossAssetSignal(
            primary_asset=primary,
            supporting_assets=supporting,
            conflicting_assets=conflicting,
            correlation_score=normalized_score,
            macro_alignment=macro_alignment
        )

    def adjust_confidence(self, base_confidence: float, cross_signal: CrossAssetSignal) -> float:
        """
        Ajuste la confiance selon la corrélation cross-asset.
        Score +0.5 → +10% confiance, -0.5 → -15% confiance.
        """
        adjustment = cross_signal.correlation_score * 0.20
        adjusted = base_confidence + adjustment
        if cross_signal.macro_alignment:
            adjusted += 0.05
        return max(0.0, min(1.0, adjusted))
