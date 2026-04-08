"""
Performance Tracker — Métriques financières en temps réel.
Calcule Sharpe, Sortino, Calmar, win rate, profit factor, drawdown.
Toutes les métriques sont écrites dans le vault Obsidian.
Persiste l'historique des trades dans vault/config/trade_history.json.
"""

from __future__ import annotations

import json
import logging
import math
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from models.learning import TradeOutcome, AgentMemory, MarketRegime
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.045   # 4.5% annuel (T-bills US 2024)
TRADING_DAYS   = 252
MAX_HISTORY    = 500     # trades gardés en mémoire


class PerformanceTracker:
    """
    Suit les performances financières globales du système.

    Métriques calculées :
    - Sharpe Ratio (ajusté au taux sans risque)
    - Sortino Ratio (pénalise uniquement la volatilité négative)
    - Calmar Ratio (return / max drawdown)
    - Win Rate, Profit Factor, Expectancy
    - Drawdown maximum et actuel
    - Séquences gagnantes/perdantes
    - Performance par asset et par timeframe
    """

    def __init__(self, obsidian: ObsidianClient, initial_capital: float = 10_000):
        self.obsidian        = obsidian
        self.initial_capital = initial_capital
        self._capital        = initial_capital
        self._peak_capital   = initial_capital

        self._trades: deque[TradeOutcome] = deque(maxlen=MAX_HISTORY)
        self._daily_returns: deque[float] = deque(maxlen=252)  # 1 an glissant
        self._equity_curve:  list[float]  = [initial_capital]

        # Charger l'historique persisté (survit aux redémarrages)
        self._load_history()

    # ── Persistance des trades ───────────────────────────────────────────────

    @property
    def _history_path(self) -> Path:
        return self.obsidian.vault_path / "config" / "trade_history.json"

    def _load_history(self) -> None:
        """Recharge l'historique des trades depuis vault/config/trade_history.json."""
        path = self._history_path
        if not path.exists():
            logger.info("[Tracker] Aucun historique trouvé — démarrage à zéro")
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            capital = raw.get("capital", self.initial_capital)
            peak    = raw.get("peak_capital", capital)
            trades  = raw.get("trades", [])
            daily_r = raw.get("daily_returns", [])
            equity  = raw.get("equity_curve", [self.initial_capital])

            self._capital       = capital
            self._peak_capital  = peak
            self._equity_curve  = equity
            self._daily_returns = deque(daily_r, maxlen=252)

            loaded = 0
            for t in trades[-MAX_HISTORY:]:
                self._daily_returns.append(t.get("daily_ret", 0))
                loaded += 1

            logger.info(
                "[Tracker] Historique restauré : %d trades | Capital $%.2f | Peak $%.2f",
                loaded, self._capital, self._peak_capital,
            )
        except Exception as exc:
            logger.warning("[Tracker] Erreur chargement historique: %s", exc)

    def _save_history(self) -> None:
        """Persiste l'état courant avec écriture atomique (tmp + rename)."""
        try:
            # Sauvegarder les 100 derniers trades (résumé léger)
            trade_summaries = []
            for t in list(self._trades)[-100:]:
                trade_summaries.append({
                    "asset":     t.asset,
                    "side":      t.side.value,
                    "pnl_pct":   round(t.pnl_pct, 4),
                    "pnl_usd":   round(t.pnl_usd, 2),
                    "is_win":    t.is_win,
                    "exit":      t.exit_reason.value if t.exit_reason else "unknown",
                    "entry_t":   t.entry_time.isoformat(),
                    "exit_t":    t.exit_time.isoformat(),
                    "confidence":t.confidence,
                    "regime":    t.regime.value if hasattr(t.regime, 'value') else str(t.regime),
                    "duration_h":round(t.duration_hours, 2),
                    "daily_ret": round(t.pnl_pct / 100 / max(t.duration_hours / 24, 1/24), 6),
                })

            # Borner l'equity curve en mémoire
            if len(self._equity_curve) > 1000:
                self._equity_curve = self._equity_curve[-500:]

            data = {
                "last_saved":    datetime.now(timezone.utc).isoformat(),
                "capital":       round(self._capital, 2),
                "peak_capital":  round(self._peak_capital, 2),
                "initial_capital": self.initial_capital,
                "total_trades":  len(self._trades),
                "trades":        trade_summaries,
                "daily_returns": list(self._daily_returns)[-252:],
                "equity_curve":  self._equity_curve[-500:],
            }
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            # Écriture atomique : écrire dans .tmp puis rename
            tmp_path = self._history_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.replace(self._history_path)
        except Exception as exc:
            logger.warning("[Tracker] Erreur sauvegarde historique: %s", exc)

    # ── Enregistrement ────────────────────────────────────────────────────────

    def record(self, outcome: TradeOutcome) -> None:
        """Enregistre un résultat de trade et met à jour toutes les métriques."""
        self._trades.append(outcome)
        self._capital += outcome.pnl_usd
        self._equity_curve.append(self._capital)

        if self._capital > self._peak_capital:
            self._peak_capital = self._capital

        # Return journalier approximatif (répartition uniforme sur la durée)
        days = max(outcome.duration_hours / 24, 1/24)
        daily_return = outcome.pnl_pct / 100 / days
        self._daily_returns.append(daily_return)

        # Persister après chaque trade (survit aux crashs)
        self._save_history()

        logger.debug(
            "Trade enregistré : %s %+.2f%% | Capital : $%.2f",
            outcome.asset, outcome.pnl_pct, self._capital,
        )

    # ── Métriques principales ─────────────────────────────────────────────────

    @property
    def capital(self) -> float:
        return self._capital

    @property
    def total_return_pct(self) -> float:
        return (self._capital - self.initial_capital) / self.initial_capital * 100

    @property
    def win_rate(self) -> float:
        if not self._trades:
            return 0.0
        return sum(1 for t in self._trades if t.is_win) / len(self._trades)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl_usd for t in self._trades if t.is_win)
        gross_loss   = abs(sum(t.pnl_usd for t in self._trades if not t.is_win))
        return gross_profit / max(gross_loss, 0.001)

    @property
    def expectancy(self) -> float:
        """Gain moyen par trade (USD)."""
        if not self._trades:
            return 0.0
        return sum(t.pnl_usd for t in self._trades) / len(self._trades)

    @property
    def max_drawdown(self) -> float:
        """Drawdown maximum historique (%)."""
        if len(self._equity_curve) < 2:
            return 0.0
        eq = np.array(self._equity_curve)
        peak = np.maximum.accumulate(eq)
        dd   = (peak - eq) / np.maximum(peak, 1e-9) * 100
        return float(dd.max())

    @property
    def current_drawdown(self) -> float:
        if self._peak_capital <= 0:
            return 0.0
        return (self._peak_capital - self._capital) / self._peak_capital * 100

    @property
    def sharpe_ratio(self) -> float:
        if len(self._daily_returns) < 10:
            return 0.0
        returns = np.array(list(self._daily_returns))
        excess  = returns - RISK_FREE_RATE / TRADING_DAYS
        std     = returns.std()
        if std < 1e-9:
            return 0.0
        return float(excess.mean() / std * math.sqrt(TRADING_DAYS))

    @property
    def sortino_ratio(self) -> float:
        """Sharpe qui pénalise uniquement la volatilité négative."""
        if len(self._daily_returns) < 10:
            return 0.0
        returns  = np.array(list(self._daily_returns))
        excess   = returns - RISK_FREE_RATE / TRADING_DAYS
        neg_rets = returns[returns < 0]
        if len(neg_rets) == 0:
            return 99.0
        downside_std = neg_rets.std()
        if downside_std < 1e-9:
            return 0.0
        return float(excess.mean() / downside_std * math.sqrt(TRADING_DAYS))

    @property
    def calmar_ratio(self) -> float:
        """Return annualisé / drawdown max."""
        ann_return = self.total_return_pct / max(1, len(self._trades) / 20)
        return ann_return / max(self.max_drawdown, 0.001)

    def avg_holding_hours(self) -> float:
        if not self._trades:
            return 0.0
        return sum(t.duration_hours for t in self._trades) / len(self._trades)

    def best_asset(self) -> tuple[str, float]:
        """Asset avec le meilleur P&L total."""
        by_asset: dict[str, float] = {}
        for t in self._trades:
            by_asset[t.asset] = by_asset.get(t.asset, 0.0) + t.pnl_usd
        if not by_asset:
            return ("—", 0.0)
        best = max(by_asset, key=by_asset.__getitem__)
        return (best, by_asset[best])

    def worst_asset(self) -> tuple[str, float]:
        by_asset: dict[str, float] = {}
        for t in self._trades:
            by_asset[t.asset] = by_asset.get(t.asset, 0.0) + t.pnl_usd
        if not by_asset:
            return ("—", 0.0)
        worst = min(by_asset, key=by_asset.__getitem__)
        return (worst, by_asset[worst])

    def win_rate_by_asset(self) -> dict[str, float]:
        by_asset: dict[str, list[bool]] = {}
        for t in self._trades:
            by_asset.setdefault(t.asset, []).append(t.is_win)
        return {
            asset: sum(wins) / len(wins)
            for asset, wins in by_asset.items()
        }

    def detect_regime(self) -> MarketRegime:
        """Détecte le régime de marché courant via l'equity curve."""
        if len(self._equity_curve) < 10:
            return MarketRegime.SIDEWAYS
        recent = np.array(self._equity_curve[-20:])
        slope  = np.polyfit(range(len(recent)), recent, 1)[0]
        std    = recent.std()

        if std / recent.mean() > 0.05:
            return MarketRegime.VOLATILE
        if slope > 0:
            return MarketRegime.BULL
        if slope < 0:
            return MarketRegime.BEAR
        return MarketRegime.SIDEWAYS

    # ── Snapshot complet ──────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        best_asset, best_pnl   = self.best_asset()
        worst_asset, worst_pnl = self.worst_asset()
        wr_by_asset = self.win_rate_by_asset()

        return {
            "capital":          round(self._capital, 2),
            "initial_capital":  self.initial_capital,
            "total_return_pct": round(self.total_return_pct, 3),
            "total_trades":     len(self._trades),
            "win_rate":         round(self.win_rate, 3),
            "profit_factor":    round(self.profit_factor, 3),
            "expectancy_usd":   round(self.expectancy, 2),
            "sharpe_ratio":     round(self.sharpe_ratio, 3),
            "sortino_ratio":    round(self.sortino_ratio, 3),
            "calmar_ratio":     round(self.calmar_ratio, 3),
            "max_drawdown_pct": round(self.max_drawdown, 2),
            "current_drawdown": round(self.current_drawdown, 2),
            "avg_holding_h":    round(self.avg_holding_hours(), 1),
            "best_asset":       best_asset,
            "best_pnl_usd":     round(best_pnl, 2),
            "worst_asset":      worst_asset,
            "worst_pnl_usd":    round(worst_pnl, 2),
            "regime":           self.detect_regime().value,
            "win_rate_by_asset":wr_by_asset,
        }

    # ── Écriture Obsidian ─────────────────────────────────────────────────────

    def write_performance_note(self) -> None:
        """Écrit le tableau de bord de performance dans vault/risque/."""
        snap = self.snapshot()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        frontmatter = {
            "date":          date_str,
            "agent":         "PerformanceTracker",
            "tags":          ["performance", "metriques", "trading"],
            "sharpe":        snap["sharpe_ratio"],
            "sortino":       snap["sortino_ratio"],
            "win_rate":      snap["win_rate"],
            "capital":       snap["capital"],
            "drawdown":      snap["current_drawdown"],
        }

        wr_rows = "\n".join(
            f"| {asset} | {rate:.1%} |"
            for asset, rate in snap["win_rate_by_asset"].items()
        ) or "| — | — |"

        content = f"""## Tableau de Bord Performance — {date_str}

### Métriques Financières Clés
| Métrique | Valeur | Benchmark |
|---|---|---|
| 💰 Capital actuel | `${snap['capital']:,.2f}` | `${self.initial_capital:,.2f}` |
| 📈 Return total | `{snap['total_return_pct']:+.2f}%` | — |
| 🎯 Win Rate | `{snap['win_rate']:.1%}` | > 50% |
| 💎 Profit Factor | `{snap['profit_factor']:.2f}` | > 1.5 |
| 📊 Sharpe Ratio | `{snap['sharpe_ratio']:.2f}` | > 1.0 |
| 🛡️ Sortino Ratio | `{snap['sortino_ratio']:.2f}` | > 1.5 |
| 🏔️ Calmar Ratio | `{snap['calmar_ratio']:.2f}` | > 0.5 |
| ⬇️ Max Drawdown | `{snap['max_drawdown_pct']:.2f}%` | < 15% |
| ⏱️ Durée moy. trade | `{snap['avg_holding_h']:.1f}h` | — |
| 💵 Expectancy | `${snap['expectancy_usd']:+.2f}` | > $0 |

### Régime de Marché Détecté
**{snap['regime'].upper()}** — basé sur la courbe d'equity des {min(len(self._trades), 20)} derniers trades.

### Performance par Asset
| Asset | Win Rate |
|---|---|
{wr_rows}

### Top Performance
- 🥇 Meilleur asset : **{snap['best_asset']}** (`${snap['best_pnl_usd']:+,.2f}`)
- 🥴 Pire asset : **{snap['worst_asset']}** (`${snap['worst_pnl_usd']:+,.2f}`)

### Total Trades : {snap['total_trades']}
"""
        self.obsidian.write_note("risque", f"performance_{date_str}", frontmatter, content)
        logger.info(
            "📊 Performance : Sharpe=%.2f | Sortino=%.2f | WR=%.1f%% | DD=%.1f%%",
            snap["sharpe_ratio"], snap["sortino_ratio"],
            snap["win_rate"] * 100, snap["current_drawdown"],
        )
