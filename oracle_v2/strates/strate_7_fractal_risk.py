"""
Strate 7 — Fractal Risk Engine
"Les marchés ont des queues grasses et une mémoire longue." — Benoît Mandelbrot

Théorie : Mandelbrot (1963) a montré que les rendements financiers suivent des distributions
alpha-stables (Lévy), pas gaussiennes. Les marchés ont une dimension fractale mesurable.

Composants :
  - Hurst Exponent   → mémoire longue du marché (R/S analysis)
  - Fractal Dimension → complexité/prévisibilité (méthode Higuchi)
  - Lévy Distribution → paramétrage des queues grasses (scipy alpha-stable)
  - Expected Shortfall → CVaR, mesure de risque cohérente (au-delà du VaR)
  - Kelly Modifié     → dimensionnement optimal avec pondération Minsky + Hurst

Régimes de marché basés sur H (exposant de Hurst) :
  H > 0.6 → TRENDING      (mémoire longue, momentum)
  H < 0.4 → MEAN_REVERTING (anti-corrélation)
  0.4–0.6 → RANDOM         (marche aléatoire)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

HURST_TRENDING_THRESHOLD      = 0.6
HURST_MEAN_REVERTING_THRESHOLD = 0.4
HURST_DEFAULT                 = 0.5

FD_DEFAULT                    = 1.5
FD_K_MAX                      = 10

LEVY_ALPHA_GAUSSIAN           = 2.0
LEVY_DEFAULT_PARAMS           = {"alpha": 2.0, "beta": 0.0, "loc": 0.0, "scale": 1.0, "tail_index": 2.0}

KELLY_MAX_FRACTION            = 0.25
MINSKY_RISK_PER_PHASE         = 0.15

REGIME_TRENDING        = "TRENDING"
REGIME_MEAN_REVERTING  = "MEAN_REVERTING"
REGIME_RANDOM          = "RANDOM"

MIN_SERIES_LENGTH = 20


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class FractalRiskProfile:
    hurst: float
    fractal_dimension: float
    levy_alpha: float          # tail index
    levy_beta: float
    es_1pct: float
    es_5pct: float
    risk_regime: str           # TRENDING / MEAN_REVERTING / RANDOM
    kelly_fraction: float
    computed_at: datetime


# ── Engine ────────────────────────────────────────────────────────────────────

class FractalRiskEngine:
    """
    Moteur de risque fractal basé sur les travaux de Mandelbrot.
    Toutes les méthodes sont robustes aux séries courtes (< 20 points).
    """

    def __init__(self) -> None:
        self._last_hurst: float = HURST_DEFAULT

    # ── 1. Hurst Exponent (R/S Analysis) ──────────────────────────────────────

    def compute_hurst_exponent(self, prices: pd.Series) -> float:
        """
        Calcule l'exposant de Hurst via l'analyse R/S (Rescaled Range).

        H > 0.5 → tendance (mémoire longue)
        H < 0.5 → mean-reverting (anti-corrélation)
        H ≈ 0.5 → marche aléatoire

        Returns H in [0, 1]. Default 0.5 if series too short (< 20 points).
        """
        series = prices.dropna()
        if len(series) < MIN_SERIES_LENGTH:
            logger.debug("Hurst: série trop courte (%d pts), retourne 0.5", len(series))
            self._last_hurst = HURST_DEFAULT
            return HURST_DEFAULT

        try:
            prices_arr = series.values.astype(float)

            # R/S analysis opère sur les log-rendements (standard académique)
            # Évite les biais de tendance des prix bruts
            log_returns = np.diff(np.log(np.abs(prices_arr) + 1e-10))
            n = len(log_returns)

            if n < MIN_SERIES_LENGTH - 1:
                self._last_hurst = HURST_DEFAULT
                return HURST_DEFAULT

            # Tailles de blocs logarithmiquement espacées
            # Entre 8 et n//2, au moins 8 points par bloc
            min_block = max(8, n // 20)
            max_block = n // 2

            if max_block < min_block:
                self._last_hurst = HURST_DEFAULT
                return HURST_DEFAULT

            # Générer ~10 tailles de blocs espacées logarithmiquement
            num_sizes = min(10, int(np.log2(max_block / min_block)) + 2)
            num_sizes = max(num_sizes, 3)
            raw_sizes = np.unique(
                np.round(np.geomspace(min_block, max_block, num_sizes)).astype(int)
            )
            block_sizes = [int(s) for s in raw_sizes if min_block <= s <= max_block]

            if len(block_sizes) < 2:
                block_sizes = [min_block, max_block]

            rs_values = []
            ns_values = []

            for size in block_sizes:
                if size < 4 or size > n:
                    continue
                num_blocks = n // size
                if num_blocks < 1:
                    continue

                block_rs = []
                for i in range(num_blocks):
                    block = log_returns[i * size:(i + 1) * size]
                    if len(block) < 2:
                        continue
                    mean = np.mean(block)
                    deviations = block - mean
                    cumsum = np.cumsum(deviations)
                    R = np.max(cumsum) - np.min(cumsum)
                    S = np.std(block, ddof=1)
                    if S > 0:
                        block_rs.append(R / S)

                if block_rs:
                    rs_values.append(np.mean(block_rs))
                    ns_values.append(size)

            if len(rs_values) < 2:
                self._last_hurst = HURST_DEFAULT
                return HURST_DEFAULT

            log_n  = np.log(ns_values)
            log_rs = np.log(rs_values)
            slope, _, _, _, _ = stats.linregress(log_n, log_rs)

            H = float(np.clip(slope, 0.0, 1.0))
            self._last_hurst = H
            return H

        except Exception as exc:
            logger.warning("Hurst: erreur de calcul (%s), retourne 0.5", exc)
            self._last_hurst = HURST_DEFAULT
            return HURST_DEFAULT

    # ── 2. Fractal Dimension (Higuchi) ────────────────────────────────────────

    def compute_fractal_dimension(self, prices: pd.Series) -> float:
        """
        Calcule la dimension fractale via la méthode de Higuchi.

        FD ∈ [1, 2] :
          FD ≈ 1 → courbe lisse/prévisible
          FD ≈ 2 → courbe chaotique/complexe

        Returns FD. Default 1.5 if series too short (< 20 points).
        """
        series = prices.dropna()
        if len(series) < MIN_SERIES_LENGTH:
            logger.debug("FD Higuchi: série trop courte (%d pts), retourne 1.5", len(series))
            return FD_DEFAULT

        try:
            x = series.values.astype(float)
            n = len(x)
            k_max = min(FD_K_MAX, n // 4)

            if k_max < 2:
                return FD_DEFAULT

            log_k  = []
            log_Lm = []

            for k in range(1, k_max + 1):
                lengths = []
                for m in range(1, k + 1):
                    # Indices : m-1, m-1+k, m-1+2k, ...
                    idxs = list(range(m - 1, n, k))
                    if len(idxs) < 2:
                        continue
                    sub = x[idxs]
                    # Longueur normalisée du segment
                    Lm_k = (np.sum(np.abs(np.diff(sub))) * (n - 1)) / (k * (len(sub) - 1))
                    lengths.append(Lm_k)

                if lengths:
                    log_k.append(np.log(k))
                    log_Lm.append(np.log(np.mean(lengths)))

            if len(log_k) < 2:
                return FD_DEFAULT

            slope, _, _, _, _ = stats.linregress(log_k, log_Lm)
            FD = float(np.clip(-slope, 1.0, 2.0))
            return FD

        except Exception as exc:
            logger.warning("Fractal Dimension: erreur (%s), retourne 1.5", exc)
            return FD_DEFAULT

    # ── 3. Lévy Distribution (Alpha-Stable) ───────────────────────────────────

    def fit_levy_distribution(self, returns: pd.Series) -> dict:
        """
        Ajuste une distribution alpha-stable (Lévy/Pareto) aux rendements.

        alpha < 2 → queues grasses (Gaussienne = alpha=2)

        Returns dict: {alpha, beta, loc, scale, tail_index}
        """
        r = returns.dropna()
        if len(r) < MIN_SERIES_LENGTH:
            logger.debug("Lévy fit: série trop courte, retourne paramètres normaux")
            return dict(LEVY_DEFAULT_PARAMS)

        try:
            # scipy levy_stable.fit retourne (alpha, beta, loc, scale)
            alpha, beta, loc, scale = stats.levy_stable.fit(r.values)
            alpha = float(np.clip(alpha, 0.1, 2.0))
            beta  = float(np.clip(beta, -1.0, 1.0))
            return {
                "alpha":      alpha,
                "beta":       float(beta),
                "loc":        float(loc),
                "scale":      float(scale),
                "tail_index": alpha,
            }
        except Exception as exc:
            logger.warning("Lévy fit: échec (%s), fallback normal (alpha=2.0)", exc)
            return dict(LEVY_DEFAULT_PARAMS)

    # ── 4. Expected Shortfall (CVaR) ──────────────────────────────────────────

    def compute_expected_shortfall(self, returns: pd.Series, alpha: float = 0.01) -> float:
        """
        Calcule l'Expected Shortfall (CVaR) au niveau alpha.

        ES = E[loss | loss > VaR_alpha]

        Returns positive float (magnitude de la perte attendue).
        """
        r = returns.dropna()
        if len(r) == 0:
            return 0.0

        try:
            var_alpha = r.quantile(alpha)
            tail = r[r <= var_alpha]
            if len(tail) == 0:
                return float(abs(var_alpha))
            es = float(abs(tail.mean()))
            return es
        except Exception as exc:
            logger.warning("ES: erreur (%s), retourne 0.0", exc)
            return 0.0

    # ── 5. Kelly Fraction (Modifié) ───────────────────────────────────────────

    def compute_kelly_fraction(
        self,
        edge: float,
        odds: float,
        conviction: float,
        minsky_phase: int,
    ) -> float:
        """
        Calcule la fraction de Kelly modifiée.

        f* = (edge / odds) × (conviction / 100) × (1 - minsky_risk) × hurst_adjustment

        - minsky_risk = minsky_phase × 0.15  (0% → 60%)
        - hurst_adjustment : H=0.5 → 1.0, H=0.7 → 1.2, H=0.3 → 0.8
        - Cap à 0.25 (25% du capital maximum)
        - Retourne 0.0 si edge <= 0
        """
        if edge <= 0:
            return 0.0

        try:
            # Minsky risk reduction
            minsky_risk = float(np.clip(minsky_phase, 0, 4)) * MINSKY_RISK_PER_PHASE
            minsky_factor = max(0.0, 1.0 - minsky_risk)

            # Hurst adjustment : interpolation linéaire autour de 0.5
            H = self._last_hurst
            # H=0.5 → 1.0, H=0.7 → 1.2, H=0.3 → 0.8
            # Pente : +0.2 / 0.2 = +1.0 par unité de H au-dessus de 0.5
            hurst_adjustment = 1.0 + (H - 0.5) * 2.0
            hurst_adjustment = float(np.clip(hurst_adjustment, 0.5, 1.5))

            # Kelly de base
            base_kelly = edge / odds if odds > 0 else 0.0
            conviction_factor = float(np.clip(conviction, 0.0, 100.0)) / 100.0

            f = base_kelly * conviction_factor * minsky_factor * hurst_adjustment
            f = float(np.clip(f, 0.0, KELLY_MAX_FRACTION))
            return f

        except Exception as exc:
            logger.warning("Kelly: erreur (%s), retourne 0.0", exc)
            return 0.0

    # ── 6. Analyze (interface principale) ─────────────────────────────────────

    def analyze(self, prices: pd.Series, returns: pd.Series = None) -> dict:
        """
        Lance toutes les analyses fractales sur une série de prix.

        Si returns est None, les rendements sont calculés depuis les prix.

        Returns dict avec clés :
          hurst, fractal_dimension, levy_params,
          es_1pct, es_5pct, risk_regime
        """
        if returns is None:
            returns = prices.pct_change().dropna()

        H  = self.compute_hurst_exponent(prices)
        FD = self.compute_fractal_dimension(prices)
        levy_params = self.fit_levy_distribution(returns)
        es_1pct = self.compute_expected_shortfall(returns, alpha=0.01)
        es_5pct = self.compute_expected_shortfall(returns, alpha=0.05)

        # Régime de marché
        if H > HURST_TRENDING_THRESHOLD:
            risk_regime = REGIME_TRENDING
        elif H < HURST_MEAN_REVERTING_THRESHOLD:
            risk_regime = REGIME_MEAN_REVERTING
        else:
            risk_regime = REGIME_RANDOM

        return {
            "hurst":            H,
            "fractal_dimension": FD,
            "levy_params":      levy_params,
            "es_1pct":          es_1pct,
            "es_5pct":          es_5pct,
            "risk_regime":      risk_regime,
        }

    # ── 7. Build FractalRiskProfile ───────────────────────────────────────────

    def build_profile(
        self,
        prices: pd.Series,
        returns: pd.Series = None,
        edge: float = 0.0,
        odds: float = 1.0,
        conviction: float = 50.0,
        minsky_phase: int = 0,
    ) -> FractalRiskProfile:
        """
        Construit un FractalRiskProfile complet.
        """
        result = self.analyze(prices, returns)
        kelly  = self.compute_kelly_fraction(edge, odds, conviction, minsky_phase)

        return FractalRiskProfile(
            hurst            = result["hurst"],
            fractal_dimension= result["fractal_dimension"],
            levy_alpha       = result["levy_params"]["alpha"],
            levy_beta        = result["levy_params"]["beta"],
            es_1pct          = result["es_1pct"],
            es_5pct          = result["es_5pct"],
            risk_regime      = result["risk_regime"],
            kelly_fraction   = kelly,
            computed_at      = datetime.now(timezone.utc),
        )
