"""
MarketDataManager — Source unique de vérité pour toutes les données de marché.

Architecture complémentaire :
  WebSocket  → prix tick-by-tick, klines 1m en temps réel, réaction immédiate
  REST       → historique OHLCV 1h/4h/1d, order book snapshot, contexte long terme

Les agents appellent get_candles(), get_ticker(), get_orderbook() sans se soucier
de l'origine (WS ou REST) — le manager choisit la meilleure source disponible.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

BINANCE_REST = "https://api.binance.com/api/v3"
BINANCE_WS   = "wss://stream.binance.com:9443/stream"

# Nombre de candles conservées par (symbol, timeframe)
CANDLE_BUFFER = {"1m": 200, "5m": 100, "1h": 200, "4h": 100, "1d": 60}

# Mapping pair de trading → symbole Binance
PAIR_TO_SYMBOL: dict[str, str] = {
    "BTC/USDT": "BTCUSDT", "ETH/USDT": "ETHUSDT",
    "SOL/USDT": "SOLUSDT", "BNB/USDT": "BNBUSDT",
    "EUR/USD":  "EURUSDT",
}
SYMBOL_TO_PAIR: dict[str, str] = {v: k for k, v in PAIR_TO_SYMBOL.items()}


class Candle:
    __slots__ = ("t", "o", "h", "l", "c", "v", "closed")

    def __init__(self, t, o, h, l, c, v, closed=True):
        self.t      = float(t)   # unix timestamp (s)
        self.o      = float(o)
        self.h      = float(h)
        self.l      = float(l)
        self.c      = float(c)
        self.v      = float(v)   # volume
        self.closed = bool(closed)


class MarketDataManager:
    """
    Gestionnaire centralisé des données de marché.

    Usage :
        mdm = MarketDataManager(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        await mdm.start()          # lance WS + fetch historique initial
        candles = mdm.get_candles("BTC/USDT", "1h", 100)
        ticker  = mdm.get_ticker("BTC/USDT")
        book    = mdm.get_orderbook("BTC/USDT")
        await mdm.stop()
    """

    def __init__(self, pairs: list[str], ws_timeframes: list[str] = None, rate_limiter=None):
        self.pairs       = pairs
        self.symbols     = [PAIR_TO_SYMBOL[p] for p in pairs if p in PAIR_TO_SYMBOL]
        self.ws_tfs      = ws_timeframes or ["1m", "1h"]
        self._rate_limiter = rate_limiter

        # Candle buffers : {symbol: {timeframe: deque[Candle]}}
        self._candles: dict[str, dict[str, deque]] = {
            s: {tf: deque(maxlen=CANDLE_BUFFER.get(tf, 100)) for tf in CANDLE_BUFFER}
            for s in self.symbols
        }

        # Ticker cache : {symbol: dict}
        self._tickers: dict[str, dict] = {}

        # Order book cache : {symbol: {"bids": [...], "asks": [...], "ts": float}}
        self._books: dict[str, dict] = {}

        # VWAP intraday : {symbol: (cum_pv, cum_v)}
        self._vwap: dict[str, tuple] = {}

        # ── Order Flow / CVD ──────────────────────────────────────────────────
        # CVD (Cumulative Volume Delta) : buy_vol - sell_vol
        self._cvd: dict[str, float] = {s: 0.0 for s in self.symbols}
        # Delta par candle 1m (deque de (timestamp, delta))
        self._delta_1m: dict[str, deque] = {
            s: deque(maxlen=200) for s in self.symbols
        }
        # Dernier delta minute en cours
        self._current_minute_delta: dict[str, dict] = {
            s: {"minute": 0, "delta": 0.0, "buy_vol": 0.0, "sell_vol": 0.0}
            for s in self.symbols
        }

        # ── Anchored VWAP ─────────────────────────────────────────────────────
        # Ancré au swing low/high du jour ou dernière 4h
        self._anchored_vwap: dict[str, dict] = {}
        # Format: {symbol: {"anchor_price": float, "anchor_ts": float, "pv": float, "v": float, "value": float}}

        self._http:     Optional[httpx.AsyncClient] = None
        self._ws_task:  Optional[asyncio.Task]      = None
        self._agg_task: Optional[asyncio.Task]      = None
        self._ob_task:  Optional[asyncio.Task]      = None
        self._running   = False
        self._ready     = asyncio.Event()           # True quand historique chargé
        self._last_ws_message_time: float = 0.0     # détection de données périmées

    # ── Démarrage ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._http    = httpx.AsyncClient(timeout=15)
        self._running = True

        # 1. Charger l'historique REST pour tous les timeframes
        await self._load_history()

        # 2. Lancer le WebSocket pour les klines temps réel
        self._ws_task = asyncio.create_task(self._ws_kline_loop(), name="mdm:ws_kline")

        # 3. Lancer le poll order book toutes les 5s
        self._ob_task = asyncio.create_task(self._orderbook_loop(), name="mdm:orderbook")

        # 4. Lancer le WebSocket aggTrades pour order flow / CVD
        self._agg_task = asyncio.create_task(self._ws_aggtrades_loop(), name="mdm:ws_aggtrades")

        # 5. Initialiser les Anchored VWAP
        self._init_anchored_vwaps()

        self._ready.set()
        logger.info("[MarketData] ✅ Démarré — %d paires | WS: klines+aggTrades", len(self.symbols))

    async def stop(self) -> None:
        self._running = False
        for t in [self._ws_task, self._ob_task, self._agg_task]:
            if t:
                t.cancel()
        if self._http:
            await self._http.aclose()
        logger.info("[MarketData] Arrêté")

    # ── API publique ──────────────────────────────────────────────────────────

    def get_candles(self, pair: str, timeframe: str, limit: int = 100) -> list[Candle]:
        """Retourne les N dernières candles fermées (source WS ou REST selon dispo)."""
        sym = PAIR_TO_SYMBOL.get(pair)
        if not sym:
            return []
        buf = self._candles.get(sym, {}).get(timeframe, deque())
        candles = [c for c in buf if c.closed]
        return list(candles)[-limit:]

    def get_ticker(self, pair: str) -> dict:
        """Ticker 24h : lastPrice, priceChangePercent, quoteVolume, etc."""
        sym = PAIR_TO_SYMBOL.get(pair)
        return self._tickers.get(sym, {})

    def get_orderbook(self, pair: str, depth: int = 10) -> dict:
        """Order book snapshot : bids / asks (les N meilleurs niveaux)."""
        sym = PAIR_TO_SYMBOL.get(pair)
        book = self._books.get(sym, {"bids": [], "asks": [], "ts": 0})
        return {
            "bids":      book["bids"][:depth],
            "asks":      book["asks"][:depth],
            "imbalance": self._book_imbalance(book["bids"][:depth], book["asks"][:depth]),
            "spread_pct": self._spread_pct(book),
            "ts":        book["ts"],
        }

    def get_last_price(self, pair: str) -> Optional[float]:
        """Dernier prix connu pour une paire (ticker WS ou REST, puis fallback dernière candle 1m)."""
        sym = PAIR_TO_SYMBOL.get(pair)
        if not sym:
            return None
        # 1. Ticker (mis à jour en temps réel via WS ou REST polling)
        ticker = self._tickers.get(sym, {})
        price = ticker.get("lastPrice")
        if price and price > 0:
            return float(price)
        # 2. Fallback : dernière candle 1m fermée
        buf = self._candles.get(sym, {}).get("1m", deque())
        if buf:
            return float(buf[-1].c)
        return None

    def get_vwap(self, pair: str) -> Optional[float]:
        """VWAP intraday calculé sur les candles 1m disponibles."""
        sym = PAIR_TO_SYMBOL.get(pair)
        pv, v = self._vwap.get(sym, (0.0, 0.0))
        return pv / v if v > 0 else None

    def get_cvd(self, pair: str) -> float:
        """CVD (Cumulative Volume Delta) = somme(buy_vol - sell_vol) depuis le démarrage."""
        sym = PAIR_TO_SYMBOL.get(pair)
        return self._cvd.get(sym, 0.0)

    def get_delta_history(self, pair: str, limit: int = 60) -> list[tuple[float, float]]:
        """Historique du delta par minute. Retourne [(timestamp, delta), ...]."""
        sym = PAIR_TO_SYMBOL.get(pair)
        buf = self._delta_1m.get(sym, deque())
        return list(buf)[-limit:]

    def get_order_flow(self, pair: str) -> dict:
        """
        Métriques d'order flow combinées :
        - cvd : CVD cumulé
        - delta_1m : delta de la dernière minute
        - delta_5m : delta moyen sur 5 min
        - delta_divergence : True si prix monte et CVD baisse (ou inverse)
        - absorption : True si gros volume mais peu de mouvement de prix
        """
        sym = PAIR_TO_SYMBOL.get(pair)
        if not sym:
            return {}

        cvd = self._cvd.get(sym, 0.0)
        cur = self._current_minute_delta.get(sym, {})
        delta_1m = cur.get("delta", 0.0)

        # Delta 5 min
        history = list(self._delta_1m.get(sym, deque()))
        delta_5m = sum(d for _, d in history[-5:]) if len(history) >= 5 else delta_1m

        # Delta divergence : prix monte mais delta baisse sur 5 min
        candles = self.get_candles(pair, "1m", 5)
        price_change = 0.0
        if len(candles) >= 2:
            price_change = (candles[-1].c - candles[0].c) / candles[0].c * 100

        delta_divergence = (price_change > 0.1 and delta_5m < 0) or \
                           (price_change < -0.1 and delta_5m > 0)

        # Absorption : gros volume, petit mouvement
        total_vol = cur.get("buy_vol", 0) + cur.get("sell_vol", 0)
        absorption = False
        if len(candles) >= 1 and total_vol > 0:
            last_range_pct = abs(candles[-1].h - candles[-1].l) / candles[-1].c * 100
            avg_vol = np.mean([c.v for c in candles]) if candles else 1
            if total_vol > avg_vol * 1.5 and last_range_pct < 0.1:
                absorption = True

        return {
            "cvd":              cvd,
            "delta_1m":         delta_1m,
            "delta_5m":         delta_5m,
            "delta_divergence": delta_divergence,
            "absorption":       absorption,
            "buy_vol_1m":       cur.get("buy_vol", 0.0),
            "sell_vol_1m":      cur.get("sell_vol", 0.0),
        }

    def get_anchored_vwap(self, pair: str) -> Optional[dict]:
        """
        Anchored VWAP ancré au swing low/high récent.
        Retourne {"value": float, "anchor_price": float, "anchor_ts": float, "dist_pct": float}
        """
        sym = PAIR_TO_SYMBOL.get(pair)
        data = self._anchored_vwap.get(sym)
        if not data or data.get("v", 0) <= 0:
            return None
        value = data["pv"] / data["v"]
        price = self.get_last_price(pair)
        dist_pct = ((price - value) / value * 100) if price and value > 0 else 0.0
        return {
            "value":        round(value, 6),
            "anchor_price": data["anchor_price"],
            "anchor_ts":    data["anchor_ts"],
            "dist_pct":     round(dist_pct, 3),
        }

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def is_data_stale(self, max_age_seconds: float = 120) -> bool:
        """True si aucun message WS reçu depuis max_age_seconds."""
        if self._last_ws_message_time == 0:
            return False  # pas encore démarré
        return (time.time() - self._last_ws_message_time) > max_age_seconds

    # ── Chargement historique REST ─────────────────────────────────────────────

    async def _load_history(self) -> None:
        """Charge l'historique OHLCV via REST pour tous symbols et timeframes."""
        tasks = []
        for sym in self.symbols:
            for tf in CANDLE_BUFFER:
                tasks.append(self._fetch_klines_rest(sym, tf, CANDLE_BUFFER[tf]))
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("[MarketData] Historique chargé (%d×%d flux)", len(self.symbols), len(CANDLE_BUFFER))

    async def _fetch_klines_rest(self, symbol: str, interval: str, limit: int) -> None:
        try:
            if self._rate_limiter:
                await self._rate_limiter.acquire("binance_rest")
            r = await self._http.get(f"{BINANCE_REST}/klines", params={
                "symbol": symbol, "interval": interval, "limit": limit,
            })
            r.raise_for_status()
            buf = self._candles[symbol][interval]
            for row in r.json():
                # [open_time, open, high, low, close, volume, close_time, ...]
                buf.append(Candle(
                    t=row[0] / 1000, o=row[1], h=row[2],
                    l=row[3], c=row[4], v=row[5], closed=True,
                ))
            # VWAP intraday sur les 1m
            if interval == "1m":
                self._rebuild_vwap(symbol)
            logger.debug("[MarketData] REST %s/%s → %d candles", symbol, interval, len(buf))
        except Exception as exc:
            logger.warning("[MarketData] REST klines %s/%s : %s", symbol, interval, exc)

    # ── WebSocket klines temps réel ────────────────────────────────────────────

    async def _ws_kline_loop(self) -> None:
        """Connexion WebSocket Binance combined stream, reconnexion avec backoff exponentiel."""
        try:
            import websockets
        except ImportError:
            logger.warning("[MarketData] websockets absent — WS désactivé, REST polling actif")
            asyncio.create_task(self._rest_poll_loop())
            return

        streams = "/".join(
            f"{s.lower()}@kline_{tf}"
            for s in self.symbols
            for tf in self.ws_tfs
        ) + "/" + "/".join(f"{s.lower()}@ticker" for s in self.symbols)

        url = f"{BINANCE_WS}?streams={streams}"
        consecutive_errors = 0
        _WS_BACKOFF_BASE = 5
        _WS_BACKOFF_MAX = 120

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("[MarketData] 🔌 WebSocket connecté (%d streams)", len(streams.split("/")))
                    consecutive_errors = 0  # reset on successful connection
                    self._last_ws_message_time = time.time()
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            self._handle_ws_message(msg)
                            self._last_ws_message_time = time.time()
                        except Exception as e:
                            logger.debug("[MarketData] WS parse error: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._running:
                    consecutive_errors += 1
                    backoff = min(_WS_BACKOFF_BASE * (2 ** (consecutive_errors - 1)), _WS_BACKOFF_MAX)
                    logger.warning(
                        "[MarketData] WS déconnecté (%s) — reconnexion dans %ds (attempt #%d)",
                        exc, backoff, consecutive_errors,
                    )
                    await asyncio.sleep(backoff)

    def _handle_ws_message(self, msg: dict) -> None:
        data   = msg.get("data", {})
        stream = msg.get("stream", "")

        # Kline update
        if "@kline_" in stream:
            k      = data.get("k", {})
            symbol = k.get("s", "")
            tf     = k.get("i", "")
            if symbol in self._candles and tf in self._candles[symbol]:
                c = Candle(
                    t=k["t"] / 1000, o=k["o"], h=k["h"],
                    l=k["l"], c=k["c"], v=k["v"],
                    closed=k.get("x", False),
                )
                buf = self._candles[symbol][tf]
                # Remplacer la dernière candle si même timestamp, sinon append
                if buf and buf[-1].t == c.t:
                    buf[-1] = c
                else:
                    buf.append(c)
                if tf == "1m":
                    self._update_vwap(symbol, c)

        # Ticker 24h
        elif "@ticker" in stream:
            symbol = data.get("s", "")
            if symbol:
                self._tickers[symbol] = {
                    "lastPrice":            float(data.get("c", 0)),
                    "priceChangePercent":   float(data.get("P", 0)),
                    "quoteVolume":          float(data.get("q", 0)),
                    "highPrice":            float(data.get("h", 0)),
                    "lowPrice":             float(data.get("l", 0)),
                    "openPrice":            float(data.get("o", 0)),
                    "ts":                   time.time(),
                }

    # ── Fallback REST polling (si websockets absent) ──────────────────────────

    async def _rest_poll_loop(self) -> None:
        """Polling REST toutes les 30s si WebSocket non disponible, avec backoff."""
        consecutive_errors = 0
        while self._running:
            try:
                for sym in self.symbols:
                    await self._fetch_klines_rest(sym, "1m",  50)
                    await self._fetch_klines_rest(sym, "1h",  50)
                    await self._fetch_ticker_rest(sym)
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                logger.warning("[MarketData] REST poll error (#%d): %s", consecutive_errors, exc)
            delay = min(30 * (2 ** max(consecutive_errors - 1, 0)), 300)
            await asyncio.sleep(delay)

    async def _fetch_ticker_rest(self, symbol: str) -> None:
        try:
            if self._rate_limiter:
                await self._rate_limiter.acquire("binance_rest")
            r = await self._http.get(f"{BINANCE_REST}/ticker/24hr", params={"symbol": symbol})
            r.raise_for_status()
            d = r.json()
            self._tickers[symbol] = {
                "lastPrice":          float(d.get("lastPrice", 0)),
                "priceChangePercent": float(d.get("priceChangePercent", 0)),
                "quoteVolume":        float(d.get("quoteVolume", 0)),
                "highPrice":          float(d.get("highPrice", 0)),
                "lowPrice":           float(d.get("lowPrice", 0)),
                "openPrice":          float(d.get("openPrice", 0)),
                "ts":                 time.time(),
            }
        except Exception as exc:
            logger.debug("[MarketData] REST ticker %s: %s", symbol, exc)

    # ── Order Book loop ────────────────────────────────────────────────────────

    async def _orderbook_loop(self) -> None:
        """Poll order book REST toutes les 5s (WS orderbook = trop verbeux)."""
        while self._running:
            for sym in self.symbols:
                try:
                    if self._rate_limiter:
                        await self._rate_limiter.acquire("binance_rest")
                    r = await self._http.get(f"{BINANCE_REST}/depth",
                                              params={"symbol": sym, "limit": 20})
                    r.raise_for_status()
                    d = r.json()
                    self._books[sym] = {
                        "bids": [[float(p), float(q)] for p, q in d.get("bids", [])],
                        "asks": [[float(p), float(q)] for p, q in d.get("asks", [])],
                        "ts":   time.time(),
                    }
                except Exception as exc:
                    logger.debug("[MarketData] orderbook %s: %s", sym, exc)
            await asyncio.sleep(5)

    # ── Calculs VWAP ──────────────────────────────────────────────────────────

    def _rebuild_vwap(self, symbol: str) -> None:
        candles = list(self._candles[symbol]["1m"])
        if not candles:
            return
        pv = sum((c.h + c.l + c.c) / 3 * c.v for c in candles)
        v  = sum(c.v for c in candles)
        self._vwap[symbol] = (pv, v)

    def _update_vwap(self, symbol: str, c: Candle) -> None:
        pv, v = self._vwap.get(symbol, (0.0, 0.0))
        typical = (c.h + c.l + c.c) / 3
        self._vwap[symbol] = (pv + typical * c.v, v + c.v)

    # ── WebSocket aggTrades — Order Flow / CVD ──────────────────────────────

    async def _ws_aggtrades_loop(self) -> None:
        """WebSocket aggTrades pour calculer le CVD (buy vol - sell vol) en temps réel."""
        try:
            import websockets
        except ImportError:
            logger.warning("[MarketData] websockets absent — aggTrades désactivé")
            return

        streams = "/".join(f"{s.lower()}@aggTrade" for s in self.symbols)
        url = f"{BINANCE_WS}?streams={streams}"
        consecutive_errors = 0

        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("[MarketData] 🔌 aggTrades WS connecté (%d paires)", len(self.symbols))
                    consecutive_errors = 0
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            self._handle_aggtrade(msg.get("data", {}))
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._running:
                    consecutive_errors += 1
                    backoff = min(5 * (2 ** (consecutive_errors - 1)), 120)
                    logger.warning("[MarketData] aggTrades WS déconnecté: %s — retry %ds", exc, backoff)
                    await asyncio.sleep(backoff)

    def _handle_aggtrade(self, data: dict) -> None:
        """Traite un aggTrade Binance : {s: symbol, p: price, q: qty, m: is_buyer_maker}."""
        symbol = data.get("s", "")
        if symbol not in self._cvd:
            return

        price = float(data.get("p", 0))
        qty   = float(data.get("q", 0))
        vol   = price * qty  # volume en quote currency (USDT)

        # m=True → seller initiated (buyer is maker) → sell volume
        # m=False → buyer initiated → buy volume
        is_sell = data.get("m", False)
        delta = -vol if is_sell else vol

        # CVD cumulé
        self._cvd[symbol] += delta

        # Delta par minute
        minute = int(data.get("T", time.time() * 1000)) // 60000
        cur = self._current_minute_delta[symbol]
        if cur["minute"] != minute:
            # Sauvegarder la minute précédente
            if cur["minute"] > 0:
                self._delta_1m[symbol].append((cur["minute"] * 60, cur["delta"]))
            cur["minute"] = minute
            cur["delta"] = 0.0
            cur["buy_vol"] = 0.0
            cur["sell_vol"] = 0.0
        cur["delta"] += delta
        if is_sell:
            cur["sell_vol"] += vol
        else:
            cur["buy_vol"] += vol

        # Mise à jour Anchored VWAP avec chaque trade
        avwap = self._anchored_vwap.get(symbol)
        if avwap:
            typical = price
            avwap["pv"] += typical * vol
            avwap["v"]  += vol

    # ── Anchored VWAP ────────────────────────────────────────────────────────

    def _init_anchored_vwaps(self) -> None:
        """Initialise l'Anchored VWAP au swing low/high récent des candles 1h."""
        for sym in self.symbols:
            candles = list(self._candles[sym].get("1h", deque()))
            if len(candles) < 10:
                candles = list(self._candles[sym].get("1m", deque()))
            if len(candles) < 10:
                continue

            # Trouver le swing low et swing high des dernières candles
            lows  = [(c.l, c.t) for c in candles[-48:]]  # 48h max
            highs = [(c.h, c.t) for c in candles[-48:]]
            swing_low  = min(lows, key=lambda x: x[0])
            swing_high = max(highs, key=lambda x: x[0])

            # Ancrer au plus récent des deux (le swing le plus récent)
            if swing_low[1] > swing_high[1]:
                anchor_price, anchor_ts = swing_low
            else:
                anchor_price, anchor_ts = swing_high

            # Calculer AVWAP depuis l'ancre
            pv, v = 0.0, 0.0
            for c in candles:
                if c.t >= anchor_ts:
                    typical = (c.h + c.l + c.c) / 3
                    pv += typical * c.v
                    v  += c.v

            self._anchored_vwap[sym] = {
                "anchor_price": anchor_price,
                "anchor_ts":    anchor_ts,
                "pv":           pv,
                "v":            v,
            }
            pair = SYMBOL_TO_PAIR.get(sym, sym)
            avwap_val = pv / v if v > 0 else 0
            logger.debug(
                "[MarketData] Anchored VWAP %s = %.4f (ancré à %.4f)",
                pair, avwap_val, anchor_price,
            )

    # ── Métriques order book ──────────────────────────────────────────────────

    @staticmethod
    def _book_imbalance(bids: list, asks: list) -> float:
        """
        Imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        > 0 → pression acheteuse  |  < 0 → pression vendeuse
        """
        bid_vol = sum(q for _, q in bids)
        ask_vol = sum(q for _, q in asks)
        total   = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total if total > 0 else 0.0

    @staticmethod
    def _spread_pct(book: dict) -> float:
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if not bids or not asks:
            return 0.0
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid      = (best_bid + best_ask) / 2
        return (best_ask - best_bid) / mid * 100 if mid > 0 else 0.0

    # ── Indicateurs techniques sur données réelles ────────────────────────────

    def compute_indicators(self, pair: str, timeframe: str) -> dict:
        """
        Calcule RSI, MACD, Bollinger, ATR, VWAP distance sur les vraies candles.
        Retourné comme dict prêt à l'emploi pour ScanAgent.
        """
        candles = self.get_candles(pair, timeframe, 150)
        if len(candles) < 30:
            return {}

        closes = np.array([c.c for c in candles])
        highs  = np.array([c.h for c in candles])
        lows   = np.array([c.l for c in candles])
        vols   = np.array([c.v for c in candles])

        rsi   = self._rsi(closes, 14)
        macd, signal = self._macd(closes)
        bb_pos        = self._bb_position(closes, 20)
        atr           = self._atr(highs, lows, closes, 14)
        vwap          = self.get_vwap(pair)
        price         = float(closes[-1])

        return {
            "price":      price,
            "rsi":        float(rsi),
            "macd":       float(macd),
            "macd_signal":float(signal),
            "macd_hist":  float(macd - signal),
            "bb_position":float(bb_pos),  # 0=bas BB, 1=haut BB
            "atr":        float(atr),
            "atr_pct":    float(atr / price * 100) if price > 0 else 0,
            "volume":     float(vols[-1]),
            "vol_ratio":  float(vols[-1] / np.mean(vols[-20:])) if np.mean(vols[-20:]) > 0 else 1.0,
            "vwap":       vwap,
            "vwap_dist_pct": float((price - vwap) / vwap * 100) if vwap else 0,
            "trend_slope": float(np.polyfit(range(20), closes[-20:], 1)[0] / price * 100),
        }

    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> float:
        deltas = np.diff(closes)
        gains  = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_g  = np.mean(gains[-period:])
        avg_l  = np.mean(losses[-period:])
        if avg_l < 1e-10:
            return 95.0
        rs  = avg_g / avg_l
        rsi = 100 - 100 / (1 + rs)
        return float(np.clip(rsi, 5, 95))

    @staticmethod
    def _macd(closes: np.ndarray, fast=12, slow=26, sig=9) -> tuple[float, float]:
        def ema(x, n):
            k, out = 2/(n+1), [x[0]]
            for v in x[1:]:
                out.append(v * k + out[-1] * (1-k))
            return np.array(out)
        if len(closes) < slow + sig:
            return 0.0, 0.0
        e12    = ema(closes, fast)
        e26    = ema(closes, slow)
        macd_l = e12 - e26
        sig_l  = ema(macd_l[slow-fast:], sig)
        return float(macd_l[-1]), float(sig_l[-1])

    @staticmethod
    def _bb_position(closes: np.ndarray, period: int = 20) -> float:
        """Position dans la bande Bollinger : 0=bas, 0.5=milieu, 1=haut."""
        if len(closes) < period:
            return 0.5
        w   = closes[-period:]
        mid = np.mean(w)
        std = np.std(w)
        if std < 1e-10:
            return 0.5
        return float(np.clip((closes[-1] - (mid - 2*std)) / (4*std), 0, 1))

    @staticmethod
    def _atr(highs, lows, closes, period=14) -> float:
        if len(closes) < 2:
            return 0.0
        tr = np.maximum(highs[1:] - lows[1:],
             np.maximum(abs(highs[1:] - closes[:-1]),
                        abs(lows[1:] - closes[:-1])))
        return float(np.mean(tr[-period:]))
