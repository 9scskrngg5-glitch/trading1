"""
MirofishClient — Simulation probabiliste multi-agents.

Mirofish analyse des milliers d'agents virtuels sur une même information de marché
et retourne une distribution comportementale probabiliste.

Rôle dans l'écosystème :
  - SOURCE SECONDAIRE — confirme ou infirme l'analyse primaire, ne la remplace jamais
  - Priorité 4 sur 4 dans la hiérarchie des sources
  - Utilisé par SynthesisAgent comme couche de confirmation comportementale

Ce que Mirofish apporte :
  - Consensus de la foule (% LONG / SHORT / HOLD)
  - Probabilités de scénario (bull / bear / sideways)
  - Signal contrarian quand la foule est unanime (>75% → piège potentiel)
  - Divergence entre comportement de foule et analyse technique
  - Score de risque de manipulation comportementale

Architecture de la simulation :
  1. Agents Trend-Followers (35%) — suivent l'EMA et le MACD
  2. Agents Mean-Reversion (25%) — contrarians RSI/BB
  3. Agents Breakout (20%) — cassures de structure
  4. Agents News-Driven (15%) — sentiment dominant
  5. Agents Noise (5%) — aléatoire, simule les retail non-informés
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Nombre d'agents simulés par run
N_AGENTS = 2000

# Seuil de consensus extrême → signal contrarian
CONTRARIAN_THRESHOLD = 0.75


@dataclass
class MirofishResult:
    """Résultat d'une simulation Mirofish."""
    asset:             str
    timestamp:         str
    agents_simulated:  int

    # Consensus
    long_pct:          float   # % d'agents qui votent LONG
    short_pct:         float   # % d'agents qui votent SHORT
    hold_pct:          float   # % d'agents qui votent HOLD
    direction:         str     # "bullish" | "bearish" | "neutral"
    crowd_extremity:   float   # 0=parfait split, 1=consensus total (0-1)

    # Probabilités de scénario
    bull_probability:  float
    bear_probability:  float
    sideways_probability: float

    # Signaux dérivés
    contrarian_signal: bool    # True si foule > 75% d'un côté
    divergence_score:  int     # + si aligned avec tech, - si divergent (-50 à +50)
    manipulation_risk: float   # 0-1, risque de piège de foule

    # Texte explicatif
    behavioral_note:   str
    source_label:      str = "🎯 Mirofish (simulation probabiliste)"

    def to_dict(self) -> dict:
        return {
            "asset":              self.asset,
            "timestamp":          self.timestamp,
            "agents_simulated":   self.agents_simulated,
            "long_pct":           round(self.long_pct, 3),
            "short_pct":          round(self.short_pct, 3),
            "hold_pct":           round(self.hold_pct, 3),
            "direction":          self.direction,
            "crowd_extremity":    round(self.crowd_extremity, 3),
            "bull_probability":   round(self.bull_probability, 3),
            "bear_probability":   round(self.bear_probability, 3),
            "sideways_probability": round(self.sideways_probability, 3),
            "contrarian_signal":  self.contrarian_signal,
            "divergence_score":   self.divergence_score,
            "manipulation_risk":  round(self.manipulation_risk, 3),
            "behavioral_note":    self.behavioral_note,
            "source_label":       self.source_label,
        }


