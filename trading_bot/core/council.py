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


@dataclass
class CouncilVerdict:
    verdict:          str
    confidence_adj:   int
    reasoning:        str
    bull_view:        str
    bear_view:        str
    devil_view:       str
    final_confidence: int


class Council:
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

        bull_resp, bear_resp, devil_resp = await asyncio.gather(
            self._llm.complete("gpt-4o", _BULL.format(**ctx),  max_tokens=200, timeout=15.0),
            self._llm.complete("gpt-4o", _BEAR.format(**ctx),  max_tokens=200, timeout=15.0),
            self._llm.complete("gpt-4o", _DEVIL.format(**ctx), max_tokens=200, timeout=15.0),
        )

        bull_text  = bull_resp.text  if bull_resp  else "Analyst indisponible."
        bear_text  = bear_resp.text  if bear_resp  else "Analyst indisponible."
        devil_text = devil_resp.text if devil_resp else "Analyst indisponible."

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
        try:
            return json.loads(text.strip())
        except Exception:
            pass
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
