"""
Circuit Breaker — Protection automatique du capital.

Coupe le trading automatiquement quand :
  1. N pertes consécutives (défaut : 5)
  2. Drawdown max atteint (défaut : 15%)
  3. Drawdown journalier atteint (défaut : 5%)
  4. Perte USD maximale par jour (défaut : $500)

États :
  CLOSED  → trading normal
  OPEN    → trading suspendu (circuit ouvert)
  HALF    → trading avec taille réduite (-50%)

Cooldown configurable avant réactivation automatique.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class BreakerState(str, Enum):
    CLOSED   = "closed"      # Normal — trading actif
    HALF     = "half_open"   # Prudent — taille réduite 50%
    OPEN     = "open"        # Coupé — aucun trade


@dataclass
class CircuitBreakerConfig:
    """Configuration du circuit breaker."""
    max_consecutive_losses: int   = 5       # pertes d'affilée → OPEN
    half_open_losses:       int   = 3       # pertes d'affilée → HALF
    max_drawdown_pct:       float = 15.0    # DD global → OPEN
    warning_drawdown_pct:   float = 10.0    # DD global → HALF
    max_daily_drawdown_pct: float = 5.0     # DD journalier → OPEN
    max_daily_loss_usd:     float = 500.0   # perte USD journalière → OPEN
    cooldown_minutes:       int   = 30      # minutes avant auto-réactivation
    half_size_factor:       float = 0.5     # réduction taille en mode HALF


class CircuitBreaker:
    """
    Circuit breaker pour la protection automatique du capital.

    Usage dans RiskAgent:
        if not self.circuit_breaker.can_trade():
            return  # trading bloqué
        size_factor = self.circuit_breaker.size_factor()  # 1.0 ou 0.5
    """

    def __init__(self, config: CircuitBreakerConfig = None, telegram=None):
        self.config   = config or CircuitBreakerConfig()
        self.telegram = telegram

        self._state:            BreakerState = BreakerState.CLOSED
        self._consecutive_losses: int        = 0
        self._daily_pnl_usd:    float        = 0.0
        self._daily_start_capital: float     = 0.0
        self._current_day:      Optional[str] = None
        self._tripped_at:       Optional[datetime] = None
        self._trip_reason:      str          = ""
        self._total_trips:      int          = 0
        self._manual_override:  bool         = False

    # ── API publique ─────────────────────────────────────────────────────────

    @property
    def state(self) -> BreakerState:
        return self._state

    def can_trade(self) -> bool:
        """Retourne True si le trading est autorisé."""
        self._check_cooldown()
        return self._state != BreakerState.OPEN

    def size_factor(self) -> float:
        """Facteur de réduction de taille (1.0 = normal, 0.5 = réduit)."""
        if self._state == BreakerState.HALF:
            return self.config.half_size_factor
        return 1.0

    def record_trade(self, pnl_usd: float, capital: float, drawdown_pct: float) -> None:
        """
        Enregistre un trade et vérifie les conditions du circuit breaker.
        Appelé par RiskAgent après chaque trade clôturé.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Reset journalier
        if today != self._current_day:
            self._daily_pnl_usd = 0.0
            self._daily_start_capital = capital - pnl_usd
            self._current_day = today

        self._daily_pnl_usd += pnl_usd

        # Mise à jour séquence de pertes
        if pnl_usd < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
            # Un win peut ramener de HALF à CLOSED
            if self._state == BreakerState.HALF:
                self._state = BreakerState.CLOSED
                logger.info("[CircuitBreaker] ✅ Trade gagnant → retour CLOSED")

        # ── Vérifications par priorité ──

        # 1. Drawdown global max → OPEN
        if drawdown_pct >= self.config.max_drawdown_pct:
            self._trip(
                BreakerState.OPEN,
                f"Drawdown max atteint ({drawdown_pct:.1f}% >= {self.config.max_drawdown_pct}%)",
            )
            return

        # 2. Pertes consécutives max → OPEN
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            self._trip(
                BreakerState.OPEN,
                f"{self._consecutive_losses} pertes consécutives (max {self.config.max_consecutive_losses})",
            )
            return

        # 3. Perte journalière max USD → OPEN
        if self._daily_pnl_usd <= -self.config.max_daily_loss_usd:
            self._trip(
                BreakerState.OPEN,
                f"Perte journalière ${abs(self._daily_pnl_usd):.2f} >= ${self.config.max_daily_loss_usd:.2f}",
            )
            return

        # 4. Drawdown journalier → OPEN
        if self._daily_start_capital > 0:
            daily_dd = (self._daily_start_capital - capital) / self._daily_start_capital * 100
            if daily_dd >= self.config.max_daily_drawdown_pct:
                self._trip(
                    BreakerState.OPEN,
                    f"Drawdown journalier {daily_dd:.1f}% >= {self.config.max_daily_drawdown_pct}%",
                )
                return

        # 5. Warning drawdown → HALF
        if drawdown_pct >= self.config.warning_drawdown_pct:
            if self._state == BreakerState.CLOSED:
                self._trip(
                    BreakerState.HALF,
                    f"Drawdown warning ({drawdown_pct:.1f}% >= {self.config.warning_drawdown_pct}%)",
                )
            return

        # 6. Pertes consécutives warning → HALF
        if self._consecutive_losses >= self.config.half_open_losses:
            if self._state == BreakerState.CLOSED:
                self._trip(
                    BreakerState.HALF,
                    f"{self._consecutive_losses} pertes consécutives (warning à {self.config.half_open_losses})",
                )

    def force_open(self, reason: str = "Manuel") -> None:
        """Force l'ouverture du circuit breaker (arrêt manuel)."""
        self._trip(BreakerState.OPEN, f"FORCE: {reason}")
        self._manual_override = True

    def force_close(self) -> None:
        """Force la fermeture du circuit breaker (reprise manuelle)."""
        self._state = BreakerState.CLOSED
        self._manual_override = False
        self._tripped_at = None
        self._trip_reason = ""
        self._consecutive_losses = 0
        logger.info("[CircuitBreaker] 🔧 Reset manuel → CLOSED")

    def snapshot(self) -> dict:
        """État complet pour monitoring/Telegram."""
        return {
            "state":               self._state.value,
            "consecutive_losses":  self._consecutive_losses,
            "daily_pnl_usd":      round(self._daily_pnl_usd, 2),
            "trip_reason":         self._trip_reason,
            "tripped_at":          self._tripped_at.isoformat() if self._tripped_at else None,
            "total_trips":         self._total_trips,
            "cooldown_remaining":  self._cooldown_remaining_min(),
            "size_factor":         self.size_factor(),
        }

    # ── Internals ────────────────────────────────────────────────────────────

    def _trip(self, new_state: BreakerState, reason: str) -> None:
        """Déclenche le circuit breaker."""
        old = self._state
        self._state       = new_state
        self._tripped_at  = datetime.now(timezone.utc)
        self._trip_reason = reason
        self._total_trips += 1

        icon = "🚨" if new_state == BreakerState.OPEN else "⚠️"
        logger.warning(
            "[CircuitBreaker] %s %s → %s : %s (trip #%d)",
            icon, old.value, new_state.value, reason, self._total_trips,
        )

        # Notification Telegram (fire-and-forget avec logging d'erreur)
        if self.telegram:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self.telegram.send(
                    f"{icon} *CIRCUIT BREAKER*\n"
                    f"État : `{old.value}` → `{new_state.value}`\n"
                    f"Raison : {reason}\n"
                    f"Cooldown : {self.config.cooldown_minutes} min"
                ))
                task.add_done_callback(
                    lambda t: logger.warning("[CircuitBreaker] Telegram send failed: %s", t.exception())
                    if not t.cancelled() and t.exception() else None
                )
            except RuntimeError:
                pass

    def _check_cooldown(self) -> None:
        """Réactive le trading après le cooldown (sauf override manuel)."""
        if self._state == BreakerState.CLOSED:
            return
        if self._manual_override:
            return
        if self._tripped_at is None:
            return

        elapsed = datetime.now(timezone.utc) - self._tripped_at
        if elapsed >= timedelta(minutes=self.config.cooldown_minutes):
            old = self._state
            # OPEN → HALF (pas CLOSED directement — prudence)
            if self._state == BreakerState.OPEN:
                self._state = BreakerState.HALF
                logger.info(
                    "[CircuitBreaker] ⏰ Cooldown écoulé → HALF (prudence, taille réduite)"
                )
            else:
                self._state = BreakerState.CLOSED
                self._tripped_at = None
                logger.info("[CircuitBreaker] ⏰ Cooldown écoulé → CLOSED (trading normal)")

    def _cooldown_remaining_min(self) -> float:
        """Minutes restantes avant réactivation."""
        if self._state == BreakerState.CLOSED or self._tripped_at is None:
            return 0.0
        elapsed = (datetime.now(timezone.utc) - self._tripped_at).total_seconds() / 60
        remaining = self.config.cooldown_minutes - elapsed
        return max(0.0, round(remaining, 1))
