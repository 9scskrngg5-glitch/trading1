"""
Base Strate — Classe abstraite pour toutes les strates ORACLE v2.
Interface uniforme : analyze() → StrateResult.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging


@dataclass
class StrateResult:
    strate_name: str
    direction: str        # "LONG", "SHORT", "NEUTRAL"
    confidence: float     # 0.0 - 1.0
    reasoning: str
    signal_strength: float
    metadata: Optional[dict] = None


class BaseStrate(ABC):
    """Interface commune pour toutes les strates ORACLE v2."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"ORACLE.{name}")
        self._last_result: Optional[StrateResult] = None

    @abstractmethod
    def analyze(self, data: dict) -> StrateResult:
        """
        Analyse les données et retourne un StrateResult.
        Ne doit JAMAIS lever d'exception — fail-safe obligatoire.
        """
        ...

    def safe_analyze(self, data: dict) -> StrateResult:
        """Wrapper fail-safe autour de analyze()."""
        try:
            result = self.analyze(data)
            self._last_result = result
            return result
        except Exception as e:
            self.logger.error(f"[{self.name}] Erreur analyze(): {e}")
            return StrateResult(
                strate_name=self.name,
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"Erreur interne: {e}",
                signal_strength=0.0
            )

    @property
    def last_result(self) -> Optional[StrateResult]:
        return self._last_result
