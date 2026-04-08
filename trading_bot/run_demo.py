"""
Trading Bot — Lanceur principal.

Modes :
    python run_demo.py                      → SIMULATION (defaut)
    TRADING_MODE=paper python run_demo.py   → PAPER (donnees reelles, ordres simules)
    TRADING_MODE=live  python run_demo.py   → LIVE (ordres reels sur Binance)

Options :
    BINANCE_TESTNET=1  → utilise le testnet Binance (pour tester les ordres reels)
    --backtest         → backtest historique

Arret : Ctrl+C
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    print("ERREUR CRITIQUE : python-dotenv n'est pas installe !")
    print("  -> pip install python-dotenv")
    print("  -> Sans ca, le .env n'est PAS lu et Telegram ne marchera JAMAIS.")
    import sys as _sys
    _sys.exit(1)

# ── Logging coloré ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s \033[36m[%(name)-18s]\033[0m %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("demo")

# ── Imports ───────────────────────────────────────────────────────────────────
from core.message_bus_local  import LocalMessageBus
from core.obsidian_client    import ObsidianClient
from core.learning_engine    import LearningEngine
from core.performance_tracker import PerformanceTracker
from core.message_bus        import CHANNELS
from core.telegram_notifier  import TelegramNotifier
from core.rate_limiter       import create_default_limiter
from core.trading_mode       import TradingModeManager, TradingMode

from agents.scan_agent       import ScanAgent
from agents.research_agent   import ResearchAgent
from agents.predict_agent    import PredictAgent
from agents.risk_agent       import RiskAgent
from agents.execute_agent    import ExecuteAgent
from agents.compound_agent   import CompoundAgent
from agents.synthesis_agent  import SynthesisAgent
from agents.supervisor_agent import SupervisorAgent
# ── Nouveaux agents (spec complète) ──
from agents.regime_agent     import RegimeAgent
from agents.knowledge_agent  import KnowledgeAgent
from agents.shadow_agent     import ShadowAgent
from agents.behavior_agent   import BehaviorAgent
from agents.meta_agent       import MetaAgent

from core.llm_client       import LLMClient
from core.narrative_memory import NarrativeMemory
from core.council          import Council

from data.swarmode_client       import SwarmodeClient
from core.market_data           import MarketDataManager
from core.vault_initializer     import VaultInitializer

# ── Config démo ───────────────────────────────────────────────────────────────
VAULT_PATH = Path(__file__).parent / "vault"

CONFIG = {
    "vault_path":          str(VAULT_PATH),
    "capital_usd":         10_000,
    "risk_per_trade_pct":  1.5,       # Optimise par backtest 90j (meilleur Sharpe)
    "max_drawdown_pct":    18.0,      # Adapte au MaxDD backtest (17.4%)
    "compound_enabled":    True,

    # Exchanges — clés chargées depuis .env
    "exchanges":           ["binance"],
    "binance_api_key":     os.environ.get("BINANCE_API_KEY", ""),
    "binance_secret":      os.environ.get("BINANCE_SECRET", ""),
    "oanda_account":       os.environ.get("OANDA_ACCOUNT", ""),
    "oanda_token":         os.environ.get("OANDA_TOKEN", ""),

    # News
    "cryptopanic_token":   os.environ.get("CRYPTOPANIC_TOKEN", ""),
    "newsapi_key":         os.environ.get("NEWSAPI_KEY", ""),

    # Swarmode (simulation intégrée)
    "swarmode_api_key":    os.environ.get("SWARMODE_API_KEY", ""),
    "swarmode_simulate":   True,

    # Telegram
    "telegram_token":   os.environ.get("TELEGRAM_TOKEN", ""),
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),

    # LLM
    "anthropic_api_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
    "openai_api_key":     os.environ.get("OPENAI_API_KEY", ""),
    "llm_daily_budget":   float(os.environ.get("LLM_DAILY_BUDGET_USD", "10")),

    "pairs":  ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "assets": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
}

INTERVALS = {
    "ScanAgent":        15,    # cycle rapide en démo
    "ResearchAgent":    20,
    "PredictAgent":     5,
    "RiskAgent":        10,
    "ExecuteAgent":     15,
    "CompoundAgent":    60,
    "SynthesisAgent":   45,    # DataSheet toutes les 45s
    "SupervisorAgent":  60,    # supervision toutes les 60s
    # Nouveaux agents
    "RegimeAgent":      30,    # Détection régime toutes les 30s
    "KnowledgeAgent":  120,    # Sauvegarde DB toutes les 2 min
    "ShadowAgent":      60,    # Évaluation shadow toutes les 60s
    "BehaviorAgent":    30,    # Contrôle discipline toutes les 30s
    "MetaAgent":        90,    # CEO cycle toutes les 90s
}


# ── Checks de securite au demarrage ───────────────────────────────────────────

def check_dependencies() -> list[str]:
    """Verifie que toutes les dependances critiques sont installees."""
    issues = []
    required = {
        "httpx":      "pip install httpx",
        "yaml":       "pip install pyyaml",
        "numpy":      "pip install numpy",
        "pandas":     "pip install pandas",
        "websockets": "pip install websockets",
    }
    for mod, fix in required.items():
        try:
            __import__(mod)
        except ImportError:
            issues.append(f"Module '{mod}' manquant — {fix}")

    # ccxt est requis pour paper/live
    mode = os.environ.get("TRADING_MODE", "simulation")
    if mode in ("paper", "live"):
        try:
            __import__("ccxt")
        except ImportError:
            issues.append("Module 'ccxt' manquant (requis pour paper/live) — pip install ccxt")

    return issues


def check_env_vars(mode: str) -> list[str]:
    """Verifie les variables d'environnement selon le mode."""
    issues = []

    # Telegram : toujours verifier
    if not os.environ.get("TELEGRAM_TOKEN"):
        issues.append("TELEGRAM_TOKEN vide dans .env — pas de notifications Telegram")
    if not os.environ.get("TELEGRAM_CHAT_ID"):
        issues.append("TELEGRAM_CHAT_ID vide dans .env — pas de notifications Telegram")

    # Binance : requis pour paper/live
    if mode in ("paper", "live"):
        if not os.environ.get("BINANCE_API_KEY"):
            issues.append("BINANCE_API_KEY vide — requis pour le mode " + mode.upper())
        if not os.environ.get("BINANCE_SECRET"):
            issues.append("BINANCE_SECRET vide — requis pour le mode " + mode.upper())

    return issues


