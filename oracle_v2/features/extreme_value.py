"""
Extreme Value Theory (EVT) for tail risk quantification.

Modules:
- fit_gpd: Fit Generalized Pareto Distribution to losses above threshold
- evt_var: Value-at-Risk via EVT
- expected_shortfall: Conditional Value-at-Risk (Expected Shortfall)
- tail_risk_score: Rolling tail risk indicator (0-1 scale)

References
----------
Embrechts, Klüppelberg & Mikosch (1997). "Modelling Extremal Events for Insurance and Finance."
"""

import numpy as np
HAS_SCIPY = False
try:
    from scipy.special import gamma
    from scipy.optimize import minimize
    HAS_SCIPY = True
except ImportError:
    pass  # scipy optional — install with: pip install scipy

def _minimize_fallback(func, x0, **kwargs):
    """Minimal Nelder-Mead substitute using numpy gradient-free search."""
    x = np.array(x0, dtype=float)
    best_val = func(x)
    for _ in range(500):
        step = np.random.randn(len(x)) * 0.05
        x_new = x + step
        val = func(x_new)
        if val < best_val:
            best_val = val
            x = x_new

    class _Result:
        success = True
        x = None
    r = _Result()
    r.x = x
    return r

if not HAS_SCIPY:
    minimize = _minimize_fallback


def fit_gpd(losses, threshold_pct=0.95):
    """
    Fit Generalized Pareto Distribution (GPD) to losses above threshold.

    GPD CDF: F(x) = 1 - (1 + ξ*x/σ)^(-1/ξ)  for ξ ≠ 0
             F(x) = 1 - exp(-x/σ)            for ξ = 0 (exponential)

    Parameters
    ----------
    losses : array-like
        Loss values (positive = losses, e.g., negative returns).
        Should contain extreme/tail values.
    threshold_pct : float, default=0.95
        Percentile threshold for tail extraction (0-100).
        E.g., 0.95 = fit GPD to top 5% worst losses.

    Returns
    -------
    xi : float
        Shape parameter. ξ > 0 = heavy-tailed, ξ = 0 = exponential, ξ < 0 = bounded.
    sigma : float
        Scale parameter (>0).
    threshold : float
        Absolute loss threshold value used.

    Notes
    -----
    Trading use: ξ > 0.1 indicates heavy tails (fat tail risk).
                 Use this to adjust position sizing and VaR estimates.
    """
    losses = np.asarray(losses, dtype=float)
    losses = losses[~np.isnan(losses)]

    # Extract tail
    threshold = np.percentile(losses, threshold_pct)
    tail_losses = losses[losses > threshold] - threshold

    if len(tail_losses) < 10:
        # Fallback to exponential approximation
        return 0.0, np.mean(tail_losses) + 1e-6, threshold

    # MLE for GPD
    def neg_loglik(params):
        xi, sigma = params
        if sigma <= 0 or (xi < 0 and sigma > -tail_losses.min() * xi):
            return 1e10

        if abs(xi) < 1e-6:
            # Exponential case
            return len(tail_losses) * np.log(sigma) + np.sum(tail_losses / sigma)
        else:
            # General GPD
            term = 1 + (xi / sigma) * tail_losses
            if np.any(term <= 0):
                return 1e10
            return len(tail_losses) * np.log(sigma) + (1 + 1/xi) * np.sum(np.log(term))

    # Initial guess: method of moments
    mean_tail = np.mean(tail_losses)
    var_tail = np.var(tail_losses)
    xi_init = 0.5 * (1 - mean_tail**2 / var_tail)
    sigma_init = 0.5 * mean_tail * (1 + xi_init)

    result = minimize(neg_loglik, [xi_init, sigma_init], method='Nelder-Mead',
                      options={'maxiter': 1000})

    if result.success:
        xi, sigma = result.x
    else:
        xi, sigma = xi_init, sigma_init

    return float(xi), float(abs(sigma)), float(threshold)


