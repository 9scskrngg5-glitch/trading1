"""
Tests BtcLatencyArbStrate — fair value model, parsing, edge detection, vote.
All network calls mocked.
"""
import pytest
import math
import sys
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.strates.latency_arb_strate import (
    BtcLatencyArbStrate, LatencySignal, _norm_cdf
)


# ─── norm_cdf sanity ──────────────────────────────────────────────────────────

class TestNormCdf:

    def test_norm_cdf_zero(self):
        assert abs(_norm_cdf(0.0) - 0.5) < 1e-4

    def test_norm_cdf_positive(self):
        # N(1.96) ≈ 0.975
        assert abs(_norm_cdf(1.96) - 0.975) < 0.002

    def test_norm_cdf_negative(self):
        # N(-1.96) ≈ 0.025
        assert abs(_norm_cdf(-1.96) - 0.025) < 0.002

    def test_norm_cdf_large_positive(self):
        assert _norm_cdf(5.0) > 0.999

    def test_norm_cdf_large_negative(self):
        assert _norm_cdf(-5.0) < 0.001


# ─── fair value model ─────────────────────────────────────────────────────────

class TestFairValueModel:

    def test_fair_above_spot_equals_threshold(self):
        """When BTC == threshold, P(above) ≈ 0.50 for very short expiry."""
        strate = BtcLatencyArbStrate(sigma=0.85)
        # Very short expiry (0.1 day) → d2 ≈ 0 → 0.5
        fair = strate.fair_yes_price(80_000, 80_000, "above", 0.1)
        assert abs(fair - 0.5) < 0.05

    def test_fair_above_spot_well_above_threshold(self):
        """When BTC >> threshold, P(above) is high."""
        strate = BtcLatencyArbStrate(sigma=0.85)
        fair = strate.fair_yes_price(80_000, 60_000, "above", 1.0)
        assert fair > 0.70

    def test_fair_above_spot_well_below_threshold(self):
        """When BTC << threshold, P(above) is low."""
        strate = BtcLatencyArbStrate(sigma=0.85)
        fair = strate.fair_yes_price(60_000, 150_000, "above", 7.0)
        assert fair < 0.10

    def test_fair_below_is_complement(self):
        """P(below) = 1 - P(above) for same parameters."""
        strate = BtcLatencyArbStrate(sigma=0.85)
        S, X, T = 80_000, 75_000, 3.0
        above = strate.fair_yes_price(S, X, "above", T)
        below = strate.fair_yes_price(S, X, "below", T)
        assert abs(above + below - 1.0) < 1e-9

    def test_fair_invalid_inputs(self):
        strate = BtcLatencyArbStrate()
        assert strate.fair_yes_price(0, 80_000, "above", 1) == 0.5
        assert strate.fair_yes_price(80_000, 0, "above", 1) == 0.5
        assert strate.fair_yes_price(80_000, 80_000, "above", 0) == 0.5


# ─── Market parsing ───────────────────────────────────────────────────────────

class TestMarketParsing:

    def _make_market(self, question, prices="[\"0.30\", \"0.70\"]",
                     volume=500_000, end="2026-04-20T00:00:00Z"):
        return {
            "id": "test-id",
            "question": question,
            "outcomePrices": prices,
            "volume": volume,
            "endDate": end,
        }

    def test_parse_above_market(self):
        m = self._make_market("Will the price of Bitcoin be above $78,000 on April 13?")
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is not None
        assert parsed.threshold == 78_000
        assert parsed.direction == "above"
        assert abs(parsed.current_price_yes - 0.30) < 1e-9

    def test_parse_reach_market(self):
        m = self._make_market("Will Bitcoin reach $150,000 in April?")
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is not None
        assert parsed.threshold == 150_000
        assert parsed.direction == "above"  # "reach" → above

    def test_parse_k_suffix(self):
        m = self._make_market("Will Bitcoin exceed $100k by end of 2025?")
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is not None
        assert parsed.threshold == 100_000

    def test_parse_below_market(self):
        m = self._make_market("Will Bitcoin fall below $60,000 in Q2?")
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is not None
        assert parsed.direction == "below"

    def test_parse_no_price_returns_none(self):
        m = self._make_market("Will Bitcoin halving happen in 2024?")
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is None

    def test_parse_settled_market_filtered(self):
        # YES at 0.999 → already settled
        m = self._make_market(
            "Will Bitcoin be above $62,000 on April 13?",
            prices='["0.999", "0.001"]'
        )
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is None

    def test_parse_json_string_prices(self):
        m = self._make_market(
            "Will Bitcoin reach $80,000 in April?",
            prices='["0.45", "0.55"]'
        )
        parsed = BtcLatencyArbStrate.parse_btc_market(m)
        assert parsed is not None
        assert abs(parsed.current_price_yes - 0.45) < 1e-9


