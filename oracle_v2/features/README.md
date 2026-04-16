# ORACLE v2 — Math Feature Engineering Modules

Pure mathematical feature engineering for algorithmic trading systems. All modules use only NumPy and SciPy — no external dependencies.

## Modules

### 1. entropy.py (241 lignes, 5 fonctions)
Information-theoretic features for regime detection and uncertainty quantification.

**Functions:**
- `shannon_entropy(returns, n_bins=10)` — Shannon entropy of discretized returns
- `rolling_entropy(returns, window=20, n_bins=10)` — Rolling entropy for regime changes
- `transfer_entropy(source, target, lag=1, n_bins=5)` — Directed info flow (volume→returns)
- `kolmogorov_proxy(data, window=100)` — Complexity proxy via gzip compression
- `snr_gate(signal, noise, window=50, percentile=75)` — Signal-to-Noise gate (no look-ahead)

**Trading Use:**
- High entropy = choppy/mean-reverting markets
- Rising entropy = regime uncertainty (reduce sizing)
- SNR gate = enable/disable entry signals based on quality

---

### 2. topology.py (252 lignes, 4 fonctions)
Topological and microstructure features for trend detection and clustering.

**Functions:**
- `rolling_hurst(series, window=100)` — Hurst exponent via R/S analysis (H > 0.5 = trending)
- `hawkes_intensity(events, mu=0.1, alpha=0.5, beta=1.0)` — Hawkes self-exciting model
- `rolling_hawkes(volume, window=50, threshold_std=1.5, ...)` — Volume spike clustering detection
- `persistent_homology_proxy(returns, window=20)` — Topological persistence (regime stability)

**Trading Use:**
- H > 0.6 = momentum strategies
- H < 0.4 = mean-reversion strategies
- High Hawkes intensity = volume clusters (momentum bursts)

---

### 3. extreme_value.py (245 lignes, 4 fonctions)
Tail risk quantification via Extreme Value Theory (EVT).

**Functions:**
- `fit_gpd(losses, threshold_pct=0.95)` — GPD fit to losses above threshold
- `evt_var(losses, confidence=0.99, threshold_pct=0.95)` — Value-at-Risk via EVT
- `expected_shortfall(losses, confidence=0.99, threshold_pct=0.95)` — CVaR/Expected Shortfall
- `tail_risk_score(returns, window=100, threshold_pct=0.95)` — Rolling tail risk [0-1]

**Trading Use:**
- Tail risk score > 0.7 = reduce sizing immediately
- EVT-based VaR = more accurate for fat-tailed assets
- Heavy tails (ξ > 0.1) = adjust models for extreme moves

---

### 4. graph_signal.py (201 lignes, 4 fonctions)
Cross-asset correlation and anomaly detection via Graph Signal Processing.

**Functions:**
- `compute_correlation_graph(returns_matrix, threshold=0.3)` — Sparse correlation matrix
- `gsp_laplacian(adj_matrix, normalized=True)` — Graph Laplacian for spectral analysis
- `gsp_residual(returns, adj_matrix)` — Signal unexplained by correlated neighbors
- `cross_asset_momentum_signal(returns_dict, window=20)` — Momentum weighted by correlations

**Trading Use:**
- High GSP residual = abnormal asset movement (alpha opportunity)
- Laplacian eigenvalues = asset clustering strength
- Cross-asset momentum = coordinate sizing across correlated pairs

---

## Key Design Principles

✓ **No Look-Ahead Bias:** All rolling calculations use strictly past data only
- `snr_gate` uses percentile from past window only
- Window indices always [i-window, i) not including current time

✓ **Pure Math:** NumPy + SciPy only, no ML dependencies

✓ **Docstrings:** Every function has clear trading interpretation

✓ **Microstructure Aware:** Hawkes models, self-exciting behavior, regime detection

✓ **Risk-Aware:** EVT for tail quantification, not parametric risk

---

## Requirements
```
numpy
scipy
```

## Import
```python
from oracle_v2.math import (
    # Entropy
    shannon_entropy, rolling_entropy, transfer_entropy, kolmogorov_proxy, snr_gate,
    # Topology  
    rolling_hurst, hawkes_intensity, persistent_homology_proxy, rolling_hawkes,
    # EVT
    fit_gpd, evt_var, expected_shortfall, tail_risk_score,
    # GSP
    gsp_laplacian, gsp_residual, compute_correlation_graph, cross_asset_momentum_signal
)
```

---

**Total:** 968 lignes de code, 17 fonctions mathématiques pures