def startup_checks() -> None:
    """Checks complets au demarrage. Crash si critique."""
    mode = os.environ.get("TRADING_MODE", "simulation")

    print(f"\n{'=' * 60}")
    print(f"  CHECKS DE DEMARRAGE — Mode {mode.upper()}")
    print(f"{'=' * 60}")

    all_ok = True

    # 1. Dependances
    dep_issues = check_dependencies()
    if dep_issues:
        for issue in dep_issues:
            print(f"  FAIL  {issue}")
        all_ok = False
    else:
        print(f"  OK    Toutes les dependances installees")

    # 2. Variables d'environnement
    env_issues = check_env_vars(mode)
    warnings = []
    criticals = []
    for issue in env_issues:
        if "TELEGRAM" in issue:
            warnings.append(issue)
        else:
            criticals.append(issue)

    for w in warnings:
        print(f"  WARN  {w}")
    for c in criticals:
        print(f"  FAIL  {c}")
        all_ok = False

    if not env_issues:
        print(f"  OK    Variables d'environnement configurees")

    # 3. Mode LIVE — avertissement supplementaire
    if mode == "live":
        testnet = os.environ.get("BINANCE_TESTNET", "0") in ("1", "true", "True")
        if not testnet:
            print(f"\n  {'!' * 50}")
            print(f"  !!!  MODE LIVE — ARGENT REEL — PAS DE TESTNET  !!!")
            print(f"  {'!' * 50}")

    print(f"{'=' * 60}\n")

    # Crash si erreur critique en paper/live
    if not all_ok and mode in ("paper", "live"):
        print("ERREUR: Checks critiques echoues — impossible de demarrer en mode", mode.upper())
        sys.exit(1)


