"""
Tests unitaires — Strate 5 : Behavioral Bias Arbitrage Engine

Couvre :
  - _detect_anchoring : prix proche nombres ronds
  - _detect_loss_aversion : support/résistance testé多次
  - _detect_recency_bias : bougies consécutives même direction
  - _detect_disposition_effect : volume spike + stagnation
  - _detect_herding : long/short ratio extrême
  - _detect_fomo : volume + accélération
  - _detect_panic : mouvement 3-sigma + volume
  - _aggregate_signal : combinaison des biais
  - _compute_contrarian_score : scoring opportunités
  - _compute_sizing_modifier : multiplicateur de position
  - analyze() : résultat complet
  - backtest() : replay sur DataFrame
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest

from core.strate_5_behavioral_bias import (
    BehavioralBiasEngine,
    BehavioralBiasResult,
    BiasSignal,
    BiasType,
    SignalDirection,
    ContrarianAction,
    BacktestResult,
    ROUND_NUMBER_TOLERANCE_PCT,
    SUPPORT_TEST_THRESHOLD,
    CONSECUTIVE_CANDLES_THRESHOLD,
    HERDING_RATIO_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_engine(**kwargs) -> BehavioralBiasEngine:
    """Engine sans vault_path (pas d'I/O) pour les tests."""
    return BehavioralBiasEngine(vault_path=None, **kwargs)


def trending_prices(n: int = 50, drift: float = 0.002) -> pd.Series:
    """Série avec tendance haussière."""
    rng = np.random.default_rng(42)
    rets = rng.normal(drift, 0.005, n)
    p = 100.0 * np.cumprod(1 + rets)
    return pd.Series(p)


def mean_reverting_prices(n: int = 50) -> pd.Series:
    """Série mean-reverting (range-bound)."""
    rng = np.random.default_rng(99)
    p = [100.0]
    for _ in range(n - 1):
        noise = rng.normal(0, 0.8)
        p.append(p[-1] + noise)
    return pd.Series(p)


def volume_spike(n: int = 50, spike_at_end: bool = True) -> pd.Series:
    """Série de volume avec spike optionnel à la fin."""
    rng = np.random.default_rng(13)
    vol = rng.uniform(100, 200, n)
    if spike_at_end:
        vol[-1] = vol[-1] * 4  # 4x la normale
    return pd.Series(vol)


# ── _detect_anchoring ─────────────────────────────────────────────────────────

class TestDetectAnchoring:
    def test_price_at_round_number(self):
        """Prix exactement sur un nombre rond → anchoring détecté."""
        engine = make_engine()
        prices = np.array([98.0, 99.0, 99.5, 100.0, 100.0, 100.0, 100.0])
        result = engine._detect_anchoring(prices)
        assert result is not None
        assert result.bias_type == BiasType.ANCHORING
        assert result.metadata["round_number"] == 100

    def test_price_near_round_number(self):
        """Prix à 0.1% d'un nombre rond → anchoring détecté."""
        engine = make_engine()
        prices = np.array([98.0, 99.0, 99.5, 99.9, 99.95, 99.98, 99.99])
        result = engine._detect_anchoring(prices)
        assert result is not None
        assert result.bias_type == BiasType.ANCHORING

    def test_price_far_from_round_number(self):
        """Prix loin des nombres ronds → pas d'anchoring."""
        engine = make_engine()
        prices = np.array([93.17, 93.50, 94.23, 95.00, 94.50, 93.80, 94.10])
        result = engine._detect_anchoring(prices)
        assert result is None

    def test_anchoring_signal_direction(self):
        """Prix > round number → bearish; prix < round number → bullish."""
        engine = make_engine()

        # Prix au-dessus du nombre rond
        prices_above = np.array([100.0, 100.1, 100.05, 100.08, 100.1, 100.1, 100.1])
        result = engine._detect_anchoring(prices_above)
        assert result is not None
        assert result.signal == SignalDirection.BEARISH
        assert result.contrarian_action == ContrarianAction.SHORT

        # Prix en-dessous
        prices_below = np.array([100.0, 99.9, 99.95, 99.92, 99.9, 99.9, 99.9])
        result = engine._detect_anchoring(prices_below)
        assert result is not None
        assert result.signal == SignalDirection.BULLISH
        assert result.contrarian_action == ContrarianAction.LONG


# ── _detect_loss_aversion ─────────────────────────────────────────────────────

class TestDetectLossAversion:
    def test_support_tested_multiple_times(self):
        """Support testé 3+ fois → loss aversion détecté."""
        engine = make_engine()
        # Support à 100, testé 4 fois
        prices = np.array([105, 103, 101, 100.5, 102, 100.2, 103, 100.1, 100.3, 100.1])
        result = engine._detect_loss_aversion(prices)
        assert result is not None
        assert result.bias_type == BiasType.LOSS_AVERSION
        assert result.signal == SignalDirection.BEARISH  # cassure imminente

    def test_resistance_tested_multiple_times(self):
        """Résistance testée 3+ fois → breakout haussier."""
        engine = make_engine()
        # Résistance à 110, testée 4 fois
        prices = np.array([105, 108, 109.5, 110, 108, 109.8, 110, 109.5, 110, 109.9])
        result = engine._detect_loss_aversion(prices)
        assert result is not None
        assert result.bias_type == BiasType.LOSS_AVERSION
        assert result.signal == SignalDirection.BULLISH

    def test_no_clear_support_resistance(self):
        """Pas de niveau clair → pas de loss aversion."""
        engine = make_engine()
        prices = np.array([100, 102, 104, 106, 108, 110, 112, 114, 116, 118])
        result = engine._detect_loss_aversion(prices)
        assert result is None

    def test_short_series_returns_none(self):
        """Série trop courte → None."""
        engine = make_engine()
        prices = np.array([100, 101, 100.5, 101.5, 100.2])
        result = engine._detect_loss_aversion(prices)
        assert result is None


# ── _detect_recency_bias ──────────────────────────────────────────────────────

class TestDetectRecencyBias:
    def test_consecutive_up_candles(self):
        """5+ bougies haussières → signal bearish (mean reversion)."""
        engine = make_engine()
        # 6 bougies haussières consécutives
        prices = np.array([100, 101, 102, 103, 104, 105, 106, 107])
        result = engine._detect_recency_bias(prices)
        assert result is not None
        assert result.bias_type == BiasType.RECENCY
        assert result.signal == SignalDirection.BEARISH
        assert result.contrarian_action == ContrarianAction.SHORT

    def test_consecutive_down_candles(self):
        """5+ bougies baissières → signal bullish (rebond)."""
        engine = make_engine()
        # 6 bougies baissières consécutives
        prices = np.array([107, 106, 105, 104, 103, 102, 101, 100])
        result = engine._detect_recency_bias(prices)
        assert result is not None
        assert result.bias_type == BiasType.RECENCY
        assert result.signal == SignalDirection.BULLISH
        assert result.contrarian_action == ContrarianAction.LONG

    def test_mixed_candles_returns_none(self):
        """Bougies mélangées → pas de recency bias."""
        engine = make_engine()
        prices = np.array([100, 101, 100, 102, 101, 103, 102, 104])
        result = engine._detect_recency_bias(prices)
        assert result is None

    def test_only_4_consecutive_returns_none(self):
        """4 bougies consécutives → en-dessous du seuil."""
        engine = make_engine()
        prices = np.array([100, 101, 102, 103, 104, 103, 102, 101])
        result = engine._detect_recency_bias(prices)
        assert result is None


# ── _detect_herding ───────────────────────────────────────────────────────────

class TestDetectHerding:
    def test_extreme_long_ratio(self):
        """Long/short > 85% → signal bearish (tout le monde est long)."""
        engine = make_engine()
        result = engine._detect_herding(0.90)
        assert result is not None
        assert result.bias_type == BiasType.HERDING
        assert result.signal == SignalDirection.BEARISH
        assert result.contrarian_action == ContrarianAction.SHORT

    def test_extreme_short_ratio(self):
        """Long/short < 15% → signal bullish (tout le monde est short)."""
        engine = make_engine()
        result = engine._detect_herding(0.10)
        assert result is not None
        assert result.bias_type == BiasType.HERDING
        assert result.signal == SignalDirection.BULLISH
        assert result.contrarian_action == ContrarianAction.LONG

    def test_neutral_ratio_returns_none(self):
        """Ratio entre 20% et 80% → pas de herding."""
        engine = make_engine()
        assert engine._detect_herding(0.50) is None
        assert engine._detect_herding(0.30) is None
        assert engine._detect_herding(0.70) is None


# ── _detect_fomo ──────────────────────────────────────────────────────────────

class TestDetectFomo:
    def test_volume_spike_with_acceleration(self):
        """Volume 3x + accélération → FOMO détecté."""
        engine = make_engine()
        prices = trending_prices(30, drift=0.01)  # forte hausse
        volume = volume_spike(30, spike_at_end=True)
        result = engine._detect_fomo(prices.values, volume.values)
        assert result is not None
        assert result.bias_type == BiasType.FOMO
        assert result.signal == SignalDirection.BEARISH

    def test_no_volume_spike_returns_none(self):
        """Pas de volume spike → pas de FOMO."""
        engine = make_engine()
        prices = trending_prices(30, drift=0.01)
        volume = volume_spike(30, spike_at_end=False)
        result = engine._detect_fomo(prices.values, volume.values)
        assert result is None

    def test_no_acceleration_returns_none(self):
        """Volume spike sans accélération → pas de FOMO."""
        engine = make_engine()
        prices = mean_reverting_prices(30)  # pas de tendance
        volume = volume_spike(30, spike_at_end=True)
        result = engine._detect_fomo(prices.values, volume.values)
        assert result is None


# ── _detect_panic ─────────────────────────────────────────────────────────────

class TestDetectPanic:
    def test_3sigma_drop_with_volume(self):
        """Chute 3-sigma + volume spike → panique détectée."""
        engine = make_engine()
        rng = np.random.default_rng(42)
        # Crée une série avec un drop brutal
        prices = [100.0]
        for i in range(29):
            if i == 28:
                prices.append(prices[-1] * 0.90)  # -10% brutal
            else:
                prices.append(prices[-1] * (1 + rng.normal(0, 0.01)))
        volume = volume_spike(30, spike_at_end=True)
        result = engine._detect_panic(np.array(prices), volume.values)
        assert result is not None
        assert result.bias_type == BiasType.PANIC
        assert result.signal == SignalDirection.BULLISH  # rebond probable

    def test_no_volume_spike_returns_none(self):
        """3-sigma sans volume spike → pas de panique."""
        engine = make_engine()
        rng = np.random.default_rng(42)
        prices = [100.0]
        for i in range(29):
            if i == 28:
                prices.append(prices[-1] * 0.90)
            else:
                prices.append(prices[-1] * (1 + rng.normal(0, 0.01)))
        volume = pd.Series([100] * 30)  # volume constant
        result = engine._detect_panic(np.array(prices), volume.values)
        assert result is None


# ── _detect_disposition_effect ────────────────────────────────────────────────

class TestDetectDispositionEffect:
    def test_volume_spike_near_high(self):
        """Volume spike + prix près des plus-hauts → disposition effect."""
        engine = make_engine()
        # Prix près des plus-hauts
        prices = np.array([95, 96, 97, 98, 99, 98.5, 99.2, 99.5, 99.3, 99.8])
        volume = volume_spike(10, spike_at_end=True)
        result = engine._detect_disposition_effect(prices, volume.values)
        assert result is not None
        assert result.bias_type == BiasType.DISPOSITION
        assert result.signal == SignalDirection.BULLISH

    def test_no_volume_spike_returns_none(self):
        """Pas de volume spike → pas de disposition."""
        engine = make_engine()
        prices = np.array([95, 96, 97, 98, 99, 98.5, 99.2, 99.5, 99.3, 99.8])
        volume = volume_spike(10, spike_at_end=False)
        result = engine._detect_disposition_effect(prices, volume.values)
        assert result is None


# ── _aggregate_signal ─────────────────────────────────────────────────────────

class TestAggregateSignal:
    def test_all_bullish_biases(self):
        """Tous les biais bullish → aggregate bullish."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.RECENCY,
                confidence=0.8,
                intensity=0.7,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=6,
                metadata={},
            ),
            BiasSignal(
                bias_type=BiasType.PANIC,
                confidence=0.9,
                intensity=0.8,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=12,
                metadata={},
            ),
        ]
        result = engine._aggregate_signal(biases)
        assert result == SignalDirection.BULLISH

    def test_all_bearish_biases(self):
        """Tous les biais bearish → aggregate bearish."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.FOMO,
                confidence=0.8,
                intensity=0.7,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={},
            ),
        ]
        result = engine._aggregate_signal(biases)
        assert result == SignalDirection.BEARISH

    def test_mixed_biases_returns_neutral(self):
        """Biais mélangés → neutral."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.RECENCY,
                confidence=0.7,
                intensity=0.5,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=6,
                metadata={},
            ),
            BiasSignal(
                bias_type=BiasType.FOMO,
                confidence=0.7,
                intensity=0.5,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={},
            ),
        ]
        result = engine._aggregate_signal(biases)
        assert result == SignalDirection.NEUTRAL

    def test_empty_biases_returns_neutral(self):
        """Aucun biais → neutral."""
        engine = make_engine()
        result = engine._aggregate_signal([])
        assert result == SignalDirection.NEUTRAL


# ── _compute_contrarian_score ─────────────────────────────────────────────────

class TestContrarianScore:
    def test_no_biases_zero_score(self):
        """Aucun biais → score 0."""
        engine = make_engine()
        score = engine._compute_contrarian_score([])
        assert score == 0.0

    def test_single_high_confidence_bias(self):
        """Un biais haute confiance → score élevé."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.9,
                intensity=0.8,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=72,
                metadata={},
            ),
        ]
        score = engine._compute_contrarian_score(biases)
        assert score > 10  # 0.9 * 0.8 * 20 = 14.4

    def test_multiple_biases_higher_score(self):
        """Plusieurs biais → score plus élevé."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.8,
                intensity=0.7,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=72,
                metadata={},
            ),
            BiasSignal(
                bias_type=BiasType.FOMO,
                confidence=0.8,
                intensity=0.6,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={},
            ),
        ]
        score = engine._compute_contrarian_score(biases)
        # 0.8*0.7*20 + 0.8*0.6*20 = 11.2 + 9.6 = 20.8
        assert score > 15


# ── _compute_sizing_modifier ──────────────────────────────────────────────────

class TestSizingModifier:
    def test_no_biases_returns_1(self):
        """Aucun biais → sizing 1.0."""
        engine = make_engine()
        modifier = engine._compute_sizing_modifier([])
        assert modifier == 1.0

    def test_high_confidence_biases_boosts_sizing(self):
        """Biais haute confiance → sizing augmenté."""
        engine = make_engine()
        biases = [
            BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.8,
                intensity=0.7,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=72,
                metadata={},
            ),
            BiasSignal(
                bias_type=BiasType.FOMO,
                confidence=0.7,
                intensity=0.6,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={},
            ),
        ]
        modifier = engine._compute_sizing_modifier(biases)
        assert modifier > 1.0
        assert modifier <= 1.2  # cap

    def test_modifier_clipped_to_range(self):
        """Sizing clippé entre 0.8 et 1.2."""
        engine = make_engine()
        # Beaucoup de biais haute confiance
        biases = [
            BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.9,
                intensity=0.9,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=72,
                metadata={},
            )
            for _ in range(10)
        ]
        modifier = engine._compute_sizing_modifier(biases)
        assert 0.8 <= modifier <= 1.2


# ── analyze ───────────────────────────────────────────────────────────────────

class TestAnalyze:
    def test_analyze_returns_dict(self):
        engine = make_engine()
        prices = trending_prices(50)
        result = engine.analyze(prices)
        assert isinstance(result, dict)

    def test_analyze_has_required_keys(self):
        engine = make_engine()
        prices = trending_prices(50)
        result = engine.analyze(prices)
        for key in ["biases_detected", "aggregate_signal", "contrarian_score",
                    "sizing_modifier", "positioning_bias", "signals", "timestamp"]:
            assert key in result, f"Clé manquante : {key}"

    def test_analyze_short_series_returns_neutral(self):
        engine = make_engine()
        prices = pd.Series([100, 101, 102])
        result = engine.analyze(prices)
        assert result["aggregate_signal"] == "neutral"
        assert result["contrarian_score"] == 0.0

    def test_analyze_with_herding_signal(self):
        """Avec long/short ratio extrême → herding détecté."""
        engine = make_engine()
        prices = trending_prices(50)
        result = engine.analyze(prices, long_short_ratio=0.90)
        biases = result["biases_detected"]
        herding_found = any(b["bias_type"] == "herding" for b in biases)
        assert herding_found

    def test_analyze_stores_last_result(self):
        engine = make_engine()
        prices = trending_prices(50)
        engine.analyze(prices)
        assert engine.last_result is not None


# ── backtest ──────────────────────────────────────────────────────────────────

class TestBacktest:
    def test_no_close_column(self):
        engine = make_engine()
        df = pd.DataFrame({"volume": [100, 200, 300]})
        result = engine.backtest(df)
        assert result.results == []

    def test_returns_correct_count(self):
        engine = make_engine()
        prices = trending_prices(60)
        df = pd.DataFrame({"close": prices.values})
        result = engine.backtest(df)
        expected = len(df) - 20  # fenêtre de 20
        assert len(result.results) == expected

    def test_results_have_required_keys(self):
        engine = make_engine()
        prices = trending_prices(40)
        df = pd.DataFrame({"close": prices.values})
        result = engine.backtest(df)
        for row in result.results:
            for key in ["idx", "biases", "contrarian_score", "sizing_modifier"]:
                assert key in row, f"Clé manquante : {key}"

    def test_backtest_with_pnl(self):
        engine = make_engine()
        n = 50
        prices = trending_prices(n)
        pnl = np.random.default_rng(0).normal(0.1, 1.0, n)
        df = pd.DataFrame({"close": prices.values, "pnl_pct": pnl})
        result = engine.backtest(df)
        for row in result.results:
            assert "pnl_pct" in row


# ── BacktestResult.summary ────────────────────────────────────────────────────

class TestBacktestSummary:
    def test_empty_summary(self):
        bt = BacktestResult(results=[])
        assert "Aucun" in bt.summary()

    def test_summary_contains_strate_header(self):
        results = [
            {
                "biases": [{"bias_type": "herding", "confidence": 0.8}],
                "contrarian_score": 50,
            },
            {
                "biases": [{"bias_type": "fomo", "confidence": 0.7}],
                "contrarian_score": 30,
            },
        ]
        summary = BacktestResult(results=results).summary()
        assert "STRATE 5" in summary
        assert "BEHAVIORAL" in summary.upper()


# ── Cohérence des constantes ──────────────────────────────────────────────────

class TestConstants:
    def test_round_number_tolerance_positive(self):
        assert ROUND_NUMBER_TOLERANCE_PCT > 0

    def test_support_test_threshold_minimum(self):
        assert SUPPORT_TEST_THRESHOLD >= 3

    def test_consecutive_candles_threshold_minimum(self):
        assert CONSECUTIVE_CANDLES_THRESHOLD >= 5

    def test_herding_ratio_threshold_valid(self):
        assert 0.5 < HERDING_RATIO_THRESHOLD < 1.0

    def test_bias_type_values(self):
        """Tous les biais sont définis."""
        expected = ["anchoring", "loss_aversion", "recency",
                    "disposition", "herding", "fomo", "panic"]
        actual = [b.value for b in BiasType]
        assert sorted(actual) == sorted(expected)

    def test_signal_direction_values(self):
        expected = ["bullish", "bearish", "neutral"]
        actual = [s.value for s in SignalDirection]
        assert sorted(actual) == sorted(expected)

    def test_contrarian_action_values(self):
        expected = ["long", "short", "wait"]
        actual = [a.value for a in ContrarianAction]
        assert sorted(actual) == sorted(expected)
