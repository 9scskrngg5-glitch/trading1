"""
Strate 7 — EVT Volatility Forecaster (S7) pour ORACLE v2.

Forecaster de risque basé sur Extreme Value Theory (EVT).
Calibre les paramètres GPD (Generalized Pareto Distribution) pour :
- Estimer VaR et Expected Shortfall
- Évaluer le régime de queue de distribution (CALM, STRESSED, CRISIS)
- Ajuster le Kelly sizing selon le tail risk
- Émettre des votes parlement basés sur le risk regime

PAS un classifieur, mais un calculateur de risque pour le sizing.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Union
import logging

from ml.base_model import OracleModel
from features.extreme_value import fit_gpd, evt_var, expected_shortfall, tail_risk_score

logger = logging.getLogger("ORACLE.S7VolatilityEVT")


class S7EVTVolatilityForecaster(OracleModel):
    """
    Strate 7 — EVT Volatility Forecaster.

    Utilise Extreme Value Theory pour :
    1. Calibrer la GPD (Generalized Pareto Distribution) sur l'historique
    2. Calculer VaR et Expected Shortfall
    3. Évaluer le régime de tail risk (CALM / STRESSED / CRISIS)
    4. Ajuster dynamiquement le Kelly factor pour le sizing

    Ne prédit pas LONG/SHORT, mais quantifie le risque.
    Le parliament l'utilise pour RÉDUIRE ou AUGMENTER la confiance des autres strates.

    References
    ----------
    - Embrechts, P., Klüppelberg, C., & Mikosch, T. (1997).
      "Modelling Extremal Events for Insurance and Finance."
    """

    def __init__(self, name: str = 'S7_VolatilityEVT',
                 window: int = 100,
                 threshold_pct: float = 0.95,
                 base_kelly: float = 0.25):
        """
        Initialize S7 EVT Volatility Forecaster.

        Parameters
        ----------
        name : str
            Nom du modèle
        window : int
            Fenêtre historique pour calibration EVT
        threshold_pct : float
            Percentile pour tail extraction (0-100), default 95%
        base_kelly : float
            Kelly factor baseline
        """
        super().__init__(model_type='sklearn', name=name)

        self.window = window
        self.threshold_pct = threshold_pct
        self.base_kelly = base_kelly

        # Calibrated EVT parameters
        self._xi = None  # Shape parameter
        self._sigma = None  # Scale parameter
        self._threshold = None  # Tail threshold

    def fit(self, returns: np.ndarray, window: Optional[int] = None):
        """
        Calibre les paramètres EVT (GPD) sur l'historique.

        Parameters
        ----------
        returns : np.ndarray
            Série historique de returns (N,)
        window : int, optional
            Fenêtre de calibration (défaut: self.window)
        """
        returns = np.asarray(returns, dtype=float)

        if window is None:
            window = self.window

        # Utiliser les derniers `window` points
        if len(returns) > window:
            calibration_returns = returns[-window:]
        else:
            calibration_returns = returns

        # Convertir returns en losses
        losses = -np.minimum(calibration_returns, 0)
        losses = losses[losses > 0]

        if len(losses) < 10:
            logger.warning(f"S7: Only {len(losses)} losses, using default EVT params")
            self._xi = 0.1
            self._sigma = np.mean(losses) if len(losses) > 0 else 1e-6
            self._threshold = np.percentile(losses, self.threshold_pct) if len(losses) > 0 else 0.0
        else:
            # Fit GPD
            self._xi, self._sigma, self._threshold = fit_gpd(losses, self.threshold_pct)

        logger.info(f"S7 EVT calibrated: ξ={self._xi:.4f}, σ={self._sigma:.6f}, threshold={self._threshold:.6f}")
        self.is_fitted = True

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Pas utilisé (le forecaster n'émet pas de prédictions de classe).
        Retourne des NaNs.

        Parameters
        ----------
        X : array-like
            (Ignoré)

        Returns
        -------
        np.ndarray
            Vecteur de NaNs
        """
        if isinstance(X, pd.DataFrame):
            X = X.values
        return np.full(len(X), np.nan)

    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Pas utilisé.

        Parameters
        ----------
        X : array-like
            (Ignoré)

        Returns
        -------
        np.ndarray
            Vecteur de NaNs
        """
        if isinstance(X, pd.DataFrame):
            X = X.values
        return np.full((len(X), 3), np.nan)

    def compute_var_evt(self, returns: np.ndarray,
                       confidence: float = 0.99) -> float:
        """
        Calcule la VaR via EVT.

        Parameters
        ----------
        returns : np.ndarray
            Série de returns (N,)
        confidence : float
            Confidence level (0.99 = 99%)

        Returns
        -------
        float
            VaR_EVT en tant que loss (positive)
            Interprétation : avec (1-confidence)*100% de probabilité,
            la perte surpasse cette valeur.
        """
        returns = np.asarray(returns, dtype=float)
        losses = -np.minimum(returns, 0)
        losses = losses[losses > 0]

        if len(losses) < 10:
            logger.warning("Insufficient data for VaR calculation, using historical percentile")
            return np.percentile(losses, confidence * 100)

        var = evt_var(losses, confidence=confidence, threshold_pct=self.threshold_pct)
        return float(var)

    def compute_es_evt(self, returns: np.ndarray,
                      confidence: float = 0.99) -> float:
        """
        Calcule l'Expected Shortfall (CVaR) via EVT.

        Parameters
        ----------
        returns : np.ndarray
            Série de returns (N,)
        confidence : float
            Confidence level (0.99 = 99%)

        Returns
        -------
        float
            Expected Shortfall (average loss beyond VaR)
        """
        returns = np.asarray(returns, dtype=float)
        losses = -np.minimum(returns, 0)
        losses = losses[losses > 0]

        if len(losses) < 10:
            logger.warning("Insufficient data for ES calculation")
            var = np.percentile(losses, confidence * 100)
            return np.mean(losses[losses >= var])

        es = expected_shortfall(losses, confidence=confidence, threshold_pct=self.threshold_pct)
        return float(es)

    def tail_regime(self, returns: np.ndarray, window: int = 100) -> str:
        """
        Détermine le régime de queue de distribution.

        Régimes :
        - CALM: tail_risk_score < 0.3 (light tail, low extreme risk)
        - STRESSED: 0.3 <= tail_risk_score < 0.7 (moderate tail)
        - CRISIS: tail_risk_score >= 0.7 (heavy tail, extreme risk)

        Parameters
        ----------
        returns : np.ndarray
            Série de returns (N,)
        window : int
            Rolling window

        Returns
        -------
        str
            'CALM', 'STRESSED', ou 'CRISIS'
        """
        returns = np.asarray(returns, dtype=float)

        if len(returns) < window:
            logger.warning("Not enough data for tail regime estimation, defaulting to CALM")
            return 'CALM'

        # Compute rolling tail risk score
        tail_scores = tail_risk_score(returns, window=window, threshold_pct=self.threshold_pct)

        # Use last valid score
        last_scores = tail_scores[~np.isnan(tail_scores)]
        if len(last_scores) == 0:
            return 'CALM'

        latest_score = float(last_scores[-1])

        if latest_score >= 0.7:
            return 'CRISIS'
        elif latest_score >= 0.3:
            return 'STRESSED'
        else:
            return 'CALM'

    def predict_sizing_factor(self, returns_recent: np.ndarray,
                             capital: float,
                             base_kelly: Optional[float] = None) -> float:
        """
        Prédit le facteur de sizing (multiplicateur du Kelly factor).

        Retourne un facteur dans [0.1, 1.0] :
        - 1.0 = Kelly nominal
        - 0.5 = Kelly demi (risque moyen)
        - 0.1 = Kelly minimal (crise, risque extrême)

        La volatilité extrême réduit le facteur.

        Parameters
        ----------
        returns_recent : np.ndarray
            Retours récents (20-100 points)
        capital : float
            Capital disponible
        base_kelly : float, optional
            Kelly factor baseline (défaut: self.base_kelly)

        Returns
        -------
        float
            Sizing factor [0.1, 1.0]
        """
        returns_recent = np.asarray(returns_recent, dtype=float)

        if base_kelly is None:
            base_kelly = self.base_kelly

        # Get tail regime
        regime = self.tail_regime(returns_recent, window=min(100, len(returns_recent)))

        # Map regime to sizing factor
        if regime == 'CRISIS':
            factor = 0.1  # Très réduit
        elif regime == 'STRESSED':
            factor = 0.5  # Moitié
        else:  # CALM
            factor = 1.0  # Nominal

        return float(factor)

    def sizing_report(self, returns: np.ndarray, capital: float) -> Dict:
        """
        Rapport complet de sizing et risk metrics.

        Parameters
        ----------
        returns : np.ndarray
            Série de returns
        capital : float
            Capital disponible

        Returns
        -------
        dict
            Rapport avec:
            - var_99: VaR 99%
            - es_99: Expected Shortfall 99%
            - kelly_factor: Kelly baseline
            - sizing_factor: Multiplicateur du Kelly
            - effective_kelly: Kelly * sizing_factor
            - tail_regime: 'CALM'/'STRESSED'/'CRISIS'
            - position_size_usd: Capital * effective_kelly
        """
        returns = np.asarray(returns, dtype=float)

        var_99 = self.compute_var_evt(returns, confidence=0.99)
        es_99 = self.compute_es_evt(returns, confidence=0.99)
        regime = self.tail_regime(returns, window=100)
        sizing_factor = self.predict_sizing_factor(returns[-100:], capital)
        effective_kelly = self.base_kelly * sizing_factor

        position_size_usd = capital * effective_kelly

        return {
            'var_99': float(var_99),
            'es_99': float(es_99),
            'kelly_factor': float(self.base_kelly),
            'sizing_factor': float(sizing_factor),
            'effective_kelly': float(effective_kelly),
            'tail_regime': regime,
            'position_size_usd': float(position_size_usd),
        }

    def parliament_vote(self, returns: np.ndarray,
                       close: np.ndarray) -> Dict:
        """
        Vote du parlement (strate 7) — Régime de risque.

        Le vote CHANGE la DIRECTION en fonction du régime de tail :
        - CRISIS: SHORT + réduire la confiance
        - STRESSED: NEUTRAL (laisser les autres décider)
        - CALM: LONG + augmenter la confiance

        La confiance reflète la inverse du tail_risk_score
        (tail_risk_score élevé = confiance basse, et vice versa).

        Parameters
        ----------
        returns : np.ndarray
            Série de returns
        close : np.ndarray
            Série de prix (non utilisée, mais pour consistency)

        Returns
        -------
        dict
            Vote avec structure:
            {
                'strate_name': 'S7_VolatilityEVT',
                'direction': 'LONG'|'SHORT'|'NEUTRAL',
                'confidence': float [0-1],
                'reasoning': str,
                'polymarket_signal': None
            }
        """
        returns = np.asarray(returns, dtype=float)

        # Fit si pas déjà fait
        if not self.is_fitted:
            self.fit(returns)

        # Get metrics
        regime = self.tail_regime(returns, window=100)
        var_99 = self.compute_var_evt(returns, confidence=0.99)
        sizing_factor = self.predict_sizing_factor(returns[-100:], capital=1.0)

        # Map regime to direction and confidence
        if regime == 'CRISIS':
            direction = 'SHORT'
            confidence = sizing_factor  # Low confidence in crisis
            reasoning_detail = "CRISIS: Heavy tail detected, extreme risk regime. Reducing position size and preferring SHORT for risk mitigation."
        elif regime == 'STRESSED':
            direction = 'NEUTRAL'
            confidence = 0.5
            reasoning_detail = "STRESSED: Moderate tail risk. Reducing leverage but remaining flexible."
        else:  # CALM
            direction = 'LONG'
            confidence = 1.0 - sizing_factor + 1.0  # Boost confidence
            confidence = min(confidence, 1.0)
            reasoning_detail = "CALM: Light tail, low extreme risk. Comfortable with nominal Kelly sizing."

        reasoning = (
            f"S7 EVT Volatility signal: {direction} (regime: {regime}, VaR_99%: {var_99:.6f}). "
            f"{reasoning_detail}"
        )

        return {
            'strate_name': self.name,
            'direction': direction,
            'confidence': float(confidence),
            'reasoning': reasoning,
            'polymarket_signal': None
        }
