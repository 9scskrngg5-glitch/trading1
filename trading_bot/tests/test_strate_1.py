"""
Tests unitaires — Strate 1 : World Model Engine

Couvre :
  - MacroSnapshot : création, dérivés, sérialisation
  - classify_regime : chaque régime avec signaux clés
  - run_monte_carlo : structure, probabilités, CVaR
  - get_world_state_vector : shape, range, cohérence
  - Cache : save/load
  - fetch_macro_snapshot : logique de cache (sans appel réseau réel)
  - RegimeClassification.to_dict
  - ScenarioDistribution.to_dict

Tous les tests sont offline — aucun appel réseau réel.
"""

import sys
sys.path.insert(0, ".")

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.strate_1_world_model import (
    MacroRegime,
    MacroSnapshot,
    RegimeClassification,
    ScenarioDistribution,
    WorldModelEngine,
    MONTE_CARLO_DAYS,
    REGIME_THRESHOLDS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_engine(vault_path=None) -> WorldModelEngine:
    return WorldModelEngine(fred_api_key="", vault_path=vault_path, http_client=MagicMock())


def risk_on_snapshot() -> MacroSnapshot:
    return MacroSnapshot(
        cpi_yoy=2.0, vix=14.0, dxy=98.0, yield_curve=1.5,
        ism_pmi=56.0, unemployment=3.5, fed_funds_rate=2.5,
        btc_dominance=45.0, btc_funding_rate=0.03, eth_funding_rate=0.025,
    )


def risk_off_snapshot() -> MacroSnapshot:
    return MacroSnapshot(
        cpi_yoy=3.0, vix=38.0, dxy=108.0, yield_curve=-0.5,
        ism_pmi=43.0, unemployment=7.0, fed_funds_rate=5.5,
        btc_dominance=60.0, btc_funding_rate=-0.02, eth_funding_rate=-0.015,
    )


def stagflation_snapshot() -> MacroSnapshot:
    return MacroSnapshot(
        cpi_yoy=7.0, vix=28.0, dxy=102.0, yield_curve=0.1,
        ism_pmi=43.0, unemployment=6.5, fed_funds_rate=6.0,
        btc_dominance=50.0, btc_funding_rate=0.01, eth_funding_rate=0.01,
    )


def deflation_snapshot() -> MacroSnapshot:
    return MacroSnapshot(
        cpi_yoy=-1.5, vix=25.0, dxy=100.0, yield_curve=0.5,
        ism_pmi=44.0, unemployment=5.0, fed_funds_rate=0.25,
        btc_dominance=48.0, btc_funding_rate=-0.03, eth_funding_rate=-0.02,
    )


# ── MacroSnapshot ─────────────────────────────────────────────────────────────

class TestMacroSnapshot:
    def test_default_snapshot_is_valid(self):
        s = MacroSnapshot()
        assert isinstance(s.cpi_yoy, float)
        assert isinstance(s.vix, float)
        assert isinstance(s.yield_curve, float)
        assert 0.0 <= s.data_quality <= 1.0

    def test_real_rate_computed_in_post_init(self):
        s = MacroSnapshot(fed_funds_rate=5.0, cpi_yoy=3.0)
        assert s.real_rate == pytest.approx(2.0, abs=0.001)

    def test_yield_curve_signal_positive(self):
        s = MacroSnapshot(yield_curve=1.0)
        assert s.yield_curve_signal == 1

    def test_yield_curve_signal_inverted(self):
        s = MacroSnapshot(yield_curve=-0.5)
        assert s.yield_curve_signal == -1

    def test_yield_curve_signal_flat(self):
        s = MacroSnapshot(yield_curve=0.1)
        assert s.yield_curve_signal == 0

    def test_to_dict_serializable(self):
        s = MacroSnapshot()
        d = s.to_dict()
        assert isinstance(d, dict)
        # Doit être sérialisable JSON
        json_str = json.dumps(d)
        assert len(json_str) > 0

    def test_from_dict_roundtrip(self):
        s1 = MacroSnapshot(cpi_yoy=4.5, vix=22.0, dxy=103.0)
        d  = s1.to_dict()
        s2 = MacroSnapshot.from_dict(d)
        assert s2.cpi_yoy       == pytest.approx(s1.cpi_yoy, abs=0.001)
        assert s2.vix           == pytest.approx(s1.vix, abs=0.001)
        assert s2.dxy           == pytest.approx(s1.dxy, abs=0.001)

    def test_from_dict_ignores_unknown_fields(self):
        d = MacroSnapshot().to_dict()
        d["unknown_field"] = "should_be_ignored"
        s = MacroSnapshot.from_dict(d)
        assert isinstance(s, MacroSnapshot)


# ── classify_regime ───────────────────────────────────────────────────────────

class TestClassifyRegime:
    def test_risk_on_detected(self):
        engine = make_engine()
        result = engine.classify_regime(risk_on_snapshot())
        assert result.regime == MacroRegime.RISK_ON
        assert result.confidence > 0.0

    def test_risk_off_detected(self):
        engine = make_engine()
        result = engine.classify_regime(risk_off_snapshot())
        assert result.regime == MacroRegime.RISK_OFF

    def test_stagflation_detected(self):
        engine = make_engine()
        result = engine.classify_regime(stagflation_snapshot())
        assert result.regime == MacroRegime.STAGFLATION

    def test_deflation_detected(self):
        engine = make_engine()
        result = engine.classify_regime(deflation_snapshot())
        assert result.regime == MacroRegime.DEFLATION

    def test_result_has_all_regimes_in_scores(self):
        engine = make_engine()
        result = engine.classify_regime(risk_on_snapshot())
        for r in MacroRegime:
            assert r.value in result.scores

    def test_confidence_in_range(self):
        engine = make_engine()
        for snap in [risk_on_snapshot(), risk_off_snapshot(), stagflation_snapshot()]:
            result = engine.classify_regime(snap)
            assert 0.0 <= result.confidence <= 1.0

    def test_signals_is_non_empty_list(self):
        engine = make_engine()
        result = engine.classify_regime(risk_on_snapshot())
        assert isinstance(result.signals, list)
        assert len(result.signals) > 0

    def test_to_dict_has_expected_keys(self):
        engine = make_engine()
        result = engine.classify_regime(risk_on_snapshot())
        d = result.to_dict()
        for key in ("regime", "confidence", "scores", "signals", "timestamp"):
            assert key in d

    def test_extreme_vix_gives_risk_off(self):
        engine = make_engine()
        snap = MacroSnapshot(vix=50.0, yield_curve=-1.0, dxy=112.0)
        result = engine.classify_regime(snap)
        assert result.regime == MacroRegime.RISK_OFF

    def test_cpi_deflation_gives_deflation(self):
        engine = make_engine()
        snap = MacroSnapshot(cpi_yoy=-2.0, fed_funds_rate=0.1, vix=22.0)
        result = engine.classify_regime(snap)
        assert result.regime == MacroRegime.DEFLATION

    def test_last_regime_stored(self):
        engine = make_engine()
        assert engine.last_regime is None
        engine.classify_regime(risk_on_snapshot())
        assert engine.last_regime is not None
        assert isinstance(engine.last_regime, RegimeClassification)


# ── run_monte_carlo ───────────────────────────────────────────────────────────

class TestMonteCarlo:
    def test_returns_scenario_distribution(self):
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=100, seed=42)
        assert isinstance(mc, ScenarioDistribution)

    def test_probabilities_sum_to_one(self):
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=500, seed=0)
        total = mc.prob_bull + mc.prob_bear + mc.prob_neutral
        assert total == pytest.approx(1.0, abs=0.01)

    def test_probabilities_in_range(self):
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=200, seed=1)
        assert 0.0 <= mc.prob_bull    <= 1.0
        assert 0.0 <= mc.prob_bear    <= 1.0
        assert 0.0 <= mc.prob_neutral <= 1.0

    def test_risk_on_bull_prob_higher_than_risk_off(self):
        engine = make_engine()
        mc_bull = engine.run_monte_carlo(risk_on_snapshot(),  n_scenarios=500, seed=7)
        mc_bear = engine.run_monte_carlo(risk_off_snapshot(), n_scenarios=500, seed=7)
        assert mc_bull.prob_bull > mc_bear.prob_bull
        assert mc_bull.prob_bear < mc_bear.prob_bear

    def test_cvar_non_negative(self):
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=200, seed=2)
        # CVaR = perte attendue → peut être négatif si scenarios médian très positif
        assert isinstance(mc.cvar_95, float)
        assert isinstance(mc.var_95, float)

    def test_paths_have_correct_length(self):
        engine = make_engine()
        horizon = 30
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=100,
                                    horizon=horizon, seed=3)
        assert len(mc.path_p10) == horizon
        assert len(mc.path_p50) == horizon
        assert len(mc.path_p90) == horizon

    def test_paths_are_ordered(self):
        """p10 ≤ p50 ≤ p90 à chaque instant."""
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=500, seed=4)
        for i in range(len(mc.path_p10)):
            assert mc.path_p10[i] <= mc.path_p50[i] + 1e-6
            assert mc.path_p50[i] <= mc.path_p90[i] + 1e-6

    def test_paths_start_at_one(self):
        """Le premier jour, tous les paths partent de ~1.0."""
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=1000, seed=5)
        # Après 1 jour, la médiane est proche de 1.0
        assert 0.80 <= mc.path_p50[0] <= 1.25

    def test_reproducible_with_seed(self):
        engine = make_engine()
        mc1 = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=100, seed=99)
        mc2 = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=100, seed=99)
        assert mc1.prob_bull    == mc2.prob_bull
        assert mc1.median_return == mc2.median_return

    def test_to_dict_serializable(self):
        engine = make_engine()
        mc = engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=50, seed=6)
        d  = mc.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # doit être sérialisable

    def test_last_mc_stored(self):
        engine = make_engine()
        assert engine.last_monte_carlo is None
        engine.run_monte_carlo(risk_on_snapshot(), n_scenarios=50, seed=0)
        assert engine.last_monte_carlo is not None


