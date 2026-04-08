"""
Modèles de signaux inter-agents.
TechnicalSignal (Agent 1) + FundamentalSignal (Agent 2) → CombinedSignal (Agent 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketType(str, Enum):
    CRYPTO = "crypto"
    FOREX  = "forex"


# ── Signal Technique (Agent 1) ────────────────────────────────────────────────

@dataclass
class TechnicalSignal:
    """
    Produit par TechnicalAgent.
    Publié sur le canal  signals:technical.
    """
    asset:         str
    signal:        SignalType
    confidence:    int            # 0–100
    timeframe:     str            # "1h" | "4h" | "1d"
    market:        MarketType = MarketType.CRYPTO

    rsi:           Optional[float] = None
    macd_hist:     Optional[float] = None
    bb_position:   Optional[float] = None  # 0 = bande basse, 1 = bande haute
    volume_ratio:  Optional[float] = None  # vs moyenne 20 périodes
    pattern:       Optional[str]  = None   # "double_bottom", "head_shoulders", …

    entry_price:   Optional[float] = None  # prix courant au moment de l'analyse
    atr:           Optional[float] = None  # Average True Range

    # Données enrichies (MarketDataManager)
    ob_imbalance:  Optional[float] = None  # order book imbalance : +1=full bid, -1=full ask
    vwap_dist_pct: Optional[float] = None  # distance % au VWAP intraday
    trend_slope:   Optional[float] = None  # pente de tendance sur 20 périodes (% par candle)

    # Order Flow / CVD
    cvd:                Optional[float] = None  # Cumulative Volume Delta
    delta_5m:           Optional[float] = None  # Delta volume 5 min
    delta_divergence:   Optional[bool]  = None  # True si prix et delta divergent
    absorption:         Optional[bool]  = None  # True si gros volume, peu de mouvement

    # Anchored VWAP
    avwap_dist_pct:     Optional[float] = None  # distance % à l'Anchored VWAP

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "type":          "technical_signal",
            "asset":         self.asset,
            "signal":        self.signal.value,
            "confidence":    self.confidence,
            "timeframe":     self.timeframe,
            "market":        self.market.value,
            "rsi":           self.rsi,
            "macd_hist":     self.macd_hist,
            "bb_position":   self.bb_position,
            "volume_ratio":  self.volume_ratio,
            "pattern":       self.pattern,
            "entry_price":   self.entry_price,
            "atr":           self.atr,
            "ob_imbalance":      self.ob_imbalance,
            "vwap_dist_pct":     self.vwap_dist_pct,
            "trend_slope":       self.trend_slope,
            "cvd":               self.cvd,
            "delta_5m":          self.delta_5m,
            "delta_divergence":  self.delta_divergence,
            "absorption":        self.absorption,
            "avwap_dist_pct":    self.avwap_dist_pct,
            "timestamp":         self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TechnicalSignal":
        return cls(
            asset         = d["asset"],
            signal        = SignalType(d["signal"]),
            confidence    = d["confidence"],
            timeframe     = d["timeframe"],
            market        = MarketType(d.get("market", "crypto")),
            rsi           = d.get("rsi"),
            macd_hist     = d.get("macd_hist"),
            bb_position   = d.get("bb_position"),
            volume_ratio  = d.get("volume_ratio"),
            pattern       = d.get("pattern"),
            entry_price   = d.get("entry_price"),
            atr           = d.get("atr"),
            ob_imbalance      = d.get("ob_imbalance"),
            vwap_dist_pct     = d.get("vwap_dist_pct"),
            trend_slope       = d.get("trend_slope"),
            cvd               = d.get("cvd"),
            delta_5m          = d.get("delta_5m"),
            delta_divergence  = d.get("delta_divergence"),
            absorption        = d.get("absorption"),
            avwap_dist_pct    = d.get("avwap_dist_pct"),
        )


# ── Signal Fondamental (Agent 2) ──────────────────────────────────────────────

@dataclass
class FundamentalSignal:
    """
    Produit par FundamentalAgent.
    Publié sur le canal  signals:fundamental.
    """
    asset:           str
    sentiment_score: int           # −100 à +100
    signal:          SignalType
    confidence:      int           # 0–100
    news_count:      int = 0

    key_events:      list[str] = field(default_factory=list)
    social_score:    Optional[float] = None
    onchain_metrics: Optional[dict] = None  # crypto uniquement
    macro_events:    Optional[list[str]] = None  # forex uniquement

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "type":            "fundamental_signal",
            "asset":           self.asset,
            "sentiment_score": self.sentiment_score,
            "signal":          self.signal.value,
            "confidence":      self.confidence,
            "news_count":      self.news_count,
            "key_events":      self.key_events,
            "social_score":    self.social_score,
            "onchain_metrics": self.onchain_metrics,
            "macro_events":    self.macro_events,
            "timestamp":       self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FundamentalSignal":
        return cls(
            asset           = d["asset"],
            sentiment_score = d["sentiment_score"],
            signal          = SignalType(d["signal"]),
            confidence      = d["confidence"],
            news_count      = d.get("news_count", 0),
            key_events      = d.get("key_events", []),
            social_score    = d.get("social_score"),
            onchain_metrics = d.get("onchain_metrics"),
            macro_events    = d.get("macro_events"),
        )


# ── Signal Combiné (sortie Agent 3) ──────────────────────────────────────────

@dataclass
class CombinedSignal:
    """
    Convergence des signaux technique + fondamental.
    Utilisé par RiskAgent pour valider un ordre.
    """
    asset:               str
    final_signal:        SignalType
    combined_confidence: int          # 0–100 (moyenne pondérée)
    technical_weight:    float = 0.60
    fundamental_weight:  float = 0.40

    technical:   Optional[TechnicalSignal]   = None
    fundamental: Optional[FundamentalSignal] = None

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_signals(
        cls,
        tech: TechnicalSignal,
        fund: FundamentalSignal,
        tech_weight: float = 0.60,
    ) -> Optional["CombinedSignal"]:
        """
        Retourne un CombinedSignal si les deux agents sont alignés,
        None si les signaux divergent ou si la confiance combinée < 55.
        """
        if tech.signal != fund.signal or tech.signal == SignalType.NEUTRAL:
            return None

        combined = int(tech.confidence * tech_weight + fund.confidence * (1 - tech_weight))
        if combined < 55:
            return None

        return cls(
            asset               = tech.asset,
            final_signal        = tech.signal,
            combined_confidence = combined,
            technical_weight    = tech_weight,
            fundamental_weight  = 1 - tech_weight,
            technical           = tech,
            fundamental         = fund,
        )
