"""
Handlers — Logique métier des commandes Telegram ORACLE v2.
Séparé du bot.py pour garder les handlers testables indépendamment.
"""
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.Handlers")


class OracleHandlers:
    """
    Handlers réutilisables pour les commandes Telegram.
    Reçoit l'oracle_system comme dépendance — facilite le mocking en tests.
    """

    def __init__(self, oracle_system=None):
        self.oracle = oracle_system

    def get_status_text(self) -> str:
        if not self.oracle:
            return "⚠️ Système ORACLE non connecté"
        status = self.oracle.get_status()
        bs = status.get("brainstem", {})
        alive = bs.get("alive", False)
        return (
            f"{'🟢' if alive else '🔴'} *ORACLE v2 — Status*\n"
            f"```\n"
            f"Mode       : {status.get('mode', 'UNKNOWN')}\n"
            f"Brainstem  : {'ALIVE' if alive else 'OFFLINE — ' + bs.get('reason', '')}\n"
            f"PnL jour   : {bs.get('daily_pnl', 'N/A')}\n"
            f"Trades/Sess: {bs.get('session_trades', 0)}\n"
            f"Positions  : {status.get('open_positions', 0)}\n"
            f"Cooling    : {'OUI ⏸️' if bs.get('cooling') else 'NON'}\n"
            f"```"
        )

    def get_brainstem_text(self) -> str:
        if not self.oracle:
            return "⚠️ Système non connecté"
        bs = self.oracle.brainstem.get_status_dict()
        alive = bs["alive"]
        return (
            f"{'🟢' if alive else '🔴'} *Brainstem Status*\n"
            f"```\n"
            f"État        : {'ALIVE' if alive else 'BLOCKED'}\n"
            f"Raison      : {bs['reason']}\n"
            f"Pertes cons.: {bs['consecutive_losses']}\n"
            f"PnL jour    : {bs['daily_pnl']}\n"
            f"Trades sess : {bs['session_trades']}\n"
            f"Cooling     : {'OUI ⏸️' if bs['cooling'] else 'NON'}\n"
            f"```"
        )

    def get_signals_text(self) -> str:
        if not self.oracle:
            return "⚠️ Système non connecté"
        signals = self.oracle.get_active_signals()
        if not signals:
            return "📭 Aucun signal actif."
        lines = ["📡 *Signaux Actifs*\n"]
        for sig in signals:
            d = sig.get("direction", "NEUTRAL")
            emoji = "🟢" if d == "LONG" else "🔴" if d == "SHORT" else "⚪"
            lines.append(
                f"{emoji} *{sig.get('symbol', '')}* — {d}\n"
                f"   `{sig.get('confidence', 0):.0%}` | {sig.get('source', '')}"
            )
        return "\n".join(lines)

    def get_parliament_text(self) -> str:
        if not self.oracle:
            return "⚠️ Système non connecté"
        decision = self.oracle.last_parliament_decision
        if not decision:
            return "📭 Pas encore de décision parlementaire."
        dir_emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(decision.direction, "❓")
        poly = "✅ Aligné" if decision.polymarket_alignment else "❌ Divergent"
        lines = [
            f"🏛️ *Parlement — Dernière Décision*\n",
            f"{dir_emoji} Direction: `{decision.direction}`",
            f"Force: `{decision.strength:.0%}`",
            f"Polymarket: {poly}",
            "",
            f"*Votes gagnants ({len(decision.votes)}):*"
        ]
        for v in decision.votes:
            lines.append(f"  • {v.strate_name}: `{v.direction}` ({v.confidence:.0%})")
        if decision.dissenting:
            lines.append(f"\n*Dissidents ({len(decision.dissenting)}):*")
            for v in decision.dissenting:
                lines.append(f"  • {v.strate_name}: `{v.direction}` ({v.confidence:.0%})")
        return "\n".join(lines)

    def get_daily_report_text(self) -> str:
        if not self.oracle:
            return "⚠️ Système non connecté"
        report = self.oracle.get_daily_report()
        pnl = report.get("pnl_pct", 0)
        return (
            f"📊 *Rapport Journalier ORACLE v2*\n"
            f"```\n"
            f"Trades total  : {report.get('total_trades', 0)}\n"
            f"Gagnants      : {report.get('wins', 0)}\n"
            f"Perdants      : {report.get('losses', 0)}\n"
            f"Win rate      : {report.get('winrate', 0):.1%}\n"
            f"PnL brut      : {pnl:+.2%}\n"
            f"Meilleur trade: {report.get('best_trade', 'N/A')}\n"
            f"Pire trade    : {report.get('worst_trade', 'N/A')}\n"
            f"```"
        )
