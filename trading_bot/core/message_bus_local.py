"""
MessageBus Local — Mode sans Redis (asyncio.Queue en mémoire).
Utilisé en développement / simulation quand Redis n'est pas disponible.
API identique à MessageBus pour un remplacement transparent.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]


class LocalMessageBus:
    """
    Bus de messages in-process basé sur asyncio.Queue.
    Même interface que MessageBus (Redis) → aucun changement dans les agents.
    """

    def __init__(self, *args, **kwargs):
        self._queues:  dict[str, asyncio.Queue]   = {}
        self._handlers: dict[str, list[Handler]]  = {}
        self._running = False

    async def connect(self) -> None:
        self._running = True
        logger.info("LocalMessageBus ▶ démarré (mode in-memory, pas de Redis)")

    async def disconnect(self) -> None:
        self._running = False
        logger.info("LocalMessageBus ▶ arrêté")

    async def publish(self, channel: str, message: dict) -> None:
        payload = {**message, "_ts": datetime.now(timezone.utc).isoformat()}
        q = self._queues.get(channel)
        if q:
            await q.put(payload)
        logger.debug("📤  [%s] %s", channel, message.get("type", "?"))

    def subscribe(self, channel: str, handler: Handler) -> None:
        if channel not in self._queues:
            self._queues[channel]  = asyncio.Queue()
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    async def listen(self) -> None:
        """
        Lance une tâche par canal, surveille leur santé toutes les 3s
        et redémarre automatiquement toute tâche morte.
        Tourne jusqu'à disconnect() ou CancelledError.
        """
        if not self._handlers:
            await asyncio.Event().wait()
            return

        tasks: dict[str, asyncio.Task] = {
            ch: asyncio.create_task(self._consume(ch), name=f"bus:{ch}")
            for ch in self._handlers
        }
        logger.info("LocalMessageBus ▶ écoute sur %d canaux : %s",
                    len(tasks), list(tasks.keys()))

        restart_counts: dict[str, int] = {ch: 0 for ch in self._handlers}
        try:
            while self._running:
                await asyncio.sleep(3.0)
                for ch in list(self._handlers.keys()):
                    t = tasks.get(ch)
                    if t and t.done():
                        exc_info = ""
                        if not t.cancelled():
                            try:
                                ex = t.exception()
                                exc_info = f" | erreur: {ex}"
                            except Exception:
                                pass
                        restart_counts[ch] = restart_counts.get(ch, 0) + 1
                        backoff = min(3.0 * (2 ** min(restart_counts[ch] - 1, 4)), 60.0)
                        logger.warning(
                            "LocalMessageBus ▶ consume [%s] mort%s — redémarrage #%d (backoff %.0fs)",
                            ch, exc_info, restart_counts[ch], backoff,
                        )
                        if restart_counts[ch] > 10:
                            logger.error(
                                "LocalMessageBus ▶ consume [%s] : %d redémarrages — vérifier le handler",
                                ch, restart_counts[ch],
                            )
                        await asyncio.sleep(backoff)
                        tasks[ch] = asyncio.create_task(
                            self._consume(ch), name=f"bus:{ch}"
                        )
        except asyncio.CancelledError:
            pass
        finally:
            for t in tasks.values():
                t.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            logger.info("LocalMessageBus ▶ toutes les tâches consume arrêtées")

    async def _consume(self, channel: str) -> None:
        q       = self._queues[channel]
        handlers= self._handlers[channel]
        while self._running:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=1.0)
                for h in handlers:
                    try:
                        await h(msg)
                    except Exception as exc:
                        logger.error("Handler [%s]: %s", channel, exc, exc_info=True)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
