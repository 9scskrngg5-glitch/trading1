"""
Client Swarmode — Swarm Intelligence financière
https://www.swarmode.ai

Swarmode développe des algorithmes propriétaires de prédiction de séries
temporelles financières utilisés par des hedge funds.

En l'absence de clé API : génère des signaux simulés réalistes.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SWARMODE_BASE = "https://api.swarmode.ai/v1"   # URL hypothétique — à confirmer


class SwarmodeClient:
    """
    Interface vers l'API Swarmode.
    Retourne des signaux quantitatifs (directionnels + confiance) par asset.

    Sans clé API → mode simulation avec données financières réalistes.
    """

    def __init__(self, api_key: str = "", simulate: bool = True):
        self.api_key  = api_key
        self.simulate = simulate or not api_key
        self._http: Optional[httpx.AsyncClient] = None
        self._cache: dict[str, dict] = {}   # cache 5 min par asset

    async def connect(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=15,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        mode = "simulation" if self.simulate else "production"
        logger.info("[Swarmode] Client prêt ��� mode %s", mode)

    async def disconnect(self) -> None:
        """Ferme le client HTTP proprement."""
        if self._http:
            await self._http.aclose()
            self._http = None

    async def get_signal(self, asset: str) -> dict:
        """
        Retourne le signal Swarmode pour un asset.

        Structure retournée :
        {
          "asset":       "BTC/USDT",
          "direction":   "bullish" | "bearish" | "neutral",
          "confidence":  0–100,
          "score":       -100 à +100,
          "forecast_1h": float,   # variation % prédite sur 1h
          "forecast_24h":float,   # variation % prédite sur 24h
          "regime":      "trending" | "mean_reverting" | "volatile",
          "source":      "swarmode",
        }
        """
        if self.simulate:
            logger.warning("[Swarmode] ⚠️  Mode SIMULÉ pour %s — données fondamentales INVENTÉES", asset)
            return self._simulate_signal(asset)

        try:
            r = await self._http.get(
                f"{SWARMODE_BASE}/signals",
                params={"symbol": asset.replace("/", ""), "interval": "1h"},
            )
            r.raise_for_status()
            data = r.json()
            return self._parse_response(asset, data)
        except Exception as exc:
            logger.warning("[Swarmode] API error (%s) — fallback simulation", exc)
            return self._simulate_signal(asset)

    # ── Simulation réaliste ───────────────────────────────────────────────────

    @staticmethod
    def _simulate_signal(asset: str) -> dict:
        """
        Génère un signal simulé cohérent avec des données financières réelles.
        Les paramètres sont calibrés selon la volatilité historique des assets.
        """
        VOLATILITY = {
            "BTC/USDT": 0.8, "ETH/USDT": 1.0, "SOL/USDT": 1.4,
            "EUR/USD":  0.2, "GBP/USD":  0.3,
        }
        TREND_BIAS = {
            "BTC/USDT": 0.5, "ETH/USDT": 0.4, "SOL/USDT": 0.3,
            "EUR/USD": -0.2, "GBP/USD": -0.15,
        }

        vol  = VOLATILITY.get(asset, 0.6)
        bias = TREND_BIAS.get(asset, 0.0)

        # Score du swarm — seed aligné sur fenêtre 5 min (même que ScanAgent)
        # → garantit cohérence directionnelle entre signals technique et fondamental
        import numpy as np
        seed = (hash(asset) + int(datetime.now().timestamp()) // 300) % 2**31
        rng   = np.random.default_rng(seed=seed)
        # Tirage de direction identique à ScanAgent._sim_ohlcv
        direction_sign = rng.choice([-1, 1])
        drift_magnitude = rng.uniform(0.4, 0.8)  # 40-80% du max
        base_score = direction_sign * drift_magnitude * 100
        # Ajout du biais fondamental de l'asset (BTC légèrement bullish historiquement)
        score = float(np.clip(base_score + bias * 40 + rng.normal(0, 8), -100, 100))

        # Prévisions
        f1h  = score / 100 * vol * 0.5 + rng.normal(0, vol * 0.1)
        f24h = score / 100 * vol * 2.0 + rng.normal(0, vol * 0.5)

        # Régime de marché
        abs_score = abs(score)
        if abs_score > 60:
            regime = "trending"
        elif vol > 0.8 and abs_score < 30:
            regime = "volatile"
        else:
            regime = "mean_reverting"

        direction = (
            "bullish" if score > 15 else
            "bearish" if score < -15 else
            "neutral"
        )

        return {
            "asset":        asset,
            "direction":    direction,
            "confidence":   int(min(abs_score, 100)),
            "score":        round(score, 1),
            "forecast_1h":  round(f1h, 3),
            "forecast_24h": round(f24h, 3),
            "regime":       regime,
            "source":       "swarmode_sim",
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _parse_response(asset: str, data: dict) -> dict:
        """Parse la réponse réelle de l'API Swarmode (adapter selon leur doc)."""
        score = data.get("swarm_score", 0)
        return {
            "asset":        asset,
            "direction":    data.get("direction", "neutral"),
            "confidence":   data.get("confidence", int(abs(score))),
            "score":        score,
            "forecast_1h":  data.get("forecast_1h", 0.0),
            "forecast_24h": data.get("forecast_24h", 0.0),
            "regime":       data.get("market_regime", "sideways"),
            "source":       "swarmode",
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }
