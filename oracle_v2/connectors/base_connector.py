"""
ORACLE v2 — Interface abstraite des connecteurs.

Tous les connecteurs (BinanceConnector, CapitalConnector, MockConnector)
implémentent IConnector.

Avantages :
  - Swap d'exchange sans toucher OracleSystem/CycleManager
  - MockConnector pour les tests sans réseau
  - Heartbeat standardisé pour la détection de déconnexions
  - Typing complet — mypy vérifie les contrats
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ─── Data classes partagées ───────────────────────────────────────────────────

@dataclass
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float
    change_pct: float


@dataclass
class FundingInfo:
    symbol: str
    funding_rate: float
    next_funding_time: int
    open_interest: float


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str           # "buy" | "sell"
    amount: float
    price: Optional[float]
    status: str         # "filled" | "partially_filled" | "rejected"
    filled_qty: float = 0.0
    avg_price: float = 0.0


@dataclass
class BalanceInfo:
    total: float
    free: float
    used: float


# ─── Interface ────────────────────────────────────────────────────────────────

class IConnector(ABC):
    """
    Contrat commun pour tous les connecteurs d'exchange ORACLE v2.

    Conventions :
      - Toutes les méthodes sont async.
      - Les erreurs ne doivent jamais propager hors du connecteur sauf
        ConnectorError/RateLimitError (gérées par CycleManager).
      - initialize() est idempotent.
      - close() est safe à appeler même si initialize() n'a pas été fait.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifiant lisible du connecteur (ex: 'binance', 'capital')."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True si le connecteur est opérationnel."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialise la connexion. Idempotent."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        """
        Teste la connectivité. Retourne True si le serveur répond.
        Utilisé par ConnectorHealthCheck toutes les 30s.
        """
        ...

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> list[dict]:
        """Retourne une liste de bougies OHLCV (dicts avec timestamp/open/high/low/close/volume)."""
        ...

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Optional[Ticker]:
        """Retourne le ticker courant ou None en cas d'erreur."""
        ...

    @abstractmethod
    async def fetch_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """Retourne {'bids': [...], 'asks': [...]}."""
        ...

    @abstractmethod
    async def fetch_balance(self) -> BalanceInfo:
        """Retourne le solde USDT du compte."""
        ...

    @abstractmethod
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
        Place un ordre. Retourne None si rejeté ou erreur réseau.
        TOUJOURS passer par SafetyKernel avant d'appeler cette méthode.
        """
        ...

    @abstractmethod
    async def fetch_position_symbols(self) -> list[str]:
        """
        Retourne la liste des symboles ayant une position ouverte sur l'exchange.
        Utilisé par SafetyKernel.reconcile() au démarrage live pour corriger
        les désynchronisations entre la DB locale et l'état réel de l'exchange.
        Retourne [] si non supporté ou en cas d'erreur.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Ferme proprement la connexion."""
        ...


# ─── Mock Connector (tests) ───────────────────────────────────────────────────

class MockConnector(IConnector):
    """
    Connecteur fictif pour les tests unitaires.
    Retourne des données configurables, zéro appel réseau.
    """

    def __init__(
        self,
        balance: float = 10_000.0,
        price: float = 50_000.0,
        fail_ping: bool = False,
    ):
        self._balance = balance
        self._price = price
        self._fail_ping = fail_ping
        self._connected = False
        self.orders: list[OrderResult] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def initialize(self) -> None:
        self._connected = True

    async def ping(self) -> bool:
        if self._fail_ping:
            return False
        return self._connected

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 100,
    ) -> list[dict]:
        import time
        now = int(time.time() * 1000)
        candles = []
        for i in range(limit):
            p = self._price * (1 + (i - limit / 2) * 0.0002)
            candles.append({
                "timestamp": now - (limit - i) * 300_000,
                "open": p * 0.999,
                "high": p * 1.002,
                "low": p * 0.997,
                "close": p,
                "volume": 100.0 + i * 5,
            })
        return candles

    async def fetch_ticker(self, symbol: str) -> Optional[Ticker]:
        return Ticker(
            symbol=symbol,
            bid=self._price * 0.9999,
            ask=self._price * 1.0001,
            last=self._price,
            volume_24h=50_000.0,
            change_pct=0.005,
        )

    async def fetch_orderbook(self, symbol: str, limit: int = 20) -> dict:
        bids = [[self._price - i * 10, 1.0] for i in range(limit)]
        asks = [[self._price + i * 10, 1.0] for i in range(limit)]
        return {"bids": bids, "asks": asks}

    async def fetch_balance(self) -> BalanceInfo:
        return BalanceInfo(total=self._balance, free=self._balance, used=0.0)

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        params: Optional[dict] = None,
    ) -> Optional[OrderResult]:
        result = OrderResult(
            order_id=f"mock_{len(self.orders)}",
            symbol=symbol,
            side=side,
            amount=amount,
            price=price or self._price,
            status="filled",
            filled_qty=amount,
            avg_price=price or self._price,
        )
        self.orders.append(result)
        return result

    async def fetch_position_symbols(self) -> list[str]:
        """MockConnector : aucune position ouverte par défaut."""
        return []

    async def close(self) -> None:
        self._connected = False
