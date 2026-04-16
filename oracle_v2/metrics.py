"""
ORACLE v2 — Métriques financières avancées.

Calcule en temps réel :
  - VaR (Value at Risk) à 95% sur fenêtre glissante
  - CVaR (Expected Shortfall) — perte moyenne au-delà du VaR
  - Sortino Ratio par strate
  - Corrélation entre signaux de strates (détecte redondances)

Usage:
    tracker = MetricsTracker()
    tracker.record_pnl("PARLIAMENT", pnl_pct=0.015)
    tracker.record_pnl("PARLIAMENT", pnl_pct=-0.008)

    report = tracker.get_report()
    # {
    #   "var_95": -0.012,
    #   "cvar_95": -0.018,
    #   "sortino": 1.4,
    #   "correlated_strates": [("AMD", "MOMENTUM", 0.82)],
    #   ...
    # }
"""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


RISK_FREE_RATE_DAILY = 0.0001   # ~3.65% annuel, neutre pour crypto


@dataclass
class StrateMetrics:
    name: str
    pnl_history: deque = field(default_factory=lambda: deque(maxlen=200))
    signal_history: deque = field(default_factory=lambda: deque(maxlen=200))   # +1 LONG / -1 SHORT / 0 NEU
    wins: int = 0
    losses: int = 0
    last_updated: float = field(default_factory=time.time)


