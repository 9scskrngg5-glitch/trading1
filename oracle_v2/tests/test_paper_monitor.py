"""
Tests PaperPositionMonitor — circuit de clôture SL/TP en paper mode.

Couvre :
  - LONG : SL hit, TP hit, ni l'un ni l'autre (en cours)
  - SHORT : SL hit, TP hit
  - Slippage : prise en compte dans le PnL SL
  - Comportement si entry_price absent ou mode != paper
  - Retrait de la position après clôture (pas de double-close)
  - Test d'intégration : TradeOpenedEvent → bus → register() → check_positions()
"""
import sys
import os

import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from oracle_v2.paper_monitor import PaperPositionMonitor
from oracle_v2.connectors.base_connector import Ticker


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_event(
    symbol="BTCUSDT",
    direction="LONG",
    entry_price=100.0,
    sl_pct=0.02,
    tp_pct=0.05,
    trade_id=42,
    mode="paper",
):
    """Crée un mock TradeOpenedEvent avec les champs nécessaires."""
    ev = MagicMock()
    ev.symbol = symbol
    ev.direction = direction
    ev.entry_price = entry_price
    ev.sl_pct = sl_pct
    ev.tp_pct = tp_pct
    ev.trade_id = trade_id
    ev.mode = mode
    return ev


def make_binance(price: float):
    """Crée un connecteur mock retournant un Ticker au prix donné."""
    binance = AsyncMock()
    binance.fetch_ticker.return_value = Ticker(
        symbol="BTCUSDT",
        bid=price * 0.9999,
        ask=price * 1.0001,
        last=price,
        volume_24h=50_000.0,
        change_pct=0.0,
    )
    return binance


# ─── Tests unitaires : _evaluate ──────────────────────────────────────────────

class TestEvaluate:
    """Tests de la logique SL/TP sans I/O async."""

    def test_long_sl_hit(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        event = make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=97.9)  # sous 98.0 (SL)
        assert result is not None
        hit_type, pnl = result
        assert hit_type == "SL"
        assert pnl == pytest.approx(-0.02)

    def test_long_tp_hit(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        event = make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=105.1)  # au-dessus de 105.0 (TP)
        assert result is not None
        hit_type, pnl = result
        assert hit_type == "TP"
        assert pnl == pytest.approx(0.05)

    def test_long_in_range(self):
        monitor = PaperPositionMonitor()
        event = make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        # Entre SL (98) et TP (105) → rien
        assert monitor._evaluate(pos, current_price=101.0) is None

    def test_short_sl_hit(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        event = make_event(direction="SHORT", entry_price=100.0, sl_pct=0.02, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=102.1)  # au-dessus de 102.0 (SL)
        assert result is not None
        hit_type, pnl = result
        assert hit_type == "SL"
        assert pnl == pytest.approx(-0.02)

    def test_short_tp_hit(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        event = make_event(direction="SHORT", entry_price=100.0, sl_pct=0.02, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=94.9)  # sous 95.0 (TP short)
        assert result is not None
        hit_type, pnl = result
        assert hit_type == "TP"
        assert pnl == pytest.approx(0.05)

    def test_slippage_applied_on_sl(self):
        """Le slippage doit aggraver la perte SL."""
        monitor = PaperPositionMonitor(slippage_pct=0.001)
        event = make_event(direction="LONG", entry_price=100.0, sl_pct=0.02)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=97.0)
        assert result is not None
        _, pnl = result
        assert pnl == pytest.approx(-(0.02 + 0.001))

    def test_slippage_not_applied_on_tp(self):
        """Pas de slippage sur un TP (ordre passif)."""
        monitor = PaperPositionMonitor(slippage_pct=0.001)
        event = make_event(direction="LONG", entry_price=100.0, tp_pct=0.05)
        monitor.register(event)
        pos = monitor._positions["BTCUSDT"]

        result = monitor._evaluate(pos, current_price=106.0)
        assert result is not None
        _, pnl = result
        assert pnl == pytest.approx(0.05)  # pas de slippage


# ─── Tests async : check_positions ────────────────────────────────────────────

class TestCheckPositions:

    @pytest.mark.asyncio
    async def test_sl_triggers_close(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        monitor.register(make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, trade_id=1))

        binance = make_binance(price=96.0)   # sous SL (98.0)
        engine = AsyncMock()

        await monitor.check_positions(binance, engine)

        engine.close_position.assert_called_once_with("BTCUSDT", pytest.approx(-0.02), 1)
        assert "BTCUSDT" not in monitor.watched_symbols  # position retirée

    @pytest.mark.asyncio
    async def test_tp_triggers_close(self):
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        monitor.register(make_event(direction="LONG", entry_price=100.0, tp_pct=0.05, trade_id=7))

        binance = make_binance(price=106.0)   # au-dessus de TP (105.0)
        engine = AsyncMock()

        await monitor.check_positions(binance, engine)

        engine.close_position.assert_called_once_with("BTCUSDT", pytest.approx(0.05), 7)
        assert monitor.watched_count == 0

    @pytest.mark.asyncio
    async def test_no_trigger_when_in_range(self):
        monitor = PaperPositionMonitor()
        monitor.register(make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, tp_pct=0.05))

        binance = make_binance(price=101.5)  # entre SL et TP
        engine = AsyncMock()

        await monitor.check_positions(binance, engine)

        engine.close_position.assert_not_called()
        assert monitor.watched_count == 1  # toujours en surveillance

    @pytest.mark.asyncio
    async def test_no_double_close(self):
        """Une position fermée ne doit pas déclencher un second close."""
        monitor = PaperPositionMonitor(slippage_pct=0.0)
        monitor.register(make_event(direction="LONG", entry_price=100.0, sl_pct=0.02, trade_id=3))

        binance = make_binance(price=95.0)  # SL hit
        engine = AsyncMock()

        await monitor.check_positions(binance, engine)
        await monitor.check_positions(binance, engine)  # deuxième appel

        assert engine.close_position.call_count == 1  # appelé UNE seule fois

    @pytest.mark.asyncio
    async def test_binance_none_skips(self):
        """Sans connecteur, aucune action ne doit être prise."""
        monitor = PaperPositionMonitor()
        monitor.register(make_event())
        engine = AsyncMock()

        await monitor.check_positions(binance=None, execution_engine=engine)

        engine.close_position.assert_not_called()


