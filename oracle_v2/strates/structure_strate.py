"""
Structure Strate — Market Structure, Support/Resistance, Break of Structure.
Détecte HH/HL (bullish) et LH/LL (bearish).
"""
from .base_strate import BaseStrate, StrateResult
import logging

logger = logging.getLogger("ORACLE.Structure")


class StructureStrate(BaseStrate):
    def __init__(self, swing_lookback: int = 5):
        super().__init__("STRUCTURE")
        self.swing_lookback = swing_lookback

    def _find_swings(self, highs: list, lows: list) -> dict:
        swing_highs = []
        swing_lows = []
        lb = self.swing_lookback
        for i in range(lb, len(highs) - lb):
            if highs[i] == max(highs[i-lb:i+lb+1]):
                swing_highs.append((i, highs[i]))
            if lows[i] == min(lows[i-lb:i+lb+1]):
                swing_lows.append((i, lows[i]))
        return {"highs": swing_highs[-4:], "lows": swing_lows[-4:]}

    def _detect_structure(self, swings: dict) -> tuple:
        sh = [s[1] for s in swings["highs"]]
        sl = [s[1] for s in swings["lows"]]
        if len(sh) >= 2 and len(sl) >= 2:
            hh = sh[-1] > sh[-2]
            hl = sl[-1] > sl[-2]
            lh = sh[-1] < sh[-2]
            ll = sl[-1] < sl[-2]
            if hh and hl:
                return "BULLISH_STRUCTURE", 0.75
            elif lh and ll:
                return "BEARISH_STRUCTURE", 0.75
            elif hh and ll:
                return "CONSOLIDATION", 0.40
        return "NEUTRAL", 0.30

    def analyze(self, data: dict) -> StrateResult:
        ohlcv = data.get("ohlcv", [])
        if len(ohlcv) < 20:
            return StrateResult(self.name, "NEUTRAL", 0.0, "Données insuffisantes", 0.0)

        highs = [c["high"] if isinstance(c, dict) else c.high for c in ohlcv]
        lows = [c["low"] if isinstance(c, dict) else c.low for c in ohlcv]
        swings = self._find_swings(highs, lows)
        structure, confidence = self._detect_structure(swings)

        if structure == "BULLISH_STRUCTURE":
            return StrateResult(self.name, "LONG", confidence, "Structure HH/HL bullish confirmée", confidence)
        elif structure == "BEARISH_STRUCTURE":
            return StrateResult(self.name, "SHORT", confidence, "Structure LH/LL bearish confirmée", confidence)
        else:
            return StrateResult(self.name, "NEUTRAL", confidence, f"Structure: {structure}", confidence * 0.5)
