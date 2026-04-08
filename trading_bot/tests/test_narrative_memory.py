"""Tests pour NarrativeMemory — mémoire de patterns en langage naturel."""

import sys
sys.path.insert(0, ".")

import json
import tempfile
from pathlib import Path
from core.narrative_memory import NarrativeMemory, NarrativePattern


def make_memory() -> tuple[NarrativeMemory, Path]:
    tmp = Path(tempfile.mkdtemp())
    return NarrativeMemory(vault_path=tmp), tmp


# ── Ajout de patterns ─────────────────────────────────────────────────────────

def test_add_pattern_creates_file():
    mem, tmp = make_memory()
    mem.add_pattern("BTC/USDT", "trending_bull", "RSI_divergence_bull", "win",
                    "BTC cassure haussière sur volume fort → +4% en 2h")
    assert (tmp / "memory" / "narrative_patterns.jsonl").exists()


def test_add_pattern_increments_count_for_same_key():
    mem, _ = make_memory()
    mem.add_pattern("BTC/USDT", "trending_bull", "RSI_divergence_bull", "win", "Pattern A")
    mem.add_pattern("BTC/USDT", "trending_bull", "RSI_divergence_bull", "win", "Pattern A v2")
    assert len(mem._patterns) == 1
    assert mem._patterns[0].confirmed_count == 2


def test_add_different_assets_creates_separate_entries():
    mem, _ = make_memory()
    mem.add_pattern("BTC/USDT", "ranging", "BB_squeeze", "loss", "BTC fausse cassure")
    mem.add_pattern("ETH/USDT", "ranging", "BB_squeeze", "loss", "ETH fausse cassure")
    assert len(mem._patterns) == 2


# ── Recherche de patterns ─────────────────────────────────────────────────────

def test_find_similar_returns_top_k():
    mem, _ = make_memory()
    mem.add_pattern("BTC/USDT", "trending_bull", "RSI_divergence", "win", "Pattern BTC")
    mem.add_pattern("ETH/USDT", "ranging", "BB_squeeze", "loss", "Pattern ETH")
    mem.add_pattern("SOL/USDT", "trending_bull", "MACD_cross", "win", "Pattern SOL")

    results = mem.find_similar("BTC/USDT", "trending_bull", "RSI_divergence", top_k=2)
    assert len(results) <= 2
    assert results[0].asset == "BTC/USDT"


def test_find_similar_empty_returns_empty_list():
    mem, _ = make_memory()
    results = mem.find_similar("BTC/USDT", "trending_bull", "RSI_divergence")
    assert results == []


def test_find_similar_prefers_same_asset():
    mem, _ = make_memory()
    mem.add_pattern("BTC/USDT", "ranging", "RSI_oversold", "win", "BTC ranging win")
    mem.add_pattern("ETH/USDT", "trending_bull", "RSI_oversold", "win", "ETH trending win")

    results = mem.find_similar("BTC/USDT", "ranging", "RSI_oversold")
    assert results[0].asset == "BTC/USDT"


# ── Persistance ───────────────────────────────────────────────────────────────

def test_patterns_persist_across_reload():
    mem, tmp = make_memory()
    mem.add_pattern("BTC/USDT", "trending_bull", "MACD_cross", "win", "Pattern persistant")

    mem2 = NarrativeMemory(vault_path=tmp)
    assert len(mem2._patterns) == 1
    assert mem2._patterns[0].pattern == "Pattern persistant"


def test_patterns_format_is_valid_jsonl():
    mem, tmp = make_memory()
    mem.add_pattern("BTC/USDT", "ranging", "BB_squeeze", "loss", "Test JSONL")

    lines = (tmp / "memory" / "narrative_patterns.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["asset"] == "BTC/USDT"
    assert data["outcome"] == "loss"
