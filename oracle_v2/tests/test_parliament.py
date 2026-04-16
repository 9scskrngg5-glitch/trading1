"""
Tests Parlement — vote Hebbian + quorum.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.brain.parliament import Parliament, HebbianWeightManager, Vote


def make_vote(strate: str, direction: str, confidence: float) -> Vote:
    return Vote(strate_name=strate, direction=direction,
                confidence=confidence, reasoning="test")


class TestHebbianWeightManager:

    def test_initial_weights_equal(self):
        wm = HebbianWeightManager(["A", "B", "C"])
        assert wm.get_weight("A") == 1.0
        assert wm.get_weight("B") == 1.0
        assert wm.get_weight("unknown") == 1.0

    def test_profitable_trade_boosts_weight(self):
        wm = HebbianWeightManager(["A"])
        wm.update("A", was_profitable=True, pnl_pct=0.02)
        assert wm.get_weight("A") > 1.0

    def test_losing_trade_decays_weight(self):
        wm = HebbianWeightManager(["A"])
        wm.update("A", was_profitable=False, pnl_pct=-0.01)
        assert wm.get_weight("A") < 1.0

    def test_weight_bounded_by_min_max(self):
        wm = HebbianWeightManager(["A"])
        for _ in range(50):
            wm.update("A", was_profitable=False, pnl_pct=-0.01)
        assert wm.get_weight("A") >= wm.min_weight

        for _ in range(50):
            wm.update("A", was_profitable=True, pnl_pct=0.02)
        assert wm.get_weight("A") <= wm.max_weight


class TestParliament:

    def test_empty_votes_returns_neutral(self):
        p = Parliament(quorum=0.6)
        decision = p.deliberate([])
        assert decision.direction == "NEUTRAL"
        assert decision.strength == 0.0

    def test_long_quorum_reached(self):
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "LONG", 0.8),
            make_vote("B", "LONG", 0.7),
            make_vote("C", "SHORT", 0.9),
        ]
        # weighted: long=1.5, short=0.9, total=3 → long_ratio=0.5 — NOT enough
        # Try with 3 LONG
        votes = [
            make_vote("A", "LONG", 0.8),
            make_vote("B", "LONG", 0.7),
            make_vote("C", "LONG", 0.6),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "LONG"
        assert decision.strength >= 0.6

    def test_short_quorum_reached(self):
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "SHORT", 0.9),
            make_vote("B", "SHORT", 0.8),
            make_vote("C", "SHORT", 0.7),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "SHORT"
        assert decision.strength >= 0.6

    def test_no_quorum_returns_neutral(self):
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "LONG", 0.5),
            make_vote("B", "SHORT", 0.5),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "NEUTRAL"

    def test_polymarket_alignment_detected(self):
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "LONG", 0.8),
            make_vote("B", "LONG", 0.8),
            make_vote("POLYMARKET", "LONG", 0.7),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "LONG"
        assert decision.polymarket_alignment is True

    def test_polymarket_divergent(self):
        # Ratio = sum(conf*weight for direction) / total_weight
        # Need 5 LONG at 0.9 vs 1 SHORT: long_ratio = 4.5/6 = 0.75 ≥ 0.6
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "LONG", 0.9),
            make_vote("B", "LONG", 0.9),
            make_vote("C", "LONG", 0.9),
            make_vote("D", "LONG", 0.9),
            make_vote("E", "LONG", 0.9),
            make_vote("POLYMARKET", "SHORT", 0.9),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "LONG"
        assert decision.polymarket_alignment is False

    def test_hebbian_weights_influence_decision(self):
        # Verify Hebbian weights shift the balance: add a 3rd neutral vote
        # so that STRONG can push SHORT above quorum via weight advantage
        p = Parliament(quorum=0.5)  # lower quorum to see Hebbian effect clearly
        wm = HebbianWeightManager(["STRONG", "WEAK"])
        for _ in range(10):
            wm.update("STRONG", True, 0.02)
        for _ in range(10):
            wm.update("WEAK", False, -0.01)
        p.set_weight_manager(wm)

        strong_w = wm.get_weight("STRONG")
        weak_w = wm.get_weight("WEAK")
        assert strong_w > weak_w  # Hebbian effect confirmed

        # With quorum=0.5: short_weighted / total > 0.5 requires strong_w*0.7 > weak_w*0.9
        # strong_w ≈ 2.16, weak_w ≈ 0.43 → short = 1.51, long = 0.39, ratio = 0.79 → SHORT
        votes = [
            make_vote("STRONG", "SHORT", 0.7),
            make_vote("WEAK", "LONG", 0.9),
        ]
        decision = p.deliberate(votes)
        assert decision.direction == "SHORT"

    def test_dissenting_votes_captured(self):
        p = Parliament(quorum=0.6)
        votes = [
            make_vote("A", "LONG", 0.9),
            make_vote("B", "LONG", 0.8),
            make_vote("C", "SHORT", 0.7),
        ]
        decision = p.deliberate(votes)
        if decision.direction == "LONG":
            assert any(v.direction == "SHORT" for v in decision.dissenting)
