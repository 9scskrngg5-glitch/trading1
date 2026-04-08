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
    ts: str
    asset: str
    regime: str
    setup: str
    outcome: str
    pattern: str
    confirmed_count: int = 1


class NarrativeMemory:
    def __init__(self, vault_path: Path):
        self._path = vault_path / "memory" / "narrative_patterns.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._patterns: list[NarrativePattern] = []
        self._load()

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
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(p)) + "\n")

    def _save_all(self) -> None:
        self._path.write_text(
            "\n".join(json.dumps(asdict(p)) for p in self._patterns) + "\n",
            encoding="utf-8",
        )

    def add_pattern(
        self,
        asset: str,
        regime: str,
        setup: str,
        outcome: str,
        pattern_text: str,
    ) -> None:
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
        if not patterns:
            return "Aucun pattern similaire trouvé dans la mémoire."
        lines = []
        for p in patterns:
            lines.append(
                f"- [{p.outcome.upper()} ×{p.confirmed_count}] {p.pattern}"
            )
        return "\n".join(lines)
