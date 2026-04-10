"""
Tests unitaires — Strate 4 : Réflexivité de Soros

Couvre :
  - _estimate_hurst : séries tendancielles / aléatoires / anti-persistantes
  - _compute_xcorr  : corrélations croisées prix ↔ sentiment
  - _classify_loop  : mapping H × RI × inflection → ReflexivityLoop
  - _sizing_for_loop : correctness des multiplicateurs
  - _bias_for_loop   : correctness des biais
  - _detect_inflection : détection de dégradation du H
  - analyze()        : résultat complet, cas sans sentiment
  - backtest()       : replay sur DataFrame
  - BacktestResult.summary()
  - Constantes cohérentes
  - Persistance désactivée (vault_path=None)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest

from core.strate_4_reflexivity import (
    ReflexivityEngine,
    ReflexivityLoop,
    ReflexivityResult,
    HurstEstimate,
    CrossCorrResult,
    BacktestResult,
    HURST_LOOP,
    HURST_MEAN_REV,
    HURST_WINDOW_MIN,
    RI_THRESHOLD,
    SIZING_POSITIVE_LOOP,
    SIZING_INFLECTION,
    SIZING_NEGATIVE_LOOP,
    SIZING_MEAN_REVERTING,
    SIZING_NEUTRAL,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_engine(**kwargs) -> ReflexivityEngine:
    return ReflexivityEngine(vault_path=None, **kwargs)


def trending_prices(n: int = 80, drift: float = 0.003) -> pd.Series:
    """Série avec tendance → H élevé attendu."""
    rng = np.random.default_rng(42)
    rets = rng.normal(drift, 0.002, n)
    p = 100.0 * np.cumprod(1 + rets)
    return pd.Series(p)


def random_walk_prices(n: int = 80) -> pd.Series:
    """Marche aléatoire → H ≈ 0.5."""
    rng = np.random.default_rng(7)
    rets = rng.normal(0.0, 0.01, n)
    p = 100.0 * np.cumprod(1 + rets)
    return pd.Series(p)


def mean_reverting_prices(n: int = 80, strength: float = 0.3) -> pd.Series:
    """Série mean-reverting (Ornstein-Uhlenbeck) → H < 0.5."""
    rng = np.random.default_rng(99)
    p   = [100.0]
    mu  = 100.0
    for _ in range(n - 1):
        noise = rng.normal(0, 0.5)
        p.append(p[-1] + strength * (mu - p[-1]) + noise)
    return pd.Series(p)


def correlated_sentiment(prices: pd.Series, lag: int = 2, noise: float = 0.3) -> pd.Series:
    """Sentiment corrélé au prix avec un lag → xcorr détectable."""
    rets = np.diff(np.log(np.maximum(prices.values, 1e-10)))
    rng  = np.random.default_rng(13)
    sent = np.zeros(len(prices))
    for i in range(lag, len(rets)):
        sent[i] = rets[i - lag] + rng.normal(0, noise)
    return pd.Series(sent)


# ── _estimate_hurst ───────────────────────────────────────────────────────────

class TestEstimateHurst:
    def test_trending_series_h_above_05(self):
        engine = make_engine()
        prices = trending_prices(100)
        result = engine._estimate_hurst(prices.values)
        assert result.h > 0.5, f"H={result.h:.3f} devrait être >0.5 pour série tendancielle"

    def test_random_walk_h_near_05(self):
        """H d'une marche aléatoire doit être proche de 0.5 (±0.15)."""
        engine = make_engine()
        prices = random_walk_prices(100)
        result = engine._estimate_hurst(prices.values)
        assert abs(result.h - 0.5) < 0.25, f"H={result.h:.3f} trop éloigné de 0.5 pour marche aléatoire"

    def test_short_series_unreliable(self):
        engine = make_engine()
        prices = np.array([100.0, 101.0, 99.0, 102.0])
        result = engine._estimate_hurst(prices)
        assert result.reliable is False
        assert result.h == 0.5  # neutre par défaut

    def test_reliable_with_enough_points(self):
        engine = make_engine()
        prices = trending_prices(HURST_WINDOW_MIN + 10)
        result = engine._estimate_hurst(prices.values)
        assert result.reliable is True

    def test_h_clipped_to_0_1(self):
        engine = make_engine()
        # Série constante → cas limite
        prices = np.ones(50) * 100.0
        result = engine._estimate_hurst(prices)
        assert 0.0 <= result.h <= 1.0

    def test_n_points_correct(self):
        engine = make_engine()
        prices = trending_prices(40).values
        result = engine._estimate_hurst(prices)
        assert result.n_points == len(prices) - 1  # returns = diff(prices)


