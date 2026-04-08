"""
Modèles de données pour l'apprentissage machine inter-agents.
Chaque agent maintient une AgentMemory persistée dans le vault Obsidian.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .orders import OrderSide


class ExitReason(str, Enum):
    STOP_LOSS  = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIMEOUT    = "timeout"
    MANUAL     = "manual"


class MarketRegime(str, Enum):
    BULL    = "bull"
    BEAR    = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"


# ── Résultat d'un trade clôturé ──────────────────────────────────────────────

@dataclass
class TradeOutcome:
    """
    Enregistrement complet d'un trade du début à la fin.
    Produit par RiskAgent quand une position est clôturée.
    Transmis au LearningEngine pour l'apprentissage.
    """
    order_id:   str
    asset:      str
    side:       OrderSide
    entry_price: float
    exit_price:  float
    stop_loss:   float
    take_profit: float
    quantity:    float
    entry_time:  datetime
    exit_time:   datetime
    exit_reason: ExitReason
    exchange:    str

    # Contexte des signaux au moment de l'entrée
    tech_signal:    dict = field(default_factory=dict)
    fund_signal:    dict = field(default_factory=dict)
    confidence:     int  = 0
    regime:         MarketRegime = MarketRegime.SIDEWAYS

    # Calculé automatiquement
    pnl_pct:        float = 0.0
    pnl_usd:        float = 0.0
    is_win:         bool  = False
    duration_hours: float = 0.0
    max_favorable:  float = 0.0   # meilleur P&L non réalisé pendant le trade (%)
    max_adverse:    float = 0.0   # pire P&L non réalisé (drawdown intra-trade %)

    def __post_init__(self):
        direction = 1 if self.side == OrderSide.BUY else -1
        self.pnl_pct = direction * (self.exit_price - self.entry_price) / self.entry_price * 100
        self.pnl_usd = self.pnl_pct / 100 * self.entry_price * self.quantity
        self.is_win  = self.pnl_pct > 0
        self.duration_hours = (self.exit_time - self.entry_time).total_seconds() / 3600

    def to_dict(self) -> dict:
        return {
            "order_id":      self.order_id,
            "asset":         self.asset,
            "side":          self.side.value,
            "entry_price":   self.entry_price,
            "exit_price":    self.exit_price,
            "stop_loss":     self.stop_loss,
            "take_profit":   self.take_profit,
            "quantity":      self.quantity,
            "entry_time":    self.entry_time.isoformat(),
            "exit_time":     self.exit_time.isoformat(),
            "exit_reason":   self.exit_reason.value,
            "exchange":      self.exchange,
            "pnl_pct":       round(self.pnl_pct, 4),
            "pnl_usd":       round(self.pnl_usd, 2),
            "is_win":        self.is_win,
            "duration_hours":round(self.duration_hours, 2),
            "confidence":    self.confidence,
            "regime":        self.regime.value,
            "max_favorable": self.max_favorable,
            "max_adverse":   self.max_adverse,
        }


# ── Performance par indicateur ────────────────────────────────────────────────

@dataclass
class IndicatorStats:
    """
    Statistiques Bayésiennes pour un indicateur donné.
    Mise à jour à chaque résultat de trade.
    """
    name:       str
    timeframe:  str
    asset:      str

    total_signals: int   = 0
    wins:          int   = 0
    losses:        int   = 0
    total_pnl_pct: float = 0.0
    avg_win_pct:   float = 0.0
    avg_loss_pct:  float = 0.0

    # Poids adaptatif (0.0 → 1.0), normalisé par le LearningEngine
    weight: float = 1.0

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_signals, 1)

    @property
    def profit_factor(self) -> float:
        gross_profit = self.wins * abs(self.avg_win_pct)
        gross_loss   = self.losses * abs(self.avg_loss_pct)
        return gross_profit / max(gross_loss, 0.001)

    @property
    def expectancy(self) -> float:
        """Espérance mathématique par trade (en % du capital)."""
        return self.win_rate * self.avg_win_pct - (1 - self.win_rate) * abs(self.avg_loss_pct)

    def bayesian_update(self, is_win: bool, pnl_pct: float, alpha: float = 0.1):
        """
        Mise à jour en ligne via EMA (Exponential Moving Average).
        alpha : taux d'apprentissage (0.05 = lent, 0.2 = rapide)
        """
        self.total_signals += 1
        if is_win:
            self.wins += 1
            self.avg_win_pct = (1 - alpha) * self.avg_win_pct + alpha * pnl_pct
        else:
            self.losses += 1
            self.avg_loss_pct = (1 - alpha) * self.avg_loss_pct + alpha * pnl_pct
        self.total_pnl_pct += pnl_pct

    def to_dict(self) -> dict:
        return {
            "name":           self.name,
            "timeframe":      self.timeframe,
            "asset":          self.asset,
            "total_signals":  self.total_signals,
            "wins":           self.wins,
            "losses":         self.losses,
            "win_rate":       round(self.win_rate, 3),
            "profit_factor":  round(self.profit_factor, 2),
            "expectancy":     round(self.expectancy, 4),
            "avg_win_pct":    round(self.avg_win_pct, 4),
            "avg_loss_pct":   round(self.avg_loss_pct, 4),
            "total_pnl_pct":  round(self.total_pnl_pct, 3),
            "weight":         round(self.weight, 4),
        }


# ── Mémoire persistante d'un agent ───────────────────────────────────────────

@dataclass
class AgentMemory:
    """
    État appris d'un agent — persisté dans vault/config/{agent}_memory.md.
    Rechargé au démarrage pour reprendre là où on s'est arrêté.
    """
    agent_name:     str
    version:        int   = 1
    total_trades:   int   = 0
    total_wins:     int   = 0
    total_pnl_usd:  float = 0.0
    total_pnl_pct:  float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct:float = 0.0
    current_streak: int   = 0    # >0 = wins consécutifs, <0 = losses
    last_updated:   str   = ""

    # Poids des indicateurs (clé = "indicator:timeframe:asset")
    indicator_weights: dict[str, float] = field(default_factory=dict)

    # Paramètres adaptatifs (SL multiplier, TP ratio, confidence floor, etc.)
    adaptive_params: dict[str, float] = field(default_factory=lambda: {
        "sl_atr_multiplier":     2.0,     # Optimise par backtest 90j
        "tp_rr_ratio":           3.0,     # Optimise par backtest 90j
        "confidence_floor":      55.0,
        "tech_weight":           0.60,
        "fund_weight":           0.40,
        "learning_rate":         0.10,
        "regime_sensitivity":    0.5,
        "leverage":              1.0,     # Levier appris en paper (1x = pas de levier)
    })

    # Paramètres par régime de marché (bull/bear/sideways/volatile)
    # Chaque régime a ses propres SL/TP/confidence_floor appris séparément
    regime_params: dict[str, dict] = field(default_factory=lambda: {
        "bull":     {"sl_atr_multiplier": 2.0, "tp_rr_ratio": 3.5, "confidence_floor": 50.0, "leverage": 1.5},
        "bear":     {"sl_atr_multiplier": 1.5, "tp_rr_ratio": 2.5, "confidence_floor": 65.0, "leverage": 1.0},
        "sideways": {"sl_atr_multiplier": 2.0, "tp_rr_ratio": 3.0, "confidence_floor": 55.0, "leverage": 1.0},
        "volatile": {"sl_atr_multiplier": 2.5, "tp_rr_ratio": 2.0, "confidence_floor": 70.0, "leverage": 0.5},
    })

    # Statistiques par asset
    asset_stats: dict[str, dict] = field(default_factory=dict)

    # Statistiques par indicateur
    indicator_stats: dict[str, dict] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return self.total_wins / max(self.total_trades, 1)

    @property
    def sharpe_approx(self) -> float:
        """Sharpe approximatif basé sur les stats globales."""
        if self.total_trades < 5:
            return 0.0
        avg_return = self.total_pnl_pct / self.total_trades
        return avg_return / max(abs(self.worst_trade_pct) * 0.5, 0.01)

    def to_frontmatter(self) -> dict:
        return {
            "agent":         self.agent_name,
            "version":       self.version,
            "total_trades":  self.total_trades,
            "total_wins":    self.total_wins,
            "win_rate":      round(self.win_rate, 3),
            "total_pnl_usd": round(self.total_pnl_usd, 2),
            "sharpe_approx": round(self.sharpe_approx, 3),
            "last_updated":  self.last_updated,
            "tags":          ["config", "ml", "memory", self.agent_name.lower()],
        }

    @classmethod
    def default(cls, agent_name: str) -> "AgentMemory":
        """Mémoire initiale (première exécution)."""
        m = cls(agent_name=agent_name)
        m.last_updated = datetime.now(timezone.utc).isoformat()
        return m


# ── Résultat de l'analyse contrefactuelle ────────────────────────────────────

@dataclass
class CounterfactualResult:
    """
    "Qu'est-ce qui aurait marché ?"
    Calculé par LearningEngine pour chaque trade perdant.
    """
    trade_outcome: TradeOutcome

    # Résultat réel
    actual_pnl_pct:  float = 0.0
    actual_exit:     str   = ""

    # Meilleure configuration trouvée
    best_sl_mult:    float = 0.0
    best_tp_ratio:   float = 0.0
    best_pnl_pct:    float = 0.0
    best_exit:       str   = ""
    improvement_pct: float = 0.0    # gain potentiel vs résultat réel

    # Ce que l'agent apprend
    lesson:          str   = ""
    param_updates:   dict  = field(default_factory=dict)

    @property
    def was_avoidable(self) -> bool:
        """Le trade aurait pu être gagnant avec des params différents."""
        return self.best_pnl_pct > 0 and self.actual_pnl_pct < 0

    def to_markdown(self) -> str:
        arrow = "✅" if self.was_avoidable else "❌"
        return f"""### Analyse Contrefactuelle {arrow}

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `{self.trade_outcome.stop_loss:.4f}` | `{self.best_sl_mult}× ATR` |
| TP Ratio | `réel` | `1:{self.best_tp_ratio}` |
| P&L résultat | `{self.actual_pnl_pct:+.2f}%` | `{self.best_pnl_pct:+.2f}%` |
| Amélioration possible | — | `{self.improvement_pct:+.2f}%` |

**Leçon apprise :** {self.lesson}
"""