# ── Injection Swarmode dans ResearchAgent ─────────────────────────────────────

async def _inject_swarmode_once(bus: LocalMessageBus, swarmode: SwarmodeClient):
    """Un tour de collecte Swarmode pour tous les assets."""
    for asset in CONFIG["assets"]:
        sig = await swarmode.get_signal(asset)
        logger.info(
            "\033[35m[Swarmode]\033[0m %s → %s (%d/100) | 1h:%.2f%% | régime:%s",
            asset, sig["direction"], sig["confidence"],
            sig["forecast_1h"], sig["regime"],
        )
        await bus.publish(CHANNELS["signals_fundamental"], {
            "type":            "fundamental_signal",
            "asset":           asset,
            "signal":          sig["direction"],
            "sentiment_score": sig["score"],
            "confidence":      sig["confidence"],
            "news_count":      1,
            "key_events":      [
                f"[Swarmode] Prévision 1h: {sig['forecast_1h']:+.2f}% | "
                f"24h: {sig['forecast_24h']:+.2f}% | Régime: {sig['regime']}"
            ],
            "source":          sig["source"],
        })


async def inject_swarmode_signals(bus: LocalMessageBus, swarmode: SwarmodeClient):
    """
    Tâche résiliente : relance automatiquement en cas d'erreur.
    Publie les signaux Swarmode sur signals:fundamental pour PredictAgent.
    """
    while True:
        try:
            await _inject_swarmode_once(bus, swarmode)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("\033[35m[Swarmode]\033[0m Erreur (relance dans 5s): %s", exc)
            await asyncio.sleep(5)
            continue
        await asyncio.sleep(30)