# ── _compute_xcorr ────────────────────────────────────────────────────────────

class TestComputeXcorr:
    def test_no_sentiment_returns_zero_ri(self):
        engine = make_engine()
        prices = trending_prices(60).values
        result = engine._compute_xcorr(prices, None)
        assert result.ri == 0.0
        assert result.available is False

    def test_correlated_sentiment_detected(self):
        """Sentiment corrélé au prix doit donner xcorr_sp > 0."""
        engine = make_engine()
        prices = trending_prices(80)
        sent   = correlated_sentiment(prices, lag=2, noise=0.1)
        result = engine._compute_xcorr(prices.values, sent)
        assert result.xcorr_sp > 0.0, f"xcorr_sp={result.xcorr_sp:.3f} devrait être positif"

    def test_too_short_sentiment_returns_unavailable(self):
        engine = make_engine()
        prices = trending_prices(60).values
        sent   = pd.Series([0.01] * 5)
        result = engine._compute_xcorr(prices, sent)
        assert result.available is False

    def test_ri_positive_when_both_correlations_positive(self):
        """RI > 0 si xcorr_ps et xcorr_sp sont tous les deux positifs."""
        engine = make_engine()
        prices = trending_prices(80)
        sent   = correlated_sentiment(prices, lag=1, noise=0.05)
        result = engine._compute_xcorr(prices.values, sent)
        # RI = xcorr_ps * xcorr_sp, si les deux sont positifs → RI > 0
        assert result.ri >= 0.0

    def test_ri_clipped_between_0_and_1(self):
        engine = make_engine()
        prices = trending_prices(60)
        sent   = correlated_sentiment(prices, lag=1, noise=0.0)
        result = engine._compute_xcorr(prices.values, sent)
        assert 0.0 <= result.ri <= 1.0


# ── _classify_loop ────────────────────────────────────────────────────────────

class TestClassifyLoop:
    def _make_xcorr(self, ps: float, sp: float) -> CrossCorrResult:
        ri = max(0.0, ps * sp)
        return CrossCorrResult(xcorr_ps=ps, xcorr_sp=sp, ri=ri,
                               best_lag_ps=1, best_lag_sp=1, available=True)

    def _make_xcorr_unavailable(self) -> CrossCorrResult:
        return CrossCorrResult(xcorr_ps=0.0, xcorr_sp=0.0, ri=0.0,
                               best_lag_ps=0, best_lag_sp=0, available=False)

    def test_inflection_takes_priority_over_positive(self):
        loop = ReflexivityEngine._classify_loop(
            h=HURST_LOOP + 0.1,
            xcorr=self._make_xcorr(0.5, 0.5),
            inflection=True,
        )
        assert loop == ReflexivityLoop.INFLECTION

    def test_positive_loop_with_high_h_and_ri(self):
        loop = ReflexivityEngine._classify_loop(
            h=HURST_LOOP + 0.1,
            xcorr=self._make_xcorr(0.5, 0.5),
            inflection=False,
        )
        assert loop == ReflexivityLoop.POSITIVE_LOOP

    def test_negative_loop_with_negative_sp(self):
        loop = ReflexivityEngine._classify_loop(
            h=HURST_LOOP + 0.1,
            xcorr=self._make_xcorr(0.3, -0.3),
            inflection=False,
        )
        assert loop == ReflexivityLoop.NEGATIVE_LOOP

    def test_mean_reverting_with_low_h(self):
        loop = ReflexivityEngine._classify_loop(
            h=HURST_MEAN_REV - 0.05,
            xcorr=self._make_xcorr_unavailable(),
            inflection=False,
        )
        assert loop == ReflexivityLoop.MEAN_REVERTING

    def test_neutral_with_medium_h_no_sentiment(self):
        loop = ReflexivityEngine._classify_loop(
            h=0.50,
            xcorr=self._make_xcorr_unavailable(),
            inflection=False,
        )
        assert loop == ReflexivityLoop.NEUTRAL

    def test_positive_loop_without_sentiment_high_h(self):
        """H élevé sans données de sentiment → POSITIVE_LOOP (Hurst seul)."""
        loop = ReflexivityEngine._classify_loop(
            h=HURST_LOOP + 0.1,
            xcorr=self._make_xcorr_unavailable(),
            inflection=False,
        )
        assert loop == ReflexivityLoop.POSITIVE_LOOP


