"""Tests pour le Dynamic Sizer — sizing adaptatif des positions."""

import sys
sys.path.insert(0, ".")

from core.dynamic_sizer import DynamicSizer


def make_sizer(**kwargs) -> DynamicSizer:
    defaults = dict(method="adaptive", base_risk_pct=2.0, min_risk_pct=0.5, max_risk_pct=5.0)
    defaults.update(kwargs)
    return DynamicSizer(**defaults)


# ── Sizing de base ───────────────────────────────────────────────────────────

def test_base_risk_with_default_params():
    sizer = make_sizer()
    risk = sizer.compute(
        win_rate=0.5, avg_win_pct=3.0, avg_loss_pct=1.5,
        confidence=60, drawdown_pct=0, max_drawdown_pct=15,
        atr_pct=1.5, streak=0, total_trades=50,
    )
    assert 0.5 <= risk <= 5.0


def test_high_confidence_increases_risk():
    sizer = make_sizer()
    kwargs = dict(
        win_rate=0.55, avg_win_pct=3.0, avg_loss_pct=1.5,
        drawdown_pct=0, max_drawdown_pct=15,
        atr_pct=1.5, streak=0, total_trades=50,
    )
    risk_low = sizer.compute(confidence=40, **kwargs)
    risk_high = sizer.compute(confidence=90, **kwargs)
    assert risk_high >= risk_low


def test_high_drawdown_reduces_risk():
    sizer = make_sizer()
    kwargs = dict(
        win_rate=0.5, avg_win_pct=3.0, avg_loss_pct=1.5,
        confidence=60, max_drawdown_pct=15,
        atr_pct=1.5, streak=0, total_trades=50,
    )
    risk_no_dd = sizer.compute(drawdown_pct=0, **kwargs)
    risk_high_dd = sizer.compute(drawdown_pct=12, **kwargs)
    assert risk_high_dd < risk_no_dd


def test_losing_streak_reduces_risk():
    sizer = make_sizer()
    kwargs = dict(
        win_rate=0.5, avg_win_pct=3.0, avg_loss_pct=1.5,
        confidence=60, drawdown_pct=0, max_drawdown_pct=15,
        atr_pct=1.5, total_trades=50,
    )
    risk_no_streak = sizer.compute(streak=0, **kwargs)
    risk_losing = sizer.compute(streak=-4, **kwargs)
    assert risk_losing <= risk_no_streak


# ── Bornes ───────────────────────────────────────────────────────────────────

def test_risk_never_below_min():
    sizer = make_sizer(min_risk_pct=0.5)
    risk = sizer.compute(
        win_rate=0.1, avg_win_pct=0.5, avg_loss_pct=5.0,
        confidence=20, drawdown_pct=14, max_drawdown_pct=15,
        atr_pct=5.0, streak=-10, total_trades=100,
    )
    assert risk >= 0.5


def test_risk_never_above_max():
    sizer = make_sizer(max_risk_pct=5.0)
    risk = sizer.compute(
        win_rate=0.9, avg_win_pct=10.0, avg_loss_pct=0.5,
        confidence=100, drawdown_pct=0, max_drawdown_pct=50,
        atr_pct=0.5, streak=10, total_trades=200,
    )
    assert risk <= 5.0


# ── Peu de trades → conservateur ─────────────────────────────────────────────

def test_few_trades_is_conservative():
    sizer = make_sizer()
    kwargs = dict(
        win_rate=0.5, avg_win_pct=3.0, avg_loss_pct=1.5,
        confidence=60, drawdown_pct=0, max_drawdown_pct=15,
        atr_pct=1.5, streak=0,
    )
    risk_few = sizer.compute(total_trades=3, **kwargs)
    risk_many = sizer.compute(total_trades=100, **kwargs)
    assert risk_few <= risk_many
