"""
Alerts — Système d'alertes push Telegram pour ORACLE v2.
Envoi asynchrone — ne bloque JAMAIS la boucle de trading.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("ORACLE.Alerts")


class AlertLevel:
    CRITICAL = "🚨"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SUCCESS = "✅"
    TRADE = "⚡"
    POLYMARKET = "🎯"


class AlertQueue:
    """
    File d'attente d'alertes asynchrone.
    Les alertes sont envoyées sans bloquer le trading loop.
    """

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._worker())

    async def stop(self):
        self._running = False

    async def _worker(self):
        while self._running:
            try:
                text, parse_mode = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._send(text, parse_mode)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"AlertQueue worker error: {e}")

    async def _send(self, text: str, parse_mode: str = "Markdown"):
        try:
            from telegram import Bot
            bot = Bot(self.token)
            await bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Alert send error: {e}")

    def push(self, text: str, parse_mode: str = "Markdown"):
        """Enfile une alerte sans attendre l'envoi."""
        try:
            self._queue.put_nowait((text, parse_mode))
        except asyncio.QueueFull:
            logger.warning("AlertQueue pleine — alerte ignorée")

    def alert_trade_open(self, symbol: str, direction: str, size_usdt: float,
                         leverage: float, sl_pct: float, tp_pct: float,
                         confidence: float, source: str):
        dir_emoji = "🟢" if direction == "LONG" else "🔴"
        text = (
            f"⚡ *Nouveau Trade*\n\n"
            f"{dir_emoji} *{symbol}* — {direction}\n"
            f"Size: `${size_usdt:,.0f}` x{leverage}\n"
            f"SL: `{sl_pct:.1%}` | TP: `{tp_pct:.1%}`\n"
            f"Conf: `{confidence:.0%}` | Via: `{source}`"
        )
        self.push(text)

    def alert_trade_close(self, symbol: str, direction: str, pnl_pct: float):
        emoji = "✅" if pnl_pct > 0 else "❌"
        text = (
            f"{emoji} *Trade Clôturé*\n"
            f"*{symbol}* {direction}\n"
            f"PnL: `{pnl_pct:+.2%}`"
        )
        self.push(text)

    def alert_brainstem(self, reason: str):
        text = f"🚨 *BRAINSTEM DÉCLENCHÉ*\n\nRaison: `{reason}`\nTrading suspendu."
        self.push(text)

    def alert_polymarket(self, asset: str, edge: float, question: str,
                         kelly: float, confidence: str):
        emoji = "📈" if edge > 0 else "📉"
        conf_e = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💧"}.get(confidence, "")
        text = (
            f"🎯 {conf_e} *Polymarket Signal*\n\n"
            f"{emoji} *{asset}*\n"
            f"_{question[:70]}..._\n"
            f"Edge: `{edge:+.1%}` | Kelly: `{kelly:.1%}`"
        )
        self.push(text)

    def alert_system(self, message: str, level: str = "INFO"):
        emoji_map = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️", "SUCCESS": "✅"}
        emoji = emoji_map.get(level, "ℹ️")
        self.push(f"{emoji} *ORACLE v2*\n{message}")
