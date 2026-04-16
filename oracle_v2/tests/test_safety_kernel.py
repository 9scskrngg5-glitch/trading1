"""
Tests Safety Kernel — vérifie le rejet et l'ajustement d'ordres.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.brain.safety_kernel import SafetyKernel, Order


def make_order(**kwargs):
    defaults = dict(
        symbol="BTCUSDT",
        direction="LONG",
        size_usdt=500.0,
        leverage=1.5,
        sl_pct=0.010,
        tp_pct=0.025,
        source_strate="MOMENTUM",
        confidence=0.75
    )
    defaults.update(kwargs)
    return Order(**defaults)


class TestSafetyKernel:

    def test_valid_order_clears(self):
        sk = SafetyKernel()
        order = make_order()
        report = sk.validate(order, capital=10_000)
        assert report.cleared is True
        assert report.reason == "CLEARED"

    def test_rejects_excessive_leverage(self):
        sk = SafetyKernel(max_leverage=2.0)
        order = make_order(leverage=3.0)
        report = sk.validate(order, capital=10_000)
        assert report.cleared is False
        assert "LEVERAGE_EXCEEDED" in report.reason

    def test_rejects_sl_too_tight(self):
        sk = SafetyKernel(min_sl_pct=0.005)
        order = make_order(sl_pct=0.002)
        report = sk.validate(order, capital=10_000)
        assert report.cleared is False
        assert "SL_TOO_TIGHT" in report.reason

    def test_rejects_sl_too_wide(self):
        sk = SafetyKernel(max_sl_pct=0.02)
        order = make_order(sl_pct=0.03)
        report = sk.validate(order, capital=10_000)
        assert report.cleared is False
        assert "SL_TOO_WIDE" in report.reason

    def test_adjusts_oversized_position(self):
        sk = SafetyKernel(max_position_pct=0.10)
        order = make_order(size_usdt=2000)  # 20% of 10k
        report = sk.validate(order, capital=10_000)
        assert report.cleared is True
        assert report.reason == "SIZE_ADJUSTED"
        assert report.adjusted_size == 1000.0  # 10% of 10k

    def test_rejects_too_many_positions(self):
        sk = SafetyKernel(max_open_positions=2)
        o1 = make_order(symbol="BTCUSDT")
        o2 = make_order(symbol="ETHUSDT")
        sk.register_open(o1)
        sk.register_open(o2)
        o3 = make_order(symbol="BNBUSDT")
        report = sk.validate(o3, capital=10_000)
        assert report.cleared is False
        assert "MAX_POSITIONS" in report.reason

    def test_rejects_correlated_overexposure(self):
        sk = SafetyKernel(max_correlated_positions=2)
        sk.register_open(make_order(symbol="BTCUSDT"))
        sk.register_open(make_order(symbol="ETHUSDT"))
        order = make_order(symbol="BNBUSDT")
        report = sk.validate(order, capital=10_000)
        assert report.cleared is False
        assert "CORRELATED_OVEREXPOSURE" in report.reason

    def test_register_and_close_positions(self):
        sk = SafetyKernel()
        order = make_order(symbol="BTCUSDT")
        sk.register_open(order)
        assert len(sk.open_positions) == 1
        sk.register_close("BTCUSDT")
        assert len(sk.open_positions) == 0

    def test_non_crypto_not_correlated(self):
        sk = SafetyKernel(max_correlated_positions=2)
        sk.register_open(make_order(symbol="BTCUSDT"))
        sk.register_open(make_order(symbol="ETHUSDT"))
        # Gold is not crypto — should not trigger correlated check
        order = make_order(symbol="XAUUSD")
        report = sk.validate(order, capital=10_000)
        assert report.cleared is True
