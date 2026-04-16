"""
Latency Arbitrage Strate — BTC/Polymarket 5-minute specialist.

Logic:
  1. Fetch BTC spot price from Binance public API (no key needed)
  2. Fetch active BTC binary markets from Polymarket Gamma API
  3. Compute fair YES price using lognormal model: P(BTC > X) = N(d2)
     d2 = ln(S / X) / (sigma * sqrt(T))
  4. If |fair - market_price| > min_edge → latency gap detected
  5. Generate BTC LONG/SHORT parliament vote from aggregated signal

Fast polling cycle: 30s (vs 300s for general Polymarket scan).
Specialized on BTC binary outcome markets only.
"""
import asyncio
import httpx
import math
import re
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Optional

logger = logging.getLogger("ORACLE.LatencyArb")

# BTC price sources (public, no auth)
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
GAMMA_BTC_URL = (
    "https://gamma-api.polymarket.com/markets"
    "?active=true&closed=false&limit=500"
    "&order=volume&ascending=false"          # sort by total volume, not 24h
)

# Annualized BTC volatility (historical ~80-100%)
BTC_SIGMA_ANNUAL: float = 0.85


# ─── Pure-Python normal CDF (Abramowitz & Stegun, error < 7.5e-8) ────────────

def _norm_cdf(x: float) -> float:
    """Standard normal CDF without scipy dependency."""
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
           + t * (-1.821255978 + t * 1.330274429))))
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
    return 0.5 + sign * (0.5 - pdf * poly)


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class BtcMarketParsed:
    """Parsed data from a Polymarket BTC binary market."""
    market_id: str
    question: str
    threshold: float          # dollar price in question ($78,000 → 78000)
    direction: str            # "above" or "below"
    current_price_yes: float  # Polymarket YES price
    volume_24h: float
    end_date: str
    days_to_expiry: float


@dataclass
class LatencySignal:
    """An actionable latency arbitrage signal on BTC."""
    market_id: str
    question: str
    threshold: float
    direction_in_market: str   # "above" / "below"
    current_market_price: float
    fair_value: float
    edge: float                # fair_value - current_market_price
    kelly_fraction: float
    btc_spot: float
    days_to_expiry: float
    trade_direction: str       # "LONG" or "SHORT" for BTC spot
    confidence: str            # "HIGH" / "MEDIUM" / "LOW"
    volume_24h: float


# ─── Main strate ──────────────────────────────────────────────────────────────

