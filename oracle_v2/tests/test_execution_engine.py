"""Tests ExecutionEngine — compute_atr_sl, compute_volatility_adjusted_size."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from oracle_v2.execution_engine import compute_atr_sl, compute_volatility_adjusted_size


class TestComputeAtrSl:

    def test_returns_hard_floor_when_zero_inputs(self):
        sl, tp = compute_atr_sl(atr=0, price=0, hard_floor=0.005)
        assert sl == 0.005

    def test_sl_adapts_to_high_volatility(self):
        """ATR élevé → SL plus large."""
        sl_low_vol, _ = compute_atr_sl(atr=100, price=50_000, atr_multiplier=1.5)
        sl_high_vol, _ = compute_atr_sl(atr=1_000, price=50_000, atr_multiplier=1.5)
        assert sl_high_vol > sl_low_vol

    def test_sl_adapts_to_low_volatility(self):
        """ATR faible → SL plus serré."""
        sl_low, _ = compute_atr_sl(atr=50, price=50_000, atr_multiplier=1.5, hard_floor=0.001)
        sl_high, _ = compute_atr_sl(atr=500, price=50_000, atr_multiplier=1.5)
        assert sl_low < sl_high

    def test_sl_bounded_by_hard_floor(self):
        sl, _ = compute_atr_sl(atr=1, price=50_000, hard_floor=0.003)
        assert sl >= 0.003

    def test_sl_bounded_by_hard_ceiling(self):
        sl, _ = compute_atr_sl(atr=100_000, price=100, hard_ceiling=0.05)
        assert sl <= 0.05

    def test_tp_is_ratio_times_sl(self):
        sl, tp = compute_atr_sl(atr=500, price=50_000, tp_ratio=2.5)
        assert tp == pytest.approx(sl * 2.5, rel=0.001)

    def test_default_rr_ratio(self):
        sl, tp = compute_atr_sl(atr=500, price=50_000)
        assert tp / sl == pytest.approx(2.5, rel=0.01)

    def test_reasonable_btc_scenario(self):
        """Scénario BTC : ATR≈500$, prix≈50k$ → SL entre 0.3% et 5%."""
        sl, tp = compute_atr_sl(atr=500, price=50_000, atr_multiplier=1.5)
        assert 0.003 <= sl <= 0.05
        assert tp > sl


class TestComputeVolatilityAdjustedSize:

    def test_reduces_size_in_high_volatility(self):
        """Haute volatilité → taille réduite."""
        size_low = compute_volatility_adjusted_size(1000, atr=100, price=50_000)
        size_high = compute_volatility_adjusted_size(1000, atr=2000, price=50_000)
        assert size_high < size_low

    def test_keeps_base_size_in_normal_volatility(self):
        """Volatilité normale → taille ≈ base (pas de réduction majeure)."""
        # ATR/price = 0.01 = 1%, target_risk_pct = 0.01 → ratio=1.0 → taille inchangée
        size = compute_volatility_adjusted_size(1000, atr=500, price=50_000, target_risk_pct=0.01)
        assert size == pytest.approx(1000, rel=0.05)

    def test_never_below_20pct_of_base(self):
        """La taille ajustée ne descend jamais sous 20% de la taille brute."""
        size = compute_volatility_adjusted_size(1000, atr=100_000, price=100)
        assert size >= 200.0

    def test_returns_base_on_zero_price(self):
        size = compute_volatility_adjusted_size(500, atr=0, price=0)
        assert size == 500.0