class MetricsTracker:
    """
    Tracker de métriques financières ORACLE v2.

    Fenêtre glissante configurable (défaut : 100 trades).
    Thread-safe pour les lectures ; pas de verrou nécessaire en asyncio
    (tout tourne sur la même boucle event).
    """

    def __init__(self, window: int = 100, corr_threshold: float = 0.7):
        self.window = window
        self.corr_threshold = corr_threshold
        self._pnl_all: deque[float] = deque(maxlen=window)
        self._strates: dict[str, StrateMetrics] = {}
        self._starte_ts = time.time()

    # ─── Enregistrement ───────────────────────────────────────────────

    def record_pnl(
        self,
        source: str,
        pnl_pct: float,
        direction: Optional[str] = None,
    ) -> None:
        """Enregistre un PnL réel (positif = profit, négatif = perte)."""
        self._pnl_all.append(pnl_pct)

        sm = self._get_or_create(source)
        sm.pnl_history.append(pnl_pct)
        sm.last_updated = time.time()

        if pnl_pct > 0:
            sm.wins += 1
        elif pnl_pct < 0:
            sm.losses += 1

    def record_signal(self, source: str, direction: str, confidence: float) -> None:
        """Enregistre un signal (pour calcul de corrélation inter-strates)."""
        sm = self._get_or_create(source)
        score = confidence if direction == "LONG" else (-confidence if direction == "SHORT" else 0.0)
        sm.signal_history.append(score)

    def _get_or_create(self, name: str) -> StrateMetrics:
        if name not in self._strates:
            self._strates[name] = StrateMetrics(name=name)
        return self._strates[name]

    # ─── Métriques globales ───────────────────────────────────────────

    def var_95(self) -> float:
        """
        Value at Risk à 95% (perte maximale journalière avec 95% de probabilité).
        Retourne un nombre négatif ou 0.
        """
        if len(self._pnl_all) < 10:
            return 0.0
        sorted_pnl = sorted(self._pnl_all)
        idx = max(0, int(len(sorted_pnl) * 0.05) - 1)
        return sorted_pnl[idx]

    def cvar_95(self) -> float:
        """
        CVaR / Expected Shortfall — perte moyenne au-delà du VaR 95%.
        Mesure le risque de queue (fat tails crypto).
        """
        if len(self._pnl_all) < 10:
            return 0.0
        sorted_pnl = sorted(self._pnl_all)
        n_tail = max(1, int(len(sorted_pnl) * 0.05))
        tail = sorted_pnl[:n_tail]
        return sum(tail) / len(tail)

    def sortino_ratio(self, source: Optional[str] = None) -> float:
        """
        Sortino Ratio = (mean_return - Rf) / downside_deviation.
        Un Sortino > 1.0 indique une bonne performance ajustée au risque baissier.
        """
        pnl_series = (
            list(self._strates[source].pnl_history)
            if source and source in self._strates
            else list(self._pnl_all)
        )
        if len(pnl_series) < 5:
            return 0.0

        mean_r = sum(pnl_series) / len(pnl_series)
        downside = [min(0.0, r - RISK_FREE_RATE_DAILY) ** 2 for r in pnl_series]
        downside_std = math.sqrt(sum(downside) / len(downside))

        if downside_std < 1e-10:
            return float("inf") if mean_r > 0 else 0.0
        return (mean_r - RISK_FREE_RATE_DAILY) / downside_std

    def correlated_strates(self) -> list[tuple[str, str, float]]:
        """
        Retourne les paires de strates dont la corrélation de signaux > corr_threshold.
        Permet de désactiver les strates redondantes.

        Retourne [(strate_a, strate_b, correlation), ...]
        """
        names = [n for n, sm in self._strates.items() if len(sm.signal_history) >= 10]
        pairs = []

        for i, a in enumerate(names):
            for b in names[i + 1:]:
                corr = self._pearson(
                    list(self._strates[a].signal_history),
                    list(self._strates[b].signal_history),
                )
                if corr is not None and abs(corr) >= self.corr_threshold:
                    pairs.append((a, b, round(corr, 3)))

        return pairs

    def _pearson(self, x: list[float], y: list[float]) -> Optional[float]:
        """Corrélation de Pearson entre deux séries (longueur min commune)."""
        n = min(len(x), len(y))
        if n < 5:
            return None
        x, y = x[-n:], y[-n:]
        mx, my = sum(x) / n, sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if dx < 1e-10 or dy < 1e-10:
            return None
        return num / (dx * dy)

    # ─── Rapport complet ──────────────────────────────────────────────

    def get_report(self) -> dict:
        """
        Rapport métriques complet.
        Alerte si Sortino < 1.0 ou CVaR < -5%.
        """
        var = self.var_95()
        cvar = self.cvar_95()
        sortino = self.sortino_ratio()
        corr_pairs = self.correlated_strates()

        strate_reports = {}
        for name, sm in self._strates.items():
            total = sm.wins + sm.losses
            strate_reports[name] = {
                "wins": sm.wins,
                "losses": sm.losses,
                "winrate": sm.wins / total if total > 0 else 0.0,
                "sortino": round(self.sortino_ratio(name), 3),
                "n_pnl": len(sm.pnl_history),
            }

        return {
            "var_95": round(var, 4),
            "cvar_95": round(cvar, 4),
            "sortino_global": round(sortino, 3),
            "n_trades": len(self._pnl_all),
            "correlated_strates": corr_pairs,
            "alerts": self._get_alerts(var, cvar, sortino, corr_pairs),
            "strates": strate_reports,
        }

    def _get_alerts(
        self,
        var: float,
        cvar: float,
        sortino: float,
        corr_pairs: list,
    ) -> list[str]:
        alerts = []
        if sortino < 1.0 and len(self._pnl_all) >= 20:
            alerts.append(f"⚠️ Sortino {sortino:.2f} < 1.0 — performance ajustée risque insuffisante")
        if cvar < -0.05:
            alerts.append(f"🚨 CVaR {cvar:.1%} < -5% — risque de queue élevé (fat tails)")
        if var < -0.03:
            alerts.append(f"⚠️ VaR 95% {var:.1%} < -3% — drawdown exceptionnel probable")
        for a, b, c in corr_pairs:
            alerts.append(f"ℹ️ Corrélation {a}↔{b} = {c:.2f} — strate possiblement redondante")
        return alerts
