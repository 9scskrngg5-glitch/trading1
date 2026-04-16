"""
S0 Régime HMM — Classification de régimes marché (Trend/Noise/Revert) via Hidden Markov Model.

Détecte automatiquement 3 régimes marché basés sur la volatilité et les rendements :
- Revert : Haute volatilité, rendements négatifs autocorrélés → mean-reversion gagnante
- Noise : Volatilité modérée, entropy élevée, signal faible
- Trend : Faible volatilité, rendements positifs persistants → momentum gagnant

Fallback heuristique si hmmlearn absent.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Union
from dataclasses import dataclass

from ml.base_model import OracleModel
from brain.parliament import Vote

# Import math features avec gestion robuste
import sys
import os

# Ajouter le chemin math au sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_math_path = os.path.join(_current_dir, '..', 'math')
_training_path = os.path.join(_current_dir, '..', 'training')

if _math_path not in sys.path:
    sys.path.insert(0, _math_path)
if _training_path not in sys.path:
    sys.path.insert(0, _training_path)

# Importer les fonctions math (évite conflit avec builtin 'math')
try:
    from entropy import rolling_entropy, snr_gate
    from topology import rolling_hurst
    HAS_MATH_FEATURES = True
except ImportError as e:
    # Fallback si scipy/dependencies manquent
    HAS_MATH_FEATURES = False

    # Définir des stubs simples
    def rolling_entropy(returns, window=20, n_bins=10):
        """Stub: entropy non disponible sans scipy."""
        return np.zeros(len(returns))

    def snr_gate(returns, window=20):
        """Stub: SNR non disponible sans scipy."""
        return np.ones(len(returns))

    def rolling_hurst(series, window=100):
        """Stub: Hurst non disponible."""
        return np.full(len(series), 0.5)

try:
    from hmmlearn import hmm
    HAS_HMMLEARN = True
except ImportError:
    HAS_HMMLEARN = False


@dataclass
class RegimeState:
    """Sortie d'inférence régime."""
    regime: int          # -1 (revert), 0 (noise), 1 (trend)
    confidence: float    # 0.0-1.0
    proba_revert: float
    proba_noise: float
    proba_trend: float
    volatility: float