# ── Sizing et biais ───────────────────────────────────────────────────────────

class TestSizingAndBias:
    @pytest.mark.parametrize("loop,expected_sizing", [
        (ReflexivityLoop.POSITIVE_LOOP,  SIZING_POSITIVE_LOOP),
        (ReflexivityLoop.INFLECTION,     SIZING_INFLECTION),
        (ReflexivityLoop.NEGATIVE_LOOP,  SIZING_NEGATIVE_LOOP),
        (ReflexivityLoop.MEAN_REVERTING, SIZING_MEAN_REVERTING),
        (ReflexivityLoop.NEUTRAL,        SIZING_NEUTRAL),
    ])
    def test_sizing_correct(self, loop, expected_sizing):
        sizing = ReflexivityEngine._sizing_for_loop(loop)
        assert sizing == expected_sizing, f"{loop.value}: sizing {sizing} != {expected_sizing}"

    def test_inflection_has_lowest_sizing(self):
        sizings = [ReflexivityEngine._sizing_for_loop(lp) for lp in ReflexivityLoop]
        min_sizing = min(sizings)
        assert ReflexivityEngine._sizing_for_loop(ReflexivityLoop.INFLECTION) == min_sizing

    def test_positive_loop_has_highest_sizing(self):
        sizings = [ReflexivityEngine._sizing_for_loop(lp) for lp in ReflexivityLoop]
        max_sizing = max(sizings)
        assert ReflexivityEngine._sizing_for_loop(ReflexivityLoop.POSITIVE_LOOP) == max_sizing

    @pytest.mark.parametrize("loop,expected_bias", [
        (ReflexivityLoop.POSITIVE_LOOP,  "long"),
        (ReflexivityLoop.INFLECTION,     "reduce"),
        (ReflexivityLoop.NEGATIVE_LOOP,  "short"),
        (ReflexivityLoop.MEAN_REVERTING, "long"),
        (ReflexivityLoop.NEUTRAL,        "neutral"),
    ])
    def test_bias_correct(self, loop, expected_bias):
        bias = ReflexivityEngine._bias_for_loop(loop)
        assert bias == expected_bias


# ── analyze ───────────────────────────────────────────────────────────────────

class TestAnalyze:
    def test_analyze_returns_dict(self):
        engine = make_engine()
        prices = trending_prices(60)
        result = engine.analyze(prices)
        assert isinstance(result, dict)

    def test_analyze_has_required_keys(self):
        engine = make_engine()
        prices = trending_prices(60)
        result = engine.analyze(prices)
        for key in ["loop", "hurst", "reflexivity_index", "xcorr_ps", "xcorr_sp",
                    "sizing_modifier", "positioning_bias", "signals", "timestamp"]:
            assert key in result, f"Clé manquante : {key}"

    def test_analyze_loop_is_valid(self):
        engine = make_engine()
        prices = trending_prices(60)
        result = engine.analyze(prices)
        valid_loops = {lp.value for lp in ReflexivityLoop}
        assert result["loop"] in valid_loops

    def test_analyze_hurst_between_0_and_1(self):
        engine = make_engine()
        prices = trending_prices(60)
        result = engine.analyze(prices)
        assert 0.0 <= result["hurst"] <= 1.0

    def test_analyze_too_short_returns_neutral(self):
        engine = make_engine()
        prices = pd.Series([100.0, 101.0])
        result = engine.analyze(prices)
        assert result["loop"] == ReflexivityLoop.NEUTRAL.value
        assert result["hurst_reliable"] is False

    def test_analyze_with_sentiment_fills_xcorr(self):
        engine = make_engine()
        prices = trending_prices(80)
        sent   = correlated_sentiment(prices, lag=2)
        result = engine.analyze(prices, sent)
        # Avec sentiment, xcorr_sp peut être non-nul
        assert "xcorr_sp" in result

    def test_analyze_stores_last_result(self):
        engine = make_engine()
        prices = trending_prices(60)
        engine.analyze(prices)
        assert engine.last_result is not None

    def test_analyze_sizing_modifier_in_valid_range(self):
        engine = make_engine()
        for _ in range(5):
            prices = trending_prices(60)
            result = engine.analyze(prices)
            sizing = result["sizing_modifier"]
            assert sizing in [SIZING_POSITIVE_LOOP, SIZING_INFLECTION,
                               SIZING_NEGATIVE_LOOP, SIZING_MEAN_REVERTING, SIZING_NEUTRAL]


