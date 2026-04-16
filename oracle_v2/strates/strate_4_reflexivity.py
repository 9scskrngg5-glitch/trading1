"""
Strate 4 — Reflexivity Engine
"Les marchés financiers ne reflètent pas la réalité — ils la créent." — George Soros

Théorie : Soros (The Alchemy of Finance, 1987) — la réflexivité est une boucle
de rétroaction bidirectionnelle entre les anticipations des acteurs et la réalité :

  Fonction cognitive    : les prix affectent les perceptions
  Fonction participative: les perceptions affectent les prix

  Boucle positive : prix hausse → consensus haussier → achats → prix hausse (auto-renforcement)
  Inflexion       : prix continue mais le sentiment stagne ou diverge → retournement proche
  Boucle négative : prix baisse → panique → ventes → prix baisse (capitulation accélérée)

Métriques calculées :
  1. Exposant de Hurst H (analyse R/S de Mandelbrot)
       H > 0.6  → processus persistant = boucle réflexive active
       H ≈ 0.5  → marche aléatoire = efficience (pas de boucle)
       H < 0.4  → processus anti-persistant = mean-reversion

  2. Cross-corrélation prix → sentiment (lags 1..MAX_LAG)
       xcorr_ps > 0  → le prix d'hier crée le sentiment d'aujourd'hui
  3. Cross-corrélation sentiment → prix (lags 1..MAX_LAG)
       xcorr_sp > 0  → le sentiment d'hier anticipe le prix d'aujourd'hui
  4. Reflexivity Index = xcorr_ps × xcorr_sp
       RI > 0     → boucle fermée (les deux directions actives)
       RI ≈ 0     → boucle ouverte ou absence de sentiment

  5. Inflexion : boucle positive (H > H_LOOP, RI > RI_THRESHOLD)
                 + momentum corrélation décroissant → signal de retournement

Sizing modifiers :
  POSITIVE_LOOP (H élevé, RI élevé)    : 1.10x — rider la vague réflexive
  INFLECTION_DETECTED                   : 0.65x — danger, réduire rapidement
  NEGATIVE_LOOP                         : 0.80x — short/neutre
  MEAN_REVERTING (H < 0.45)            : 1.00x — normal, pas de biais réflexif

Sentiment proxy utilisé (si disponible) :
  - Funding rate BTC (MacroSnapshot.btc_funding_rate) — le meilleur proxy crypto
  - Strate 3 ecosystem_heat — sentiment narratif
  - Si aucun : Hurst seul + autocorrélation proxy

Stockage : vault/world_model/reflexivity_history.db
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
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constantes Hurst ──────────────────────────────────────────────────────────

HURST_WINDOW_MIN:  int   = 20    # minimum de points pour estimer H de façon fiable
HURST_WINDOW_DEF:  int   = 60    # fenêtre par défaut (candles 1h → 2.5 jours)
HURST_LOOP:        float = 0.60  # H > 0.60 → boucle réflexive
HURST_MEAN_REV:    float = 0.45  # H < 0.45 → mean-reversion franche

# ── Constantes cross-corrélation ──────────────────────────────────────────────

XCORR_MAX_LAG:      int   = 7     # lags max pour la corrélation croisée
XCORR_MIN_POINTS:   int   = 15    # minimum de points communs pour xcorr valide
RI_THRESHOLD:       float = 0.08  # Reflexivity Index minimum pour déclarer boucle active

# ── Détection d'inflexion ─────────────────────────────────────────────────────

INFLECTION_CORR_DECAY: float = 0.15  # baisse du RI sur la dernière moitié de fenêtre

# ── Sizing par boucle ─────────────────────────────────────────────────────────

SIZING_POSITIVE_LOOP:    float = 1.10
SIZING_INFLECTION:       float = 0.65
SIZING_NEGATIVE_LOOP:    float = 0.80
SIZING_MEAN_REVERTING:   float = 1.00
SIZING_NEUTRAL:          float = 1.00


# ── Énumérations ──────────────────────────────────────────────────────────────

class ReflexivityLoop(str, Enum):
    POSITIVE_LOOP      = "positive_loop"   # boucle haussière active
    NEGATIVE_LOOP      = "negative_loop"   # boucle baissière active
    INFLECTION         = "inflection"      # boucle qui se brise → danger
    MEAN_REVERTING     = "mean_reverting"  # H < HURST_MEAN_REV
    NEUTRAL            = "neutral"         # H ≈ 0.5, pas de signal fort

    @property
    def emoji(self) -> str:
        return {
            "positive_loop": "🔄", "negative_loop": "🌀",
            "inflection": "⚡", "mean_reverting": "↔", "neutral": "→"
        }[self.value]


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class HurstEstimate:
    """Résultat de l'analyse R/S."""
    h:           float   # exposant de Hurst ∈ [0, 1]
    n_points:    int     # nombre de points utilisés
    reliable:    bool    # True si n_points >= HURST_WINDOW_MIN
    log_rs_slope: float  # pente brute de la régression log-log


