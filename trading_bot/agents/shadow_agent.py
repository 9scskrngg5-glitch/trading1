"""
Agent 11 — Shadow Agent (R&D)
Système de shadow trading en parallèle pour tester des stratégies alternatives.

3 stratégies shadow parallèles :
- Shadow A : Aggressive  — confidence ≥ 60, SL 1.0×ATR, TP 1:3.0
- Shadow B : Conservative — confidence ≥ 75, SL 2.0×ATR, TP 1:2.0
- Shadow C : Trend-only  — confidence ≥ 65, uniquement en régime trending

Chaque stratégie maintient son propre P&L virtuel.
Publie les résultats sur shadow:result → MetaAgent adapte le système.
Vault : vault/experiments/
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)


# ── Structures de données ─────────────────────────────────────────────────────

@dataclass
class ShadowConfig:
    """Configuration d'une stratégie shadow."""
    name:               str
    min_confidence:     int
    sl_atr_multiplier:  float
    tp_rr_ratio:        float
    regime_filter:      str | None      # None = toutes régimes, "trending" = trending seulement
    risk_pct:           float = 1.5
    emoji:              str   = "🔬"


@dataclass
class ShadowTrade:
    """Trade virtuel en cours dans une stratégie shadow."""
    asset:         str
    direction:     str      # "buy" | "sell"
    entry_price:   float
    stop_loss:     float
    take_profit:   float
    confidence:    int
    regime:        str
    opened_at:     str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    risk_pct:      float = 1.5


