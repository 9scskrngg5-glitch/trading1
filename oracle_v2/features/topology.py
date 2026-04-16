"""
Topological and market microstructure features.

Modules:
- rolling_hurst: Hurst exponent via Rescaled Range analysis (trending vs mean-reversion)
- hawkes_intensity: Hawkes process intensity for self-exciting events
- rolling_hawkes: Rolling Hawkes intensity detection for volume spikes
- persistent_homology_proxy: Lightweight topological persistence proxy
"""

import numpy as np
try:
    from scipy import optimize
except ImportError:
    pass  # scipy optional — install with: pip install scipy


def rolling_hurst(series, window=100):
    """
    Rescaled Range (R/S) analysis to estimate Hurst exponent.

    H = 0.5: Random walk (Brownian motion), no memory.
    H > 0.5: Trending, positive autocorrelation, momentum.
    H < 0.5: Mean-reverting, negative autocorrelation, anti-momentum.

    Parameters
    ----------
    series : array-like
        Price or return series.
    window : int, default=100
        Rolling window size for H estimation.

    Returns
    -------
    array
        Hurst exponent array, shape (N - window + 1,).
        Values typically in [0.0, 1.0], but can exceed if data is non-stationary.

    Notes
    -----
    Trading use: H > 0.6 = strong trend, use momentum strategies.
                 H < 0.4 = strong mean-reversion, use anti-momentum.
                 0.45 < H < 0.55 = indifferent (low edge).

    References
    ----------
    Hurst, H. E. (1951). "Long-term storage capacity of reservoirs."
    """
    series = np.asarray(series, dtype=float)
    n = len(series)
    hurst = np.full(n, np.nan)

    for end_idx in range(window, n + 1):
        window_data = series[end_idx - window:end_idx]

        # Mean-center
        mean = np.mean(window_data)
        y = np.cumsum(window_data - mean)

        # Compute R/S for different lags
        lags = np.arange(10, len(y) // 2, 10)
        if len(lags) < 2:
            continue

        rs_values = []
        for lag in lags:
            n_chunks = len(y) // lag
            if n_chunks < 1:
                continue

            r_values = []
            for chunk_idx in range(n_chunks):
                start = chunk_idx * lag
                end = start + lag
                chunk = y[start:end]
                if len(chunk) < 2:
                    continue

                mean_chunk = np.mean(chunk)
                y_centered = chunk - mean_chunk
                r = np.max(np.cumsum(y_centered)) - np.min(np.cumsum(y_centered))
                s = np.std(window_data[start:end], ddof=1)
                if s > 1e-10:
                    r_values.append(r / s)

            if r_values:
                rs_values.append(np.mean(r_values))

        # Log-log regression
        if len(rs_values) >= 2:
            log_lags = np.log(lags[:len(rs_values)])
            log_rs = np.log(np.array(rs_values) + 1e-10)
            h_est = np.polyfit(log_lags, log_rs, 1)[0]
            hurst[end_idx - 1] = np.clip(h_est, 0.0, 1.5)

    return hurst


def hawkes_intensity(events, mu=0.1, alpha=0.5, beta=1.0):
    """
    Hawkes process intensity: λ(t) = μ + Σ α*exp(-β*(t - t_i)) for t_i < t.

    Models self-exciting behavior: a large order can trigger follow-up orders.

    Parameters
    ----------
    events : array-like
        Times/indices of event occurrences (e.g., volume spikes).
        Shape (n_events,) with 0 <= events[i] < total_time.
    mu : float, default=0.1
        Baseline intensity (exogenous).
    alpha : float, default=0.5
        Magnitude of self-excitement (impact of each past event).
    beta : float, default=1.0
        Decay rate of self-excitement.

    Returns
    -------
    array
        Intensity at each time point: λ(t).
        Shape (max(events) + 1,) or (total_time,).

    Notes
    -----
    Trading use: High intensity = clusters of volume/trades.
                 Use to detect momentum bursts or forced liquidations.
    """
    events = np.asarray(events, dtype=int)
    if len(events) == 0:
        return np.array([])

    max_time = np.max(events) + 1
    intensity = np.full(max_time, mu, dtype=float)

    for t in range(max_time):
        past_events = events[events < t]
        if len(past_events) > 0:
            time_diffs = t - past_events
            intensity[t] += np.sum(alpha * np.exp(-beta * time_diffs))

    return intensity


def rolling_hawkes(volume, window=50, threshold_std=1.5, mu=0.1, alpha=0.5, beta=1.0):
    """
    Rolling Hawkes intensity detector for volume spike clusters.

    Detects when volume exhibits self-exciting behavior (Hawkes process),
    indicating potential momentum bursts or coordination.

    Parameters
    ----------
    volume : array-like
        Volume time series.
    window : int, default=50
        Rolling window size.
    threshold_std : float, default=1.5
        Threshold in std deviations above rolling mean to flag as event.
    mu : float, default=0.1
        Hawkes baseline intensity.
    alpha : float, default=0.5
        Self-excitement magnitude.
    beta : float, default=1.0
        Decay rate.

    Returns
    -------
    array
        Rolling Hawkes intensity, shape (N,).
        High values indicate self-exciting volume (clusters/momentum).

    Notes
    -----
    Trading use: Rolling Hawkes intensity > 0.5 = volume clustering detected.
                 Use with momentum strategies.
    """
    volume = np.asarray(volume, dtype=float)
    n = len(volume)
    rolling_intensity = np.full(n, np.nan)

    for i in range(window, n):
        window_vol = volume[i - window:i]

        # Detect spikes
        mean_vol = np.mean(window_vol)
        std_vol = np.std(window_vol) + 1e-8
        spike_threshold = mean_vol + threshold_std * std_vol

        spike_indices = np.where(window_vol >= spike_threshold)[0]

        # Fit Hawkes to spikes
        if len(spike_indices) > 1:
            hawkes_int = hawkes_intensity(spike_indices, mu, alpha, beta)
            rolling_intensity[i] = np.mean(hawkes_int)
        elif len(spike_indices) == 1:
            rolling_intensity[i] = mu + alpha
        else:
            rolling_intensity[i] = mu

    return rolling_intensity


def persistent_homology_proxy(returns, window=20):
    """
    Lightweight proxy for persistent homology (topological features).

    Uses maximin distance (Chebyshev distance in return space) instead of TDA.
    Detects topological "holes" or clusters in return distribution.

    Proxy Metric:
        PH = max_min_distance / std(returns)

    Higher PH = return distribution has more spread-out structure (regime change).
    Lower PH = returns clustered tightly (stable regime).

    Parameters
    ----------
    returns : array-like
        Return series.
    window : int, default=20
        Rolling window for computation.

    Returns
    -------
    array
        Topological persistence proxy, shape (N - window + 1,).

    Notes
    -----
    Trading use: Rising PH = market entering different regime (adjust models).
                 Falling PH = market stabilizing (increase confidence).

    Computation:
    For each window, find the maximum minimum distance between any two points
    in the window (using Chebyshev/L-infinity metric).
    """
    returns = np.asarray(returns, dtype=float)
    n = len(returns)
    ph_proxy = np.full(n, np.nan)

    for i in range(window - 1, n):
        window_data = returns[i - window + 1:i + 1].reshape(-1, 1)

        # Pairwise Chebyshev distances
        distances = np.abs(window_data - window_data.T)
        np.fill_diagonal(distances, np.inf)

        # Maximin: max of the minimum distances
        if distances.size > 0:
            min_distances = np.nanmin(distances, axis=1)
            max_min_dist = np.nanmax(min_distances)
            std_ret = np.std(window_data) + 1e-8
            ph_proxy[i] = max_min_dist / std_ret

    return ph_proxy
