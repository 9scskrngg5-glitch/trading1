"""
Sensory Layer — Ingestion données marché (prix, volume, macro).
Équivalent cortex sensoriel : collecte brute, normalisation minimale.
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.SensoryLayer")


@dataclass
class OHLCV:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: float


@dataclass
class SensoryInput:
    ohlcv: list                          # list[OHLCV]
    orderbook_imbalance: float           # bid/ask ratio -1.0 to 1.0
    funding_rate: Optional[float]        # futures funding
    open_interest: Optional[float]
    macro_context: Optional[dict]        # {"DXY": float, "VIX": float, ...}


class SensoryLayer:
    """
    Collecte et normalise les données brutes de marché.
    Interface avec les connectors (Binance, Capital).
    """
    def __init__(self, symbols: list, timeframes: list = None):
        self.symbols = symbols
        self.timeframes = timeframes or ["5m", "15m", "1h"]
        self._cache: dict = {}

    def ingest_ohlcv(self, raw_candles: list, symbol: str, timeframe: str) -> list:
        """Convertit les candles brutes en objets OHLCV."""
        result = []
        for c in raw_candles:
            if isinstance(c, dict):
                result.append(OHLCV(
                    symbol=symbol, timeframe=timeframe,
                    timestamp=float(c.get("timestamp", 0)),
                    open=float(c.get("open", 0)),
                    high=float(c.get("high", 0)),
                    low=float(c.get("low", 0)),
                    close=float(c.get("close", 0)),
                    volume=float(c.get("volume", 0))
                ))
            elif isinstance(c, (list, tuple)) and len(c) >= 6:
                result.append(OHLCV(
                    symbol=symbol, timeframe=timeframe,
                    timestamp=float(c[0]), open=float(c[1]),
                    high=float(c[2]), low=float(c[3]),
                    close=float(c[4]), volume=float(c[5])
                ))
        self._cache[f"{symbol}_{timeframe}"] = result
        return result

    def get_orderbook_imbalance(self, bids: list, asks: list) -> float:
        """
        Ratio bid/ask normalisé [-1, +1].
        +1 = pression achat totale, -1 = pression vente totale.
        """
        if not bids or not asks:
            return 0.0
        bid_volume = sum(float(b[1]) for b in bids[:10])
        ask_volume = sum(float(a[1]) for a in asks[:10])
        total = bid_volume + ask_volume
        if total == 0:
            return 0.0
        return (bid_volume - ask_volume) / total

    def build_sensory_input(
        self,
        symbol: str,
        candles_by_tf: dict,
        orderbook: Optional[dict] = None,
        funding_rate: Optional[float] = None,
        open_interest: Optional[float] = None,
        macro: Optional[dict] = None
    ) -> SensoryInput:
        ohlcv_all = []
        for tf, candles in candles_by_tf.items():
            ohlcv_all.extend(self.ingest_ohlcv(candles, symbol, tf))

        imbalance = 0.0
        if orderbook:
            imbalance = self.get_orderbook_imbalance(
                orderbook.get("bids", []), orderbook.get("asks", [])
            )

        return SensoryInput(
            ohlcv=ohlcv_all,
            orderbook_imbalance=imbalance,
            funding_rate=funding_rate,
            open_interest=open_interest,
            macro_context=macro
        )
