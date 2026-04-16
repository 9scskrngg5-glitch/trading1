"""
Strate 3 — Narrative XGBoost (S3) pour ORACLE v2.

Utilise XGBoost pour classifier les regimes de marché (LONG/SHORT/NEUTRAL)
en combinant des features Hawkes, momentum de volume et momentum de returns.
Intègre un fallback sklearn et support SHAP optionnel.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Union
import logging

from ml.base_model import OracleModel
from features.topology import hawkes_intensity

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

try:
    from sklearn.ensemble import GradientBoostingClassifier
    _HAS_SKLEARN = True
except ImportError:
    GradientBoostingClassifier = None
    _HAS_SKLEARN = False

logger = logging.getLogger("ORACLE.S3NarrativeXGB")


class S3NarrativeXGB(OracleModel):
    """
    Strate 3 — Narrative XGBoost Classifier.

    Prédit le régime de marché (-1: SHORT, 0: NEUTRAL, 1: LONG) en combinant:
    - Hawkes intensity (clustering de volume)
    - Momentum de volume
    - Momentum de returns
    - Features macro optionnelles (funding_rate, put_call_ratio, fear_greed)

    Utilise XGBoost avec early stopping si disponible, sinon fallback
    GradientBoostingClassifier de sklearn.
    """

    def __init__(self, name: str = 'S3_NarrativeXGB',
                 learning_rate: float = 0.1,
                 max_depth: int = 5,
                 n_estimators: int = 100,
                 early_stopping_rounds: int = 20):
        """
        Initialize S3 Narrative XGB.

        Parameters
        ----------
        name : str
            Nom du modèle
        learning_rate : float
            Learning rate for boosting
        max_depth : int
            Max depth des arbres
        n_estimators : int
            Nombre d'estimators
        early_stopping_rounds : int
            Nombre de rounds sans amélioration avant stopping
        """
        super().__init__(model_type='sklearn', name=name)

        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.n_estimators = n_estimators
        self.early_stopping_rounds = early_stopping_rounds

        self._hawkes_params = {'mu': 0.1, 'alpha': 0.5, 'beta': 1.0}
        self._feature_scaler = None

    def build_features(self, volume: np.ndarray, returns: np.ndarray,
                      funding_rate: Optional[np.ndarray] = None,
                      put_call_ratio: Optional[np.ndarray] = None,
                      fear_greed: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        Construire les features pour le modèle.

        Features:
        1. hawkes_intensity : clustering de volume
        2. volume_momentum_5d, volume_momentum_20d : élan du volume
        3. return_momentum_5d, return_momentum_20d : élan des returns
        4. volume_volatility : volatilité du volume
        5. return_volatility : volatilité des returns
        6. macro_funding_rate (optionnel)
        7. macro_put_call_ratio (optionnel)
        8. macro_fear_greed (optionnel)

        Parameters
        ----------
        volume : np.ndarray
            Serie de volume (N,)
        returns : np.ndarray
            Serie de returns (N,)
        funding_rate : np.ndarray, optional
            Taux de financement crypto (N,)
        put_call_ratio : np.ndarray, optional
            Ratio put/call options (N,)
        fear_greed : np.ndarray, optional
            Fear & Greed Index (0-100) (N,)

        Returns
        -------
        pd.DataFrame
            Features (N, n_features)
        """
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)
        n = len(volume)

        features = {}

        # 1. Hawkes Intensity
        volume_normalized = volume / (np.std(volume) + 1e-8)
        spike_threshold = np.mean(volume_normalized) + 1.5 * np.std(volume_normalized)
        spike_indices = np.where(volume_normalized > spike_threshold)[0]

        if len(spike_indices) > 1:
            hawkes_int = hawkes_intensity(spike_indices, **self._hawkes_params)
            hawkes_padded = np.full(n, np.nan)
            hawkes_padded[:len(hawkes_int)] = hawkes_int
            # Forward fill NaNs
            for i in range(1, n):
                if np.isnan(hawkes_padded[i]) and not np.isnan(hawkes_padded[i-1]):
                    hawkes_padded[i] = hawkes_padded[i-1]
            features['hawkes_intensity'] = hawkes_padded
        else:
            features['hawkes_intensity'] = np.full(n, 0.1)

        # 2. Volume Momentum
        features['volume_momentum_5d'] = self._compute_momentum(volume, window=5)
        features['volume_momentum_20d'] = self._compute_momentum(volume, window=20)

        # 3. Return Momentum
        features['return_momentum_5d'] = self._compute_momentum(returns, window=5)
        features['return_momentum_20d'] = self._compute_momentum(returns, window=20)

        # 4. Volatility Features
        features['volume_volatility'] = self._compute_volatility(volume, window=20)
        features['return_volatility'] = self._compute_volatility(returns, window=20)

        # 5. Macro Features (optionnels)
        if funding_rate is not None:
            funding_rate = np.asarray(funding_rate, dtype=float)
            features['macro_funding_rate'] = np.clip(funding_rate, -0.1, 0.1)

        if put_call_ratio is not None:
            put_call_ratio = np.asarray(put_call_ratio, dtype=float)
            features['macro_put_call_ratio'] = np.log1p(put_call_ratio)

        if fear_greed is not None:
            fear_greed = np.asarray(fear_greed, dtype=float)
            features['macro_fear_greed'] = (fear_greed - 50.0) / 50.0  # Normalize to [-1, 1]

        df = pd.DataFrame(features)

        # Handle NaNs
        df = df.fillna(method='bfill').fillna(method='ffill').fillna(0.0)

        return df

    def _compute_momentum(self, series: np.ndarray, window: int = 5) -> np.ndarray:
        """Momentum as rolling sum of returns."""
        series = np.asarray(series, dtype=float)
        momentum = np.full_like(series, np.nan)

        for i in range(window, len(series)):
            momentum[i] = np.sum(series[i-window:i])

        return np.nan_to_num(momentum, nan=0.0)

    def _compute_volatility(self, series: np.ndarray, window: int = 20) -> np.ndarray:
        """Rolling standard deviation."""
        series = np.asarray(series, dtype=float)
        volatility = np.full_like(series, np.nan)

        for i in range(window, len(series)):
            volatility[i] = np.std(series[i-window:i])

        return np.nan_to_num(volatility, nan=0.0)

    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: np.ndarray, **kwargs):
        """
        Entraîne le modèle XGBoost avec early stopping.

        Parameters
        ----------
        X : array-like or DataFrame
            Features (n_samples, n_features)
        y : array-like
            Labels (-1, 0, 1)
        **kwargs
            Arguments additionnels
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X = X.values
        else:
            X = np.asarray(X)
            if self.feature_names is None:
                self.feature_names = [f"feat_{i}" for i in range(X.shape[1])]

        y = np.asarray(y)

        # Encode labels: -1 -> 0, 0 -> 1, 1 -> 2
        y_encoded = (y + 1).astype(int)

        if HAS_XGBOOST:
            # Train-validation split (80-20)
            n_samples = len(X)
            n_train = int(0.8 * n_samples)

            indices = np.arange(n_samples)
            np.random.shuffle(indices)
            train_idx = indices[:n_train]
            val_idx = indices[n_train:]

            X_train = X[train_idx]
            y_train = y_encoded[train_idx]
            X_val = X[val_idx]
            y_val = y_encoded[val_idx]

            self.model = xgb.XGBClassifier(
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                n_estimators=self.n_estimators,
                early_stopping_rounds=self.early_stopping_rounds,
                eval_metric='logloss',
                random_state=42,
                tree_method='hist'
            )

            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )

            logger.info(f"S3 XGB trained: {self.model.best_iteration} iterations")
        else:
            # Fallback sklearn
            self.model = GradientBoostingClassifier(
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                n_estimators=self.n_estimators,
                random_state=42
            )
            self.model.fit(X, y_encoded)
            logger.info("S3 XGB (sklearn fallback) trained")

        self.is_fitted = True

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Prédit le régime (-1, 0, 1).

        Parameters
        ----------
        X : array-like or DataFrame
            Features

        Returns
        -------
        np.ndarray
            Prédictions (-1, 0, 1)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        if isinstance(X, pd.DataFrame):
            X = X.values

        X = np.asarray(X)
        y_encoded = self.model.predict(X)

        # Decode: 0 -> -1, 1 -> 0, 2 -> 1
        y_decoded = y_encoded - 1

        return y_decoded.astype(int)

    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Probabilités de classe.

        Parameters
        ----------
        X : array-like or DataFrame
            Features

        Returns
        -------
        np.ndarray
            Probabilités (n_samples, 3) pour classes [-1, 0, 1]
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        if isinstance(X, pd.DataFrame):
            X = X.values

        return self.model.predict_proba(X)

    def feature_importance_report(self) -> Dict[str, float]:
        """
        Retourne l'importance de chaque feature.

        Returns
        -------
        dict
            {feature_name: importance_value}
        """
        if not self.is_fitted or self.model is None:
            return {}

        importances = self.model.feature_importances_
        report = {}

        if self.feature_names:
            for fname, imp in zip(self.feature_names, importances):
                report[fname] = float(imp)

        return report

    def get_shap_values(self, X: Union[np.ndarray, pd.DataFrame]) -> Optional[np.ndarray]:
        """
        Calcule les SHAP values si disponibles.

        Parameters
        ----------
        X : array-like or DataFrame
            Features (petit sample pour SHAP)

        Returns
        -------
        np.ndarray or None
            SHAP values, ou None si shap non installé
        """
        if not HAS_SHAP:
            logger.warning("SHAP not installed, cannot compute SHAP values")
            return None

        if isinstance(X, pd.DataFrame):
            X = X.values

        try:
            if HAS_XGBOOST and isinstance(self.model, xgb.XGBClassifier):
                explainer = shap.TreeExplainer(self.model)
            else:
                # sklearn model
                explainer = shap.TreeExplainer(self.model)

            shap_values = explainer.shap_values(X)
            return shap_values
        except Exception as e:
            logger.warning(f"Failed to compute SHAP values: {e}")
            return None

    def parliament_vote(self, volume: np.ndarray, returns: np.ndarray,
                       **kwargs) -> Dict:
        """
        Vote du parlement (strate 3).

        Combine la prédiction avec la feature d'importance et le reasoning.

        Parameters
        ----------
        volume : np.ndarray
            Serie de volume
        returns : np.ndarray
            Serie de returns
        **kwargs
            Options additionnelles (funding_rate, put_call_ratio, fear_greed, etc.)

        Returns
        -------
        dict
            Vote avec structure:
            {
                'strate_name': 'S3_NarrativeXGB',
                'direction': 'LONG'|'SHORT'|'NEUTRAL',
                'confidence': float [0-1],
                'reasoning': str,
                'polymarket_signal': None
            }
        """
        # Build features
        features_df = self.build_features(volume, returns, **kwargs)

        # Predict
        pred = self.predict(features_df.values)[-1]  # Last prediction
        proba = self.predict_proba(features_df.values)[-1]  # Last proba

        # Direction
        direction_map = {-1: 'SHORT', 0: 'NEUTRAL', 1: 'LONG'}
        direction = direction_map[int(pred)]

        # Confidence
        confidence = float(np.max(proba))

        # Feature importance
        importance = self.feature_importance_report()
        top_feature = max(importance.items(), key=lambda x: x[1])[0] if importance else "n/a"

        reasoning = (
            f"S3 Narrative XGB signal: {direction} "
            f"(confidence: {confidence:.2%}, top_feature: {top_feature}). "
            f"Volume={volume[-1]:.0f}, Returns={returns[-1]:.4f}"
        )

        return {
            'strate_name': self.name,
            'direction': direction,
            'confidence': confidence,
            'reasoning': reasoning,
            'polymarket_signal': None
        }
