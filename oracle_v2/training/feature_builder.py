"""Feature builder pour ORACLE v2 : assemble toutes les features."""

import numpy as np
import pandas as pd
# from math import entropy  # replaced below


class FeatureBuilder:
    """
    Construit un ensemble complet de features pour l'entraînement du modèle ORACLE v2.
    Inclut technical indicators, statistiques et mesures avancées.
    """

    def build(self, ohlcv_df, macro_df=None):
        """
        Assemble TOUTES les features à partir du DataFrame OHLCV.

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            DataFrame avec colonnes 'open', 'high', 'low', 'close', 'volume'.
        macro_df : pd.DataFrame, optional
            DataFrame macroéconomique avec colonne 'funding_rate' (ou autre).

        Returns
        -------
        features_df : pd.DataFrame
            DataFrame avec toutes les features construites.
        """
        df = ohlcv_df.copy()
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values

        # Initialiser le DataFrame des features
        features = pd.DataFrame(index=df.index)

        # === Returns et log-returns ===
        features['returns'] = pd.Series(close).pct_change()
        features['log_returns'] = np.log(close / np.roll(close, 1))
        features['log_returns'].iloc[0] = 0

        # === Volatilité (rolling) ===
        features['volatility_10'] = features['returns'].rolling(window=10, min_periods=1).std()
        features['volatility_20'] = features['returns'].rolling(window=20, min_periods=1).std()
        features['volatility_60'] = features['returns'].rolling(window=60, min_periods=1).std()

        # === RSI(14) ===
        features['rsi_14'] = self._rsi(close, period=14)

        # === MACD(12, 26, 9) ===
        macd, signal, hist = self._macd(close, fast=12, slow=26, smooth=9)
        features['macd'] = macd
        features['macd_signal'] = signal
        features['macd_histogram'] = hist

        # === Bollinger Bands position ===
        bb_position = self._bollinger_position(close, period=20, num_std=2)
        features['bollinger_position'] = bb_position

        # === Volume ratio ===
        features['volume_ratio'] = volume / (pd.Series(volume).rolling(window=20, min_periods=1).mean() + 1e-8)

        # === ATR (Average True Range) ===
        features['atr'] = self._atr(high, low, close, period=14)

        # === Momentum sur différents horizons ===
        features['momentum_3'] = close - np.roll(close, 3)
        features['momentum_7'] = close - np.roll(close, 7)
        features['momentum_14'] = close - np.roll(close, 14)
        features['momentum_30'] = close - np.roll(close, 30)

        # === Funding rate (si fourni) ===
        if macro_df is not None and 'funding_rate' in macro_df.columns:
            features['funding_rate'] = macro_df['funding_rate'].values
        else:
            features['funding_rate'] = 0.0

        # === Rolling entropy ===
        features['rolling_entropy'] = self._rolling_entropy(close, window=20)

        # === Rolling Hurst exponent ===
        features['rolling_hurst'] = self._rolling_hurst(close, window=50)

        # === Hawkes intensity ===
        features['hawkes_intensity'] = self._hawkes_intensity(volume, window=30)

        # === Tail risk score ===
        features['tail_risk_score'] = self._tail_risk_score(features['returns'], window=60)

        return features

    def normalize(self, features_df, method='zscore', window=252):
        """
        Normalise les features via rolling zscore ou min-max, sans look-ahead.

        Parameters
        ----------
        features_df : pd.DataFrame
            DataFrame des features.
        method : str, default 'zscore'
            'zscore' pour standardisation rolling, 'minmax' pour normalisation 0-1.
        window : int, default 252
            Fenêtre rolling pour la normalisation.

        Returns
        -------
        normalized_df : pd.DataFrame
            Features normalisées.
        """
        normalized = features_df.copy()

        for col in normalized.columns:
            if normalized[col].dtype in [np.float64, np.float32]:
                if method == 'zscore':
                    rolling_mean = normalized[col].rolling(window=window, min_periods=1).mean()
                    rolling_std = normalized[col].rolling(window=window, min_periods=1).std()
                    normalized[col] = (normalized[col] - rolling_mean) / (rolling_std + 1e-8)
                elif method == 'minmax':
                    rolling_min = normalized[col].rolling(window=window, min_periods=1).min()
                    rolling_max = normalized[col].rolling(window=window, min_periods=1).max()
                    normalized[col] = (normalized[col] - rolling_min) / (rolling_max - rolling_min + 1e-8)

        return normalized

    @staticmethod
    def _rsi(prices, period=14):
        """Relative Strength Index."""
        prices = pd.Series(prices)
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
        rs = gain / (loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))
        return rsi.values

    @staticmethod
    def _macd(prices, fast=12, slow=26, smooth=9):
        """MACD (Moving Average Convergence Divergence)."""
        prices = pd.Series(prices)
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=smooth, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.values, signal_line.values, histogram.values

    @staticmethod
    def _bollinger_position(prices, period=20, num_std=2):
        """Position du prix dans les bandes de Bollinger (0-1)."""
        prices = pd.Series(prices)
        sma = prices.rolling(window=period, min_periods=1).mean()
        std = prices.rolling(window=period, min_periods=1).std()
        upper_band = sma + num_std * std
        lower_band = sma - num_std * std
        position = (prices - lower_band) / (upper_band - lower_band + 1e-8)
        position = position.clip(0, 1)
        return position.values

    @staticmethod
    def _atr(high, low, close, period=14):
        """Average True Range."""
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period, min_periods=1).mean()
        return atr.values

    @staticmethod
    def _rolling_entropy(prices, window=20):
        """Entropie Shannon rolling des returns."""
        prices = pd.Series(prices)
        returns = prices.pct_change().dropna()

        entropies = []
        for i in range(len(prices)):
            start_idx = max(0, i - window + 1)
            window_returns = returns.iloc[start_idx:i]

            if len(window_returns) == 0:
                entropies.append(0.0)
                continue

            # Discrétiser les returns en bins pour calculer l'entropie
            counts, _ = np.histogram(window_returns, bins=10)
            counts = counts[counts > 0]
            probs = counts / counts.sum()

            try:
                ent = entropy(probs)
            except:
                ent = 0.0

            entropies.append(ent)

        return np.array(entropies)

    @staticmethod
    def _rolling_hurst(prices, window=50):
        """
        Exposant de Hurst rolling (estimation simple).
        Hurst > 0.5 : momentum, Hurst < 0.5 : mean reversion, Hurst = 0.5 : random walk.
        """
        prices = pd.Series(prices)
        hurst_values = []

        for i in range(len(prices)):
            start_idx = max(0, i - window + 1)
            window_prices = prices.iloc[start_idx : i + 1]

            if len(window_prices) < 10:
                hurst_values.append(0.5)
                continue

            # Calcul simplifié de Hurst via rescaled range analysis
            returns = window_prices.pct_change().dropna().values
            mean_return = np.mean(returns)
            Y = np.cumsum(returns - mean_return)
            R = np.max(Y) - np.min(Y)
            S = np.std(returns, ddof=1)

            if S == 0:
                hurst = 0.5
            else:
                hurst = np.log(R / S) / np.log(len(returns) ** 0.5)
                hurst = max(0.0, min(1.0, hurst))  # Clamp [0, 1]

            hurst_values.append(hurst)

        return np.array(hurst_values)

    @staticmethod
    def _hawkes_intensity(volumes, window=30):
        """
        Intensité de Hawkes approximée : mesure du clustering temporel des gros volumes.
        Volume élevé suivi de volume élevé -> intensité élevée.
        """
        volumes = pd.Series(volumes)
        mean_vol = volumes.rolling(window=window, min_periods=1).mean()
        std_vol = volumes.rolling(window=window, min_periods=1).std()

        # Standardiser les volumes
        standardized = (volumes - mean_vol) / (std_vol + 1e-8)
        standardized = standardized.clip(-3, 3)

        # Autocorrélation simplifée (clustering)
        hawkes = []
        for i in range(len(volumes)):
            start_idx = max(0, i - window + 1)
            window_std = standardized.iloc[start_idx : i + 1]

            if len(window_std) < 2:
                hawkes.append(0.0)
                continue

            # Somme des produits successifs (autocorrélation lag-1)
            auto_corr = np.sum(window_std.values[:-1] * window_std.values[1:]) / len(window_std)
            hawkes.append(max(0.0, auto_corr))

        return np.array(hawkes)

    @staticmethod
    def _tail_risk_score(returns, window=60):
        """
        Score de risque de queue basé sur l'estimation de la Value at Risk 5% et 1%.
        Score élevé = queues épaisses = risque de perte extrême.
        """
        returns = pd.Series(returns)
        tail_scores = []

        for i in range(len(returns)):
            start_idx = max(0, i - window + 1)
            window_returns = returns.iloc[start_idx : i + 1]

            if len(window_returns) < 10:
                tail_scores.append(0.0)
                continue

            # VaR 5% et 1% (percentiles)
            var_5 = np.percentile(window_returns, 5)
            var_1 = np.percentile(window_returns, 1)

            # Ratio des queues : mesure l'asymétrie des pertes
            mean_return = np.mean(window_returns)
            tail_ratio = (mean_return - var_1) / (mean_return - var_5 + 1e-8)

            # Skewness comme composante du risque de queue
            skew = (window_returns - mean_return).pow(3).mean() / (window_returns.std() ** 3 + 1e-8)

            # Score final : combinaison tail_ratio et skewness
            tail_score = max(0.0, tail_ratio * (1 + skew))

            tail_scores.append(tail_score)

        return np.array(tail_scores)
