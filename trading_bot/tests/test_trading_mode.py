"""Tests pour le TradingModeManager — separation simulation/paper/live."""

import sys
sys.path.insert(0, ".")

from core.trading_mode import TradingModeManager, TradingMode, LiveReadinessError
import pytest


# ── Modes de base ────────────────────────────────────────────────────────────

def test_simulation_mode():
    tm = TradingModeManager(vault_path="vault", mode="simulation")
    assert tm.mode == TradingMode.SIMULATION
    assert tm.use_real_data is False
    assert tm.execute_real_orders is False


def test_paper_mode():
    tm = TradingModeManager(vault_path="vault", mode="paper")
    assert tm.mode == TradingMode.PAPER
    assert tm.use_real_data is True
    assert tm.execute_real_orders is False


def test_live_mode():
    tm = TradingModeManager(vault_path="vault", mode="live")
    assert tm.mode == TradingMode.LIVE
    assert tm.use_real_data is True
    assert tm.execute_real_orders is True


# ── Validation de config ─────────────────────────────────────────────────────

def test_simulation_no_keys_needed():
    tm = TradingModeManager(vault_path="vault", mode="simulation")
    issues = tm.validate_config({"binance_api_key": "", "binance_secret": ""})
    # Simulation n'a pas besoin de cles
    assert not any("binance" in i for i in issues)


def test_paper_needs_api_keys():
    tm = TradingModeManager(vault_path="vault", mode="paper")
    issues = tm.validate_config({"binance_api_key": "", "binance_secret": ""})
    assert len(issues) >= 2  # api_key + secret manquants


def test_paper_ok_with_keys():
    tm = TradingModeManager(vault_path="vault", mode="paper")
    issues = tm.validate_config({"binance_api_key": "abc", "binance_secret": "def"})
    assert len(issues) == 0


# ── Live readiness ───────────────────────────────────────────────────────────

def test_live_readiness_fails_not_enough_trades():
    tm = TradingModeManager(vault_path="vault", mode="paper", min_paper_trades=50)
    result = tm.check_live_readiness({
        "total_trades": 10,
        "sharpe_ratio": 1.0,
        "win_rate": 0.55,
        "profit_factor": 1.5,
        "max_drawdown_pct": 5.0,
        "total_return_pct": 10.0,
    })
    assert result["ready"] is False


def test_live_readiness_passes_all_checks():
    tm = TradingModeManager(vault_path="vault", mode="paper", min_paper_trades=50)
    result = tm.check_live_readiness({
        "total_trades": 100,
        "sharpe_ratio": 1.5,
        "win_rate": 0.55,
        "profit_factor": 1.8,
        "max_drawdown_pct": 10.0,
        "total_return_pct": 25.0,
    })
    assert result["ready"] is True
    assert result["failed"] == 0


# ── Snapshot ─────────────────────────────────────────────────────────────────

def test_snapshot():
    tm = TradingModeManager(vault_path="vault", mode="paper")
    snap = tm.snapshot()
    assert snap["mode"] == "paper"
    assert snap["use_real_data"] is True
    assert snap["execute_orders"] is False
