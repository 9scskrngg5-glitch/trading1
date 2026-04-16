"""
Tests Polymarket Strate — mock API + edge calculation + Kelly.
"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.strates.polymarket_strate import PolymarketStrate, PolymarketOpportunity


MOCK_MARKETS = [
    {
        "id": "market-btc-100k",
        "question": "Will Bitcoin exceed $100,000 by end of 2025?",
        "volume": 500_000,
        "liquidity": 200_000,
        "outcomePrices": ["0.65", "0.35"],
        "endDate": "2025-12-31",
        "active": True
    },
    {
        "id": "market-eth-5k",
        "question": "Will Ethereum reach $5,000 in Q2 2025?",
        "volume": 150_000,
        "outcomePrices": ["0.40", "0.60"],
        "endDate": "2025-06-30",
        "active": True
    },
    {
        "id": "market-gold-rate",
        "question": "Will the Federal Reserve cut rates before September 2025?",
        "volume": 300_000,
        "outcomePrices": ["0.72", "0.28"],
        "endDate": "2025-09-01",
        "active": True
    },
    {
        "id": "market-tiny-volume",
        "question": "Will BTC hit $200k?",
        "volume": 1_000,  # below min_volume
        "outcomePrices": ["0.10", "0.90"],
        "endDate": "2025-12-31",
        "active": True
    },
]


class TestPolymarketStrate:

    def test_classify_btc_market(self):
        strate = PolymarketStrate()
        asset, bullish = strate.classify_market("Will Bitcoin exceed $100k?")
        assert asset == "BTC"
        assert bullish is True

    def test_classify_bearish_market(self):
        strate = PolymarketStrate()
        asset, bullish = strate.classify_market("Will Bitcoin crash below $20k?")
        assert asset == "BTC"
        assert bullish is False

    def test_classify_gold_market(self):
        strate = PolymarketStrate()
        # "federal reserve" is a GOLD keyword — unambiguous
        asset, bullish = strate.classify_market(
            "Will the Federal Reserve cut rates before September 2025?"
        )
        assert asset == "GOLD"

    def test_classify_unknown_market(self):
        strate = PolymarketStrate()
        asset, bullish = strate.classify_market("Will Manchester City win the Champions League?")
        assert asset is None

    def test_kelly_size_positive_edge(self):
        strate = PolymarketStrate(kelly_fraction_max=0.30)
        # p_estimate=0.75, market=0.65 → edge=0.10
        kelly = strate.kelly_size(0.75, 0.65)
        assert kelly > 0
        assert kelly <= 0.30

    def test_kelly_size_zero_edge(self):
        strate = PolymarketStrate()
        kelly = strate.kelly_size(0.65, 0.65)
        assert kelly == 0.0

    def test_kelly_size_negative_edge(self):
        strate = PolymarketStrate()
        kelly = strate.kelly_size(0.50, 0.70)
        assert kelly == 0.0  # capped at 0

    def test_kelly_invalid_price(self):
        strate = PolymarketStrate()
        assert strate.kelly_size(0.5, 0.0) == 0.0
        assert strate.kelly_size(0.5, 1.0) == 0.0

    def test_estimate_probability_contrarian_high(self):
        strate = PolymarketStrate()
        # Market > 0.80 → slight downward adjustment (float precision)
        est = strate.estimate_oracle_probability("test", "BTC", 0.85)
        assert abs(est - 0.80) < 1e-9

    def test_estimate_probability_contrarian_low(self):
        strate = PolymarketStrate()
        # Market < 0.20 → slight upward adjustment
        est = strate.estimate_oracle_probability("test", "BTC", 0.15)
        assert est == 0.22

    def test_estimate_probability_with_context(self):
        strate = PolymarketStrate()
        est = strate.estimate_oracle_probability("test", "BTC", 0.65, {"BTC": 0.80})
        assert est == 0.80

    @pytest.mark.asyncio
    async def test_scan_filters_by_min_volume(self):
        strate = PolymarketStrate(min_edge=0.05, min_volume=25_000)
        with patch.object(strate, 'fetch_markets', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_MARKETS
            opps = await strate.scan()
        # market-tiny-volume (1k) should be filtered
        ids = [o.market_id for o in opps]
        assert "market-tiny-volume" not in ids

    @pytest.mark.asyncio
    async def test_scan_returns_sorted_by_edge(self):
        strate = PolymarketStrate(min_edge=0.05, min_volume=25_000)
        with patch.object(strate, 'fetch_markets', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_MARKETS
            opps = await strate.scan()
        edges = [abs(o.edge) for o in opps]
        assert edges == sorted(edges, reverse=True)

    @pytest.mark.asyncio
    async def test_scan_uses_cache(self):
        # Cache only activates when last_opportunities is non-empty.
        # Pre-populate last_opportunities and set _last_fetch to now.
        import time
        strate = PolymarketStrate(min_edge=0.05, min_volume=25_000)
        strate.last_opportunities = [
            PolymarketOpportunity(
                market_id="x", question="Will BTC hit 100k?",
                current_price_yes=0.15, oracle_estimate=0.22,
                edge=0.07, kelly_fraction=0.05,
                direction="YES", correlated_asset="BTC",
                volume_24h=500_000, end_date="2025-12-31",
                confidence="LOW", bullish_for_asset=True
            )
        ]
        strate._last_fetch = time.time()  # just fetched

        with patch.object(strate, 'fetch_markets', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOCK_MARKETS
            opps = await strate.scan()
            # Should return cache without calling fetch_markets
            assert mock_fetch.call_count == 0
            assert opps == strate.last_opportunities

    def test_parliament_vote_long(self):
        strate = PolymarketStrate()
        opps = [
            PolymarketOpportunity(
                market_id="m1", question="Will BTC hit 100k?",
                current_price_yes=0.65, oracle_estimate=0.80,
                edge=0.15, kelly_fraction=0.12,
                direction="YES", correlated_asset="BTC",
                volume_24h=500_000, end_date="2025-12-31",
                confidence="HIGH", bullish_for_asset=True
            )
        ]
        vote = strate.generate_parliament_vote(opps, "BTC")
        assert vote.strate_name == "POLYMARKET"
        assert vote.direction == "LONG"
        assert vote.confidence > 0

    def test_parliament_vote_neutral_when_no_asset(self):
        strate = PolymarketStrate()
        vote = strate.generate_parliament_vote([], "BTC")
        assert vote.direction == "NEUTRAL"
        assert vote.confidence == 0.0
