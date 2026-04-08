# LLM Trading Council — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une couche d'intelligence LLM (GPT-4o + Claude) au-dessus du pipeline algorithmique existant : Conseil de délibération avant chaque trade, briefing matinal narratif, et mémoire de patterns en langage naturel.

**Architecture:** Le pipeline algorithmique existant reste intact. Un `Council` LLM s'interpose dans `RiskAgent._on_prediction()` avant chaque ordre. `MetaAgent` produit une thèse quotidienne (Claude Opus) et un post-mortem après chaque trade. `ScanAgent` enrichit ses signaux avec GPT-4o. Trois nouveaux modules core : `llm_client`, `narrative_memory`, `council`.

**Tech Stack:** Python 3.10+, `anthropic>=0.40`, `openai>=1.50`, asyncio, pytest, modules existants (BaseAgent, MessageBus, ObsidianClient)

---

## Fichiers créés / modifiés

| Action | Fichier |
|---|---|
| **Créer** | `trading_bot/core/llm_client.py` |
| **Créer** | `trading_bot/core/narrative_memory.py` |
| **Créer** | `trading_bot/core/council.py` |
| **Créer** | `trading_bot/tests/test_llm_client.py` |
| **Créer** | `trading_bot/tests/test_narrative_memory.py` |
| **Créer** | `trading_bot/tests/test_council.py` |
| **Modifier** | `trading_bot/requirements.txt` |
| **Modifier** | `trading_bot/core/message_bus.py` (2 canaux) |
| **Modifier** | `trading_bot/core/vault_initializer.py` (5 dossiers) |
| **Modifier** | `trading_bot/agents/meta_agent.py` (briefing + postmortem) |
| **Modifier** | `trading_bot/agents/risk_agent.py` (Council hook) |
| **Modifier** | `trading_bot/agents/scan_agent.py` (enrichissement GPT-4o) |
| **Modifier** | `trading_bot/run_demo.py` (injection LLMClient + NarrativeMemory) |

---

## Task 1 : Dépendances et variables d'environnement

**Files:**
- Modify: `trading_bot/requirements.txt`
- Modify: `trading_bot/.env` (ou créer si absent)

- [ ] **Step 1 : Ajouter anthropic et openai dans requirements.txt**

Ouvrir `trading_bot/requirements.txt` et ajouter à la fin :

```
# ── LLM Clients ──────────────────────────────────────────────────
anthropic>=0.40.0           # Claude Sonnet + Opus (Conseil, briefings)
openai>=1.50.0              # GPT-4o (analyses rapides, 3 analysts)
```

- [ ] **Step 2 : Installer les dépendances**

```bash
cd trading_bot
pip install anthropic>=0.40.0 openai>=1.50.0
```

Résultat attendu : `Successfully installed anthropic-X.X.X openai-X.X.X`

- [ ] **Step 3 : Ajouter les clés dans .env**

Ouvrir `trading_bot/.env` (ou le créer) et ajouter :

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LLM_DAILY_BUDGET_USD=10
```

- [ ] **Step 4 : Ajouter les clés dans CONFIG de run_demo.py**

Dans `trading_bot/run_demo.py`, dans le dict `CONFIG`, ajouter :

```python
    # LLM
    "anthropic_api_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
    "openai_api_key":     os.environ.get("OPENAI_API_KEY", ""),
    "llm_daily_budget":   float(os.environ.get("LLM_DAILY_BUDGET_USD", "10")),
