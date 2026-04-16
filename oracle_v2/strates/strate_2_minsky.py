"""
Strate 2 — Minsky Cycle Detector
"La stabilité est déstabilisante." — Hyman Minsky

Théorie : Minsky (1986) + Kindleberger (1978) — les longues périodes de calme
poussent les acteurs à prendre des risques croissants, construisant la prochaine crise.
Le modèle à 5 phases de Kindleberger décompose ce cycle.

Les 5 phases Minsky :
  1. DISPLACEMENT  — nouveau paradigme, adopteurs précoces, optimisme rationnel
  2. BOOM          — expansion du crédit, momentum, FOMO qui commence
  3. EUPHORIA      — tout le monde est un génie, levier maximal, irrationnel
  4. DISTRESS      — premières fissures, smart money sort discrètement
  5. REVULSION     — panique, capitulation, pessimisme maximal

Multiplicateurs de sizing par phase (CLAUDE.md) :
  Phase 1-2 : 1.0x (normal)
  Phase 3   : 0.4x (réduction, hedges activés)
  Phase 4   : 0.6x (contrarian activé, biais short)
  Phase 5   : 0.8x (accumulation agressive, contrarian max)

Sources d'indicateurs :
  MacroSnapshot (Strate 1) → VIX, funding_rates, dominance, yield_curve, real_rate, ISM
  Données optionnelles     → OI trend, L/S ratio, liquidation volume, put/call ratio

Stockage : SQLite → vault/world_model/minsky_history.db
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Énumérations ──────────────────────────────────────────────────────────────

class MinskyPhase(int, Enum):
    DISPLACEMENT = 1
    BOOM         = 2
    EUPHORIA     = 3
    DISTRESS     = 4
    REVULSION    = 5

    @property
    def label(self) -> str:
        return {
            1: "Displacement",
            2: "Boom",
            3: "Euphoria",
            4: "Distress",
            5: "Revulsion",
        }[self.value]

    @property
    def emoji(self) -> str:
        return {1: "🌱", 2: "📈", 3: "🚀", 4: "⚠️", 5: "💥"}[self.value]


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class CryptoLiveData:
    """
    Données live optionnelles (Binance / CryptoQuant / Glassnode).
    Si absentes, le détecteur fonctionne en mode dégradé avec les données MacroSnapshot.
    """
    open_interest_btc:    float = 0.0    # Open Interest BTC en USD (milliards)
    oi_change_24h_pct:    float = 0.0    # Variation OI 24h en %
    long_short_ratio:     float = 1.0    # Ratio longs/shorts (> 1 = majorité longs)
    liquidations_24h_usd: float = 0.0   # Volume liquidations 24h en millions USD
    put_call_ratio:       float = 1.0    # Put/call options (> 1 = bear)
    btc_price_change_30d: float = 0.0   # Variation prix BTC sur 30 jours (%)
    funding_rate_trend:   str   = "flat" # "rising" / "falling" / "flat"


@dataclass
class PhaseScore:
    """Score brut de chaque phase avant normalisation."""
    phase:    MinskyPhase
    score:    float        # [0, ∞) — plus élevé = plus probable
    signals:  list[str]    # Signaux ayant contribué


@dataclass
class MinskyResult:
    """Résultat complet de la détection de phase Minsky."""
    phase:              MinskyPhase
    confidence:         float        # 0.0 → 1.0
    sizing_multiplier:  float        # Multiplicateur de taille de position
    positioning_bias:   str          # "long" / "short" / "neutral"
    phase_scores:       dict         # {phase_value: score} pour traçabilité
    signals:            list[str]    # Signaux ayant déterminé la phase
    transition_alert:   bool = False # True si changement de phase détecté
    previous_phase:     Optional[int] = None
    timestamp:          str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "phase":             self.phase.value,
            "phase_label":       self.phase.label,
            "confidence":        round(self.confidence, 3),
            "sizing_multiplier": round(self.sizing_multiplier, 2),
            "positioning_bias":  self.positioning_bias,
            "phase_scores":      {str(k): round(v, 3) for k, v in self.phase_scores.items()},
            "signals":           self.signals,
            "transition_alert":  self.transition_alert,
            "previous_phase":    self.previous_phase,
            "timestamp":         self.timestamp,
        }

    def summary(self) -> str:
        alert = " ⚠️ TRANSITION DÉTECTÉE" if self.transition_alert else ""
        return (
            f"{self.phase.emoji} Phase {self.phase.value} — {self.phase.label}{alert}\n"
            f"  Confiance : {self.confidence:.0%} | Sizing : {self.sizing_multiplier}x "
            f"| Bias : {self.positioning_bias}\n"
            f"  Signaux : {' | '.join(self.signals[:3])}"
        )


# ── Détecteur principal ───────────────────────────────────────────────────────

class MinskyDetector:
    """
    Détecte la phase du cycle de Minsky à partir de signaux macro et crypto.

    Algorithme de scoring :
      Chaque indicateur vote pour une ou plusieurs phases avec un poids donné.
      Le score de chaque phase est la somme des poids de ses votes.
      La phase dominante = score le plus élevé.
      La confiance = écart entre 1er et 2e, normalisé.

    Indicateurs utilisés (par ordre de priorité) :
      1. Funding rate BTC/ETH   → levier directionnel dominant
      2. VIX + VIX trend         → stress systémique
      3. OI trend                → bâtissement ou liquidation des positions
      4. L/S ratio               → sentiment directionnel
      5. BTC dominance           → appétit pour le risque crypto
      6. Yield curve + real_rate → conditions macro de fond
      7. ISM PMI                 → cycle économique réel
      8. Liquidations 24h        → violence des exits
    """

    # ── Tables de scoring par indicateur ─────────────────────────────────────
    # Format : {condition → {MinskyPhase: weight}}

    _SIZING: dict[MinskyPhase, float] = {
        MinskyPhase.DISPLACEMENT: 1.0,
        MinskyPhase.BOOM:         1.0,
        MinskyPhase.EUPHORIA:     0.4,
        MinskyPhase.DISTRESS:     0.6,
        MinskyPhase.REVULSION:    0.8,
    }

    _BIAS: dict[MinskyPhase, str] = {
        MinskyPhase.DISPLACEMENT: "long",
        MinskyPhase.BOOM:         "long",
        MinskyPhase.EUPHORIA:     "neutral",
        MinskyPhase.DISTRESS:     "short",
        MinskyPhase.REVULSION:    "long",
    }

    def __init__(self, vault_path: Optional[Path] = None):
        self._vault_path   = vault_path
        self._db_path      = (vault_path / "world_model" / "minsky_history.db") if vault_path else None
        self._last_result: Optional[MinskyResult] = None

        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    # ── Interface publique ────────────────────────────────────────────────────

    def detect_phase(
        self,
        snapshot:    "MacroSnapshot",         # type: ignore[name-defined]
        crypto_data: Optional[CryptoLiveData] = None,
    ) -> MinskyResult:
        """
        Détecte la phase Minsky courante.

        Args:
            snapshot:    MacroSnapshot de Strate 1 (obligatoire).
            crypto_data: Données live optionnelles (OI, L/S, liquidations…).
                         Si absent, le détecteur fonctionne en mode dégradé.

        Returns:
            MinskyResult avec phase, confiance, sizing, bias et signaux.
        """
        scores: dict[MinskyPhase, PhaseScore] = {
            p: PhaseScore(phase=p, score=0.0, signals=[]) for p in MinskyPhase
        }

        # ── 1. Funding Rate BTC (indicateur le plus direct du levier) ────────
        self._score_funding_rate(snapshot.btc_funding_rate, scores)

        # ── 2. VIX (stress systémique) ────────────────────────────────────────
        self._score_vix(snapshot.vix, scores)

        # ── 3. Yield Curve (macro backdrop) ──────────────────────────────────
        self._score_yield_curve(snapshot.yield_curve, scores)

        # ── 4. Taux réels (conditions de liquidité) ───────────────────────────
        self._score_real_rate(snapshot.real_rate, scores)

        # ── 5. ISM PMI (cycle économique) ─────────────────────────────────────
        self._score_ism(snapshot.ism_pmi, scores)

        # ── 6. BTC Dominance (appétit risque crypto) ──────────────────────────
        self._score_btc_dominance(snapshot.btc_dominance, scores)

        # ── 7. Total Market Cap trend (momentum macro crypto) ─────────────────
        self._score_market_cap(snapshot.total_market_cap_b, scores)

        # ── 8. Données live optionnelles ──────────────────────────────────────
        if crypto_data:
            self._score_open_interest(crypto_data, scores)
            self._score_long_short_ratio(crypto_data.long_short_ratio, scores)
            self._score_liquidations(crypto_data.liquidations_24h_usd, scores)
            self._score_btc_price_trend(crypto_data.btc_price_change_30d, scores)
            self._score_funding_trend(crypto_data.funding_rate_trend, scores)
            if crypto_data.put_call_ratio != 1.0:
                self._score_put_call(crypto_data.put_call_ratio, scores)

        # ── Sélection de la phase dominante ───────────────────────────────────
        phase_totals = {p: s.score for p, s in scores.items()}
        sorted_phases = sorted(phase_totals.items(), key=lambda x: x[1], reverse=True)
        top_phase, top_score = sorted_phases[0]
        sec_score = sorted_phases[1][1] if len(sorted_phases) > 1 else 0.0

        total = sum(phase_totals.values())
        confidence = float(np.clip(
            (top_score - sec_score) / max(total, 1e-6), 0.0, 1.0
        ))

        # Rassemble tous les signaux de la phase gagnante + 2e phase
        signals = scores[top_phase].signals.copy()
        if sorted_phases[1][1] > 0:
            signals += [f"[2e: {sorted_phases[1][0].label}]" + s
                        for s in scores[sorted_phases[1][0]].signals[:1]]

        # ── Détection de transition ────────────────────────────────────────────
        prev_phase = self._last_result.phase.value if self._last_result else None
        transition = (prev_phase is not None and prev_phase != top_phase.value)

        result = MinskyResult(
            phase             = top_phase,
            confidence        = confidence,
            sizing_multiplier = self.get_sizing_multiplier(top_phase),
            positioning_bias  = self.get_positioning_bias(top_phase),
            phase_scores      = {p.value: s.score for p, s in scores.items()},
            signals           = signals[:6],
            transition_alert  = transition,
            previous_phase    = prev_phase,
        )

        if transition:
            prev_label = MinskyPhase(prev_phase).label if prev_phase else "?"
            logger.warning(
                "[Strate2] ⚠️ TRANSITION MINSKY : %s → %s (confiance=%.0f%%)",
                prev_label, top_phase.label, confidence * 100,
            )
        else:
            logger.info(
                "[Strate2] %s Phase %d — %s | sizing=%.1fx bias=%s conf=%.0f%%",
                top_phase.emoji, top_phase.value, top_phase.label,
                result.sizing_multiplier, result.positioning_bias, confidence * 100,
            )

        self._last_result = result
        self._save_to_db(result)
        return result

    def get_sizing_multiplier(self, phase: MinskyPhase) -> float:
        """
        Retourne le multiplicateur de taille de position pour la phase donnée.

        Phase 1-2 : 1.0x (risque normal)
        Phase 3   : 0.4x (euphorie → réduire drastiquement)
        Phase 4   : 0.6x (distress → positions contrariantes modérées)
        Phase 5   : 0.8x (revulsion → accumulation agressive mais pas maximale)
        """
        return self._SIZING[phase]

    def get_positioning_bias(self, phase: MinskyPhase) -> str:
        """
        Retourne le biais de positionnement pour la phase donnée.

        "long"    → Phase 1, 2, 5 (momentum ou contrarian bull)
        "neutral" → Phase 3 (euphorie → ne pas surenchérir)
        "short"   → Phase 4 (distress → biais vendeur)
        """
        return self._BIAS[phase]

    @property
    def last_result(self) -> Optional[MinskyResult]:
        return self._last_result

    def get_history(self, limit: int = 100) -> list[dict]:
        """Récupère les N dernières détections depuis SQLite."""
        if not self._db_path or not self._db_path.exists():
            return []
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM minsky_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            cols = ["id", "timestamp", "phase", "phase_label", "confidence",
                    "sizing_multiplier", "positioning_bias", "transition_alert",
                    "previous_phase", "signals_json"]
            return [dict(zip(cols, row)) for row in rows]
        except Exception as exc:
            logger.debug("[Strate2] get_history error: %s", exc)
            return []

    # ── Méthodes de scoring ───────────────────────────────────────────────────

    @staticmethod
    def _score_funding_rate(fr: float, scores: dict) -> None:
        """
        Funding rate BTC — indicateur le plus direct du levier en cours.

        > 0.10% / 8h  → Euphorie (levier long maximal)
        0.03-0.10%    → Boom (levier long croissant)
        0-0.03%       → Displacement (prudent, haussier modéré)
        -0.01-0%      → Distress (retournement, premiers shorts)
        < -0.05%      → Revulsion (panic, shorts dominants)
        """
        if fr > 0.10:
            scores[MinskyPhase.EUPHORIA].score   += 4.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"Funding très élevé ({fr:.3f}%) → levier max")
        elif fr > 0.03:
            scores[MinskyPhase.BOOM].score       += 3.0
            scores[MinskyPhase.BOOM].signals.append(f"Funding positif ({fr:.3f}%) → levier croissant")
        elif fr >= 0:
            scores[MinskyPhase.DISPLACEMENT].score += 2.0
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"Funding neutre ({fr:.3f}%) → prudent")
        elif fr > -0.05:
            scores[MinskyPhase.DISTRESS].score   += 3.0
            scores[MinskyPhase.DISTRESS].signals.append(f"Funding négatif ({fr:.3f}%) → pression short")
        else:
            scores[MinskyPhase.REVULSION].score  += 4.0
            scores[MinskyPhase.REVULSION].signals.append(f"Funding très négatif ({fr:.3f}%) → capitulation")

    @staticmethod
    def _score_vix(vix: float, scores: dict) -> None:
        """
        VIX — stress systémique du marché.

        < 15          → Euphorie (complacency dangereuse)
        15-20         → Boom (optimisme, faible volatilité)
        20-25         → Displacement (normalisation)
        25-35         → Distress (stress croissant)
        > 35          → Revulsion (panique)
        """
        if vix < 15:
            scores[MinskyPhase.EUPHORIA].score   += 3.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"VIX extrêmement bas ({vix:.1f}) → complaisance dangereuse")
        elif vix < 20:
            scores[MinskyPhase.BOOM].score       += 2.5
            scores[MinskyPhase.BOOM].signals.append(f"VIX bas ({vix:.1f}) → optimisme dominant")
        elif vix < 25:
            scores[MinskyPhase.DISPLACEMENT].score += 2.0
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"VIX modéré ({vix:.1f}) → phase d'installation")
        elif vix < 35:
            scores[MinskyPhase.DISTRESS].score   += 3.0
            scores[MinskyPhase.DISTRESS].signals.append(f"VIX élevé ({vix:.1f}) → stress de marché")
        else:
            scores[MinskyPhase.REVULSION].score  += 4.0
            scores[MinskyPhase.REVULSION].signals.append(f"VIX extrême ({vix:.1f}) → panique")

    @staticmethod
    def _score_yield_curve(yc: float, scores: dict) -> None:
        """
        Yield curve (10Y-2Y spread).

        > 1.5%   → Displacement (conditions favorables, cycle haussier)
        0.5-1.5% → Boom (expansion saine)
        0-0.5%   → Euphorie / fin de cycle (flat = late cycle)
        < 0%     → Distress (inversion = signal récession)
        < -0.5%  → Revulsion si combiné avec autres signaux
        """
        if yc > 1.5:
            scores[MinskyPhase.DISPLACEMENT].score += 2.5
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"Courbe pentue ({yc:.2f}%) → début de cycle")
        elif yc > 0.5:
            scores[MinskyPhase.BOOM].score         += 2.0
            scores[MinskyPhase.BOOM].signals.append(f"Courbe normale ({yc:.2f}%) → expansion")
        elif yc >= 0:
            scores[MinskyPhase.EUPHORIA].score     += 1.5
            scores[MinskyPhase.EUPHORIA].signals.append(f"Courbe plate ({yc:.2f}%) → fin de cycle")
        elif yc > -0.5:
            scores[MinskyPhase.DISTRESS].score     += 2.5
            scores[MinskyPhase.DISTRESS].signals.append(f"Courbe inversée ({yc:.2f}%) → récession proche")
        else:
            scores[MinskyPhase.DISTRESS].score     += 2.0
            scores[MinskyPhase.REVULSION].score    += 1.5
            scores[MinskyPhase.REVULSION].signals.append(f"Courbe très inversée ({yc:.2f}%) → récession")

    @staticmethod
    def _score_real_rate(real_rate: float, scores: dict) -> None:
        """
        Taux d'intérêt réels (Fed Funds − CPI).

        < -2%  → Boom/Euphorie (liquidité abondante, bulle facilitée)
        -2%-0% → Displacement/Boom (conditions accommodantes)
        0%-2%  → Neutre
        > 2%   → Distress (conditions restrictives)
        > 4%   → Revulsion (conditions très restrictives = crash trigger)
        """
        if real_rate < -2.0:
            scores[MinskyPhase.EUPHORIA].score += 2.0
            scores[MinskyPhase.BOOM].score     += 1.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"Taux réels très négatifs ({real_rate:.1f}%) → bulle facilitée")
        elif real_rate < 0:
            scores[MinskyPhase.BOOM].score         += 1.5
            scores[MinskyPhase.DISPLACEMENT].score += 1.0
            scores[MinskyPhase.BOOM].signals.append(f"Taux réels négatifs ({real_rate:.1f}%) → liquidité")
        elif real_rate < 2.0:
            pass  # neutre — pas de score
        elif real_rate < 4.0:
            scores[MinskyPhase.DISTRESS].score += 2.0
            scores[MinskyPhase.DISTRESS].signals.append(f"Taux réels élevés ({real_rate:.1f}%) → conditions restrictives")
        else:
            scores[MinskyPhase.DISTRESS].score  += 1.5
            scores[MinskyPhase.REVULSION].score += 2.5
            scores[MinskyPhase.REVULSION].signals.append(f"Taux réels très élevés ({real_rate:.1f}%) → trigger crash")

    @staticmethod
    def _score_ism(ism: float, scores: dict) -> None:
        """
        ISM Manufacturing PMI — cycle économique réel.

        > 60  → Euphorie (surchauffe économique)
        55-60 → Boom (expansion forte)
        50-55 → Displacement (expansion modérée)
        45-50 → Distress (contraction légère)
        < 45  → Revulsion (contraction forte)
        """
        if ism > 60:
            scores[MinskyPhase.EUPHORIA].score += 2.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"ISM surchauffe ({ism:.1f}) → expansion extrême")
        elif ism > 55:
            scores[MinskyPhase.BOOM].score     += 2.0
            scores[MinskyPhase.BOOM].signals.append(f"ISM expansion forte ({ism:.1f})")
        elif ism > 50:
            scores[MinskyPhase.DISPLACEMENT].score += 1.5
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"ISM expansion modérée ({ism:.1f})")
        elif ism > 45:
            scores[MinskyPhase.DISTRESS].score += 1.5
            scores[MinskyPhase.DISTRESS].signals.append(f"ISM contraction légère ({ism:.1f})")
        else:
            scores[MinskyPhase.REVULSION].score += 2.0
            scores[MinskyPhase.DISTRESS].score  += 1.0
            scores[MinskyPhase.REVULSION].signals.append(f"ISM contraction forte ({ism:.1f})")

    @staticmethod
    def _score_btc_dominance(dom: float, scores: dict) -> None:
        """
        BTC Dominance — appétit pour le risque dans le marché crypto.

        < 40% → Euphorie (alt season = pic de cycle)
        40-50% → Boom (bull market, argent dans les alts)
        50-60% → Displacement (BTC leading, prudence)
        > 60%  → Distress/Revulsion (fuite vers la qualité)
        """
        if dom < 40:
            scores[MinskyPhase.EUPHORIA].score += 2.5
            scores[MinskyPhase.EUPHORIA].signals.append(f"BTC dom très basse ({dom:.1f}%) → pic alt-season")
        elif dom < 50:
            scores[MinskyPhase.BOOM].score     += 2.0
            scores[MinskyPhase.BOOM].signals.append(f"BTC dom basse ({dom:.1f}%) → appétit risque alt")
        elif dom < 60:
            scores[MinskyPhase.DISPLACEMENT].score += 1.5
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"BTC dom normale ({dom:.1f}%) → BTC leading")
        else:
            scores[MinskyPhase.DISTRESS].score  += 1.5
            scores[MinskyPhase.REVULSION].score += 1.0
            scores[MinskyPhase.DISTRESS].signals.append(f"BTC dom élevée ({dom:.1f}%) → fuite qualité")

    @staticmethod
    def _score_market_cap(mcap_b: float, scores: dict) -> None:
        """
        Market cap totale crypto (milliards USD) — taille de la bulle potentielle.

        Indicateur relatif : grandes valeurs → euphorie plus probable.
        Utilise des niveaux historiques approximatifs.
        """
        if mcap_b > 3000:
            scores[MinskyPhase.EUPHORIA].score += 2.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"Market cap crypto énorme ({mcap_b:.0f}B) → cycle avancé")
        elif mcap_b > 2000:
            scores[MinskyPhase.BOOM].score     += 1.5
            scores[MinskyPhase.BOOM].signals.append(f"Market cap crypto élevée ({mcap_b:.0f}B) → expansion")
        elif mcap_b > 1000:
            scores[MinskyPhase.DISPLACEMENT].score += 1.0
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"Market cap crypto modérée ({mcap_b:.0f}B)")
        else:
            scores[MinskyPhase.REVULSION].score += 1.5
            scores[MinskyPhase.DISTRESS].score  += 0.5
            scores[MinskyPhase.REVULSION].signals.append(f"Market cap crypto basse ({mcap_b:.0f}B) → après crash")

    @staticmethod
    def _score_open_interest(cd: CryptoLiveData, scores: dict) -> None:
        """OI trend — accumulation (boom) vs liquidation (distress/revulsion)."""
        oi_chg = cd.oi_change_24h_pct
        if oi_chg > 10:
            scores[MinskyPhase.EUPHORIA].score += 2.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"OI +{oi_chg:.1f}% 24h → levier explosif")
        elif oi_chg > 3:
            scores[MinskyPhase.BOOM].score     += 1.5
            scores[MinskyPhase.BOOM].signals.append(f"OI +{oi_chg:.1f}% 24h → positions croissantes")
        elif oi_chg < -10:
            scores[MinskyPhase.REVULSION].score += 2.5
            scores[MinskyPhase.REVULSION].signals.append(f"OI {oi_chg:.1f}% 24h → liquidation massive")
        elif oi_chg < -3:
            scores[MinskyPhase.DISTRESS].score += 2.0
            scores[MinskyPhase.DISTRESS].signals.append(f"OI {oi_chg:.1f}% 24h → désendettement")

    @staticmethod
    def _score_long_short_ratio(ls: float, scores: dict) -> None:
        """
        Long/Short Ratio — sentiment directionnel levé.

        > 2.0  → Euphorie (majorité écrasante de longs → contrarian bear)
        1.5-2.0 → Boom (optimisme dominant)
        0.8-1.5 → Neutre
        0.5-0.8 → Distress (shorts majoritaires)
        < 0.5  → Revulsion (short squeeze zone)
        """
        if ls > 2.0:
            scores[MinskyPhase.EUPHORIA].score += 2.5
            scores[MinskyPhase.EUPHORIA].signals.append(f"L/S ratio {ls:.2f} → majorité longs (contrarian bear)")
        elif ls > 1.5:
            scores[MinskyPhase.BOOM].score     += 1.5
            scores[MinskyPhase.BOOM].signals.append(f"L/S ratio {ls:.2f} → optimisme levé")
        elif ls < 0.5:
            scores[MinskyPhase.REVULSION].score += 2.5
            scores[MinskyPhase.REVULSION].signals.append(f"L/S ratio {ls:.2f} → shorts extrêmes")
        elif ls < 0.8:
            scores[MinskyPhase.DISTRESS].score += 1.5
            scores[MinskyPhase.DISTRESS].signals.append(f"L/S ratio {ls:.2f} → shorts dominants")

    @staticmethod
    def _score_liquidations(liq_musd: float, scores: dict) -> None:
        """Volume de liquidations 24h (millions USD)."""
        if liq_musd > 500:
            scores[MinskyPhase.REVULSION].score += 3.0
            scores[MinskyPhase.REVULSION].signals.append(f"Liquidations massives (${liq_musd:.0f}M) → capitulation")
        elif liq_musd > 100:
            scores[MinskyPhase.DISTRESS].score  += 2.0
            scores[MinskyPhase.DISTRESS].signals.append(f"Liquidations élevées (${liq_musd:.0f}M) → stress")
        elif liq_musd < 20 and liq_musd > 0:
            scores[MinskyPhase.EUPHORIA].score  += 1.0
            scores[MinskyPhase.EUPHORIA].signals.append(f"Liquidations quasi-nulles (${liq_musd:.0f}M) → complaisance")

    @staticmethod
    def _score_btc_price_trend(chg_30d: float, scores: dict) -> None:
        """Variation BTC sur 30 jours."""
        if chg_30d > 50:
            scores[MinskyPhase.EUPHORIA].score += 2.5
            scores[MinskyPhase.EUPHORIA].signals.append(f"BTC +{chg_30d:.0f}% en 30j → accélération parabolique")
        elif chg_30d > 20:
            scores[MinskyPhase.BOOM].score     += 2.0
            scores[MinskyPhase.BOOM].signals.append(f"BTC +{chg_30d:.0f}% en 30j → momentum fort")
        elif chg_30d > 5:
            scores[MinskyPhase.DISPLACEMENT].score += 1.5
            scores[MinskyPhase.DISPLACEMENT].signals.append(f"BTC +{chg_30d:.0f}% en 30j → tendance haussière")
        elif chg_30d < -30:
            scores[MinskyPhase.REVULSION].score += 2.5
            scores[MinskyPhase.REVULSION].signals.append(f"BTC {chg_30d:.0f}% en 30j → crash")
        elif chg_30d < -10:
            scores[MinskyPhase.DISTRESS].score += 2.0
            scores[MinskyPhase.DISTRESS].signals.append(f"BTC {chg_30d:.0f}% en 30j → correction sévère")

    @staticmethod
    def _score_funding_trend(trend: str, scores: dict) -> None:
        """Tendance des funding rates (rising/falling/flat)."""
        if trend == "rising":
            scores[MinskyPhase.BOOM].score     += 1.0
            scores[MinskyPhase.EUPHORIA].score += 0.5
            scores[MinskyPhase.BOOM].signals.append("Funding en hausse → levier s'accumule")
        elif trend == "falling":
            scores[MinskyPhase.DISTRESS].score += 1.0
            scores[MinskyPhase.DISTRESS].signals.append("Funding en baisse → dés-endettement")

    @staticmethod
    def _score_put_call(pc: float, scores: dict) -> None:
        """Put/Call ratio — sentiment options."""
        if pc > 1.5:
            scores[MinskyPhase.REVULSION].score += 1.5
            scores[MinskyPhase.REVULSION].signals.append(f"Put/Call {pc:.2f} → peur options extrême")
        elif pc > 1.0:
            scores[MinskyPhase.DISTRESS].score  += 1.0
            scores[MinskyPhase.DISTRESS].signals.append(f"Put/Call {pc:.2f} → protection croissante")
        elif pc < 0.5:
            scores[MinskyPhase.EUPHORIA].score  += 1.5
            scores[MinskyPhase.EUPHORIA].signals.append(f"Put/Call {pc:.2f} → complacency options")

    # ── SQLite ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS minsky_history (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp         TEXT NOT NULL,
                        phase             INTEGER NOT NULL,
                        phase_label       TEXT NOT NULL,
                        confidence        REAL NOT NULL,
                        sizing_multiplier REAL NOT NULL,
                        positioning_bias  TEXT NOT NULL,
                        transition_alert  INTEGER NOT NULL,
                        previous_phase    INTEGER,
                        signals_json      TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_minsky_ts
                    ON minsky_history (timestamp DESC)
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("[Strate2] DB init error: %s", exc)

    def _save_to_db(self, result: MinskyResult) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO minsky_history
                    (timestamp, phase, phase_label, confidence, sizing_multiplier,
                     positioning_bias, transition_alert, previous_phase, signals_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.timestamp,
                    result.phase.value,
                    result.phase.label,
                    result.confidence,
                    result.sizing_multiplier,
                    result.positioning_bias,
                    int(result.transition_alert),
                    result.previous_phase,
                    json.dumps(result.signals),
                ))
                conn.commit()
        except Exception as exc:
            logger.debug("[Strate2] DB save error: %s", exc)
