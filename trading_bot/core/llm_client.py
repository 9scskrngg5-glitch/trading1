"""
LLMClient — Wrapper unifié Anthropic (Claude) + OpenAI (GPT-4o).

Interface unique pour tous les appels LLM du système :
- Retry automatique (3 tentatives, backoff exponentiel)
- Tracking du coût journalier avec coupe-circuit budget
- Timeout configurable par appel
- Lazy init des clients (pas de crash si clés absentes)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Tarifs en $/1M tokens (mis à jour avril 2026)
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":            {"input": 2.50,  "output": 10.0},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.0},
    "claude-opus-4-6":   {"input": 15.0,  "output": 75.0},
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # secondes


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_sec: float


class LLMClient:
    def __init__(
        self,
        anthropic_key: str = "",
        openai_key: str = "",
        daily_budget_usd: float = 10.0,
    ):
        self._anthropic_key    = anthropic_key
        self._openai_key       = openai_key
        self.daily_budget_usd  = daily_budget_usd
        self._daily_spend: float = 0.0
        self._day_start: float   = time.time()
        self._anthropic_client   = None
        self._openai_client      = None

    def _reset_daily_if_needed(self) -> None:
        if time.time() - self._day_start >= 86400:
            self._daily_spend = 0.0
            self._day_start   = time.time()
            logger.info("[LLMClient] Reset budget journalier")

    @property
    def budget_exceeded(self) -> bool:
        self._reset_daily_if_needed()
        return self._daily_spend >= self.daily_budget_usd

    @property
    def daily_spend(self) -> float:
        return self._daily_spend

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
        return self._anthropic_client

    def _get_openai(self):
        if self._openai_client is None:
            import openai as _openai
            self._openai_client = _openai.AsyncOpenAI(api_key=self._openai_key)
        return self._openai_client

    def _calc_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p = PRICING.get(model, {"input": 5.0, "output": 15.0})
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 500,
        timeout: float = 30.0,
    ) -> Optional[LLMResponse]:
        if self.budget_exceeded:
            logger.warning(
                "[LLMClient] Budget journalier %.2f$ dépassé — appel annulé",
                self.daily_budget_usd,
            )
            return None

        t0 = time.time()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = await asyncio.wait_for(
                    self._do_complete(model, prompt, max_tokens),
                    timeout=timeout,
                )
                break
            except asyncio.TimeoutError:
                logger.warning(
                    "[LLMClient] Timeout %.0fs (tentative %d/%d) — %s",
                    timeout, attempt, MAX_RETRIES, model,
                )
                return None
            except Exception as exc:
                logger.warning(
                    "[LLMClient] Erreur tentative %d/%d — %s: %s",
                    attempt, MAX_RETRIES, model, exc,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                else:
                    return None
        else:
            return None

        latency = time.time() - t0
        cost    = self._calc_cost(model, raw.input_tokens, raw.output_tokens)
        self._daily_spend += cost

        logger.debug(
            "[LLMClient] %s | %d+%d tokens | $%.4f | %.1fs",
            model, raw.input_tokens, raw.output_tokens, cost, latency,
        )

        return LLMResponse(
            text=raw.text, model=model,
            input_tokens=raw.input_tokens, output_tokens=raw.output_tokens,
            cost_usd=cost, latency_sec=latency,
        )

    async def _do_complete(self, model: str, prompt: str, max_tokens: int):
        if model.startswith("claude"):
            client = self._get_anthropic()
            msg = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return type("_R", (), {
                "text":          msg.content[0].text,
                "input_tokens":  msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
            })()
        else:
            client = self._get_openai()
            resp = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            usage = resp.usage
            return type("_R", (), {
                "text":          resp.choices[0].message.content,
                "input_tokens":  usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
            })()