@dataclass
class ShadowPortfolio:
    """Portfolio virtuel d'une stratégie shadow."""
    config:         ShadowConfig
    capital:        float
    initial_capital: float
    trades:         list[dict]    = field(default_factory=list)
    open_trades:    dict[str, ShadowTrade] = field(default_factory=dict)
    wins:           int = 0
    losses:         int = 0

    @property
    def total_trades(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def return_pct(self) -> float:
        return (self.capital / self.initial_capital - 1) * 100

    def score(self) -> float:
        """Score composite = return_pct × win_rate × log(total_trades+1)."""
        if self.total_trades < 3:
            return 0.0
        return self.return_pct * self.win_rate * math.log(self.total_trades + 1)


# ── Agent ────────────────────────────────────────────────────────────────────

class ShadowAgent(BaseAgent):
    """
    Agent R&D — Shadow trading en parallèle.

    Reçoit les mêmes signaux que le vrai pipeline mais les filtre
    différemment selon 3 stratégies alternatives, sans risquer de capital réel.
    Compare les performances et publie la meilleure stratégie vers MetaAgent.
    """

    STRATEGIES: list[ShadowConfig] = [
        ShadowConfig(
            name              = "ShadowA_Aggressive",
            min_confidence    = 60,
            sl_atr_multiplier = 1.0,
            tp_rr_ratio       = 3.0,
            regime_filter     = None,
            risk_pct          = 2.0,
            emoji             = "🚀",
        ),
        ShadowConfig(
            name              = "ShadowB_Conservative",
            min_confidence    = 75,
            sl_atr_multiplier = 2.0,
            tp_rr_ratio       = 2.0,
            regime_filter     = None,
            risk_pct          = 1.0,
            emoji             = "🛡️",
        ),
        ShadowConfig(
            name              = "ShadowC_TrendOnly",
            min_confidence    = 65,
            sl_atr_multiplier = 1.5,
            tp_rr_ratio       = 2.5,
            regime_filter     = "trending",
            risk_pct          = 1.5,
            emoji             = "📈",
        ),
    ]

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        config: dict,
        telegram=None,
    ):
        super().__init__("ShadowAgent", "experiments", bus, obsidian, config)
        self.telegram = telegram
        initial_cap   = float(config.get("capital_usd", 10_000))

        # Un portfolio par stratégie
        self._portfolios: dict[str, ShadowPortfolio] = {
            s.name: ShadowPortfolio(
                config          = s,
                capital         = initial_cap,
                initial_capital = initial_cap,
            )
            for s in self.STRATEGIES
        }

        # Régimes courants par asset (feed depuis RegimeAgent)
        self._regimes: dict[str, str] = {}

        # Tracking
        self._cycle_count: int = 0
        self._best_strategy: str | None = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "experiments").mkdir(exist_ok=True)
        logger.info(
            "[%s] Shadow mode actif | %d stratégies : %s",
            self.name,
            len(self.STRATEGIES),
            " | ".join(s.emoji + " " + s.name for s in self.STRATEGIES),
        )

    def _register_subscriptions(self) -> None:
        # Recevoir les signaux de convergence (mêmes que PredictAgent)
        self.bus.subscribe(CHANNELS["decisions"],     self._on_convergence_signal)
        # Recevoir les exécutions réelles pour simuler le résultat shadow
        self.bus.subscribe(CHANNELS["portfolio_update"], self._on_trade_closed)
        # Recevoir les régimes pour ShadowC
        self.bus.subscribe(CHANNELS["regime"],           self._on_regime_update)

    # ── Handlers bus ──────────────────────────────────────────────────────────

    async def _on_regime_update(self, data: dict) -> None:
        asset  = data.get("asset")
        regime = data.get("regime", "unknown")
        if asset:
            self._regimes[asset] = regime

    async def _on_convergence_signal(self, data: dict) -> None:
        """
        Reçoit un signal de convergence et l'évalue dans chaque portfolio shadow.
        Applique les règles de chaque stratégie indépendamment.
        """
        asset      = data.get("asset", "?")
        direction  = str(data.get("direction", "")).lower()
        confidence = int(data.get("confidence", 0))
        price      = float(data.get("price", 0.0))

        if not price or direction not in ("buy", "sell"):
            return

        current_regime = self._regimes.get(asset, "unknown")

        for portfolio in self._portfolios.values():
            cfg = portfolio.config

            # Filtrer par confiance minimale
            if confidence < cfg.min_confidence:
                continue

            # Filtrer par régime (ShadowC = trending only)
            if cfg.regime_filter == "trending":
                if current_regime not in ("trending_up", "trending_down"):
                    continue
                # Alignement direction / régime
                if current_regime == "trending_up"   and direction != "buy":
                    continue
                if current_regime == "trending_down" and direction != "sell":
                    continue

            # Un seul trade ouvert par asset par portfolio
            if asset in portfolio.open_trades:
                continue

            # Calculer SL/TP shadow
            atr_approx = price * 0.015   # ~1.5% ATR approx
            sl_dist    = cfg.sl_atr_multiplier * atr_approx
            tp_dist    = sl_dist * cfg.tp_rr_ratio

            if direction == "buy":
                sl = price - sl_dist
                tp = price + tp_dist
            else:
                sl = price + sl_dist
                tp = price - tp_dist

            portfolio.open_trades[asset] = ShadowTrade(
                asset       = asset,
                direction   = direction,
                entry_price = price,
                stop_loss   = sl,
                take_profit = tp,
                confidence  = confidence,
                regime      = current_regime,
                risk_pct    = cfg.risk_pct,
            )
            logger.debug(
                "[%s] %s %s OPEN %s @ %.4f | SL=%.4f TP=%.4f",
                self.name, cfg.emoji, cfg.name, asset, price, sl, tp,
            )

    async def _on_trade_closed(self, data: dict) -> None:
        """
        Quand un trade RÉEL se clôture, clôture aussi les trades shadow
        correspondants et calcule le P&L virtuel.
        """
        if data.get("type") != "trade_closed":
            return

        asset       = data.get("asset", "?")
        close_price = float(data.get("exit_price", 0.0) or data.get("price", 0.0))

        if not close_price:
            return

        for portfolio in self._portfolios.values():
            if asset not in portfolio.open_trades:
                continue

            trade = portfolio.open_trades.pop(asset)
            pnl   = self._compute_shadow_pnl(trade, close_price, portfolio)

            is_win = pnl > 0
            if is_win:
                portfolio.wins += 1
            else:
                portfolio.losses += 1

            portfolio.capital = max(portfolio.capital + pnl, 0.01)
            portfolio.trades.append({
                "asset":     asset,
                "direction": trade.direction,
                "pnl":       round(pnl, 2),
                "pnl_pct":   round((pnl / portfolio.initial_capital) * 100, 3),
                "is_win":    is_win,
                "regime":    trade.regime,
                "ts":        datetime.now(timezone.utc).isoformat(),
            })
            logger.debug(
                "[%s] %s %s CLOSE %s | P&L=%+.2f$ | WR=%.0f%%",
                self.name, portfolio.config.emoji, portfolio.config.name,
                asset, pnl, portfolio.win_rate * 100,
            )

    def _compute_shadow_pnl(
        self,
        trade: ShadowTrade,
        close_price: float,
        portfolio: ShadowPortfolio,
    ) -> float:
        """Calcule le P&L virtuel d'un trade shadow."""
        risk_usd = portfolio.capital * trade.risk_pct / 100
        entry    = trade.entry_price
        sl       = trade.stop_loss
        sl_dist  = abs(entry - sl)

        if sl_dist == 0:
            return 0.0

        if trade.direction == "buy":
            pnl_per_unit = close_price - entry
        else:
            pnl_per_unit = entry - close_price

        # Sizing en termes de risque
        qty    = risk_usd / sl_dist
        raw_pnl = pnl_per_unit * qty

        # Clip : un trade ne peut pas perdre plus que le risque défini
        return max(raw_pnl, -risk_usd)

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        self._cycle_count += 1

        # Calcul du ranking des stratégies
        ranking = sorted(
            self._portfolios.values(),
            key=lambda p: p.score(),
            reverse=True,
        )

        best    = ranking[0]
        worst   = ranking[-1]
        new_best = best.config.name

        # Détecter un changement de meilleure stratégie
        if new_best != self._best_strategy:
            if self._best_strategy is not None:
                logger.info(
                    "[%s] 🏆 Meilleure stratégie : %s %s (score=%.2f)",
                    self.name, best.config.emoji, best.config.name, best.score(),
                )
                # Publier le résultat pour MetaAgent
                await self.bus.publish(CHANNELS["shadow_result"], {
                    "type":             "shadow_ranking",
                    "best_strategy":    best.config.name,
                    "best_score":       round(best.score(), 3),
                    "best_win_rate":    round(best.win_rate, 3),
                    "best_return_pct":  round(best.return_pct, 3),
                    "ranking":          [
                        {
                            "name":       p.config.name,
                            "emoji":      p.config.emoji,
                            "score":      round(p.score(), 3),
                            "win_rate":   round(p.win_rate, 3),
                            "return_pct": round(p.return_pct, 3),
                            "trades":     p.total_trades,
                        }
                        for p in ranking
                    ],
                    "recommendation":   self._build_recommendation(best),
                })
            self._best_strategy = new_best

        # Écrire un rapport d'expérience toutes les 10 cycles
        if self._cycle_count % 10 == 0:
            self._write_experiment_report(ranking)

        # Log synthèse
        logger.info(
            "[%s] %s %s (score=%.1f, WR=%.0f%%, return=%+.1f%%) | "
            "%s %s (score=%.1f) | %s %s (score=%.1f)",
            self.name,
            ranking[0].config.emoji, ranking[0].config.name, ranking[0].score(),
            ranking[0].win_rate * 100, ranking[0].return_pct,
            ranking[1].config.emoji, ranking[1].config.name, ranking[1].score(),
            ranking[2].config.emoji, ranking[2].config.name, ranking[2].score(),
        )

    def _build_recommendation(self, best: ShadowPortfolio) -> dict:
        """Construit la recommandation d'adaptation pour MetaAgent."""
        cfg = best.config
        return {
            "suggested_min_confidence":    cfg.min_confidence,
            "suggested_sl_atr_multiplier": cfg.sl_atr_multiplier,
            "suggested_tp_rr_ratio":       cfg.tp_rr_ratio,
            "suggested_risk_pct":          cfg.risk_pct,
            "regime_filter":               cfg.regime_filter,
            "rationale": (
                f"Stratégie {cfg.name} donne les meilleures performances "
                f"(WR={best.win_rate:.0%}, return={best.return_pct:+.1f}%) "
                f"sur {best.total_trades} trades shadow."
            ),
        }

    def _write_experiment_report(self, ranking: list[ShadowPortfolio]) -> None:
        """Écrit un rapport d'expérience dans vault/experiments/."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")

        rows = "\n".join(
            f"| {p.config.emoji} **{p.config.name}** | `{p.win_rate:.0%}` | "
            f"`{p.return_pct:+.1f}%` | `{p.total_trades}` | "
            f"`{p.config.min_confidence}` | `1:{p.config.tp_rr_ratio}` | "
            f"`{p.score():.2f}` |"
            for p in ranking
        )

        best = ranking[0]
        frontmatter = {
            "date":          datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "agent":         "ShadowAgent",
            "type":          "experiment_report",
            "best_strategy": best.config.name,
            "best_win_rate": round(best.win_rate, 3),
            "tags":          ["shadow", "expérience", "R&D"],
        }

        content = f"""## 🔬 Rapport d'Expériences Shadow — {date_str}