async def _watchdog(agents: list, tracker, telegram) -> None:
    """
    Publie un heartbeat logs toutes les 60s.
    Envoie un résumé Telegram toutes les 10 min.
    Redémarre les agents morts automatiquement.
    Vérifie la santé de Telegram.
    """
    iteration = 0
    while True:
        await asyncio.sleep(60)
        iteration += 1
        alive = [a.name for a in agents if a.is_running]
        dead  = [a.name for a in agents if not a.is_running]

        if dead:
            logger.error("💀 [Watchdog] Agents morts: %s — tentative de redémarrage", dead)
            for agent in agents:
                if not agent.is_running:
                    try:
                        await agent.start()
                        logger.info("🔄 [Watchdog] %s redémarré avec succès", agent.name)
                    except Exception as exc:
                        logger.error("❌ [Watchdog] Échec redémarrage %s: %s", agent.name, exc)
        else:
            logger.info("💓 [Watchdog] Tous actifs (%d agents) | itération #%d", len(alive), iteration)

        # Vérifier la santé de Telegram
        if telegram and not telegram.is_healthy():
            logger.warning("⚠️ [Watchdog] Telegram non-responsive — recréation du client")
            try:
                await telegram._recreate_http_client()
            except Exception as exc:
                logger.error("[Watchdog] Échec recréation client Telegram: %s", exc)

        # Résumé Telegram toutes les 10 min (10 itérations × 60s)
        if iteration % 10 == 0 and telegram:
            try:
                snap = tracker.snapshot()
                await telegram.performance_summary(
                    capital       = snap["capital"],
                    pnl_pct       = snap["total_return_pct"],
                    win_rate      = snap["win_rate"],
                    sharpe        = snap["sharpe_ratio"],
                    drawdown      = snap["max_drawdown_pct"],
                    total_trades  = snap["total_trades"],
                )
            except Exception as exc:
                logger.debug("[Watchdog] Erreur résumé Telegram: %s", exc)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    # ── Checks de securite ──
    startup_checks()

    mode = os.environ.get("TRADING_MODE", "simulation").upper()
    use_testnet = os.environ.get("BINANCE_TESTNET", "0") in ("1", "true", "True")
    CONFIG["binance_testnet"] = use_testnet

    print("\n" + "=" * 70)
    print(f"  AI TRADING COMPANY — MODE {mode}" + (" (TESTNET)" if use_testnet else ""))
    print("  Pipeline : Scan > Research > Predict > Risk > Execute > Compound")
    print("  13 agents : + RegimeAgent | KnowledgeAgent | ShadowAgent")
    print("              + BehaviorAgent | MetaAgent (CEO) | SupervisorAgent")
    print("=" * 70 + "\n")

    bus      = LocalMessageBus()
    obsidian = ObsidianClient(CONFIG["vault_path"])
    learning = LearningEngine(obsidian, CONFIG)
    tracker  = PerformanceTracker(obsidian, CONFIG["capital_usd"])
    swarmode = SwarmodeClient(simulate=True)

    # ── Initialiser la structure complète du vault ────────────────────────────
    vault_init = VaultInitializer(VAULT_PATH)
    vault_init.initialize()
    logger.info("✅  Vault initialisé : 13 dossiers + pages agents wikilinked")

    # ── LLM Intelligence ─────────────────────────────────────────────────────
    llm_client = LLMClient(
        anthropic_key    = CONFIG.get("anthropic_api_key", ""),
        openai_key       = CONFIG.get("openai_api_key", ""),
        daily_budget_usd = CONFIG.get("llm_daily_budget", 10.0),
    )
    narrative_memory = NarrativeMemory(vault_path=VAULT_PATH)
    council = Council(
        llm=llm_client,
        narrative_memory=narrative_memory,
        vault_path=VAULT_PATH,
    )
    daily_thesis_ref: list = []

    logger.info(
        "🧠 LLM Council actif | Budget: $%.1f/jour | Patterns mémorisés: %d",
        CONFIG.get("llm_daily_budget", 10.0),
        len(narrative_memory._patterns),
    )

    # ── Rate Limiter (Binance + Telegram) ──
    rate_limiter = create_default_limiter()

    telegram = TelegramNotifier(
        CONFIG["telegram_token"], CONFIG["telegram_chat_id"],
        rate_limiter=rate_limiter,
    )

    # ── Trading Mode (simulation par défaut) ──
    trading_mode = TradingModeManager(
        vault_path=VAULT_PATH,
        mode=os.environ.get("TRADING_MODE", "simulation"),
    )
    issues = trading_mode.validate_config(CONFIG)
    if issues:
        for issue in issues:
            logger.warning("[TradingMode] ⚠️  %s", issue)
    logger.info(
        "[TradingMode] Mode : %s | Données réelles : %s | Ordres réels : %s",
        trading_mode.mode.value, trading_mode.use_real_data, trading_mode.execute_real_orders,
    )

    # ── MarketDataManager : WebSocket + REST Binance ──
    # Démarre en parallèle — les agents utilisent is_ready() avant d'y accéder
    market_data = MarketDataManager(
        pairs         = CONFIG["pairs"],
        ws_timeframes = ["1m", "1h"],
        rate_limiter  = rate_limiter,
    )
    await market_data.start()

    await bus.connect()
    await swarmode.connect()

    def cfg(name: str) -> dict:
        return {**CONFIG, "cycle_interval_seconds": INTERVALS[name]}

    # ── Instanciation des agents core ────────────────────────────────────────
    scan_agent     = ScanAgent(      bus, obsidian, learning,                   cfg("ScanAgent"),     market_data=market_data, llm=llm_client)
    research_agent = ResearchAgent(  bus, obsidian, learning,                   cfg("ResearchAgent"))
    predict_agent  = PredictAgent(   bus, obsidian, learning,          telegram, cfg("PredictAgent"))
    risk_agent     = RiskAgent(      bus, obsidian, learning, tracker, telegram, cfg("RiskAgent"), council=council,
                           daily_thesis_ref=daily_thesis_ref)
    execute_agent  = ExecuteAgent(   bus, obsidian,                    telegram, cfg("ExecuteAgent"),  market_data=market_data, trading_mode=trading_mode)
    compound_agent = CompoundAgent(  bus, obsidian, learning, tracker,          cfg("CompoundAgent"),  telegram=telegram)
    synthesis_agent= SynthesisAgent( bus, obsidian, learning,                   cfg("SynthesisAgent"), market_data=market_data, telegram=telegram)

    # ── Nouveaux agents ───────────────────────────────────────────────────────
    regime_agent    = RegimeAgent(   bus, obsidian, cfg("RegimeAgent"),    market_data=market_data, telegram=telegram)
    knowledge_agent = KnowledgeAgent(bus, obsidian, cfg("KnowledgeAgent"), telegram=telegram)
    shadow_agent    = ShadowAgent(   bus, obsidian, cfg("ShadowAgent"),    telegram=telegram)
    behavior_agent  = BehaviorAgent( bus, obsidian, cfg("BehaviorAgent"),  telegram=telegram)
    meta_agent      = MetaAgent(     bus, obsidian, tracker, cfg("MetaAgent"), telegram=telegram, llm=llm_client,
                           narrative_memory=narrative_memory)

    # ── SupervisorAgent : monitoring opérationnel ──────────────────────────
    all_core = [
        scan_agent, research_agent, predict_agent, risk_agent,
        execute_agent, compound_agent, synthesis_agent,
        regime_agent, knowledge_agent, shadow_agent, behavior_agent, meta_agent,
    ]
    supervisor = SupervisorAgent(
        bus=bus, obsidian=obsidian,
        agents=[a.name for a in all_core],
        tracker=tracker, telegram=telegram,
        config=cfg("SupervisorAgent"),
    )

    agents = all_core + [supervisor]

    # ── Connecter Telegram au PerformanceTracker + agents pour commandes live ──
    telegram.set_tracker(tracker)
    telegram.set_risk_agent(risk_agent)
    telegram.set_compound_agent(compound_agent)

    results = await asyncio.gather(*[a.start() for a in agents], return_exceptions=True)
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            logger.error("❌ Échec démarrage %s: %s", agent.name, result)

    # Vérifier la connexion Telegram AVANT tout le reste
    tg_ok = await telegram.verify_connection()
    if not tg_ok:
        logger.error("=" * 50)
        logger.error("  TELEGRAM NON FONCTIONNEL")
        logger.error("  Verifier TELEGRAM_TOKEN et TELEGRAM_CHAT_ID dans .env")
        logger.error("=" * 50)
    else:
        logger.info("[Telegram] Connexion verifiee — demarrage du polling")

    # Démarrer le polling des commandes Telegram
    await telegram.start_polling()

    logger.info("✅  13 agents démarrés | Vault : %s", VAULT_PATH)
    logger.info("🏢  Agents : ScanAgent | ResearchAgent | PredictAgent | RiskAgent")
    logger.info("🏢          ExecuteAgent | CompoundAgent | SynthesisAgent | SupervisorAgent")
    logger.info("🆕  Nouveaux : RegimeAgent | KnowledgeAgent | ShadowAgent | BehaviorAgent | MetaAgent")
    logger.info("🧠  LLM Council : GPT-4o (analysts) + Claude Sonnet (arbitre) + Claude Opus (CEO)")
    logger.info("📓  Vault LLM : /briefing/ /council/ /postmortems/ /memory/ /llm_logs/")
    logger.info("📊  Vault Obsidian : /agents/ /patterns/ /market_conditions/ /reports/ /experiments/")
    logger.info("📱  Telegram : commandes /status /pnl /positions /risk /memory")
    logger.info("⚠️   Ctrl+C pour arrêter proprement\n")

    # Message Telegram de démarrage
    await telegram.bot_started(
        agents=[a.name for a in agents], mode="simulation"
    )

    # ── Démarrer le bus (consume tasks pour distribuer les messages aux handlers) ──
    bus_task = asyncio.create_task(bus.listen(), name="bus_listen")

    # Tâches parallèles : Swarmode + Watchdog
    swarmode_task = asyncio.create_task(
        inject_swarmode_signals(bus, swarmode), name="swarmode"
    )
    watchdog_task = asyncio.create_task(
        _watchdog(agents, tracker, telegram), name="watchdog"
    )

    try:
        # Maintenir le processus en vie
        await asyncio.gather(bus_task, swarmode_task, watchdog_task)
    except asyncio.CancelledError:
        pass
    finally:
        bus_task.cancel()
        swarmode_task.cancel()
        watchdog_task.cancel()
        await asyncio.gather(bus_task, swarmode_task, watchdog_task, return_exceptions=True)
        await telegram.stop_polling()
        for a in agents:
            await a.stop()
        await market_data.stop()
        await swarmode.disconnect()
        await bus.disconnect()
        print("\n🛑  Bot arrêté proprement. Vault Obsidian mis à jour.")