class BtcLatencyArbStrate:
    """
    BTC/Polymarket latency arbitrage strate.

    Detects when Polymarket binary market prices lag real BTC price movements
    and translates the detected edge into BTC spot LONG/SHORT parliament votes.
    """

    def __init__(
        self,
        min_edge: float = 0.05,
        min_volume: float = 10_000,
        kelly_max: float = 0.25,
        sigma: float = BTC_SIGMA_ANNUAL,
        cache_ttl: int = 30,          # seconds — fast polling
    ):
        self.min_edge = min_edge
        self.min_volume = min_volume
        self.kelly_max = kelly_max
        self.sigma = sigma
        self.cache_ttl = cache_ttl

        self.client = httpx.AsyncClient(timeout=10.0)
        self.last_signals: list[LatencySignal] = []
        self.last_btc_price: float = 0.0
        self._last_btc_fetch: float = 0.0
        self._last_scan: float = 0.0
        self._btc_price_ttl: int = 15  # cache BTC price 15s

    # ── Fetch helpers ────────────────────────────────────────────────────

    async def fetch_btc_price(self) -> float:
        """Fetch BTC spot price from Binance public API, CoinGecko as fallback."""
        import time
        now = time.time()
        if self.last_btc_price > 0 and (now - self._last_btc_fetch) < self._btc_price_ttl:
            return self.last_btc_price

        # Primary: Binance public endpoint
        try:
            resp = await self.client.get(BINANCE_TICKER_URL)
            resp.raise_for_status()
            price = float(resp.json()["price"])
            self.last_btc_price = price
            self._last_btc_fetch = now
            logger.debug(f"BTC spot (Binance): ${price:,.0f}")
            return price
        except Exception as e:
            logger.warning(f"Binance ticker failed: {e}")

        # Fallback: CoinGecko
        try:
            resp = await self.client.get(COINGECKO_URL)
            resp.raise_for_status()
            price = float(resp.json()["bitcoin"]["usd"])
            self.last_btc_price = price
            self._last_btc_fetch = now
            logger.debug(f"BTC spot (CoinGecko): ${price:,.0f}")
            return price
        except Exception as e:
            logger.error(f"CoinGecko fallback failed: {e}")

        return self.last_btc_price  # stale price is better than 0

    async def fetch_btc_markets(self) -> list[dict]:
        """Fetch active Polymarket markets that mention Bitcoin/BTC."""
        try:
            resp = await self.client.get(GAMMA_BTC_URL)
            resp.raise_for_status()
            data = resp.json()
            markets = data if isinstance(data, list) else data.get("markets", [])
            # Pre-filter to BTC markets only
            btc_keywords = {"bitcoin", "btc"}
            return [
                m for m in markets
                if any(kw in m.get("question", "").lower() for kw in btc_keywords)
            ]
        except Exception as e:
            logger.error(f"Gamma API BTC fetch failed: {e}")
            return []

    # ── Parsing ─────────────────────────────────────────────────────────

    _PRICE_RE = re.compile(
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(k|K|m|M)?'
    )
    _ABOVE_WORDS = {"above", "over", "exceed", "reach", "surpass", "hit", "break", "pass"}
    _BELOW_WORDS = {"below", "under", "drop", "fall", "decline", "crash", "dip", "sink", "lose"}

    @classmethod
    def parse_btc_market(cls, market: dict) -> Optional[BtcMarketParsed]:
        """
        Parse a Polymarket market dict into BtcMarketParsed.
        Returns None if the question cannot be parsed.
        """
        import json as _json
        import time

        question = market.get("question", "")
        q_lower = question.lower()

        # Must contain a dollar threshold
        match = cls._PRICE_RE.search(question)
        if not match:
            return None

        raw_num = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        threshold = raw_num * (1_000 if suffix == "k" else 1_000_000 if suffix == "m" else 1.0)

        if threshold < 10_000 or threshold > 10_000_000:
            return None  # sanity check

        # Determine direction
        words = set(q_lower.split())
        if any(w in words for w in cls._ABOVE_WORDS):
            direction = "above"
        elif any(w in words for w in cls._BELOW_WORDS):
            direction = "below"
        else:
            # "reach" implicitly means above
            direction = "above"

        # Parse YES price
        prices_raw = market.get("outcomePrices", ["0.5"])
        if isinstance(prices_raw, str):
            try:
                prices_raw = _json.loads(prices_raw)
            except Exception:
                return None
        try:
            yes_price = float(prices_raw[0])
        except (ValueError, IndexError):
            return None

        if yes_price <= 0.001 or yes_price >= 0.999:
            return None  # already settled

        volume = float(market.get("volume", 0) or 0)

        # Days to expiry
        end_date_str = market.get("endDate", "")
        days_to_expiry = 1.0
        try:
            if end_date_str:
                end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                now_utc = datetime.now(timezone.utc)
                days_to_expiry = max(0.04, (end_dt - now_utc).total_seconds() / 86400)
        except Exception:
            pass

        return BtcMarketParsed(
            market_id=market.get("id", ""),
            question=question,
            threshold=threshold,
            direction=direction,
            current_price_yes=yes_price,
            volume_24h=volume,
            end_date=end_date_str,
            days_to_expiry=days_to_expiry,
        )

    # ── Fair value model ────────────────────────────────────────────────

    def fair_yes_price(self, btc_spot: float, threshold: float,
                       direction: str, days_to_expiry: float) -> float:
        """
        Lognormal fair probability for a BTC binary outcome market.

        For 'above' markets:  P(BTC_T > X) = N(d2)
        For 'below' markets:  P(BTC_T < X) = 1 - N(d2)
        where d2 = ln(S/X) / (sigma * sqrt(T))
        """
        if btc_spot <= 0 or threshold <= 0 or days_to_expiry <= 0:
            return 0.5

        T = days_to_expiry / 365.0
        d2 = math.log(btc_spot / threshold) / (self.sigma * math.sqrt(T))
        prob_above = _norm_cdf(d2)

        return prob_above if direction == "above" else (1.0 - prob_above)

    def kelly_size(self, fair: float, market_price: float) -> float:
        """Kelly criterion for binary bets."""
        if market_price <= 0 or market_price >= 1:
            return 0.0
        b = (1 - market_price) / market_price
        q = 1 - fair
        kelly = (fair * b - q) / b
        return max(0.0, min(self.kelly_max, kelly))

    # ── Main scan ────────────────────────────────────────────────────────

    async def scan(self) -> list[LatencySignal]:
        """
        Fast scan (30s cache) — fetch BTC price + BTC Polymarket markets,
        detect latency gaps, return sorted signals.
        """
        import time
        now = time.time()
        if self.last_signals and (now - self._last_scan) < self.cache_ttl:
            return self.last_signals

        # Parallel fetch
        btc_price, markets = await asyncio.gather(
            self.fetch_btc_price(),
            self.fetch_btc_markets(),
            return_exceptions=True
        )
        if isinstance(btc_price, Exception) or not btc_price:
            logger.warning("Cannot fetch BTC price — aborting latency scan")
            return self.last_signals
        if isinstance(markets, Exception):
            markets = []

        signals: list[LatencySignal] = []
        for m in markets:
            parsed = self.parse_btc_market(m)
            if parsed is None:
                continue
            if parsed.volume_24h < self.min_volume:
                continue

            fair = self.fair_yes_price(
                btc_price, parsed.threshold, parsed.direction, parsed.days_to_expiry
            )
            edge = fair - parsed.current_price_yes
            if abs(edge) < self.min_edge:
                continue

            kelly = self.kelly_size(fair, parsed.current_price_yes)

            # Translate to BTC spot direction
            # YES underpriced (edge>0) on "above" market → expect BTC to stay up → LONG
            # YES overpriced (edge<0) on "above" market → expect BTC to fall → SHORT
            if parsed.direction == "above":
                trade_dir = "LONG" if edge > 0 else "SHORT"
            else:  # "below"
                trade_dir = "SHORT" if edge > 0 else "LONG"

            abs_edge = abs(edge)
            confidence = "HIGH" if abs_edge > 0.15 else "MEDIUM" if abs_edge > 0.08 else "LOW"

            signals.append(LatencySignal(
                market_id=parsed.market_id,
                question=parsed.question,
                threshold=parsed.threshold,
                direction_in_market=parsed.direction,
                current_market_price=parsed.current_price_yes,
                fair_value=round(fair, 4),
                edge=round(edge, 4),
                kelly_fraction=round(kelly, 4),
                btc_spot=btc_price,
                days_to_expiry=parsed.days_to_expiry,
                trade_direction=trade_dir,
                confidence=confidence,
                volume_24h=parsed.volume_24h,
            ))

        self.last_signals = sorted(signals, key=lambda s: abs(s.edge), reverse=True)
        self._last_scan = now

        logger.info(
            f"LatencyArb scan: BTC=${btc_price:,.0f} | "
            f"{len(markets)} BTC markets -> {len(self.last_signals)} signals"
        )
        return self.last_signals

    def generate_parliament_vote(self, signals: list[LatencySignal]):
        """
        Aggregate latency signals into a single BTC parliament vote.
        Weighted by edge magnitude and volume.
        """
        try:
            from oracle_v2.brain.parliament import Vote
        except ImportError:
            from brain.parliament import Vote

        if not signals:
            return Vote(
                strate_name="LATENCY_ARB",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="No latency signals detected"
            )

        long_score = sum(
            abs(s.edge) * min(s.volume_24h / 1_000_000, 2.0)
            for s in signals if s.trade_direction == "LONG"
        )
        short_score = sum(
            abs(s.edge) * min(s.volume_24h / 1_000_000, 2.0)
            for s in signals if s.trade_direction == "SHORT"
        )
        total = long_score + short_score
        if total == 0:
            return Vote("LATENCY_ARB", "NEUTRAL", 0.0, "Balanced signals")

        if long_score > short_score:
            direction = "LONG"
            raw_conf = long_score / total
        else:
            direction = "SHORT"
            raw_conf = short_score / total

        # Confidence: imbalance ratio capped at 0.9
        confidence = min(0.9, raw_conf * (1 + 0.1 * len(signals)))
        top = signals[0]
        reasoning = (
            f"BTC=${top.btc_spot:,.0f} | "
            f"top edge={top.edge:+.1%} on ${top.threshold:,.0f} "
            f"({top.days_to_expiry:.1f}d) | {len(signals)} signals"
        )

        return Vote(
            strate_name="LATENCY_ARB",
            direction=direction,
            confidence=confidence,
            reasoning=reasoning
        )

    async def close(self):
        await self.client.aclose()
