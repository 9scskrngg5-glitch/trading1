"""
Macro Strate — DXY, VIX, SKEW, Put/Call ratio.
Contexte macro pour filtrer les faux signaux techniques.
"""
from .base_strate import BaseStrate, StrateResult
import logging

logger = logging.getLogger("ORACLE.Macro")

VIX_FEAR_THRESHOLD = 25.0
VIX_EXTREME_THRESHOLD = 35.0
DXY_STRONG_THRESHOLD = 105.0


class MacroStrate(BaseStrate):
    def __init__(self):
        super().__init__("MACRO")

    def analyze(self, data: dict) -> StrateResult:
        macro = data.get("macro", {})
        if not macro:
            return StrateResult(self.name, "NEUTRAL", 0.3, "Pas de données macro", 0.0)

        vix = macro.get("VIX", 20.0)
        dxy = macro.get("DXY", 100.0)
        put_call = macro.get("PUT_CALL", 1.0)

        score_long = 0.0
        score_short = 0.0
        reasons = []

        if vix > VIX_EXTREME_THRESHOLD:
            score_long += 0.25
            reasons.append(f"VIX extrême ({vix:.1f}) → opportunité contrarian")
        elif vix > VIX_FEAR_THRESHOLD:
            score_short += 0.20
            reasons.append(f"VIX élevé ({vix:.1f}) → risk-off")
        elif vix < 15:
            score_long += 0.15
            reasons.append(f"VIX bas ({vix:.1f}) → risk-on")

        if dxy > DXY_STRONG_THRESHOLD:
            score_short += 0.20
            reasons.append(f"DXY fort ({dxy:.1f}) → pression baissière crypto")
        elif dxy < 100:
            score_long += 0.15
            reasons.append(f"DXY faible ({dxy:.1f}) → favorable crypto")

        if put_call > 1.3:
            score_long += 0.15
            reasons.append(f"Put/Call élevé ({put_call:.2f}) → contrarian long")
        elif put_call < 0.7:
            score_short += 0.15
            reasons.append(f"Put/Call bas ({put_call:.2f}) → contrarian short")

        if score_long > score_short and score_long > 0.25:
            direction = "LONG"
            confidence = min(0.85, score_long)
        elif score_short > score_long and score_short > 0.25:
            direction = "SHORT"
            confidence = min(0.85, score_short)
        else:
            direction = "NEUTRAL"
            confidence = 0.3

        return StrateResult(
            strate_name=self.name,
            direction=direction,
            confidence=confidence,
            reasoning=" | ".join(reasons) if reasons else "Macro neutre",
            signal_strength=max(score_long, score_short),
            metadata={"vix": vix, "dxy": dxy, "put_call": put_call}
        )
