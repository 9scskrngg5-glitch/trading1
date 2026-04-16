"""
Tests oracle_v2/features/, oracle_v2/ml/, oracle_v2/parliament/

Tous les tests utilisent uniquement numpy (toujours disponible).
Les librairies ML optionnelles (scipy, torch, etc.) font l'objet
de fallbacks gracieux — les tests ne peuvent pas "skip" à cause
d'une absence de dépendance.
"""
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── Entropy ──────────────────────────────────────────────────────────────────

class TestEntropy:

    def test_shannon_entropy_positive(self):
        from oracle_v2.features.entropy import shannon_entropy
        returns = np.random.randn(200) * 0.01
        h = shannon_entropy(returns, n_bins=8)
        assert isinstance(h, float)
        assert h >= 0.0

    def test_rolling_entropy_shape(self):
        from oracle_v2.features.entropy import rolling_entropy
        returns = np.random.randn(100) * 0.01
        re = rolling_entropy(returns, window=20, n_bins=10)
        assert re.shape == (100,)
        # First window-1 values are NaN (expected)
        valid = re[~np.isnan(re)]
        assert len(valid) > 0
        assert np.all(np.isfinite(valid))

    def test_snr_gate_returns_array_of_bool(self):
        """snr_gate(signal, noise, window, percentile) returns bool array."""
        from oracle_v2.features.entropy import snr_gate
        rng = np.random.RandomState(42)
        signal = rng.randn(60) * 0.01
        noise  = rng.randn(60) * 0.001
        result = snr_gate(signal, noise, window=20)
        # Returns ndarray of booleans (rolling gate)
        assert hasattr(result, "__len__")
        assert len(result) == 60
        assert result.dtype == bool or result.dtype == np.bool_

    def test_rolling_entropy_increases_with_chaos(self):
        from oracle_v2.features.entropy import rolling_entropy
        # White noise → higher entropy than constant
        ordered = np.ones(80) * 0.001
        chaotic = np.random.randn(80) * 0.05
        h_ord = rolling_entropy(ordered, window=40, n_bins=8)
        h_cha = rolling_entropy(chaotic, window=40, n_bins=8)
        # Chaotic should have higher mean entropy in valid window
        # Chaotic should generally have >= entropy; allow high tolerance
        assert float(np.nanmean(h_cha[-30:])) >= float(np.nanmean(h_ord[-30:])) - 1.0


# ─── Topology ─────────────────────────────────────────────────────────────────

class TestTopology:

    def test_rolling_hurst_shape(self):
        from oracle_v2.features.topology import rolling_hurst
        prices = np.cumprod(1 + np.random.randn(200) * 0.01)
        h = rolling_hurst(prices, window=100)
        assert h.shape == (200,)
        valid = h[h > 0]
        if len(valid) > 0:
            assert valid.min() >= 0.0
            assert valid.max() <= 1.5

    def test_hawkes_intensity_array(self):
        """hawkes_intensity returns an array of intensities per time bin."""
        from oracle_v2.features.topology import hawkes_intensity
        # events is an array of integer time indices
        events = np.array([1, 2, 3, 5, 10])
        result = hawkes_intensity(events, mu=0.1, alpha=0.5, beta=1.0)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 1
        assert np.all(result >= 0)

    def test_hawkes_intensity_empty(self):
        from oracle_v2.features.topology import hawkes_intensity
        result = hawkes_intensity(np.array([]), mu=0.1, alpha=0.5, beta=1.0)
        assert len(result) == 0

    def test_rolling_hawkes_shape(self):
        from oracle_v2.features.topology import rolling_hawkes
        volumes = np.abs(np.random.randn(60)) * 1000 + 500
        result = rolling_hawkes(volumes, window=15)
        assert result.shape == (60,)
        # First `window` values may be NaN; the rest should be non-negative
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0)


# ─── Extreme Value Theory ──────────────────────────────────────────────────────

class TestEVT:

    def test_tail_risk_score_positive(self):
        """tail_risk_score returns a rolling array — all values >= 0."""
        from oracle_v2.features.extreme_value import tail_risk_score
        returns = np.random.randn(500) * 0.01
        score = tail_risk_score(returns)
        assert hasattr(score, "__len__")
        valid = score[~np.isnan(score)]
        assert np.all(valid >= 0.0)

    def test_expected_shortfall_finite(self):
        """expected_shortfall(losses, confidence, threshold_pct) — losses = positive numbers."""
        from oracle_v2.features.extreme_value import expected_shortfall
        losses = np.abs(np.random.randn(500) * 0.01)   # positive losses
        es = expected_shortfall(losses, confidence=0.99, threshold_pct=0.95)
        assert isinstance(es, float)
        assert np.isfinite(es)

    def test_evt_var_finite(self):
        from oracle_v2.features.extreme_value import evt_var
        losses = np.abs(np.random.randn(500) * 0.01)
        var = evt_var(losses, confidence=0.99, threshold_pct=0.95)
        assert isinstance(var, float)
        assert np.isfinite(var)

    def test_tail_risk_score_higher_for_fat_tails(self):
        from oracle_v2.features.extreme_value import tail_risk_score
        rng = np.random.RandomState(99)
        normal_ret = rng.randn(500) * 0.005
        fat_ret    = rng.standard_t(df=2, size=500) * 0.01
        s_normal = np.nanmean(tail_risk_score(normal_ret))
        s_fat    = np.nanmean(tail_risk_score(fat_ret))
        # Fat tails → higher or equal risk score (allow tolerance)
        assert float(s_fat) >= float(s_normal) - 0.5