### Classement des Stratégies
| Stratégie | Win Rate | Return | Trades | Min Conf. | TP Ratio | Score |
|---|---|---|---|---|---|---|
{rows}

### Meilleure Stratégie : {best.config.emoji} {best.config.name}
**Configuration :**
- Confidence minimale : `{best.config.min_confidence}/100`
- SL : `{best.config.sl_atr_multiplier}×ATR`
- TP : `1:{best.config.tp_rr_ratio}`
- Risque/trade : `{best.config.risk_pct}%`
- Filtre régime : `{best.config.regime_filter or 'Aucun'}`

**Recommandation au système :**
> {self._build_recommendation(best)['rationale']}

### Liens
[[agents/ShadowAgent]] | [[agents/MetaAgent]] | [[experiments/index]]
"""
        self.obsidian.write_note("experiments", f"experiment_{date_str}", frontmatter, content)

    # ── API publique ──────────────────────────────────────────────────────────

    def get_portfolio_summary(self) -> list[dict]:
        """Retourne un résumé des portfolios shadow pour MetaAgent."""
        return [
            {
                "name":       p.config.name,
                "emoji":      p.config.emoji,
                "win_rate":   round(p.win_rate, 3),
                "return_pct": round(p.return_pct, 3),
                "trades":     p.total_trades,
                "score":      round(p.score(), 3),
            }
            for p in sorted(self._portfolios.values(), key=lambda x: x.score(), reverse=True)
        ]
