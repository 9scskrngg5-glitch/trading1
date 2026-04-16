"""
Polymarket Connector — Gamma API + CLOB API.
Interface basse couche pour la PolymarketStrate.
"""
import httpx
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("ORACLE.PolymarketConnector")

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"


@dataclass
class MarketInfo:
    market_id: str
    condition_id: str
    question: str
    end_date: str
    volume: float
    liquidity: float
    active: bool
    outcomes: list
    outcome_prices: list


@dataclass
class OrderbookLevel:
    price: float
    size: float


@dataclass
class MarketOrderbook:
    market_id: str
    asset_id: str
    bids: list
    asks: list
    best_bid: float
    best_ask: float
    mid: float


class PolymarketConnector:
    """
    Connecteur bas niveau vers les APIs Polymarket.
    Utilisé par PolymarketStrate pour la récupération de données.
    """

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_markets(
        self, active: bool = True, limit: int = 200, order_by: str = "volume24hr"
    ) -> list:
        try:
            resp = await self.client.get(
                f"{GAMMA_API_BASE}/markets",
                params={"active": active, "closed": False, "limit": limit,
                        "order": order_by, "ascending": False}
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data if isinstance(data, list) else data.get("markets", [])
            result = []
            for m in raw:
                try:
                    outcome_prices = []
                    for p in m.get("outcomePrices", []):
                        try:
                            outcome_prices.append(float(p))
                        except ValueError:
                            outcome_prices.append(0.5)
                    result.append(MarketInfo(
                        market_id=m.get("id", ""),
                        condition_id=m.get("conditionId", ""),
                        question=m.get("question", ""),
                        end_date=m.get("endDate", ""),
                        volume=float(m.get("volume", 0) or 0),
                        liquidity=float(m.get("liquidity", 0) or 0),
                        active=bool(m.get("active", True)),
                        outcomes=m.get("outcomes", ["Yes", "No"]),
                        outcome_prices=outcome_prices
                    ))
                except Exception:
                    continue
            return result
        except Exception as e:
            logger.error(f"fetch_markets: {e}")
            return []

    async def fetch_market_by_id(self, market_id: str) -> Optional[MarketInfo]:
        try:
            resp = await self.client.get(f"{GAMMA_API_BASE}/markets/{market_id}")
            resp.raise_for_status()
            m = resp.json()
            outcome_prices = []
            for p in m.get("outcomePrices", []):
                try:
                    outcome_prices.append(float(p))
                except ValueError:
                    outcome_prices.append(0.5)
            return MarketInfo(
                market_id=m.get("id", ""),
                condition_id=m.get("conditionId", ""),
                question=m.get("question", ""),
                end_date=m.get("endDate", ""),
                volume=float(m.get("volume", 0) or 0),
                liquidity=float(m.get("liquidity", 0) or 0),
                active=bool(m.get("active", True)),
                outcomes=m.get("outcomes", ["Yes", "No"]),
                outcome_prices=outcome_prices
            )
        except Exception as e:
            logger.error(f"fetch_market_by_id {market_id}: {e}")
            return None

    async def fetch_orderbook(self, token_id: str) -> Optional[MarketOrderbook]:
        try:
            resp = await self.client.get(
                f"{CLOB_API_BASE}/book", params={"token_id": token_id}
            )
            resp.raise_for_status()
            data = resp.json()
            bids = [OrderbookLevel(price=float(b["price"]), size=float(b["size"]))
                    for b in data.get("bids", [])[:10]]
            asks = [OrderbookLevel(price=float(a["price"]), size=float(a["size"]))
                    for a in data.get("asks", [])[:10]]
            best_bid = bids[0].price if bids else 0.0
            best_ask = asks[0].price if asks else 1.0
            return MarketOrderbook(
                market_id="", asset_id=token_id,
                bids=bids, asks=asks,
                best_bid=best_bid, best_ask=best_ask,
                mid=(best_bid + best_ask) / 2
            )
        except Exception as e:
            logger.warning(f"fetch_orderbook {token_id}: {e}")
            return None

    async def close(self) -> None:
        await self.client.aclose()