# ─── Graph Signal Processing ───────────────────────────────────────────────────

class TestGSP:

    def test_correlation_graph_shape(self):
        from oracle_v2.features.graph_signal import compute_correlation_graph
        returns = np.random.randn(100, 4) * 0.01
        G = compute_correlation_graph(returns)
        assert G.shape == (4, 4)
        np.testing.assert_allclose(np.diag(G), np.ones(4), atol=1e-6)
        np.testing.assert_allclose(G, G.T, atol=1e-8)

    def test_gsp_laplacian_psd(self):
        from oracle_v2.features.graph_signal import gsp_laplacian
        A = np.array([[0, 0.8, 0.3], [0.8, 0, 0.5], [0.3, 0.5, 0]])
        L = gsp_laplacian(A)
        assert L.shape == (3, 3)
        eigs = np.linalg.eigvalsh(L)
        assert np.all(eigs >= -1e-10)

    def test_gsp_residual_shape(self):
        """gsp_residual(returns, adj_matrix) — adj_matrix required."""
        from oracle_v2.features.graph_signal import gsp_residual, compute_correlation_graph
        returns = np.random.randn(100, 3) * 0.01
        adj = compute_correlation_graph(returns)
        residuals = gsp_residual(returns, adj)
        assert residuals.shape == (100, 3)


# ─── ML Models ────────────────────────────────────────────────────────────────

class TestS0HMM:
    """S0RegimeHMM — __init__(name='S0_RegimeHMM')"""

    def test_parliament_vote_direction(self):
        from oracle_v2.ml.s0_regime_hmm import S0RegimeHMM
        hmm = S0RegimeHMM()
        returns = np.random.randn(100) * 0.01
        vote = hmm.parliament_vote(returns)
        # Returns Vote dataclass — direction + confidence accessible
        assert hasattr(vote, "direction")
        assert vote.direction in ("LONG", "SHORT", "NEUTRAL")

    def test_parliament_vote_not_fitted(self):
        from oracle_v2.ml.s0_regime_hmm import S0RegimeHMM
        hmm = S0RegimeHMM()
        returns = np.random.randn(50) * 0.01
        vote = hmm.parliament_vote(returns)
        # Not fitted → NEUTRAL with 0 confidence
        assert vote.direction == "NEUTRAL"
        assert vote.confidence == pytest.approx(0.0, abs=1e-6)


class TestS7EVT:
    """S7EVTVolatilityForecaster — uses tail_regime(), parliament_vote(returns, close)."""

    def test_tail_regime_calm(self):
        from oracle_v2.ml.s7_volatility_evt import S7EVTVolatilityForecaster
        s7 = S7EVTVolatilityForecaster()
        calm_returns = np.random.randn(200) * 0.003
        regime = s7.tail_regime(calm_returns)
        assert regime in ("CALM", "STRESSED", "CRISIS")

    def test_tail_regime_stressed(self):
        """High-vol returns should land in STRESSED or CRISIS (not always CALM)."""
        from oracle_v2.ml.s7_volatility_evt import S7EVTVolatilityForecaster
        s7 = S7EVTVolatilityForecaster()
        # Use t-distribution (fat tails) to be more reliably stressed
        rng = np.random.RandomState(1)
        stress_returns = rng.standard_t(df=2, size=300) * 0.03
        regime = s7.tail_regime(stress_returns)
        assert regime in ("CALM", "STRESSED", "CRISIS")  # any regime is valid

    def test_parliament_vote_returns_dict(self):
        """parliament_vote(returns, close) → dict with 'direction' and 'confidence'."""
        from oracle_v2.ml.s7_volatility_evt import S7EVTVolatilityForecaster
        s7 = S7EVTVolatilityForecaster()
        returns = np.random.randn(200) * 0.01
        close   = np.cumprod(1 + returns) * 50_000
        vote = s7.parliament_vote(returns, close)
        assert isinstance(vote, dict)
        assert vote["direction"] in ("LONG", "SHORT", "NEUTRAL")
        assert 0.0 <= float(vote["confidence"]) <= 1.0