# ─── Tests register() ─────────────────────────────────────────────────────────

class TestRegister:

    def test_ignores_live_mode(self):
        monitor = PaperPositionMonitor()
        monitor.register(make_event(mode="live"))
        assert monitor.watched_count == 0

    def test_ignores_missing_entry_price(self):
        monitor = PaperPositionMonitor()
        monitor.register(make_event(entry_price=0.0))
        assert monitor.watched_count == 0

    def test_registers_valid_event(self):
        monitor = PaperPositionMonitor()
        monitor.register(make_event(symbol="ETHUSDT", entry_price=3000.0))
        assert "ETHUSDT" in monitor.watched_symbols

    def test_remove_clears_position(self):
        monitor = PaperPositionMonitor()
        monitor.register(make_event(symbol="BTCUSDT", entry_price=50000.0))
        assert monitor.watched_count == 1
        monitor.remove("BTCUSDT")
        assert monitor.watched_count == 0


# ─── Test d'intégration : Event Bus → register ────────────────────────────────

class TestBusIntegration:

    @pytest.mark.asyncio
    async def test_event_bus_wires_register(self):
        """
        Vérifie que le bus global déclenche bien monitor.register()
        quand un TradeOpenedEvent est émis — tel que câblé dans oracle_system.
        """
        from oracle_v2.events import get_event_bus, reset_event_bus, TradeOpenedEvent, EventType

        reset_event_bus()
        bus = get_event_bus()
        monitor = PaperPositionMonitor()

        bus.subscribe(EventType.TRADE_OPENED, monitor.register)

        await bus.emit(TradeOpenedEvent(
            symbol="BTCUSDT",
            direction="LONG",
            size_usdt=500.0,
            leverage=1.0,
            sl_pct=0.02,
            tp_pct=0.05,
            confidence=0.8,
            mode="paper",
            trade_id=99,
            entry_price=45000.0,
        ))

        assert "BTCUSDT" in monitor.watched_symbols
        pos = monitor._positions["BTCUSDT"]
        assert pos.entry_price == 45000.0
        assert pos.sl_pct == 0.02

        reset_event_bus()
