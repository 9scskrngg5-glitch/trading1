"""
ORACLE v2 — Entry Point
Usage:
  python main.py --mode paper          # Paper trading avec dashboard
  python main.py --mode live           # Live trading (confirmation requise)
  python main.py --dashboard           # Dashboard seul (monitoring)
  python main.py --polymarket          # Scan Polymarket seul
"""
import asyncio
import argparse
import logging
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Force UTF-8 output on Windows to support Unicode log messages
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import config


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    try:
        from rich.logging import RichHandler
        logging.basicConfig(
            level=level,
            format="%(message)s",
            handlers=[RichHandler(rich_tracebacks=True, markup=True, show_path=False)]
        )
    except ImportError:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
        )


async def run_polymarket_scan():
    """Scan Polymarket standalone avec affichage rich."""
    from strates.polymarket_strate import PolymarketStrate
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
    except ImportError:
        print("Install rich: pip install rich")
        return

    console.print("\n[bold cyan]ORACLE v2 -- Polymarket Scanner[/]\n")
    strate = PolymarketStrate(
        min_edge=config.POLYMARKET_MIN_EDGE,
        min_volume=config.POLYMARKET_MIN_VOLUME
    )

    with console.status("[bold green]Scanning Polymarket..."):
        opportunities = await strate.scan()

    if not opportunities:
        console.print("[red]No opportunities found.[/]")
        await strate.close()
        return

    table = Table(title=f"Top Opportunities ({len(opportunities)} found)")
    table.add_column("Asset", style="cyan", no_wrap=True)
    table.add_column("Direction", style="bold")
    table.add_column("Edge", style="bold")
    table.add_column("Kelly", style="yellow")
    table.add_column("Confidence", style="bold")
    table.add_column("Volume 24h", style="dim")
    table.add_column("Question", style="dim")

    for opp in opportunities[:15]:
        edge_color = "green" if opp.edge > 0 else "red"
        conf_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "white"}.get(opp.confidence, "white")
        table.add_row(
            opp.correlated_asset,
            f"{'YES' if opp.direction == 'YES' else 'NO'}",
            f"[{edge_color}]{opp.edge:+.1%}[/]",
            f"{opp.kelly_fraction:.1%}",
            f"[{conf_color}]{opp.confidence}[/]",
            f"${opp.volume_24h:,.0f}",
            opp.question[:50] + "..."
        )

    console.print(table)
    await strate.close()


async def run_btc_latency_scan():
    """BTC Polymarket latency arbitrage scanner — standalone."""
    from strates.latency_arb_strate import BtcLatencyArbStrate
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
    except ImportError:
        print("Install rich: pip install rich")
        return

    console.print("\n[bold yellow]ORACLE v2 -- BTC Latency Arbitrage Scanner[/]\n")
    strate = BtcLatencyArbStrate(
        min_edge=config.BTC_LATENCY_ARB_MIN_EDGE,
        min_volume=config.BTC_LATENCY_ARB_MIN_VOLUME,
        sigma=config.BTC_SIGMA_ANNUAL,
    )

    with console.status("[bold green]Fetching BTC price + Polymarket markets..."):
        signals = await strate.scan()

    btc_price = strate.last_btc_price
    console.print(f"[cyan]BTC spot: ${btc_price:,.0f}[/]")

    if not signals:
        console.print("[red]No latency signals found (min_edge threshold not met).[/]")
        await strate.close()
        return

    table = Table(title=f"BTC Latency Arb ({len(signals)} signals)")
    table.add_column("Direction", style="bold")
    table.add_column("Edge", style="bold")
    table.add_column("Fair", style="cyan")
    table.add_column("Market", style="dim")
    table.add_column("Kelly", style="yellow")
    table.add_column("DTE", style="dim")
    table.add_column("Confidence")
    table.add_column("Question", style="dim")

    for s in signals[:12]:
        edge_color = "green" if s.edge > 0 else "red"
        dir_color = "green" if s.trade_direction == "LONG" else "red"
        table.add_row(
            f"[{dir_color}]{s.trade_direction}[/]",
            f"[{edge_color}]{s.edge:+.1%}[/]",
            f"{s.fair_value:.2%}",
            f"{s.current_market_price:.2%}",
            f"{s.kelly_fraction:.1%}",
            f"{s.days_to_expiry:.1f}d",
            s.confidence,
            s.question[:48] + "..."
        )
    console.print(table)

    vote = strate.generate_parliament_vote(signals)
    conf_color = "green" if vote.direction == "LONG" else "red"
    console.print(
        f"\n[bold]Parliament vote:[/] [{conf_color}]{vote.direction}[/] "
        f"conf={vote.confidence:.0%} | {vote.reasoning}"
    )
    await strate.close()