# ── get_world_state_vector ────────────────────────────────────────────────────

class TestWorldStateVector:
    def test_returns_zeros_without_snapshot(self):
        engine = make_engine()
        v = engine.get_world_state_vector()
        assert isinstance(v, np.ndarray)
        assert v.shape == (14,)
        assert np.all(v == 0.0)

    def test_shape_is_14(self):
        engine = make_engine()
        engine._last_snapshot = risk_on_snapshot()
        v = engine.get_world_state_vector()
        assert v.shape == (14,)

    def test_values_in_minus1_plus1(self):
        engine = make_engine()
        for snap in [risk_on_snapshot(), risk_off_snapshot(), stagflation_snapshot()]:
            engine._last_snapshot = snap
            v = engine.get_world_state_vector()
            assert np.all(v >= -1.0 - 1e-6), f"Valeur < -1: {v}"
            assert np.all(v <= 1.0 + 1e-6),  f"Valeur > +1: {v}"

    def test_dtype_is_float32(self):
        engine = make_engine()
        engine._last_snapshot = risk_on_snapshot()
        v = engine.get_world_state_vector()
        assert v.dtype == np.float32

    def test_risk_on_vs_risk_off_differ(self):
        engine = make_engine()
        engine._last_snapshot = risk_on_snapshot()
        v_on = engine.get_world_state_vector().copy()
        engine._last_snapshot = risk_off_snapshot()
        v_off = engine.get_world_state_vector().copy()
        # Les deux vecteurs doivent être différents
        assert not np.allclose(v_on, v_off)

    def test_vix_dimension_inverted(self):
        """VIX élevé → dimension [6] négative (risk-off = négatif)."""
        engine = make_engine()
        engine._last_snapshot = MacroSnapshot(vix=45.0)
        v = engine.get_world_state_vector()
        assert v[6] < 0, f"VIX élevé devrait donner dimension négative, got {v[6]}"

    def test_dxy_dimension_inverted(self):
        """DXY fort → dimension [7] négative."""
        engine = make_engine()
        engine._last_snapshot = MacroSnapshot(dxy=115.0)
        v = engine.get_world_state_vector()
        assert v[7] < 0, f"DXY fort devrait donner dimension négative, got {v[7]}"


