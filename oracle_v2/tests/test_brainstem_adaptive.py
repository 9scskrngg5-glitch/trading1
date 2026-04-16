"""Tests Brainstem — drawdown adaptatif, register_trade séparé, cooling."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
import time
from oracle_v2.brain.brainstem import Brainstem


class TestBrainstemAdaptive:

    def test_base_drawdown_blocks_at_threshold(self):
        bs = Brainstem(max_daily_drawdown=0.02, adaptive_drawdown=False)
        bs.register_trade(-0.021)
        alive, reason = bs.is_alive()
        assert not alive
        assert "MAX_DAILY_DRAWDOWN" in reason

    def test_adaptive_drawdown_allows_more_with_high_confidence(self):
        """Avec haute confiance, le seuil de drawdown est élargi."""
        bs = Brainstem(
            max_daily_drawdown=0.02,
            adaptive_drawdown=True,
            high_edge_threshold=0.75,
            high_edge_max_drawdown=0.04,
        )
        bs.set_signal_confidence(1.0)   # confiance maximale → seuil ≈ 4%
        bs.register_trade(-0.025)       # -2.5% : dépasse base (2%) mais pas max (4%)
        alive, reason = bs.is_alive()
        assert alive, f"Brainstem devrait autoriser avec haute confiance. Raison: {reason}"

    def test_adaptive_drawdown_blocks_above_max(self):
        bs = Brainstem(
            max_daily_drawdown=0.02,
            adaptive_drawdown=True,
            high_edge_threshold=0.75,
            high_edge_max_drawdown=0.04,
        )
        bs.set_signal_confidence(1.0)
        bs.register_trade(-0.045)   # Dépasse même le seuil élargi (4%)
        alive, reason = bs.is_alive()
        assert not alive

    def test_low_confidence_keeps_base_drawdown(self):
        bs = Brainstem(
            max_daily_drawdown=0.02,
            adaptive_drawdown=True,
            high_edge_threshold=0.75,
        )
        bs.set_signal_confidence(0.3)   # faible confiance → seuil de base
        bs.register_trade(-0.021)
        alive, reason = bs.is_alive()
        assert not alive, "Basse confiance → seuil de base → doit bloquer"

    def test_register_trade_opened_does_not_affect_pnl(self):
        """register_trade_opened() ne doit pas toucher daily_pnl."""
        bs = Brainstem(max_daily_drawdown=0.02)
        initial_pnl = bs.state.daily_pnl
        bs.register_trade_opened()
        bs.register_trade_opened()
        assert bs.state.daily_pnl == initial_pnl
        assert bs.state.session_trades == 2

    def test_register_trade_updates_pnl_correctly(self):
        bs = Brainstem()
        bs.register_trade(0.015)
        assert bs.state.daily_pnl == pytest.approx(0.015)
        bs.register_trade(-0.008)
        assert bs.state.daily_pnl == pytest.approx(0.007)

    def test_consecutive_losses_trigger_cooling(self):
        """3 pertes consécutives de -0.5% (total -1.5%) → sous le drawdown de 2% → cooling activé."""
        bs = Brainstem(
            max_consecutive_losses=3,
            cooling_period_seconds=900,
            max_daily_drawdown=0.02,
        )
        for _ in range(3):
            bs.register_trade(-0.005)   # -0.5% × 3 = -1.5% total < 2% drawdown
        alive, reason = bs.is_alive()
        assert not alive
        assert "COOLING" in reason

    def test_profit_resets_consecutive_losses(self):
        bs = Brainstem(max_consecutive_losses=3)
        bs.register_trade(-0.01)
        bs.register_trade(-0.01)
        bs.register_trade(0.02)   # un gain réinitialise le compteur
        assert bs.state.consecutive_losses == 0

    def test_cumulative_winrate(self):
        bs = Brainstem()
        bs.register_trade(0.01)
        bs.register_trade(0.02)
        bs.register_trade(-0.005)
        status = bs.get_status_dict()
        assert status["cumulative_winrate"] == pytest.approx(2/3, abs=0.01)

    def test_daily_reset_clears_pnl(self):
        from datetime import date, timedelta
        bs = Brainstem(max_daily_drawdown=0.02)
        bs.register_trade(-0.021)
        # Simuler un reset journalier en changeant la date
        bs.state.daily_date = date.today() - timedelta(days=1)
        # is_alive() va réinitialiser
        alive, _ = bs.is_alive()
        assert alive, "Après reset journalier, le brainstem doit être vivant"
        assert bs.state.daily_pnl == 0.0

    def test_status_dict_has_all_keys(self):
        bs = Brainstem()
        status = bs.get_status_dict()
        for key in ["alive", "reason", "daily_pnl", "session_trades",
                    "cooling", "effective_drawdown_limit", "cumulative_winrate"]:
            assert key in status, f"Clé manquante: {key}"
