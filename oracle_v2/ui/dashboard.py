"""
Dashboard Terminal ORACLE v2
UI riche en CMD avec Textual — thème cyberpunk neural
"""
from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, DataTable, Label,
    Log, TabbedContent, TabPane
)
from textual.containers import Grid, Horizontal
from textual import work
from datetime import datetime


ORACLE_ASCII = r"""
 ██████╗ ██████╗  █████╗  ██████╗██╗     ███████╗    ██╗   ██╗██████╗
██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝    ██║   ██║╚════██╗
██║   ██║██████╔╝███████║██║     ██║     █████╗      ██║   ██║ █████╔╝
██║   ██║██╔══██╗██╔══██║██║     ██║     ██╔══╝      ╚██╗ ██╔╝██╔═══╝
╚██████╔╝██║  ██║██║  ██║╚██████╗███████╗███████╗     ╚████╔╝ ███████╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝      ╚═══╝  ╚══════╝
"""


class BrainstemWidget(Static):
    def compose(self) -> ComposeResult:
        yield Label("🧠 BRAINSTEM", id="brainstem-title")
        yield Static("", id="brainstem-status")
        yield Static("", id="brainstem-metrics")

    def update_state(self, state: dict):
        alive = state.get("alive", False)
        status = self.query_one("#brainstem-status", Static)
        metrics = self.query_one("#brainstem-metrics", Static)
        status_color = "green" if alive else "red"
        status_text = f"[bold {status_color}]{'● ALIVE' if alive else '● BLOCKED'}[/]"
        if not alive:
            status_text += f"\n[dim]{state.get('reason', '')}[/]"
        status.update(status_text)
        metrics.update(
            f"Pertes consec : [yellow]{state.get('consecutive_losses', 0)}[/]\n"
            f"PnL jour      : {state.get('daily_pnl', '0.00%')}\n"
            f"Trades session: [cyan]{state.get('session_trades', 0)}[/]\n"
            f"Cooling       : [{'red' if state.get('cooling') else 'green'}]"
            f"{'OUI ⏸️' if state.get('cooling') else 'NON'}[/]"
        )


class ParliamentWidget(Static):
    def compose(self) -> ComposeResult:
        yield Label("🏛️ PARLEMENT", id="parliament-title")
        yield Static("", id="parliament-direction")
        yield Static("", id="parliament-votes")

    def update_decision(self, decision):
        if not decision:
            return
        direction_widget = self.query_one("#parliament-direction", Static)
        votes_widget = self.query_one("#parliament-votes", Static)
        color_map = {"LONG": "green", "SHORT": "red", "NEUTRAL": "yellow"}
        color = color_map.get(decision.direction, "white")
        direction_widget.update(
            f"[bold {color}]{decision.direction}[/] — Force: [bold]{decision.strength:.0%}[/]\n"
            f"Polymarket: [{'green' if decision.polymarket_alignment else 'red'}]"
            f"{'ALIGNÉ ✓' if decision.polymarket_alignment else 'DIVERGENT ✗'}[/]"
        )
        votes_text = ""
        for v in decision.votes[:4]:
            c = color_map.get(v.direction, "white")
            votes_text += f"[{c}]▸[/] {v.strate_name:<15} {v.confidence:.0%}\n"
        votes_widget.update(votes_text)


class PolymarketWidget(Static):
    def compose(self) -> ComposeResult:
        yield Label("🎯 POLYMARKET", id="poly-title")
        yield DataTable(id="poly-table")

    def on_mount(self):
        table = self.query_one("#poly-table", DataTable)
        table.add_columns("Asset", "Dir", "Edge", "Kelly", "Conf", "Question")

    def update_opportunities(self, opportunities: list):
        table = self.query_one("#poly-table", DataTable)
        table.clear()
        for opp in opportunities[:8]:
            edge_color = "green" if opp.edge > 0 else "red"
            conf_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "white"}.get(opp.confidence, "white")
            table.add_row(
                opp.correlated_asset,
                f"{'YES 📈' if opp.direction == 'YES' else 'NO 📉'}",
                f"[{edge_color}]{opp.edge:+.1%}[/]",
                f"{opp.kelly_fraction:.1%}",
                f"[{conf_color}]{opp.confidence}[/]",
                opp.question[:40] + "..."
            )


class SignalsWidget(Static):
    def compose(self) -> ComposeResult:
        yield Label("📡 SIGNAUX ACTIFS", id="signals-title")
        yield DataTable(id="signals-table")

    def on_mount(self):
        table = self.query_one("#signals-table", DataTable)
        table.add_columns("Symbol", "Direction", "Conf", "TF", "Strate")

    def update_signals(self, signals: list):
        table = self.query_one("#signals-table", DataTable)
        table.clear()
        for sig in signals:
            dir_color = "green" if sig.get("direction") == "LONG" else "red"
            table.add_row(
                sig.get("symbol", ""),
                f"[bold {dir_color}]{sig.get('direction', '')}[/]",
                f"{sig.get('confidence', 0):.0%}",
                sig.get("timeframe", "5m"),
                sig.get("source", "")
            )


class OracleLogWidget(Log):
    pass


