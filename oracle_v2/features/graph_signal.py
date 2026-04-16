"""
Graph Signal Processing (GSP) for cross-asset correlation and anomaly detection.

Modules:
- compute_correlation_graph: Build filtered correlation matrix between assets
- gsp_laplacian: Graph Laplacian for spectral analysis
- gsp_residual: Anomaly detection via signal residuals
- cross_asset_momentum_signal: Cross-asset momentum weighted by correlations
"""

import numpy as np
try:
    from scipy.linalg import eigh
except ImportError:
    pass  # scipy optional — install with: pip install scipy


def compute_correlation_graph(returns_matrix, threshold=0.3):
    """
    Compute filtered correlation matrix between assets.

    Correlations below |threshold| are zeroed out (sparsification).

    Parameters
    ----------
    returns_matrix : array-like
        Shape (n_times, n_assets). Each column is a single asset return series.
    threshold : float, default=0.3
        Absolute correlation threshold. |correlation| < threshold → 0.

    Returns
    -------
    array
        Sparse correlation matrix, shape (n_assets, n_assets).
        Diagonal = 1.0, off-diagonal = correlation or 0.

    Notes
    -----
    Trading use: Identify clusters of correlated assets.
                 High correlation = diversification risk.
    """
    returns_matrix = np.asarray(returns_matrix, dtype=float)

    # Compute full correlation
    corr = np.corrcoef(returns_matrix.T)

    # Threshold
    corr[np.abs(corr) < threshold] = 0

    # Ensure diagonal = 1
    np.fill_diagonal(corr, 1.0)

    return corr


def gsp_laplacian(adj_matrix, normalized=True):
    """
    Compute Graph Laplacian from adjacency/correlation matrix.

    L = D - A (combinatorial)
    L_norm = I - D^{-1/2} A D^{-1/2} (normalized)

    Parameters
    ----------
    adj_matrix : array-like
        Adjacency or correlation matrix, shape (n, n).
        Should be symmetric with non-negative entries.
    normalized : bool, default=True
        If True, compute normalized Laplacian. Otherwise, combinatorial.

    Returns
    -------
    array
        Laplacian matrix L, shape (n, n).

    Notes
    -----
    Eigenvalues of L capture graph structure:
    - λ_1 = 0 (trivial)
    - λ_2 = Fiedler value (algebraic connectivity)
    - Larger gaps in spectrum → more community structure

    Trading use: High algebraic connectivity = tightly coupled assets.
                 Use spectral clustering to find asset groups.
    """
    adj = np.asarray(adj_matrix, dtype=float)
    n = adj.shape[0]

    # Degree matrix
    degree = np.sum(np.abs(adj), axis=1)
    D = np.diag(degree)

    if normalized:
        # Normalized Laplacian
        # L_norm = I - D^{-1/2} A D^{-1/2}
        d_inv_sqrt = np.diag(1.0 / np.sqrt(degree + 1e-10))
        L = np.eye(n) - d_inv_sqrt @ adj @ d_inv_sqrt
    else:
        # Combinatorial Laplacian
        L = D - adj

    return L


def gsp_residual(returns, adj_matrix):
    """
    Compute GSP residuals: unexplained signal after filtering by graph structure.

    For each asset: e_i = x_i - h_i
    where h_i = Σ_j A_{ij} x_j / degree_i (average of neighbors)

    High residual = asset movement not explained by correlated neighbors = anomaly.

    Parameters
    ----------
    returns : array-like
        Return matrix, shape (n_times, n_assets).
    adj_matrix : array-like
        Adjacency/correlation matrix (e.g., from compute_correlation_graph).

    Returns
    -------
    array
        Residual matrix e, shape (n_times, n_assets).
        High values = abnormal movements (trading signal).

    Notes
    -----
    Trading use: Large residuals indicate assets moving independently from peers.
                 Can signal alpha opportunities or regime breaks.
    """
    returns = np.asarray(returns, dtype=float)
    adj = np.asarray(adj_matrix, dtype=float)

    n_times, n_assets = returns.shape

    # Degree-weighted average of neighbors
    degree = np.sum(np.abs(adj), axis=1)
    degree[degree == 0] = 1.0  # Avoid division by zero

    smoothed = np.zeros_like(returns)
    for t in range(n_times):
        for i in range(n_assets):
            neighbor_returns = adj[i, :] @ returns[t, :]
            smoothed[t, i] = neighbor_returns / degree[i]

    # Residual
    residual = returns - smoothed

    return residual


def cross_asset_momentum_signal(returns_dict, window=20):
    """
    Cross-asset momentum signal weighted by correlation structure.

    For each asset i, compute:
        m_i = Σ_j A_{ij} * momentum_j

    where momentum_j = returns over past window, and A is the correlation graph.

    Parameters
    ----------
    returns_dict : dict
        Dictionary mapping asset_name -> return_series (1D array).
        E.g., {'BTC': [...], 'ETH': [...]}
    window : int, default=20
        Lookback window for momentum computation.

    Returns
    -------
    dict
        Mapping asset_name -> cross_asset_momentum_signal (scalar per asset).

    Notes
    -----
    Trading use: Positive signal = asset has momentum AND correlated peers have momentum.
                 Use to coordinate position sizing across correlated assets.
    """
    assets = list(returns_dict.keys())
    n_assets = len(assets)

    if n_assets < 2:
        # Single asset, return self momentum
        return {asset: np.sum(returns_dict[asset][-window:]) for asset in assets}

    # Stack returns
    returns_matrix = np.column_stack([returns_dict[asset] for asset in assets])

    # Get latest window
    if len(returns_matrix) < window:
        window = len(returns_matrix)
    window_returns = returns_matrix[-window:, :]

    # Compute individual momentums
    momentums = np.sum(window_returns, axis=0)

    # Correlation graph
    corr = compute_correlation_graph(returns_matrix, threshold=0.2)

    # Cross-asset weighted momentum
    cross_asset_signal = corr @ momentums

    return {assets[i]: cross_asset_signal[i] for i in range(n_assets)}
