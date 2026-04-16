"""
ORACLE v2 — Event Bus léger.

Pattern Observer : les composants émettent des événements typés.
Les abonnés (Telegram, UI, Narrator, Logger, MetricsTracker) s'inscrivent
sans que l'émetteur les connaisse.

Usage:
    bus = EventBus()

    # Abonnement
    bus.subscribe(EventType.TRADE_OPENED, my_handler)

    # Émission (sync ou async)
    await bus.emit(TradeOpenedEvent(symbol="BTCUSDT", direction="LONG", ...))

    # Émission fire-and-forget depuis contexte sync
    bus.emit_sync(BrainstemBlockedEvent(reason="COOLING_PERIOD"))
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("ORACLE.Events")


# ─── Types d'événements ───────────────────────────────────────────────────────

class EventType(Enum):
    # Trading
    TRADE_OPENED         = auto()
    TRADE_CLOSED         = auto()
    TRADE_REJECTED       = auto()

    # Signaux
    PARLIAMENT_DECIDED   = auto()
    BRAINSTEM_BLOCKED    = auto()
    SAFETY_REJECTED      = auto()

    # Système
    SYSTEM_STARTED       = auto()
    SYSTEM_STOPPED       = auto()
    CONNECTOR_DOWN       = auto()
    CONNECTOR_UP         = auto()

    # Marchés
    POLYMARKET_SIGNAL    = auto()
    TWITTER_SIGNAL       = auto()
    BTC_ARB_SIGNAL       = auto()


# ─── Événements typés ─────────────────────────────────────────────────────────

@dataclass
class BaseEvent:
    event_type: EventType
    timestamp: float = field(default_factory=lambda: __import__("time").time())


@dataclass
class TradeOpenedEvent(BaseEvent):
    event_type: EventType = EventType.TRADE_OPENED
    symbol: str = ""
    direction: str = ""
    size_usdt: float = 0.0
    leverage: float = 1.0
    sl_pct: float = 0.0
    tp_pct: float = 0.0
    confidence: float = 0.0
    source: str = "PARLIAMENT"
    mode: str = "paper"
    trade_id: Optional[int] = None
    entry_price: float = 0.0  # Prix d'entrée — requis par PaperPositionMonitor pour calculer SL/TP


@dataclass
class TradeClosedEvent(BaseEvent):
    event_type: EventType = EventType.TRADE_CLOSED
    symbol: str = ""
    direction: str = ""
    pnl_pct: float = 0.0
    trade_id: Optional[int] = None
    source_strate: str = ""


@dataclass
class TradeRejectedEvent(BaseEvent):
    event_type: EventType = EventType.TRADE_REJECTED
    symbol: str = ""
    reason: str = ""
    layer: str = ""    # "BRAINSTEM" | "SAFETY" | "CAPITAL"


@dataclass
class ParliamentDecidedEvent(BaseEvent):
    event_type: EventType = EventType.PARLIAMENT_DECIDED
    symbol: str = ""
    direction: str = ""
    strength: float = 0.0
    n_votes: int = 0
    polymarket_aligned: bool = False


@dataclass
class BrainstemBlockedEvent(BaseEvent):
    event_type: EventType = EventType.BRAINSTEM_BLOCKED
    reason: str = ""


@dataclass
class SafetyRejectedEvent(BaseEvent):
    event_type: EventType = EventType.SAFETY_REJECTED
    symbol: str = ""
    reason: str = ""


@dataclass
class ConnectorStatusEvent(BaseEvent):
    connector_name: str = ""
    error: str = ""


@dataclass
class ConnectorDownEvent(ConnectorStatusEvent):
    event_type: EventType = EventType.CONNECTOR_DOWN


@dataclass
class ConnectorUpEvent(ConnectorStatusEvent):
    event_type: EventType = EventType.CONNECTOR_UP


# ─── Event Bus ────────────────────────────────────────────────────────────────

Handler = Callable[[BaseEvent], Any]


class EventBus:
    """
    Bus d'événements ORACLE v2.

    Thread-safe pour les émissions sync (emit_sync).
    Async-safe pour les émissions await (emit).

    Les handlers async sont awaitables ; les handlers sync sont appelés directement.
    Les erreurs dans un handler n'interrompent jamais l'émetteur.
    """

    def __init__(self):
        self._handlers: dict[EventType, list[Handler]] = {}

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """Inscrit un handler à un type d'événement."""
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        """Désinscrit un handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event: BaseEvent) -> None:
        """Émet un événement (async). Await chaque handler async."""
        for handler in self._handlers.get(event.event_type, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"EventBus handler error [{event.event_type}]: {e}")

    def emit_sync(self, event: BaseEvent) -> None:
        """
        Émet un événement depuis un contexte synchrone.
        Les handlers async sont planifiés sur la boucle courante (fire-and-forget).
        """
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        for handler in self._handlers.get(event.event_type, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result) and loop:
                    loop.create_task(result)
            except Exception as e:
                logger.warning(f"EventBus sync handler error [{event.event_type}]: {e}")


# Singleton global — importable depuis n'importe quel module
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Retourne le bus d'événements global (singleton)."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Réinitialise le bus (utile pour les tests)."""
    global _bus
    _bus = None
