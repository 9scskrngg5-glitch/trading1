"""
S2 Minsky LSTM — Détection des 5 phases Minsky via réseau LSTM.

Phases Minsky (1-5) mappées sur signaux de trading :
1. Displacement → Accumulation, neutre (signal 0)
2. Boom → Croissance saine, long modéré (signal +0.6)
3. Euphoria → Peak, surexcitation, réduire (signal -0.3)
4. Distress → Début de panique, court fort (signal -0.7)
5. Panic/Crash → Vente de panique, court maximal (signal -0.9)

Fallback heuristique si PyTorch absent.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union
from dataclasses import dataclass

from ml.base_model import OracleModel, HAS_TORCH
from brain.parliament import Vote

# Import labeler avec gestion robuste
import sys
import os

_current_dir = os.path.dirname(os.path.abspath(__file__))
_training_path = os.path.join(_current_dir, '..', 'training')

if _training_path not in sys.path:
    sys.path.insert(0, _training_path)

from labeler import ForwardReturnLabeler

if HAS_TORCH:
    import torch
    import torch.nn as nn
    import torch.optim as optim


@dataclass
class MinskyPhase:
    """Détection phase Minsky."""
    phase: int      # 1-5
    signal: float   # [-1, 1]
    confidence: float


class MinskyLSTMNet(nn.Module if HAS_TORCH else object):
    """Architecture LSTM propre pour classification Minsky."""

    def __init__(self, input_size: int = 8, hidden_size: int = 64, n_layers: int = 2):
        if HAS_TORCH:
            super().__init__()
            self.hidden_size = hidden_size
            self.n_layers = n_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=n_layers,
                batch_first=True,
                dropout=0.3 if n_layers > 1 else 0.0
            )
            self.batch_norm = nn.BatchNorm1d(hidden_size)
            self.dropout = nn.Dropout(p=0.2)
            self.fc = nn.Linear(hidden_size, 5)  # 5 phases Minsky

    def forward(self, x):
        """x: (batch_size, seq_len, input_size)"""
        if not HAS_TORCH:
            raise RuntimeError("PyTorch not available")

        lstm_out, (h_n, c_n) = self.lstm(x)
        # Prendre le dernier output
        last_output = lstm_out[:, -1, :]
        norm_out = self.batch_norm(last_output)
        dropped = self.dropout(norm_out)
        logits = self.fc(dropped)
        return logits


class S2MinskyLSTM(OracleModel):
    """
    LSTM pour détection phases Minsky ORACLE v2.

    Entraîné sur OHLCV pour prédire la phase Minsky courante (1-5).
    Chaque phase a un signal de trading associé.

    Méthodes principales :
    - fit(close, volume, returns, y_phases=None, epochs=50)
    - predict(close, volume, returns) → signal float dans [-1, 1]
    - parliament_vote(close, volume, returns) → Vote pour parliament
    """

    def __init__(self, name: str = "S2_MinskyLSTM"):
        super().__init__(model_type='torch', name=name)
        self.lstm_net = None
        self.seq_len = 20  # Fenêtre lookback
        self.phase_signal_map = {
            1: 0.0,      # Displacement → neutre
            2: 0.6,      # Boom → long modéré
            3: -0.3,     # Euphoria → réduire
            4: -0.7,     # Distress → short fort
            5: -0.9,     # Panic → short maximal
        }
        self.feature_names = [
            'return', 'mom_10d', 'mom_30d', 'vol_10d', 'vol_30d',
            'volume_norm', 'vol_trend', 'drawdown_from_high'
        ]

    def build_features(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        returns: np.ndarray
    ) -> np.ndarray:
        """
        Construit les 8 features Minsky.

        Parameters
        ----------
        close : np.ndarray
            Prix fermeture, shape (n,)
        volume : np.ndarray
            Volume trading, shape (n,)
        returns : np.ndarray
            Rendements simples, shape (n,)

        Returns
        -------
        features : np.ndarray
            Features assemblées normalisées, shape (n, 8)
        """
        close = np.asarray(close, dtype=float)
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)
        n = len(close)

        # Feature 1 : return normalisé
        ret_norm = returns / (np.nanstd(returns) + 1e-8)

        # Feature 2 : momentum 10 jours
        mom_10 = pd.Series(close).diff(10).values
        mom_10_norm = mom_10 / (np.nanstd(mom_10) + 1e-8)

        # Feature 3 : momentum 30 jours
        mom_30 = pd.Series(close).diff(30).values
        mom_30_norm = mom_30 / (np.nanstd(mom_30) + 1e-8)

        # Feature 4 : volatilité 10 jours
        vol_10 = pd.Series(returns).rolling(window=10, min_periods=1).std().values
        vol_10_norm = vol_10 / (np.nanstd(vol_10) + 1e-8)

        # Feature 5 : volatilité 30 jours
        vol_30 = pd.Series(returns).rolling(window=30, min_periods=1).std().values
        vol_30_norm = vol_30 / (np.nanstd(vol_30) + 1e-8)

        # Feature 6 : volume normalisé (ratio à moyenne rolling)
        vol_mean = pd.Series(volume).rolling(window=20, min_periods=1).mean().values
        vol_norm = volume / (vol_mean + 1e-8)
        vol_norm_scaled = vol_norm / (np.nanstd(vol_norm) + 1e-8)

        # Feature 7 : trend volatilité (vol_30 - vol_10)
        vol_trend = vol_30 - vol_10
        vol_trend_norm = vol_trend / (np.nanstd(vol_trend) + 1e-8)

        # Feature 8 : drawdown depuis le high rolling 60j
        rolling_high = pd.Series(close).rolling(window=60, min_periods=1).max().values
        drawdown = (rolling_high - close) / (rolling_high + 1e-8)
        drawdown_norm = drawdown / (np.nanstd(drawdown) + 1e-8)

        features = np.column_stack([
            ret_norm, mom_10_norm, mom_30_norm, vol_10_norm, vol_30_norm,
            vol_norm_scaled, vol_trend_norm, drawdown_norm
        ])

        return np.nan_to_num(features, nan=0.0)

    def _create_sequences(self, X: np.ndarray, y: Optional[np.ndarray] = None):
        """
        Crée des séquences (seq_len, n_features) pour LSTM.

        Parameters
        ----------
        X : np.ndarray
            Features, shape (n, n_features)
        y : np.ndarray, optional
            Labels, shape (n,)

        Returns
        -------
        X_seq : np.ndarray
            Séquences, shape (n - seq_len + 1, seq_len, n_features)
        y_seq : np.ndarray or None
            Labels décalés
        """
        X_seq = []
        y_seq = []

        for i in range(len(X) - self.seq_len + 1):
            X_seq.append(X[i : i + self.seq_len])
            if y is not None:
                y_seq.append(y[i + self.seq_len - 1])

        X_seq = np.array(X_seq)
        y_seq = np.array(y_seq) if y is not None else None

        return X_seq, y_seq

    def fit(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        returns: np.ndarray,
        y_phases: Optional[np.ndarray] = None,
        epochs: int = 50
    ):
        """
        Entraîne le modèle LSTM.

        Parameters
        ----------
        close : np.ndarray
            Prix fermeture
        volume : np.ndarray
            Volume trading
        returns : np.ndarray
            Rendements
        y_phases : np.ndarray, optional
            Labels phases {1, 2, 3, 4, 5}. Si None, génère via ForwardReturnLabeler.
        epochs : int, default 50
            Nombre d'epochs
        """
        close = np.asarray(close, dtype=float)
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)

        # Générer labels si absent
        if y_phases is None:
            labeler = ForwardReturnLabeler()
            # Générer labels {-1, 0, 1} puis mapper sur phases
            y_labels = labeler.label(returns, horizon=5, threshold_multiplier=0.5)
            # Mapper : -1→5 (panic), 0→1 (displacement), 1→2 (boom)
            y_phases = np.where(y_labels == -1, 5, np.where(y_labels == 1, 2, 1))

        # Build features
        features = self.build_features(close, volume, returns)

        if not HAS_TORCH:
            # Fallback : assigner les phases directement
            self.is_fitted = True
            return

        # Créer séquences
        X_seq, y_seq = self._create_sequences(features, y_phases)

        if len(X_seq) < 10:
            self.is_fitted = True
            return

        # Initialiser le réseau
        self.lstm_net = MinskyLSTMNet(input_size=8, hidden_size=64, n_layers=2)
        optimizer = optim.Adam(self.lstm_net.parameters(), lr=1e-3)
        criterion = nn.CrossEntropyLoss()

        # Convertir en tensors
        X_tensor = torch.FloatTensor(X_seq)
        y_tensor = torch.LongTensor(y_seq - 1)  # phases 1-5 → indices 0-4

        # Entraîner
        self.lstm_net.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits = self.lstm_net(X_tensor)
            loss = criterion(logits, y_tensor)
            loss.backward()
            optimizer.step()

        self.lstm_net.eval()
        self.is_fitted = True

    def predict(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        returns: np.ndarray
    ) -> float:
        """
        Prédit le signal Minsky.

        Parameters
        ----------
        close : np.ndarray
        volume : np.ndarray
        returns : np.ndarray

        Returns
        -------
        signal : float
            Signal dans [-1, 1] selon la phase Minsky
        """
        if not self.is_fitted:
            return 0.0

        close = np.asarray(close, dtype=float)
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)

        if len(close) < self.seq_len:
            return 0.0

        features = self.build_features(close, volume, returns)

        if not HAS_TORCH or self.lstm_net is None:
            # Fallback heuristique
            return self._fallback_predict(close, volume, returns)

        # Prendre la dernière séquence
        X_seq = features[-self.seq_len:].reshape(1, self.seq_len, 8)
        X_tensor = torch.FloatTensor(X_seq)

        with torch.no_grad():
            logits = self.lstm_net(X_tensor)
            proba = torch.softmax(logits, dim=1)
            phase_idx = torch.argmax(proba, dim=1).item()
            phase = phase_idx + 1  # phases 1-5

        signal = self.phase_signal_map.get(phase, 0.0)
        return float(signal)

    def _fallback_predict(self, close: np.ndarray, volume: np.ndarray, returns: np.ndarray) -> float:
        """
        Fallback heuristique si PyTorch absent.
        Basé sur volatilité, momentum et drawdown.
        """
        close = np.asarray(close, dtype=float)
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)

        if len(close) < 30:
            return 0.0

        # Indicateurs simples
        recent_returns = returns[-20:].mean()
        vol_30 = np.std(returns[-30:])
        vol_10 = np.std(returns[-10:])
        vol_trend = vol_30 - vol_10

        rolling_high = np.max(close[-60:])
        drawdown = (rolling_high - close[-1]) / rolling_high

        # Heuristique
        if vol_trend > 0:  # Volatilité augmente
            if drawdown > 0.1:
                return -0.9  # Phase 5 : panic
            else:
                return -0.7  # Phase 4 : distress
        else:  # Volatilité baisse
            if recent_returns > vol_10:
                return 0.6  # Phase 2 : boom
            else:
                return 0.0  # Phase 1 : displacement

    def parliament_vote(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        returns: np.ndarray
    ) -> Vote:
        """
        Génère un Vote compatible parliament ORACLE v2.

        Parameters
        ----------
        close : np.ndarray
        volume : np.ndarray
        returns : np.ndarray

        Returns
        -------
        vote : Vote
            Vote pour parliament
        """
        if not self.is_fitted:
            return Vote(
                strate_name="S2_MINSKY",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="S2_MINSKY not fitted"
            )

        close = np.asarray(close, dtype=float)
        volume = np.asarray(volume, dtype=float)
        returns = np.asarray(returns, dtype=float)

        if len(close) < self.seq_len:
            return Vote(
                strate_name="S2_MINSKY",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"Insufficient data (< {self.seq_len} bars)"
            )

        signal = self.predict(close, volume, returns)

        # Mapper signal → direction
        if signal > 0.3:
            direction = "LONG"
        elif signal < -0.3:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # Confiance proportionnelle à |signal|
        confidence = min(abs(signal), 1.0)

        # Phase pour le reasoning
        features = self.build_features(close, volume, returns)
        if not HAS_TORCH or self.lstm_net is None:
            phase = "Heuristic"
        else:
            X_seq = features[-self.seq_len:].reshape(1, self.seq_len, 8)
            X_tensor = torch.FloatTensor(X_seq)
            with torch.no_grad():
                logits = self.lstm_net(X_tensor)
                proba = torch.softmax(logits, dim=1)
                phase_idx = torch.argmax(proba, dim=1).item()
                phase = phase_idx + 1

        phase_name = {
            1: "Displacement",
            2: "Boom",
            3: "Euphoria",
            4: "Distress",
            5: "Panic"
        }.get(phase, "Unknown")

        reasoning = (
            f"Minsky phase {phase} ({phase_name}). "
            f"Signal {signal:.2f}. Confidence {confidence:.2f}"
        )

        return Vote(
            strate_name="S2_MINSKY",
            direction=direction,
            confidence=confidence,
            reasoning=reasoning
        )
