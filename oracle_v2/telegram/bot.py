"""
Bot Telegram ORACLE v2
Commandes : /status /signals /polymarket /brainstem /parliament /report /pause /resume /help
"""
import logging
from typing import Optional

logger = logging.getLogger("ORACLE.Telegram")


class OracleTelegramBot:
    def __init__(
        self,
        token: str,
        chat_id: str,
        oracle_system=None
    ):
        self.token = token
        self.chat_id = chat_id
        self.oracle = oracle_system
        self.app = None
        self._setup_app()

    def _setup_app(self):
        try:
            from telegram.ext import Application, CommandHandler
            self.app = Application.builder().token(self.token).build()
            self._setup_handlers()
        except ImportError:
            logger.error("python-telegram-bot non installé — pip install python-telegram-bot>=21.0.0")

    def _setup_handlers(self):
        from telegram.ext import CommandHandler
        handlers = [
            ("start", self.cmd_start),
            ("help", self.cmd_help),
            ("status", self.cmd_status),
            ("signals", self.cmd_signals),
            ("polymarket", self.cmd_polymarket),
            ("brainstem", self.cmd_brainstem),
            ("parliament", self.cmd_parliament),
            ("report", self.cmd_report),
            ("pause", self.cmd_pause),
            ("resume", self.cmd_resume),
        ]
        for name, handler in handlers:
            self.app.add_handler(CommandHandler(name, handler))

    async def cmd_start(self, update, ctx):
        from telegram.constants import ParseMode
        await update.message.reply_text(
            "🧠 *ORACLE v2 — Système Neural de Trading*\n\nTape /help pour voir les commandes.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_help(self, update, ctx):
        from telegram.constants import ParseMode
        text = (
            "🧠 *ORACLE v2 — Commandes*\n\n"
            "📊 *Monitoring*\n"
            "/status — État global du système\n"
            "/signals — Signaux actifs par asset\n"
            "/brainstem — État circuit breaker\n"
            "/parliament — Dernier vote du parlement\n\n"
            "🎯 *Polymarket*\n"
            "/polymarket — Top opportunités actuelles\n\n"
            "📈 *Trading*\n"
            "/report — Rapport PnL du jour\n"
            "/pause — Pause trading (safety)\n"
            "/resume — Reprendre trading\n"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_status(self, update, ctx):
        from telegram.constants import ParseMode
        if not self.oracle:
            await update.message.reply_text("⚠️ Système ORACLE non connecté")
            return
        status = self.oracle.get_status()
        brainstem = status.get("brainstem", {})
        alive = brainstem.get("alive", False)
        text = (
            f"{'🟢' if alive else '🔴'} *ORACLE v2 — Status*\n"
            f"```\n"
            f"Mode       : {status.get('mode', 'UNKNOWN')}\n"
            f"Brainstem  : {'ALIVE' if alive else 'OFFLINE — ' + brainstem.get('reason', '')}\n"
            f"PnL jour   : {brainstem.get('daily_pnl', 'N/A')}\n"
            f"Trades/Sess: {brainstem.get('session_trades', 0)}\n"
            f"Positions  : {status.get('open_positions', 0)}\n"
            f"Cooling    : {'OUI ⏸️' if brainstem.get('cooling') else 'NON'}\n"
            f"```"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_polymarket(self, update, ctx):
        from telegram.constants import ParseMode
        await update.message.reply_text("🔍 Scan Polymarket en cours...")
        if not self.oracle:
            return
        opportunities = await self.oracle.polymarket_strate.scan()
        if not opportunities:
            await update.message.reply_text("❌ Aucune opportunité détectée.")
            return
        text = "🎯 *Top Opportunités Polymarket*\n\n"
        for i, opp in enumerate(opportunities[:5], 1):
            emoji = "📈" if opp.edge > 0 else "📉"
            conf_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💧"}.get(opp.confidence, "")
            text += (
                f"{i}. {conf_emoji} *{opp.correlated_asset}* — {opp.direction}\n"
                f"   _{opp.question[:55]}..._\n"
                f"   {emoji} Edge: `{opp.edge:+.1%}` | Kelly: `{opp.kelly_fraction:.1%}`\n"
                f"   Vol: `${opp.volume_24h:,.0f}`\n\n"
            )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_brainstem(self, update, ctx):
        from telegram.constants import ParseMode
        if not self.oracle:
            return
        bs = self.oracle.brainstem.get_status_dict()
        alive = bs["alive"]
        text = (
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
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_signals(self, update, ctx):
        from telegram.constants import ParseMode
        if not self.oracle:
            return
        signals = self.oracle.get_active_signals()
        if not signals:
            await update.message.reply_text("📭 Aucun signal actif.")
            return
        text = "📡 *Signaux Actifs*\n\n"
        for sig in signals:
            dir_color = "🟢" if sig.get("direction") == "LONG" else "🔴"
            text += (
                f"{dir_color} *{sig['symbol']}* — {sig['direction']}\n"
                f"   Confiance: `{sig['confidence']:.0%}` | Source: `{sig['source']}`\n\n"
            )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_parliament(self, update, ctx):
        from telegram.constants import ParseMode
        if not self.oracle:
            return
        decision = self.oracle.last_parliament_decision
        if not decision:
            await update.message.reply_text("📭 Pas encore de décision parlementaire.")
            return
        dir_emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(decision.direction, "❓")
        poly = "✅ Aligné" if decision.polymarket_alignment else "❌ Divergent"
        text = (
            f"🏛️ *Parlement — Dernière Décision*\n\n"
            f"{dir_emoji} Direction: `{decision.direction}`\n"
            f"Force: `{decision.strength:.0%}`\n"
            f"Polymarket: {poly}\n\n"
            f"*Votes gagnants ({len(decision.votes)}):*\n"
        )
        for v in decision.votes:
            text += f"  • {v.strate_name}: `{v.direction}` ({v.confidence:.0%})\n"
        if decision.dissenting:
            text += f"\n*Dissidents ({len(decision.dissenting)}):*\n"
            for v in decision.dissenting:
                text += f"  • {v.strate_name}: `{v.direction}` ({v.confidence:.0%})\n"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_report(self, update, ctx):
        from telegram.constants import ParseMode
        if not self.oracle:
            return
        report = self.oracle.get_daily_report()
        text = (
            f"📊 *Rapport Journalier ORACLE v2*\n"
            f"```\n"
            f"Trades total  : {report.get('total_trades', 0)}\n"
            f"Gagnants      : {report.get('wins', 0)}\n"
            f"Perdants      : {report.get('losses', 0)}\n"
            f"Win rate      : {report.get('winrate', 0):.1%}\n"
            f"PnL brut      : {report.get('pnl_pct', 0):+.2%}\n"
            f"Meilleur trade: {report.get('best_trade', 'N/A')}\n"
            f"Pire trade    : {report.get('worst_trade', 'N/A')}\n"
            f"```"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_pause(self, update, ctx):
        from telegram.constants import ParseMode
        if self.oracle:
            self.oracle.pause()
        await update.message.reply_text("⏸️ *ORACLE v2 mis en pause.*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_resume(self, update, ctx):
        from telegram.constants import ParseMode
        if self.oracle:
            self.oracle.resume()
        await update.message.reply_text("▶️ *ORACLE v2 repris.*", parse_mode=ParseMode.MARKDOWN)

    async def send_trade_alert(self, order, decision, pnl: Optional[float] = None):
        from telegram import Bot
        from telegram.constants import ParseMode
        bot = Bot(self.token)
        if pnl is None:
            dir_emoji = "🟢 LONG" if order.direction == "LONG" else "🔴 SHORT"
            text = (
                f"⚡ *Nouveau Trade — ORACLE v2*\n\n"
                f"{dir_emoji} *{order.symbol}*\n"
                f"Size: `${order.size_usdt:,.0f}` | Leverage: `{order.leverage}x`\n"
                f"SL: `{order.sl_pct:.1%}` | TP: `{order.tp_pct:.1%}`\n"
                f"Source: `{order.source_strate}` | Conf: `{order.confidence:.0%}`\n"
                f"Parlement: `{decision.strength:.0%}` consensus"
            )
        else:
            pnl_emoji = "✅" if pnl > 0 else "❌"
            text = (
                f"{pnl_emoji} *Trade Clôturé — {order.symbol}*\n"
                f"PnL: `{pnl:+.2%}` | Direction: `{order.direction}`"
            )
        await bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.MARKDOWN)

    async def send_brainstem_alert(self, reason: str):
        from telegram import Bot
        from telegram.constants import ParseMode
        bot = Bot(self.token)
        await bot.send_message(
            chat_id=self.chat_id,
            text=f"🚨 *BRAINSTEM ACTIVÉ*\n\nRaison: `{reason}`\nTrading suspendu automatiquement.",
            parse_mode=ParseMode.MARKDOWN
        )

    def run(self):
        if self.app:
            self.app.run_polling()