# ─── Kelly sizing ─────────────────────────────────────────────────────────────

class TestKellySizing:

    def test_kelly_positive_edge(self):
        strate = BtcLatencyArbStrate(kelly_max=0.25)
        k = strate.kelly_size(fair=0.70, market_price=0.40)
        assert k > 0
        assert k <= 0.25

    def test_kelly_zero_edge(self):
        strate = BtcLatencyArbStrate()
        k = strate.kelly_size(fair=0.50, market_price=0.50)
        assert k == 0.0

    def test_kelly_negative_edge(self):
        strate = BtcLatencyArbStrate()
        k = strate.kelly_size(fair=0.30, market_price=0.60)
        assert k == 0.0

    def test_kelly_invalid_market_price(self):
        strate = BtcLatencyArbStrate()
        assert strate.kelly_size(0.5, 0.0) == 0.0
        assert strate.kelly_size(0.5, 1.0) == 0.0


# ─── Edge detection & trade direction ────────────────────────────────────────

class TestEdgeDetection:

    def test_above_underpriced_is_long(self):
        """YES underpriced on 'above' market → BTC expected to hold → LONG."""
        # BTC at 80k, threshold 75k, market says 30% but fair is 65% → YES underpriced
        strate = BtcLatencyArbStrate(min_edge=0.05)
        fair = strate.fair_yes_price(80_000, 75_000, "above", 3.0)
        edge = fair - 0.30
        assert edge > 0  # fair > market
        # LONG when edge > 0 on "above" market
        trade_dir = "LONG" if edge > 0 else "SHORT"
        assert trade_dir == "LONG"

    def test_above_overpriced_is_short(self):
        """YES overpriced on 'above' market → BTC expected to fall → SHORT."""
        # BTC at 60k, threshold 75k, market says 60% but fair is ~10%
        strate = BtcLatencyArbStrate(min_edge=0.05)
        fair = strate.fair_yes_price(60_000, 75_000, "above", 3.0)
        edge = fair - 0.60
        assert edge < 0  # fair < market
        trade_dir = "LONG" if edge > 0 else "SHORT"
        assert trade_dir == "SHORT"


# ─── Async scan ───────────────────────────────────────────────────────────────

MOCK_BTC_MARKETS = [
    {
        "id": "btc-above-78k",
        "question": "Will the price of Bitcoin be above $78,000 on April 13?",
        "outcomePrices": '["0.10", "0.90"]',  # market says 10%
        "volume": 300_000,
        "endDate": "2026-04-20T00:00:00Z",
        "active": True,
    },
    {
        "id": "btc-reach-150k",
        "question": "Will Bitcoin reach $150,000 in April?",
        "outcomePrices": '["0.03", "0.97"]',
        "volume": 5_000_000,
        "endDate": "2026-04-30T00:00:00Z",
        "active": True,
    },
    {
        "id": "btc-low-volume",
        "question": "Will Bitcoin reach $200,000 in April?",
        "outcomePrices": '["0.01", "0.99"]',
        "volume": 500,  # below min_volume
        "endDate": "2026-04-30T00:00:00Z",
        "active": True,
    },
]


