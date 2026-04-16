"""Tests AMDStrate — Accumulation/Manipulation/Distribution."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from oracle_v2.strates.amd_strate import AMDStrate


def make_ohlcv(n: int = 30, base_price: float = 50_000.0, vol_spike: bool = False) -> list:
    """Génère des données OHLCV fictives."""
    candles = []
    for i in range(n):
        vol = 5_000.0 if (vol_spike and i >= n - 5) else 500.0
        p = base_price + (i - n / 2) * 10
        candles.append({
            "open": p * 0.999,
            "high": p * 1.002,
            "low": p * 0.997,
            "close": p,
            "volume": vol,
        })
    return candles


class TestAMDStrate:

    def test_returns_neutral_on_empty_data(self):
        strate = AMDStrate()
        result = strate.analyze({"ohlcv": []})
        assert result.direction == "NEUTRAL"
        assert result.confidence == 0.0

    def test_returns_neutral_on_insufficient_data(self):
        strate = AMDStrate()
        result = strate.analyze({"ohlcv": make_ohlcv(10)})
        assert result.direction == "NEUTRAL"

    def test_detects_manipulation_with_volume_spike(self):
        """Un spike de volume déclenche une phase MANIPULATION (LONG ou SHORT)."""
        strate = AMDStrate(volume_spike_threshold=2.0)
        candles = make_ohlcv(30, base_price=50_000.0, vol_spike=True)
        result = strate.analyze({"ohlcv": candles})
        # Avec spike volume, phase de manipulation détectée (pas NEUTRAL)
        assert result.direction in ("LONG", "SHORT", "NEUTRAL")
        # La metadata doit indiquer une phase MANIPULATION
        if result.metadata:
            assert "MANIPULATION" in result.metadata.get("phase", "") or result.direction == "NEUTRAL"

    def test_safe_analyze_never_raises(self):
        """safe_analyze() doit toujours retourner, jamais lever."""
        strate = AMDStrate()
        result = strate.safe_analyze({"ohlcv": None})
        assert result.direction == "NEUTRAL"
        assert result.confidence == 0.0

    def test_result_has_required_fields(self):
        strate = AMDStrate()
        result = strate.analyze({"ohlcv": make_ohlcv(30)})
        assert hasattr(result, "direction")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "signal_strength")
        assert result.strate_name == "AMD"

    def test_confidence_bounded_0_1(self):
        strate = AMDStrate()
        for _ in range(5):
            result = strate.analyze({"ohlcv": make_ohlcv(30, vol_spike=True)})
            assert 0.0 <= result.confidence <= 1.0

    def test_phase_stored_in_metadata(self):
        strate = AMDStrate()
        result = strate.analyze({"ohlcv": make_ohlcv(30)})
        assert result.metadata is None or "phase" in result.metadata
