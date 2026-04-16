"""
Brainstem — Gestion survie système.
Override absolu en cas de conditions vitales compromises.
Inspiré du brainstem neuromorphique : énergie + survie avant tout.

Améliorations v2.1 :
  - Drawdown journalier adaptatif (ajusté selon l'edge du signal)
  - register_trade_opened() sépare l'ouverture (throttle) de la fermeture (PnL)
  - register_trade(pnl_réel) doit être appelé à la FERMETURE du trade
  - Tracking enrichi : winrate cumulatif, historique intra-day
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import logging
import time

logger = logging.getLogger("ORACLE.Brainstem")


@dataclass
class BrainstemState:
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    session_trades: int = 0
    last_trade_time: Optional[float] = None
    is_cooling: bool = False
    cooling_until: Optional[float] = None
    daily_date: date = field(default_factory=date.today)
    daily_pnl_list: list = field(default_factory=list)
    cumulative_wins: int = 0
    cumulative_losses: int = 0


class Brainstem:
    """
    Circuit breaker neuromorphique.
    Aucune action n'est possible si le brainstem dit NON.

    Drawdown adaptatif :
      - Confiance signal >= high_edge_threshold : tolérance élargie jusqu'à high_edge_max_drawdown
      - Confiance signal faible                 : tolérance de base (base_max_daily_drawdown)
    """

    def __init__(
        self,
        max_consecutive_losses: int = 3,
        max_daily_drawdown: float = 0.02,
        max_session_trades: int = 8,
        cooling_period_seconds: int = 900,
        min_trade_interval_seconds: int = 60,
        adaptive_drawdown: bool = True,
        high_edge_threshold: float = 0.75,
        high_edge_max_drawdown: float = 0.04,
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.base_max_daily_drawdown = max_daily_drawdown
        self.max_session_trades = max_session_trades
        self.cooling_period_seconds = cooling_period_seconds
        self.min_trade_interval_seconds = min_trade_interval_seconds
        self.adaptive_drawdown = adaptive_drawdown
        self.high_edge_threshold = high_edge_threshold
        self.high_edge_max_drawdown = high_edge_max_drawdown
        self.state = BrainstemState()
        self._current_confidence: float = 0.0

    def set_signal_confidence(self, confidence: float) -> None:
        """Met à jour la confiance courante (pour drawdown adaptatif)."""
        self._current_confidence = max(0.0, min(1.0, confidence))

    def _effective_max_drawdown(self) -> float:
        """Seuil de drawdown journalier effectif, adaptatif."""
        if not self.adaptive_drawdown:
            return self.base_max_daily_drawdown
        if self._current_confidence >= self.high_edge_threshold:
            alpha = (self._current_confidence - self.high_edge_threshold) / (
                1.0 - self.high_edge_threshold + 1e-10
            )
            return self.base_max_daily_drawdown + alpha * (
                self.high_edge_max_drawdown - self.base_max_daily_drawdown
            )
        return self.base_max_daily_drawdown

    def is_alive(self) -> tuple[bool, str]:
        """
        Retourne (True/False, raison).
        False = reflex withdrawal déclenché.
        """
        now = time.time()
        today = date.today()

        # Reset journalier
        if self.state.daily_date != today:
            self.state.daily_pnl = 0.0
            self.state.session_trades = 0
            self.state.consecutive_losses = 0
            self.state.daily_pnl_list = []
            self.state.daily_date = today
            logger.info("Brainstem: Reset journalier effectué")

        # Cooling period
        if self.state.is_cooling and self.state.cooling_until:
            if now < self.state.cooling_until:
                remaining = int(self.state.cooling_until - now)
                return False, f"COOLING_PERIOD ({remaining}s restantes)"
            else:
                self.state.is_cooling = False
                self.state.cooling_until = None
                logger.info("Brainstem: Cooling period terminée")

        # Drawdown journalier adaptatif
        eff_dd = self._effective_max_drawdown()
        if self.state.daily_pnl <= -eff_dd:
            return False, (
                f"MAX_DAILY_DRAWDOWN ({self.state.daily_pnl:.2%} ≤ "
                f"-{eff_dd:.2%} | edge={self._current_confidence:.0%})"
            )

        # Pertes consécutives → cooling
        if self.state.consecutive_losses >= self.max_consecutive_losses:
            self.state.is_cooling = True
            self.state.cooling_until = now + self.cooling_period_seconds
            self.state.consecutive_losses = 0
            logger.warning(
                f"Brainstem: {self.max_consecutive_losses} pertes consécutives "
                f"→ cooling {self.cooling_period_seconds}s"
            )
            return False, "CONSECUTIVE_LOSSES → COOLING ACTIVÉ"

        # Trop de trades
        if self.state.session_trades >= self.max_session_trades:
            return False, f"MAX_SESSION_TRADES ({self.state.session_trades})"

        # Intervalle minimum
        if self.state.last_trade_time:
            elapsed = now - self.state.last_trade_time
            if elapsed < self.min_trade_interval_seconds:
                remaining = int(self.min_trade_interval_seconds - elapsed)
                return False, f"MIN_INTERVAL ({remaining}s)"

        return True, "OK"

    def register_trade_opened(self) -> None:
        """
        Enregistre l'OUVERTURE d'un trade (pour les compteurs de throttle).
        N'affecte PAS daily_pnl ni consecutive_losses — seul register_trade() le fait.
        """
        self.state.session_trades += 1
        self.state.last_trade_time = time.time()

    def register_trade(self, pnl_pct: float) -> None:
        """
        Enregistre le résultat RÉEL d'un trade FERMÉ.

        CRITIQUE : appeler à la FERMETURE (quand SL/TP est atteint),
        jamais au placement. C'est la seule façon pour le circuit breaker
        "pertes consécutives" de fonctionner correctement.
        """
        self.state.daily_pnl += pnl_pct
        self.state.daily_pnl_list.append(pnl_pct)

        if pnl_pct < 0:
            self.state.consecutive_losses += 1
            self.state.cumulative_losses += 1
            logger.warning(
                f"Brainstem: Perte #{self.state.consecutive_losses} — "
                f"PnL: {pnl_pct:.2%} | Daily: {self.state.daily_pnl:.2%}"
            )
        else:
            self.state.consecutive_losses = 0
            self.state.cumulative_wins += 1
            logger.info(
                f"Brainstem: Gain enregistré — "
                f"PnL: {pnl_pct:.2%} | Daily: {self.state.daily_pnl:.2%}"
            )

    def get_status_dict(self) -> dict:
        alive, reason = self.is_alive()
        total = self.state.cumulative_wins + self.state.cumulative_losses
        return {
            "alive": alive,
            "reason": reason,
            "consecutive_losses": self.state.consecutive_losses,
            "daily_pnl": f"{self.state.daily_pnl:.2%}",
            "effective_drawdown_limit": f"{self._effective_max_drawdown():.2%}",
            "session_trades": self.state.session_trades,
            "cooling": self.state.is_cooling,
            "signal_confidence": f"{self._current_confidence:.0%}",
            "cumulative_winrate": (
                round(self.state.cumulative_wins / total, 3) if total > 0 else 0.0
            ),
        }
