"""
Entropy-based features for algorithmic trading.

Modules:
- shannon_entropy: Classical Shannon entropy of discretized price movements
- rolling_entropy: Rolling window entropy to detect regime uncertainty
- transfer_entropy: Directional information flow from volume to returns
- kolmogorov_proxy: Approximate Kolmogorov complexity via gzip entropy
- snr_gate: Signal-to-Noise gate using past entropy percentile (no look-ahead)
"""

import numpy as np
try:
    from scipy.stats import entropy as scipy_entropy
except ImportError:
    # Fallback: numpy-based entropy
    import numpy as _np_ent
    def scipy_entropy(pk, base=2):
        pk = _np_ent.array(pk, dtype=float)
        s  = pk.sum()
        if s == 0:
            return 0.0
        pk = pk / s
        mask = pk > 0
        h = -float(_np_ent.sum(pk[mask] * _np_ent.log(pk[mask])))
        if base is not None:
            h /= float(_np_ent.log(base))
        return h
import zlib


def shannon_entropy(returns, n_bins=10):
    """
    Compute Shannon entropy of discretized returns.

    Parameters
    ----------
    returns : array-like
        Price returns series.
    n_bins : int, default=10
        Number of bins for discretization.

    Returns
    -------
    float
        Shannon entropy [0, log(n_bins)]. Higher = more disorder/uncertainty.
        Trading use: Regime uncertainty. High entropy = choppy/mean-reverting.
        Low entropy = trending.
    """
    returns = np.asarray(returns)
    hist, _ = np.histogram(returns, bins=n_bins)
    # Avoid log(0)
    hist = hist[hist > 0]
    return scipy_entropy(hist, base=2)


def rolling_entropy(returns, window=20, n_bins=10):
    """
    Rolling Shannon entropy to detect regime changes.

    Parameters
    ----------
    returns : array-like
        Price returns series, shape (N,).
    window : int, default=20
        Rolling window size.
    n_bins : int, default=10
        Number of discretization bins per window.

    Returns
    -------
    array
        Rolling entropy array, shape (N-window+1,). NaN for first window-1 values
        if you want zero-padding.

    Notes
    -----
    Trading use: Rising entropy = market becoming less predictable (reduce position size).
                 Falling entropy = market settling into a pattern (increase confidence).
    """
    returns = np.asarray(returns, dtype=float)
    n = len(returns)
    result = np.full(n, np.nan)

    for i in range(window - 1, n):
        window_data = returns[i - window + 1:i + 1]
        hist, _ = np.histogram(window_data, bins=n_bins)
        hist = hist[hist > 0]
        result[i] = scipy_entropy(hist, base=2)

    return result


def transfer_entropy(source, target, lag=1, n_bins=5):
    """
    Compute transfer entropy from source to target series.

    TE(X -> Y) = H(Y_t | Y_{t-lag}) - H(Y_t | Y_{t-lag}, X_{t-lag})

    Measures directed information flow: how much does lagged X reduce uncertainty in Y?

    Parameters
    ----------
    source : array-like
        Source time series (e.g., volume).
    target : array-like
        Target time series (e.g., returns).
    lag : int, default=1
        Lag to use for conditioning.
    n_bins : int, default=5
        Discretization bins.

    Returns
    -------
    float
        Transfer entropy >= 0. Higher = stronger causal influence of source on target.

    Notes
    -----
    Trading use: TE(volume -> returns) > threshold suggests volume has predictive power
                 for future returns.
    """
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)

    # Remove NaN
    mask = ~(np.isnan(source) | np.isnan(target))
    source = source[mask]
    target = target[mask]

    # Discretize
    source_binned = np.digitize(source, np.percentile(source, np.linspace(0, 100, n_bins + 1)))
    target_binned = np.digitize(target, np.percentile(target, np.linspace(0, 100, n_bins + 1)))

    # Build contingency tables
    n = len(source_binned) - lag
    if n <= 0:
        return 0.0

    # H(Y_t | Y_{t-lag})
    y_t = target_binned[lag:]
    y_t_lag = target_binned[:-lag]

    # H(Y_t | Y_{t-lag}, X_{t-lag})
    x_t_lag = source_binned[:-lag]

    # Compute conditional entropies via joint distributions
    unique_pairs_y = np.column_stack([y_t_lag, y_t])
    unique_triples = np.column_stack([y_t_lag, x_t_lag, y_t])

    _, counts_pair = np.unique(unique_pairs_y, axis=0, return_counts=True)
    _, counts_triple = np.unique(unique_triples, axis=0, return_counts=True)

    h_y_given_y_lag = scipy_entropy(counts_pair, base=2)
    h_y_given_y_lag_x_lag = scipy_entropy(counts_triple, base=2)

    te = h_y_given_y_lag - h_y_given_y_lag_x_lag
    return max(0.0, te)


