"""
Rate Limiter — Protection contre le dépassement des limites API.

Limites par défaut :
  Binance REST  : 1200 req/min (poids), 10 ordres/sec, 100k ordres/jour
  Binance WS    : 5 messages/sec
  Telegram Bot  : 30 msg/sec (global), 1 msg/sec/chat (standard)

Implémentation : Token Bucket + Sliding Window combinés.
Thread-safe via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration pour un endpoint."""
    name:             str
    max_requests:     int          # requêtes max dans la fenêtre
    window_seconds:   float        # durée de la fenêtre glissante
    burst_limit:      int   = 0    # max instantané (0 = pas de burst limit)
    burst_window_sec: float = 1.0  # fenêtre du burst


class RateLimiter:
    """
    Rate limiter par clé (endpoint/service) avec fenêtre glissante.

    Usage:
        limiter = RateLimiter()
        limiter.add("binance_rest", max_requests=1100, window_seconds=60)
        limiter.add("telegram", max_requests=25, window_seconds=1)

        await limiter.acquire("binance_rest")  # attend si nécessaire
        # ... faire la requête ...
    """

    def __init__(self):
        self._configs:    dict[str, RateLimitConfig] = {}
        self._timestamps: dict[str, deque[float]]    = {}
        self._locks:      dict[str, asyncio.Lock]    = {}
        self._total_waits: dict[str, int]            = {}
        self._total_calls: dict[str, int]            = {}

    def add(
        self,
        name: str,
        max_requests: int,
        window_seconds: float,
        burst_limit: int = 0,
        burst_window_sec: float = 1.0,
    ) -> None:
        """Enregistre un endpoint avec ses limites."""
        self._configs[name] = RateLimitConfig(
            name=name,
            max_requests=max_requests,
            window_seconds=window_seconds,
            burst_limit=burst_limit,
            burst_window_sec=burst_window_sec,
        )
        # maxlen = 2x max_requests pour safety margin while keeping memory bounded
        self._timestamps[name] = deque(maxlen=max_requests * 2)
        self._locks[name]      = asyncio.Lock()
        self._total_waits[name] = 0
        self._total_calls[name] = 0

    async def acquire(self, name: str, weight: int = 1) -> float:
        """
        Acquiert le droit de faire `weight` requêtes.
        Bloque si la limite est atteinte.

        Returns:
            Temps d'attente en secondes (0.0 si pas d'attente).
        """
        if name not in self._configs:
            return 0.0

        config = self._configs[name]
        lock   = self._locks[name]
        waited = 0.0

        async with lock:
            while True:
                now = time.monotonic()
                ts  = self._timestamps[name]

                # Purger les timestamps hors fenêtre
                cutoff = now - config.window_seconds
                while ts and ts[0] < cutoff:
                    ts.popleft()

                # Vérifier la limite de fenêtre
                if len(ts) + weight > config.max_requests:
                    # Calculer le temps d'attente
                    wait_until = ts[0] + config.window_seconds
                    sleep_time = max(wait_until - now, 0.05)
                    logger.debug(
                        "[RateLimiter] %s : limite atteinte (%d/%d) — attente %.2fs",
                        name, len(ts), config.max_requests, sleep_time,
                    )
                    self._total_waits[name] += 1
                    waited += sleep_time
                    await asyncio.sleep(sleep_time)
                    continue

                # Vérifier le burst limit
                if config.burst_limit > 0:
                    burst_cutoff = now - config.burst_window_sec
                    burst_count = sum(1 for t in ts if t >= burst_cutoff)
                    if burst_count + weight > config.burst_limit:
                        sleep_time = config.burst_window_sec
                        logger.debug(
                            "[RateLimiter] %s : burst limit (%d/%d) — attente %.2fs",
                            name, burst_count, config.burst_limit, sleep_time,
                        )
                        self._total_waits[name] += 1
                        waited += sleep_time
                        await asyncio.sleep(sleep_time)
                        continue

                # OK — enregistrer les timestamps
                for _ in range(weight):
                    ts.append(now)
                self._total_calls[name] += weight
                break

        if waited > 0.5:
            logger.info(
                "[RateLimiter] %s : attendu %.2fs (throttled)",
                name, waited,
            )
        return waited

    def usage(self, name: str) -> dict:
        """Retourne l'utilisation courante d'un endpoint."""
        if name not in self._configs:
            return {}
        config = self._configs[name]
        ts     = self._timestamps[name]
        now    = time.monotonic()

        # Compter les requêtes dans la fenêtre active
        cutoff = now - config.window_seconds
        active = sum(1 for t in ts if t >= cutoff)

        return {
            "name":           name,
            "active":         active,
            "limit":          config.max_requests,
            "window_sec":     config.window_seconds,
            "usage_pct":      round(active / max(config.max_requests, 1) * 100, 1),
            "total_calls":    self._total_calls.get(name, 0),
            "total_throttles": self._total_waits.get(name, 0),
        }

    def snapshot(self) -> dict:
        """État complet de tous les rate limiters."""
        return {name: self.usage(name) for name in self._configs}


# ── Instance globale pré-configurée pour le bot ─────────────────────────────

def create_default_limiter() -> RateLimiter:
    """
    Crée un rate limiter avec les limites Binance + Telegram pré-configurées.
    """
    rl = RateLimiter()

    # Binance REST API — 1200 weight/min, on garde 10% de marge
    rl.add("binance_rest",
           max_requests=1080,
           window_seconds=60,
           burst_limit=10,
           burst_window_sec=1.0)

    # Binance Orders — 10 ordres/sec, 100k/jour
    rl.add("binance_orders",
           max_requests=8,
           window_seconds=1.0)

    # Binance WebSocket — 5 msg/sec
    rl.add("binance_ws",
           max_requests=4,
           window_seconds=1.0)

    # Telegram Bot API — 30 msg/sec global, mais 1 msg/sec/chat recommandé
    rl.add("telegram",
           max_requests=25,
           window_seconds=1.0,
           burst_limit=3,
           burst_window_sec=1.0)

    # Telegram per-chat — 1 msg/sec max
    rl.add("telegram_chat",
           max_requests=1,
           window_seconds=1.0)

    # MarketData (Binance REST fallback) — Requests for candles
    rl.add("market_data",
           max_requests=50,
           window_seconds=60)

    logger.info(
        "[RateLimiter] Configuré : %s",
        ", ".join(f"{k}({v.max_requests}/{v.window_seconds}s)"
                  for k, v in rl._configs.items()),
    )
    return rl