```

- [ ] **Step 5 : Commit**

```bash
git add trading_bot/requirements.txt trading_bot/run_demo.py
git commit -m "feat: add anthropic and openai dependencies for LLM Council"
```

---

## Task 2 : core/llm_client.py

**Files:**
- Create: `trading_bot/core/llm_client.py`
- Create: `trading_bot/tests/test_llm_client.py`

- [ ] **Step 1 : Écrire le test en premier (TDD)**

Créer `trading_bot/tests/test_llm_client.py` :

```python
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
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd trading_bot
pytest tests/test_llm_client.py -v
```

Résultat attendu : `ERROR — ModuleNotFoundError: No module named 'core.llm_client'`

- [ ] **Step 3 : Implémenter core/llm_client.py**

Créer `trading_bot/core/llm_client.py` :

```python
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
    """
    Client LLM unifié avec gestion du budget journalier.

    Usage :
        client = LLMClient(anthropic_key="...", openai_key="...", daily_budget_usd=10.0)
        resp = await client.complete("gpt-4o", "Analyse ce setup...", max_tokens=200)
        if resp:
            print(resp.text, f"coût: ${resp.cost_usd:.4f}")
    """

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

    # ── Budget ────────────────────────────────────────────────────────────────

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

    # ── Clients lazy ─────────────────────────────────────────────────────────

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

    # ── Coût ─────────────────────────────────────────────────────────────────

    def _calc_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p = PRICING.get(model, {"input": 5.0, "output": 15.0})
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

    # ── Interface publique ────────────────────────────────────────────────────

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 500,
        timeout: float = 30.0,
    ) -> Optional[LLMResponse]:
        """
        Appelle le LLM avec retry et timeout.
        Retourne None si budget dépassé, timeout ou erreur persistante.
        """
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
        """Appel brut au bon provider selon le préfixe du modèle."""
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
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
cd trading_bot
pip install pytest pytest-asyncio
pytest tests/test_llm_client.py -v
```

Résultat attendu : tous les tests `PASSED`

- [ ] **Step 5 : Commit**

```bash
git add trading_bot/core/llm_client.py trading_bot/tests/test_llm_client.py
git commit -m "feat: add LLMClient unified wrapper for Anthropic + OpenAI"
```

---

## Task 3 : core/narrative_memory.py

**Files:**
- Create: `trading_bot/core/narrative_memory.py`
- Create: `trading_bot/tests/test_narrative_memory.py`

- [ ] **Step 1 : Écrire les tests**

Créer `trading_bot/tests/test_narrative_memory.py` :

```python
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
    # BTC exact match should be first
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
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd trading_bot
pytest tests/test_narrative_memory.py -v
```

Résultat attendu : `ERROR — ModuleNotFoundError: No module named 'core.narrative_memory'`

- [ ] **Step 3 : Implémenter core/narrative_memory.py**

Créer `trading_bot/core/narrative_memory.py` :

```python
"""
NarrativeMemory — Mémoire de patterns en langage naturel.

Stocke des observations de trading sous forme de phrases humaines,
indexées par (asset, régime, setup). Alimente le Conseil LLM avec
des exemples historiques similaires avant chaque décision de trade.

Stockage : vault/memory/narrative_patterns.jsonl (une entrée JSON par ligne)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NarrativePattern:
    ts: str              # ISO timestamp de création
    asset: str           # ex : "BTC/USDT"
    regime: str          # ex : "trending_bull"
    setup: str           # ex : "RSI_divergence_bull"
    outcome: str         # "win" | "loss"
    pattern: str         # texte en langage naturel
    confirmed_count: int = 1  # nombre de fois confirmé


class NarrativeMemory:
    """
    Mémoire narrative partagée par MetaAgent (écriture) et Council (lecture).

    MetaAgent appelle add_pattern() après chaque post-mortem.
    Council appelle find_similar() avant chaque délibération.
    """

    def __init__(self, vault_path: Path):
        self._path = vault_path / "memory" / "narrative_patterns.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._patterns: list[NarrativePattern] = []
        self._load()

    # ── Persistance ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                self._patterns.append(NarrativePattern(**d))
            except Exception as exc:
                logger.warning("[NarrativeMemory] Ligne ignorée: %s", exc)
        if self._patterns:
            logger.info("[NarrativeMemory] %d patterns chargés", len(self._patterns))

    def _append(self, p: NarrativePattern) -> None:
        """Ajoute une ligne sans réécrire tout le fichier."""
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(p)) + "\n")

    def _save_all(self) -> None:
        """Réécriture complète — uniquement pour les mises à jour (count++)."""
        self._path.write_text(
            "\n".join(json.dumps(asdict(p)) for p in self._patterns) + "\n",
            encoding="utf-8",
        )

    # ── Interface publique ────────────────────────────────────────────────────

    def add_pattern(
        self,
        asset: str,
        regime: str,
        setup: str,
        outcome: str,
        pattern_text: str,
    ) -> None:
        """
        Ajoute ou consolide un pattern.
        Si un pattern (asset, regime, setup) existe déjà → incrémente confirmed_count.
        """
        for p in self._patterns:
            if p.asset == asset and p.regime == regime and p.setup == setup:
                p.confirmed_count += 1
                p.pattern = pattern_text
                self._save_all()
                logger.info(
                    "[NarrativeMemory] Pattern consolidé [×%d] : %s %s",
                    p.confirmed_count, asset, setup,
                )
                return

        new_p = NarrativePattern(
            ts=datetime.now(timezone.utc).isoformat(),
            asset=asset, regime=regime, setup=setup,
            outcome=outcome, pattern=pattern_text,
        )
        self._patterns.append(new_p)
        self._append(new_p)
        logger.info("[NarrativeMemory] Nouveau pattern : %s | %s | %s", asset, regime, setup)

    def find_similar(
        self,
        asset: str,
        regime: str,
        setup: str,
        top_k: int = 3,
    ) -> list[NarrativePattern]:
        """
        Retourne les top_k patterns les plus similaires.
        Score : +3 même asset, +2 même régime, +1 par mot commun dans le setup.
        """
        if not self._patterns:
            return []

        setup_words = set(setup.lower().split("_"))
        scored: list[tuple[int, NarrativePattern]] = []

        for p in self._patterns:
            score = 0
            if p.asset == asset:
                score += 3
            if p.regime == regime:
                score += 2
            p_words = set(p.setup.lower().split("_"))
            score += len(setup_words & p_words)
            scored.append((score, p))

        scored.sort(key=lambda x: (-x[0], -x[1].confirmed_count))
        return [p for _, p in scored[:top_k]]

    def format_for_prompt(self, patterns: list[NarrativePattern]) -> str:
        """Formate les patterns pour injection dans un prompt LLM."""
        if not patterns:
            return "Aucun pattern similaire trouvé dans la mémoire."
        lines = []
        for p in patterns:
            lines.append(
                f"- [{p.outcome.upper()} ×{p.confirmed_count}] {p.pattern}"
            )
        return "\n".join(lines)
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
cd trading_bot
pytest tests/test_narrative_memory.py -v
```

Résultat attendu : tous les tests `PASSED`

- [ ] **Step 5 : Commit**

```bash
git add trading_bot/core/narrative_memory.py trading_bot/tests/test_narrative_memory.py
git commit -m "feat: add NarrativeMemory for LLM-readable pattern storage"
```

---

## Task 4 : core/council.py

**Files:**
- Create: `trading_bot/core/council.py`
- Create: `trading_bot/tests/test_council.py`

- [ ] **Step 1 : Écrire les tests**

Créer `trading_bot/tests/test_council.py` :

```python
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
    # Doit quand même retourner un verdict valide
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
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd trading_bot
pytest tests/test_council.py -v
```

Résultat attendu : `ERROR — ModuleNotFoundError: No module named 'core.council'`

- [ ] **Step 3 : Implémenter core/council.py**

Créer `trading_bot/core/council.py` :

```python
"""
Council — Délibération LLM avant chaque décision de trade.