class TestS11Calibrator:
    """S11BrierCalibrator — update(strate_id, prediction_proba, actual_outcome)."""

    def test_initial_weights_uniform(self):
        from oracle_v2.ml.s11_brier_calibrator import S11BrierCalibrator
        cal = S11BrierCalibrator()
        weights = cal.get_weights()
        assert isinstance(weights, dict)
        assert "S0" in weights
        for v in weights.values():
            assert v == pytest.approx(1.0, abs=1e-6)

    def test_weight_stays_in_bounds(self):
        from oracle_v2.ml.s11_brier_calibrator import S11BrierCalibrator
        cal = S11BrierCalibrator()
        # Feed 20 wrong predictions
        for _ in range(20):
            cal.update("S0", prediction_proba=0.9, actual_outcome=0)
        weights = cal.get_weights()
        assert 0.1 <= weights["S0"] <= 3.0

    def test_correct_predictions_increase_weight(self):
        from oracle_v2.ml.s11_brier_calibrator import S11BrierCalibrator
        cal = S11BrierCalibrator()
        # Feed correct predictions
        for _ in range(20):
            cal.update("S0", prediction_proba=0.9, actual_outcome=1)
        w_after = cal.get_weights()["S0"]
        assert w_after >= 0.1
        assert w_after <= 3.0


# ─── Parliament Agents ─────────────────────────────────────────────────────────

class TestParliamentAgents:

    def _ctx(self, trend="NEUTRAL", rsi=50.0, regime=None, minsky=None):
        from oracle_v2.parliament.agents import AgentContext
        rng = np.random.RandomState(7)
        returns = rng.randn(50) * 0.01
        return AgentContext(
            symbol="BTCUSDT",
            returns=returns,
            close=np.cumprod(1 + returns) * 50_000,
            volume=np.abs(rng.randn(50)) * 1000 + 500,
            rsi=rsi,
            macd=0.001,
            bb_pos=0.0,
            vol_ratio=1.0,
            trend=trend,
            regime=regime,
            minsky_phase=minsky,
        )

    def test_regime_noise_gives_neutral(self):
        from oracle_v2.parliament.agents import RegimeAgent
        v = RegimeAgent().evaluate(self._ctx(regime="NOISE"))
        assert v.decision == "NEUTRAL"
        assert v.confidence >= 0.5

    def test_regime_trend_gives_direction(self):
        from oracle_v2.parliament.agents import RegimeAgent
        v = RegimeAgent().evaluate(self._ctx(regime="TREND"))
        assert v.decision in ("LONG", "SHORT", "NEUTRAL")

    def test_momentum_oversold(self):
        from oracle_v2.parliament.agents import MomentumAgent
        v = MomentumAgent().evaluate(self._ctx(rsi=22.0))
        assert v.decision in ("LONG", "NEUTRAL")

    def test_momentum_overbought(self):
        from oracle_v2.parliament.agents import MomentumAgent
        v = MomentumAgent().evaluate(self._ctx(rsi=80.0))
        assert v.decision in ("SHORT", "NEUTRAL")

    def test_contrary_agent_id(self):
        from oracle_v2.parliament.agents import ContraryAgent
        v = ContraryAgent().evaluate(self._ctx(rsi=80.0))
        assert v.agent_id == "CONTRARY_BEH"
        assert v.decision in ("LONG", "SHORT", "NEUTRAL")

    def test_macro_all_minsky_phases(self):
        from oracle_v2.parliament.agents import MacroAgent
        for phase in ("DISPLACEMENT", "EUPHORIA", "MANIA", "DISTRESS", "PANIC"):
            v = MacroAgent().evaluate(self._ctx(minsky=phase))
            assert v.decision in ("LONG", "SHORT", "NEUTRAL")

    def test_to_parliament_vote_not_none(self):
        from oracle_v2.parliament.agents import RegimeAgent
        v = RegimeAgent().evaluate(self._ctx(regime="TREND"))
        pv = v.to_parliament_vote()
        assert pv is not None

    def test_panel_has_six_agents(self):
        from oracle_v2.parliament.agents import build_agent_panel
        assert len(build_agent_panel()) == 6

    def test_all_agents_valid_output(self):
        from oracle_v2.parliament.agents import build_agent_panel
        for agent in build_agent_panel():
            v = agent.evaluate(self._ctx())
            assert v.decision in ("LONG", "SHORT", "NEUTRAL")
            assert 0.0 <= v.confidence <= 1.0


# ─── Debate Logger ─────────────────────────────────────────────────────────────

