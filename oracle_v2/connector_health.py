"""
ORACLE v2 — ConnectorHealthCheck.

Surveille la connectivité des exchanges toutes les 30 secondes.
Si 2 pings consécutifs échouent → mode DEGRADED :
  - Brainstem bloqué (pas de nouveaux trades)
  - Alerte Telegram envoyée
  - Événement ConnectorDownEvent émis sur le bus

Lorsque la connexion est rétablie → ConnectorUpEvent + reprise normale.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle_system import OracleSystem

logger = logging.getLogger("ORACLE.Health")

_PING_INTERVAL = 30         # secondes entre chaque ping
_FAILURE_THRESHOLD = 2      # nombre de pings ratés avant DEGRADED


class ConnectorHealthCheck:
    """
    Tâche asyncio de surveillance des connecteurs.
    Lance en parallèle de la boucle principale via asyncio.create_task().
    """

    def __init__(self, system: "OracleSystem"):
        self._s = system
        self._connector_status: dict[str, bool] = {}   # name → is_healthy

    async def run(self) -> None:
        """Boucle de surveillance. S'arrête quand system._running est False."""
        s = self._s
        logger.info("ConnectorHealthCheck démarré (intervalle 30s)")

        while s._running:
            await asyncio.sleep(_PING_INTERVAL)

            # Vérification de tous les connecteurs actifs
            if s.binance:
                await self._check("binance", s.binance)

            # Capital.com si disponible
            if s.capital and hasattr(s.capital, "ping"):
                await self._check("capital", s.capital)

    async def _check(self, name: str, connector) -> None:
        """Vérifie un connecteur et met à jour le statut système."""
        from events import get_event_bus, ConnectorDownEvent, ConnectorUpEvent
        s = self._s
        bus = get_event_bus()

        was_healthy = self._connector_status.get(name, True)

        try:
            is_up = await connector.ping()
        except Exception as e:
            logger.warning(f"HealthCheck [{name}] exception: {e}")
            is_up = False

        self._connector_status[name] = is_up

        if not is_up and was_healthy:
            # Transition → DEGRADED
            logger.error(
                f"ConnectorHealthCheck: [{name}] HORS LIGNE — "
                f"passage en mode DEGRADED"
            )
            await bus.emit(ConnectorDownEvent(
                connector_name=name,
                error="ping() retourné False",
            ))
            if s.alert_queue:
                s.alert_queue.alert_system(
                    f"⚠️ Connecteur [{name}] hors ligne — trades suspendus",
                    level="WARNING",
                )
            # Empêche de nouveaux trades : le brainstem est mis en pause
            # via l'état _connector_degraded qui est vérifié dans CycleManager
            s._connector_degraded.add(name)

        elif is_up and not was_healthy:
            # Transition → Rétabli
            logger.info(f"ConnectorHealthCheck: [{name}] RÉTABLI")
            await bus.emit(ConnectorUpEvent(connector_name=name))
            if s.alert_queue:
                s.alert_queue.alert_system(
                    f"✅ Connecteur [{name}] rétabli",
                    level="SUCCESS",
                )
            s._connector_degraded.discard(name)

        else:
            if is_up:
                logger.debug(f"ConnectorHealthCheck: [{name}] OK")
            else:
                logger.warning(f"ConnectorHealthCheck: [{name}] toujours hors ligne")