async def run_backtest_cli():
    """
    Lance un backtest sur données historiques Binance.
    Usage : python run_demo.py --backtest [--days 90] [--pairs BTC/USDT,ETH/USDT]
    """
    import argparse
    parser = argparse.ArgumentParser(description="Backtest historique")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--days", type=int, default=90, help="Jours d'historique")
    parser.add_argument("--pairs", type=str, default="BTC/USDT,ETH/USDT,SOL/USDT",
                        help="Paires séparées par des virgules")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    args = parser.parse_args()

    if not args.backtest:
        return False  # pas de backtest demandé

    from core.backtester import Backtester
    from core.learning_engine import LearningEngine

    pairs = [p.strip() for p in args.pairs.split(",")]
    obsidian = ObsidianClient(CONFIG["vault_path"])
    learning = LearningEngine(obsidian, CONFIG)

    # Charger les poids adaptatifs depuis la mémoire
    mem = learning.load_memory("ScanAgent")
    weights = {
        "w_rsi":  mem.indicator_weights.get(f"rsi:{args.timeframe}:{pairs[0]}", 1.0),
        "w_macd": mem.indicator_weights.get(f"macd:{args.timeframe}:{pairs[0]}", 1.0),
        "w_bb":   mem.indicator_weights.get(f"bb:{args.timeframe}:{pairs[0]}", 1.0),
        "w_vol":  1.0,
    }

    sl_mult  = mem.adaptive_params.get("sl_atr_multiplier", 1.5)
    tp_ratio = mem.adaptive_params.get("tp_rr_ratio", 2.5)

    bt = Backtester(
        initial_capital=CONFIG["capital_usd"],
        risk_pct=CONFIG["risk_per_trade_pct"],
        sl_atr_mult=sl_mult,
        tp_rr_ratio=tp_ratio,
        min_confidence=35,
        indicator_weights=weights,
    )

    print(f"\n{'═'*65}")
    print(f"  BACKTEST — {', '.join(pairs)} | {args.timeframe} | {args.days}j")
    print(f"  Poids ML : RSI={weights['w_rsi']:.2f} MACD={weights['w_macd']:.2f} BB={weights['w_bb']:.2f}")
    print(f"  SL={sl_mult:.2f}×ATR | TP=1:{tp_ratio:.2f}")
    print(f"{'═'*65}\n")

    # Récupérer les données
    data = {}
    for pair in pairs:
        try:
            df = await Backtester.fetch_historical_data(
                symbol=pair, timeframe=args.timeframe, days=args.days,
            )
            data[pair] = df
            print(f"  ✅ {pair} : {len(df)} candles")
        except Exception as exc:
            from core.backtester import _generate_simulated_data
            df = _generate_simulated_data(pair, args.timeframe, args.days)
            data[pair] = df
            print(f"  ⚠️  {pair} : {len(df)} candles (simulées — {exc})")

    # Lancer le backtest
    result = await bt.run(data=data, timeframe=args.timeframe)
    print(f"\n{result.summary()}")

    # Écrire le rapport dans le vault
    report_path = Backtester.write_obsidian_report(result, VAULT_PATH)
    print(f"\n📊 Rapport Obsidian : {report_path}")
    return True


if __name__ == "__main__":
    # Vérifier si mode backtest
    if "--backtest" in sys.argv:
        asyncio.run(run_backtest_cli())
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n👋 Arrêt demandé par l'utilisateur.")