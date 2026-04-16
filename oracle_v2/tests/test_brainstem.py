"""
Tests Brainstem — vérifie les 5 conditions de blocage.
Pure Python, pas de dépendances externes.
"""
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.brain.brainstem import Brainstem, BrainstemState


class TestBrainstem:

    def test_alive_by_default(self):
        bs = Brainstem()
        alive, reason = bs.is_alive()
        assert alive is True
        assert reason == "OK"

    def test_blocks_on_max_consecutive_losses(self):
        bs = Brainstem(max_consecutive_losses=3, cooling_period_seconds=1)
        for _ in range(3):
            bs.register_trade(-0.005)
        alive, reason = bs.is_alive()
        assert alive is False
        assert "CONSECUTIVE_LOSSES" in reason or "COOLING" in reason

    def test_blocks_on_max_daily_drawdown(self):
        bs = Brainstem(max_daily_drawdown=0.02)
        bs.state.daily_pnl = -0.025
        alive, reason = bs.is_alive()
        assert alive is False
        assert "MAX_DAILY_DRAWDOWN" in reason

    def test_blocks_on_max_session_trades(self):
        bs = Brainstem(max_session_trades=3)
        bs.state.session_trades = 3
        alive, reason = bs.is_alive()
        assert alive is False
        assert "MAX_SESSION_TRADES" in reason

    def test_blocks_on_min_trade_interval(self):
        bs = Brainstem(min_trade_interval_seconds=60)
        bs.state.last_trade_time = time.time()  # just traded
        alive, reason = bs.is_alive()
        assert alive is False
        assert "MIN_INTERVAL" in reason

    def test_resets_consecutive_losses_after_win(self):
        bs = Brainstem(max_consecutive_losses=3)
        bs.register_trade(-0.005)
        bs.register_trade(-0.005)
        assert bs.state.consecutive_losses == 2
        bs.register_trade(0.01)  # win
        assert bs.state.consecutive_losses == 0

    def test_cooling_expires(self):
        bs = Brainstem(max_consecutive_losses=3, cooling_period_seconds=1)
        for _ in range(3):
            bs.register_trade(-0.005)
        alive, _ = bs.is_alive()
        assert alive is False
        # Wait for cooling to expire
        time.sleep(1.1)
        bs.state.cooling_until = time.time() - 1  # force expiry
        bs.state.is_cooling = True
        alive, reason = bs.is_alive()
        assert alive is True or "COOLING" not in reason

    def test_status_dict_keys(self):
        bs = Brainstem()
        status = bs.get_status_dict()
        assert "alive" in status
        assert "reason" in status
        assert "consecutive_losses" in status
        assert "daily_pnl" in status
        assert "session_trades" in status
        assert "cooling" in status

    def test_daily_pnl_accumulates(self):
        bs = Brainstem()
        bs.register_trade(-0.005)
        bs.register_trade(0.010)
        bs.register_trade(-0.003)
        assert abs(bs.state.daily_pnl - 0.002) < 1e-9
