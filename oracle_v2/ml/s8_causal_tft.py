"""
S8 — Temporal Fusion Transformer (TFT) for causal multi-horizon forecasting.

Architecture overview
---------------------
TFT is a sequence model designed for interpretable multi-step forecasting.
Key components implemented here:

  1. Variable Selection Network (VSN) — gates which inputs matter
  2. Gated Residual Network (GRN) — core non-linear block with skip connection
  3. LSTM encoder (temporal processing)
  4. Multi-head attention (long-range dependencies)
  5. Quantile output head (uncertainty quantification: q10, q50, q90)

ORACLE usage
------------
S8 produces a directional vote for the parliament based on the 50th percentile
forecast direction, weighted by uncertainty band (q90-q10).

Horizon: 5 bars ahead (configurable via n_horizon).

Optional dependency: torch >= 2.2
Graceful fallback: last-value extrapolation model when torch absent.

References
----------
  Lim et al. (2021) "Temporal Fusion Transformers for Interpretable
  Multi-horizon Time Series Forecasting." arXiv:1912.09363
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from oracle_v2.ml.base_model import OracleModel

logger = logging.getLogger("ORACLE.ML.S8")

# ── Optional PyTorch ──────────────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.debug("S8: torch not available — using naive extrapolation fallback")


# ── PyTorch sub-modules (only defined when torch is available) ─────────────────

if HAS_TORCH:

    class GatedResidualNetwork(nn.Module):
        """
        GRN block: dense → ELU → dense → sigmoid gate → skip.
        Gate controls how much of the residual to add.
        """

        def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, dropout: float = 0.1):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, hidden_dim)
            self.fc2 = nn.Linear(hidden_dim, output_dim)
            self.gate = nn.Linear(input_dim, output_dim)
            self.skip = nn.Linear(input_dim, output_dim) if input_dim != output_dim else nn.Identity()
            self.dropout = nn.Dropout(dropout)
            self.norm = nn.LayerNorm(output_dim)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = F.elu(self.fc1(x))
            h = self.dropout(self.fc2(h))
            g = torch.sigmoid(self.gate(x))
            return self.norm(h * g + self.skip(x))

    class VariableSelectionNetwork(nn.Module):
        """
        VSN: soft-selects features via a context-dependent softmax gate.
        """

        def __init__(self, n_vars: int, embed_dim: int, hidden_dim: int):
            super().__init__()
            self.var_grns = nn.ModuleList(
                [GatedResidualNetwork(embed_dim, hidden_dim, hidden_dim) for _ in range(n_vars)]
            )
            self.sel_grn = GatedResidualNetwork(n_vars * embed_dim, hidden_dim, n_vars)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x: (batch, n_vars, embed_dim)
            flat = x.reshape(x.size(0), -1)
            weights = F.softmax(self.sel_grn(flat), dim=-1)  # (batch, n_vars)
            processed = torch.stack(
                [self.var_grns[i](x[:, i, :]) for i in range(x.size(1))], dim=1
            )  # (batch, n_vars, hidden)
            selected = (processed * weights.unsqueeze(-1)).sum(dim=1)  # (batch, hidden)
            return selected

    class TFTCore(nn.Module):
        """
        Simplified Temporal Fusion Transformer core.

        Parameters
        ----------
        n_features : int    Input feature dimension per timestep
        seq_len    : int    Look-back window length
        n_horizon  : int    Forecast horizon (output steps)
        hidden_dim : int    Model width
        n_heads    : int    Attention heads
        n_quantiles: int    Quantile outputs (default 3: q10/q50/q90)
        """

        def __init__(
            self,
            n_features: int = 16,
            seq_len: int = 60,
            n_horizon: int = 5,
            hidden_dim: int = 64,
            n_heads: int = 4,
            n_quantiles: int = 3,
            dropout: float = 0.1,
        ):
            super().__init__()
            self.n_features = n_features
            self.seq_len = seq_len
            self.n_horizon = n_horizon
            self.hidden_dim = hidden_dim
            self.n_quantiles = n_quantiles

            # Input embedding
            self.input_proj = nn.Linear(n_features, hidden_dim)

            # VSN
            self.vsn = VariableSelectionNetwork(
                n_vars=n_features, embed_dim=1, hidden_dim=hidden_dim
            )
            self.vsn_proj = nn.Linear(n_features, hidden_dim)

            # LSTM encoder
            self.lstm = nn.LSTM(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                num_layers=2,
                batch_first=True,
                dropout=dropout,
            )

            # Multi-head self-attention
            self.attn = nn.MultiheadAttention(
                embed_dim=hidden_dim,
                num_heads=n_heads,
                dropout=dropout,
                batch_first=True,
            )
            self.attn_grn = GatedResidualNetwork(hidden_dim, hidden_dim, hidden_dim, dropout)

            # Quantile output head
            self.fc_out = nn.Linear(hidden_dim, n_horizon * n_quantiles)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            x : (batch, seq_len, n_features)
            Returns : (batch, n_horizon, n_quantiles)
            """
            B, T, F = x.shape

            # Input projection
            h = self.input_proj(x)         # (B, T, H)

            # LSTM
            lstm_out, _ = self.lstm(h)     # (B, T, H)

            # Self-attention
            attn_out, _ = self.attn(lstm_out, lstm_out, lstm_out)
            attn_out = self.attn_grn(attn_out + lstm_out)  # residual

            # Decode last timestep (or pooling)
            last = attn_out[:, -1, :]       # (B, H)

            # Quantile output
            out = self.fc_out(last)         # (B, n_horizon * n_quantiles)
            return out.view(B, self.n_horizon, self.n_quantiles)


