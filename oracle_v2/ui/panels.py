"""
Panels — Composants individuels réutilisables pour le dashboard ORACLE v2.
"""
from textual.widgets import Static, DataTable, Label
from textual.app import ComposeResult
from datetime import datetime


class PnLPanel(Static):
    """Panel PnL en temps réel avec indicateur coloré."""

    def compose(self) -> ComposeResult:
        yield Label("💰 PnL SESSION", id="pnl-title")
        yield Static("", id="pnl-value")
        yield Static("", id="pnl-details")

    def update_pnl(self, daily_pnl: float, session_trades: int, wins: int, losses: int):
        pnl_widget = self.query_one("#pnl-value", Static)
        details_widget = self.query_one("#pnl-details", Static)

        color = "green" if daily_pnl > 0 else "red" if daily_pnl < 0 else "yellow"
        sign = "+" if daily_pnl > 0 else ""
        pnl_widget.update(f"[bold {color}]{sign}{daily_pnl:.2%}[/]")

        winrate = wins / session_trades if session_trades > 0 else 0
        details_widget.update(
            f"Trades: [cyan]{session_trades}[/] | "
            f"W: [green]{wins}[/] | "
            f"L: [red]{losses}[/] | "
            f"WR: [yellow]{winrate:.0%}[/]"
        )


class TimezonePanel(Static):
    """Affiche l'heure UTC-10 (Tahiti) en temps réel."""

    def compose(self) -> ComposeResult:
        yield Label("🌺 UTC-10 TAHITI", id="tz-title")
        yield Static("", id="tz-time")
        yield Static("", id="tz-session")

    def update_time(self):
        from datetime import timezone, timedelta
        tahiti_tz = timezone(timedelta(hours=-10))
        now_tahiti = datetime.now(tahiti_tz)
        hour = now_tahiti.hour

        if 22 <= hour or hour < 4:
            session = "[cyan]Asia Open[/]"
        elif 4 <= hour < 10:
            session = "[yellow]Europe Open[/]"
        elif 15 <= hour < 22:
            session = "[green]US Session[/]"
        else:
            session = "[dim]Off-hours[/]"

        self.query_one("#tz-time", Static).update(
            f"[bold white]{now_tahiti.strftime('%H:%M:%S')}[/]"
        )
        self.query_one("#tz-session", Static).update(f"Session: {session}")


class RiskMeterPanel(Static):
    """Jauge de risque globale ORACLE v2."""

    def compose(self) -> ComposeResult:
        yield Label("⚠️ RISK METER", id="risk-title")
        yield Static("", id="risk-level")
        yield Static("", id="risk-details")

    def update_risk(
        self,
        consecutive_losses: int,
        daily_drawdown: float,
        open_positions: int,
        max_losses: int = 3,
        max_drawdown: float = 0.02,
        max_positions: int = 3
    ):
        loss_pct = consecutive_losses / max_losses
        dd_pct = abs(daily_drawdown) / max_drawdown
        pos_pct = open_positions / max_positions
        risk_score = (loss_pct + dd_pct + pos_pct) / 3

        if risk_score < 0.33:
            color = "green"
            label = "LOW"
        elif risk_score < 0.67:
            color = "yellow"
            label = "MEDIUM"
        else:
            color = "red"
            label = "HIGH"

        bar_len = 20
        filled = int(risk_score * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        self.query_one("#risk-level", Static).update(
            f"[bold {color}]{label}[/] [{color}]{bar}[/] {risk_score:.0%}"
        )
        self.query_one("#risk-details", Static).update(
            f"Pertes: {consecutive_losses}/{max_losses} | "
            f"DD: {daily_drawdown:.2%} | "
            f"Pos: {open_positions}/{max_positions}"
        )


class TradesTablePanel(Static):
    """Historique des trades de la session."""

    def compose(self) -> ComposeResult:
        yield Label("📋 TRADES SESSION", id="trades-title")
        yield DataTable(id="trades-data")

    def on_mount(self):
        table = self.query_one("#trades-data", DataTable)
        table.add_columns("Heure", "Symbol", "Dir", "Size", "PnL", "Strate")

    def add_trade(
        self,
        symbol: str,
        direction: str,
        size_usdt: float,
        pnl_pct: float,
        source: str
    ):
        table = self.query_one("#trades-data", DataTable)
        now = datetime.now().strftime("%H:%M")
        dir_color = "green" if direction == "LONG" else "red"
        pnl_color = "green" if pnl_pct > 0 else "red"
        sign = "+" if pnl_pct > 0 else ""
        table.add_row(
            now,
            symbol,
            f"[{dir_color}]{direction}[/]",
            f"${size_usdt:,.0f}",
            f"[{pnl_color}]{sign}{pnl_pct:.2%}[/]",
            source
        )