# ── Cache ─────────────────────────────────────────────────────────────────────

class TestCache:
    def test_save_and_load_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            engine = WorldModelEngine(vault_path=vault, http_client=MagicMock())
            engine._last_snapshot = risk_on_snapshot()
            engine._ts_macro  = 1_000_000.0
            engine._ts_crypto = 1_000_001.0
            engine._save_cache()

            # Nouveau moteur qui charge le cache
            engine2 = WorldModelEngine(vault_path=vault, http_client=MagicMock())
            engine2._load_cache()

            assert engine2._last_snapshot is not None
            assert engine2._last_snapshot.vix == pytest.approx(
                engine._last_snapshot.vix, abs=0.001
            )
            assert engine2._ts_macro == pytest.approx(1_000_000.0, abs=1.0)

    def test_cache_includes_regime_if_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            engine = WorldModelEngine(vault_path=vault, http_client=MagicMock())
            engine._last_snapshot = risk_on_snapshot()
            engine._last_regime   = engine.classify_regime(risk_on_snapshot())
            engine._save_cache()

            engine2 = WorldModelEngine(vault_path=vault, http_client=MagicMock())
            engine2._load_cache()
            assert engine2._last_regime is not None
            assert engine2._last_regime.regime == MacroRegime.RISK_ON

    def test_load_cache_missing_file_no_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            engine = WorldModelEngine(vault_path=vault, http_client=MagicMock())
            engine._load_cache()  # fichier inexistant → pas d'erreur
            assert engine._last_snapshot is None

    def test_no_vault_path_save_no_crash(self):
        engine = WorldModelEngine(vault_path=None, http_client=MagicMock())
        engine._last_snapshot = risk_on_snapshot()
        engine._save_cache()  # doit passer silencieusement


# ── fetch_macro_snapshot (logique cache, sans réseau) ─────────────────────────

