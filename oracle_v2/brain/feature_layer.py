"""
Feature Layer — Extraction features + cascade multi-timeframe 5m→15m→1h.
Équivalent cortex d'association primaire.
"""
from dataclasses import dataclass
from typing import Optional
import logging
import time

logger = logging.getLogger("ORACLE.FeatureLayer")


@dataclass
class FeatureVector:
    symbol: str
    timeframe: str
    rsi: float
    macd: float
    macd_signal: float
    ema_fast: float
    ema_slow: float
    atr: float
    volume_ratio: float   # volume / volume_ma
    price_change_pct: float
    bb_position: float    # position dans les bandes de Bollinger [-1, +1]
    trend: str            # "UP", "DOWN", "SIDEWAYS"
    timestamp: float


class FeatureLayer:
    """
    Calcule les features techniques à partir des OHLCV.
    Cascade multi-timeframe : 5m (bruit) → 15m (structure) → 1h (tendance).
    """

    def compute_rsi(self, closes: list, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 1e-10
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def compute_ema(self, closes: list, period: int) -> float:
        if len(closes) < period:
            return closes[-1] if closes else 0.0
        k = 2 / (period + 1)
        ema = sum(closes[:period]) / period
        for price in closes[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def compute_atr(self, ohlcv_list: list, period: int = 14) -> float:
        if len(ohlcv_list) < 2:
            return 0.0
        trs = []
        for i in range(1, len(ohlcv_list)):
            prev_close = ohlcv_list[i-1].close
            cur = ohlcv_list[i]
            tr = max(
                cur.high - cur.low,
                abs(cur.high - prev_close),
                abs(cur.low - prev_close)
            )
            trs.append(tr)
        return sum(trs[-period:]) / min(len(trs), period)

    def compute_macd(self, closes: list, fast: int = 12, slow: int = 26, signal_period: int = 9) -> tuple:
        """
        Calcule (macd_line, signal_line) pour la dernière bougie.
        Construit la série MACD complète (EMA12−EMA26 par bougie) puis applique EMA9.
        """
        if len(closes) < slow + signal_period:
            return 0.0, 0.0
        macd_series = []
        for i in range(slow - 1, len(closes)):
            ef = self.compute_ema(closes[:i + 1], fast)
            es = self.compute_ema(closes[:i + 1], slow)
            macd_series.append(ef - es)
        if len(macd_series) < signal_period:
            return macd_series[-1] if macd_series else 0.0, 0.0
        return macd_series[-1], self.compute_ema(macd_series, signal_period)

    def compute_bollinger_position(self, closes: list, period: int = 20) -> float:
        if len(closes) < period:
            return 0.0
        recent = closes[-period:]
        mean = sum(recent) / period
        variance = sum((x - mean) ** 2 for x in recent) / period
        std = variance ** 0.5
        if std == 0:
            return 0.0
        return (closes[-1] - mean) / (2 * std)

    def extract(self, ohlcv_list: list, symbol: str, timeframe: str) -> Optional[FeatureVector]:
        if len(ohlcv_list) < 30:
            return None

        closes = [c.close for c in ohlcv_list]
        volumes = [c.volume for c in ohlcv_list]

        rsi = self.compute_rsi(closes)
        ema_fast = self.compute_ema(closes, 12)
        ema_slow = self.compute_ema(closes, 26)
        macd, macd_signal = self.compute_macd(closes)
        atr = self.compute_atr(ohlcv_list)
        vol_ma = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
        volume_ratio = volumes[-1] / vol_ma if vol_ma else 1.0
        price_change = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] else 0.0
        bb_pos = self.compute_bollinger_position(closes)

        if ema_fast > ema_slow and rsi > 50:
            trend = "UP"
        elif ema_fast < ema_slow and rsi < 50:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"

        return FeatureVector(
            symbol=symbol, timeframe=timeframe,
            rsi=rsi, macd=macd, macd_signal=macd_signal,
            ema_fast=ema_fast, ema_slow=ema_slow, atr=atr,
            volume_ratio=volume_ratio, price_change_pct=price_change,
            bb_position=bb_pos, trend=trend, timestamp=time.time()
        )

    def cascade_analysis(self, features_by_tf: dict) -> dict:
        """
        Cascade 5m → 15m → 1h.
        La tendance 1h prime sur 15m qui prime sur 5m.
        """
        trend_scores = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0}
        weights = {"1h": 3, "15m": 2, "5m": 1}

        for tf, fv in features_by_tf.items():
            if fv:
                w = weights.get(tf, 1)
                trend_scores[fv.trend] += w

        dominant = max(trend_scores, key=trend_scores.get)
        total = sum(trend_scores.values())
        confidence = trend_scores[dominant] / total if total > 0 else 0.0

        return {
            "dominant_trend": dominant,
            "confidence": confidence,
            "scores": trend_scores,
            "features": features_by_tf
        }
