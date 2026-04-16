"""
AMD Strate — Accumulation / Manipulation / Distribution.
Détecte les phases Wyckoff via volume profile et price action.
"""
from .base_strate import BaseStrate, StrateResult
import logging

logger = logging.getLogger("ORACLE.AMD")


class AMDStrate(BaseStrate):
    """
    Détecte les phases AMD (Accumulation/Manipulation/Distribution).
    Wyckoff adapté aux marchés crypto 24/7.
    """

    def __init__(
        self,
        volume_spike_threshold: float = 2.0,
        manipulation_candle_ratio: float = 2.5
    ):
        super().__init__("AMD")
        self.volume_spike_threshold = volume_spike_threshold
        self.manipulation_candle_ratio = manipulation_candle_ratio

    def _detect_phase(self, ohlcv: list) -> tuple:
        if len(ohlcv) < 20:
            return "NEUTRAL", 0.0

        closes = [c["close"] if isinstance(c, dict) else c.close for c in ohlcv]
        volumes = [c["volume"] if isinstance(c, dict) else c.volume for c in ohlcv]
        highs = [c["high"] if isinstance(c, dict) else c.high for c in ohlcv]
        lows = [c["low"] if isinstance(c, dict) else c.low for c in ohlcv]

        recent = ohlcv[-5:]
        vol_ma = sum(volumes[-20:]) / 20
        recent_vol_list = [c["volume"] if isinstance(c, dict) else c.volume for c in recent]
        recent_vol = sum(recent_vol_list) / 5
        vol_ratio = recent_vol / vol_ma if vol_ma > 0 else 1.0

        price_range = max(closes[-20:]) - min(closes[-20:])
        avg_range = sum(h - l for h, l in zip(highs[-20:], lows[-20:])) / 20
        compression_ratio = avg_range / (price_range + 1e-10)

        if compression_ratio < 0.15 and vol_ratio < 1.2:
            return "ACCUMULATION", min(0.8, (1 - compression_ratio) * 2)

        if vol_ratio > self.volume_spike_threshold:
            close_change = (closes[-1] - closes[-5]) / closes[-5]
            if close_change > 0.02:
                return "MANIPULATION_UP", min(0.9, vol_ratio / 4)
            elif close_change < -0.02:
                return "MANIPULATION_DOWN", min(0.9, vol_ratio / 4)

        if vol_ratio > 1.5 and closes[-1] < closes[-5]:
            return "DISTRIBUTION", 0.6

        return "NEUTRAL", 0.3

    def analyze(self, data: dict) -> StrateResult:
        ohlcv = data.get("ohlcv", [])
        if not ohlcv:
            return StrateResult(self.name, "NEUTRAL", 0.0, "No OHLCV data", 0.0)

        phase, confidence = self._detect_phase(ohlcv)

        phase_map = {
            "ACCUMULATION": ("LONG", "Accumulation détectée — compression volume + range serré"),
            "MANIPULATION_UP": ("LONG", "Manipulation haussière — spike volume avec clôture haute"),
            "MANIPULATION_DOWN": ("SHORT", "Manipulation baissière — spike volume avec clôture basse"),
            "DISTRIBUTION": ("SHORT", "Distribution détectée — volume élevé avec clôture sous ouverture"),
            "NEUTRAL": ("NEUTRAL", "Pas de phase AMD claire"),
        }
        direction, reasoning = phase_map.get(phase, ("NEUTRAL", "Phase inconnue"))

        return StrateResult(
            strate_name=self.name,
            direction=direction,
            confidence=confidence,
            reasoning=reasoning,
            signal_strength=confidence,
            metadata={"phase": phase}
        )
