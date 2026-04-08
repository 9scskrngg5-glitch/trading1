"""
Agent 12 — Behavior Agent (Discipline)
Contrôleur de discipline comportementale du système de trading.

Responsabilités :
1. Détection du surtrading (> N trades dans une fenêtre temporelle)
2. Protection après séries de pertes (streak négatif)
3. Respect des horaires de marché (éviter les heures à faible liquidité)
4. Contrôle des biais émotionnels (revenge trading, FOMO)
5. Publication du multiplicateur de risque comportemental (0.3 – 1.0)

RiskAgent consomme le behavior_alert → réduit dynamiquement le sizing.
Vault : vault/behavior/
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

# ── Constantes de discipline ──────────────────────────────────────────────────
MAX_TRADES_PER_HOUR      = 3       # Au-delà = surtrading
MAX_TRADES_PER_DAY       = 8       # Limite journalière
LOSS_STREAK_SOFT_LIMIT   = 2       # 2 pertes consécutives → risk ×0.7
LOSS_STREAK_HARD_LIMIT   = 4       # 4 pertes consécutives → risk ×0.4
LOSS_STREAK_KILL         = 6       # 6 pertes consécutives → risk ×0.0 (pause totale)
COOLDOWN_AFTER_BIG_LOSS  = 30 * 60 # 30 min de cooldown après une grosse perte (> 3%)
DAILY_LOSS_LIMIT_PCT     = 5.0     # Limite de perte journalière (% du capital)

# Heures UTC à faible liquidité (éviter de trader)
LOW_LIQUIDITY_HOURS_UTC  = {22, 23, 0, 1, 2, 3}  # 22h–4h UTC


class BehaviorAgent(BaseAgent):
    """
    Agent de discipline comportementale.

    Publie sur system:behavior un multiplicateur de risque :
    - 1.0 = comportement normal
    - 0.7 = risque réduit (perte douce)
    - 0.4 = risque fortement réduit (perte sévère)
    - 0.0 = pause forcée (kill switch comportemental)

    RiskAgent consomme ce multiplicateur dans son calcul de sizing.
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        config: dict,
        telegram=None,
    ):
        super().__init__("BehaviorAgent", "behavior", bus, obsidian, config)
        self.telegram = telegram

        # ── Historique des trades ──────────────────────────────────────────────
        self._trade_timestamps: deque    = deque(maxlen=100)    # timestamps ISO
        self._loss_streak:      int      = 0
        self._daily_trades:     int      = 0
        self._daily_pnl_pct:    float    = 0.0
        self._last_day:         str      = ""

        # ── Cooldown après grosse perte ───────────────────────────────────────
        self._cooldown_until:   float    = 0.0    # timestamp UNIX

        # ── État comportemental courant ───────────────────────────────────────
        self._risk_multiplier:  float    = 1.0
        self._discipline_mode:  str      = "normal"
        self._current_reasons:  list[str]= []

        # ── Cycle ─────────────────────────────────────────────────────────────
        self._cycle_count:      int      = 0

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "behavior").mkdir(exist_ok=True)
        logger.info(
            "[%s] Actif | Limites : %d trades/h, %d/jour, streak_kill=%d",
            self.name, MAX_TRADES_PER_HOUR, MAX_TRADES_PER_DAY, LOSS_STREAK_KILL,
        )

    def _register_subscriptions(self) -> None:
        # Observer tous les trades clôturés
        self.bus.subscribe(CHANNELS["portfolio_update"],  self._on_trade_event)
        # Observer les ordres validés (pour détecter le surtrading)
        self.bus.subscribe(CHANNELS["orders_validated"],  self._on_order_validated)

    # ── Handlers bus ──────────────────────────────────────────────────────────

    async def _on_order_validated(self, data: dict) -> None:
        """Enregistre chaque ordre validé pour le comptage journalier."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if now_str != self._last_day:
            # Nouveau jour → reset
            self._daily_trades  = 0
            self._daily_pnl_pct = 0.0
            self._last_day      = now_str

        self._daily_trades += 1
        self._trade_timestamps.append(datetime.now(timezone.utc).isoformat())

    async def _on_trade_event(self, data: dict) -> None:
        """Analyse chaque trade clôturé pour détecter les patterns de comportement."""
        if data.get("type") != "trade_closed":
            return

        is_win  = data.get("is_win", False)
        pnl_pct = float(data.get("pnl_pct", 0.0))

        # Mise à jour P&L journalier
        self._daily_pnl_pct += pnl_pct

        # Mise à jour streak
        if is_win:
            self._loss_streak = max(0, self._loss_streak - 1)
        else:
            self._loss_streak += 1

        # Cooldown après grosse perte
        if pnl_pct < -3.0:
            self._cooldown_until = time.time() + COOLDOWN_AFTER_BIG_LOSS
            logger.warning(
                "[%s] ⚠️ Grosse perte (%.2f%%) — cooldown 30 min activé",
                self.name, pnl_pct,
            )

        # Réévaluation immédiate
        await self._evaluate_and_publish()

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        self._cycle_count += 1
        await self._evaluate_and_publish()

        # Log périodique
        emoji = {
            "normal":     "✅",
            "caution":    "⚠️",
            "restricted": "🔴",
            "paused":     "🛑",
        }.get(self._discipline_mode, "❓")

        logger.info(
            "[%s] %s Mode=%s | Multiplicateur=%.2f | Streak=%+d | Trades jour=%d/%d",
            self.name, emoji, self._discipline_mode.upper(),
            self._risk_multiplier, -self._loss_streak,
            self._daily_trades, MAX_TRADES_PER_DAY,
        )

        # Rapport vault toutes les 5 cycles si en mode non-normal
        if self._cycle_count % 5 == 0 and self._discipline_mode != "normal":
            self._write_behavior_note()

    # ── Évaluation comportementale ────────────────────────────────────────────

    async def _evaluate_and_publish(self) -> None:
        """
        Évalue tous les critères de discipline et calcule le multiplicateur.
        Publie sur system:behavior si le multiplicateur a changé.
        """
        reasons: list[str] = []
        multiplier = 1.0
        mode       = "normal"

        # ── 1. Kill switch comportemental (streak fatal) ──────────────────────
        if self._loss_streak >= LOSS_STREAK_KILL:
            multiplier = 0.0
            mode       = "paused"
            reasons.append(f"🛑 {self._loss_streak} pertes consécutives — pause totale")

        # ── 2. Cooldown après grosse perte ───────────────────────────────────
        elif time.time() < self._cooldown_until:
            remaining = int(self._cooldown_until - time.time()) // 60
            multiplier = min(multiplier, 0.0)
            mode       = "paused"
            reasons.append(f"⏱️ Cooldown grosse perte — {remaining} min restantes")

        # ── 3. Streak de pertes sévère ────────────────────────────────────────
        elif self._loss_streak >= LOSS_STREAK_HARD_LIMIT:
            multiplier = min(multiplier, 0.4)
            mode       = "restricted"
            reasons.append(f"🔴 Streak pertes sévère ({self._loss_streak}) — risque ×0.4")

        # ── 4. Streak de pertes doux ──────────────────────────────────────────
        elif self._loss_streak >= LOSS_STREAK_SOFT_LIMIT:
            multiplier = min(multiplier, 0.7)
            mode       = "caution"
            reasons.append(f"⚠️ Streak pertes ({self._loss_streak}) — risque ×0.7")

        # ── 5. Limite de perte journalière ───────────────────────────────────
        if self._daily_pnl_pct < -DAILY_LOSS_LIMIT_PCT:
            multiplier = min(multiplier, 0.0)
            mode       = "paused"
            reasons.append(f"📊 Limite perte journalière atteinte ({self._daily_pnl_pct:.1f}%)")

        # ── 6. Surtrading — fréquence horaire ────────────────────────────────
        trades_last_hour = self._count_trades_last_hour()
        if trades_last_hour >= MAX_TRADES_PER_HOUR:
            multiplier = min(multiplier, 0.5)
            if mode == "normal":
                mode = "caution"
            reasons.append(f"⚡ Surtrading détecté ({trades_last_hour} trades/h — max {MAX_TRADES_PER_HOUR})")

        # ── 7. Limite journalière ─────────────────────────────────────────────
        if self._daily_trades >= MAX_TRADES_PER_DAY:
            multiplier = min(multiplier, 0.0)
            mode       = "paused"
            reasons.append(f"📅 Limite journalière atteinte ({self._daily_trades}/{MAX_TRADES_PER_DAY} trades)")

        # ── 8. Heures à faible liquidité ──────────────────────────────────────
        hour_utc = datetime.now(timezone.utc).hour
        if hour_utc in LOW_LIQUIDITY_HOURS_UTC:
            multiplier = min(multiplier, 0.5)
            if mode == "normal":
                mode = "caution"
            reasons.append(f"🌙 Faible liquidité (heure UTC={hour_utc}:00)")

        # ── Détecter les changements d'état ───────────────────────────────────
        prev_mult = self._risk_multiplier
        prev_mode = self._discipline_mode

        self._risk_multiplier  = round(multiplier, 2)
        self._discipline_mode  = mode
        self._current_reasons  = reasons

        # Publier uniquement si changement significatif
        if abs(multiplier - prev_mult) > 0.05 or mode != prev_mode:
            await self.bus.publish(CHANNELS["behavior_alert"], {
                "type":             "behavior_update",
                "agent":            self.name,
                "risk_multiplier":  self._risk_multiplier,
                "discipline_mode":  self._discipline_mode,
                "loss_streak":      self._loss_streak,
                "daily_trades":     self._daily_trades,
                "daily_pnl_pct":    round(self._daily_pnl_pct, 3),
                "reasons":          reasons,
            })

            # Alerte Telegram si passage en mode restrictif
            if mode in ("restricted", "paused") and self.telegram:
                try:
                    reason_str = " | ".join(reasons) if reasons else "Discipline activée"
                    await self.telegram.behavior_alert(
                        mode       = mode,
                        multiplier = multiplier,
                        reasons    = reasons,
                        streak     = self._loss_streak,
                    )
                except Exception as exc:
                    logger.warning("[%s] Telegram behavior_alert: %s", self.name, exc)

            logger.info(
                "[%s] État comportemental → %s (×%.2f) | %s",
                self.name, mode.upper(), multiplier,
                " | ".join(reasons) if reasons else "Comportement normal",
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _count_trades_last_hour(self) -> int:
        """Compte le nombre de trades dans la dernière heure."""
        if not self._trade_timestamps:
            return 0
        now  = datetime.now(timezone.utc)
        count = 0
        for ts_str in self._trade_timestamps:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if (now - ts).total_seconds() <= 3600:
                    count += 1
            except Exception:
                pass
        return count

    def _write_behavior_note(self) -> None:
        """Écrit une note de comportement dans vault/behavior/."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")

        frontmatter = {
            "date":             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "agent":            "BehaviorAgent",
            "type":             "behavior_alert",
            "discipline_mode":  self._discipline_mode,
            "risk_multiplier":  self._risk_multiplier,
            "loss_streak":      self._loss_streak,
            "daily_trades":     self._daily_trades,
            "tags":             ["behaviour", "discipline", self._discipline_mode],
        }

        reasons_md = "\n".join(f"- {r}" for r in self._current_reasons) or "- Comportement normal"

        emoji_map = {"normal": "✅", "caution": "⚠️", "restricted": "🔴", "paused": "🛑"}
        emoji     = emoji_map.get(self._discipline_mode, "❓")

        content = f"""## {emoji} Rapport Comportemental — {date_str}

### État Actuel
| Paramètre | Valeur |
|---|---|
| Mode | **`{self._discipline_mode.upper()}`** |
| Multiplicateur de risque | **`×{self._risk_multiplier:.2f}`** |
| Streak de pertes | `{self._loss_streak}` |
| Trades aujourd'hui | `{self._daily_trades}/{MAX_TRADES_PER_DAY}` |
| P&L journalier | `{self._daily_pnl_pct:+.2f}%` |
| Trades (dernière heure) | `{self._count_trades_last_hour()}/{MAX_TRADES_PER_HOUR}` |

### Raisons
{reasons_md}

### Impact
Le RiskAgent applique ce multiplicateur sur le sizing de chaque position.
Multiplicateur `×{self._risk_multiplier:.2f}` = risque/trade réduit à `{self._risk_multiplier:.0%}` du niveau normal.

### Liens
[[agents/BehaviorAgent]] | [[agents/RiskAgent]] | [[agents/MetaAgent]]
"""
        self.obsidian.write_note("behavior", f"behavior_{date_str}", frontmatter, content)

    # ── API publique ──────────────────────────────────────────────────────────

    @property
    def risk_multiplier(self) -> float:
        """Retourne le multiplicateur de risque comportemental actuel."""
        return self._risk_multiplier

    @property
    def discipline_mode(self) -> str:
        return self._discipline_mode

    @property
    def is_trading_allowed(self) -> bool:
        """True si le trading est autorisé (multiplicateur > 0)."""
        return self._risk_multiplier > 0.0
