"""
Agent 5 — Exécuteur d'Ordres (Execute)
Place les ordres sur Binance/OANDA, trace le slippage, optimise les horaires.
Vault : vault/execution/

REFONTE v2 :
  - Résolution des trades par PRIX RÉEL (MarketDataManager) au lieu de random
  - Persistance des trades ouverts dans vault/config/open_trades.json
  - Les trades survivent aux redémarrages du bot
  - Plus aucun `random.random()` pour décider si un trade est gagnant/perdant
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from models.orders import ExecutionReport, OrderSide, OrderStatus

logger = logging.getLogger(__name__)

SLIPPAGE_ALERT_BPS = 25
MAX_RETRY          = 3
RETRY_DELAY        = 5


class ExecuteAgent(BaseAgent):
    """
    Agent d'exécution avec suivi de prix en temps réel.

    Modes de fonctionnement (via TradingModeManager) :
      SIMULATION : entrée simulée, suivi par prix réels MarketDataManager
      PAPER      : entrée simulée, suivi par prix réels Binance (données live)
      LIVE       : ordres réels via ccxt + OCO SL/TP sur l'exchange

    Trades ouverts persistés dans vault/config/open_trades.json.
    Au redémarrage, les trades sont rechargés et le suivi reprend.
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        telegram=None,
        config: dict = None,
        market_data=None,
        trading_mode=None,
    ):
        super().__init__("ExecuteAgent", "execution", bus, obsidian, config or {})
        self.telegram = telegram
        self._market_data = market_data
        self._trading_mode = trading_mode
        self._exchanges: dict = {}
        self._oanda_api = None
        self._history: list[dict] = []

        # Modèle slippage : {heure_utc: [bps, ...]}
        self._slippage_by_hour: dict[int, list[float]] = {h: [] for h in range(24)}

        # Trades ouverts : asset → {entry, sl, tp, side, qty, order_id, open_time, peak_price}
        self._live_trades: dict[str, dict] = {}

        # Chemin de persistance
        self._trades_path = Path(config.get("vault_path", "vault")) / "config" / "open_trades.json"

    # ── Setup ─────────────────────────────────────────────────────────────────

    @property
    def is_live(self) -> bool:
        """True si on exécute des ordres réels sur l'exchange."""
        return self._trading_mode is not None and self._trading_mode.execute_real_orders

    @property
    def is_paper(self) -> bool:
        """True si on est en mode paper (données réelles, ordres simulés)."""
        return self._trading_mode is not None and self._trading_mode.is_paper

    async def setup(self) -> None:
        mode_label = self._trading_mode.mode.value if self._trading_mode else "simulation"
        use_testnet = self.config.get("binance_testnet", False)

        try:
            import ccxt.async_support as ccxt

            if "binance" in self.config.get("exchanges", []):
                api_key = self.config.get("binance_api_key", "")
                secret = self.config.get("binance_secret", "")

                if not api_key or not secret:
                    logger.warning("[%s] Cles API Binance vides — execution simulee", self.name)
                else:
                    exchange_opts = {
                        "apiKey": api_key,
                        "secret": secret,
                        "enableRateLimit": True,
                        "options": {"defaultType": "spot"},
                    }

                    # Binance Testnet pour le mode PAPER ou test
                    if use_testnet:
                        exchange_opts["urls"] = {
                            "api": {
                                "public":  "https://testnet.binance.vision/api/v3",
                                "private": "https://testnet.binance.vision/api/v3",
                            },
                        }
                        logger.info("[%s] Mode TESTNET Binance active", self.name)

                    self._exchanges["binance"] = ccxt.binance(exchange_opts)

                    # Vérifier la connexion en mode LIVE/PAPER
                    if self.is_live or self.is_paper:
                        try:
                            balance = await self._exchanges["binance"].fetch_balance()
                            usdt_free = float(balance.get("USDT", {}).get("free", 0))
                            usdt_total = float(balance.get("USDT", {}).get("total", 0))
                            logger.info(
                                "[%s] Binance connecte — USDT: $%.2f libre / $%.2f total%s",
                                self.name, usdt_free, usdt_total,
                                " (TESTNET)" if use_testnet else "",
                            )
                        except Exception as exc:
                            logger.error(
                                "[%s] ECHEC connexion Binance: %s — passage en simulation",
                                self.name, exc,
                            )
                            await self._exchanges["binance"].close()
                            self._exchanges.clear()

        except ImportError:
            logger.warning("[%s] ccxt absent — execution simulee", self.name)

        # Recharger les trades ouverts depuis le disque
        self._load_open_trades()

        if self._live_trades:
            logger.info(
                "[%s] %d trade(s) ouvert(s) restaure(s) depuis le disque : %s",
                self.name, len(self._live_trades), list(self._live_trades.keys()),
            )

        # Résumé du mode
        has_exchange = bool(self._exchanges)
        logger.info(
            "[%s] Mode: %s | Exchange: %s | Ordres reels: %s%s",
            self.name, mode_label.upper(),
            list(self._exchanges.keys()) if has_exchange else "aucun (simule)",
            "OUI" if (self.is_live and has_exchange) else "NON",
            " | TESTNET" if use_testnet else "",
        )

    def _register_subscriptions(self) -> None:
        self.bus.subscribe(CHANNELS["orders_validated"], self._on_order)

    # ── Persistance des trades ouverts ────────────────────────────────────────

    def _load_open_trades(self) -> None:
        """Charge les trades ouverts depuis vault/config/open_trades.json."""
        if not self._trades_path.exists():
            return
        try:
            data = json.loads(self._trades_path.read_text(encoding="utf-8"))
            self._live_trades = data
            logger.info("[%s] 📂 %d trade(s) ouvert(s) chargé(s)", self.name, len(data))
        except Exception as exc:
            logger.warning("[%s] Erreur chargement open_trades.json: %s", self.name, exc)

    def _save_open_trades(self) -> None:
        """Persiste les trades ouverts sur disque."""
        try:
            self._trades_path.parent.mkdir(parents=True, exist_ok=True)
            self._trades_path.write_text(
                json.dumps(self._live_trades, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[%s] Erreur sauvegarde open_trades.json: %s", self.name, exc)

    # ── Cycle ─────────────────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        if len(self._history) >= 5:
            pass  # vault/execution/slippage_model supprimé — slippage déjà dans _history (mémoire)

        # Vérifier les trades ouverts avec les prix réels
        await self._check_trades_real_prices()

    # ── Exécution d'ordre ─────────────────────────────────────────────────────

    async def _on_order(self, data: dict) -> None:
        asset    = data.get("asset", "?")
        order_id = data.get("order_id", "?")
        logger.info("[%s] 📨 Ordre %s : %s %s", self.name, order_id, data.get("side"), asset)

        # Vérifier qu'on n'a pas déjà un trade ouvert sur cet asset
        if asset in self._live_trades:
            logger.warning(
                "[%s] ⚠️  Trade déjà ouvert sur %s (order %s) — ordre ignoré",
                self.name, asset, self._live_trades[asset].get("order_id"),
            )
            return

        for attempt in range(1, MAX_RETRY + 1):
            try:
                report = await self._execute(data)
                if report:
                    # Journaliser le slippage par heure
                    hour = datetime.now(timezone.utc).hour
                    self._slippage_by_hour[hour].append(report.slippage_bps)
                    self._history.append(report.to_dict())

                    # vault/execution/exec_* supprimé — rapport déjà publié sur le bus
                    # et persisté dans _history (→ slippage_by_hour). Aucun agent ne relisait.
                    await self.bus.publish(CHANNELS["orders_executed"], report.to_dict())

                    # Enregistrer le trade ouvert + persister
                    self._live_trades[asset] = {
                        "order_id":   data.get("order_id"),
                        "entry":      report.filled_price,
                        "sl":         data.get("stop_loss", 0),
                        "tp":         data.get("take_profit", 0),
                        "side":       data.get("side", "buy"),
                        "qty":        data.get("quantity", 0),
                        "open_time":  datetime.now(timezone.utc).isoformat(),
                        "peak_price": report.filled_price,  # MFE tracking
                    }
                    self._save_open_trades()
                    logger.info(
                        "[%s] 📂 Trade ouvert persisté : %s %s @ %.6f | SL=%.6f | TP=%.6f",
                        self.name, data.get("side"), asset, report.filled_price,
                        data.get("stop_loss", 0), data.get("take_profit", 0),
                    )
                    return
            except Exception as exc:
                logger.warning("[%s] Tentative %d/%d : %s", self.name, attempt, MAX_RETRY, exc)
                if attempt < MAX_RETRY:
                    await asyncio.sleep(RETRY_DELAY)

        # Échec définitif
        await self.bus.publish(CHANNELS["orders_executed"], {
            "type": "execution_report", "order_id": order_id,
            "asset": asset, "status": OrderStatus.REJECTED.value,
            "exit_reason": "rejected",
        })

    # ── Suivi des trades par prix réels ──────────────────────────────────────

    async def _check_trades_real_prices(self) -> None:
        """
        Chaque cycle, récupère le prix actuel via MarketDataManager
        et vérifie si le SL ou TP est touché.

        PLUS DE random.random() — le marché décide.
        """
        if not self._live_trades:
            return

        now_str = datetime.now(timezone.utc).isoformat()
        to_close = []

        # Log des positions ouvertes
        open_summary = {}
        for asset, trade in self._live_trades.items():
            current_price = self._get_current_price(asset)
            if current_price:
                entry = trade["entry"]
                pnl_pct = ((current_price - entry) / entry * 100) if trade["side"] == "buy" \
                    else ((entry - current_price) / entry * 100)
                open_summary[asset] = f"{'🟢' if pnl_pct >= 0 else '🔴'}{pnl_pct:+.2f}%"
            else:
                open_summary[asset] = "❓ pas de prix"

        if open_summary:
            logger.info("[%s] 📋 Positions ouvertes : %s", self.name, open_summary)

        for asset, trade in list(self._live_trades.items()):
            current_price = self._get_current_price(asset)

            if current_price is None:
                logger.debug("[%s] ⚠️  Pas de prix actuel pour %s — skip", self.name, asset)
                continue

            entry = trade["entry"]
            sl    = trade["sl"]
            tp    = trade["tp"]
            side  = trade["side"]

            # Mettre à jour le peak price (pour MFE tracking)
            if side == "buy":
                if current_price > trade.get("peak_price", entry):
                    trade["peak_price"] = current_price
            else:
                if current_price < trade.get("peak_price", entry):
                    trade["peak_price"] = current_price

            # Vérifier SL/TP
            exit_price  = None
            exit_reason = None

            if side == "buy":
                if sl and current_price <= sl:
                    exit_price  = sl
                    exit_reason = "stop_loss"
                elif tp and current_price >= tp:
                    exit_price  = tp
                    exit_reason = "take_profit"
            else:  # sell
                if sl and current_price >= sl:
                    exit_price  = sl
                    exit_reason = "stop_loss"
                elif tp and current_price <= tp:
                    exit_price  = tp
                    exit_reason = "take_profit"

            if exit_reason:
                pnl_pct = ((exit_price - entry) / entry * 100) if side == "buy" \
                    else ((entry - exit_price) / entry * 100)
                is_win = pnl_pct > 0

                logger.info(
                    "[%s] 🔔 %s %s → %s @ %.6f (entrée: %.6f | P&L: %+.2f%%)",
                    self.name, exit_reason.upper(), asset,
                    "✅ WIN" if is_win else "❌ LOSS",
                    exit_price, entry, pnl_pct,
                )

                # Calculer le PnL en USD
                pnl_usd = trade["qty"] * (exit_price - entry) if side == "buy" \
                    else trade["qty"] * (entry - exit_price)
                fees = round(trade["qty"] * exit_price * 0.001, 6)

                await self.bus.publish(CHANNELS["orders_executed"], {
                    "type":         "execution_report",
                    "order_id":     trade["order_id"],
                    "asset":        asset,
                    "side":         side,
                    "entry_price":  round(entry, 6),
                    "filled_price": round(exit_price, 6),
                    "quantity":     trade["qty"],
                    "fees":         fees,
                    "pnl_usd":     round(pnl_usd - fees, 2),
                    "pnl_pct":     round(pnl_pct, 4),
                    "is_win":      is_win,
                    "status":       exit_reason,
                    "exit_reason":  exit_reason,
                    "exchange":     "binance" if self.is_live else ("binance_paper" if self.is_paper else "binance_sim"),
                    "peak_price":   trade.get("peak_price", entry),
                })

                to_close.append(asset)

        # Nettoyer et persister
        if to_close:
            for asset in to_close:
                self._live_trades.pop(asset, None)
            self._save_open_trades()

    def _get_current_price(self, pair: str) -> Optional[float]:
        """
        Récupère le prix actuel via MarketDataManager.
        Retourne None si aucune donnée disponible (PAS de prix inventé).
        """
        if self._market_data and self._market_data.is_ready():
            price = self._market_data.get_last_price(pair)
            if price and price > 0:
                return price

        # Fallback : dernière candle 1m du MarketDataManager
        if self._market_data:
            candles = self._market_data.get_candles(pair, "1m", 1)
            if candles:
                return float(candles[-1].c)

        # PAS de simulation — retourner None (le trade reste ouvert)
        logger.warning(
            "[%s] ⚠️  Aucun prix disponible pour %s — trade reste ouvert",
            self.name, pair,
        )
        return None

    # ── Exécution des ordres ─────────────────────────────────────────────────

    async def _execute(self, data: dict) -> Optional[ExecutionReport]:
        if self._is_forex(data.get("asset", "")):
            return await self._exec_oanda(data)
        return await self._exec_binance(data)

    async def _exec_binance(self, data: dict) -> Optional[ExecutionReport]:
        # Mode simulation ou pas d'exchange connecté → simuler l'entrée
        if not self._exchanges or not self.is_live:
            label = "binance_paper" if self.is_paper else "binance_sim"
            return self._simulate_entry(data, label)

        exchange = self._exchanges.get("binance") or next(iter(self._exchanges.values()))
        asset = data["asset"]
        side = data["side"]
        qty = data["quantity"]

        try:
            # 1. Ordre market pour l'entrée
            raw = await exchange.create_market_order(asset, side, qty)
            filled = float(raw.get("average") or raw.get("price") or data["entry_price"])
            fee = (raw.get("fee") or {}).get("cost") or qty * filled * 0.001
            slip = abs(filled - data["entry_price"]) / data["entry_price"] * 10_000

            if slip > SLIPPAGE_ALERT_BPS:
                logger.warning("[%s] Slippage eleve : %.1f bps sur %s", self.name, slip, asset)

            # 2. Placer les ordres SL/TP sur l'exchange (OCO)
            sl_price = data.get("stop_loss", 0)
            tp_price = data.get("take_profit", 0)
            oco_ids = await self._place_sl_tp_orders(exchange, asset, side, qty, sl_price, tp_price, filled)

            return ExecutionReport(
                order_id=data["order_id"], asset=asset,
                side=OrderSide(side),
                requested_price=data["entry_price"], filled_price=filled,
                quantity=qty, fees=float(fee),
                slippage_bps=slip, exchange="binance",
                status=OrderStatus.FILLED,
                exchange_order_id=str(raw.get("id", "")),
            )

        except Exception as exc:
            logger.error("[%s] ERREUR execution reelle %s: %s", self.name, asset, exc)
            # En cas d'erreur sur un ordre réel, NE PAS simuler — rejeter
            raise

    async def _place_sl_tp_orders(
        self, exchange, asset: str, entry_side: str, qty: float,
        sl_price: float, tp_price: float, filled_price: float,
    ) -> dict:
        """
        Place des ordres SL et TP sur Binance pour proteger la position.
        En mode LIVE, le SL est sur l'exchange — si le bot crash, le SL tient.

        Retourne les IDs des ordres {sl_id, tp_id}.
        """
        result = {"sl_id": None, "tp_id": None}
        # Le côté de sortie est l'inverse de l'entrée
        exit_side = "sell" if entry_side == "buy" else "buy"

        try:
            # Stop-Loss : ordre stop-market
            if sl_price and sl_price > 0:
                sl_order = await exchange.create_order(
                    symbol=asset,
                    type="STOP_LOSS_LIMIT",
                    side=exit_side,
                    amount=qty,
                    price=sl_price,
                    params={
                        "stopPrice": sl_price,
                        "timeInForce": "GTC",
                    },
                )
                result["sl_id"] = sl_order.get("id")
                logger.info(
                    "[%s] SL place sur exchange: %s %s @ %.6f (id: %s)",
                    self.name, exit_side, asset, sl_price, result["sl_id"],
                )
        except Exception as exc:
            logger.error("[%s] Echec placement SL exchange %s: %s", self.name, asset, exc)

        try:
            # Take-Profit : ordre limit
            if tp_price and tp_price > 0:
                tp_order = await exchange.create_order(
                    symbol=asset,
                    type="TAKE_PROFIT_LIMIT",
                    side=exit_side,
                    amount=qty,
                    price=tp_price,
                    params={
                        "stopPrice": tp_price,
                        "timeInForce": "GTC",
                    },
                )
                result["tp_id"] = tp_order.get("id")
                logger.info(
                    "[%s] TP place sur exchange: %s %s @ %.6f (id: %s)",
                    self.name, exit_side, asset, tp_price, result["tp_id"],
                )
        except Exception as exc:
            logger.error("[%s] Echec placement TP exchange %s: %s", self.name, asset, exc)

        return result

    async def _exec_oanda(self, data: dict) -> Optional[ExecutionReport]:
        if not self._oanda_api:
            return self._simulate_entry(data, "oanda_sim")
        import oandapyV20.endpoints.orders as ep
        instrument = data["asset"].replace("/", "_")
        units = data["quantity"] * (-1 if data["side"] == "sell" else 1)
        req  = ep.OrderCreate(self.config["oanda_account"], data={
            "order": {"type": "MARKET", "instrument": instrument, "units": str(int(units))}
        })
        resp  = self._oanda_api.request(req)
        fill  = resp.get("orderFillTransaction", {})
        price = float(fill.get("price", data["entry_price"]))
        slip  = abs(price - data["entry_price"]) / data["entry_price"] * 10_000
        return ExecutionReport(
            order_id=data["order_id"], asset=data["asset"],
            side=OrderSide(data["side"]),
            requested_price=data["entry_price"], filled_price=price,
            quantity=abs(units), fees=float(fill.get("commission", {}).get("amount", 0)),
            slippage_bps=slip, exchange="oanda",
            status=OrderStatus.FILLED,
            exchange_order_id=fill.get("id", ""),
        )

    @staticmethod
    def _simulate_entry(data: dict, exchange: str) -> ExecutionReport:
        """
        Simule l'ENTRÉE d'un ordre (slippage réaliste).
        Note : la SORTIE est gérée par _check_trades_real_prices() — prix réels.
        """
        # Slippage d'entrée basé sur une estimation réaliste (2-5 bps)
        import random
        slip  = random.uniform(1.0, 5.0)
        side  = data.get("side", "buy")
        # Slippage défavorable : on achète un peu plus cher, on vend un peu moins cher
        if side == "buy":
            fill = data["entry_price"] * (1 + slip / 10_000)
        else:
            fill = data["entry_price"] * (1 - slip / 10_000)
        fees  = data["quantity"] * fill * 0.001
        return ExecutionReport(
            order_id=data["order_id"], asset=data["asset"],
            side=OrderSide(side),
            requested_price=data["entry_price"], filled_price=round(fill, 6),
            quantity=data["quantity"], fees=round(fees, 6),
            slippage_bps=round(slip, 2), exchange=exchange,
            status=OrderStatus.FILLED,
        )

    # ── Vault Obsidian ────────────────────────────────────────────────────────

    def _write_execution_note(self, r: ExecutionReport) -> None:
        filename = self.obsidian.timestamp_filename("exec", r.asset, r.timestamp)
        hour = r.timestamp.hour
        avg_slip_this_hour = (
            statistics.mean(self._slippage_by_hour[hour])
            if self._slippage_by_hour[hour] else None
        )
        slip_vs_avg = (
            f"`{r.slippage_bps - avg_slip_this_hour:+.1f} bps vs. heure {hour}h`"
            if avg_slip_this_hour else "—"
        )

        frontmatter = {
            "date":        r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "agent":       "ExecuteAgent",
            "asset":       r.asset,
            "signal":      r.side.value,
            "confiance":   100,
            "tags":        ["execution", r.exchange],
            "order_id":    r.order_id,
            "slippage_bps":r.slippage_bps,
        }

        sl_icon = "⚠️" if r.slippage_bps > SLIPPAGE_ALERT_BPS else "✅"

        content = f"""## Rapport d'Exécution — {r.asset}

| Champ | Valeur |
|---|---|
| Ordre ID | `{r.order_id}` |
| Direction | **{r.side.value.upper()}** |
| Prix demandé | `{r.requested_price}` |
| Prix obtenu | `{r.filled_price}` |
| Slippage | `{r.slippage_bps:.2f} bps` {sl_icon} |
| vs. moy. heure {hour}h | {slip_vs_avg} |
| Quantité | `{r.quantity}` |
| Frais | `{r.fees:.6f}` |
| Coût total | `{r.total_cost:.4f}` |
| Exchange | `{r.exchange}` |
| Statut | ✅ `{r.status.value}` |

### Liens
{self.obsidian.wikilink('risque', self.obsidian.timestamp_filename('risque_decision', r.asset))}
"""
        self.obsidian.write_note("execution", filename, frontmatter, content)
        logger.info(
            "[%s] ✅ %s @ %.6f | slippage %.2f bps | frais %.4f",
            self.name, r.asset, r.filled_price, r.slippage_bps, r.fees,
        )

    def _write_slippage_model(self) -> None:
        """Modèle de slippage par heure pour optimiser les horaires d'exécution."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []
        for h in range(24):
            vals = self._slippage_by_hour[h]
            if vals:
                avg  = statistics.mean(vals)
                best = min(vals)
                icon = "🟢" if avg < 5 else ("🟡" if avg < 15 else "🔴")
                rows.append(f"| `{h:02d}:00` UTC | `{avg:.1f}` | `{best:.1f}` | {icon} |")

        rows_md = "\n".join(rows) or "| — | — | — | — |"

        best_hour = min(
            (h for h in range(24) if self._slippage_by_hour[h]),
            key=lambda h: statistics.mean(self._slippage_by_hour[h]),
            default=None,
        )

        frontmatter = {"date": date_str, "agent": "ExecuteAgent", "tags": ["execution", "slippage"]}
        content = f"""## Modèle de Slippage — {date_str}

### Slippage par Heure UTC (bps)
| Heure | Moy. (bps) | Min (bps) | Qualité |
|---|---|---|---|
{rows_md}

### Recommandation
**Meilleure heure d'exécution : `{best_hour:02d}:00 UTC`** (slippage minimal historique)

### Résumé Global
- Ordres analysés : **{len(self._history)}**
- Slippage moyen global : **{statistics.mean(r['slippage_bps'] for r in self._history):.2f} bps**
"""
        self.obsidian.write_note("execution", f"slippage_model_{date_str}", frontmatter, content)

    async def cleanup(self) -> None:
        """Ferme les connexions exchange proprement."""
        for name, exchange in self._exchanges.items():
            try:
                await exchange.close()
                logger.info("[%s] Exchange %s ferme", self.name, name)
            except Exception as exc:
                logger.warning("[%s] Erreur fermeture %s: %s", self.name, name, exc)
        self._exchanges.clear()

    @staticmethod
    def _is_forex(pair: str) -> bool:
        FIAT = {"EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}
        return len(set(pair.replace("/", " ").upper().split()) & FIAT) >= 2