def evt_var(losses, confidence=0.99, threshold_pct=0.95):
    """
    Compute Value-at-Risk via Extreme Value Theory.

    VaR_EVT(p) = threshold + (σ/ξ) * ((N/n_tail) * (1-p))^(-ξ) - 1)

    where N = total samples, n_tail = samples above threshold.

    Parameters
    ----------
    losses : array-like
        Loss values (positive for losses, e.g., negative returns).
    confidence : float, default=0.99
        Confidence level (0-1). E.g., 0.99 = 99% VaR.
    threshold_pct : float, default=0.95
        Percentile for GPD threshold.

    Returns
    -------
    float
        VaR_EVT at given confidence level.
        Interpretation: with (1-confidence)*100% probability, loss exceeds this value.

    Notes
    -----
    Trading use: VaR(0.99) = position size limit for 99% confidence daily loss.
    """
    losses = np.asarray(losses, dtype=float)
    losses = losses[~np.isnan(losses)]

    xi, sigma, threshold = fit_gpd(losses, threshold_pct)

    n_total = len(losses)
    n_tail = np.sum(losses > threshold)

    if n_tail < 5:
        return np.percentile(losses, confidence * 100)

    p = 1 - confidence
    ratio = (n_total / n_tail) * p

    if xi < -0.01:
        # Bounded tail: risk capped
        var = threshold - (sigma / xi) * (ratio**(-xi) - 1)
    elif abs(xi) < 0.01:
        # Exponential tail
        var = threshold - sigma * np.log(ratio)
    else:
        # Heavy tail
        var = threshold + (sigma / xi) * (ratio**(-xi) - 1)

    return float(var)


def expected_shortfall(losses, confidence=0.99, threshold_pct=0.95):
    """
    Expected Shortfall (ES) / Conditional Value-at-Risk (CVaR) via EVT.

    ES(p) = E[Loss | Loss > VaR(p)]

    For GPD tail: ES ≈ VaR + (σ + ξ*VaR) / (1 - ξ)

    Parameters
    ----------
    losses : array-like
        Loss values.
    confidence : float, default=0.99
        Confidence level (0-1).
    threshold_pct : float, default=0.95
        Percentile for GPD threshold.

    Returns
    -------
    float
        Expected Shortfall: average loss conditional on exceeding VaR.

    Notes
    -----
    Trading use: ES is more coherent than VaR (sensitive to tail severity).
                 Use for position sizing and stress testing.
    """
    losses = np.asarray(losses, dtype=float)
    losses = losses[~np.isnan(losses)]

    xi, sigma, threshold = fit_gpd(losses, threshold_pct)
    var_evt = evt_var(losses, confidence, threshold_pct)

    if xi >= 1.0:
        # Unbounded ES (shouldn't happen in practice)
        return np.inf

    if abs(xi) < 1e-6:
        # Exponential tail
        es = var_evt + sigma
    else:
        es = var_evt + (sigma + xi * (var_evt - threshold)) / (1 - xi)

    return float(max(var_evt, es))


def tail_risk_score(returns, window=100, threshold_pct=0.95):
    """
    Rolling tail risk score (0 to 1) based on EVT shape parameter.

    score = max(0, min(1, (ξ - ξ_low) / (ξ_high - ξ_low)))

    where ξ_low = 0.05 (light tail) and ξ_high = 0.5 (heavy tail).

    Parameters
    ----------
    returns : array-like
        Return series (negative values = losses).
    window : int, default=100
        Rolling window for EVT fitting.
    threshold_pct : float, default=0.95
        Percentile threshold for GPD.

    Returns
    -------
    array
        Rolling tail risk score [0, 1], shape (N - window + 1,).
        score = 0: light tail (safe), score = 1: heavy tail (risky).

    Notes
    -----
    Trading use: score > 0.7 = reduce position size immediately.
                 score < 0.3 = can safely increase leverage if other conditions met.
    """
    returns = np.asarray(returns, dtype=float)
    n = len(returns)
    score = np.full(n, np.nan)

    for i in range(window, n):
        window_data = returns[i - window:i]

        # Convert returns to losses (take absolute value of negative returns)
        losses = -np.minimum(window_data, 0)
        losses = losses[losses > 0]

        if len(losses) < 10:
            score[i] = 0.0
            continue

        xi, _, _ = fit_gpd(losses, threshold_pct)

        # Normalize ξ to [0, 1]
        xi_low = 0.05  # Light tails
        xi_high = 0.5  # Heavy tails
        normalized = np.clip((xi - xi_low) / (xi_high - xi_low), 0, 1)
        score[i] = normalized

    return score
