"""
Working Memory — Filtre le bruit du 5min.
Consensus requis sur N bougies consécutives avant de valider un signal.
"""
from collections import deque
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class MemoryState:
    signal: str          # "LONG", "SHORT", "NEUTRAL"
    confidence: float    # 0.0 - 1.0
    timestamp: float
    strate_source: str


class WorkingMemory:
    def __init__(self, window: int = 3, required_consensus: int = 2, ttl: float = 300.0):
        self.window = window
        self.required_consensus = required_consensus
        self.ttl = ttl          # secondes — signaux plus anciens ignorés
        self.buffer: deque[MemoryState] = deque(maxlen=window)
        self.last_consensus: Optional[str] = None

    def push(self, signal: str, confidence: float, source: str) -> None:
        self.buffer.append(MemoryState(
            signal=signal,
            confidence=confidence,
            timestamp=time.time(),
            strate_source=source
        ))

    def get_consensus(self) -> Optional[tuple[str, float]]:
        """
        Retourne (signal, confidence_moyenne) si consensus atteint.
        Retourne None si pas assez de données valides (TTL) ou pas de consensus.
        """
        now = time.time()
        valid = [s for s in self.buffer if now - s.timestamp <= self.ttl]

        if len(valid) < self.required_consensus:
            return None

        signals = [s.signal for s in valid]
        confidences = [s.confidence for s in valid]

        for direction in ["LONG", "SHORT"]:
            count = signals.count(direction)
            if count >= self.required_consensus:
                avg_conf = sum(
                    c for s, c in zip(signals, confidences)
                    if s == direction
                ) / count
                return (direction, avg_conf)
        return None

    def clear(self) -> None:
        self.buffer.clear()
