"""
ORACLE v2 — NarratorMemory.

Module extrait de narrator.py (546L → 3 modules).
Gère la mémoire de travail du Narrator : historique des Thoughts,
contexte pour le LLM, affichage rich.

Utilisé par OracleNarrator via composition.
"""
from __future__ import annotations

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("ORACLE.Narrator.Memory")

TAHITI_TZ = timezone(timedelta(hours=-10))

try:
    from rich.console import Console
    _HAS_RICH = True
    _console = Console()
except ImportError:
    _HAS_RICH = False
    _console = None


@dataclass
class Thought:
    ts: float
    event: str          # OBSERVE / DELIBERATE / SIGNAL / ARB / BLOCK / REFLECT / TRADE / START
    symbol: str
    content: str        # texte lisible
    data: dict = field(default_factory=dict)


class NarratorMemory:
    """
    Mémoire de travail du Narrator.

    Responsabilités :
      - Stocker les Thoughts (fenêtre glissante configurable)
      - Construire le contexte LLM (historique résumé)
      - Afficher les événements en console (rich si disponible)
      - Résumer la mémoire pour le mode chat
    """

    COLOR_MAP = {
        "OBSERVE":    "cyan",
        "DELIBERATE": "yellow",
        "SIGNAL":     "green",
        "ARB":        "magenta",
        "BLOCK":      "red",
        "REFLECT":    "blue",
        "TRADE":      "bright_green",
        "START":      "bright_cyan",
        "INFO":       "white",
    }

    def __init__(self, max_thoughts: int = 50):
        self.memory: deque[Thought] = deque(maxlen=max_thoughts)

    def push(self, event: str, symbol: str, content: str, data: dict = None) -> None:
        """Ajoute un Thought à la mémoire."""
        self.memory.append(Thought(
            ts=time.time(),
            event=event,
            symbol=symbol,
            content=content,
            data=data or {},
        ))

    def display(self, text: str, event: str = "INFO", symbol: str = "") -> None:
        """Affiche un événement en console avec rich si disponible."""
        color = self.COLOR_MAP.get(event, "white")
        ts = self._ts()
        if _HAS_RICH and _console:
            sym_part = f" [dim]{symbol}[/dim]" if symbol else ""
            _console.print(
                f"[dim]{ts}[/dim] [bold {color}]ORACLE {event}[/bold {color}]{sym_part}  {text}"
            )
        else:
            print(f"[{ts}] ORACLE {event}: {text}")

    def build_context(self, extra: dict = None, n_recent: int = 8) -> str:
        """Construit le contexte texte pour le LLM depuis la mémoire récente."""
        recent = list(self.memory)[-n_recent:]
        history = "\n".join(
            f"- [{t.event}] {t.symbol}: {t.content[:80]}"
            for t in recent
        )
        parts = [f"Historique récent:\n{history}"]
        for k, v in (extra or {}).items():
            parts.append(f"{k}: {v}")
        return "\n".join(parts)

    def get_summary(self, n: int = 10) -> str:
        """Résumé lisible de la mémoire récente (pour le mode chat)."""
        recent = list(self.memory)[-n:]
        if not recent:
            return "Mémoire vide."
        lines = [
            f"[{t.event:10}] "
            f"{datetime.fromtimestamp(t.ts, TAHITI_TZ).strftime('%H:%M')} "
            f"{t.symbol}: {t.content[:70]}"
            for t in recent
        ]
        return "\n".join(lines)

    @staticmethod
    def _ts() -> str:
        return datetime.now(TAHITI_TZ).strftime("%H:%M:%S")
