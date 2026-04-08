"""Tests pour Council — délibération LLM avant chaque trade."""

import sys
sys.path.insert(0, ".")

import asyncio
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from core.council import Council, CouncilVerdict
from core.llm_client import LLMClient, LLMResponse
from core.narrative_memory import NarrativeMemory


def make_mock_llm(text: str = "Réponse mock") -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.budget_exceeded = False
    resp = LLMResponse(
        text=text, model="gpt-4o",
        input_tokens=100, output_tokens=50,
        cost_usd=0.001, latency_sec=0.5,
    )
    llm.complete = AsyncMock(return_value=resp)
    return llm


def make_council(llm=None) -> tuple[Council, Path]:
    tmp = Path(tempfile.mkdtemp())
    mem = NarrativeMemory(vault_path=tmp)
    if llm is None:
        llm = make_mock_llm()
    return Council(llm=llm, narrative_memory=mem, vault_path=tmp), tmp


# ── Verdict normal ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convene_returns_execute_verdict():
    council, _ = make_council(llm=make_mock_llm(
        '{"verdict": "EXECUTE", "confidence_adj": 5, "reasoning": "Signal fort."}'
    ))
    verdict = await council.convene(
        asset="BTC/USDT", direction="BULLISH", confidence=70,
        regime="trending_bull", daily_thesis="BTC en hausse",
        indicators={"rsi": 45, "macd": 0.5},
    )
    assert verdict.verdict == "EXECUTE"
    assert verdict.confidence_adj == 5
    assert verdict.final_confidence == 75


@pytest.mark.asyncio
async def test_convene_returns_passe_verdict():
    council, _ = make_council(llm=make_mock_llm(
        '{"verdict": "PASSE", "confidence_adj": -15, "reasoning": "Risque trop élevé."}'
    ))
    verdict = await council.convene(
        asset="ETH/USDT", direction="BEARISH", confidence=60,
        regime="ranging", daily_thesis="Marché incertain",
        indicators={"rsi": 55},
    )
    assert verdict.verdict == "PASSE"
    assert verdict.final_confidence == 45


# ── Fail-open sur timeout ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convene_failopen_on_timeout():
    async def slow(*args, **kwargs):
        await asyncio.sleep(999)

    llm = MagicMock(spec=LLMClient)
    llm.budget_exceeded = False
    llm.complete = slow

    council, _ = make_council(llm=llm)
    verdict = await council.convene(
        asset="SOL/USDT", direction="BULLISH", confidence=65,
        regime="volatile", daily_thesis="", indicators={},
        timeout=0.01,
    )
    assert verdict.verdict == "EXECUTE"
    assert verdict.confidence_adj == 0
    assert verdict.final_confidence == 65


# ── JSON malformé ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convene_handles_malformed_json():
    council, _ = make_council(llm=make_mock_llm("Pas du JSON valide ici"))
    verdict = await council.convene(
        asset="BTC/USDT", direction="BULLISH", confidence=70,
        regime="trending_bull", daily_thesis="", indicators={},
    )
    assert verdict.verdict in ("EXECUTE", "PASSE", "REDUIS_TAILLE")


# ── Sauvegarde vault ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convene_saves_council_thread_to_vault():
    council, tmp = make_council(llm=make_mock_llm(
        '{"verdict": "EXECUTE", "confidence_adj": 0, "reasoning": "OK."}'
    ))
    await council.convene(
        asset="BTC/USDT", direction="BULLISH", confidence=70,
        regime="trending_bull", daily_thesis="Test", indicators={},
    )
    council_files = list((tmp / "council").glob("*.md"))
    assert len(council_files) == 1
    content = council_files[0].read_text()
    assert "BTC" in content
    assert "EXECUTE" in content
