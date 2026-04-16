"""
Capital.com Connector — CFD pour XAU/USD (Gold) et Nikkei 225.
API REST Capital.com — clés depuis .env uniquement.
"""
import logging
import httpx
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("ORACLE.Capital")

CAPITAL_DEMO_URL = "https://demo-api-capital.backend-capital.com/api/v1"
CAPITAL_LIVE_URL = "https://api-capital.backend-capital.com/api/v1"


@dataclass
class CapitalPosition:
    position_id: str
    epic: str
    direction: str
    size: float
    open_level: float
    currency: str
    pnl: float


class CapitalConnector:
    """
    Connecteur Capital.com pour CFD.
    Nécessite CAPITAL_API_KEY et CAPITAL_PASSWORD dans .env.
    Mode demo par défaut.
    """

    INSTRUMENTS = {
        "GOLD": "CC.D.XAUUSD.CASH.IP",
        "NIKKEI": "IX.D.NIKKEI.DAILY.IP",
    }

    def __init__(self, api_key: str, password: str, demo: bool = True):
        self.api_key = api_key
        self.password = password
        self.demo = demo
        self.base_url = CAPITAL_DEMO_URL if demo else CAPITAL_LIVE_URL
        self._session_token: Optional[str] = None
        self._account_token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=15.0)

    async def authenticate(self) -> bool:
        try:
            resp = await self.client.post(
                f"{self.base_url}/session",
                headers={"X-CAP-API-KEY": self.api_key},
                json={"identifier": self.api_key, "password": self.password}
            )
            resp.raise_for_status()
            self._session_token = resp.headers.get("X-SECURITY-TOKEN")
            self._account_token = resp.headers.get("CST")
            logger.info(f"Capital.com authentifié (demo={self.demo})")
            return True
        except Exception as e:
            logger.error(f"Capital.com auth error: {e}")
            return False

    def _headers(self) -> dict:
        return {
            "X-SECURITY-TOKEN": self._session_token or "",
            "CST": self._account_token or "",
            "Content-Type": "application/json"
        }

    async def fetch_prices(self, instrument: str) -> Optional[dict]:
        epic = self.INSTRUMENTS.get(instrument, instrument)
        try:
            resp = await self.client.get(
                f"{self.base_url}/markets/{epic}", headers=self._headers()
            )
            resp.raise_for_status()
            snapshot = resp.json().get("snapshot", {})
            return {
                "instrument": instrument,
                "bid": snapshot.get("bid", 0),
                "ask": snapshot.get("offer", 0),
                "mid": (snapshot.get("bid", 0) + snapshot.get("offer", 0)) / 2,
                "change_pct": snapshot.get("percentageChange", 0)
            }
        except Exception as e:
            logger.error(f"fetch_prices {instrument}: {e}")
            return None

    async def fetch_ohlcv(
        self, instrument: str, resolution: str = "MINUTE_5", limit: int = 100
    ) -> list:
        epic = self.INSTRUMENTS.get(instrument, instrument)
        try:
            resp = await self.client.get(
                f"{self.base_url}/prices/{epic}",
                headers=self._headers(),
                params={"resolution": resolution, "max": limit}
            )
            resp.raise_for_status()
            result = []
            for p in resp.json().get("prices", []):
                op = p.get("openPrice", {})
                cp = p.get("closePrice", {})
                hp = p.get("highPrice", {})
                lp = p.get("lowPrice", {})
                result.append({
                    "timestamp": p.get("snapshotTimeUTC", ""),
                    "open": (op.get("bid", 0) + op.get("ask", 0)) / 2,
                    "high": (hp.get("bid", 0) + hp.get("ask", 0)) / 2,
                    "low": (lp.get("bid", 0) + lp.get("ask", 0)) / 2,
                    "close": (cp.get("bid", 0) + cp.get("ask", 0)) / 2,
                    "volume": p.get("lastTradedVolume", 0)
                })
            return result
        except Exception as e:
            logger.error(f"fetch_ohlcv Capital {instrument}: {e}")
            return []

    async def get_positions(self) -> list:
        try:
            resp = await self.client.get(
                f"{self.base_url}/positions", headers=self._headers()
            )
            resp.raise_for_status()
            result = []
            for p in resp.json().get("positions", []):
                pos = p.get("position", {})
                market = p.get("market", {})
                result.append(CapitalPosition(
                    position_id=pos.get("dealId", ""),
                    epic=market.get("epic", ""),
                    direction=pos.get("direction", ""),
                    size=float(pos.get("size", 0)),
                    open_level=float(pos.get("openLevel", 0)),
                    currency=pos.get("currency", "USD"),
                    pnl=float(pos.get("upl", 0))
                ))
            return result
        except Exception as e:
            logger.error(f"get_positions Capital: {e}")
            return []

    async def close(self) -> None:
        await self.client.aclose()
