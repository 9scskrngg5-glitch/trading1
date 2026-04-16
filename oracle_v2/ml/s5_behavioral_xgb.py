"""
Strate 5 — Behavioral Contrarian XGBoost (S5) pour ORACLE v2.

Détecteur de biais comportementaux (Kahneman) pour signaux contrarian.
Identifie quand le marché est dominé par l'aversion aux pertes, le troupeau,
l'effet de disposition, etc., puis suggère des trades contraires.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Union
import logging

from ml.base_model import OracleModel

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    from sklearn.ensemble import GradientBoostingClassifier
    _HAS_SKLEARN = True
except ImportError:
    GradientBoostingClassifier = None
    _HAS_SKLEARN = False

logger = logging.getLogger("ORACLE.S5BehavioralXGB")


class S5BehavioralContrarianXGB(OracleModel):
    """
    Strate 5 — Behavioral Contrarian XGBoost.

    Classe les biais comportementaux du marché (Disposition Effect, Anchoring Bias,
    Herding Signal, Overconfidence, Loss Aversion) puis émet un signal CONTRARIAN:
    si tous les biais pointent vers l'achat, on VEND (et vice versa).

    Construit un signal invéré : quand la conviction comportementale est max,
    on fait le contraire.

    References
    ----------
    - Kahneman, D., & Tversky, A. (1979). "Prospect Theory: An Analysis of Decision under Risk"
    - Thaler, R. H. (1999). "Mental Accounting and Marketingside Behavior"
    """

    def __init__(self, name: str = 'S5_BehavioralContrarian',
                 learning_rate: float = 0.1,
                 max_depth: int = 5,
                 n_estimators: int = 100):
        """
        Initialize S5 Behavioral Contrarian XGB.

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
        """
        super().__init__(model_type='sklearn', name=name)

        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.n_estimators = n_estimators

    def build_features(self, returns: np.ndarray, volume: np.ndarray,
                      close: np.ndarray) -> pd.DataFrame:
        """
        Construire les features comportementales.

        Features:
        1. disposition_effect : ratio gains réalisés / pertes non réalisées
           = returns_positive_rolling / max_drawdown_rolling
        2. anchoring_bias : distance du prix au round number le plus proche
           Mesure la "collante" au prix rond (50000 pour BTC, 30000, etc.)
        3. herding_signal : correlation entre volume_spike et retour récent
           Quand le volume monte ET le marché monte = troupeau haussier
        4. overconfidence_proxy : ratio volatilité réalisée / volatilité implicite proxy
           = realized_vol_5d / ATR_5d (si realized > ATR, confiance excessive)
        5. loss_aversion_ratio : asymétrie returns positifs / négatifs rolling
           = sum(pos_returns) / abs(sum(neg_returns)) rolling 20j
        6. momentum_reversal_20j, momentum_reversal_60j
           Signal de retournement après momentum extremal

        Parameters
        ----------
        returns : np.ndarray
            Serie de returns (N,)
        volume : np.ndarray
            Serie de volume (N,)
        close : np.ndarray
            Serie de prix de clôture (N,)

        Returns
        -------
        pd.DataFrame
            Features (N, n_features)
        """
        returns = np.asarray(returns, dtype=float)
        volume = np.asarray(volume, dtype=float)
        close = np.asarray(close, dtype=float)
        n = len(returns)

        features = {}

        # 1. Disposition Effect
        # Gains réalisés vs pertes non réalisées
        pos_returns = np.maximum(returns, 0)
        neg_returns = np.minimum(returns, 0)
        features['disposition_effect'] = self._rolling_disposition(pos_returns, neg_returns, window=20)

        # 2. Anchoring Bias
        features['anchoring_bias'] = self._compute_anchoring_bias(close)

        # 3. Herding Signal
        # Correlation entre volume spike et momentum récent
        features['herding_signal'] = self._compute_herding_signal(volume, returns, window=20)

        # 4. Overconfidence Proxy
        features['overconfidence_proxy'] = self._compute_overconfidence(returns, window=5)

        # 5. Loss Aversion Ratio
        features['loss_aversion_ratio'] = self._rolling_loss_aversion(returns, window=20)

        # 6. Momentum Reversals
        features['momentum_reversal_20j'] = self._compute_momentum_reversal(returns, window=20)
        features['momentum_reversal_60j'] = self._compute_momentum_reversal(returns, window=60)

        df = pd.DataFrame(features)
        df = df.fillna(method='bfill').fillna(method='ffill').fillna(0.0)

        return df

    def _rolling_disposition(self, pos_returns: np.ndarray, neg_returns: np.ndarray,
                            window: int = 20) -> np.ndarray:
        """Disposition effect: ratio gains/pertes."""
        pos_returns = np.asarray(pos_returns, dtype=float)
        neg_returns = np.asarray(neg_returns, dtype=float)
        n = len(pos_returns)

        disposition = np.full(n, np.nan)

        for i in range(window, n):
            sum_pos = np.sum(pos_returns[i-window:i])
            sum_neg = np.abs(np.sum(neg_returns[i-window:i]))

            if sum_neg > 1e-8:
                disposition[i] = sum_pos / sum_neg
            else:
                disposition[i] = 0.0 if sum_pos < 1e-8 else 1e6

        return np.nan_to_num(disposition, nan=1.0)

    def _compute_anchoring_bias(self, close: np.ndarray) -> np.ndarray:
        """
        Anchoring bias: distance to nearest round number.

        Round numbers: 1000, 5000, 10000, 50000, etc.
        If price is close to round number, traders anchor to it.
        """
        close = np.asarray(close, dtype=float)
        n = len(close)
        anchoring = np.full(n, 0.0)

        for i in range(n):
            price = close[i]
            if price <= 0:
                continue

            # Find nearest round number (power of 10 scale)
            order = np.floor(np.log10(np.abs(price)))
            round_base = 10 ** order

            # Check multiples: 1x, 5x, 2x
            for mult in [1, 2, 5]:
                round_num = mult * round_base
                distance = np.abs(price - round_num) / price
                if distance < anchoring[i] or anchoring[i] == 0.0:
                    anchoring[i] = distance

        return np.minimum(anchoring, 1.0)  # Clip to [0, 1]

    def _compute_herding_signal(self, volume: np.ndarray, returns: np.ndarray,
                               window: int = 20) -> np.ndarray:
        """
        Herding signal: correlation between volume spike and recent momentum.
        High correlation = marché du troupeau (tous achetent/vendent ensemble).
        """
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)
        n = len(volume)

        herding = np.full(n, 0.0)

        for i in range(window, n):
            window_vol = volume[i-window:i]
            window_ret = returns[i-window:i]

            # Normalize
            vol_normalized = (window_vol - np.mean(window_vol)) / (np.std(window_vol) + 1e-8)
            ret_normalized = (window_ret - np.mean(window_ret)) / (np.std(window_ret) + 1e-8)

            # Correlation
            correlation = np.corrcoef(vol_normalized, ret_normalized)[0, 1]
            herding[i] = np.nan_to_num(correlation, nan=0.0, posinf=1.0, neginf=-1.0)

        return np.clip(herding, -1.0, 1.0)

    def _compute_overconfidence(self, returns: np.ndarray, window: int = 5) -> np.ndarray:
        """
        Overconfidence proxy: realized_volatility / expected_volatility.
        High ratio = traders are overconfident (realized vol > expected).
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)

        overconfidence = np.full(n, 1.0)

        for i in range(window, n):
            window_ret = returns[i-window:i]

            # Realized volatility
            realized_vol = np.std(window_ret)

            # Proxy for expected vol (ATR-like): mean absolute return
            atr_proxy = np.mean(np.abs(window_ret))

            if atr_proxy > 1e-8:
                overconfidence[i] = realized_vol / atr_proxy
            else:
                overconfidence[i] = 1.0

        return np.nan_to_num(overconfidence, nan=1.0)

    def _rolling_loss_aversion(self, returns: np.ndarray, window: int = 20) -> np.ndarray:
        """
        Loss aversion ratio: sum(positive_returns) / abs(sum(negative_returns)).
        High ratio = market rewards gains more than it penalizes losses (loss aversion active).
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)

        loss_aversion = np.full(n, 1.0)

        for i in range(window, n):
            window_ret = returns[i-window:i]

            pos_sum = np.sum(np.maximum(window_ret, 0))
            neg_sum = np.abs(np.sum(np.minimum(window_ret, 0)))

            if neg_sum > 1e-8:
                loss_aversion[i] = pos_sum / neg_sum
            else:
                loss_aversion[i] = 1.0 if pos_sum < 1e-8 else 100.0

        return np.nan_to_num(loss_aversion, nan=1.0)

    def _compute_momentum_reversal(self, returns: np.ndarray, window: int = 20) -> np.ndarray:
        """
        Momentum reversal: rolling momentum autocorrelation.
        High positive = momentum continues (trending). Low/negative = reversal (mean-reversion).
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)

        reversal = np.full(n, 0.0)

        for i in range(2 * window, n):
            # Momentum in first half
            mom_1 = np.sum(returns[i-2*window:i-window])
            # Momentum in second half
            mom_2 = np.sum(returns[i-window:i])

            # Correlation-like: do they move together?
            if mom_1 > 1e-8 and mom_2 > 1e-8:
                reversal[i] = np.sign(mom_1) * np.sign(mom_2)
            else:
                reversal[i] = 0.0

        return reversal

    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: np.ndarray, **kwargs):
        """
        Entraîne le modèle XGBoost.

        Parameters
        ----------
        X : array-like or DataFrame
            Features (n_samples, n_features)
        y : array-like
            Labels (-1 SHORT/contrarian, 0 NEUTRAL, 1 LONG/contrarian)
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
        y_encoded = (y + 1).astype(int)

        if HAS_XGBOOST:
            self.model = xgb.XGBClassifier(
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                n_estimators=self.n_estimators,
                random_state=42,
                tree_method='hist'
            )
            self.model.fit(X, y_encoded)
        else:
            self.model = GradientBoostingClassifier(
                learning_rate=self.learning_rate,
                max_depth=self.max_depth,
                n_estimators=self.n_estimators,
                random_state=42
            )
            self.model.fit(X, y_encoded)

        logger.info(f"S5 Behavioral XGB trained")
        self.is_fitted = True

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Prédit le signal (-1 SHORT, 0 NEUTRAL, 1 LONG).

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

    def parliament_vote(self, returns: np.ndarray, volume: np.ndarray,
                       close: np.ndarray) -> Dict:
        """
        Vote du parlement (strate 5) — Signal contrarian.

        Si la majorité des biais comportementaux pointent vers l'achat (LONG),
        on émet un signal de VENTE (SHORT). Et inversement.

        Parameters
        ----------
        returns : np.ndarray
            Serie de returns
        volume : np.ndarray
            Serie de volume
        close : np.ndarray
            Serie de prix

        Returns
        -------
        dict
            Vote avec structure:
            {
                'strate_name': 'S5_BehavioralContrarian',
                'direction': 'LONG'|'SHORT'|'NEUTRAL',
                'confidence': float [0-1],
                'reasoning': str,
                'polymarket_signal': None
            }
        """
        # Build behavioral features
        features_df = self.build_features(returns, volume, close)

        # Predict behavioral regime
        pred = self.predict(features_df.values)[-1]
        proba = self.predict_proba(features_df.values)[-1]

        # CONTRARIAN: inverse la prédiction
        # Si pred=1 (market says LONG due to biases), on dit SHORT
        contrarian_pred = -pred

        direction_map = {-1: 'SHORT', 0: 'NEUTRAL', 1: 'LONG'}
        direction = direction_map[int(contrarian_pred)]

        # Confidence based on probability
        confidence = float(np.max(proba))

        # Behavioral features report
        features_dict = features_df.iloc[-1].to_dict()
        top_bias = max(features_dict.items(), key=lambda x: abs(x[1]))[0]

        reasoning = (
            f"S5 Behavioral Contrarian signal: {direction} "
            f"(contrarian confidence: {confidence:.2%}, dominant_bias: {top_bias}). "
            f"Market biases detected — recommending OPPOSITE direction. "
            f"Latest close: {close[-1]:.2f}"
        )

        return {
            'strate_name': self.name,
            'direction': direction,
            'confidence': confidence,
            'reasoning': reasoning,
            'polymarket_signal': None
        }
