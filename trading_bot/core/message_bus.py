"""
Message Bus — Redis Pub/Sub
Communication inter-agents asynchrone.
"""

import json
import asyncio
import logging
from typing import Callable, Awaitable
from datetime import datetime, timezone

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore

logger = logging.getLogger(__name__)

# ── Canaux Redis ──────────────────────────────────────────────────────────────
CHANNELS = {
    # ── Signaux de marché ─────────────────────────────────────────────────────
    "signals_technical":    "signals:technical",
    "signals_fundamental":  "signals:fundamental",

    # ── Pipeline de trading ───────────────────────────────────────────────────
    "orders_validated":     "orders:validated",
    "orders_executed":      "orders:executed",
    "portfolio_update":     "portfolio:update",

    # ── Contexte marché ───────────────────────────────────────────────────────
    "market_context":       "market:context",       # SynthesisAgent → DataSheet structurée
    "regime":               "market:regime",        # RegimeAgent → PredictAgent/RiskAgent/SynthesisAgent

    # ── Intelligence / Mémoire ────────────────────────────────────────────────
    "knowledge_query":      "knowledge:query",      # Agents → KnowledgeAgent (requête similitude)
    "knowledge_result":     "knowledge:result",     # KnowledgeAgent → agents (réponse enrichie)

    # ── Comportement / Discipline ─────────────────────────────────────────────
    "behavior_alert":       "system:behavior",      # BehaviorAgent → RiskAgent/MetaAgent

    # ── R&D Shadow ────────────────────────────────────────────────────────────
    "shadow_result":        "shadow:result",        # ShadowAgent → MetaAgent (perf stratégies alternatives)

    # ── Directives CEO ────────────────────────────────────────────────────────
    "meta_directive":       "meta:directive",       # MetaAgent → agents (poids, kill switch, ajustements)

    # ── Intelligence LLM ──────────────────────────────────────────────────────
    "daily_thesis":         "meta:daily_thesis",    # MetaAgent → tous les agents
    "council_result":       "council:result",       # Council → logs

    # ── Système ───────────────────────────────────────────────────────────────
    "heartbeat":            "system:heartbeat",
    "error":                "system:error",
    "decisions":            "decisions:convergence",
}

Handler = Callable[[dict], Awaitable[None]]


class MessageBus:
    """
    Wrapper Redis Pub/Sub.
    - Sérialisation JSON automatique
    - Ajout d'un timestamp UTC à chaque message
    - Gestion des exceptions dans les handlers (isolation)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._publisher: aioredis.Redis | None = None
        self._subscriber: aioredis.Redis | None = None
        self._handlers: dict[str, list[Handler]] = {}

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._publisher = await aioredis.from_url(
            self.redis_url, decode_responses=True
        )
        self._subscriber = await aioredis.from_url(
            self.redis_url, decode_responses=True
        )
        logger.info("MessageBus ▶ connecté à Redis (%s)", self.redis_url)

    async def disconnect(self) -> None:
        if self._publisher:
            await self._publisher.aclose()
        if self._subscriber:
            await self._subscriber.aclose()
        logger.info("MessageBus ▶ déconnecté")

    # ── Publication ───────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: dict) -> None:
        """Publie un message (dict) sur un canal Redis."""
        if self._publisher is None:
            raise RuntimeError("MessageBus non connecté — appelez connect() d'abord")

        payload = {
            **message,
            "_ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._publisher.publish(channel, json.dumps(payload, ensure_ascii=False))
        logger.debug("📤  [%s] type=%s", channel, message.get("type", "?"))

    # ── Souscription ──────────────────────────────────────────────────────────

    def subscribe(self, channel: str, handler: Handler) -> None:
        """Enregistre un handler asynchrone pour un canal."""
        self._handlers.setdefault(channel, []).append(handler)
        logger.debug("📥  Handler enregistré sur [%s]", channel)

    async def listen(self) -> None:
        """
        Démarre l'écoute en boucle infinie.
        Chaque message est dispatchable à tous les handlers du canal.
        """
        if not self._handlers:
            logger.warning("MessageBus ▶ aucun handler enregistré, listen() inutile")
            return

        pubsub = self._subscriber.pubsub()
        await pubsub.subscribe(*self._handlers.keys())
        logger.info(
            "MessageBus ▶ écoute sur %d canaux : %s",
            len(self._handlers),
            list(self._handlers.keys()),
        )

        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue

            channel: str = raw["channel"]
            try:
                data = json.loads(raw["data"])
            except json.JSONDecodeError as exc:
                logger.error("JSON invalide sur [%s]: %s", channel, exc)
                continue

            for handler in self._handlers.get(channel, []):
                try:
                    await handler(data)
                except Exception as exc:                                    # Isolation : une erreur dans un handler n'arrête pas les autres
                    logger.error(
                        "Erreur handler [%s]: %s", channel, exc, exc_info=True
                    )