class OracleDashboard(App):
    CSS = """
    Screen { background: #0a0e1a; }
    Header { background: #0d1b2a; color: #00d4ff; text-style: bold; }
    Footer { background: #0d1b2a; color: #4a9eff; }
    #ascii-banner { color: #00d4ff; text-style: bold; text-align: center; padding: 0 1; }
    #main-grid {
        grid-size: 3 2; grid-rows: 1fr 1fr;
        grid-columns: 1fr 1fr 2fr; height: 1fr; padding: 1; grid-gutter: 1;
    }
    BrainstemWidget { background: #0d1b2a; border: solid #1e3a5f; padding: 1 2; height: 100%; }
    ParliamentWidget { background: #0d1b2a; border: solid #1e3a5f; padding: 1 2; height: 100%; }
    PolymarketWidget { background: #0d1b2a; border: solid #1e3a5f; padding: 1; row-span: 2; height: 100%; }
    SignalsWidget { background: #0d1b2a; border: solid #1e3a5f; padding: 1; height: 100%; }
    OracleLogWidget { background: #060d1a; border: solid #1a2a3a; padding: 1; height: 100%; }
    #brainstem-title, #parliament-title, #poly-title, #signals-title {
        color: #4a9eff; text-style: bold; padding-bottom: 1;
    }
    DataTable { background: #060d1a; border: none; }
    DataTable > .datatable--header { background: #0d1b2a; color: #4a9eff; text-style: bold; }
    #bottom-bar { height: 3; background: #0d1b2a; border-top: solid #1e3a5f; padding: 0 2; color: #4a9eff; }
    Label { color: #4a9eff; }
    """

    TITLE = "ORACLE v2 — Neural Trading System"
    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("r", "refresh", "Refresh"),
        ("p", "toggle_pause", "Pause/Resume"),
        ("l", "toggle_log", "Logs"),
    ]

    def __init__(self, oracle_system=None):
        super().__init__()
        self.oracle = oracle_system
        self._paused = False

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("🧠 Dashboard", id="tab-dashboard"):
                yield Static(ORACLE_ASCII, id="ascii-banner")
                with Grid(id="main-grid"):
                    yield BrainstemWidget(id="brainstem")
                    yield ParliamentWidget(id="parliament")
                    yield PolymarketWidget(id="polymarket")
                    yield SignalsWidget(id="signals")
                    yield OracleLogWidget(id="oracle-log", highlight=True, markup=True)
            with TabPane("📊 Trades", id="tab-trades"):
                yield DataTable(id="trades-table")
            with TabPane("📡 Logs", id="tab-logs"):
                yield OracleLogWidget(id="full-log", highlight=True, markup=True)
        with Horizontal(id="bottom-bar"):
            yield Static("", id="status-bar")
            yield Static("UTC-10 (Tahiti)", id="timezone-bar")
        yield Footer()

    def on_mount(self):
        trades_table = self.query_one("#trades-table", DataTable)
        trades_table.add_columns("Heure", "Symbol", "Direction", "Size", "PnL", "Strate", "Parlement")
        self.set_interval(5, self.refresh_dashboard)
        self.set_interval(30, self.refresh_polymarket)

    @work(exclusive=True)
    async def refresh_dashboard(self):
        if not self.oracle:
            return
        try:
            self.query_one("#brainstem", BrainstemWidget).update_state(
                self.oracle.brainstem.get_status_dict()
            )
            if self.oracle.last_parliament_decision:
                self.query_one("#parliament", ParliamentWidget).update_decision(
                    self.oracle.last_parliament_decision
                )
            self.query_one("#signals", SignalsWidget).update_signals(
                self.oracle.get_active_signals()
            )
            now = datetime.now().strftime("%H:%M:%S")
            paused = " ⏸️ PAUSED" if self._paused else ""
            mode = self.oracle.get_status().get("mode", "UNKNOWN")
            self.query_one("#status-bar", Static).update(
                f"[cyan]{now}[/] | Mode: [bold]{mode}[/]{paused}"
            )
        except Exception as e:
            self.query_one("#oracle-log", OracleLogWidget).write_line(
                f"[red]Dashboard refresh error: {e}[/]"
            )

    @work(exclusive=True)
    async def refresh_polymarket(self):
        if not self.oracle:
            return
        try:
            opportunities = await self.oracle.polymarket_strate.scan()
            self.query_one("#polymarket", PolymarketWidget).update_opportunities(opportunities)
        except Exception:
            pass

    def log_event(self, message: str, level: str = "INFO"):
        color_map = {
            "INFO": "white", "SUCCESS": "green",
            "WARNING": "yellow", "ERROR": "red",
            "TRADE": "cyan", "POLYMARKET": "magenta"
        }
        color = color_map.get(level, "white")
        now = datetime.now().strftime("%H:%M:%S")
        self.query_one("#oracle-log", OracleLogWidget).write_line(
            f"[dim]{now}[/] [{color}]{level:<10}[/] {message}"
        )

    def action_toggle_pause(self):
        if self.oracle:
            if self._paused:
                self.oracle.resume()
                self._paused = False
                self.log_event("Trading REPRIS", "SUCCESS")
            else:
                self.oracle.pause()
                self._paused = True
                self.log_event("Trading EN PAUSE", "WARNING")

    def action_refresh(self):
        self.refresh_dashboard()
        self.refresh_polymarket()

    def action_toggle_log(self):
        pass