class TestScan:

    @pytest.mark.asyncio
    async def test_scan_filters_low_volume(self):
        strate = BtcLatencyArbStrate(min_edge=0.03, min_volume=10_000)
        with patch.object(strate, 'fetch_btc_price', new_callable=AsyncMock) as mp, \
             patch.object(strate, 'fetch_btc_markets', new_callable=AsyncMock) as mm:
            mp.return_value = 80_000.0
            mm.return_value = MOCK_BTC_MARKETS
            signals = await strate.scan()
        ids = [s.market_id for s in signals]
        assert "btc-low-volume" not in ids

    @pytest.mark.asyncio
    async def test_scan_sorted_by_edge(self):
        strate = BtcLatencyArbStrate(min_edge=0.01, min_volume=1_000)
        with patch.object(strate, 'fetch_btc_price', new_callable=AsyncMock) as mp, \
             patch.object(strate, 'fetch_btc_markets', new_callable=AsyncMock) as mm:
            mp.return_value = 80_000.0
            mm.return_value = MOCK_BTC_MARKETS
            signals = await strate.scan()
        edges = [abs(s.edge) for s in signals]
        assert edges == sorted(edges, reverse=True)

    @pytest.mark.asyncio
    async def test_scan_uses_cache(self):
        strate = BtcLatencyArbStrate(min_edge=0.01, min_volume=1_000)
        # Pre-populate cache
        strate.last_signals = [
            LatencySignal(
                market_id="cached", question="Will Bitcoin exceed $100k?",
                threshold=100_000, direction_in_market="above",
                current_market_price=0.10, fair_value=0.25, edge=0.15,
                kelly_fraction=0.10, btc_spot=82_000.0, days_to_expiry=7.0,
                trade_direction="LONG", confidence="MEDIUM", volume_24h=1_000_000,
            )
        ]
        strate._last_scan = time.time()

        with patch.object(strate, 'fetch_btc_price', new_callable=AsyncMock) as mp, \
             patch.object(strate, 'fetch_btc_markets', new_callable=AsyncMock) as mm:
            mp.return_value = 80_000.0
            mm.return_value = []
            result = await strate.scan()
            assert mp.call_count == 0  # cache hit
            assert result == strate.last_signals

    @pytest.mark.asyncio
    async def test_scan_no_btc_price_returns_stale(self):
        strate = BtcLatencyArbStrate()
        strate.last_signals = []  # empty stale
        with patch.object(strate, 'fetch_btc_price', new_callable=AsyncMock) as mp, \
             patch.object(strate, 'fetch_btc_markets', new_callable=AsyncMock) as mm:
            mp.return_value = 0.0  # simulate failure
            mm.return_value = MOCK_BTC_MARKETS
            result = await strate.scan()
        assert result == []


# ─── Parliament vote ──────────────────────────────────────────────────────────

class TestParliamentVote:

    def _make_signal(self, trade_dir, edge, volume=500_000) -> LatencySignal:
        return LatencySignal(
            market_id="x", question="test", threshold=80_000,
            direction_in_market="above", current_market_price=0.10,
            fair_value=0.10 + edge, edge=edge, kelly_fraction=0.05,
            btc_spot=82_000, days_to_expiry=3.0,
            trade_direction=trade_dir, confidence="MEDIUM",
            volume_24h=volume,
        )

    def test_vote_long_dominant(self):
        strate = BtcLatencyArbStrate()
        signals = [
            self._make_signal("LONG", 0.15, 1_000_000),
            self._make_signal("LONG", 0.12, 500_000),
            self._make_signal("SHORT", 0.07, 100_000),
        ]
        vote = strate.generate_parliament_vote(signals)
        assert vote.strate_name == "LATENCY_ARB"
        assert vote.direction == "LONG"
        assert vote.confidence > 0

    def test_vote_short_dominant(self):
        strate = BtcLatencyArbStrate()
        signals = [self._make_signal("SHORT", 0.20, 2_000_000)]
        vote = strate.generate_parliament_vote(signals)
        assert vote.direction == "SHORT"

    def test_vote_empty_is_neutral(self):
        strate = BtcLatencyArbStrate()
        vote = strate.generate_parliament_vote([])
        assert vote.direction == "NEUTRAL"
        assert vote.confidence == 0.0

    def test_vote_confidence_bounded(self):
        strate = BtcLatencyArbStrate()
        signals = [self._make_signal("LONG", 0.30, 5_000_000) for _ in range(10)]
        vote = strate.generate_parliament_vote(signals)
        assert 0.0 < vote.confidence <= 0.9