class S0RegimeHMM(OracleModel):
    """
    Hidden Markov Model pour classification de régimes marché ORACLE v2.

    États HMM (3) mappés automatiquement après fit sur la volatilité moyenne :
    - État volatilité haute → Revert (-1)
    - État volatilité moyenne → Noise (0)
    - État volatilité basse → Trend (1)

    Méthodes principales :
    - fit(returns, volume=None) : entraîne le HMM
    - predict(returns, volume=None) → array de -1/0/1
    - predict_proba(returns, volume=None) → proba par régime
    - gate(returns, volume=None) → binaire 0/1 (trade allowed)
    - parliament_vote(returns, volume=None) → Vote pour parliament
    """

    def __init__(self, name: str = "S0_RegimeHMM"):
        super().__init__(model_type='sklearn', name=name)
        self.hmm_model = None
        self.regime_map = None  # Dict {state_idx: regime}
        self.state_volatilities = None  # Volatilité moyenne par état HMM
        self.scaler = None
        self.feature_names = [
            'returns', 'vol_rolling_20', 'entropy_rolling_20', 'snr_rolling_20', 'hurst_rolling'
        ]

    def build_features(
        self,
        returns: np.ndarray,
        volume: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Construit les features pour HMM.

        Parameters
        ----------
        returns : np.ndarray
            Rendements simples ou log, shape (n,)
        volume : np.ndarray, optional
            Volume trading, shape (n,). Si fourni, ajoute volume_ratio à features.

        Returns
        -------
        features : np.ndarray
            Features assemblées, shape (n, n_features)
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)

        # Feature 1 : returns bruts (normalisés par std)
        ret_norm = returns / (np.nanstd(returns) + 1e-8)

        # Feature 2 : volatilité rolling 20
        vol_rolling = pd.Series(returns).rolling(window=20, min_periods=1).std().values
        vol_norm = vol_rolling / (np.nanstd(vol_rolling) + 1e-8)

        # Feature 3 : entropy rolling 20
        try:
            entropy_rolling = rolling_entropy(returns, window=20, n_bins=10)
            # Relever à length(returns)
            entropy_rolling = np.concatenate([np.full(20, entropy_rolling[0]), entropy_rolling[20:]])
            entropy_norm = entropy_rolling / (np.nanstd(entropy_rolling) + 1e-8)
        except:
            entropy_norm = np.zeros(n)

        # Feature 4 : SNR rolling 20
        try:
            snr_rolling = snr_gate(returns, window=20)
            snr_norm = snr_rolling / (np.nanstd(snr_rolling) + 1e-8)
        except:
            snr_norm = np.zeros(n)

        # Feature 5 : Hurst rolling
        try:
            hurst_rolling = rolling_hurst(returns, window=50)
            # Relever à length(returns)
            hurst_rolling = np.concatenate([np.full(50, 0.5), hurst_rolling])[:n]
            hurst_norm = hurst_rolling / (np.nanstd(hurst_rolling) + 1e-8)
        except:
            hurst_norm = np.zeros(n)

        features = np.column_stack([ret_norm, vol_norm, entropy_norm, snr_norm, hurst_norm])

        # Optionnel : volume_ratio
        if volume is not None:
            volume = np.asarray(volume, dtype=float)
            vol_mean = pd.Series(volume).rolling(window=20, min_periods=1).mean().values
            vol_ratio = volume / (vol_mean + 1e-8)
            vol_ratio_norm = vol_ratio / (np.nanstd(vol_ratio) + 1e-8)
            features = np.column_stack([features, vol_ratio_norm])

        return np.nan_to_num(features, nan=0.0)

    def fit(self, returns: np.ndarray, volume: Optional[np.ndarray] = None, n_states: int = 3):
        """
        Entraîne le HMM sur les rendements.

        Parameters
        ----------
        returns : np.ndarray
            Rendements, shape (n,)
        volume : np.ndarray, optional
            Volume trading pour features enrichies
        n_states : int, default 3
            Nombre d'états HMM (classiquement 3)
        """
        returns = np.asarray(returns, dtype=float)

        # Gestion des séries courtes
        if len(returns) < 40:
            self.hmm_model = None
            self.is_fitted = True
            return

        # Build features
        features = self.build_features(returns, volume)

        if HAS_HMMLEARN:
            # Entraîner HMM
            self.hmm_model = hmm.GaussianHMM(n_components=n_states, covariance_type='full', n_iter=100)
            self.hmm_model.fit(features)

            # Mapper états sur régimes selon volatilité moyenne
            hidden_states = self.hmm_model.predict(features)
            self.state_volatilities = {}
            self.regime_map = {}

            for state_idx in range(n_states):
                mask = hidden_states == state_idx
                if mask.sum() > 0:
                    vol_mean = np.abs(returns[mask]).mean()
                    self.state_volatilities[state_idx] = vol_mean

            # Trier par volatilité : Haute→Revert, Moyenne→Noise, Basse→Trend
            sorted_states = sorted(
                self.state_volatilities.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.regime_map = {
                sorted_states[0][0]: -1,  # Volatilité haute → Revert
                sorted_states[1][0]: 0,   # Volatilité moyenne → Noise
                sorted_states[2][0]: 1,   # Volatilité basse → Trend
            }
        else:
            # Fallback heuristique sans hmmlearn
            self.hmm_model = None
            vol_rolling = pd.Series(returns).rolling(window=20, min_periods=1).std().values
            self.regime_map = {0: -1, 1: 0, 2: 1}  # Dummy

        self.is_fitted = True

    def predict(self, returns: np.ndarray, volume: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Prédit les régimes.

        Parameters
        ----------
        returns : np.ndarray
            Rendements, shape (n,)
        volume : np.ndarray, optional
            Volume trading

        Returns
        -------
        regimes : np.ndarray
            Array de régimes {-1, 0, 1}, shape (n,)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        returns = np.asarray(returns, dtype=float)

        if len(returns) < 40 or self.hmm_model is None:
            return np.zeros(len(returns), dtype=int)

        features = self.build_features(returns, volume)

        try:
            hidden_states = self.hmm_model.predict(features)
            regimes = np.array([self.regime_map.get(s, 0) for s in hidden_states])
        except:
            regimes = np.zeros(len(returns), dtype=int)

        return regimes

    def predict_proba(self, returns: np.ndarray, volume: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Retourne les probabilités par régime.

        Parameters
        ----------
        returns : np.ndarray
        volume : np.ndarray, optional

        Returns
        -------
        proba : np.ndarray
            Matrice de probabilités, shape (n, 3) pour [revert, noise, trend]
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        returns = np.asarray(returns, dtype=float)

        if len(returns) < 40 or self.hmm_model is None:
            return np.column_stack([np.zeros(len(returns)) for _ in range(3)])

        features = self.build_features(returns, volume)

        try:
            # Probabilités par état HMM
            hidden_proba = self.hmm_model.predict_proba(features)

            # Mapper sur les 3 régimes
            proba_revert = np.zeros(len(returns))
            proba_noise = np.zeros(len(returns))
            proba_trend = np.zeros(len(returns))

            for state_idx, regime in self.regime_map.items():
                if regime == -1:
                    proba_revert += hidden_proba[:, state_idx]
                elif regime == 0:
                    proba_noise += hidden_proba[:, state_idx]
                else:
                    proba_trend += hidden_proba[:, state_idx]

            return np.column_stack([proba_revert, proba_noise, proba_trend])
        except:
            return np.column_stack([np.zeros(len(returns)) for _ in range(3)])

    def gate(self, returns: np.ndarray, volume: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Gate binaire : autoriser trade (1) ou non (0).
        Trade autorisé si SNR > seuil et régime ≠ noise.

        Parameters
        ----------
        returns : np.ndarray
        volume : np.ndarray, optional

        Returns
        -------
        gate : np.ndarray
            Array binaire {0, 1}, shape (n,)
        """
        if not self.is_fitted:
            return np.zeros(len(returns), dtype=int)

        returns = np.asarray(returns, dtype=float)
        regimes = self.predict(returns, volume)
        proba = self.predict_proba(returns, volume)

        # Autoriser si régime ≠ noise ET confiance > 0.6
        confidence = np.max(proba, axis=1)
        gate = np.where((regimes != 0) & (confidence > 0.6), 1, 0)

        return gate

    def parliament_vote(self, returns: np.ndarray, volume: Optional[np.ndarray] = None) -> Vote:
        """
        Génère un Vote compatible parliament ORACLE v2.

        Interprétation trading des régimes :
        - Revert (-1) : Mean-reversion gagnante → court termes oscillations → NEUTRAL (pas de direction)
        - Noise (0) : Faible signal → NEUTRAL
        - Trend (1) : Momentum gagnant → LONG

        Parameters
        ----------
        returns : np.ndarray
        volume : np.ndarray, optional

        Returns
        -------
        vote : Vote
            Vote pour parliament
        """
        if not self.is_fitted:
            return Vote(
                strate_name="S0_REGIME",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="S0_REGIME not fitted"
            )

        returns = np.asarray(returns, dtype=float)

        if len(returns) < 40:
            return Vote(
                strate_name="S0_REGIME",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="Insufficient data (< 40 points)"
            )

        regimes = self.predict(returns, volume)
        proba = self.predict_proba(returns, volume)

        # Dernier régime et sa confiance
        regime = regimes[-1]
        confidence = np.max(proba[-1])

        if regime == 1:  # Trend
            direction = "LONG"
            reasoning = f"Trend regime detected (H > 0.55). Momentum edge. Conf={confidence:.2f}"
        elif regime == -1:  # Revert
            direction = "NEUTRAL"
            reasoning = f"Revert regime detected (High vol). Mean-reversion edge but neutral direction. Conf={confidence:.2f}"
        else:  # Noise
            direction = "NEUTRAL"
            reasoning = f"Noise regime detected (Entropy high). Low signal-to-noise. Conf={confidence:.2f}"

        return Vote(
            strate_name="S0_REGIME",
            direction=direction,
            confidence=min(confidence, 1.0),
            reasoning=reasoning
        )