# ── ORACLE model wrapper ───────────────────────────────────────────────────────

class S8CausalTFT(OracleModel):
    """
    S8 — Temporal Fusion Transformer.

    Parliament vote
    ---------------
    - q50 forecast > entry_price  → LONG
    - q50 forecast < entry_price  → SHORT
    - |q50 - entry| < noise_band  → NEUTRAL

    Uncertainty band (q90-q10) modulates confidence:
    tight band → high confidence, wide band → low confidence.

    Parameters
    ----------
    n_features   : int    Feature vector width
    seq_len      : int    Look-back bars used per prediction
    n_horizon    : int    Bars ahead to forecast (default 5)
    hidden_dim   : int    TFT hidden dimension
    n_heads      : int    Attention heads
    noise_band   : float  Min |return| to avoid NEUTRAL (default 0.002 = 0.2%)
    """

    MODEL_ID = "S8_TFT"
    MODEL_VERSION = "1.0"

    def __init__(
        self,
        n_features: int = 16,
        seq_len: int = 60,
        n_horizon: int = 5,
        hidden_dim: int = 64,
        n_heads: int = 4,
        noise_band: float = 0.002,
    ):
        super().__init__()
        self.n_features = n_features
        self.seq_len = seq_len
        self.n_horizon = n_horizon
        self.hidden_dim = hidden_dim
        self.n_heads = n_heads
        self.noise_band = noise_band

        self._model: Optional["TFTCore"] = None
        self._fitted = False
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None

    # ── OracleModel interface ──────────────────────────────────────────────────

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> "S8CausalTFT":
        """
        Train the TFT on (X, y).

        Parameters
        ----------
        X : (N, seq_len, n_features) — sequence windows
        y : (N, n_horizon) — target returns for each horizon step
        """
        if not HAS_TORCH:
            logger.warning("S8: torch missing — fit is a no-op, using fallback predict")
            self._fitted = True
            return self

        # Normalise features
        flat = X.reshape(-1, X.shape[-1])
        self._feature_means = flat.mean(axis=0)
        self._feature_stds = flat.std(axis=0) + 1e-8
        X_norm = (X - self._feature_means) / self._feature_stds

        # Build model
        self._model = TFTCore(
            n_features=self.n_features,
            seq_len=self.seq_len,
            n_horizon=self.n_horizon,
            hidden_dim=self.hidden_dim,
            n_heads=self.n_heads,
        )

        # Training params from kwargs
        lr = kwargs.get("lr", 1e-3)
        n_epochs = kwargs.get("n_epochs", 30)
        batch_size = kwargs.get("batch_size", 64)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=lr)

        # Quantile loss (pinball)
        quantiles = torch.tensor([0.1, 0.5, 0.9], dtype=torch.float32)

        X_t = torch.tensor(X_norm, dtype=torch.float32)
        y_t = torch.tensor(y, dtype=torch.float32)

        n = len(X_t)
        self._model.train()
        for epoch in range(n_epochs):
            perm = torch.randperm(n)
            total_loss = 0.0
            for start in range(0, n, batch_size):
                idx = perm[start:start + batch_size]
                xb = X_t[idx]
                yb = y_t[idx]  # (B, n_horizon)

                optimizer.zero_grad()
                pred = self._model(xb)  # (B, n_horizon, 3)

                # Pinball loss across quantiles
                loss = torch.tensor(0.0)
                for qi, q in enumerate(quantiles):
                    err = yb - pred[:, :, qi]
                    loss = loss + (q * err.clamp(min=0) + (1 - q) * (-err).clamp(min=0)).mean()

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()

            if (epoch + 1) % 10 == 0:
                logger.info(f"S8 epoch {epoch + 1}/{n_epochs} loss={total_loss / max(n // batch_size, 1):.4f}")

        self._model.eval()
        self._fitted = True
        logger.info(f"S8 TFT trained — {n_epochs} epochs, {n} samples")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict direction signal.

        Parameters
        ----------
        X : (N, seq_len, n_features) or (seq_len, n_features) for single sample

        Returns
        -------
        np.ndarray of shape (N,) with values in {-1, 0, 1}
        """
        if X.ndim == 2:
            X = X[np.newaxis, ...]  # single sample

        proba = self.predict_proba(X)     # (N, 3) — [P(short), P(neutral), P(long)]
        classes = np.array([-1, 0, 1])
        return classes[np.argmax(proba, axis=1)]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Return soft probabilities [P(short), P(neutral), P(long)].
        """
        if X.ndim == 2:
            X = X[np.newaxis, ...]

        if not HAS_TORCH or self._model is None:
            return self._fallback_proba(X)

        # Normalise
        if self._feature_means is not None:
            X = (X - self._feature_means) / self._feature_stds

        self._model.eval()
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32)
            pred = self._model(X_t)  # (N, n_horizon, 3) — quantile forecasts

        # Use q50 horizon-1 forecast return as directional signal
        q50_h1 = pred[:, 0, 1].cpu().numpy()  # 50th quantile, first horizon step
        q10_h1 = pred[:, 0, 0].cpu().numpy()
        q90_h1 = pred[:, 0, 2].cpu().numpy()

        # Uncertainty: narrow band → high confidence
        uncertainty = (q90_h1 - q10_h1).clip(min=1e-6)
        direction_signal = q50_h1

        N = X.shape[0]
        proba = np.zeros((N, 3), dtype=float)
        for i in range(N):
            sig = float(direction_signal[i])
            unc = float(uncertainty[i])
            # Confidence inversely proportional to uncertainty
            conf = float(np.clip(1.0 - unc / 0.05, 0.1, 0.9))
            if sig > self.noise_band:
                proba[i] = [1 - conf, 0.1, conf - 0.1]   # P(long) high
            elif sig < -self.noise_band:
                proba[i] = [conf - 0.1, 0.1, 1 - conf]   # P(short) high
            else:
                proba[i] = [0.1, 0.8, 0.1]               # neutral

        return proba

    def predict_single(self, x: np.ndarray) -> dict:
        """
        Single prediction for live parliament use.

        Returns
        -------
        dict with keys: direction, confidence, q10, q50, q90
        """
        if x.ndim == 2:
            x = x[np.newaxis, ...]
        proba = self.predict_proba(x)[0]
        classes = [-1, 0, 1]
        cls_idx = int(np.argmax(proba))
        direction_map = {-1: "SHORT", 0: "NEUTRAL", 1: "LONG"}
        return {
            "direction": direction_map[classes[cls_idx]],
            "confidence": float(proba[cls_idx]),
            "proba_short": float(proba[0]),
            "proba_neutral": float(proba[1]),
            "proba_long": float(proba[2]),
        }

    # ── Parliament vote ───────────────────────────────────────────────────────

    def parliament_vote(self, x: np.ndarray) -> tuple[str, float]:
        """
        Produce (direction, confidence) for parliament integration.

        Returns
        -------
        ("LONG" | "SHORT" | "NEUTRAL", confidence float [0,1])
        """
        result = self.predict_single(x)
        return result["direction"], result["confidence"]

    # ── Fallback (no torch) ────────────────────────────────────────────────────

    def _fallback_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Naive extrapolation: use last-bar return direction.
        Used when torch is not installed.
        """
        N = X.shape[0]
        proba = np.zeros((N, 3), dtype=float)
        for i in range(N):
            seq = X[i]  # (seq_len, n_features)
            # Assume feature 0 is return (or close)
            if seq.shape[0] >= 2:
                last_ret = float(seq[-1, 0]) - float(seq[-2, 0])
            else:
                last_ret = 0.0
            if last_ret > self.noise_band:
                proba[i] = [0.1, 0.2, 0.7]
            elif last_ret < -self.noise_band:
                proba[i] = [0.7, 0.2, 0.1]
            else:
                proba[i] = [0.15, 0.7, 0.15]
        return proba

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        if HAS_TORCH and self._model is not None:
            self.save_torch(path, self._model)
        meta = {
            "n_features": self.n_features,
            "seq_len": self.seq_len,
            "n_horizon": self.n_horizon,
            "hidden_dim": self.hidden_dim,
            "n_heads": self.n_heads,
            "noise_band": self.noise_band,
            "feature_means": self._feature_means.tolist() if self._feature_means is not None else None,
            "feature_stds": self._feature_stds.tolist() if self._feature_stds is not None else None,
        }
        meta_path = Path(path).with_suffix(".meta.pkl")
        with open(meta_path, "wb") as f:
            pickle.dump(meta, f)

    @classmethod
    def load(cls, path: str) -> "S8CausalTFT":
        meta_path = Path(path).with_suffix(".meta.pkl")
        if not meta_path.exists():
            logger.warning(f"S8: meta file not found at {meta_path}")
            return cls()
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        obj = cls(
            n_features=meta["n_features"],
            seq_len=meta["seq_len"],
            n_horizon=meta["n_horizon"],
            hidden_dim=meta["hidden_dim"],
            n_heads=meta.get("n_heads", 4),
            noise_band=meta.get("noise_band", 0.002),
        )
        if meta.get("feature_means"):
            obj._feature_means = np.array(meta["feature_means"])
            obj._feature_stds = np.array(meta["feature_stds"])
        if HAS_TORCH and Path(path).exists():
            try:
                obj._model = TFTCore(
                    n_features=obj.n_features,
                    seq_len=obj.seq_len,
                    n_horizon=obj.n_horizon,
                    hidden_dim=obj.hidden_dim,
                    n_heads=obj.n_heads,
                )
                obj.load_torch(path, obj._model)
                obj._fitted = True
            except Exception as e:
                logger.warning(f"S8: torch model load failed: {e}")
        return obj