class MirofishClient:
    """
    Client de simulation comportementale multi-agents.

    Simule N agents avec différentes stratégies sur les mêmes données.
    Retourne une distribution probabiliste exploitable comme signal secondaire.

    Usage :
        mf = MirofishClient()
        result = await mf.simulate(asset, price, rsi, macd_hist, bb_pos,
                                   vol_ratio, sentiment_score, regime, structure)
    """

    def __init__(self, n_agents: int = N_AGENTS, simulate: bool = True):
        self.n_agents = n_agents
        self.simulate = simulate   # Toujours True (pas d'API externe réelle)
        self._cache: dict[str, MirofishResult] = {}
        self._cache_ttl = 120   # secondes avant d'invalider le cache

    async def simulate_market(
        self,
        asset:           str,
        price:           float,
        rsi:             Optional[float] = 50.0,
        macd_hist:       Optional[float] = 0.0,
        bb_position:     Optional[float] = 0.5,
        vol_ratio:       Optional[float] = 1.0,
        sentiment_score: Optional[float] = 0.0,
        regime_dir:      str = "neutral",
        structure_pattern: str = "unclear",
        ob_imbalance:    Optional[float] = 0.0,
    ) -> MirofishResult:
        """
        Simule le comportement de N agents avec stratégies différentes.

        Inputs normalisés en [-1, +1] avant simulation :
        - rsi_signal    : rsi > 60 → +1 (bull), rsi < 40 → -1 (bear)
        - macd_signal   : direction de l'histogramme
        - bb_signal     : bb_pos < 0.2 → +1 (rebond), > 0.8 → -1 (résistance)
        - volume_signal : vol_ratio > 1.5 → amplifie la direction courante
        - sentiment     : score / 100
        - regime        : +1 bullish, -1 bearish, 0 neutral
        - ob_imbalance  : déjà en [-1, +1]
        """
        # Normaliser les inputs
        rsi_n   = self._normalize_rsi(rsi or 50)
        macd_n  = math.copysign(min(abs(macd_hist or 0) * 10, 1.0), macd_hist or 0)
        bb_n    = (0.5 - (bb_position or 0.5)) * 2   # 0.2 → +0.6, 0.8 → -0.6
        vol_n   = min(max((vol_ratio or 1.0) - 1.0, -0.5), 0.5) * 2  # -1 à +1
        sent_n  = (sentiment_score or 0) / 100
        reg_n   = 1.0 if regime_dir == "bullish" else (-1.0 if regime_dir == "bearish" else 0.0)
        struct_n = 1.0 if structure_pattern == "HH_HL" else (-1.0 if structure_pattern == "LH_LL" else 0.0)
        ob_n    = float(ob_imbalance or 0)

        # ── Simulation des 5 types d'agents ──────────────────────────────────
        rng = np.random.default_rng(seed=int(abs(hash(f"{asset}{price:.2f}")) % 2**32))

        votes_long  = 0
        votes_short = 0
        votes_hold  = 0

        # 1. Trend-Followers (35%) — MACD + Regime + Structure
        trend_n   = int(self.n_agents * 0.35)
        trend_sig = 0.6 * reg_n + 0.25 * macd_n + 0.15 * struct_n
        trend_votes = self._vote_batch(rng, trend_n, trend_sig, noise=0.20)
        votes_long  += trend_votes[0]
        votes_short += trend_votes[1]
        votes_hold  += trend_votes[2]

        # 2. Mean-Reversion (25%) — RSI + BB (contrarians)
        mrv_n   = int(self.n_agents * 0.25)
        mrv_sig = 0.5 * rsi_n + 0.5 * bb_n   # RSI > 60 ou BB haut → SHORT pour eux
        mrv_votes = self._vote_batch(rng, mrv_n, -mrv_sig, noise=0.25)  # inverse
        votes_long  += mrv_votes[0]
        votes_short += mrv_votes[1]
        votes_hold  += mrv_votes[2]

        # 3. Breakout Traders (20%) — Structure + Volume + OB
        bko_n   = int(self.n_agents * 0.20)
        bko_sig = 0.4 * struct_n + 0.35 * vol_n + 0.25 * ob_n
        bko_votes = self._vote_batch(rng, bko_n, bko_sig, noise=0.22)
        votes_long  += bko_votes[0]
        votes_short += bko_votes[1]
        votes_hold  += bko_votes[2]

        # 4. News-Driven (15%) — Sentiment dominant
        nws_n   = int(self.n_agents * 0.15)
        nws_sig = sent_n
        nws_votes = self._vote_batch(rng, nws_n, nws_sig, noise=0.30)
        votes_long  += nws_votes[0]
        votes_short += nws_votes[1]
        votes_hold  += nws_votes[2]

        # 5. Noise Traders (5%) — aléatoire (retail non-informés)
        noise_n = self.n_agents - trend_n - mrv_n - bko_n - nws_n
        noise_votes = self._vote_batch(rng, noise_n, 0.0, noise=0.50)
        votes_long  += noise_votes[0]
        votes_short += noise_votes[1]
        votes_hold  += noise_votes[2]

        # ── Calcul des résultats ──────────────────────────────────────────────
        total      = votes_long + votes_short + votes_hold
        long_pct   = votes_long  / total
        short_pct  = votes_short / total
        hold_pct   = votes_hold  / total

        # Direction
        if long_pct >= 0.45:
            direction = "bullish"
        elif short_pct >= 0.45:
            direction = "bearish"
        else:
            direction = "neutral"

        # Extrémité du consensus : 0 = split parfait 50/50, 1 = unanime
        dominant   = max(long_pct, short_pct)
        extremity  = (dominant - 0.5) * 2

        # ── Probabilités de scénario ──────────────────────────────────────────
        # Combine les votes avec un modèle probabiliste simple
        base_bull = 0.5 + 0.4 * (long_pct - short_pct)
        noise_adj = rng.normal(0, 0.02)
        bull_p    = float(np.clip(base_bull + noise_adj, 0.05, 0.90))
        bear_p    = float(np.clip(1 - bull_p - hold_pct * 0.5, 0.05, 0.90))
        side_p    = max(0.0, 1.0 - bull_p - bear_p)

        # ── Signaux dérivés ───────────────────────────────────────────────────
        contrarian = dominant >= CONTRARIAN_THRESHOLD
        manip_risk = float(np.clip(extremity * 0.5 + abs(ob_n) * 0.3 + (0.2 if contrarian else 0), 0, 1))

        # Divergence avec signal technique (-50 à +50)
        tech_dir  = 1 if regime_dir == "bullish" else (-1 if regime_dir == "bearish" else 0)
        crowd_dir = 1 if direction == "bullish" else (-1 if direction == "bearish" else 0)
        divergence = int((crowd_dir - tech_dir) * 25)   # +25 aligned, -25 opposed

        # ── Note comportementale ──────────────────────────────────────────────
        note = self._build_behavioral_note(
            asset, direction, long_pct, short_pct, contrarian,
            divergence, manip_risk, extremity,
        )

        result = MirofishResult(
            asset              = asset,
            timestamp          = datetime.now(timezone.utc).isoformat(),
            agents_simulated   = self.n_agents,
            long_pct           = long_pct,
            short_pct          = short_pct,
            hold_pct           = hold_pct,
            direction          = direction,
            crowd_extremity    = float(extremity),
            bull_probability   = bull_p,
            bear_probability   = bear_p,
            sideways_probability = side_p,
            contrarian_signal  = contrarian,
            divergence_score   = divergence,
            manipulation_risk  = manip_risk,
            behavioral_note    = note,
        )

        self._cache[asset] = result
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_rsi(rsi: float) -> float:
        """RSI → signal [-1, +1]. >60 = positif, <40 = négatif."""
        if rsi > 60:
            return min((rsi - 60) / 40, 1.0)
        elif rsi < 40:
            return -min((40 - rsi) / 40, 1.0)
        return 0.0

    @staticmethod
    def _vote_batch(
        rng: np.random.Generator, n: int, signal: float, noise: float
    ) -> tuple[int, int, int]:
        """
        Fait voter N agents selon un signal biaisé + bruit gaussien.
        signal ∈ [-1, +1] : probabilité de voter LONG
        """
        # Probabilités de base avec distribution triangulaire autour du signal
        p_long  = max(0.0, min(1.0, 0.35 + signal * 0.30 + rng.normal(0, noise * 0.5)))
        p_short = max(0.0, min(1.0, 0.35 - signal * 0.30 + rng.normal(0, noise * 0.5)))
        p_sum   = p_long + p_short
        if p_sum > 1.0:
            p_long  /= p_sum
            p_short /= p_sum
        p_hold  = max(0.0, 1.0 - p_long - p_short)

        votes = rng.multinomial(n, [p_long, p_short, p_hold])
        return int(votes[0]), int(votes[1]), int(votes[2])

    @staticmethod
    def _build_behavioral_note(
        asset: str, direction: str,
        long_pct: float, short_pct: float,
        contrarian: bool, divergence: int,
        manip_risk: float, extremity: float,
    ) -> str:
        """Génère la note comportementale interprétable."""
        consensus_str = f"{max(long_pct, short_pct):.0%} {'LONG' if long_pct > short_pct else 'SHORT'}"

        if contrarian:
            return (
                f"⚠️  Consensus extrême ({consensus_str}) — "
                f"risque de piège de liquidité élevé. "
                f"Quand >75% des agents sont alignés, les institutionnels chassent ces stops. "
                f"Signal contrarian à surveiller."
            )
        elif divergence < -15:
            return (
                f"🔀 Divergence comportementale — foule {direction} mais technique opposé. "
                f"Crowd est contre-tendance ({long_pct:.0%}/{short_pct:.0%}). "
                f"Prudence : la foule a souvent tort contre la structure."
            )
        elif divergence > 15:
            return (
                f"✅ Alignement foule-technique — {consensus_str} avec support structurel. "
                f"Consensus comportemental renforce l'analyse primaire."
            )
        elif manip_risk > 0.5:
            return (
                f"⚡ Risque de manipulation modéré ({manip_risk:.0%}). "
                f"Order book + comportement de foule suggèrent une activité institutionnelle inhabituelle."
            )
        else:
            return (
                f"📊 Distribution équilibrée ({long_pct:.0%}L / {short_pct:.0%}S / {1-long_pct-short_pct:.0%}H). "
                f"Pas de consensus clair — marché indécis selon le crowd."
            )