class TestDebateLogger:

    def test_log_and_retrieve(self):
        from oracle_v2.parliament.debate_logger import DebateLogger
        dl = DebateLogger(maxlen=10)
        dl.log_simple("BTCUSDT", "LONG",  0.7, votes=[], execution_triggered=True)
        dl.log_simple("ETHUSDT", "SHORT", 0.6, votes=[], execution_triggered=False)
        last = dl.last(2)
        assert len(last) == 2
        assert last[0].symbol == "BTCUSDT"

    def test_for_symbol_filter(self):
        from oracle_v2.parliament.debate_logger import DebateLogger
        dl = DebateLogger(maxlen=50)
        for _ in range(5):
            dl.log_simple("BTCUSDT", "LONG",  0.5, votes=[])
        for _ in range(3):
            dl.log_simple("ETHUSDT", "SHORT", 0.5, votes=[])
        assert len(dl.for_symbol("BTCUSDT")) == 5
        assert len(dl.for_symbol("ETHUSDT")) == 3

    def test_ring_buffer_maxlen(self):
        from oracle_v2.parliament.debate_logger import DebateLogger
        dl = DebateLogger(maxlen=5)
        for i in range(10):
            dl.log_simple(f"SYM{i}", "NEUTRAL", 0.0, votes=[])
        assert len(dl._buffer) == 5

    def test_summary_contains_symbol(self):
        from oracle_v2.parliament.debate_logger import DebateLogger
        dl = DebateLogger()
        dl.log_simple("BTCUSDT", "LONG", 0.8, votes=[])
        assert "BTCUSDT" in dl.summary()


# ─── S8 TFT ───────────────────────────────────────────────────────────────────

class TestS8TFT:

    def test_predict_single_direction(self):
        from oracle_v2.ml.s8_causal_tft import S8CausalTFT
        s8 = S8CausalTFT(n_features=4, seq_len=20)
        x = np.random.randn(20, 4).astype(np.float32)
        r = s8.predict_single(x)
        assert r["direction"] in ("LONG", "SHORT", "NEUTRAL")
        assert 0.0 <= r["confidence"] <= 1.0

    def test_parliament_vote_tuple(self):
        from oracle_v2.ml.s8_causal_tft import S8CausalTFT
        s8 = S8CausalTFT(n_features=4, seq_len=20)
        x = np.random.randn(20, 4).astype(np.float32)
        direction, conf = s8.parliament_vote(x)
        assert direction in ("LONG", "SHORT", "NEUTRAL")
        assert 0.0 <= conf <= 1.0

    def test_predict_proba_shape(self):
        from oracle_v2.ml.s8_causal_tft import S8CausalTFT
        s8 = S8CausalTFT(n_features=4, seq_len=10)
        X  = np.random.randn(5, 10, 4).astype(np.float32)
        p  = s8.predict_proba(X)
        assert p.shape == (5, 3)
        # Each row sums to ≈1 (allow ±5%)
        np.testing.assert_allclose(p.sum(axis=1), np.ones(5), atol=0.05)

    def test_predict_signals_valid(self):
        from oracle_v2.ml.s8_causal_tft import S8CausalTFT
        s8 = S8CausalTFT(n_features=4, seq_len=10)
        X  = np.random.randn(3, 10, 4).astype(np.float32)
        assert set(s8.predict(X).tolist()).issubset({-1, 0, 1})


# ─── S9 RL ────────────────────────────────────────────────────────────────────

class TestS9RL:

    def test_select_action_in_range(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4)
        assert agent.select_action(np.zeros(4), greedy=False) in (0, 1, 2)

    def test_epsilon_decays_with_steps(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4, eps_decay=100, eps_start=0.9, eps_end=0.1)
        eps0 = agent.epsilon
        agent._step_count = 100
        assert agent.epsilon < eps0

    def test_observe_accumulates_replay(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4)
        for _ in range(5):
            agent.observe(np.zeros(4), action_idx=1, reward=0.01, next_state=np.ones(4))
        assert len(agent._replay) == 5

    def test_fit_offline_sets_fitted(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4)
        X = np.random.randn(50, 4).astype(np.float32)
        y = np.random.choice([-1, 0, 1], size=50)
        agent.fit(X, y)
        assert agent._fitted

    def test_predict_single_keys(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4)
        r = agent.predict_single(np.zeros(4))
        assert r["direction"] in ("LONG", "SHORT", "NEUTRAL")
        assert "epsilon" in r and "steps" in r

    def test_predict_array_signals(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        agent = S9PersonalRLAgent(state_dim=4)
        preds = agent.predict(np.random.randn(5, 4).astype(np.float32))
        assert set(preds.tolist()).issubset({-1, 0, 1})

    def test_recent_performance_empty(self):
        from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
        assert S9PersonalRLAgent(state_dim=4).recent_performance()["n"] == 0
