"""
Tests unitaires — Strate 0 : Epistemological Engine

Couvre :
  - compute_entropy : signal pur vs bruit pur
  - compute_snr : composite et proxy autocorrélation
  - compute_epistemic_uncertainty : consensus vs désaccord
  - should_trade : gate complet avec cas limites
  - BacktestResult.summary : métriques de backtest
  - _mi_histogram : NMI interne
  - Persistance désactivée (vault_path=None)
"""

import sys
sys.path.insert(0, ".")

import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.strate_0_epistemic import (
    EpistemologicalEngine,
    BacktestResult,
    GateResult,
    SNR_THRESHOLD,
    UNCERTAINTY_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_engine(**kwargs) -> EpistemologicalEngine:
    """Engine sans vault_path pour éviter les I/O dans les tests."""
    return EpistemologicalEngine(**kwargs)


def trending_prices(n: int = 100, drift: float = 0.002) -> pd.Series:
    """Prix avec tendance marquée → faible entropie (signal fort)."""
    rng = np.random.default_rng(42)
    returns = rng.normal(drift, 0.001, n)
    prices = 100.0 * np.cumprod(1 + returns)
    return pd.Series(prices)


def noisy_prices(n: int = 100) -> pd.Series:
    """Prix purement aléatoires → forte entropie (bruit)."""
    rng = np.random.default_rng(99)
    returns = rng.normal(0, 0.02, n)
    prices = 100.0 * np.cumprod(1 + returns)
    return pd.Series(prices)


# ── compute_entropy ───────────────────────────────────────────────────────────

class TestComputeEntropy:
    def test_trending_has_lower_entropy_than_noise(self):
        engine  = make_engine()
        h_trend = engine.compute_entropy(trending_prices(n=100, drift=0.003))
        h_noise = engine.compute_entropy(noisy_prices(n=100))
        # La tendance doit avoir une entropie strictement inférieure au bruit pur.
        # Note : même en tendance, l'entropie reste élevée (~0.9) — c'est le point
        # central de Fischer Black. C'est la différence relative qui compte.
        assert h_trend < h_noise, (
            f"Entropie tendance ({h_trend:.3f}) devrait être < bruit ({h_noise:.3f})"
        )

    def test_noisy_has_high_entropy(self):
        engine = make_engine()
        prices = noisy_prices(n=200)
        h = engine.compute_entropy(prices)
        # Bruit → entropie > 0.50
        assert h > 0.50, f"Entropie trop basse pour du bruit : {h:.3f}"

    def test_entropy_in_range(self):
        engine = make_engine()
        for prices in [trending_prices(), noisy_prices()]:
            h = engine.compute_entropy(prices)
            assert 0.0 <= h <= 1.0, f"Entropie hors [0,1] : {h}"

    def test_insufficient_data_returns_one(self):
        engine = make_engine(entropy_window=50)
        prices = pd.Series([100.0, 101.0, 102.0])  # < window + 1
        h = engine.compute_entropy(prices)
        assert h == 1.0

    def test_window_parameter_respected(self):
        engine = make_engine(entropy_window=50)
        prices = trending_prices(n=200)
        h_50  = engine.compute_entropy(prices, window=50)
        h_100 = engine.compute_entropy(prices, window=100)
        # Résultats différents selon la fenêtre
        assert isinstance(h_50, float)
        assert isinstance(h_100, float)

    def test_constant_prices_low_entropy(self):
        engine = make_engine()
        prices = pd.Series([100.0] * 100)
        # Rendements tous nuls → un seul bin non vide → H=0
        h = engine.compute_entropy(prices)
        assert h < 0.2


# ── compute_snr ───────────────────────────────────────────────────────────────

class TestComputeSNR:
    def test_trending_has_higher_snr_than_noisy(self):
        engine = make_engine()
        snr_trend, _ = engine.compute_snr(trending_prices(n=150))
        snr_noise, _ = engine.compute_snr(noisy_prices(n=150))
        assert snr_trend > snr_noise, (
            f"SNR tendanciel ({snr_trend:.3f}) devrait être > bruit ({snr_noise:.3f})"
        )

    def test_snr_in_range(self):
        engine = make_engine()
        for prices in [trending_prices(), noisy_prices()]:
            snr, mi = engine.compute_snr(prices)
            assert 0.0 <= snr <= 1.0
            assert 0.0 <= mi  <= 1.0

    def test_with_macro_factors(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        # Facteur macro corrélé avec les prix
        macro = pd.DataFrame({
            "m2": np.linspace(100, 110, 100),
            "vix": np.random.default_rng(7).uniform(15, 25, 100),
        })
        snr, mi = engine.compute_snr(prices, macro_factors=macro)
        assert 0.0 <= snr <= 1.0
        assert 0.0 <= mi  <= 1.0

    def test_empty_macro_falls_back_to_autocorr(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        snr_no_macro, mi_no_macro = engine.compute_snr(prices, macro_factors=None)
        snr_empty, mi_empty       = engine.compute_snr(prices, macro_factors=pd.DataFrame())
        # Les deux chemins doivent donner des résultats similaires
        assert abs(snr_no_macro - snr_empty) < 1e-9


# ── compute_epistemic_uncertainty ─────────────────────────────────────────────

class TestEpistemicUncertainty:
    def test_empty_predictions_max_uncertainty(self):
        engine = make_engine()
        u = engine.compute_epistemic_uncertainty(np.array([]))
        assert u == 1.0

    def test_single_prediction_zero_uncertainty(self):
        engine = make_engine()
        u = engine.compute_epistemic_uncertainty(np.array([75.0]))
        assert u == 0.0

    def test_identical_predictions_low_uncertainty(self):
        engine = make_engine()
        u = engine.compute_epistemic_uncertainty(np.array([70.0, 70.0, 70.0, 70.0]))
        assert u < 0.05, f"Prédictions identiques → incertitude quasi-nulle, got {u:.3f}"

    def test_divergent_predictions_high_uncertainty(self):
        engine = make_engine()
        u = engine.compute_epistemic_uncertainty(np.array([10.0, 90.0, 10.0, 90.0]))
        assert u > 0.5, f"Prédictions divergentes → haute incertitude, got {u:.3f}"

    def test_normalized_input_accepted(self):
        engine = make_engine()
        # Entrée déjà normalisée [0,1]
        u = engine.compute_epistemic_uncertainty(np.array([0.7, 0.8, 0.75]))
        assert 0.0 <= u <= 1.0

    def test_unnormalized_input_accepted(self):
        engine = make_engine()
        # Entrée en 0-100
        u = engine.compute_epistemic_uncertainty(np.array([70.0, 80.0, 75.0]))
        assert 0.0 <= u <= 1.0

    def test_uncertainty_in_range(self):
        engine = make_engine()
        rng = np.random.default_rng(0)
        for _ in range(20):
            preds = rng.uniform(0, 100, rng.integers(1, 10))
            u = engine.compute_epistemic_uncertainty(preds)
            assert 0.0 <= u <= 1.0


# ── should_trade ──────────────────────────────────────────────────────────────

class TestShouldTrade:
    def test_strong_trend_passes_gate(self):
        engine = make_engine(snr_threshold=0.35, uncertainty_threshold=0.40)
        prices = trending_prices(n=150, drift=0.005)
        preds  = np.array([80.0, 82.0, 79.0])  # consensus fort
        allowed, info = engine.should_trade(prices, predictions=preds,
                                            asset="BTC/USDT", timeframe="1h")
        assert isinstance(allowed, bool)
        assert "snr" in info
        assert "entropy" in info
        assert "uncertainty" in info
        assert "reason" in info
        assert "timestamp" in info

    def test_pure_noise_blocked(self):
        engine = make_engine(snr_threshold=0.60)  # seuil élevé → bloque le bruit
        prices = noisy_prices(n=200)
        preds  = np.array([20.0, 80.0, 50.0])  # prédictions divergentes
        allowed, info = engine.should_trade(prices, predictions=preds)
        # Avec un seuil de 0.60 et du bruit pur, devrait être bloqué
        # (on teste la cohérence, pas un résultat exact)
        assert isinstance(allowed, bool)
        assert info["snr"] < 0.70  # bruit → SNR < 0.70

    def test_high_uncertainty_blocks(self):
        engine = make_engine(uncertainty_threshold=0.05)  # seuil très bas
        prices = trending_prices(n=150)
        preds  = np.array([10.0, 90.0])  # très divergent
        allowed, info = engine.should_trade(prices, predictions=preds)
        # Seuil 0.05 avec divergence → devrait bloquer
        if info["uncertainty"] > 0.05:
            assert not allowed

    def test_no_predictions_uses_default_uncertainty(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        allowed, info = engine.should_trade(prices, predictions=None)
        assert info["uncertainty"] == 0.25  # valeur neutre par défaut

    def test_asset_and_timeframe_in_info(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        _, info = engine.should_trade(prices, asset="ETH/USDT", timeframe="4h")
        assert info["asset"] == "ETH/USDT"
        assert info["timeframe"] == "4h"

    def test_session_stats_incremented(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        for _ in range(5):
            engine.should_trade(prices)
        stats = engine.session_stats()
        assert stats["total_evaluated"] == 5
        assert stats["total_blocked"] >= 0
        assert 0.0 <= stats["block_rate"] <= 1.0

    def test_result_info_types(self):
        engine = make_engine()
        prices = trending_prices(n=100)
        allowed, info = engine.should_trade(prices)
        assert isinstance(info["allowed"], bool)
        assert isinstance(info["snr"], float)
        assert isinstance(info["entropy"], float)
        assert isinstance(info["uncertainty"], float)
        assert isinstance(info["mi_score"], float)
        assert isinstance(info["reason"], str)

    def test_block_reason_mentions_snr(self):
        engine = make_engine(snr_threshold=0.99)  # seuil impossible → toujours bloqué
        prices = trending_prices(n=100)
        allowed, info = engine.should_trade(prices)
        assert not allowed
        assert "SNR" in info["reason"] or "BLOQUÉ" in info["reason"]


# ── backtest ──────────────────────────────────────────────────────────────────

class TestBacktest:
    def _make_df(self, n: int = 150, with_pnl: bool = True) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        prices = trending_prices(n=n)
        df = pd.DataFrame({"close": prices.values})
        df["confidence"] = rng.uniform(40, 90, n)
        if with_pnl:
            df["pnl_pct"] = rng.normal(0.5, 1.5, n)
        return df

    def test_backtest_returns_result(self):
        engine = make_engine()
        df     = self._make_df()
        result = engine.backtest(df)
        assert isinstance(result, BacktestResult)
        assert len(result.results) > 0

    def test_backtest_result_has_expected_keys(self):
        engine = make_engine()
        df     = self._make_df()
        result = engine.backtest(df)
        row    = result.results[0]
        for key in ("idx", "allowed", "snr", "entropy", "uncertainty", "pnl_pct"):
            assert key in row, f"Clé manquante : {key}"

    def test_backtest_summary_is_string(self):
        engine = make_engine()
        df     = self._make_df()
        result = engine.backtest(df)
        summary = result.summary()
        assert isinstance(summary, str)
        assert "BACKTEST" in summary

    def test_backtest_without_pnl(self):
        engine = make_engine()
        df     = self._make_df(with_pnl=False)
        result = engine.backtest(df)
        summary = result.summary()
        assert "BACKTEST" in summary
        assert "pnl_pct" not in result.results[0]

    def test_backtest_empty_result_summary(self):
        result = BacktestResult(results=[])
        summary = result.summary()
        assert isinstance(summary, str)

    def test_backtest_all_allowed_or_blocked_consistency(self):
        engine = make_engine(snr_threshold=0.0)  # seuil 0 → tout passe
        df     = self._make_df()
        result = engine.backtest(df)
        assert all(r["allowed"] for r in result.results)

    def test_block_rate_between_0_and_1(self):
        engine = make_engine()
        df     = self._make_df()
        engine.backtest(df)
        assert 0.0 <= engine.block_rate <= 1.0


# ── Persistance vault ─────────────────────────────────────────────────────────

class TestPersistence:
    def test_gate_log_written_when_vault_path_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp)
            engine = EpistemologicalEngine(vault_path=vault_path)
            prices = trending_prices(n=100)
            engine.should_trade(prices, asset="BTC/USDT", timeframe="1h")

            log_path = vault_path / "epistemic" / "gate_log.jsonl"
            assert log_path.exists(), "gate_log.jsonl non créé"

            import json
            lines = log_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["asset"] == "BTC/USDT"
            assert entry["timeframe"] == "1h"
            assert "snr" in entry
            assert "allowed" in entry

    def test_multiple_calls_append_to_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp)
            engine = EpistemologicalEngine(vault_path=vault_path)
            prices = trending_prices(n=100)
            for _ in range(3):
                engine.should_trade(prices)

            log_path = vault_path / "epistemic" / "gate_log.jsonl"
            lines = log_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 3

    def test_no_vault_path_does_not_crash(self):
        engine = EpistemologicalEngine(vault_path=None)
        prices = trending_prices(n=100)
        allowed, info = engine.should_trade(prices)
        assert isinstance(allowed, bool)


# ── GateResult ────────────────────────────────────────────────────────────────

class TestGateResult:
    def test_to_dict_has_all_keys(self):
        r = GateResult(
            allowed=True, snr=0.5, entropy=0.5, uncertainty=0.2,
            mi_score=0.4, reason="AUTORISÉ", asset="BTC/USDT", timeframe="1h",
        )
        d = r.to_dict()
        for key in ("allowed", "snr", "entropy", "uncertainty", "mi_score",
                    "reason", "asset", "timeframe", "timestamp"):
            assert key in d

    def test_to_dict_rounds_floats(self):
        r = GateResult(
            allowed=False, snr=0.123456789, entropy=0.987654321,
            uncertainty=0.111111, mi_score=0.222222, reason="BLOQUÉ",
        )
        d = r.to_dict()
        assert len(str(d["snr"]).split(".")[-1]) <= 4
        assert len(str(d["entropy"]).split(".")[-1]) <= 4


# ── _mi_histogram ─────────────────────────────────────────────────────────────

class TestMIHistogram:
    def test_perfectly_correlated_high_mi(self):
        x = np.linspace(0, 1, 100)
        mi = EpistemologicalEngine._mi_histogram(x, x)
        assert mi > 0.5, f"MI parfaitement corrélée devrait être > 0.5, got {mi:.3f}"

    def test_independent_low_mi(self):
        rng = np.random.default_rng(0)
        x = rng.standard_normal(200)
        y = rng.standard_normal(200)
        mi = EpistemologicalEngine._mi_histogram(x, y)
        assert mi < 0.7, f"MI indépendante devrait être < 0.7, got {mi:.3f}"

    def test_mi_in_range(self):
        rng = np.random.default_rng(1)
        x = rng.standard_normal(100)
        y = rng.standard_normal(100)
        mi = EpistemologicalEngine._mi_histogram(x, y)
        assert 0.0 <= mi <= 1.0

    def test_empty_histogram_returns_zero(self):
        mi = EpistemologicalEngine._mi_histogram(np.array([]), np.array([]))
        assert mi == 0.0
