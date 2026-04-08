"""
Module Telegram — Notifications temps réel + Commandes interactives.
Refonte complète : connecté au PerformanceTracker, commandes /status /pnl /positions etc.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False


class TelegramNotifier:
    """
    Notificateur Telegram avec commandes interactives.

    Fonctionnalités :
    - Notifications push (signaux, trades, alertes, résumés)
    - Commandes interactives via polling getUpdates :
        /status  — état global du bot
        /pnl     — P&L détaillé
        /positions — positions ouvertes
        /risk    — métriques de risque
        /memory  — état de la mémoire ML
        /help    — aide
    - Connecté à PerformanceTracker pour données LIVE
    """

    BASE_URL = "https://api.telegram.org/bot{token}"

    # Retry / backoff constants
    _MAX_SEND_RETRIES = 3
    _POLL_BACKOFF_BASE = 5
    _POLL_BACKOFF_MAX = 60

    def __init__(self, token: str, chat_id: str, rate_limiter=None):
        self.token   = token
        self.chat_id = str(chat_id)
        self.enabled = bool(token and chat_id and _HTTPX_OK)
        self._rate_limiter = rate_limiter
        self._tracker: Optional[PerformanceTracker] = None
        self._risk_agent = None  # ref to RiskAgent for open positions
        self._compound_agent = None  # ref to CompoundAgent for mode info
        self._last_update_id = 0
        self._polling_task: Optional[asyncio.Task] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._last_successful_send: float = 0.0

        if not _HTTPX_OK:
            logger.error("[Telegram] DESACTIVE : httpx n'est pas installe (pip install httpx)")
        elif not token:
            logger.error("[Telegram] DESACTIVE : TELEGRAM_TOKEN est vide — verifier .env")
        elif not chat_id:
            logger.error("[Telegram] DESACTIVE : TELEGRAM_CHAT_ID est vide — verifier .env")
        else:
            logger.info("[Telegram] Notificateur configure (chat_id=%s, token=%s...)",
                        self.chat_id, token[:10])

    # ── Injection de dépendances (appelé par run_demo.py) ─────────────────────

    def set_tracker(self, tracker: "PerformanceTracker") -> None:
        """Connecte le PerformanceTracker pour données live."""
        self._tracker = tracker
        logger.info("[Telegram] PerformanceTracker connecté")

    def set_risk_agent(self, risk_agent) -> None:
        """Connecte le RiskAgent pour accéder aux positions ouvertes."""
        self._risk_agent = risk_agent

    def set_compound_agent(self, compound_agent) -> None:
        """Connecte le CompoundAgent pour le mode courant."""
        self._compound_agent = compound_agent

    # ── Vérification de connexion ───────────────────────────────────────────

    async def verify_connection(self) -> bool:
        """Teste la connexion Telegram avec getMe. Retourne True si OK."""
        if not self.enabled:
            logger.error("[Telegram] verify_connection: DESACTIVE (token=%s, chat_id=%s, httpx=%s)",
                         bool(self.token), bool(self.chat_id), _HTTPX_OK)
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"{self.BASE_URL.format(token=self.token)}/getMe"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    bot_name = data.get("result", {}).get("username", "?")
                    logger.info("[Telegram] Connexion OK — bot @%s", bot_name)
                    return True
                else:
                    logger.error("[Telegram] ECHEC connexion — HTTP %d: %s",
                                 resp.status_code, resp.text[:200])
                    return False
        except Exception as exc:
            logger.error("[Telegram] ECHEC connexion — %s", exc)
            return False

    # ── Polling des commandes ─────────────────────────────────────────────────

    async def start_polling(self) -> None:
        """Démarre le polling des commandes Telegram en tâche de fond."""
        if not self.enabled:
            logger.error("[Telegram] start_polling: IMPOSSIBLE — notifier desactive")
            return
        # Client HTTP persistant — réutilisé pour toute la durée de vie
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=20, write=10, pool=10),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
        self._last_successful_send = time.monotonic()
        self._polling_task = asyncio.create_task(
            self._poll_updates(), name="telegram_polling"
        )
        logger.info("[Telegram] Polling des commandes demarre (client HTTP persistant)")

    async def stop_polling(self) -> None:
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        if self._http:
            await self._http.aclose()
            self._http = None

    async def _poll_updates(self) -> None:
        """Boucle de polling getUpdates avec backoff exponentiel."""
        consecutive_errors = 0
        while True:
            try:
                if not self._http:
                    logger.warning("[Telegram] Client HTTP absent — recréation")
                    self._http = httpx.AsyncClient(
                        timeout=httpx.Timeout(connect=10, read=20, write=10, pool=10),
                        limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
                    )
                url = f"{self.BASE_URL.format(token=self.token)}/getUpdates"
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": 10,
                    "allowed_updates": '["message"]',
                }
                resp = await self._http.get(url, params=params)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 30))
                    logger.warning("[Telegram] Rate limited — attente %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status_code != 200:
                    consecutive_errors += 1
                    backoff = min(self._POLL_BACKOFF_BASE * (2 ** consecutive_errors), self._POLL_BACKOFF_MAX)
                    logger.warning("[Telegram] Polling HTTP %d — backoff %ds", resp.status_code, backoff)
                    await asyncio.sleep(backoff)
                    continue

                data = resp.json()
                consecutive_errors = 0  # reset on success

                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        self._last_update_id = update["update_id"]
                        msg = update.get("message", {})
                        text = msg.get("text", "")
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        # Only respond to our chat
                        if chat_id == self.chat_id and text.startswith("/"):
                            await self._handle_command(text.strip().lower())

            except asyncio.CancelledError:
                raise
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                consecutive_errors += 1
                backoff = min(self._POLL_BACKOFF_BASE * (2 ** consecutive_errors), self._POLL_BACKOFF_MAX)
                logger.warning("[Telegram] Connexion polling perdue (%s) — backoff %ds", exc, backoff)
                # Recréer le client en cas de problème de connexion persistant
                if consecutive_errors >= 3:
                    await self._recreate_http_client()
                    consecutive_errors = 0
                await asyncio.sleep(backoff)
            except Exception as exc:
                consecutive_errors += 1
                backoff = min(self._POLL_BACKOFF_BASE * (2 ** consecutive_errors), self._POLL_BACKOFF_MAX)
                logger.warning("[Telegram] Erreur polling: %s — backoff %ds", exc, backoff)
                await asyncio.sleep(backoff)

    async def _recreate_http_client(self) -> None:
        """Ferme et recrée le client HTTP en cas de connexion corrompue."""
        logger.info("[Telegram] Recréation du client HTTP persistant")
        try:
            if self._http:
                await self._http.aclose()
        except Exception:
            pass
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=20, write=10, pool=10),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )

    async def _handle_command(self, cmd: str) -> None:
        """Route les commandes vers les handlers."""
        cmd_base = cmd.split()[0]  # /status@botname → /status
        if "@" in cmd_base:
            cmd_base = cmd_base.split("@")[0]

        handlers = {
            "/status":    self._cmd_status,
            "/pnl":       self._cmd_pnl,
            "/positions": self._cmd_positions,
            "/risk":      self._cmd_risk,
            "/memory":    self._cmd_memory,
            "/help":      self._cmd_help,
        }

        handler = handlers.get(cmd_base)
        if handler:
            try:
                await handler()
            except Exception as exc:
                logger.warning("[Telegram] Erreur commande %s: %s", cmd_base, exc)
                await self.send(f"Erreur lors de `{cmd_base}` : `{exc}`")
        else:
            await self.send(
                "Commande inconnue. Tapez /help pour la liste."
            )

    # ── Commandes interactives ────────────────────────────────────────────────

    async def _cmd_status(self) -> None:
        """Vue d'ensemble rapide."""
        if not self._tracker:
            await self.send("Tracker non connecté.")
            return

        snap = self._tracker.snapshot()
        sign = "+" if snap["total_return_pct"] >= 0 else ""
        trend = "+" if snap["total_return_pct"] >= 0 else ""

        # Mode compound
        mode = "normal"
        risk_pct = "2.00"
        if self._compound_agent:
            mode = self._compound_agent.memory.adaptive_params.get("last_mode", "normal")
            risk_pct = f"{self._compound_agent.current_risk_pct:.2f}"

        # Positions ouvertes
        n_pos = 0
        if self._risk_agent:
            n_pos = len(self._risk_agent._open_positions)

        msg = (
            f"*Bot Status*\n"
            f"{'=' * 25}\n"
            f"Capital : `${snap['capital']:,.2f}` ({sign}{snap['total_return_pct']:.2f}%)\n"
            f"Win Rate : `{snap['win_rate']:.0%}` | Trades : `{snap['total_trades']}`\n"
            f"Sharpe : `{snap['sharpe_ratio']:.2f}` | Sortino : `{snap['sortino_ratio']:.2f}`\n"
            f"Drawdown : `{snap['current_drawdown']:.1f}%` / `{snap['max_drawdown_pct']:.1f}%` max\n"
            f"Mode : `{mode.upper()}` | Risque/trade : `{risk_pct}%`\n"
            f"Positions : `{n_pos}/5`\n"
            f"Regime : `{snap['regime'].upper()}`"
        )
        await self.send(msg)

    async def _cmd_pnl(self) -> None:
        """P&L détaillé par asset."""
        if not self._tracker:
            await self.send("Tracker non connecté.")
            return

        snap = self._tracker.snapshot()
        sign = "+" if snap["total_return_pct"] >= 0 else ""

        lines = [
            f"*P&L Détaillé*\n",
            f"Capital : `${snap['capital']:,.2f}`",
            f"Return : `{sign}{snap['total_return_pct']:.2f}%` (${snap['capital'] - snap['initial_capital']:+,.2f})",
            f"Profit Factor : `{snap['profit_factor']:.2f}`",
            f"Expectancy : `${snap['expectancy_usd']:+.2f}`/trade",
            f"\n*Par Asset :*",
        ]

        wr_by_asset = snap.get("win_rate_by_asset", {})
        for asset, wr in wr_by_asset.items():
            lines.append(f"  {asset} : WR `{wr:.0%}`")

        lines.append(f"\nMeilleur : `{snap['best_asset']}` (${snap['best_pnl_usd']:+,.2f})")
        lines.append(f"Pire : `{snap['worst_asset']}` (${snap['worst_pnl_usd']:+,.2f})")

        await self.send("\n".join(lines))

    async def _cmd_positions(self) -> None:
        """Positions ouvertes."""
        if not self._risk_agent:
            await self.send("RiskAgent non connecté.")
            return

        positions = self._risk_agent._open_positions
        if not positions:
            await self.send("Aucune position ouverte.")
            return

        lines = [f"*Positions Ouvertes ({len(positions)}/5)*\n"]
        for asset, pos in positions.items():
            side = pos.get("side", "?").upper()
            entry = pos.get("entry_price", 0)
            sl = pos.get("stop_loss", 0)
            tp = pos.get("take_profit", 0)
            rr = pos.get("risk_reward", 0)
            lines.append(
                f"  {side} `{asset}`\n"
                f"    Entry: `{entry}` | SL: `{sl}` | TP: `{tp}`\n"
                f"    R:R = `1:{rr}`"
            )
        await self.send("\n".join(lines))

    async def _cmd_risk(self) -> None:
        """Métriques de risque."""
        if not self._tracker:
            await self.send("Tracker non connecté.")
            return

        snap = self._tracker.snapshot()
        msg = (
            f"*Risk Dashboard*\n"
            f"Drawdown courant : `{snap['current_drawdown']:.2f}%`\n"
            f"Drawdown max : `{snap['max_drawdown_pct']:.2f}%`\n"
            f"Sharpe : `{snap['sharpe_ratio']:.2f}`\n"
            f"Sortino : `{snap['sortino_ratio']:.2f}`\n"
            f"Calmar : `{snap['calmar_ratio']:.2f}`\n"
            f"Durée moy. trade : `{snap['avg_holding_h']:.1f}h`\n"
            f"Regime : `{snap['regime'].upper()}`"
        )
        await self.send(msg)

    async def _cmd_memory(self) -> None:
        """État de la mémoire ML."""
        if not self._risk_agent or not self._risk_agent.memory:
            await self.send("Mémoire non disponible.")
            return

        mem = self._risk_agent.memory
        msg = (
            f"*Mémoire ML — RiskAgent*\n"
            f"SL multiplier : `{mem.adaptive_params.get('sl_atr_multiplier', 1.5):.2f}x ATR`\n"
            f"TP ratio : `1:{mem.adaptive_params.get('tp_rr_ratio', 2.5):.2f}`\n"
            f"Confidence floor : `{mem.adaptive_params.get('confidence_floor', 55)}/100`\n"
            f"Streak : `{mem.current_streak:+d}`\n"
            f"Total trades (mem) : `{mem.total_trades}`\n"
            f"Win rate (mem) : `{mem.win_rate:.1%}`"
        )
        if self._compound_agent and self._compound_agent.memory:
            cmem = self._compound_agent.memory
            mode = cmem.adaptive_params.get("last_mode", "normal")
            msg += (
                f"\n\n*CompoundAgent*\n"
                f"Mode : `{mode.upper()}`\n"
                f"Risk/trade : `{self._compound_agent.current_risk_pct:.2f}%`\n"
                f"Recovery rate : `{cmem.adaptive_params.get('recovery_rate', 0.5):.2f}`"
            )
        await self.send(msg)

    async def _cmd_help(self) -> None:
        msg = (
            "*Commandes disponibles :*\n"
            "/status — Vue d'ensemble du bot\n"
            "/pnl — P&L détaillé par asset\n"
            "/positions — Positions ouvertes\n"
            "/risk — Métriques de risque\n"
            "/memory — État mémoire ML\n"
            "/help — Cette aide"
        )
        await self.send(msg)

    # ── API d'envoi ──────────────────────────────────────────────────────────

    async def send(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Envoie un message avec retry et backoff exponentiel."""
        if not self.enabled:
            return False

        if self._rate_limiter:
            try:
                await asyncio.wait_for(
                    self._rate_limiter.acquire("telegram_chat"), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("[Telegram] Rate limiter timeout — envoi sans attente")

        url     = f"{self.BASE_URL.format(token=self.token)}/sendMessage"
        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        for attempt in range(self._MAX_SEND_RETRIES):
            try:
                if not self._http:
                    await self._recreate_http_client()

                resp = await self._http.post(url, json=payload)

                if resp.status_code == 200:
                    self._last_successful_send = time.monotonic()
                    return True

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    logger.warning("[Telegram] Rate limited — attente %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                logger.warning("[Telegram] HTTP %d — %s", resp.status_code, resp.text[:200])
                # Retry without parse_mode on Markdown syntax error
                if resp.status_code == 400 and parse_mode == "Markdown":
                    payload["parse_mode"] = ""
                    continue
                return False

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                logger.warning("[Telegram] Erreur envoi (attempt %d/%d): %s",
                               attempt + 1, self._MAX_SEND_RETRIES, exc)
                if attempt < self._MAX_SEND_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    # Recréer le client si connexion cassée
                    if attempt >= 1:
                        await self._recreate_http_client()
            except Exception as exc:
                logger.warning("[Telegram] Erreur envoi inattendue: %s", exc)
                return False

        return False

    def is_healthy(self) -> bool:
        """Vérifie si le notifier envoie encore des messages avec succès."""
        if not self.enabled:
            return True  # pas activé = pas de problème
        if self._last_successful_send == 0:
            return True  # pas encore de send tenté
        return (time.monotonic() - self._last_successful_send) < 600  # 10 min max sans succès

    # ── Messages push prédéfinis ─────────────────────────────────────────────

    async def signal_detected(
        self, asset: str, direction: str, confidence: int,
        tech_conf: int, fund_conf: int, regime: str = "—",
    ) -> None:
        return  # silencé — trop fréquent

    async def trade_opened(
        self, asset: str, direction: str, entry: float,
        sl: float, tp: float, size: float, risk_usd: float,
        capital: float = 0,
    ) -> None:
        icon = "📈" if direction.lower() in ("buy", "long", "bullish") else "📉"
        rr   = round(abs(tp - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
        cap_line = f"\nCapital : `${capital:,.2f}`" if capital > 0 else ""
        msg  = (
            f"{icon} *Trade ouvert — {asset}*\n"
            f"`{direction.upper()}` @ `{entry:,.4f}`\n"
            f"SL: `{sl:,.4f}` | TP: `{tp:,.4f}` | R:R `1:{rr}`\n"
            f"Taille: `{size}` | Risque: `${risk_usd:.2f}`"
            f"{cap_line}"
        )
        await self.send(msg)

    async def trade_closed(
        self, asset: str, pnl_usd: float, pnl_pct: float,
        win_rate: float, total_trades: int,
        capital: float = 0, drawdown: float = 0, sharpe: float = 0,
        ml_info: str = "",
    ) -> None:
        icon   = "✅" if pnl_usd >= 0 else "❌"
        sign   = "+" if pnl_usd >= 0 else ""
        lines = [
            f"{icon} *Trade fermé — {asset}*",
            f"P&L : `{sign}{pnl_usd:.2f}$` (`{sign}{pnl_pct:.2f}%`)",
            f"WR: `{win_rate:.0%}` | Trades: `{total_trades}`",
        ]
        if capital > 0:
            lines.append(f"Capital: `${capital:,.2f}` | DD: `{drawdown:.1f}%` | Sharpe: `{sharpe:.2f}`")
        if ml_info:
            lines.append(ml_info)
        await self.send("\n".join(lines))

    async def risk_alert(self, drawdown: float, capital: float, message: str) -> None:
        msg = (
            f"*Alerte Risque*\n"
            f"Drawdown : `{drawdown:.1f}%`\n"
            f"Capital : `${capital:,.2f}`\n"
            f"_{message}_"
        )
        await self.send(msg)

    async def compound_mode_change(
        self, mode: str, new_risk: float, reason: str, icon: str = "⚙️",
    ) -> None:
        return  # silencé

    async def manipulation_alert(
        self, asset: str, alert_type: str, details: str,
    ) -> None:
        """Alerte de manipulation de marché détectée par SynthesisAgent."""
        msg = (
            f"*Manipulation — {asset}*\n"
            f"Type : `{alert_type}`\n"
            f"_{details}_"
        )
        await self.send(msg)

    async def performance_summary(
        self, capital: float, pnl_pct: float, win_rate: float,
        sharpe: float, drawdown: float, total_trades: int,
    ) -> None:
        trend = "📈" if pnl_pct >= 0 else "📉"
        sign  = "+" if pnl_pct >= 0 else ""
        msg   = (
            f"{trend} *Résumé Performance*\n"
            f"Capital : `${capital:,.2f}` (`{sign}{pnl_pct:.2f}%`)\n"
            f"WR: `{win_rate:.0%}` | Sharpe: `{sharpe:.2f}` | DD: `{drawdown:.1f}%`\n"
            f"Trades : `{total_trades}`"
        )
        await self.send(msg)

    async def bot_started(self, agents: list[str], mode: str = "simulation") -> None:
        agent_list = "\n".join(f"  {a}" for a in agents)
        msg = (
            f"*Trading Bot demarré*\n"
            f"Mode : `{mode}`\n"
            f"Agents :\n{agent_list}\n"
            f"\nTapez /help pour les commandes"
        )
        await self.send(msg)

    async def convergence_signal(
        self, asset: str, direction: str, confidence: int,
        tech_w: float, fund_w: float, regime: str,
        mtf_boost: int = 0, ob_adj: int = 0, vwap_adj: int = 0,
    ) -> None:
        return  # silencé — visible via /status à la demande

    async def datasheet_summary(
        self, asset: str, bias: str, vix: float,
        structure: str, strategies: str,
    ) -> None:
        return  # silencé

    async def learning_update(
        self, agent: str, param_updates: dict, lesson: str = "",
    ) -> None:
        """Notification de mise à jour ML par LearningEngine."""
        updates_str = " | ".join(f"{k}: `{v}`" for k, v in param_updates.items())
        msg = (
            f"*ML Update — {agent}*\n"
            f"{updates_str}\n"
        )
        if lesson:
            msg += f"_{lesson}_\n"
        await self.send(msg)

    async def health_status(
        self, agents_alive: int, agents_total: int,
        capital: float, pnl_pct: float, win_rate: float,
        drawdown: float, sharpe: float, pipeline_stats: str,
    ) -> None:
        """Rapport de santé périodique du SupervisorAgent."""
        trend = "📈" if pnl_pct >= 0 else "📉"
        sign = "+" if pnl_pct >= 0 else ""
        msg = (
            f"*Health Status*\n"
            f"Agents : `{agents_alive}/{agents_total}` actifs\n"
            f"Capital : `${capital:,.2f}` (`{sign}{pnl_pct:.2f}%`)\n"
            f"WR: `{win_rate:.0%}` | Sharpe: `{sharpe:.2f}` | DD: `{drawdown:.1f}%`\n"
            f"\n*Pipeline :*\n{pipeline_stats}"
        )
        await self.send(msg)

    async def counterfactual_lesson(
        self, asset: str, actual_pnl: float,
        best_sl: float, best_tp: float, best_pnl: float,
    ) -> None:
        msg = (
            f"*ML Lesson — {asset}*\n"
            f"Trade réel : `{actual_pnl:+.2f}%`\n"
            f"Optimal : SL `x{best_sl}` TP `1:{best_tp}` = `{best_pnl:+.2f}%`"
        )
        await self.send(msg)

    # ── Nouveaux messages (MetaAgent / RegimeAgent / BehaviorAgent) ───────────

    async def regime_shift(
        self,
        asset: str,
        prev_regime: str,
        new_regime: str,
        adx: float,
        atr_pct: float,
        volume_anomaly: bool,
    ) -> None:
        """Alerte Telegram quand le régime de marché change (RegimeAgent)."""
        regime_emoji = {
            "trending_up":   "📈",
            "trending_down": "📉",
            "ranging":       "↔️",
            "volatile":      "⚡",
            "unknown":       "❓",
        }
        e_prev = regime_emoji.get(prev_regime, "❓")
        e_new  = regime_emoji.get(new_regime,  "❓")
        now    = datetime.now(timezone.utc).strftime("%H:%M UTC")
        vol_flag = " 🚨 Volume spike!" if volume_anomaly else ""

        msg = (
            f"🌊 *Changement de Régime — {asset}*\n"
            f"{e_prev} `{prev_regime.upper()}` → {e_new} `{new_regime.upper()}`\n"
            f"ADX : `{adx:.1f}` | ATR : `{atr_pct:.2f}%`{vol_flag}\n"
            f"_{now}_"
        )
        await self.send(msg)

    async def ceo_report(
        self,
        date: str,
        capital: float,
        pnl_pct: float,
        win_rate: float,
        sharpe: float,
        drawdown: float,
        total_trades: int,
        ranking: list[dict],
        regimes: dict[str, str],
        weights: dict,
        adjustments: list[str],
        risk_status: str,
    ) -> None:
        """Rapport CEO quotidien (MetaAgent) — ton professionnel et stratégique."""
        now    = datetime.now(timezone.utc).strftime("%H:%M UTC")
        trend  = "📈" if pnl_pct >= 0 else "📉"
        sign   = "+" if pnl_pct >= 0 else ""

        # Top 3 agents
        top3 = "\n".join(
            f"  {i+1}. `{r['name']}` — score `{r.get('score', 0):.2f}`, "
            f"précision `{r.get('precision', 0):.0%}`"
            for i, r in enumerate(ranking[:3])
        ) or "  _Données insuffisantes_"

        # Régimes principaux
        regime_str = " | ".join(
            f"`{a}`: {r.upper()}" for a, r in list(regimes.items())[:3]
        ) or "_Aucune donnée_"

        # Derniers ajustements
        adj_str = "\n".join(f"  • {a}" for a in adjustments[-3:]) or "  • Aucun"

        msg = (
            f"👑 *CEO Report — {date}*\n\n"
            f"*{trend} Performance*\n"
            f"Capital : `${capital:,.2f}` (`{sign}{pnl_pct:.2f}%`)\n"
            f"Win Rate : `{win_rate:.0%}` | Sharpe : `{sharpe:.2f}` | DD : `{drawdown:.1f}%`\n"
            f"Trades : `{total_trades}`\n\n"
            f"*🌊 Régimes de Marché*\n{regime_str}\n\n"
            f"*🏆 Top Agents*\n{top3}\n\n"
            f"*⚙️ Ajustements CEO*\n{adj_str}\n\n"
            f"*{risk_status}*\n\n"
            f"_Poids : tech×{weights.get('tech_weight', 1):.1f} | "
            f"fund×{weights.get('fund_weight', 1):.1f} | "
            f"conf={weights.get('min_confidence', 55)}_\n"
            f"_{now}_"
        )
        await self.send(msg)

    async def weekly_report(
        self,
        week: str,
        trades: int,
        win_rate: float,
        pnl_pct: float,
        total_pnl_pct: float,
        sharpe: float,
        drawdown: float,
        capital: float,
        best_shadow: str | None,
        adjustments: list[str],
    ) -> None:
        """Rapport hebdomadaire complet (MetaAgent)."""
        sign  = "+" if pnl_pct >= 0 else ""
        tsign = "+" if total_pnl_pct >= 0 else ""
        shadow_str = f"\n🔬 Meilleure stratégie shadow : `{best_shadow}`" if best_shadow else ""
        adj_str = "\n".join(f"  • {a}" for a in adjustments) or "  • Aucun"

        msg = (
            f"📊 *Rapport Hebdomadaire — {week}*\n\n"
            f"*Cette semaine*\n"
            f"Trades : `{trades}` | Win Rate : `{win_rate:.0%}`\n"
            f"P&L semaine : `{sign}{pnl_pct:.2f}%`\n\n"
            f"*Session totale*\n"
            f"Capital : `${capital:,.2f}` (`{tsign}{total_pnl_pct:.2f}%`)\n"
            f"Sharpe : `{sharpe:.2f}` | Max DD : `{drawdown:.2f}%`\n"
            f"{shadow_str}\n\n"
            f"*Ajustements CEO*\n{adj_str}\n\n"
            f"_Rapport généré par MetaAgent_"
        )
        await self.send(msg)

    async def behavior_alert(
        self,
        mode: str,
        multiplier: float,
        reasons: list[str],
        streak: int,
    ) -> None:
        """Alerte comportementale (BehaviorAgent) — discipline du système."""
        mode_emoji = {
            "caution":    "⚠️",
            "restricted": "🔴",
            "paused":     "🛑",
        }.get(mode, "ℹ️")

        reasons_str = "\n".join(f"  • {r}" for r in reasons[:4]) or "  • N/A"

        msg = (
            f"{mode_emoji} *Discipline Alert — {mode.upper()}*\n"
            f"Multiplicateur risque : `×{multiplier:.2f}`\n"
            f"Streak de pertes : `{streak}`\n\n"
            f"*Raisons :*\n{reasons_str}\n\n"
            f"_BehaviorAgent — {datetime.now(timezone.utc).strftime('%H:%M UTC')}_"
        )
        await self.send(msg)

    async def market_update(
        self,
        title: str,
        body: str,
        urgency: str = "info",
    ) -> None:
        """Mise à jour marché générale — news, événements, volatilité (ResearchAgent)."""
        emoji = {"info": "🌍", "warning": "⚠️", "critical": "🚨"}.get(urgency, "🌍")
        now   = datetime.now(timezone.utc).strftime("%H:%M UTC")
        msg   = (
            f"{emoji} *Market Update — {title}*\n"
            f"{body}\n"
            f"_{now}_"
        )
        await self.send(msg)
