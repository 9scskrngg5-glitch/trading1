"""Tests pour le scoring adaptatif de ScanAgent."""

import sys
sys.path.insert(0, ".")

from agents.scan_agent import ScanAgent
from models.signals import SignalType


def score(**kwargs):
    """Helper pour appeler _adaptive_score avec des defaults."""
    defaults = dict(
        rsi=50, macd_hist=0, prev_macd_hist=0,
        bb_position=0.5, vol_ratio=1.0,
        w_rsi=1.0, w_macd=1.0, w_bb=1.0, w_vol=1.0,
    )
    defaults.update(kwargs)
    return ScanAgent._adaptive_score(**defaults)


# ── Signaux neutres ──────────────────────────────────────────────────────────

def test_neutral_on_all_flat():
    direction, conf = score(rsi=50, macd_hist=0, bb_position=0.5)
    assert direction == SignalType.NEUTRAL


def test_mixed_signals_macd_cross_dominates():
    # RSI bullish (65) mais MACD crossover bearish → MACD cross est plus fort
    direction, conf = score(rsi=65, macd_hist=-0.5, prev_macd_hist=0.5, bb_position=0.5)
    # MACD crossover (-30 pts) domine RSI (+8 pts) → bearish
    assert direction == SignalType.BEARISH


def test_truly_mixed_signals_is_neutral():
    # RSI legerement haussier, MACD legerement baissier (pas de cross) → neutre
    direction, conf = score(rsi=55, macd_hist=-0.1, prev_macd_hist=-0.2, bb_position=0.5)
    assert direction == SignalType.NEUTRAL


# ── Signaux bullish ──────────────────────────────────────────────────────────

def test_bullish_on_macd_crossover():
    direction, conf = score(rsi=60, macd_hist=0.1, prev_macd_hist=-0.1, bb_position=0.6)
    assert direction == SignalType.BULLISH
    assert conf >= 40


def test_bullish_with_volume_boost():
    _, conf_low = score(rsi=65, macd_hist=0.5, prev_macd_hist=0.3, bb_position=0.7, vol_ratio=1.0)
    _, conf_high = score(rsi=65, macd_hist=0.5, prev_macd_hist=0.3, bb_position=0.7, vol_ratio=2.0)
    assert conf_high > conf_low


def test_bullish_all_aligned():
    direction, conf = score(rsi=70, macd_hist=0.5, prev_macd_hist=-0.1, bb_position=0.7, vol_ratio=1.5)
    assert direction == SignalType.BULLISH
    assert conf >= 60  # signal fort quand tout est aligne


# ── Signaux bearish ──────────────────────────────────────────────────────────

def test_bearish_on_macd_crossover():
    direction, conf = score(rsi=40, macd_hist=-0.1, prev_macd_hist=0.1, bb_position=0.3)
    assert direction == SignalType.BEARISH
    assert conf >= 40


def test_bearish_all_aligned():
    direction, conf = score(rsi=30, macd_hist=-0.5, prev_macd_hist=0.1, bb_position=0.2, vol_ratio=1.5)
    assert direction == SignalType.BEARISH
    assert conf >= 60


# ── Poids des indicateurs ───────────────────────────────────────────────────

def test_zero_weight_disables_indicator():
    # MACD crossover bullish mais poids=0 → pas de contribution
    direction1, conf1 = score(rsi=50, macd_hist=0.1, prev_macd_hist=-0.1, w_macd=0)
    direction2, conf2 = score(rsi=50, macd_hist=0.1, prev_macd_hist=-0.1, w_macd=1.0)
    assert conf1 < conf2


# ── Confidence toujours 0-100 ────────────────────────────────────────────────

def test_confidence_bounded():
    # Cas extreme : tous les signaux max
    _, conf = score(rsi=95, macd_hist=10, prev_macd_hist=-10, bb_position=0.01, vol_ratio=5.0)
    assert 0 <= conf <= 100


# ── Mean reversion ───────────────────────────────────────────────────────────

def test_reversal_bb_low_plus_macd_cross():
    direction, conf = score(rsi=45, macd_hist=0.1, prev_macd_hist=-0.1, bb_position=0.1)
    assert direction == SignalType.BULLISH  # rebond bas de bande + MACD cross
