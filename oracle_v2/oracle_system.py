"""
OracleSystem — Orchestrateur principal ORACLE v2.
Wire : Brain (brainstem + safety + parliament) ↔ Strates ↔ Connectors ↔ Telegram ↔ UI.

Usage:
    system = OracleSystem(config)
    asyncio.run(system.run())
"""
import asyncio
import logging
import os
import time
from typing import Optional
from datetime import datetime, timezone, timedelta

from config import OracleConfig
from events import get_event_bus, EventType, reset_event_bus
from metrics import MetricsTracker

logger = logging.getLogger("ORACLE.System")

# UTC-10 Tahiti
TAHITI_TZ = timezone(timedelta(hours=-10))



class OracleSystem:
    """
    Système de trading neuromorphique ORACLE v2.

    Architecture :
        Brainstem (survie) → SafetyKernel (risque) → WorkingMemory (signal) →
        Parliament (consensus) → Connectors (exécution)

    Règles non-négociables :
        1. Brainstem = priorité absolue — override tout
        2. SafetyKernel = non-bypassable — chaque ordre y passe
        3. WorkingMemory = consensus 2/3 requis sur 5min
        4. Mode paper par défaut — jamais live sans confirm
    """

    def __init__(self, config: OracleConfig):
        self.config = config
        self.mode = config.MODE
        self._paused = False
        self._running = False

        # State
        self.last_parliament_decision = None
        self._active_signals: list = []
        self._trade_history: list = []
        self._open_positions: list = []

        # Brain
        self._init_brain()

        # Strates
        self._init_strates()

        # Narrator — Oracle's voice
        self._init_narrator()

        # Connectors (lazy — initialisés au run())
        self.binance = None
        self.capital = None
        self.polymarket_connector = None

        # Telegram alerts (lazy)
        self.alert_queue = None

        # ── Trade repository (SQLite journal) ─────────────────────────────────
        self._init_trade_repo()

        # ── Multica-inspired issue tracker ────────────────────────────────────
        self._init_tracker()

        # ── Event Bus (singleton global) ───────────────────────────────────────
        self._bus = get_event_bus()
        self._wire_event_handlers()

        # ── Métriques financières (VaR/CVaR/Sortino) ──────────────────────────
        self._metrics = MetricsTracker(window=100, corr_threshold=0.7)

        # ── Suivi dégradation connecteurs ─────────────────────────────────────
        self._connector_degraded: set = set()

        # ── Délégués métier ────────────────────────────────────────────────────
        self._init_engines()

        logger.info(f"OracleSystem initialisé — Mode: {self.mode.upper()} | Paires: {config.TRADING_PAIRS}")

    def _wire_event_handlers(self) -> None:
        """Inscrit les handlers sur le bus d'événements."""
        bus = self._bus  # EventType importé en haut de module

        # Mise à jour métriques à chaque trade fermé
        bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed)
        # Log des rejets pour audit trail
        bus.subscribe(EventType.TRADE_REJECTED, self._on_trade_rejected)
        # Mise à jour métriques brainstem
        bus.subscribe(EventType.BRAINSTEM_BLOCKED, self._on_brainstem_blocked)

    def _on_trade_closed(self, event) -> None:
        self._metrics.record_pnl("PARLIAMENT", event.pnl_pct)
        logger.debug(f"Event TRADE_CLOSED: {event.symbol} PnL={event.pnl_pct:+.2%}")

    def _on_trade_rejected(self, event) -> None:
        logger.info(f"Event TRADE_REJECTED: {event.symbol} [{event.layer}] {event.reason}")

    def _on_brainstem_blocked(self, event) -> None:
        logger.info(f"Event BRAINSTEM_BLOCKED: {event.reason}")

    # ─── INITIALISATION ───────────────────────────────────────────────

    def _init_brain(self):
        from brain.brainstem import Brainstem
        from brain.safety_kernel import SafetyKernel
        from brain.working_memory import WorkingMemory
        from brain.parliament import Parliament, HebbianWeightManager
        from brain.sensory_layer import SensoryLayer
        from brain.feature_layer import FeatureLayer
        from brain.predictive_layer import PredictiveLayer
        from brain.association_cortex import AssociationCortex

        _db_path = os.path.join(os.path.dirname(__file__), "vault", "oracle.db")

        self.brainstem = Brainstem(
            max_consecutive_losses=self.config.MAX_CONSECUTIVE_LOSSES,
            max_daily_drawdown=self.config.MAX_DAILY_DRAWDOWN,
            max_session_trades=self.config.MAX_SESSION_TRADES,
            adaptive_drawdown=self.config.ADAPTIVE_DRAWDOWN,
            high_edge_threshold=self.config.HIGH_EDGE_THRESHOLD,
            high_edge_max_drawdown=self.config.HIGH_EDGE_MAX_DRAWDOWN,
        )
        self.safety_kernel = SafetyKernel(
            max_leverage=self.config.MAX_LEVERAGE,
            max_position_pct=self.config.MAX_POSITION_SIZE_PCT,
            min_sl_pct=self.config.MIN_SL_PCT,
            max_sl_pct=self.config.MAX_SL_PCT,
            max_open_positions=self.config.MAX_OPEN_POSITIONS,
            max_total_notional_pct=self.config.MAX_TOTAL_NOTIONAL_PCT,
            db_path=_db_path,   # ← persistance positions (survit aux redémarrages)
        )
        self.working_memory = WorkingMemory(
            window=self.config.WORKING_MEMORY_WINDOW,
            required_consensus=self.config.WORKING_MEMORY_CONSENSUS,
            ttl=self.config.WORKING_MEMORY_TTL,
        )
        self.parliament = Parliament(quorum=self.config.PARLIAMENT_QUORUM)

        strate_names = [
            "AMD", "MOMENTUM", "STRUCTURE", "MACRO", "POLYMARKET", "PREDICTIVE", "LATENCY_ARB",
            "EPISTEMIQUE", "MINSKY", "REFLEXIVITE", "COMPORTEMENTAL", "FRACTAL",
            "TWITTER",  # signal sentiment X/Twitter — poids Hebbian persisté
        ]
        self.hebbian = HebbianWeightManager(strate_names, db_path=_db_path)
        self.parliament.set_weight_manager(self.hebbian)

        self.sensory = SensoryLayer(
            symbols=self.config.TRADING_PAIRS,
            timeframes=[self.config.PRIMARY_TIMEFRAME] + self.config.SECONDARY_TIMEFRAMES
        )
        self.feature_layer = FeatureLayer()
        self.predictive = PredictiveLayer()
        self.association = AssociationCortex()

        logger.info("Brain initialisé (Brainstem + SafetyKernel + Parliament + Hebbian)")

    def _init_strates(self):
        # Imports directs — __init__.py garantit oracle_v2/ dans sys.path
        from strates.amd_strate import AMDStrate
        from strates.momentum_strate import MomentumStrate
        from strates.structure_strate import StructureStrate
        from strates.macro_strate import MacroStrate
        from strates.polymarket_strate import PolymarketStrate
        from strates.latency_arb_strate import BtcLatencyArbStrate

        self.amd_strate = AMDStrate()
        self.momentum_strate = MomentumStrate()
        self.structure_strate = StructureStrate()
        self.macro_strate = MacroStrate()
        self.polymarket_strate = PolymarketStrate.from_config(self.config)
        self.latency_arb = BtcLatencyArbStrate(
            min_edge=self.config.BTC_LATENCY_ARB_MIN_EDGE,
            min_volume=self.config.BTC_LATENCY_ARB_MIN_VOLUME,
            kelly_max=self.config.BTC_LATENCY_ARB_KELLY_MAX,
            sigma=self.config.BTC_SIGMA_ANNUAL,
            cache_ttl=self.config.BTC_LATENCY_ARB_INTERVAL,
        )
        # BTC-specific working memory for latency arb fast signals
        from brain.working_memory import WorkingMemory
        self.btc_working_memory = WorkingMemory(window=3, required_consensus=2)

        # Strates cognitives (Épistémique, Minsky, Réflexivité, Comportemental, Fractal)
        from strates.cognitive_strates import CognitiveStrateManager
        self.cognitive_mgr = CognitiveStrateManager(
            vault_path=os.path.join(os.path.dirname(__file__), 'vault', 'cognitive')
        )

        # Twitter/X sentiment strate — signal externe pondéré BTC
        from strates.twitter_sentiment_strate import TwitterSentimentStrate

        self.twitter_strate = None
        if self.config.TWITTER_ENABLED:
            self.twitter_strate = TwitterSentimentStrate(
                bearer_token=self.config.TWITTER_BEARER_TOKEN,
            )
            self.twitter_strate.CACHE_TTL = self.config.TWITTER_CACHE_TTL
            self.twitter_strate.MIN_TWEETS_FOR_SIGNAL = self.config.TWITTER_MIN_TWEETS
            self.twitter_strate.CONFIDENCE_SCALE = self.config.TWITTER_MAX_CONF

        twitter_status = (
            "activée" if (self.twitter_strate and self.twitter_strate._available)
            else "désactivée (TWITTER_BEARER_TOKEN absent)"
        )
        cognitive_status = (
            f"Cognitives({', '.join(self.cognitive_mgr.available)})"
            if self.cognitive_mgr.available else "Cognitives: aucune strate disponible"
        )
        logger.info(
            f"Strates init: AMD + Momentum + Structure + Macro + Polymarket + BTC LatencyArb"
            f" | {cognitive_status} | Twitter: {twitter_status}"
        )

    def _init_narrator(self):
        from brain.narrator import OracleNarrator

        self.narrator = OracleNarrator(
            api_key=self.config.ANTHROPIC_API_KEY,
            use_llm=self.config.NARRATOR_LLM,
            free_gpt4_url=self.config.FREE_GPT4_URL,
        ) if self.config.NARRATOR_ENABLED else None

        hermes_status = ""
        if self.narrator and self.narrator._hermes:
            hermes_status = " | OpenRouter(hermes)" if self.narrator._hermes.is_available() else " | OpenRouter(no key)"
        logger.info(f"Narrator: {'LLM(Haiku)' if (self.narrator and self.narrator.use_llm) else 'template'}{hermes_status}")

    def _init_trade_repo(self):
        """Trade journal SQLite."""
        try:
            from db.repositories import TradeRepository
            db_path = os.path.join(os.path.dirname(__file__), "vault", "oracle.db")
            self._trade_repo = TradeRepository(db_path=db_path)
            logger.info(f"TradeRepository initialisé → {db_path}")
        except Exception as e:
            self._trade_repo = None
            logger.warning(f"TradeRepository non disponible: {e}")

    def _init_tracker(self):
        """Multica-inspired issue tracker pour audit trail des décisions."""
        try:
            from integrations.multica_tracker import MulticaTracker
        except ImportError:
            self.tracker = None
            logger.debug("MulticaTracker non disponible (integrations/ manquant)")
            return

        vault_dir = os.path.join(os.path.dirname(__file__), "vault")
        self.tracker = MulticaTracker(vault_dir=vault_dir, workspace_id=self.mode)
        logger.info(f"MulticaTracker initialisé — workspace={self.mode}")

    def _init_engines(self):
        """Instancie ExecutionEngine, CycleManager, PaperPositionMonitor et ParliamentCouncil."""
        from execution_engine import ExecutionEngine
        from cycle_manager import CycleManager
        from paper_monitor import PaperPositionMonitor

        self._execution_engine = ExecutionEngine(self)
        self._cycle_manager = CycleManager(self)

        # Paper monitor — surveille les SL/TP en paper mode
        self.paper_monitor = PaperPositionMonitor()
        self._bus.subscribe(EventType.TRADE_OPENED, self.paper_monitor.register)

        # Parliament Council — ML + agent panel + debate logger
        _db_path = os.path.join(os.path.dirname(__file__), "vault", "debates.db")
        try:
            from parliament.council import ParliamentCouncil
            self.parliament_council = ParliamentCouncil(self, db_path=_db_path)
            logger.info(f"ParliamentCouncil initialisé — {self.parliament_council.status()}")
        except Exception as e:
            self.parliament_council = None
            logger.debug(f"ParliamentCouncil non disponible: {e}")

        logger.info("ExecutionEngine + CycleManager + PaperMonitor + ParliamentCouncil initialisés")

    async def _init_connectors(self):
        from connectors.binance_connector import BinanceConnector
        from connectors.capital_connector import CapitalConnector

        if self.config.BINANCE_API_KEY:
            self.binance = BinanceConnector(
                api_key=self.config.BINANCE_API_KEY,
                secret=self.config.BINANCE_SECRET,
                testnet=self.config.BINANCE_TESTNET
            )
            await self.binance.initialize()
            logger.info(f"Binance connecté (testnet={self.config.BINANCE_TESTNET})")

            # Réconciliation live — corrige les désynchronisations DB↔exchange après un crash
            if self.mode == "live":
                live_symbols = await self.binance.fetch_position_symbols()
                self.safety_kernel.reconcile(live_symbols)
                logger.info(f"SafetyKernel réconcilié — positions live: {live_symbols or '[]'}")
        else:
            logger.warning("BINANCE_API_KEY absent — connecteur Binance désactivé")

        if self.config.CAPITAL_API_KEY:
            self.capital = CapitalConnector(
                api_key=self.config.CAPITAL_API_KEY,
                password=self.config.CAPITAL_PASSWORD,
                demo=(self.mode != "live")
            )
            await self.capital.authenticate()
            logger.info("Capital.com connecté")

    async def _init_telegram(self):
        if not self.config.TELEGRAM_TOKEN:
            logger.warning("TELEGRAM_TOKEN absent — alertes Telegram désactivées")
            return
        from telegram.alerts import AlertQueue
        self.alert_queue = AlertQueue(
            token=self.config.TELEGRAM_TOKEN,
            chat_id=self.config.TELEGRAM_CHAT_ID
        )
        await self.alert_queue.start()
        self.alert_queue.alert_system(
            f"ORACLE v2 démarré — Mode: {self.mode.upper()}\n"
            f"Paires: {', '.join(self.config.TRADING_PAIRS)}",
            level="SUCCESS"
        )
        logger.info("Telegram AlertQueue démarrée")

    # ─── MAIN LOOP ────────────────────────────────────────────────────

    async def _btc_latency_loop(self):
        """
        Fast BTC latency arbitrage loop — runs every BTC_LATENCY_ARB_INTERVAL seconds
        in parallel with the main 60s cycle.
        Feeds BTC working memory with fast signals for intra-cycle consensus.
        """
        while self._running:
            if not self._paused and self.config.BTC_LATENCY_ARB_ENABLED:
                try:
                    signals = await self.latency_arb.scan()
                    if signals:
                        vote = self.latency_arb.generate_parliament_vote(signals)
                        if vote.direction != "NEUTRAL" and vote.confidence > 0.3:
                            self.btc_working_memory.push(
                                vote.direction, vote.confidence, "LATENCY_ARB"
                            )
                            logger.info(
                                f"[BTC-ARB] {vote.direction} conf={vote.confidence:.0%} | "
                                f"{vote.reasoning}"
                            )
                            if self.narrator:
                                await self.narrator.polymarket_signal(signals, vote)
                            if self.alert_queue and vote.confidence > 0.6:
                                top = signals[0]
                                self.alert_queue.alert_polymarket(
                                    asset="BTC",
                                    direction=vote.direction,
                                    edge=top.edge,
                                    confidence=top.confidence,
                                    question=top.question[:80],
                                    kelly=top.kelly_fraction
                                )
                except Exception as e:
                    logger.warning(f"BTC latency arb error: {e}")
            await asyncio.sleep(self.config.BTC_LATENCY_ARB_INTERVAL)

    async def run(self):
        """
        Boucle principale ORACLE v2 — cycle 60s + boucle BTC latency arb 30s
        + ConnectorHealthCheck 30s.
        """
        self._running = True
        logger.info("ORACLE v2 démarrage de la boucle principale...")

        # Validation credentials (fail-fast avant toute connexion)
        self.config.validate_live_credentials()

        await self._init_connectors()
        await self._init_telegram()

        CYCLE_INTERVAL = 60  # secondes entre chaque cycle

        # Narrator — annonce le démarrage
        if self.narrator:
            all_strates = [
                "AMD", "MOMENTUM", "STRUCTURE", "MACRO", "POLYMARKET", "PREDICTIVE", "LATENCY_ARB",
                "EPISTEMIQUE", "MINSKY", "REFLEXIVITE", "COMPORTEMENTAL", "FRACTAL", "TWITTER",
            ]
            hw = {s: self.hebbian.get_weight(s) for s in all_strates}
            self.narrator.session_start(self.mode, self.config.TRADING_PAIRS, hw)

        # Lance les tâches parallèles
        latency_task = asyncio.create_task(self._btc_latency_loop())

        # ConnectorHealthCheck — ping toutes les 30s
        from connector_health import ConnectorHealthCheck
        health_task = asyncio.create_task(ConnectorHealthCheck(self).run())

        try:
            while self._running:
                # Bloquer si un connecteur est dégradé
                if self._connector_degraded:
                    degraded = ", ".join(self._connector_degraded)
                    logger.warning(f"Mode DEGRADED — connecteurs hors ligne: {degraded}")
                    await asyncio.sleep(30)
                    continue
                cycle_start = time.time()
                now_tahiti = datetime.now(TAHITI_TZ)
                logger.info(f"Cycle {now_tahiti.strftime('%H:%M:%S')} UTC-10")

                if not self._paused:
                    await self._run_cycle()
                else:
                    logger.info("Système en pause — cycle ignoré")

                elapsed = time.time() - cycle_start
                sleep_time = max(0, CYCLE_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("ORACLE v2 arrêt demandé")
        except Exception as e:
            logger.critical(f"Erreur fatale boucle principale: {e}", exc_info=True)
        finally:
            latency_task.cancel()
            health_task.cancel()
            await self._shutdown()

    async def _run_cycle(self):
        """Délègue à CycleManager (conservé pour compatibilité tests)."""
        await self._cycle_manager.run_cycle()

    async def _analyze_symbol(self, symbol: str, poly_opps: list):
        """Délègue à CycleManager (conservé pour compatibilité tests)."""
        await self._cycle_manager.analyze_symbol(symbol, poly_opps)

    # ─── STATUS & SIGNALS ─────────────────────────────────────────────

    def get_active_signals(self) -> list:
        return self._active_signals.copy()

    def get_status(self) -> dict:
        bs = self.brainstem.get_status_dict()
        return {
            "mode": self.mode,
            "running": self._running,
            "paused": self._paused,
            "brainstem": bs,
            "open_positions": len(self._open_positions),
            "active_signals": len(self._active_signals),
        }

    def get_daily_report(self) -> dict:
        """
        Rapport journalier depuis SQLite (TradeRepository) en priorité,
        avec fallback sur _trade_history en mémoire.
        Corrige le bug original : les trades survivent aux redémarrages.
        """
        import time as _time

        if self._trade_repo:
            # Fenêtre 24h glissante depuis SQLite
            cutoff = _time.time() - 86400
            recent = self._trade_repo.get_recent(limit=500)
            trades = [t for t in recent if t.get("ts", 0) >= cutoff]
        else:
            trades = list(self._trade_history)

        if not trades:
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "winrate": 0.0, "pnl_pct": 0.0,
                "best_trade": "+0.00%", "worst_trade": "+0.00%",
                "source": "sqlite" if self._trade_repo else "memory",
            }

        closed = [t for t in trades if t.get("pnl_pct") is not None]
        wins = [t for t in closed if t["pnl_pct"] > 0]
        losses = [t for t in closed if t["pnl_pct"] < 0]
        pnl_values = [t["pnl_pct"] for t in closed]

        return {
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "winrate": len(wins) / len(closed) if closed else 0.0,
            "pnl_pct": sum(pnl_values),
            "avg_pnl_pct": sum(pnl_values) / len(pnl_values) if pnl_values else 0.0,
            "best_trade": f"{max(pnl_values, default=0):+.2%}",
            "worst_trade": f"{min(pnl_values, default=0):+.2%}",
            "source": "sqlite" if self._trade_repo else "memory",
        }

    # ─── CONTRÔLE ─────────────────────────────────────────────────────

    def pause(self):
        self._paused = True
        logger.warning("OracleSystem mis en PAUSE")

    def resume(self):
        self._paused = False
        logger.info("OracleSystem REPRIS")

    async def stop(self):
        self._running = False

    async def _shutdown(self):
        logger.info("ORACLE v2 shutdown...")
        if self.binance:
            await self.binance.close()
        if self.capital:
            await self.capital.close()
        await self.polymarket_strate.close()
        await self.latency_arb.close()
        if self.twitter_strate:
            await self.twitter_strate.close()
        if self.alert_queue:
            self.alert_queue.alert_system("ORACLE v2 arrete.", level="WARNING")
            await self.alert_queue.stop()
        logger.info("ORACLE v2 arrete proprement.")
