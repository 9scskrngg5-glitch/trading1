"""
Formatter — Formatage messages Telegram pour ORACLE v2.
Markdown-safe, compatible parse_mode=MARKDOWN.
"""
import re
from typing import Optional


def escape_md(text: str) -> str:
    """Échappe les caractères spéciaux Markdown v1."""
    special = r'_*`['
    for char in special:
        text = text.replace(char, f"\\{char}")
    return text


def format_pnl(pnl_pct: float) -> str:
    sign = "+" if pnl_pct > 0 else ""
    return f"{sign}{pnl_pct:.2%}"


def format_signal_summary(signals: list) -> str:
    if not signals:
        return "📭 Aucun signal actif."
    lines = ["📡 *Signaux Actifs*\n"]
    for sig in signals:
        direction = sig.get("direction", "NEUTRAL")
        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
        lines.append(
            f"{emoji} *{sig.get('symbol', '')}* — {direction}\n"
            f"   `{sig.get('confidence', 0):.0%}` | {sig.get('source', '')}"
        )
    return "\n".join(lines)


def format_parliament_decision(decision) -> str:
    if not decision:
        return "📭 Pas de décision parlementaire."
    dir_emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(decision.direction, "❓")
    lines = [
        f"🏛️ *Parlement ORACLE v2*\n",
        f"{dir_emoji} Direction: `{decision.direction}`",
        f"Force: `{decision.strength:.0%}`",
        f"Polymarket: {'✅ Aligné' if decision.polymarket_alignment else '❌ Divergent'}",
        "",
        f"*Votes ({len(decision.votes)}):*"
    ]
    for v in decision.votes[:5]:
        c = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(v.direction, "")
        lines.append(f"  {c} {v.strate_name}: `{v.confidence:.0%}`")
    return "\n".join(lines)


def format_polymarket_opportunities(opportunities: list, limit: int = 5) -> str:
    if not opportunities:
        return "❌ Aucune opportunité Polymarket."
    lines = [f"🎯 *Top {min(limit, len(opportunities))} Opportunités Polymarket*\n"]
    for i, opp in enumerate(opportunities[:limit], 1):
        emoji = "📈" if opp.edge > 0 else "📉"
        conf_e = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💧"}.get(opp.confidence, "")
        lines.append(
            f"{i}. {conf_e} *{opp.correlated_asset}* — {opp.direction}\n"
            f"   _{opp.question[:50]}..._\n"
            f"   {emoji} Edge: `{opp.edge:+.1%}` | Kelly: `{opp.kelly_fraction:.1%}`\n"
            f"   Vol: `${opp.volume_24h:,.0f}`"
        )
    return "\n".join(lines)


def format_daily_report(report: dict) -> str:
    wins = report.get("wins", 0)
    total = report.get("total_trades", 0)
    winrate = report.get("winrate", 0)
    pnl = report.get("pnl_pct", 0)
    pnl_emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
    return (
        f"📊 *Rapport Journalier ORACLE v2*\n"
        f"```\n"
        f"Trades   : {total} ({wins}W/{report.get('losses', 0)}L)\n"
        f"Win rate : {winrate:.1%}\n"
        f"PnL      : {format_pnl(pnl)}\n"
        f"Best     : {report.get('best_trade', 'N/A')}\n"
        f"Worst    : {report.get('worst_trade', 'N/A')}\n"
        f"```\n"
        f"{pnl_emoji} Session {'profitable' if pnl > 0 else 'négative' if pnl < 0 else 'neutre'}"
    )
