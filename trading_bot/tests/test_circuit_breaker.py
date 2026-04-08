"""Tests pour le CircuitBreaker — protection automatique du capital."""

import sys
sys.path.insert(0, ".")

from core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, BreakerState


def make_cb(**kwargs) -> CircuitBreaker:
    return CircuitBreaker(config=CircuitBreakerConfig(**kwargs))


# ── Etat initial ──────────────────────────────────────────────────────────────

def test_initial_state():
    cb = make_cb()
    assert cb.state == BreakerState.CLOSED
    assert cb.can_trade() is True
    assert cb.size_factor() == 1.0


# ── Pertes consecutives ──────────────────────────────────────────────────────

def test_half_open_after_3_losses():
    cb = make_cb(half_open_losses=3, max_consecutive_losses=5)
    for _ in range(3):
        cb.record_trade(pnl_usd=-10, capital=9900, drawdown_pct=1.0)
    assert cb.state == BreakerState.HALF
    assert cb.size_factor() == 0.5


def test_open_after_5_losses():
    cb = make_cb(max_consecutive_losses=5)
    for _ in range(5):
        cb.record_trade(pnl_usd=-10, capital=9800, drawdown_pct=2.0)
    assert cb.state == BreakerState.OPEN
    assert cb.can_trade() is False


def test_win_resets_streak():
    cb = make_cb(half_open_losses=3)
    for _ in range(2):
        cb.record_trade(pnl_usd=-10, capital=9900, drawdown_pct=1.0)
    cb.record_trade(pnl_usd=20, capital=9920, drawdown_pct=0.5)
    assert cb.state == BreakerState.CLOSED
    assert cb.can_trade() is True


# ── Drawdown ─────────────────────────────────────────────────────────────────

def test_open_on_max_drawdown():
    cb = make_cb(max_drawdown_pct=15.0)
    cb.record_trade(pnl_usd=-1500, capital=8500, drawdown_pct=15.0)
    assert cb.state == BreakerState.OPEN


def test_half_on_warning_drawdown():
    cb = make_cb(warning_drawdown_pct=10.0, max_drawdown_pct=15.0)
    cb.record_trade(pnl_usd=-50, capital=9000, drawdown_pct=10.0)
    assert cb.state == BreakerState.HALF


# ── Perte journaliere ────────────────────────────────────────────────────────

def test_open_on_daily_loss_limit():
    cb = make_cb(max_daily_loss_usd=500)
    cb.record_trade(pnl_usd=-501, capital=9499, drawdown_pct=5.0)
    assert cb.state == BreakerState.OPEN


# ── Force open / close ───────────────────────────────────────────────────────

def test_force_open_blocks_trading():
    cb = make_cb()
    cb.force_open("test manual")
    assert cb.state == BreakerState.OPEN
    assert cb.can_trade() is False


def test_force_close_resets():
    cb = make_cb()
    cb.force_open("test")
    cb.force_close()
    assert cb.state == BreakerState.CLOSED
    assert cb.can_trade() is True


# ── Snapshot ─────────────────────────────────────────────────────────────────

def test_snapshot_format():
    cb = make_cb()
    cb.record_trade(pnl_usd=-10, capital=9990, drawdown_pct=0.1)
    snap = cb.snapshot()
    assert "state" in snap
    assert "consecutive_losses" in snap
    assert "daily_pnl_usd" in snap
    assert snap["consecutive_losses"] == 1


# ── Win after HALF → retour CLOSED ──────────────────────────────────────────

def test_win_after_half_returns_to_closed():
    cb = make_cb(half_open_losses=2)
    cb.record_trade(pnl_usd=-10, capital=9990, drawdown_pct=0.1)
    cb.record_trade(pnl_usd=-10, capital=9980, drawdown_pct=0.2)
    assert cb.state == BreakerState.HALF
    cb.record_trade(pnl_usd=30, capital=10010, drawdown_pct=0.0)
    assert cb.state == BreakerState.CLOSED
