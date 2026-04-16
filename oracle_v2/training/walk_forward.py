"""
Walk-Forward Validation for ML models.

Implements time-series cross-validation with forward-chaining folds,
labels generation without look-ahead bias, and comprehensive metrics computation.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Result of a walk-forward fold validation."""
    fold_idx: int
    train_idx: range
    test_idx: range
    train_dates: List
    test_dates: List
    predictions: np.ndarray  # shape (n_test,)
    actual_labels: np.ndarray  # shape (n_test,), {-1, 0, 1}
    sharpe: float
    win_rate: float
    max_dd: float
    total_return: float
    n_trades: int
    pnl_per_trade: List[float]


class WalkForwardValidator:
    """
    Time-series forward-chaining cross-validator.

    Parameters
    ----------
    train_window : int
        Number of samples for training window
    test_window : int
        Number of samples for test window
    step : int
        Step size for rolling forward
    """

    def __init__(self, train_window: int = 180, test_window: int = 30, step: int = 30):
        self.train_window = train_window
        self.test_window = test_window
        self.step = step

    def generate_folds(self, n: int) -> List[Tuple[range, range]]:
        """
        Generate train/test index pairs.

        Parameters
        ----------
        n : int
            Total number of samples

        Returns
        -------
        List[Tuple[range, range]]
            List of (train_slice, test_slice) tuples
        """
        folds = []
        start_train = 0

        while start_train + self.train_window + self.test_window <= n:
            train_end = start_train + self.train_window
            test_start = train_end
            test_end = test_start + self.test_window

            train_slice = range(start_train, train_end)
            test_slice = range(test_start, test_end)

            folds.append((train_slice, test_slice))
            start_train += self.step

        return folds

    def run(
        self,
        model,
        features: np.ndarray,
        returns: np.ndarray,
        dates: np.ndarray,
        horizon: int = 5,
    ) -> List[WalkForwardResult]:
        """
        Execute walk-forward validation.

        Parameters
        ----------
        model : object
            ML model with fit(X, y) and predict(X) methods
        features : np.ndarray
            Shape (n, n_features)
        returns : np.ndarray
            Shape (n,), daily returns
        dates : np.ndarray
            Shape (n,), datetime objects
        horizon : int
            Label forward horizon in days

        Returns
        -------
        List[WalkForwardResult]
            Validation results per fold
        """
        folds = self.generate_folds(len(features))
        results = []

        for fold_idx, (train_slice, test_slice) in enumerate(folds):
            logger.info(f"Processing fold {fold_idx + 1}/{len(folds)}")

            # Extract train/test
            X_train = features[train_slice]
            y_train = self._generate_labels(returns[train_slice], horizon=horizon)

            X_test = features[test_slice]
            y_test = self._generate_labels(returns[test_slice], horizon=horizon)

            # Fit model on training data
            try:
                model.fit(X_train, y_train)
            except Exception as e:
                logger.error(f"Fold {fold_idx} fit failed: {e}")
                continue

            # Predict on test data
            try:
                y_pred = model.predict(X_test)
            except Exception as e:
                logger.error(f"Fold {fold_idx} predict failed: {e}")
                continue

            # Compute metrics
            metrics = self._compute_metrics(y_test, y_pred, returns[test_slice])

            result = WalkForwardResult(
                fold_idx=fold_idx,
                train_idx=train_slice,
                test_idx=test_slice,
                train_dates=dates[train_slice].tolist(),
                test_dates=dates[test_slice].tolist(),
                predictions=y_pred,
                actual_labels=y_test,
                sharpe=metrics["sharpe"],
                win_rate=metrics["win_rate"],
                max_dd=metrics["max_dd"],
                total_return=metrics["total_return"],
                n_trades=metrics["n_trades"],
                pnl_per_trade=metrics["pnl_per_trade"],
            )
            results.append(result)

        return results

    def _generate_labels(self, returns: np.ndarray, horizon: int = 5) -> np.ndarray:
        """
        Generate forward-looking labels without look-ahead bias.

        Parameters
        ----------
        returns : np.ndarray
            Daily returns, shape (n,)
        horizon : int
            Cumulative forward returns window in days

        Returns
        -------
        np.ndarray
            Labels {-1, 0, 1}, shape (n - horizon,)
            -1: negative forward return
             0: near-zero forward return
             1: positive forward return
        """
        n = len(returns)
        labels = np.zeros(n - horizon, dtype=int)

        for i in range(n - horizon):
            # Cumulative return over next 'horizon' days
            forward_return = np.sum(returns[i + 1 : i + 1 + horizon])

            if forward_return > 0.001:  # threshold for "positive"
                labels[i] = 1
            elif forward_return < -0.001:  # threshold for "negative"
                labels[i] = -1
            else:
                labels[i] = 0

        return labels

    def _compute_metrics(
        self, y_true: np.ndarray, y_pred: np.ndarray, returns: np.ndarray
    ) -> Dict:
        """
        Compute comprehensive performance metrics.

        Parameters
        ----------
        y_true : np.ndarray
            Actual labels {-1, 0, 1}
        y_pred : np.ndarray
            Predicted labels (can be floats, will be thresholded)
        returns : np.ndarray
            Actual returns during test period

        Returns
        -------
        Dict
            Dictionary with sharpe, win_rate, max_dd, total_return, n_trades, pnl_per_trade
        """
        # Threshold predictions to {-1, 0, 1}
        y_pred_discrete = np.sign(np.round(y_pred))

        # Strategy PnL: multiply prediction sign by actual return
        strategy_returns = y_pred_discrete * returns

        # Win rate: trades that were profitable
        profitable_trades = (y_pred_discrete != 0) & (strategy_returns > 0)
        total_trades = np.sum(y_pred_discrete != 0)

        win_rate = (
            np.sum(profitable_trades) / max(total_trades, 1) if total_trades > 0 else 0.0
        )

        # Total return
        total_return = np.sum(strategy_returns)

        # Sharpe ratio (annualized, assuming 252 trading days)
        if len(strategy_returns) > 1 and np.std(strategy_returns) > 0:
            sharpe = (
                np.mean(strategy_returns)
                / np.std(strategy_returns)
                * np.sqrt(252)
            )
        else:
            sharpe = 0.0

        # Max drawdown
        cumulative = np.cumprod(1 + strategy_returns)
        running_max = np.maximum.accumulate(cumulative)
        dd = (cumulative - running_max) / running_max
        max_dd = -np.min(dd) if len(dd) > 0 else 0.0

        # PnL per trade
        pnl_per_trade = strategy_returns[y_pred_discrete != 0].tolist()

        return {
            "sharpe": sharpe,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "total_return": total_return,
            "n_trades": int(total_trades),
            "pnl_per_trade": pnl_per_trade,
        }

    @staticmethod
    def summary(results: List[WalkForwardResult]) -> Dict:
        """
        Aggregate statistics across all folds.

        Parameters
        ----------
        results : List[WalkForwardResult]
            Validation results from all folds

        Returns
        -------
        Dict
            Aggregated metrics with mean, std, min, max
        """
        if not results:
            return {}

        sharpes = [r.sharpe for r in results]
        win_rates = [r.win_rate for r in results]
        max_dds = [r.max_dd for r in results]
        total_returns = [r.total_return for r in results]
        n_trades_list = [r.n_trades for r in results]

        summary = {
            "n_folds": len(results),
            "sharpe": {
                "mean": float(np.mean(sharpes)),
                "std": float(np.std(sharpes)),
                "min": float(np.min(sharpes)),
                "max": float(np.max(sharpes)),
            },
            "win_rate": {
                "mean": float(np.mean(win_rates)),
                "std": float(np.std(win_rates)),
                "min": float(np.min(win_rates)),
                "max": float(np.max(win_rates)),
            },
            "max_dd": {
                "mean": float(np.mean(max_dds)),
                "std": float(np.std(max_dds)),
                "min": float(np.min(max_dds)),
                "max": float(np.max(max_dds)),
            },
            "total_return": {
                "mean": float(np.mean(total_returns)),
                "std": float(np.std(total_returns)),
                "min": float(np.min(total_returns)),
                "max": float(np.max(total_returns)),
            },
            "n_trades": {
                "mean": float(np.mean(n_trades_list)),
                "std": float(np.std(n_trades_list)),
                "total": int(np.sum(n_trades_list)),
            },
        }

        # Print formatted summary
        print("\n" + "=" * 70)
        print("WALK-FORWARD VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Folds: {summary['n_folds']}")
        print(f"\nSharpe Ratio (annualized):")
        print(f"  Mean:  {summary['sharpe']['mean']:.3f}")
        print(f"  Std:   {summary['sharpe']['std']:.3f}")
        print(f"  Range: [{summary['sharpe']['min']:.3f}, {summary['sharpe']['max']:.3f}]")
        print(f"\nWin Rate:")
        print(f"  Mean:  {summary['win_rate']['mean']:.1%}")
        print(f"  Std:   {summary['win_rate']['std']:.1%}")
        print(f"  Range: [{summary['win_rate']['min']:.1%}, {summary['win_rate']['max']:.1%}]")
        print(f"\nMax Drawdown:")
        print(f"  Mean:  {summary['max_dd']['mean']:.1%}")
        print(f"  Std:   {summary['max_dd']['std']:.1%}")
        print(f"  Range: [{summary['max_dd']['min']:.1%}, {summary['max_dd']['max']:.1%}]")
        print(f"\nTotal Return:")
        print(f"  Mean:  {summary['total_return']['mean']:.1%}")
        print(f"  Std:   {summary['total_return']['std']:.1%}")
        print(f"  Range: [{summary['total_return']['min']:.1%}, {summary['total_return']['max']:.1%}]")
        print(f"\nTrades:")
        print(f"  Mean per fold: {summary['n_trades']['mean']:.1f}")
        print(f"  Total:         {summary['n_trades']['total']}")
        print("=" * 70 + "\n")

        return summary

    @staticmethod
    def plot_equity_curve(
        results: List[WalkForwardResult],
        returns: np.ndarray,
        predictions_per_fold: Dict[int, np.ndarray],
    ) -> None:
        """
        Plot equity curve across folds.

        Parameters
        ----------
        results : List[WalkForwardResult]
            Validation results
        returns : np.ndarray
            Full return series
        predictions_per_fold : Dict[int, np.ndarray]
            Predictions indexed by fold
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available, using ASCII plot")
            WalkForwardValidator._plot_ascii_equity(results, returns)
            return

        fig, axes = plt.subplots(2, 1, figsize=(14, 8))

        # Aggregate returns per fold
        fold_returns = []
        fold_labels = []
        for result in results:
            test_returns = returns[list(result.test_idx)]
            fold_returns.append(np.cumprod(1 + test_returns))
            fold_labels.append(f"Fold {result.fold_idx}")

        # Plot equity curves
        ax = axes[0]
        for fold_idx, equity in enumerate(fold_returns):
            ax.plot(equity, label=fold_labels[fold_idx], alpha=0.7)
        ax.set_ylabel("Cumulative Equity")
        ax.set_title("Walk-Forward Equity Curves")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Plot Sharpe over folds
        ax = axes[1]
        sharpes = [r.sharpe for r in results]
        ax.bar(range(len(sharpes)), sharpes, color="steelblue", alpha=0.7)
        ax.axhline(y=np.mean(sharpes), color="red", linestyle="--", label="Mean")
        ax.set_xlabel("Fold")
        ax.set_ylabel("Sharpe Ratio")
        ax.set_title("Walk-Forward Sharpe Ratio")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        plt.show()

    @staticmethod
    def _plot_ascii_equity(results: List[WalkForwardResult], returns: np.ndarray) -> None:
        """Plot ASCII equity curve."""
        print("\n" + "=" * 70)
        print("EQUITY CURVES (ASCII)")
        print("=" * 70)

        for result in results:
            test_returns = returns[list(result.test_idx)]
            equity = np.cumprod(1 + test_returns)

            # Normalize to 0-20 range for ASCII display
            norm_equity = (equity - equity.min()) / (equity.max() - equity.min() + 1e-9) * 20

            print(f"\nFold {result.fold_idx} (Sharpe={result.sharpe:.2f}):")
            for val in norm_equity:
                bar = "*" * int(val)
                print(f"  {bar}")

    @staticmethod
    def is_statistically_significant(
        results: List[WalkForwardResult], n_bootstrap: int = 1000, alpha: float = 0.05
    ) -> Tuple[bool, float]:
        """
        Bootstrap test for statistical significance of Sharpe ratio.

        Parameters
        ----------
        results : List[WalkForwardResult]
            Validation results
        n_bootstrap : int
            Number of bootstrap resamples
        alpha : float
            Significance level

        Returns
        -------
        Tuple[bool, float]
            (is_significant, p_value)
        """
        sharpes = np.array([r.sharpe for r in results])
        mean_sharpe = np.mean(sharpes)

        # Bootstrap test: resample and check if 0 is in CI
        bootstrap_means = []
        for _ in range(n_bootstrap):
            resample = np.random.choice(sharpes, size=len(sharpes), replace=True)
            bootstrap_means.append(np.mean(resample))

        bootstrap_means = np.array(bootstrap_means)
        ci_lower = np.percentile(bootstrap_means, alpha / 2 * 100)
        ci_upper = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)

        is_significant = ci_lower > 0 or ci_upper < 0

        # Approximate p-value
        p_value = np.mean(np.abs(bootstrap_means - mean_sharpe) >= np.abs(mean_sharpe))

        print(f"\nBootstrap Significance Test (n={n_bootstrap}):")
        print(f"  Mean Sharpe: {mean_sharpe:.3f}")
        print(f"  CI [{alpha/2*100:.1f}%, {(1-alpha/2)*100:.1f}%]: [{ci_lower:.3f}, {ci_upper:.3f}]")
        print(f"  Significant: {is_significant}")
        print(f"  p-value: {p_value:.4f}\n")

        return is_significant, p_value
