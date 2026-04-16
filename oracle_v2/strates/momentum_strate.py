"""
Momentum Strate — RSI, MACD, momentum multi-timeframe.
"""
from .base_strate import BaseStrate, StrateResult
import logging

logger = logging.getLogger("ORACLE.Momentum")


class MomentumStrate(BaseStrate):
    def __init__(
        self,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
    ):
        super().__init__("MOMENTUM")
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def analyze(self, data: dict) -> StrateResult:
        features = data.get("features", {})
        rsi = features.get("rsi", 50.0)
        macd = features.get("macd", 0.0)
        macd_signal = features.get("macd_signal", 0.0)
        volume_ratio = features.get("volume_ratio", 1.0)
        cascade = data.get("cascade", {})
        dominant_trend = cascade.get("dominant_trend", "SIDEWAYS")
        trend_confidence = cascade.get("confidence", 0.5)

        score_long = 0.0
        score_short = 0.0
        reasons = []

        if rsi < self.rsi_oversold:
            score_long += 0.35
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > self.rsi_overbought:
            score_short += 0.35
            reasons.append(f"RSI overbought ({rsi:.1f})")

        if macd > macd_signal and macd > 0:
            score_long += 0.30
            reasons.append("MACD bullish crossover")
        elif macd < macd_signal and macd < 0:
            score_short += 0.30
            reasons.append("MACD bearish crossover")

        if dominant_trend == "UP":
            score_long += 0.20 * trend_confidence
        elif dominant_trend == "DOWN":
            score_short += 0.20 * trend_confidence

        if volume_ratio > 1.5:
            score_long *= 1.1
            score_short *= 1.1

        if score_long > score_short and score_long > 0.3:
            direction = "LONG"
            confidence = min(0.95, score_long)
        elif score_short > score_long and score_short > 0.3:
            direction = "SHORT"
            confidence = min(0.95, score_short)
        else:
            direction = "NEUTRAL"
            confidence = max(score_long, score_short)

        return StrateResult(
            strate_name=self.name,
            direction=direction,
            confidence=confidence,
            reasoning=" | ".join(reasons) if reasons else "Pas de signal momentum clair",
            signal_strength=max(score_long, score_short)
        )