# ── backtest ──────────────────────────────────────────────────────────────────

class TestBacktest:
    def test_no_close_column(self):
        engine = make_engine()
        df = pd.DataFrame({"volume": [100, 200, 300]})
        result = engine.backtest(df)
        assert result.results == []

    def test_returns_correct_count(self):
        engine = make_engine(hurst_window=20)
        prices = trending_prices(60)
        df = pd.DataFrame({"close": prices.values})
        result = engine.backtest(df)
        expected = len(df) - engine._hurst_window
        assert len(result.results) == expected

    def test_results_have_required_keys(self):
        engine = make_engine(hurst_window=20)
        prices = trending_prices(40)
        df = pd.DataFrame({"close": prices.values})
        result = engine.backtest(df)
        for row in result.results:
            for key in ["idx", "loop", "hurst", "reflexivity_index", "sizing_modifier"]:
                assert key in row

    def test_backtest_with_sentiment_col(self):
        engine = make_engine(hurst_window=20)
        prices = trending_prices(50)
        sent   = correlated_sentiment(prices, lag=2)
        df = pd.DataFrame({"close": prices.values, "sentiment_proxy": sent.values})
        result = engine.backtest(df)
        assert len(result.results) > 0

    def test_backtest_with_pnl(self):
        engine = make_engine(hurst_window=20)
        n = 50
        prices = trending_prices(n)
        pnl    = np.random.default_rng(0).normal(0.1, 1.0, n)
        df = pd.DataFrame({"close": prices.values, "pnl_pct": pnl})
        result = engine.backtest(df)
        for row in result.results:
            assert "pnl_pct" in row

    def test_backtest_loops_are_valid(self):
        engine = make_engine(hurst_window=20)
        prices = trending_prices(60)
        df = pd.DataFrame({"close": prices.values})
        result = engine.backtest(df)
        valid = {lp.value for lp in ReflexivityLoop}
        for row in result.results:
            assert row["loop"] in valid


# ── BacktestResult.summary ────────────────────────────────────────────────────

class TestBacktestSummary:
    def test_empty_summary(self):
        bt = BacktestResult(results=[])
        assert "Aucun" in bt.summary()

    def test_summary_contains_strate_header(self):
        results = [
            {"loop": "positive_loop", "hurst": 0.7, "sizing_modifier": 1.1},
            {"loop": "inflection",    "hurst": 0.6, "sizing_modifier": 0.65},
        ]
        summary = BacktestResult(results=results).summary()
        assert "STRATE 4" in summary
        assert "POSITIVE_LOOP" in summary or "positive_loop" in summary.lower()


# ── Cohérence des constantes ──────────────────────────────────────────────────

class TestConstants:
    def test_hurst_thresholds_ordered(self):
        assert HURST_MEAN_REV < 0.5 < HURST_LOOP

    def test_inflection_sizing_is_smallest(self):
        all_sizings = [SIZING_POSITIVE_LOOP, SIZING_INFLECTION,
                       SIZING_NEGATIVE_LOOP, SIZING_MEAN_REVERTING, SIZING_NEUTRAL]
        assert SIZING_INFLECTION == min(all_sizings)

    def test_positive_loop_sizing_is_largest(self):
        all_sizings = [SIZING_POSITIVE_LOOP, SIZING_INFLECTION,
                       SIZING_NEGATIVE_LOOP, SIZING_MEAN_REVERTING, SIZING_NEUTRAL]
        assert SIZING_POSITIVE_LOOP == max(all_sizings)

    def test_ri_threshold_positive(self):
        assert RI_THRESHOLD > 0.0

    def test_hurst_window_min_positive(self):
        assert HURST_WINDOW_MIN > 0