@dataclass
class CrossCorrResult:
    """Résultat des corrélations croisées entre prix et sentiment."""
    xcorr_ps:      float         # prix → sentiment (max sur lags 1..MAX_LAG)
    xcorr_sp:      float         # sentiment → prix (max sur lags 1..MAX_LAG)
    ri:            float         # Reflexivity Index = xcorr_ps × xcorr_sp
    best_lag_ps:   int           # lag optimal pour prix → sentiment
    best_lag_sp:   int           # lag optimal pour sentiment → prix
    available:     bool = True   # False si pas de données de sentiment


@dataclass
class ReflexivityResult:
    """Résultat complet de l'analyse de réflexivité."""
    loop:              ReflexivityLoop
    hurst:             float   # exposant de Hurst
    reflexivity_index: float   # RI = xcorr_ps × xcorr_sp ∈ [0, 1]
    xcorr_ps:          float   # corrélation prix → sentiment
    xcorr_sp:          float   # corrélation sentiment → prix
    hurst_reliable:    bool    # True si estimation fiable (≥ HURST_WINDOW_MIN pts)
    sizing_modifier:   float   # multiplicateur de taille de position
    positioning_bias:  str     # "long" / "short" / "neutral" / "reduce"
    signals:           list[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Sérialise pour transmission au PredictAgent ou au log."""
        return {
            "loop":              self.loop.value,
            "hurst":             round(self.hurst, 4),
            "reflexivity_index": round(self.reflexivity_index, 4),
            "xcorr_ps":          round(self.xcorr_ps, 4),
            "xcorr_sp":          round(self.xcorr_sp, 4),
            "hurst_reliable":    self.hurst_reliable,
            "sizing_modifier":   round(self.sizing_modifier, 2),
            "positioning_bias":  self.positioning_bias,
            "signals":           self.signals,
            "timestamp":         self.timestamp,
        }

    def summary(self) -> str:
        icon = self.loop.emoji
        rel  = "" if self.hurst_reliable else " (H non fiable — peu de données)"
        return (
            f"{icon} Réflexivité : {self.loop.value} | H={self.hurst:.3f}{rel}\n"
            f"  RI={self.reflexivity_index:.3f} (PS={self.xcorr_ps:.3f} SP={self.xcorr_sp:.3f})"
            f" | sizing ×{self.sizing_modifier:.2f} | bias={self.positioning_bias}\n"
            f"  {' | '.join(self.signals[:3])}"
        )


class BacktestResult:
    """Résultats du backtest de la strate réflexivité sur données historiques."""

    def __init__(self, results: list[dict]):
        self.results = results

    def summary(self) -> str:
        if not self.results:
            return "Aucun résultat de backtest."

        n = len(self.results)
        by_loop = {}
        for r in self.results:
            lp = r.get("loop", "neutral")
            by_loop.setdefault(lp, []).append(r)

        lines = [
            f"\n{'═' * 57}",
            f"  BACKTEST STRATE 4 — Réflexivité Soros",
            f"{'═' * 57}",
            f"  Observations : {n}",
        ]
        for lp, rows in sorted(by_loop.items()):
            lines.append(f"  {lp.upper():<22}: {len(rows):>4} ({len(rows)/n:.1%})")

        if self.results and "pnl_pct" in self.results[0]:
            for lp in ["positive_loop", "inflection", "negative_loop", "mean_reverting"]:
                pnl = [r["pnl_pct"] for r in by_loop.get(lp, []) if "pnl_pct" in r]
                if pnl:
                    lines.append(
                        f"  P&L {lp.upper():<18}: {np.mean(pnl):+.3f}%  "
                        f"WR={sum(1 for x in pnl if x > 0) / len(pnl):.1%}"
                    )

        lines.append(f"{'═' * 57}\n")
        return "\n".join(lines)


# ── Moteur principal ──────────────────────────────────────────────────────────

class ReflexivityEngine:
    """
    Strate 4 — Réflexivité de Soros.

    Détecte et mesure les boucles de rétroaction prix/sentiment qui caractérisent
    les marchés en mode réflexif. Quantifie l'intensité de la boucle via l'exposant
    de Hurst (R/S analysis) et les corrélations croisées prix ↔ sentiment.

    Usage :
        engine = ReflexivityEngine(vault_path=Path("vault"))

        # Avec sentiment (funding rate ou ecosystem_heat de Strate 3)
        result = engine.analyze(prices=btc_prices, sentiment_proxy=funding_rates)

        # Sans sentiment (Hurst seul)
        result = engine.analyze(prices=btc_prices)

        bt = engine.backtest(df)   # df avec 'close' et optionnel 'sentiment_proxy'
        print(bt.summary())

    Fail-safe : si les séries sont trop courtes, retourne un état NEUTRAL
    sans perturber le pipeline.
    """

    def __init__(
        self,
        vault_path:     Optional[Path] = None,
        hurst_window:   int            = HURST_WINDOW_DEF,
        xcorr_max_lag:  int            = XCORR_MAX_LAG,
    ):
        self._vault_path    = vault_path
        self._hurst_window  = hurst_window
        self._xcorr_max_lag = xcorr_max_lag

        self._db_path: Optional[Path] = None
        if vault_path:
            db_dir = vault_path / "world_model"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = db_dir / "reflexivity_history.db"
            self._init_db()

        self._last_result: Optional[ReflexivityResult] = None

    # ── Interface publique ────────────────────────────────────────────────────

    def analyze(
        self,
        prices:          pd.Series,
        sentiment_proxy: Optional[pd.Series] = None,
        asset:           str                 = "BTC",
    ) -> dict:
        """
        Analyse la réflexivité sur une série de prix et (optionnel) un proxy de sentiment.

        Args:
            prices:          Series de prix de clôture (ordre chronologique).
                             Minimum HURST_WINDOW_MIN points pour une estimation fiable.
            sentiment_proxy: Series de même longueur représentant le sentiment
                             (ex: funding rate BTC, ecosystem_heat Strate 3).
                             Si None, seul le Hurst est calculé.
            asset:           Identifiant de l'actif pour le log.

        Returns:
            dict sérialisable avec : loop, hurst, reflexivity_index, xcorr_ps,
            xcorr_sp, sizing_modifier, positioning_bias, signals, timestamp.
        """
        prices_arr = np.array(prices.dropna(), dtype=float)

        if len(prices_arr) < 4:
            logger.warning("[Strate4] Série trop courte (%d pts) — état NEUTRAL", len(prices_arr))
            return self._neutral_result(reason="Données insuffisantes").to_dict()

        # 1. Exposant de Hurst
        hurst_est = self._estimate_hurst(prices_arr[-self._hurst_window:])

        # 2. Cross-corrélations
        xcorr_res = self._compute_xcorr(prices_arr, sentiment_proxy)

        # 3. Détection d'inflexion (boucle qui se brise)
        inflection = self._detect_inflection(prices_arr, sentiment_proxy)

        # 4. Classification de la boucle
        loop = self._classify_loop(hurst_est.h, xcorr_res, inflection)

        # 5. Sizing et biais de positionnement
        sizing   = self._sizing_for_loop(loop)
        bias     = self._bias_for_loop(loop)
        signals  = self._generate_signals(hurst_est, xcorr_res, loop, inflection)

        result = ReflexivityResult(
            loop              = loop,
            hurst             = hurst_est.h,
            reflexivity_index = xcorr_res.ri,
            xcorr_ps          = xcorr_res.xcorr_ps,
            xcorr_sp          = xcorr_res.xcorr_sp,
            hurst_reliable    = hurst_est.reliable,
            sizing_modifier   = sizing,
            positioning_bias  = bias,
            signals           = signals,
        )

        logger.info("[Strate4] %s | asset=%s", result.summary(), asset)
        self._last_result = result
        self._save_to_db(result, asset)
        return result.to_dict()

    def backtest(self, df: pd.DataFrame) -> BacktestResult:
        """
        Rejoue l'analyse de réflexivité sur un DataFrame historique.

        Args:
            df: DataFrame avec au minimum :
                - 'close'           (float) — prix de clôture
                - 'sentiment_proxy' (float, optionnel) — funding rate ou sentiment score
                - 'pnl_pct'         (float, optionnel) — pour les métriques qualité

        La fenêtre glisse sur chaque barre — observation par observation.
        """
        if "close" not in df.columns:
            logger.warning("[Strate4] Backtest : colonne 'close' manquante.")
            return BacktestResult(results=[])

        prices_full = df["close"].values.astype(float)
        has_sent    = "sentiment_proxy" in df.columns
        results: list[dict] = []

        for i in range(self._hurst_window, len(df)):
            window_prices = pd.Series(prices_full[max(0, i - self._hurst_window): i + 1])
            window_sent   = None
            if has_sent:
                sent_arr    = df["sentiment_proxy"].values.astype(float)
                window_sent = pd.Series(sent_arr[max(0, i - self._hurst_window): i + 1])

            res = self.analyze(window_prices, window_sent)

            row: dict = {
                "idx":              i,
                "loop":             res["loop"],
                "hurst":            res["hurst"],
                "reflexivity_index": res["reflexivity_index"],
                "sizing_modifier":  res["sizing_modifier"],
            }
            if "pnl_pct" in df.columns:
                row["pnl_pct"] = float(df["pnl_pct"].iloc[i])
            results.append(row)

        return BacktestResult(results=results)

    @property
    def last_result(self) -> Optional[ReflexivityResult]:
        """Dernier résultat calculé (None si jamais appelé)."""
        return self._last_result

    # ── Hurst Exponent (R/S Analysis) ────────────────────────────────────────

    def _estimate_hurst(self, prices: np.ndarray) -> HurstEstimate:
        """
        Estime l'exposant de Hurst via l'analyse R/S de Mandelbrot-Hurst.

        Algorithme :
          Pour chaque lag τ ∈ [4, N/2] :
            1. Divise la série en chunks de taille τ
            2. Pour chaque chunk : R = range(cumsum(deviations)), S = std
            3. R/S moyen du lag = proxy de la persistance
          Régression log(RS) ~ H × log(τ) → pente = H

        Fiabilité : marquée False si < HURST_WINDOW_MIN points.
        """
        returns = np.diff(np.log(np.maximum(prices, 1e-10)))
        n = len(returns)

        if n < HURST_WINDOW_MIN:
            return HurstEstimate(h=0.5, n_points=n, reliable=False, log_rs_slope=0.0)

        lags:      list[int]   = []
        rs_values: list[float] = []

        for lag in range(4, max(n // 2, 5)):
            chunks = [returns[i: i + lag] for i in range(0, n - lag + 1, lag)]
            rs_chunk: list[float] = []

            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                mean  = float(np.mean(chunk))
                devs  = np.cumsum(chunk - mean)
                R     = float(np.max(devs) - np.min(devs))
                S     = float(np.std(chunk, ddof=1))
                if S > 1e-12 and R > 0:
                    rs_chunk.append(R / S)

            if rs_chunk:
                lags.append(lag)
                rs_values.append(float(np.mean(rs_chunk)))

        if len(lags) < 2:
            return HurstEstimate(h=0.5, n_points=n, reliable=False, log_rs_slope=0.0)

        log_tau = np.log(np.array(lags, dtype=float))
        log_rs  = np.log(np.array(rs_values, dtype=float))

        # Régression linéaire log-log
        slope, _ = np.polyfit(log_tau, log_rs, 1)
        h = float(np.clip(slope, 0.0, 1.0))

        return HurstEstimate(h=h, n_points=n, reliable=(n >= HURST_WINDOW_MIN), log_rs_slope=slope)

    # ── Cross-corrélation prix ↔ sentiment ────────────────────────────────────

    def _compute_xcorr(
        self,
        prices:          np.ndarray,
        sentiment_proxy: Optional[pd.Series],
    ) -> CrossCorrResult:
        """
        Calcule les corrélations croisées prix → sentiment et sentiment → prix.

        Méthode : corrélation de Pearson sur (x[:-lag], y[lag:]) pour lag ∈ [1..MAX_LAG].
        Retourne le maximum de corrélation sur tous les lags positifs.

        Si sentiment_proxy est absent ou trop courte, retourne RI = 0.0.
        """
        if sentiment_proxy is None:
            return CrossCorrResult(
                xcorr_ps=0.0, xcorr_sp=0.0, ri=0.0,
                best_lag_ps=0, best_lag_sp=0, available=False,
            )

        sent_arr = np.array(sentiment_proxy.dropna(), dtype=float)
        n = min(len(prices), len(sent_arr))

        if n < XCORR_MIN_POINTS:
            return CrossCorrResult(
                xcorr_ps=0.0, xcorr_sp=0.0, ri=0.0,
                best_lag_ps=0, best_lag_sp=0, available=False,
            )

        p   = prices[-n:]
        s   = sent_arr[-n:]
        ret = np.diff(np.log(np.maximum(p, 1e-10)))  # rendements log du prix

        best_ps, best_sp = 0.0, 0.0
        lag_ps, lag_sp   = 0, 0

        for lag in range(1, min(self._xcorr_max_lag + 1, n - 1)):
            # Prix → sentiment : est-ce que le prix d'hier crée le sentiment d'aujourd'hui ?
            x_ps = ret[:-lag]
            y_ps = np.diff(s)[lag:]
            if len(x_ps) > 3 and len(y_ps) == len(x_ps):
                c = float(np.corrcoef(x_ps, y_ps)[0, 1])
                if not math.isnan(c) and c > best_ps:
                    best_ps, lag_ps = c, lag

            # Sentiment → prix : est-ce que le sentiment d'hier anticipe le prix ?
            x_sp = np.diff(s)[:-lag]
            y_sp = ret[lag:]
            if len(x_sp) > 3 and len(y_sp) == len(x_sp):
                c = float(np.corrcoef(x_sp, y_sp)[0, 1])
                if not math.isnan(c) and c > best_sp:
                    best_sp, lag_sp = c, lag

        ri = float(np.clip(best_ps * best_sp, 0.0, 1.0))

        return CrossCorrResult(
            xcorr_ps=best_ps, xcorr_sp=best_sp,
            ri=ri, best_lag_ps=lag_ps, best_lag_sp=lag_sp,
            available=True,
        )

    # ── Détection d'inflexion ─────────────────────────────────────────────────

    def _detect_inflection(
        self,
        prices:          np.ndarray,
        sentiment_proxy: Optional[pd.Series],
    ) -> bool:
        """
        Détecte si une boucle positive est sur le point de se briser.

        Condition : boucle semblait positive sur la première moitié de la fenêtre,
        mais le momentum de la corrélation décroît sur la seconde moitié.

        Implémentation : compare le Hurst sur première moitié vs seconde moitié.
        Si H diminue significativement (INFLECTION_CORR_DECAY) → inflexion.
        """
        n = len(prices)
        if n < 2 * HURST_WINDOW_MIN:
            return False

        mid = n // 2
        h_first  = self._estimate_hurst(prices[:mid])
        h_second = self._estimate_hurst(prices[mid:])

        if not h_first.reliable or not h_second.reliable:
            return False

        # Inflexion si : première moitié en boucle, seconde en déclin
        was_loop = h_first.h > HURST_LOOP
        is_fading = (h_first.h - h_second.h) > INFLECTION_CORR_DECAY
        return bool(was_loop and is_fading)

    # ── Classification de la boucle ───────────────────────────────────────────

    @staticmethod
    def _classify_loop(
        h:         float,
        xcorr:     CrossCorrResult,
        inflection: bool,
    ) -> ReflexivityLoop:
        """
        Classifie la boucle réflexive depuis H, RI, et le signal d'inflexion.

        INFLECTION  : priorité maximale — boucle active mais en train de se briser
        POSITIVE    : H > HURST_LOOP, RI > RI_THRESHOLD ou xcorr_sp > 0 (momentum haussier)
        NEGATIVE    : H > HURST_LOOP, corrélations négatives (capitulation)
        MEAN_REV    : H < HURST_MEAN_REV (force contrarian)
        NEUTRAL     : H ≈ 0.5, pas de signal fort
        """
        loop_active = h > HURST_LOOP

        if loop_active and inflection:
            return ReflexivityLoop.INFLECTION

        if loop_active and xcorr.ri > RI_THRESHOLD:
            # Les deux sens de corrélation sont positifs → boucle fermée
            return ReflexivityLoop.POSITIVE_LOOP

        if loop_active and xcorr.xcorr_sp < -0.1:
            # Corrélation inverse → la dynamique est baissière
            return ReflexivityLoop.NEGATIVE_LOOP

        if loop_active and not xcorr.available:
            # Hurst élevé mais pas de données de sentiment → POSITIVE par défaut
            return ReflexivityLoop.POSITIVE_LOOP

        if h < HURST_MEAN_REV:
            return ReflexivityLoop.MEAN_REVERTING

        return ReflexivityLoop.NEUTRAL

    # ── Sizing et biais ───────────────────────────────────────────────────────

    @staticmethod
    def _sizing_for_loop(loop: ReflexivityLoop) -> float:
        """
        Retourne le multiplicateur de sizing pour la boucle détectée.

        POSITIVE_LOOP : +10% — rider la vague réflexive (momentum justifié)
        INFLECTION    : −35% — danger maximal, réduction agressive
        NEGATIVE_LOOP : −20% — boucle baissière, short ou neutre
        MEAN_REVERTING: 0%   — position normale (pas de biais réflexif)
        NEUTRAL       : 0%   — pas de signal fort
        """
        return {
            ReflexivityLoop.POSITIVE_LOOP:  SIZING_POSITIVE_LOOP,
            ReflexivityLoop.INFLECTION:     SIZING_INFLECTION,
            ReflexivityLoop.NEGATIVE_LOOP:  SIZING_NEGATIVE_LOOP,
            ReflexivityLoop.MEAN_REVERTING: SIZING_MEAN_REVERTING,
            ReflexivityLoop.NEUTRAL:        SIZING_NEUTRAL,
        }[loop]

    @staticmethod
    def _bias_for_loop(loop: ReflexivityLoop) -> str:
        """
        Biais de positionnement associé à chaque type de boucle.

        POSITIVE_LOOP → "long"   (rider la boucle haussière)
        INFLECTION    → "reduce" (ne pas attendre, sortir rapidement)
        NEGATIVE_LOOP → "short"  (rider la boucle baissière)
        MEAN_REVERTING→ "long"   (opportunité contrarian — prix survendu)
        NEUTRAL       → "neutral"
        """
        return {
            ReflexivityLoop.POSITIVE_LOOP:  "long",
            ReflexivityLoop.INFLECTION:     "reduce",
            ReflexivityLoop.NEGATIVE_LOOP:  "short",
            ReflexivityLoop.MEAN_REVERTING: "long",
            ReflexivityLoop.NEUTRAL:        "neutral",
        }[loop]

    # ── Génération de signaux ─────────────────────────────────────────────────

    @staticmethod
    def _generate_signals(
        hurst_est:  HurstEstimate,
        xcorr_res:  CrossCorrResult,
        loop:       ReflexivityLoop,
        inflection: bool,
    ) -> list[str]:
        """Génère des descriptions textuelles pour le log et le Conseil."""
        signals: list[str] = []
        rel = "" if hurst_est.reliable else " (estimation non fiable)"

        signals.append(f"H={hurst_est.h:.3f}{rel} → {'persistant' if hurst_est.h > 0.5 else 'mean-reverting'}")

        if xcorr_res.available:
            if xcorr_res.ri > RI_THRESHOLD:
                signals.append(
                    f"Boucle fermée : RI={xcorr_res.ri:.3f} "
                    f"(PS={xcorr_res.xcorr_ps:.3f} lag={xcorr_res.best_lag_ps}j, "
                    f"SP={xcorr_res.xcorr_sp:.3f} lag={xcorr_res.best_lag_sp}j)"
                )
            else:
                signals.append(f"Boucle ouverte : RI={xcorr_res.ri:.3f} < seuil {RI_THRESHOLD}")
        else:
            signals.append("Pas de proxy de sentiment — Hurst seul disponible")

        if inflection:
            signals.append("⚡ INFLEXION DÉTECTÉE — H en déclin rapide sur seconde moitié")

        return signals

    # ── Résultat neutre par défaut ────────────────────────────────────────────

    @staticmethod
    def _neutral_result(reason: str = "") -> ReflexivityResult:
        """Retourne un état neutre quand les données sont insuffisantes."""
        return ReflexivityResult(
            loop              = ReflexivityLoop.NEUTRAL,
            hurst             = 0.5,
            reflexivity_index = 0.0,
            xcorr_ps          = 0.0,
            xcorr_sp          = 0.0,
            hurst_reliable    = False,
            sizing_modifier   = SIZING_NEUTRAL,
            positioning_bias  = "neutral",
            signals           = [reason] if reason else ["Données insuffisantes"],
        )

    # ── SQLite ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reflexivity_history (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp          TEXT NOT NULL,
                        asset              TEXT NOT NULL,
                        loop               TEXT NOT NULL,
                        hurst              REAL NOT NULL,
                        reflexivity_index  REAL NOT NULL,
                        xcorr_ps           REAL NOT NULL,
                        xcorr_sp           REAL NOT NULL,
                        sizing_modifier    REAL NOT NULL,
                        positioning_bias   TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reflex_ts
                    ON reflexivity_history (timestamp DESC)
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("[Strate4] DB init error: %s", exc)

    def _save_to_db(self, result: ReflexivityResult, asset: str) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO reflexivity_history
                    (timestamp, asset, loop, hurst, reflexivity_index, xcorr_ps,
                     xcorr_sp, sizing_modifier, positioning_bias)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.timestamp, asset, result.loop.value, result.hurst,
                    result.reflexivity_index, result.xcorr_ps, result.xcorr_sp,
                    result.sizing_modifier, result.positioning_bias,
                ))
                conn.commit()
        except Exception as exc:
            logger.debug("[Strate4] DB save error: %s", exc)

    def get_history(self, asset: str = "BTC", limit: int = 100) -> list[dict]:
        """Récupère les N dernières analyses depuis SQLite."""
        if not self._db_path or not self._db_path.exists():
            return []
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("""
                    SELECT timestamp, loop, hurst, reflexivity_index,
                           xcorr_ps, xcorr_sp, sizing_modifier, positioning_bias
                    FROM reflexivity_history
                    WHERE asset = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (asset, limit)).fetchall()
            cols = ["timestamp", "loop", "hurst", "reflexivity_index",
                    "xcorr_ps", "xcorr_sp", "sizing_modifier", "positioning_bias"]
            return [dict(zip(cols, row)) for row in rows]
        except Exception as exc:
            logger.debug("[Strate4] DB history error: %s", exc)
            return []
