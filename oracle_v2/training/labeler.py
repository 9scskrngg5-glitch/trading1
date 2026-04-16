"""Labelers pour ORACLE v2 : ForwardReturnLabeler et TripleBarrierLabeler."""

import numpy as np
import pandas as pd


class ForwardReturnLabeler:
    """
    Labeleur basé sur le forward return à horizon fixe.
    Évite le look-ahead : label[i] = signe de returns[i+1:i+1+horizon].sum()
    """

    def label(self, returns, horizon=5, threshold_multiplier=0.5):
        """
        Génère des labels {-1, 0, 1} basés sur le forward return.

        Parameters
        ----------
        returns : array-like
            Returns journaliers ou des périodes.
        horizon : int, default 5
            Nombre de périodes à regarder vers l'avant.
        threshold_multiplier : float, default 0.5
            Multiplicateur du seuil : seuil = std(returns) * threshold_multiplier

        Returns
        -------
        labels : np.ndarray
            Array de labels {-1, 0, 1} de même longueur que returns.
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)

        # Calculer le seuil basé sur la volatilité
        volatility = np.nanstd(returns)
        threshold = volatility * threshold_multiplier

        labels = np.zeros(n, dtype=int)

        # Pour chaque point i, regarder forward_return[i] = sum(returns[i+1:i+1+horizon])
        for i in range(n):
            end_idx = min(i + 1 + horizon, n)
            forward_return = np.nansum(returns[i + 1 : end_idx])

            if forward_return > threshold:
                labels[i] = 1  # Signal haussier
            elif forward_return < -threshold:
                labels[i] = -1  # Signal baissier
            else:
                labels[i] = 0  # Signal neutre

        return labels

    def label_minsky_phases(self, ohlcv_df, window=60):
        """
        Détecte les phases Minsky via heuristiques prix/volume.

        Phases Minsky (1-5) :
        1 : Displacement (Accumulation) — prix montent, volume augmente lentement
        2 : Boom — prix accélèrent, volume élevé, soutien solide
        3 : Peak — prix à nouveau haut, volume se tarit, euphorie
        4 : Panic — prix dégringolent, volume explose, panique
        5 : Crash — prix chutent rapidement, volume retombent

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            OHLCV avec colonnes 'close', 'volume', 'high', 'low'
        window : int, default 60
            Fenêtre pour les calculs rolling

        Returns
        -------
        phases : np.ndarray
            Array de phases {1, 2, 3, 4, 5}
        """
        df = ohlcv_df.copy()
        n = len(df)
        phases = np.ones(n, dtype=int)

        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values

        # Rolling high sur window
        rolling_high = pd.Series(high).rolling(window=window, min_periods=1).max().values
        rolling_low = pd.Series(low).rolling(window=window, min_periods=1).min().values

        # Drawdown du high = distance du prix courant au high sur window
        drawdown = (rolling_high - close) / (rolling_high - rolling_low + 1e-8)

        # Volume ratio : volume récent vs moyenne
        rolling_volume_mean = pd.Series(volume).rolling(window=window, min_periods=1).mean().values
        volume_ratio = volume / (rolling_volume_mean + 1e-8)

        # Returns pour détecter la direction et l'accélération
        returns = np.diff(close, prepend=close[0]) / (close + 1e-8)
        rolling_returns = pd.Series(returns).rolling(window=10, min_periods=1).mean().values

        # Accélération du prix
        accel = np.diff(rolling_returns, prepend=rolling_returns[0])

        for i in range(window, n):
            if drawdown[i] > 0.15:
                # Prix bien en dessous du high : phase de panique/crash
                if volume_ratio[i] > 1.5:
                    phases[i] = 4  # Panic : prix bas, volume élevé
                else:
                    phases[i] = 5  # Crash : prix continuent à chuter
            elif drawdown[i] < 0.02 and volume_ratio[i] < 1.0:
                # Prix proche du high, volume faible : peak
                phases[i] = 3
            elif rolling_returns[i] > 0 and accel[i] > 0 and volume_ratio[i] > 1.2:
                # Retours positifs, accélération, volume élevé : boom
                phases[i] = 2
            elif rolling_returns[i] > 0 and volume_ratio[i] < 1.2:
                # Retours positifs, volume normal : displacement
                phases[i] = 1
            else:
                # Cas par défaut : continuation de la phase précédente
                phases[i] = phases[i - 1]

        return phases


class TripleBarrierLabeler:
    """
    Labeler inspiré de la méthode de López de Prado (Advances in Financial ML).
    Utilise trois barrières : stop-loss (SL), take-profit (TP), et timeout.
    """

    def label(self, prices, sl_pct=1.0, tp_pct=2.0, timeout_bars=10):
        """
        Génère des labels {-1, 0, 1} selon quelle barrière est touchée en premier.

        Parameters
        ----------
        prices : array-like
            Série de prix (close ou quelconque).
        sl_pct : float, default 1.0
            Stop-loss en pourcentage (e.g., 1.0 = -1%).
        tp_pct : float, default 2.0
            Take-profit en pourcentage (e.g., 2.0 = +2%).
        timeout_bars : int, default 10
            Nombre de barres avant timeout (sans toucher TP ou SL).

        Returns
        -------
        labels : np.ndarray
            Array de labels {-1, 0, 1} de même longueur que prices.
            +1 si TP touché en premier
            -1 si SL touché en premier
             0 si timeout atteint
        """
        prices = np.asarray(prices, dtype=float)
        n = len(prices)
        labels = np.zeros(n, dtype=int)

        sl_level = sl_pct / 100.0
        tp_level = tp_pct / 100.0

        for i in range(n):
            entry_price = prices[i]

            # Calculer les niveaux de SL et TP
            sl_price = entry_price * (1 - sl_level)
            tp_price = entry_price * (1 + tp_level)

            # Chercher quelle barrière est touchée en premier
            end_idx = min(i + 1 + timeout_bars, n)
            future_prices = prices[i + 1 : end_idx]

            label = 0  # Par défaut : timeout

            for j, price in enumerate(future_prices):
                if price >= tp_price:
                    label = 1  # TP touché
                    break
                elif price <= sl_price:
                    label = -1  # SL touché
                    break

            labels[i] = label

        return labels
