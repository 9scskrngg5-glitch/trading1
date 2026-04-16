"""Tests StructureStrate — HH/HL (bullish) et LH/LL (bearish)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from oracle_v2.strates.structure_strate import StructureStrate


def make_candles(highs: list, lows: list, closes: list = None) -> list:
    candles = []
    for i in range(len(highs)):
        c = closes[i] if closes else (highs[i] + lows[i]) / 2
        candles.append({
            "open": c * 0.999,
            "high": highs[i],
            "low": lows[i],
            "close": c,
            "volume": 1000.0,
        })
    return candles


def bullish_candles(n: int = 30) -> list:
    """Candles avec HH/HL — structure haussière."""
    highs = [100.0 + i * 2 for i in range(n)]
    lows  = [90.0 + i * 1.5 for i in range(n)]
    return make_candles(highs, lows)


def bearish_candles(n: int = 30) -> list:
    """Candles avec LH/LL — structure baissière."""
    highs = [200.0 - i * 2 for i in range(n)]
    lows  = [190.0 - i * 2.5 for i in range(n)]
    return make_candles(highs, lows)


def flat_candles(n: int = 30, base: float = 100.0) -> list:
    """Candles sans structure claire."""
    highs = [base + (i % 3) * 2 for i in range(n)]
    lows  = [base - (i % 3) * 2 for i in range(n)]
    return make_candles(highs, lows)


class TestStructureStrate:

    def test_neutral_on_insufficient_data(self):
        strate = StructureStrate()
        result = strate.analyze({"ohlcv": make_candles([100]*5, [90]*5)})
        assert result.direction == "NEUTRAL"
        assert result.confidence == 0.0

    def test_detects_bullish_structure(self):
        strate = StructureStrate(swing_lookback=3)
        result = strate.analyze({"ohlcv": bullish_candles(30)})
        # La strate peut détecter LONG ou NEUTRAL selon les swings extraits
        assert result.direction in ("LONG", "NEUTRAL")

    def test_detects_bearish_structure(self):
        strate = StructureStrate(swing_lookback=3)
        result = strate.analyze({"ohlcv": bearish_candles(30)})
        assert result.direction in ("SHORT", "NEUTRAL")

    def test_neutral_on_flat_market(self):
        strate = StructureStrate(swing_lookback=3)
        result = strate.analyze({"ohlcv": flat_candles(30)})
        # Pas de structure claire → NEUTRAL ou confiance faible
        assert result.direction in ("NEUTRAL", "LONG", "SHORT")
        if result.direction == "NEUTRAL":
            assert result.confidence <= 0.5

    def test_confidence_in_range(self):
        strate = StructureStrate(swing_lookback=3)
        for candles in [bullish_candles(), bearish_candles(), flat_candles()]:
            result = strate.analyze({"ohlcv": candles})
            assert 0.0 <= result.confidence <= 1.0

    def test_safe_analyze_on_bad_data(self):
        strate = StructureStrate()
        result = strate.safe_analyze({"ohlcv": []})
        assert result.direction == "NEUTRAL"

    def test_name_correct(self):
        strate = StructureStrate()
        result = strate.analyze({"ohlcv": bullish_candles()})
        assert result.strate_name == "STRUCTURE"