Le Conseil convoque 3 analysts GPT-4o en parallèle (Bull, Bear, Devil's Advocate),
puis Claude Sonnet arbitre et produit un verdict structuré.

Fail-open : si timeout ou erreur, l'ordre passe avec la confiance algorithmique originale.
Thread complet sauvegardé dans vault/council/ pour traçabilité Obsidian.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.llm_client import LLMClient
from core.narrative_memory import NarrativeMemory

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

_BULL = """\
Tu es un trader haussier senior dans une trading firm. Fais l'argument le plus \
convaincant POUR ce trade en 3 phrases maximum. Ne mentionne pas les risques.

Asset: {asset} | Direction: {direction} | Confiance algo: {confidence}/100
Régime: {regime}
Thèse du jour: {daily_thesis}
Patterns passés similaires:
{patterns}
Indicateurs: {indicators}"""

_BEAR = """\
Tu es un trader baissier senior dans une trading firm. Fais l'argument le plus \
fort CONTRE ce trade en 3 phrases maximum. Ne mentionne pas les opportunités.

Asset: {asset} | Direction: {direction} | Confiance algo: {confidence}/100
Régime: {regime}
Thèse du jour: {daily_thesis}
Patterns passés similaires:
{patterns}
Indicateurs: {indicators}"""

_DEVIL = """\
Tu es l'avocat du diable d'une trading firm. Identifie ce que personne n'a vu \
en 3 phrases maximum. Focus : biais cognitifs, tail risks, information manquante.

Asset: {asset} | Direction: {direction} | Confiance algo: {confidence}/100
Régime: {regime}
Thèse du jour: {daily_thesis}
Patterns passés similaires:
{patterns}
Indicateurs: {indicators}"""

_ARBITRE = """\
Tu es le CIO d'une trading firm. Lis les 3 analyses et tranche.

== BULL ANALYST ==
{bull}

== BEAR ANALYST ==
{bear}

== DEVIL'S ADVOCATE ==
{devil}

Asset: {asset} | Direction: {direction} | Confiance algorithmique: {confidence}/100

Réponds UNIQUEMENT avec ce JSON (rien d'autre, pas de markdown) :
{{"verdict": "EXECUTE", "confidence_adj": 5, "reasoning": "3 phrases max."}}

Valeurs autorisées pour verdict : "EXECUTE", "PASSE", "REDUIS_TAILLE"
confidence_adj : entier entre -20 et +10"""


# ── Dataclass résultat ────────────────────────────────────────────────────────

@dataclass
class CouncilVerdict:
    verdict:          str    # "EXECUTE" | "PASSE" | "REDUIS_TAILLE"
    confidence_adj:   int    # ajustement appliqué à la confiance algo
    reasoning:        str    # raisonnement en 3 phrases
    bull_view:        str    # avis bull analyst
    bear_view:        str    # avis bear analyst
    devil_view:       str    # avis devil's advocate
    final_confidence: int    # confiance finale = algo + adj


# ── Council ───────────────────────────────────────────────────────────────────

class Council:
    """
    Délibération LLM avant chaque trade.

    Usage :
        council = Council(llm=llm_client, narrative_memory=mem, vault_path=vault)
        verdict = await council.convene("BTC/USDT", "BULLISH", 72, "trending_bull", thesis, indicators)
        if verdict.verdict == "PASSE":
            return  # RiskAgent bloque l'ordre
    """

    def __init__(
        self,
        llm: LLMClient,
        narrative_memory: NarrativeMemory,
        vault_path: Path,
    ):
        self._llm     = llm
        self._memory  = narrative_memory
        self._vault   = vault_path
        (vault_path / "council").mkdir(parents=True, exist_ok=True)

    async def convene(
        self,
        asset: str,
        direction: str,
        confidence: int,
        regime: str,
        daily_thesis: str,
        indicators: dict,
        timeout: float = 20.0,
    ) -> CouncilVerdict:
        """
        Lance la délibération complète avec timeout.
        Fail-open : timeout → EXECUTE avec confiance algorithmique originale.
        """
        try:
            return await asyncio.wait_for(
                self._deliberate(asset, direction, confidence, regime, daily_thesis, indicators),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[Council] ⏱ Timeout %.0fs — fail-open pour %s %s",
                timeout, asset, direction,
            )
            return CouncilVerdict(
                verdict="EXECUTE", confidence_adj=0,
                reasoning="Timeout du Conseil — décision algorithmique maintenue.",
                bull_view="N/A", bear_view="N/A", devil_view="N/A",
                final_confidence=confidence,
            )

    async def _deliberate(
        self, asset, direction, confidence, regime, daily_thesis, indicators,
    ) -> CouncilVerdict:
        # ── Contexte narratif ──
        patterns = self._memory.find_similar(
            asset, regime, f"{direction.lower()}_signal",
        )
        patterns_text = self._memory.format_for_prompt(patterns)

        ctx = dict(
            asset=asset, direction=direction, confidence=confidence,
            regime=regime,
            daily_thesis=daily_thesis or "Aucune thèse disponible.",
            patterns=patterns_text,
            indicators=str(indicators),
        )

        # ── 3 analysts GPT-4o en parallèle ──
        bull_resp, bear_resp, devil_resp = await asyncio.gather(
            self._llm.complete("gpt-4o", _BULL.format(**ctx),  max_tokens=200, timeout=15.0),
            self._llm.complete("gpt-4o", _BEAR.format(**ctx),  max_tokens=200, timeout=15.0),
            self._llm.complete("gpt-4o", _DEVIL.format(**ctx), max_tokens=200, timeout=15.0),
        )

        bull_text  = bull_resp.text  if bull_resp  else "Analyst indisponible."
        bear_text  = bear_resp.text  if bear_resp  else "Analyst indisponible."
        devil_text = devil_resp.text if devil_resp else "Analyst indisponible."

        # ── Arbitre Claude Sonnet ──
        arb_prompt = _ARBITRE.format(
            bull=bull_text, bear=bear_text, devil=devil_text,
            asset=asset, direction=direction, confidence=confidence,
        )
        arb_resp = await self._llm.complete(
            "claude-sonnet-4-6", arb_prompt, max_tokens=300, timeout=15.0,
        )

        verdict_data = self._parse_verdict(arb_resp.text if arb_resp else "")

        verdict = CouncilVerdict(
            verdict=verdict_data.get("verdict", "EXECUTE"),
            confidence_adj=int(verdict_data.get("confidence_adj", 0)),
            reasoning=verdict_data.get("reasoning", "Raisonnement indisponible."),
            bull_view=bull_text, bear_view=bear_text, devil_view=devil_text,
            final_confidence=confidence + int(verdict_data.get("confidence_adj", 0)),
        )

        self._save_thread(asset, direction, confidence, regime, verdict)
        logger.info(
            "[Council] %s %s → %s (conf %d→%d) | %s",
            asset, direction, verdict.verdict,
            confidence, verdict.final_confidence,
            verdict.reasoning[:80],
        )
        return verdict

    def _parse_verdict(self, text: str) -> dict:
        """Parse le JSON de l'arbitre avec fallback robuste."""
        # Essai direct
        try:
            return json.loads(text.strip())
        except Exception:
            pass
        # Extraction regex
        m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        logger.warning("[Council] Impossible de parser le verdict : %s", text[:200])
        return {"verdict": "EXECUTE", "confidence_adj": 0, "reasoning": text[:200]}

    def _save_thread(
        self, asset, direction, confidence, regime, v: CouncilVerdict,
    ) -> None:
        """Sauvegarde le thread complet dans vault/council/."""
        now      = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y-%m-%d_%H-%M')}_{asset.replace('/', '-')}_{direction}.md"
        path     = self._vault / "council" / filename

        content = f"""---
asset: {asset}
direction: {direction}
confidence_algo: {confidence}
confidence_final: {v.final_confidence}
verdict: {v.verdict}
regime: {regime}
date: {now.isoformat()}
tags: [council, trade-decision]
---

# Conseil de Trading — {asset} {direction}

## Verdict : {v.verdict}
**Confiance :** {confidence} → {v.final_confidence} ({v.confidence_adj:+d})

**Raisonnement :** {v.reasoning}

---

## Bull Analyst
{v.bull_view}

## Bear Analyst
{v.bear_view}

## Devil's Advocate
{v.devil_view}

---
_Généré par Council | {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""
        path.write_text(content, encoding="utf-8")
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
cd trading_bot
pytest tests/test_council.py -v
```

Résultat attendu : tous les tests `PASSED`

- [ ] **Step 5 : Commit**

```bash
git add trading_bot/core/council.py trading_bot/tests/test_council.py
git commit -m "feat: add Council LLM deliberation system with Bull/Bear/Devil/Arbitre"
```

---

## Task 5 : MetaAgent — Briefing Matinal et Post-Mortem

**Files:**
- Modify: `trading_bot/agents/meta_agent.py`

- [ ] **Step 1 : Ajouter les imports et attributs dans __init__**

Dans `trading_bot/agents/meta_agent.py`, ajouter les imports en haut du fichier (après les imports existants) :

```python
from core.llm_client import LLMClient
from core.narrative_memory import NarrativeMemory
```

Dans `MetaAgent.__init__()`, après `self._adjustments: deque = deque(maxlen=20)`, ajouter :

```python
        # ── LLM (briefing + postmortem) ───────────────────────────────────────
        self._llm: LLMClient | None         = None
        self._narrative_memory: NarrativeMemory | None = None
        self._daily_thesis: str             = ""
        self._last_briefing_date: str       = ""  # "YYYY-MM-DD" du dernier briefing
```

Modifier la signature de `__init__` pour accepter les nouveaux paramètres :

```python
    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        tracker: PerformanceTracker,
        config: dict,
        telegram=None,
        llm: LLMClient | None = None,
        narrative_memory: NarrativeMemory | None = None,
    ):
        super().__init__("MetaAgent", "reports", bus, obsidian, config)
        self.tracker  = tracker
        self.telegram = telegram
        self._llm              = llm
        self._narrative_memory = narrative_memory
        # ... reste du __init__ inchangé
```

- [ ] **Step 2 : Ajouter _daily_briefing() dans MetaAgent**

Ajouter cette méthode dans la classe `MetaAgent`, après `setup()` :

```python
    async def _daily_briefing(self) -> None:
        """
        Briefing matinal par Claude Opus.
        Produit la thèse du jour publiée sur canal daily_thesis.
        Sauvegardée dans vault/briefing/YYYY-MM-DD_briefing.md
        """
        if not self._llm:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_briefing_date == today:
            return  # déjà fait aujourd'hui

        snap = self.tracker.snapshot()

        # Récupérer les patterns narratifs récents (top 5)
        recent_patterns = ""
        if self._narrative_memory:
            all_p = self._narrative_memory._patterns[-10:]
            recent_patterns = "\n".join(
                f"- [{p.outcome.upper()} ×{p.confirmed_count}] {p.pattern}"
                for p in all_p
            ) or "Aucun pattern enregistré."

        prompt = f"""\
Tu es le stratégiste en chef d'une trading firm. Rédige la thèse de marché du jour \
en 200 mots maximum. Sois précis, actionnable, et honnête sur les incertitudes.

Date : {today}
Assets suivis : BTC/USDT, ETH/USDT, SOL/USDT
Capital actuel : ${snap.get('capital', 0):,.0f}
Win rate récent : {snap.get('win_rate', 0)*100:.1f}%
Drawdown actuel : {snap.get('max_drawdown_pct', 0):.1f}%

Patterns récents mémorisés :
{recent_patterns}

Structure de ta réponse :
1. Contexte macro (1-2 phrases)
2. Setup technique prioritaire du jour (1-2 phrases)
3. Biais directionnel par asset (1 phrase par asset)
4. Risques à surveiller aujourd'hui (1-2 phrases)
5. Règle de conduite du jour (1 phrase)"""

        resp = await self._llm.complete("claude-opus-4-6", prompt, max_tokens=400, timeout=60.0)
        if not resp:
            logger.warning("[MetaAgent] Briefing échoué — LLM indisponible")
            return

        self._daily_thesis       = resp.text
        self._last_briefing_date = today

        # Publier sur le bus
        await self.bus.publish(CHANNELS["daily_thesis"], {
            "type":   "daily_thesis",
            "date":   today,
            "thesis": self._daily_thesis,
            "cost":   resp.cost_usd,
        })

        # Sauvegarder dans le vault
        briefing_dir = self.obsidian.vault_path / "briefing"
        briefing_dir.mkdir(exist_ok=True)
        path = briefing_dir / f"{today}_briefing.md"
        path.write_text(
            f"---\ndate: {today}\ntype: daily_briefing\ntags: [briefing, thesis]\n---\n\n"
            f"# Thèse du Jour — {today}\n\n{self._daily_thesis}\n\n"
            f"---\n_Généré par MetaAgent (Claude Opus) | coût: ${resp.cost_usd:.4f}_\n",
            encoding="utf-8",
        )

        logger.info("[MetaAgent] Briefing matinal généré ($%.4f)", resp.cost_usd)
        if self.telegram:
            try:
                await self.telegram.send_message(
                    f"☀️ **Thèse du {today}**\n\n{self._daily_thesis}"
                )
            except Exception:
                pass
```

- [ ] **Step 3 : Ajouter _run_postmortem() dans MetaAgent**

Ajouter cette méthode dans la classe `MetaAgent` :

```python
    async def _run_postmortem(self, trade_data: dict) -> None:
        """
        Post-mortem d'un trade clôturé par Claude Opus.
        Extrait le pattern narratif et l'ajoute à NarrativeMemory.
        Sauvegardé dans vault/postmortems/
        """
        if not self._llm or not self._narrative_memory:
            return

        asset    = trade_data.get("asset", "INCONNU")
        pnl_pct  = trade_data.get("pnl_pct", 0.0)
        is_win   = trade_data.get("is_win", False)
        regime   = trade_data.get("regime", "unknown")
        direction = trade_data.get("direction", "UNKNOWN")
        conf     = trade_data.get("confidence", 0)

        prompt = f"""\
Tu es l'analyste post-trade d'une trading firm. Analyse ce trade clôturé \
et extrais l'enseignement le plus important en 5 lignes.

Asset: {asset}
Direction: {direction}
Confiance au signal: {conf}/100
Régime au moment du trade: {regime}
Résultat: {'GAIN' if is_win else 'PERTE'} ({pnl_pct:+.2f}%)
Thèse du jour au moment du trade: {self._daily_thesis[:300] if self._daily_thesis else 'Non disponible'}

Réponds dans ce format exact :
ATTENDU: [ce qu'on pensait qu'il allait se passer]
REEL: [ce qui s'est passé]
RATE: [ce qu'on a raté ou ignoré]
PATTERN: [1 phrase mémorisable sur ce setup dans ce régime]
REGLE: [règle concrète pour le prochain trade similaire]"""

        resp = await self._llm.complete("claude-opus-4-6", prompt, max_tokens=300, timeout=45.0)
        if not resp:
            return

        # Extraire le pattern pour NarrativeMemory
        pattern_line = ""
        for line in resp.text.splitlines():
            if line.startswith("PATTERN:"):
                pattern_line = line.replace("PATTERN:", "").strip()
                break
        if not pattern_line:
            pattern_line = resp.text[:150]

        setup = f"{direction.lower()}_signal"
        self._narrative_memory.add_pattern(
            asset=asset, regime=regime, setup=setup,
            outcome="win" if is_win else "loss",
            pattern_text=pattern_line,
        )

        # Sauvegarder dans vault/postmortems/
        now = datetime.now(timezone.utc)
        pm_dir = self.obsidian.vault_path / "postmortems"
        pm_dir.mkdir(exist_ok=True)
        filename = f"{now.strftime('%Y-%m-%d_%H-%M')}_{asset.replace('/', '-')}.md"
        (pm_dir / filename).write_text(
            f"---\nasset: {asset}\noutcome: {'win' if is_win else 'loss'}\n"
            f"pnl_pct: {pnl_pct:.2f}\ndate: {now.isoformat()}\ntags: [postmortem]\n---\n\n"
            f"# Post-Mortem — {asset} {'✅' if is_win else '❌'} ({pnl_pct:+.2f}%)\n\n"
            f"{resp.text}\n\n---\n_Généré par MetaAgent (Claude Opus) | ${resp.cost_usd:.4f}_\n",
            encoding="utf-8",
        )
        logger.info("[MetaAgent] Post-mortem %s (%s) généré", asset, "WIN" if is_win else "LOSS")
```

- [ ] **Step 4 : Brancher le briefing dans run_cycle() et le postmortem dans _on_trade_closed()**

Dans `run_cycle()` de MetaAgent, ajouter en début de méthode :

```python
    async def run_cycle(self) -> None:
        # Briefing matinal (une fois par jour, tôt le matin)
        now_hour = datetime.now(timezone.utc).hour
        if 7 <= now_hour <= 9:
            await self._daily_briefing()

        # ... reste du run_cycle inchangé
```

Dans `_on_trade_closed()`, après `self._recent_trades.append(...)`, ajouter :

```python
        # Post-mortem LLM (async, ne bloque pas le handler)
        asyncio.create_task(self._run_postmortem(data))
```

- [ ] **Step 5 : Abonner MetaAgent au canal daily_thesis pour lire sa propre thèse**

Dans `_register_subscriptions()` de MetaAgent, ajouter :

```python
        self.bus.subscribe(CHANNELS["daily_thesis"], self._on_daily_thesis)
```

Ajouter le handler :

```python
    async def _on_daily_thesis(self, data: dict) -> None:
        self._daily_thesis = data.get("thesis", "")
```

- [ ] **Step 6 : Commit**

```bash
git add trading_bot/agents/meta_agent.py
git commit -m "feat: add MetaAgent daily briefing (Claude Opus) and trade postmortem"
```

---

## Task 6 : RiskAgent — Hook Conseil avant chaque ordre

**Files:**
- Modify: `trading_bot/agents/risk_agent.py`

- [ ] **Step 1 : Ajouter les imports et attributs**

Dans `trading_bot/agents/risk_agent.py`, ajouter les imports :

```python
from core.council import Council, CouncilVerdict
```

Modifier la signature de `RiskAgent.__init__()` pour accepter `council` et `daily_thesis_ref` :

```python
    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        tracker: PerformanceTracker,
        telegram=None,
        config: dict = None,
        council: Council | None = None,
        daily_thesis_ref: list | None = None,  # list[str] d'un élément, référence mutable
    ):
        # ... code existant inchangé ...
        self._council = council
        self._daily_thesis_ref = daily_thesis_ref or []
```

- [ ] **Step 2 : Insérer le hook Council dans _on_prediction()**

Dans `_on_prediction()`, trouver le bloc de sizing de la position (après les gardes-fous). Il y a un bloc qui calcule `entry_price`, `stop_loss`, etc. Juste **avant** la ligne `await self.bus.publish(CHANNELS["orders_validated"], ...)`, ajouter :

```python
        # ── Conseil LLM (délibération avant exécution) ────────────────────────
        if self._council:
            daily_thesis = self._daily_thesis_ref[0] if self._daily_thesis_ref else ""
            council_verdict = await self._council.convene(
                asset=asset,
                direction=str(direction),
                confidence=confidence,
                regime=data.get("regime", "unknown"),
                daily_thesis=daily_thesis,
                indicators={
                    "rsi":       data.get("rsi", 0),
                    "macd_hist": data.get("macd_hist", 0),
                    "bb_pos":    data.get("bb_position", 0),
                    "atr":       data.get("atr", 0),
                },
            )

            if council_verdict.verdict == "PASSE":
                logger.info(
                    "[%s] 🛑 CONSEIL: PASSE sur %s (conf %d→%d) — %s",
                    self.name, asset,
                    confidence, council_verdict.final_confidence,
                    council_verdict.reasoning,
                )
                return  # Ordre bloqué par le Conseil

            if council_verdict.verdict == "REDUIS_TAILLE":
                position_size = position_size * 0.5
                logger.info(
                    "[%s] ⚠️ CONSEIL: REDUIS_TAILLE sur %s — taille ÷2",
                    self.name, asset,
                )

            # Mise à jour confiance avec ajustement du Conseil
            confidence = max(0, min(100, council_verdict.final_confidence))
```

- [ ] **Step 3 : Brancher daily_thesis depuis MetaAgent**

Dans `_register_subscriptions()` de RiskAgent, ajouter :

```python
        self.bus.subscribe(CHANNELS["daily_thesis"], self._on_daily_thesis)
```

Ajouter le handler :

```python
    async def _on_daily_thesis(self, data: dict) -> None:
        if self._daily_thesis_ref is not None:
            if self._daily_thesis_ref:
                self._daily_thesis_ref[0] = data.get("thesis", "")
            else:
                self._daily_thesis_ref.append(data.get("thesis", ""))
```

- [ ] **Step 4 : Commit**

```bash
git add trading_bot/agents/risk_agent.py
git commit -m "feat: add Council LLM deliberation hook in RiskAgent before order execution"
```

---

## Task 7 : ScanAgent — Enrichissement GPT-4o

**Files:**
- Modify: `trading_bot/agents/scan_agent.py`

- [ ] **Step 1 : Ajouter l'import et l'attribut llm**

Dans `trading_bot/agents/scan_agent.py`, ajouter l'import :

```python
from core.llm_client import LLMClient
```

Modifier `ScanAgent.__init__()` pour accepter `llm` :

```python
    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        config: dict,
        market_data=None,
        llm: LLMClient | None = None,
    ):
        super().__init__("ScanAgent", "technique", bus, obsidian, config)
        self.learning    = learning
        self.memory: AgentMemory = None
        self._exchanges: dict    = {}
        self._market_data = market_data
        self._llm = llm
```

- [ ] **Step 2 : Ajouter _enrich_with_llm() dans ScanAgent**

Ajouter cette méthode dans `ScanAgent` :

```python
    async def _enrich_with_llm(
        self,
        pair: str,
        timeframe: str,
        direction: str,
        confidence: int,
        rsi: float,
        macd_hist: float,
        bb_position: float,
        regime: str = "unknown",
    ) -> str:
        """
        Enrichit le signal avec un commentaire GPT-4o en 2 phrases.
        Retourne "" si LLM indisponible ou timeout.
        """
        if not self._llm or self._llm.budget_exceeded:
            return ""

        prompt = f"""\
Tu es un analyste technique senior. En 2 phrases courtes, dis si ce setup \
est techniquement valide ou douteux et pourquoi.

Asset: {pair} | Timeframe: {timeframe}
Direction: {direction} | Confiance algo: {confidence}/100
RSI: {rsi:.1f} | MACD hist: {macd_hist:.4f} | BB position: {bb_position:.2f}
Régime de marché: {regime}"""

        resp = await self._llm.complete("gpt-4o", prompt, max_tokens=100, timeout=5.0)
        return resp.text if resp else ""
```

- [ ] **Step 3 : Appeler _enrich_with_llm() dans _analyze()**

Dans `_analyze()`, après la ligne qui calcule `direction, confidence = self._adaptive_score(...)` et après les ajustements order book (vers la fin de la méthode, juste avant de construire le `TechnicalSignal`), ajouter :

```python
        # ── Enrichissement GPT-4o (si confiance suffisante) ──────────────────
        llm_comment = ""
        if confidence >= MIN_CONFIDENCE and self._llm:
            regime = self._get_current_regime(pair)
            llm_comment = await self._enrich_with_llm(
                pair=pair, timeframe=timeframe,
                direction=direction.value if hasattr(direction, "value") else str(direction),
                confidence=confidence,
                rsi=last_rsi, macd_hist=last_hist,
                bb_position=bb_pos,
                regime=regime,
            )
```

Puis inclure `llm_comment` dans le signal publié. Dans le dict publié sur le bus (dans `_process()`), le signal est `signal.to_dict()`. Modifier `_process()` pour ajouter le commentaire :

```python
    async def _process(self, pair: str, timeframe: str) -> None:
        signal = await self._analyze(pair, timeframe)
        if signal:
            signal_dict = signal.to_dict()
            # Ajouter le commentaire LLM si disponible (stocké temporairement sur l'objet)
            if hasattr(signal, "_llm_comment"):
                signal_dict["llm_comment"] = signal._llm_comment
            await self.bus.publish(CHANNELS["signals_technical"], signal_dict)
            self._write_vault_note(signal)
```

Ajouter une méthode helper :

```python
    def _get_current_regime(self, pair: str) -> str:
        """Récupère le régime courant depuis la mémoire de l'agent."""
        return self.memory.adaptive_params.get(f"regime:{pair}", "unknown")
```

Juste avant de construire le `TechnicalSignal` dans `_analyze()`, ajouter :

```python
        signal = TechnicalSignal(...)  # ligne existante
        signal._llm_comment = llm_comment  # attacher temporairement
        return signal
```

- [ ] **Step 4 : Commit**

```bash
git add trading_bot/agents/scan_agent.py
git commit -m "feat: add GPT-4o signal enrichment in ScanAgent"
```

---

## Task 8 : message_bus.py + VaultInitializer

**Files:**
- Modify: `trading_bot/core/message_bus.py`
- Modify: `trading_bot/core/vault_initializer.py`

- [ ] **Step 1 : Ajouter les 2 nouveaux canaux dans message_bus.py**

Dans `trading_bot/core/message_bus.py`, dans le dict `CHANNELS`, ajouter :

```python
    # ── Intelligence LLM ─────────────────────────────────────────────────────
    "daily_thesis":   "meta:daily_thesis",   # MetaAgent → tous les agents
    "council_result": "council:result",      # Council → logs
```

- [ ] **Step 2 : Faire la même modification dans message_bus_local.py**

Dans `trading_bot/core/message_bus_local.py`, si `CHANNELS` y est importé ou redéfini, vérifier qu'il utilise bien le même dict que `message_bus.py`. Si `LocalMessageBus` importe `CHANNELS` depuis `message_bus`, aucune modification nécessaire. Sinon, ajouter les mêmes 2 entrées.

Vérifier en lisant le début de `message_bus_local.py` :

```bash
head -20 trading_bot/core/message_bus_local.py
```

- [ ] **Step 3 : Ajouter les 5 nouveaux dossiers dans VaultInitializer**

Dans `trading_bot/core/vault_initializer.py`, dans la liste `VAULT_FOLDERS`, ajouter après `"supervision"` :

```python
    # ── LLM Intelligence ──
    "briefing",     # MetaAgent — thèses quotidiennes (Claude Opus)
    "council",      # Council — threads de délibération par trade
    "postmortems",  # MetaAgent — post-mortems par trade
    "memory",       # NarrativeMemory — narrative_patterns.jsonl
    "llm_logs",     # LLMClient — coûts et logs des appels
```

- [ ] **Step 4 : Commit**

```bash
git add trading_bot/core/message_bus.py trading_bot/core/message_bus_local.py trading_bot/core/vault_initializer.py
git commit -m "feat: add daily_thesis channel and 5 new vault folders for LLM system"
```

---

## Task 9 : run_demo.py — Intégration finale

**Files:**
- Modify: `trading_bot/run_demo.py`

- [ ] **Step 1 : Ajouter les imports dans run_demo.py**

En haut de `trading_bot/run_demo.py`, après les imports existants, ajouter :

```python
from core.llm_client       import LLMClient
from core.narrative_memory import NarrativeMemory
from core.council          import Council
```

- [ ] **Step 2 : Instancier LLMClient, NarrativeMemory et Council dans main()**

Dans `main()`, après `vault_init.initialize()`, ajouter :

```python
    # ── LLM Intelligence ─────────────────────────────────────────────────────
    llm_client = LLMClient(
        anthropic_key  = CONFIG.get("anthropic_api_key", ""),
        openai_key     = CONFIG.get("openai_api_key", ""),
        daily_budget_usd = CONFIG.get("llm_daily_budget", 10.0),
    )
    narrative_memory = NarrativeMemory(vault_path=VAULT_PATH)
    council = Council(
        llm=llm_client,
        narrative_memory=narrative_memory,
        vault_path=VAULT_PATH,
    )
    # Référence mutable partagée pour la thèse du jour
    daily_thesis_ref: list[str] = []

    logger.info(
        "🧠 LLM Council actif | Budget: $%.1f/jour | Patterns: %d",
        CONFIG.get("llm_daily_budget", 10.0),
        len(narrative_memory._patterns),
    )
```

- [ ] **Step 3 : Passer les nouveaux objets aux agents dans main()**

Modifier l'instanciation de `scan_agent` :

```python
    scan_agent = ScanAgent(bus, obsidian, learning, cfg("ScanAgent"),
                           market_data=market_data, llm=llm_client)
```

Modifier l'instanciation de `risk_agent` :

```python
    risk_agent = RiskAgent(bus, obsidian, learning, tracker, telegram,
                           cfg("RiskAgent"), council=council,
                           daily_thesis_ref=daily_thesis_ref)
```

Modifier l'instanciation de `meta_agent` :

```python
    meta_agent = MetaAgent(bus, obsidian, tracker, cfg("MetaAgent"),
                           telegram=telegram, llm=llm_client,
                           narrative_memory=narrative_memory)
```

- [ ] **Step 4 : Ajouter le log de démarrage**

Dans le bloc de logs après le démarrage des agents, ajouter :

```python
    logger.info("🧠  LLM Council : GPT-4o (analysts) + Claude Sonnet (arbitre) + Claude Opus (CEO)")
    logger.info("📓  Vault LLM : /briefing/ /council/ /postmortems/ /memory/ /llm_logs/")
```

- [ ] **Step 5 : Commit**

```bash
git add trading_bot/run_demo.py
git commit -m "feat: wire LLMClient, NarrativeMemory and Council into main pipeline"
```

---

## Task 10 : Vérification finale

**Files:** aucun fichier modifié — validation uniquement

- [ ] **Step 1 : Lancer tous les tests**

```bash
cd trading_bot
pytest tests/ -v
```

Résultat attendu : tous les tests `PASSED` (tests existants + 3 nouveaux fichiers)

- [ ] **Step 2 : Vérifier l'import complet sans erreur**

```bash
cd trading_bot
python -c "from core.llm_client import LLMClient; from core.narrative_memory import NarrativeMemory; from core.council import Council; print('Imports OK')"
```

Résultat attendu : `Imports OK`

- [ ] **Step 3 : Lancer en mode simulation (sans vraies clés API)**

Sans clés API configurées, le bot doit démarrer normalement. Le Council et le Briefing seront silencieux (LLM non disponible) mais le pipeline algorithmique tourne comme avant.

```bash
cd trading_bot
python run_demo.py
```

Résultat attendu : démarrage sans erreur, logs normaux + `🧠 LLM Council actif`

- [ ] **Step 4 : Vérifier que les 5 nouveaux dossiers vault sont créés**

```bash
ls trading_bot/vault/
```

Résultat attendu : `briefing  council  llm_logs  memory  postmortems` présents parmi les autres dossiers

- [ ] **Step 5 : Commit final**

```bash
git add -A
git commit -m "feat: LLM Trading Council complete — briefing matinal, délibération, mémoire narrative"
```

---

## Résumé des changements

| Fichier | Type | Changement |
|---|---|---|
| `core/llm_client.py` | Nouveau | Wrapper unifié Anthropic + OpenAI |
| `core/narrative_memory.py` | Nouveau | Mémoire patterns en langage naturel |
| `core/council.py` | Nouveau | Délibération Bull/Bear/Devil/Arbitre |
| `agents/meta_agent.py` | Modifié | Briefing matinal + post-mortem (Claude Opus) |
| `agents/risk_agent.py` | Modifié | Hook Council avant chaque ordre |
| `agents/scan_agent.py` | Modifié | Enrichissement GPT-4o des signaux |
| `core/message_bus.py` | Modifié | 2 nouveaux canaux |
| `core/vault_initializer.py` | Modifié | 5 nouveaux dossiers |
| `run_demo.py` | Modifié | Injection LLMClient, NarrativeMemory, Council |
| `requirements.txt` | Modifié | anthropic, openai |
