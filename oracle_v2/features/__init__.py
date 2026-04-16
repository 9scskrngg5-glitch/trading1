"""ORACLE v2 — Feature engineering mathématique."""
from .entropy import shannon_entropy, rolling_entropy, transfer_entropy, kolmogorov_proxy, snr_gate
from .topology import rolling_hurst, hawkes_intensity, persistent_homology_proxy, rolling_hawkes
from .extreme_value import fit_gpd, evt_var, expected_shortfall, tail_risk_score
from .graph_signal import gsp_laplacian, gsp_residual, compute_correlation_graph, cross_asset_momentum_signal

__all__ = [
    # Entropy
    'shannon_entropy',
    'rolling_entropy',
    'transfer_entropy',
    'kolmogorov_proxy',
    'snr_gate',
    # Topology
    'rolling_hurst',
    'hawkes_intensity',
    'persistent_homology_proxy',
    'rolling_hawkes',
    # Extreme Value Theory
    'fit_gpd',
    'evt_var',
    'expected_shortfall',
    'tail_risk_score',
    # Graph Signal Processing
    'gsp_laplacian',
    'gsp_residual',
    'compute_correlation_graph',
    'cross_asset_momentum_signal',
]
