"""Tests EventBus — souscription, émission, isolation des handlers."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import pytest
from oracle_v2.events import (
    EventBus, EventType, reset_event_bus, get_event_bus,
    TradeOpenedEvent, TradeClosedEvent, BrainstemBlockedEvent,
    TradeRejectedEvent,
)


@pytest.fixture(autouse=True)
def clean_bus():
    reset_event_bus()
    yield
    reset_event_bus()


class TestEventBus:

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.TRADE_OPENED, handler)
        await bus.emit(TradeOpenedEvent(symbol="BTCUSDT", direction="LONG"))
        assert len(received) == 1
        assert received[0].symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_async_handler(self):
        bus = EventBus()
        received = []

        async def async_handler(event):
            await asyncio.sleep(0)
            received.append(event.symbol)

        bus.subscribe(EventType.TRADE_CLOSED, async_handler)
        await bus.emit(TradeClosedEvent(symbol="ETHUSDT", pnl_pct=0.015))
        assert "ETHUSDT" in received

    @pytest.mark.asyncio
    async def test_multiple_handlers_same_event(self):
        bus = EventBus()
        log = []

        bus.subscribe(EventType.BRAINSTEM_BLOCKED, lambda e: log.append("h1"))
        bus.subscribe(EventType.BRAINSTEM_BLOCKED, lambda e: log.append("h2"))
        await bus.emit(BrainstemBlockedEvent(reason="COOLING_PERIOD"))
        assert log == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_handler_error_does_not_propagate(self):
        bus = EventBus()

        def bad_handler(event):
            raise RuntimeError("Handler crash!")

        received = []
        bus.subscribe(EventType.TRADE_REJECTED, bad_handler)
        bus.subscribe(EventType.TRADE_REJECTED, lambda e: received.append("ok"))

        # Ne doit pas lever d'exception
        await bus.emit(TradeRejectedEvent(symbol="BTC", reason="TEST", layer="TEST"))
        assert received == ["ok"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        received = []

        handler = lambda e: received.append(e)
        bus.subscribe(EventType.TRADE_OPENED, handler)
        bus.unsubscribe(EventType.TRADE_OPENED, handler)

        await bus.emit(TradeOpenedEvent(symbol="BTC"))
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_no_crossfire_between_event_types(self):
        bus = EventBus()
        trade_events = []
        brainstem_events = []

        bus.subscribe(EventType.TRADE_OPENED, lambda e: trade_events.append(e))
        bus.subscribe(EventType.BRAINSTEM_BLOCKED, lambda e: brainstem_events.append(e))

        await bus.emit(TradeOpenedEvent(symbol="BTC"))
        assert len(trade_events) == 1
        assert len(brainstem_events) == 0

    def test_emit_sync_works(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.BRAINSTEM_BLOCKED, lambda e: received.append(e.reason))
        bus.emit_sync(BrainstemBlockedEvent(reason="MAX_DAILY_DRAWDOWN"))
        assert "MAX_DAILY_DRAWDOWN" in received

    def test_singleton_bus(self):
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2

    def test_reset_clears_singleton(self):
        b1 = get_event_bus()
        reset_event_bus()
        b2 = get_event_bus()
        assert b1 is not b2