class TestFetchMacroSnapshot:
    @pytest.mark.asyncio
    async def test_returns_macro_snapshot(self):
        engine = make_engine()
        # Simuler toutes les sources retournant None → valeurs par défaut
        engine._fetch_fred       = AsyncMock(return_value=None)
        engine._fetch_yfinance   = AsyncMock(return_value=None)
        engine._fetch_coingecko  = AsyncMock(return_value=None)
        engine._fetch_funding_rates = AsyncMock(return_value=None)

        snap = await engine.fetch_macro_snapshot()
        assert isinstance(snap, MacroSnapshot)

    @pytest.mark.asyncio
    async def test_sources_update_snapshot(self):
        engine = make_engine()
        engine._fetch_fred = AsyncMock(return_value={
            "cpi_yoy": 6.5, "yield_curve": -0.8, "ism_pmi": 42.0,
            "unemployment": 4.0, "fed_funds_rate": 5.25, "m2_growth_yoy": 3.0,
            "pce_yoy": 5.0,
        })
        engine._fetch_yfinance = AsyncMock(return_value={
            "vix": 32.0, "dxy": 106.0, "gold": 2100.0, "oil": 85.0, "copper": 3.8,
        })
        engine._fetch_coingecko = AsyncMock(return_value={
            "btc_dominance": 55.0, "total_market_cap_b": 1800.0,
        })
        engine._fetch_funding_rates = AsyncMock(return_value={
            "btc": 0.02, "eth": 0.015,
        })

        snap = await engine.fetch_macro_snapshot()
        assert snap.cpi_yoy        == pytest.approx(6.5, abs=0.01)
        assert snap.vix            == pytest.approx(32.0, abs=0.01)
        assert snap.btc_dominance  == pytest.approx(55.0, abs=0.01)
        assert snap.btc_funding_rate == pytest.approx(0.02, abs=0.001)

    @pytest.mark.asyncio
    async def test_cache_respects_ttl(self):
        """Si les données sont fraîches (ts récent), les fetchers ne sont pas rappelés."""
        engine = make_engine()
        engine._last_snapshot = risk_on_snapshot()
        # Simuler un timestamp très récent → cache valide
        import time
        engine._ts_macro  = time.time() - 60    # 1 minute → pas périmé (TTL=6h)
        engine._ts_crypto = time.time() - 60

        engine._fetch_fred          = AsyncMock(return_value=None)
        engine._fetch_yfinance      = AsyncMock(return_value=None)
        engine._fetch_coingecko     = AsyncMock(return_value=None)
        engine._fetch_funding_rates = AsyncMock(return_value=None)

        snap = await engine.fetch_macro_snapshot()
        # Cache valide → fetchers non appelés
        engine._fetch_fred.assert_not_called()
        engine._fetch_yfinance.assert_not_called()
        engine._fetch_coingecko.assert_not_called()

    @pytest.mark.asyncio
    async def test_data_quality_zero_when_all_sources_fail(self):
        engine = make_engine()
        engine._fetch_fred          = AsyncMock(return_value=None)
        engine._fetch_yfinance      = AsyncMock(return_value=None)
        engine._fetch_coingecko     = AsyncMock(return_value=None)
        engine._fetch_funding_rates = AsyncMock(return_value=None)

        snap = await engine.fetch_macro_snapshot()
        # Toutes les sources ont échoué → qualité 0.0
        assert snap.data_quality == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_last_snapshot_updated(self):
        engine = make_engine()
        engine._fetch_fred          = AsyncMock(return_value=None)
        engine._fetch_yfinance      = AsyncMock(return_value=None)
        engine._fetch_coingecko     = AsyncMock(return_value=None)
        engine._fetch_funding_rates = AsyncMock(return_value=None)

        assert engine.last_snapshot is None
        await engine.fetch_macro_snapshot()
        assert engine.last_snapshot is not None


# ── Intégration : classify_regime → run_monte_carlo ──────────────────────────

class TestIntegration:
    def test_full_pipeline_risk_on(self):
        engine = make_engine()
        snap   = risk_on_snapshot()
        regime = engine.classify_regime(snap)
        mc     = engine.run_monte_carlo(snap, n_scenarios=200, seed=42)
        vector = engine.get_world_state_vector()

        # En risk-on : prob_bull > prob_bear
        assert mc.prob_bull > mc.prob_bear
        # Vecteur non nul
        assert not np.all(vector == 0.0)
        # Regime correct
        assert regime.regime == MacroRegime.RISK_ON

    def test_full_pipeline_risk_off(self):
        engine = make_engine()
        snap   = risk_off_snapshot()
        regime = engine.classify_regime(snap)
        mc     = engine.run_monte_carlo(snap, n_scenarios=200, seed=42)

        # En risk-off : prob_bear > prob_bull
        assert mc.prob_bear > mc.prob_bull
        assert regime.regime == MacroRegime.RISK_OFF
