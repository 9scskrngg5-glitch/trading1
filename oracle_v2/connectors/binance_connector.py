"""
Binance Connector — WebSocket + REST pour ORACLE v2.
Implémente IConnector.

Améliorations v2.1 :
  - Implémente IConnector (contrat commun échangeable)
  - Rate limiting intégré (max 10 req/s, exponential backoff sur 429)
  - Heartbeat : ping() utilisé par ConnectorHealthCheck
  - Retourne des dataclasses IConnector standard (Ticker, BalanceInfo, OrderResult)
  - Gestion explicite des erreurs (ConnectorError / RateLimitError)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from .base_connector import (
    IConnector, Ticker, FundingInfo, OrderResult, BalanceInfo
)
from exceptions import ConnectorError, RateLimitError, ConnectorUnavailableError

logger = logging.getLogger("ORACLE.Binance")

_MAX_REQUESTS_PER_SEC = 10
_RATE_WINDOW = 1.0          # secondes
_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0         # secondes (exponentiel)


class BinanceConnector(IConnector):
    """
    Connecteur Binance Futures — REST via ccxt.
    Nécessite BINANCE_API_KEY et BINANCE_SECRET dans .env.
    Mode testnet par défaut (BINANCE_TESTNET=True).
    """

    def __init__(self, api_key: str, secret: str, testnet: bool = True):
        self.api_key = api_key
        self.secret = secret
        self.testnet = testnet
        self._client = None
        self._connected = False

        # Rate limiter
        self._request_times: list[float] = []
        self._rate_lock = asyncio.Lock()

        # Heartbeat
        self._last_ping: float = 0.0
        self._consecutive_failures: int = 0

    # ─── IConnector Interface ─────────────────────────────────────────

    @property
    def name(self) -> str:
        return "binance"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def initialize(self) -> None:
        """Initialise le client ccxt async. Idempotent."""
        if self._client and self._connected:
            return
        try:
            import ccxt.async_support as ccxt
            self._client = ccxt.binanceusdm({
                "apiKey": self.api_key,
                "secret": self.secret,
                "sandbox": self.testnet,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            })
            # Test de connectivité au démarrage
            await self._client.load_markets()
            self._connected = True
            self._consecutive_failures = 0
            logger.info(f"Binance connector initialisé (testnet={self.testnet})")
        except ImportError:
            raise ConnectorError("ccxt non installé — pip install ccxt")
        except Exception as e:
            self._connected = False
            raise ConnectorError(f"Binance init failed: {e}") from e

    async def ping(self) -> bool:
        """Teste la connectivité. Utilisé par ConnectorHealthCheck."""
        if not self._client:
            return False
        try:
            await self._throttle()
            await self._client.fetch_time()
            self._connected = True
            self._consecutive_failures = 0
            self._last_ping = time.time()
            return True
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(f"Binance ping failed ({self._consecutive_failures}): {e}")
            if self._consecutive_failures >= 2:
                self._connected = False
            return False

    # ─── Market Data ──────────────────────────────────────────────────

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> list[dict]:
        await self._ensure_initialized()
        for attempt in range(_MAX_RETRIES):
            try:
                await self._throttle()
                data = await self._client.fetch_ohlcv(symbol, timeframe, limit=limit)
                return [
                    {
                        "timestamp": c[0], "open": c[1], "high": c[2],
                        "low": c[3], "close": c[4], "volume": c[5],
                    }
                    for c in data
                ]
            except Exception as e:
                if self._is_rate_limit(e):
                    await self._handle_rate_limit(attempt, symbol)
                    continue
                logger.error(f"fetch_ohlcv {symbol}/{timeframe}: {e}")
                return []
        return []

    async def fetch_ticker(self, symbol: str) -> Optional[Ticker]:
        await self._ensure_initialized()
        for attempt in range(_MAX_RETRIES):
            try:
                await self._throttle()
                t = await self._client.fetch_ticker(symbol)
                return Ticker(
                    symbol=symbol,
                    bid=float(t.get("bid", 0) or 0),
                    ask=float(t.get("ask", 0) or 0),
                    last=float(t.get("last", 0) or 0),
                    volume_24h=float(t.get("quoteVolume", 0) or 0),
                    change_pct=float(t.get("percentage", 0) or 0) / 100,
                )
            except Exception as e:
                if self._is_rate_limit(e):
                    await self._handle_rate_limit(attempt, symbol)
                    continue
                logger.error(f"fetch_ticker {symbol}: {e}")
                return None
        return None

    async def fetch_orderbook(self, symbol: str, limit: int = 20) -> dict:
        await self._ensure_initialized()
        for attempt in range(_MAX_RETRIES):
            try:
                await self._throttle()
                ob = await self._client.fetch_order_book(symbol, limit=limit)
                return {"bids": ob.get("bids", []), "asks": ob.get("asks", [])}
            except Exception as e:
                if self._is_rate_limit(e):
                    await self._handle_rate_limit(attempt, symbol)
                    continue
                logger.error(f"fetch_orderbook {symbol}: {e}")
                return {"bids": [], "asks": []}
        return {"bids": [], "asks": []}

    async def fetch_balance(self) -> BalanceInfo:
        await self._ensure_initialized()
        for attempt in range(_MAX_RETRIES):
            try:
                await self._throttle()
                balance = await self._client.fetch_balance()
                usdt = balance.get("USDT", {})
                return BalanceInfo(
                    total=float(usdt.get("total", 0) or 0),
                    free=float(usdt.get("free", 0) or 0),
                    used=float(usdt.get("used", 0) or 0),
                )
            except Exception as e:
                if self._is_rate_limit(e):
                    await self._handle_rate_limit(attempt, symbol="balance")
                    continue
                logger.error(f"fetch_balance: {e}")
                return BalanceInfo(total=0, free=0, used=0)
        return BalanceInfo(total=0, free=0, used=0)

    async def fetch_funding_rate(self, symbol: str) -> Optional[FundingInfo]:
        await self._ensure_initialized()
        try:
            await self._throttle()
            fr = await self._client.fetch_funding_rate(symbol)
            oi_data = await self._client.fetch_open_interest(symbol)
            return FundingInfo(
                symbol=symbol,
                funding_rate=float(fr.get("fundingRate", 0) or 0),
                next_funding_time=int(fr.get("nextFundingTime", 0) or 0),
                open_interest=float(oi_data.get("openInterest", 0) or 0),
            )
        except Exception as e:
            logger.warning(f"fetch_funding_rate {symbol}: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[dict] = None,
    ) -> Optional[OrderResult]:
        """
        Place un ordre. TOUJOURS passer par SafetyKernel avant d'appeler.
        """
        await self._ensure_initialized()
        try:
            await self._throttle()
            raw = await self._client.create_order(
                symbol=symbol, type=order_type,
                side=side.lower(), amount=amount,
                price=price, params=params or {},
            )
            result = OrderResult(
                order_id=str(raw.get("id", "unknown")),
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                status=raw.get("status", "unknown"),
                filled_qty=float(raw.get("filled", 0) or 0),
                avg_price=float(raw.get("average", price or 0) or 0),
            )
            logger.info(
                f"Ordre placé: {side} {amount} {symbol} @ "
                f"{price or 'market'} | id={result.order_id}"
            )
            return result
        except Exception as e:
            if self._is_rate_limit(e):
                raise RateLimitError("binance", retry_after=60.0) from e
            logger.error(f"place_order {symbol}: {e}")
            return None

    async def fetch_position_symbols(self) -> list[str]:
        """
        Retourne la liste des symboles avec une position ouverte (size != 0).
        Appelé par SafetyKernel.reconcile() au démarrage live.
        """
        await self._ensure_initialized()
        try:
            await self._throttle()
            positions = await self._client.fetch_positions()
            return [
                p["symbol"]
                for p in positions
                if float(p.get("contracts", 0) or 0) != 0
            ]
        except Exception as e:
            logger.warning(f"fetch_position_symbols: {e} — reconcile ignoré")
            return []

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Binance connector fermé")

    # ─── Rate Limiter ─────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """
        Limite les requêtes à _MAX_REQUESTS_PER_SEC.
        Attend si nécessaire pour respecter la fenêtre de 1s.
        """
        async with self._rate_lock:
            now = time.monotonic()
            # Purge des timestamps hors fenêtre
            self._request_times = [
                t for t in self._request_times if now - t < _RATE_WINDOW
            ]
            if len(self._request_times) >= _MAX_REQUESTS_PER_SEC:
                oldest = self._request_times[0]
                sleep_time = _RATE_WINDOW - (now - oldest) + 0.01
                if sleep_time > 0:
                    logger.debug(f"Binance throttle: {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
            self._request_times.append(time.monotonic())

    async def _ensure_initialized(self) -> None:
        if not self._client or not self._connected:
            await self.initialize()

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        return "429" in str(exc) or "rate limit" in str(exc).lower() or "DDoS" in str(exc)

    async def _handle_rate_limit(self, attempt: int, symbol: str) -> None:
        backoff = _BASE_BACKOFF * (2 ** attempt)
        logger.warning(
            f"Binance rate limit [{symbol}] — backoff {backoff:.1f}s "
            f"(attempt {attempt + 1}/{_MAX_RETRIES})"
        )
        await asyncio.sleep(backoff)
