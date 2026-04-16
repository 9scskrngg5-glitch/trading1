"""
HermesClient — Intégration hermes-agent (NousResearch) dans ORACLE v2.

Fournit :
  1. OpenRouter LLM client (partagé, lazy-init)
  2. Mixture-of-Agents (MoA) pour les décisions critiques du Parlement
  3. Hook lifecycle (gateway:startup, session:start, agent:step, agent:end)

Sources : https://github.com/NousResearch/hermes-agent
"""
import asyncio
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger("ORACLE.HermesClient")

# ─── OpenRouter lazy client ───────────────────────────────────────────────────

_openrouter_client = None


def _get_openrouter_client():
    """Retourne un client AsyncOpenAI pointant sur OpenRouter. Lazy + partagé."""
    global _openrouter_client
    if _openrouter_client is not None:
        return _openrouter_client

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    try:
        from openai import AsyncOpenAI
        _openrouter_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        logger.info("HermesClient: OpenRouter client initialisé")
    except ImportError:
        logger.debug("openai package non installé — OpenRouter indisponible")
        _openrouter_client = None

    return _openrouter_client


# ─── Mixture of Agents ────────────────────────────────────────────────────────

# Modèles de référence (parallèles, gratuits/pas chers sur OpenRouter)
REFERENCE_MODELS = [
    "google/gemma-2-9b-it:free",
    "nvidia/llama-3.1-nemotron-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

# Modèle agrégateur (synthèse finale)
AGGREGATOR_MODEL = "google/gemma-2-9b-it:free"

REFERENCE_TEMPERATURE = 0.6
AGGREGATOR_TEMPERATURE = 0.3
MIN_SUCCESSFUL_REFERENCES = 1


async def _call_reference_model(
    client,
    model: str,
    messages: List[Dict],
    temperature: float,
    max_tokens: int = 150,
) -> Optional[str]:
    """Appelle un modèle de référence. Retourne None si échec."""
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=12.0,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        logger.debug(f"MoA reference [{model}] failed: {e}")
        return None


async def mixture_of_agents(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 200,
) -> Optional[str]:
    """
    Mixture-of-Agents (MoA) — synthèse multi-modèles.

    Étapes :
      1. K modèles de référence génèrent des réponses en parallèle
      2. Un agrégateur synthétise les réponses en une réponse finale

    Retourne None si OpenRouter n'est pas disponible.
    """
    client = _get_openrouter_client()
    if client is None:
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # 1. Appels parallèles aux modèles de référence
    tasks = [
        _call_reference_model(client, model, messages, REFERENCE_TEMPERATURE)
        for model in REFERENCE_MODELS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    references = [r for r in results if isinstance(r, str) and r]

    if len(references) < MIN_SUCCESSFUL_REFERENCES:
        logger.debug(f"MoA: seulement {len(references)} réponse(s) de référence — abandon")
        return None

    # 2. Agrégation
    ref_block = "\n\n".join(f"[Modèle {i+1}]:\n{r}" for i, r in enumerate(references))
    agg_messages = [
        {
            "role": "system",
            "content": (
                "Tu es un agrégateur expert. Tu reçois plusieurs réponses d'analyse "
                "de trading et tu dois en faire une synthèse concise et précise en français. "
                "Garde uniquement les insights les plus pertinents. 2-3 phrases max."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question originale: {prompt}\n\n"
                f"Réponses des modèles de référence:\n{ref_block}\n\n"
                "Synthèse finale:"
            ),
        },
    ]

    try:
        agg_resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=AGGREGATOR_MODEL,
                messages=agg_messages,
                temperature=AGGREGATOR_TEMPERATURE,
                max_tokens=max_tokens,
            ),
            timeout=15.0,
        )
        content = agg_resp.choices[0].message.content
        if content and content.strip():
            logger.debug(f"MoA: synthèse obtenue ({len(references)} refs)")
            return content.strip()
    except Exception as e:
        logger.debug(f"MoA aggregator failed: {e}")

    # Fallback: retourne la première réponse de référence
    return references[0] if references else None


# ─── HermesClient ─────────────────────────────────────────────────────────────

class HermesClient:
    """
    Façade d'intégration hermes-agent pour ORACLE v2.

    Usage :
        hermes = HermesClient()
        text = await hermes.narrate("Signal LONG fort sur BTC")
        text = await hermes.moa_decide("Dois-je entrer LONG sur BTC maintenant?", context)
    """

    def __init__(self):
        self._hooks: Dict[str, List] = {}  # event → [callable]
        self._initialized = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def startup(self) -> None:
        """Équivalent hermes gateway:startup."""
        if self._initialized:
            return
        client = _get_openrouter_client()
        status = "✅ OpenRouter disponible" if client else "⚠ OpenRouter non configuré"
        logger.info(f"HermesClient startup — {status}")
        self._emit("gateway:startup", {"status": status})
        self._initialized = True

    def _emit(self, event: str, context: Dict[str, Any] = None) -> None:
        """Fire un événement hermes interne."""
        handlers = self._hooks.get(event, [])
        for handler in handlers:
            try:
                handler(event, context or {})
            except Exception as e:
                logger.debug(f"Hook handler error [{event}]: {e}")

    def on(self, event: str, handler) -> None:
        """Enregistre un handler pour un événement hermes."""
        self._hooks.setdefault(event, []).append(handler)

    # ── LLM via OpenRouter ─────────────────────────────────────────────────────

    async def narrate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        max_tokens: int = 150,
    ) -> Optional[str]:
        """
        Narration simple via OpenRouter (1 modèle).
        Retourne None si OpenRouter non disponible.
        """
        client = _get_openrouter_client()
        if client is None:
            return None

        target_model = model or REFERENCE_MODELS[0]
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        self._emit("agent:start", {"model": target_model, "prompt": prompt[:80]})
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=max_tokens,
                ),
                timeout=12.0,
            )
            content = resp.choices[0].message.content
            result = content.strip() if content else None
            self._emit("agent:end", {"result": (result or "")[:80]})
            return result
        except Exception as e:
            logger.debug(f"HermesClient.narrate failed: {e}")
            self._emit("agent:end", {"error": str(e)})
            return None

    async def moa_decide(
        self,
        prompt: str,
        context: Dict[str, Any] = None,
        system_prompt: str = "",
    ) -> Optional[str]:
        """
        Décision enrichie via Mixture-of-Agents.
        Utilisé par Parliament.deliberate() pour les décisions complexes.
        Retourne None si OpenRouter non disponible.
        """
        full_prompt = prompt
        if context:
            ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_prompt = f"{prompt}\n\nContexte: {ctx_str}"

        self._emit("agent:step", {"type": "moa", "prompt": prompt[:80]})
        return await mixture_of_agents(full_prompt, system_prompt=system_prompt)

    def is_available(self) -> bool:
        """Vérifie si OpenRouter est configuré."""
        return _get_openrouter_client() is not None
