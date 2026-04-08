"""
Modèles d'ordres.
ValidatedOrder (Agent 3 → Agent 4)  +  ExecutionReport (Agent 4 → Agent 3).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY  = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT  = "limit"


class OrderStatus(str, Enum):
    VALIDATED  = "validated"
    SUBMITTED  = "submitted"
    FILLED     = "filled"
    PARTIAL    = "partial"
    CANCELLED  = "cancelled"
    REJECTED   = "rejected"


# ── Ordre validé (Agent 3 → Agent 4) ─────────────────────────────────────────

@dataclass
class ValidatedOrder:
    """
    Produit par RiskAgent après convergence des signaux.
    Contient tous les paramètres de sizing + SL/TP.
    """
    asset:          str
    side:           OrderSide
    quantity:       float
    entry_price:    float
    stop_loss:      float
    take_profit:    float
    risk_amount_usd: float
    risk_percent:   float          # % du capital risqué
    confidence_score: int          # 0–100
    signal_sources: list[str]      # ["TechnicalAgent", "FundamentalAgent"]
    exchange:       str = "binance"
    order_type:     OrderType = OrderType.MARKET

    order_id: str = field(
        default_factory=lambda: f"ord_{uuid.uuid4().hex[:10]}"
    )
    status: OrderStatus = OrderStatus.VALIDATED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def risk_reward_ratio(self) -> float:
        """Ratio R:R théorique."""
        sl_dist = abs(self.entry_price - self.stop_loss)
        tp_dist = abs(self.take_profit - self.entry_price)
        return round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "type":             "validated_order",
            "order_id":         self.order_id,
            "asset":            self.asset,
            "side":             self.side.value,
            "order_type":       self.order_type.value,
            "quantity":         self.quantity,
            "entry_price":      self.entry_price,
            "stop_loss":        self.stop_loss,
            "take_profit":      self.take_profit,
            "risk_reward":      self.risk_reward_ratio,
            "risk_amount_usd":  self.risk_amount_usd,
            "risk_percent":     self.risk_percent,
            "confidence_score": self.confidence_score,
            "signal_sources":   self.signal_sources,
            "exchange":         self.exchange,
            "status":           self.status.value,
            "timestamp":        self.timestamp.isoformat(),
        }


# ── Rapport d'exécution (Agent 4 → Agent 3) ──────────────────────────────────

@dataclass
class ExecutionReport:
    """
    Produit par ExecutionAgent après placement de l'ordre.
    Contient le slippage réel et les frais de transaction.
    """
    order_id:        str
    asset:           str
    side:            OrderSide
    requested_price: float
    filled_price:    float
    quantity:        float
    fees:            float
    exchange:        str
    status:          OrderStatus

    slippage_bps: float = 0.0      # basis points (1 bps = 0.01%)
    exchange_order_id: Optional[str] = None

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_cost(self) -> float:
        return self.filled_price * self.quantity + self.fees

    @property
    def slippage_pct(self) -> float:
        return self.slippage_bps / 100

    def to_dict(self) -> dict:
        return {
            "type":              "execution_report",
            "order_id":          self.order_id,
            "asset":             self.asset,
            "side":              self.side.value,
            "requested_price":   self.requested_price,
            "filled_price":      self.filled_price,
            "quantity":          self.quantity,
            "fees":              self.fees,
            "slippage_bps":      round(self.slippage_bps, 2),
            "slippage_pct":      round(self.slippage_pct, 4),
            "total_cost":        round(self.total_cost, 6),
            "exchange":          self.exchange,
            "exchange_order_id": self.exchange_order_id,
            "status":            self.status.value,
            "timestamp":         self.timestamp.isoformat(),
        }
