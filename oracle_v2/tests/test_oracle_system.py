"""
Tests OracleSystem — intégration brain + strates + safety.
Pas de connexion réseau — tout mocké.
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.config import OracleConfig
from oracle_v2.oracle_system import OracleSystem


def make_config(**kwargs):
    cfg = OracleConfig()
    cfg.BINANCE_API_KEY = ""   # pas de connexion réelle
    cfg.TELEGRAM_TOKEN = ""
    cfg.MODE = "paper"
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestOracleSystemInit:

    def test_init_no_crash(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        assert system.brainstem is not None
        assert system.safety_kernel is not None
        assert system.working_memory is not None
        assert system.parliament is not None
        assert system.polymarket_strate is not None

    def test_status_structure(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        status = system.get_status()
        assert "mode" in status
        assert "brainstem" in status
        assert "open_positions" in status
        assert status["mode"] == "paper"

    def test_pause_resume(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        assert system._paused is False
        system.pause()
        assert system._paused is True
        system.resume()
        assert system._paused is False

    def test_get_active_signals_empty(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        assert system.get_active_signals() == []

    def test_daily_report_empty(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        report = system.get_daily_report()
        assert report["total_trades"] == 0
        assert report["wins"] == 0
        assert report["winrate"] == 0.0

    def test_brainstem_alive_on_start(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        alive, reason = system.brainstem.is_alive()
        assert alive is True

    def test_safety_kernel_blocks_bad_order(self):
        from oracle_v2.brain.safety_kernel import Order
        cfg = make_config()
        system = OracleSystem(cfg)
        bad_order = Order(
            symbol="BTCUSDT", direction="LONG",
            size_usdt=500, leverage=10.0,  # leverage trop élevé
            sl_pct=0.01, tp_pct=0.025,
            source_strate="TEST", confidence=0.8
        )
        report = system.safety_kernel.validate(bad_order, capital=10_000)
        assert report.cleared is False
        assert "LEVERAGE" in report.reason

    def test_parliament_with_brainstem_integration(self):
        """Vérifie que brainstem bloqué stoppe bien avant le parlement."""
        cfg = make_config(MAX_CONSECUTIVE_LOSSES=1)
        system = OracleSystem(cfg)
        system.brainstem.register_trade(-0.01)  # 1 perte
        alive, reason = system.brainstem.is_alive()
        assert alive is False  # bloqué

    def test_working_memory_integrated(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        system.working_memory.push("LONG", 0.8, "A")
        system.working_memory.push("LONG", 0.7, "B")
        consensus = system.working_memory.get_consensus()
        assert consensus is not None
        assert consensus[0] == "LONG"

    def test_hebbian_weights_registered(self):
        cfg = make_config()
        system = OracleSystem(cfg)
        # Tous les noms de strates doivent avoir un poids initial
        for strate in ["AMD", "MOMENTUM", "STRUCTURE", "MACRO", "POLYMARKET", "PREDICTIVE", "LATENCY_ARB"]:
            w = system.hebbian.get_weight(strate)
            assert w == 1.0, f"Poids initial {strate} != 1.0"

    def test_latency_arb_initialized(self):
        """BTC latency arb strate and dedicated working memory are present."""
        cfg = make_config()
        system = OracleSystem(cfg)
        assert system.latency_arb is not None
        assert system.btc_working_memory is not None
        assert system.config.BTC_LATENCY_ARB_ENABLED is True

    @pytest.mark.asyncio
    async def test_run_cycle_with_blocked_brainstem(self):
        """Si brainstem bloqué, _run_cycle() retourne sans analyser."""
        cfg = make_config()
        system = OracleSystem(cfg)
        # Bloquer le brainstem
        system.brainstem.state.daily_pnl = -0.99
        # Mock polymarket pour ne pas appeler l'API
        system.polymarket_strate.scan = AsyncMock(return_value=[])
        # Doit retourner sans crash
        await system._run_cycle()
        assert system.get_active_signals() == []

    @pytest.mark.asyncio
    async def test_analyze_symbol_no_connector(self):
        """Sans connecteur Binance, _analyze_symbol() retourne gracieusement."""
        cfg = make_config()
        system = OracleSystem(cfg)
        system.binance = None  # pas de connecteur
        # Ne doit pas lever d'exception
        await system._analyze_symbol("BTCUSDT", [])

    def test_cognitive_mgr_initialized(self):
        """CognitiveStrateManager est initialisé et get_status() retourne les clés attendues."""
        cfg = make_config()
        system = OracleSystem(cfg)
        assert system.cognitive_mgr is not None
        status = system.cognitive_mgr.get_status()
        assert isinstance(status, dict)
        assert "available" in status
        assert "count" in status
        # count doit correspondre à la longueur de available
        assert status["count"] == len(status["available"])
        # Si les strates cognitives ne sont pas disponibles, count == 0 est acceptable
        assert status["count"] >= 0

    def test_hebbian_includes_cognitive_strates(self):
        """HebbianWeightManager a des poids initiaux pour les 12 strates cognitives comprises."""
        cfg = make_config()
        system = OracleSystem(cfg)
        all_12 = [
            "AMD", "MOMENTUM", "STRUCTURE", "MACRO", "POLYMARKET",
            "PREDICTIVE", "LATENCY_ARB",
            "EPISTEMIQUE", "MINSKY", "REFLEXIVITE", "COMPORTEMENTAL", "FRACTAL",
        ]
        for strate in all_12:
            w = system.hebbian.get_weight(strate)
            assert w == 1.0, f"Poids initial {strate} attendu 1.0, obtenu {w}"
