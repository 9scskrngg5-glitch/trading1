"""
BaseAgent — Classe abstraite pour tous les agents du système.
Gère le cycle de vie, le heartbeat, et la tolérance aux pannes.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from .message_bus import MessageBus, CHANNELS
from .obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Classe de base pour tous les agents de trading.

    Cycle de vie :
        start() → setup() → _register_subscriptions()
                          → _main_loop()  ──┐ tournent en
                          → _heartbeat()  ──┘ parallèle
        stop()  → annule toutes les tâches
    """

    def __init__(
        self,
        name: str,
        vault_folder: str,
        bus: MessageBus,
        obsidian: ObsidianClient,
        config: dict[str, Any],
    ):
        self.name = name
        self.vault_folder = vault_folder
        self.bus = bus
        self.obsidian = obsidian
        self.config = config

        self.is_running = False
        self._tasks: list[asyncio.Task] = []

    # ── Interface abstraite ───────────────────────────────────────────────────

    @abstractmethod
    async def setup(self) -> None:
        """Initialisation de l'agent (connexions API, ressources externes)."""

    @abstractmethod
    async def run_cycle(self) -> None:
        """Logique principale — exécutée à chaque intervalle configuré."""

    def _register_subscriptions(self) -> None:
        """
        Override pour s'abonner aux canaux du bus.
        Appelé une fois lors du démarrage, APRÈS setup().
        """

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Démarre l'agent et ses tâches de fond."""
        logger.info("[%s] Démarrage...", self.name)
        self.is_running = True

        await self.setup()
        self._register_subscriptions()

        self._tasks = [
            asyncio.create_task(self._main_loop(),     name=f"{self.name}:main"),
            asyncio.create_task(self._heartbeat_loop(), name=f"{self.name}:heartbeat"),
        ]
        logger.info("[%s] ✅ Actif", self.name)

    async def stop(self) -> None:
        """Arrêt propre de l'agent avec cleanup des ressources."""
        self.is_running = False
        for task in self._tasks:
            task.cancel()
        # Attendre que les tâches soient bien annulées (timeout 10s)
        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] Timeout lors de l'arrêt des tâches", self.name)
        self._tasks.clear()
        await self.cleanup()
        logger.info("[%s] 🛑 Arrêté", self.name)

    async def cleanup(self) -> None:
        """Override pour fermer les ressources (HTTP clients, etc.)."""

    # ── Boucles internes ──────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        """
        Exécute run_cycle() à intervalle régulier.
        Une exception dans run_cycle() est loguée mais n'arrête pas la boucle.
        """
        interval = self.config.get("cycle_interval_seconds", 60)
        while self.is_running:
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[%s] Erreur dans run_cycle: %s", self.name, exc, exc_info=True)
                await self._publish_error(str(exc))
            await asyncio.sleep(interval)

    async def _heartbeat_loop(self) -> None:
        """Publie un heartbeat toutes les 30 secondes pour le monitoring."""
        while self.is_running:
            try:
                await self.bus.publish(
                    CHANNELS["heartbeat"],
                    {
                        "type": "heartbeat",
                        "agent": self.name,
                        "status": "alive",
                    },
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("[%s] Heartbeat échoué: %s", self.name, exc)
            await asyncio.sleep(30)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _publish_error(self, error_msg: str) -> None:
        """Signale une erreur sur le bus système."""
        try:
            await self.bus.publish(
                CHANNELS["error"],
                {
                    "type": "agent_error",
                    "agent": self.name,
                    "error": error_msg,
                },
            )
        except Exception:
            pass  # Ne pas propager d'exception dans le handler d'erreur

    def _build_frontmatter(
        self,
        asset: str,
        signal_type: str,
        confidence: int,
        timeframe: str = "",
        extra: dict | None = None,
    ) -> dict:
        """Construit le frontmatter YAML standard pour toutes les notes."""
        market = self.config.get("market", "crypto")
        fm: dict[str, Any] = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "agent": self.name,
            "asset": asset,
            "signal": signal_type,
            "confiance": confidence,
            "tags": ["trading", market],
        }
        if timeframe:
            fm["timeframe"] = timeframe
            fm["tags"].append(timeframe)
        if extra:
            fm.update(extra)
        return fm
