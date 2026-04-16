"""
ORACLE v2 — NarratorLLM.

Module extrait de narrator.py (546L → 3 modules).
Gère les backends LLM du Narrator : Free-GPT4 local, OpenRouter/Hermes, Claude Haiku.

Ordre de priorité :
  1. FREE_GPT4    — serveur local localhost:5500 (gratuit, sans clé)
  2. OPENROUTER   — hermes-agent (OPENROUTER_API_KEY, modèles gratuits)
  3. ANTHROPIC    — Claude Haiku (ANTHROPIC_API_KEY)
  4. ""           — vide (le caller utilisera un template)

Utilisé par OracleNarrator via composition.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("ORACLE.Narrator.LLM")

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    from integrations.hermes_client import HermesClient
    _HAS_HERMES = True
except ImportError:
    try:
        from oracle_v2.integrations.hermes_client import HermesClient
        _HAS_HERMES = True
    except ImportError:
        _HAS_HERMES = False


class NarratorLLM:
    """
    Backend LLM du Narrator.

    Responsabilités :
      - Encapsuler les appels réseau aux LLMs
      - Gérer la cascade Free-GPT4 → OpenRouter → Haiku → ""
      - Mettre en cache l'état de disponibilité de Free-GPT4 (évite les timeouts répétés)
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        api_key: str = "",
        use_llm: bool = True,
        free_gpt4_url: str = "",
    ):
        self.use_llm = use_llm
        self.free_gpt4_url = free_gpt4_url
        self._free_gpt4_available: Optional[bool] = None   # None = pas encore testé

        # Claude client
        self._llm_client = None
        if use_llm and api_key and _HAS_ANTHROPIC:
            try:
                self._llm_client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                logger.warning(f"Anthropic init failed: {e}")

        # Hermes (OpenRouter)
        self._hermes = None
        if _HAS_HERMES:
            try:
                self._hermes = HermesClient()
            except Exception as e:
                logger.debug(f"Hermes init failed: {e}")

    def is_available(self) -> bool:
        """True si au moins un backend LLM est actif."""
        return bool(
            (self.free_gpt4_url and self._free_gpt4_available is not False)
            or (self._hermes and self._hermes.is_available())
            or (self._llm_client is not None)
        )

    async def speak(
        self,
        prompt: str,
        system_prompt: str,
        context: str = "",
        max_tokens: int = 150,
    ) -> str:
        """
        Génère une narration LLM. Retourne "" si tous les backends échouent.
        Le caller utilisera alors son template de fallback.
        """
        full_prompt = f"{context}\n\nSituation: {prompt}" if context else prompt

        # 1. Free-GPT4 local
        text = await self._free_gpt4(f"{system_prompt}\n\n{full_prompt}")
        if text:
            return text

        # 2. OpenRouter via hermes-agent
        if self._hermes and self._hermes.is_available():
            try:
                text = await self._hermes.narrate(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
                if text:
                    return text
            except Exception as e:
                logger.debug(f"Hermes narration failed: {e}")

        # 3. Claude Haiku
        if self.use_llm and self._llm_client:
            try:
                msg = await asyncio.to_thread(
                    lambda: self._llm_client.messages.create(
                        model=self.DEFAULT_MODEL,
                        max_tokens=max_tokens,
                        system=[{
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }],
                        messages=[{"role": "user", "content": full_prompt}],
                    )
                )
                return msg.content[0].text.strip()
            except Exception as e:
                logger.debug(f"Claude Haiku narration failed: {e}")

        return ""

    async def _free_gpt4(self, full_prompt: str) -> str:
        """Appelle Free-GPT4-WEB-API local. Timeout 8s."""
        if not self.free_gpt4_url or not _HAS_HTTPX:
            return ""
        if self._free_gpt4_available is False:
            return ""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{self.free_gpt4_url}/",
                    params={"text": full_prompt[:1500]},
                )
                if resp.status_code == 200 and resp.text.strip():
                    self._free_gpt4_available = True
                    return resp.text.strip()
        except Exception as e:
            if self._free_gpt4_available is None:
                logger.debug(f"Free-GPT4 indisponible: {e}")
            self._free_gpt4_available = False
        return ""
