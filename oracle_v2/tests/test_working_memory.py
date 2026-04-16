"""
Tests Working Memory — vérifie le consensus sur N bougies consécutives.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from oracle_v2.brain.working_memory import WorkingMemory


class TestWorkingMemory:

    def test_no_consensus_when_empty(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        assert wm.get_consensus() is None

    def test_no_consensus_insufficient_data(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("LONG", 0.8, "MOMENTUM")
        assert wm.get_consensus() is None

    def test_consensus_long_2_of_3(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("LONG", 0.8, "MOMENTUM")
        wm.push("LONG", 0.7, "AMD")
        wm.push("SHORT", 0.6, "MACRO")
        result = wm.get_consensus()
        assert result is not None
        direction, confidence = result
        assert direction == "LONG"
        assert abs(confidence - 0.75) < 1e-9  # (0.8+0.7)/2

    def test_consensus_short_2_of_2(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("SHORT", 0.9, "STRUCTURE")
        wm.push("SHORT", 0.6, "AMD")
        result = wm.get_consensus()
        assert result is not None
        direction, confidence = result
        assert direction == "SHORT"
        assert abs(confidence - 0.75) < 1e-9

    def test_no_consensus_mixed_signals(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("LONG", 0.8, "MOMENTUM")
        wm.push("SHORT", 0.7, "AMD")
        assert wm.get_consensus() is None

    def test_window_evicts_old_signals(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("SHORT", 0.9, "AMD")
        wm.push("LONG", 0.8, "MOMENTUM")
        wm.push("LONG", 0.7, "STRUCTURE")
        wm.push("LONG", 0.6, "MACRO")  # evicts SHORT
        result = wm.get_consensus()
        assert result is not None
        assert result[0] == "LONG"

    def test_clear_resets_buffer(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("LONG", 0.8, "MOMENTUM")
        wm.push("LONG", 0.7, "AMD")
        assert wm.get_consensus() is not None
        wm.clear()
        assert wm.get_consensus() is None

    def test_neutral_never_reaches_consensus(self):
        wm = WorkingMemory(window=3, required_consensus=2)
        wm.push("NEUTRAL", 0.5, "MACRO")
        wm.push("NEUTRAL", 0.5, "AMD")
        wm.push("NEUTRAL", 0.5, "MOMENTUM")
        # NEUTRAL not in ["LONG", "SHORT"] → no consensus
        assert wm.get_consensus() is None

    def test_required_consensus_3_of_3(self):
        wm = WorkingMemory(window=3, required_consensus=3)
        wm.push("LONG", 0.9, "A")
        wm.push("LONG", 0.8, "B")
        result = wm.get_consensus()
        assert result is None  # only 2, need 3
        wm.push("LONG", 0.7, "C")
        result = wm.get_consensus()
        assert result is not None
        assert result[0] == "LONG"