async def run_chat():
    """Mode conversationnel interactif avec Oracle."""
    from brain.narrator import OracleNarrator
    try:
        from rich.console import Console
        console = Console()
        has_rich = True
    except ImportError:
        has_rich = False

    narrator = OracleNarrator(
        api_key=config.ANTHROPIC_API_KEY,
        use_llm=config.NARRATOR_LLM,
    )

    if has_rich:
        console.print("\n[bold cyan]ORACLE v2 -- Mode conversationnel[/]")
        console.print("[dim]Tapez votre question. 'exit' pour quitter. 'memoire' pour voir l'historique.[/]\n")
        if not config.ANTHROPIC_API_KEY:
            console.print("[yellow]Conseil: definissez ANTHROPIC_API_KEY pour la conversation riche.[/]\n")
    else:
        print("ORACLE v2 -- Chat (exit pour quitter)")

    # Initiation Oracle
    narrator.session_start("chat", config.TRADING_PAIRS)

    while True:
        try:
            question = input("Vous: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            break
        if question.lower() == "memoire":
            mem = narrator.get_memory_summary()
            if has_rich:
                console.print(f"[dim]{mem}[/]")
            else:
                print(mem)
            continue

        reponse = await narrator.chat(question)
        if has_rich:
            console.print(f"[bold green]Oracle:[/] {reponse}\n")
        else:
            print(f"Oracle: {reponse}\n")

    print("Session terminee.")


def run_dashboard_only():
    """Lance uniquement le dashboard en mode monitoring."""
    from ui.dashboard import OracleDashboard
    app = OracleDashboard(oracle_system=None)
    app.run()


def main():
    parser = argparse.ArgumentParser(
        description="ORACLE v2 — Neural Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python main.py --polymarket           # Scan Polymarket general
  python main.py --btc-arb              # BTC latency arbitrage scan
  python main.py --dashboard            # Dashboard monitoring
  python main.py --mode paper           # Paper trading complet
  python main.py --mode live            # Live (confirmation requise)
        """
    )
    parser.add_argument("--mode", choices=["paper", "live", "backtest"],
                        help="Mode de trading")
    parser.add_argument("--dashboard", action="store_true",
                        help="Lance uniquement le dashboard")
    parser.add_argument("--polymarket", action="store_true",
                        help="Scan Polymarket seul")
    parser.add_argument("--btc-arb", action="store_true",
                        help="BTC latency arbitrage scanner")
    parser.add_argument("--chat", action="store_true",
                        help="Chat interactif avec Oracle")
    parser.add_argument("--pairs", nargs="+",
                        help="Paires a trader (ex: BTCUSDT ETHUSDT)")
    parser.add_argument("--verbose", action="store_true",
                        help="Logs détaillés")

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("ORACLE.Main")

    if args.pairs:
        config.TRADING_PAIRS = args.pairs

    # ─── MODE POLYMARKET SCAN ─────────────────────────────────────────
    if args.polymarket:
        asyncio.run(run_polymarket_scan())
        return

    # ─── MODE BTC LATENCY ARB ─────────────────────────────────────────
    if getattr(args, "btc_arb", False):
        asyncio.run(run_btc_latency_scan())
        return

    # ─── MODE CHAT ────────────────────────────────────────────────────
    if getattr(args, "chat", False):
        asyncio.run(run_chat())
        return

    # ─── MODE DASHBOARD ONLY ──────────────────────────────────────────
    if args.dashboard:
        run_dashboard_only()
        return

    # ─── MODE TRADING ─────────────────────────────────────────────────
    if args.mode == "live":
        confirm = input(
            "\n⚠️  MODE LIVE ACTIVÉ — Cela utilisera de vrais fonds.\n"
            "Tapez 'ORACLE_LIVE_CONFIRM' pour confirmer : "
        )
        if confirm != "ORACLE_LIVE_CONFIRM":
            print("Annulé.")
            return
        config.MODE = "live"

    if args.mode in ["paper", "live"]:
        logger.info(f"ORACLE v2 démarrage — Mode: {args.mode.upper()}")
        logger.info(f"Paires: {config.TRADING_PAIRS}")
        logger.info(f"Timezone: {config.TIMEZONE}")
        from oracle_system import OracleSystem
        system = OracleSystem(config)
        asyncio.run(system.run())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