def kolmogorov_proxy(data, window=100):
    """
    Approximate Kolmogorov complexity via gzip compression entropy.

    KC(x) ≈ log2(len(gzip(x))) / len(x)

    Higher KC = more random/incompressible (high market entropy).
    Lower KC = more structured/compressible (market has patterns).

    Parameters
    ----------
    data : array-like
        Time series data (floats).
    window : int, default=100
        Rolling window for computation.

    Returns
    -------
    array
        Rolling KC proxy, shape (N - window + 1,).

    Notes
    -----
    Trading use: KC > 0.5 suggests market is random/noise.
                 KC < 0.2 suggests exploitable structure.
    """
    data = np.asarray(data, dtype=float)
    n = len(data)
    result = np.full(n, np.nan)

    for i in range(window - 1, n):
        window_data = data[i - window + 1:i + 1]
        # Quantize to integers for gzip efficiency
        quantized = np.round((window_data - np.mean(window_data)) / (np.std(window_data) + 1e-8) * 100).astype(int)
        byte_str = quantized.tobytes()
        compressed = zlib.compress(byte_str, level=9)
        kc = np.log2(len(compressed) + 1) / (len(byte_str) + 1)
        result[i] = kc

    return result


def snr_gate(signal, noise, window=50, percentile=75):
    """
    Signal-to-Noise ratio gate using *past* percentile (no look-ahead bias).

    SNR = (signal_std / noise_std)

    Gate opens (True) when SNR > percentile_threshold(past).

    Parameters
    ----------
    signal : array-like
        Trading signal (e.g., returns, strategy PnL).
    noise : array-like
        Noise component (e.g., high-freq residuals, drawdowns).
    window : int, default=50
        Rolling window to compute percentile threshold.
    percentile : float, default=75
        Percentile of past SNR to use as threshold (0-100).

    Returns
    -------
    array
        Boolean gate array, shape (N,). True = signal quality above threshold.

    Notes
    -----
    No look-ahead: threshold at time t is computed only from [t-window, t).
    This prevents overfitting.

    Trading use: Use SNR gate to enable/disable entry signals. High SNR = trade.
                 Low SNR = hold/reduce sizing.
    """
    signal = np.asarray(signal, dtype=float)
    noise = np.asarray(noise, dtype=float)

    n = len(signal)
    snr_array = np.full(n, np.nan)
    gate = np.full(n, False, dtype=bool)

    # Compute SNR for each window
    for i in range(window, n):
        sig_std = np.std(signal[i - window:i]) + 1e-8
        noi_std = np.std(noise[i - window:i]) + 1e-8
        snr_array[i] = sig_std / noi_std

    # Gate based on past percentile
    for i in range(window, n):
        # Use only past SNR values (up to i-1)
        past_snr = snr_array[window:i]
        if len(past_snr) > 0:
            threshold = np.nanpercentile(past_snr, percentile)
            gate[i] = snr_array[i] > threshold

    return gate
