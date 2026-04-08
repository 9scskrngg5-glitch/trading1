"""Tests pour LLMClient — wrapper unifié Anthropic + OpenAI."""

import sys
sys.path.insert(0, ".")

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm_client import LLMClient, LLMResponse, PRICING


# ── Tests budget ─────────────────────────────────────────────────────────────

def test_budget_not_exceeded_initially():
    client = LLMClient(daily_budget_usd=10.0)
    assert client.budget_exceeded is False


def test_budget_exceeded_when_spend_over_limit():
    client = LLMClient(daily_budget_usd=1.0)
    client._daily_spend = 1.5
    assert client.budget_exceeded is True


def test_daily_spend_resets_after_24h():
    import time
    client = LLMClient(daily_budget_usd=1.0)
    client._daily_spend = 999.0
    client._day_start = time.time() - 90000  # 25h ago
    assert client.budget_exceeded is False


# ── Tests coût ────────────────────────────────────────────────────────────────

def test_cost_calculation_gpt4o():
    client = LLMClient()
    cost = client._calc_cost("gpt-4o", input_tokens=1000, output_tokens=500)
    expected = (1000 * 2.50 + 500 * 10.0) / 1_000_000
    assert abs(cost - expected) < 1e-9


def test_cost_calculation_claude_sonnet():
    client = LLMClient()
    cost = client._calc_cost("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
    expected = (1000 * 3.00 + 500 * 15.0) / 1_000_000
    assert abs(cost - expected) < 1e-9


# ── Tests complete() ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_returns_none_when_budget_exceeded():
    client = LLMClient(daily_budget_usd=0.0)
    client._daily_spend = 1.0
    result = await client.complete("gpt-4o", "test prompt")
    assert result is None


@pytest.mark.asyncio
async def test_complete_returns_none_on_timeout():
    client = LLMClient(daily_budget_usd=100.0)

    async def slow_complete(*args, **kwargs):
        await asyncio.sleep(999)

    client._do_complete = slow_complete
    result = await client.complete("gpt-4o", "test", timeout=0.01)
    assert result is None


@pytest.mark.asyncio
async def test_complete_accumulates_spend():
    client = LLMClient(daily_budget_usd=100.0)

    fake_result = MagicMock()
    fake_result.text = "Hello"
    fake_result.input_tokens = 10
    fake_result.output_tokens = 5

    client._do_complete = AsyncMock(return_value=fake_result)

    resp = await client.complete("gpt-4o", "test", timeout=5.0)
    assert resp is not None
    assert resp.text == "Hello"
    assert client._daily_spend > 0


@pytest.mark.asyncio
async def test_complete_returns_llm_response():
    client = LLMClient(daily_budget_usd=100.0)

    fake_result = MagicMock()
    fake_result.text = "Réponse test"
    fake_result.input_tokens = 100
    fake_result.output_tokens = 50

    client._do_complete = AsyncMock(return_value=fake_result)

    resp = await client.complete("claude-sonnet-4-6", "test prompt", timeout=5.0)
    assert isinstance(resp, LLMResponse)
    assert resp.model == "claude-sonnet-4-6"
    assert resp.text == "Réponse test"
    assert resp.cost_usd > 0
    assert resp.latency_sec >= 0
