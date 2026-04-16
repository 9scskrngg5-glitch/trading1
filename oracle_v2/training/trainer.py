"""
ML Trainer — Orchestrates training of all ORACLE v2 strategies.

Handles data loading, strategy-specific training, validation, and model persistence.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
import pickle
import json
from pathlib import Path

from .walk_forward import WalkForwardValidator, WalkForwardResult

logger = logging.getLogger(__name__)


class MLTrainer:
    """
    Trains all ORACLE v2 ML strategies (S0, S2, S3, S5, S7, S11).

    Parameters
    ----------
    oracle_config : dict
        Configuration dict with strategy parameters
    data_dir : str
        Directory for raw data
    models_dir : str
        Directory for saving/loading trained models
    """

    STRATE_IDS = ["S0", "S2", "S3", "S5", "S7"]

    def __init__(
        self,
        oracle_config: Dict,
        data_dir: str = "data/",
        models_dir: str = "models/",
    ):
        self.config = oracle_config
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)

        # Create directories if missing
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"MLTrainer initialized: data_dir={self.data_dir}, models_dir={self.models_dir}")

    def load_data(
        self,
        symbols: List[str] = None,
        period: str = "4y",
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data for symbols.

        Parameters
        ----------
        symbols : List[str]
            Symbols to load (e.g., ['BTC-USD', 'ETH-USD'])
        period : str
            Data period ('4y', '2y', '1y', etc.)

        Returns
        -------
        Dict[str, pd.DataFrame]
            {symbol: OHLCV DataFrame}
        """
        if symbols is None:
            symbols = ["BTC-USD", "ETH-USD"]

        data = {}

        for symbol in symbols:
            logger.info(f"Loading data for {symbol} (period={period})")

            try:
                import yfinance as yf

                df = yf.download(
                    symbol,
                    period=period,
                    progress=False,
                    interval="1d",
                )

                if df.empty:
                    logger.warning(f"No data for {symbol}, using synthetic data")
                    df = self._generate_synthetic_data(len_days=252 * 4)
                else:
                    # Ensure columns are lowercase
                    df.columns = df.columns.str.lower()

                data[symbol] = df
                logger.info(f"Loaded {len(df)} rows for {symbol}")

            except ImportError:
                logger.warning("yfinance not installed, using synthetic data")
                data[symbol] = self._generate_synthetic_data(len_days=252 * 4)

        return data

    def train_all(self, data: Dict[str, pd.DataFrame]) -> Dict[str, object]:
        """
        Train all strategies.

        Parameters
        ----------
        data : Dict[str, pd.DataFrame]
            OHLCV data by symbol

        Returns
        -------
        Dict[str, object]
            {strategy_id: fitted_model}
        """
        models = {}

        logger.info("Training S0 (Regime HMM)")
        try:
            models["S0"] = self.train_s0(data)
        except Exception as e:
            logger.error(f"S0 training failed: {e}")
            models["S0"] = None

        logger.info("Training S2 (Minsky Phase Detector)")
        try:
            models["S2"] = self.train_s2(data)
        except Exception as e:
            logger.error(f"S2 training failed: {e}")
            models["S2"] = None

        logger.info("Training S3 (Narrative XGB)")
        try:
            models["S3"] = self.train_s3(data)
        except Exception as e:
            logger.error(f"S3 training failed: {e}")
            models["S3"] = None

        logger.info("Training S5 (Behavioral Contrarian XGB)")
        try:
            models["S5"] = self.train_s5(data)
        except Exception as e:
            logger.error(f"S5 training failed: {e}")
            models["S5"] = None

        logger.info("Training S7 (EVT Volatility Forecaster)")
        try:
            models["S7"] = self.train_s7(data)
        except Exception as e:
            logger.error(f"S7 training failed: {e}")
            models["S7"] = None

        return models

    def train_s0(self, data: Dict[str, pd.DataFrame]) -> object:
        """Train S0 — Regime HMM."""
        # Placeholder: import and train actual RegimeHMM
        try:
            from oracle_v2.ml.s0_regime_hmm import RegimeHMM

            hmm = RegimeHMM(n_regimes=3)

            # Aggregate returns across all symbols
            returns_list = []
            for df in data.values():
                if not df.empty and "close" in df.columns:
                    returns = df["close"].pct_change().dropna().values
                    returns_list.append(returns)

            if returns_list:
                all_returns = np.concatenate(returns_list)
                hmm.fit(all_returns.reshape(-1, 1))
                logger.info("S0 trained successfully")
                return hmm

        except ImportError:
            logger.warning("S0 module not available, returning placeholder")

        return self._create_placeholder_model("S0")

    def train_s2(self, data: Dict[str, pd.DataFrame]) -> object:
        """Train S2 — Minsky Phase Detector."""
        try:
            from oracle_v2.ml.s2_minsky_phase import MinskyPhaseDetector

            detector = MinskyPhaseDetector()

            # Use first symbol's data
            first_df = next(iter(data.values())) if data else None
            if first_df is not None and not first_df.empty:
                returns = first_df["close"].pct_change().dropna().values
                detector.fit(returns)
                logger.info("S2 trained successfully")
                return detector

        except ImportError:
            logger.warning("S2 module not available, returning placeholder")

        return self._create_placeholder_model("S2")

    def train_s3(self, data: Dict[str, pd.DataFrame]) -> object:
        """Train S3 — Narrative XGB."""
        try:
            from oracle_v2.ml.s3_narrative_xgb import NarrativeXGB

            xgb = NarrativeXGB()

            # Mock features: create synthetic X and y
            first_df = next(iter(data.values())) if data else None
            if first_df is not None and not first_df.empty:
                n = len(first_df)
                X = np.random.randn(n - 5, 10)  # 10 features
                returns = first_df["close"].pct_change().dropna().values
                y = (returns[5:] > 0).astype(int)

                if len(X) > 0 and len(y) > 0:
                    xgb.fit(X, y)
                    logger.info("S3 trained successfully")
                    return xgb

        except ImportError:
            logger.warning("S3 module not available, returning placeholder")

        return self._create_placeholder_model("S3")

    def train_s5(self, data: Dict[str, pd.DataFrame]) -> object:
        """Train S5 — Behavioral Contrarian XGB."""
        try:
            from oracle_v2.ml.s5_behavioral_xgb import BehavioralContrarianXGB

            xgb = BehavioralContrarianXGB()

            first_df = next(iter(data.values())) if data else None
            if first_df is not None and not first_df.empty:
                n = len(first_df)
                X = np.random.randn(n - 5, 10)
                returns = first_df["close"].pct_change().dropna().values
                y = (returns[5:] > 0).astype(int)

                if len(X) > 0 and len(y) > 0:
                    xgb.fit(X, y)
                    logger.info("S5 trained successfully")
                    return xgb

        except ImportError:
            logger.warning("S5 module not available, returning placeholder")

        return self._create_placeholder_model("S5")

    def train_s7(self, data: Dict[str, pd.DataFrame]) -> object:
        """Train S7 — EVT Volatility Forecaster."""
        try:
            from oracle_v2.ml.s7_evt_volatility import EVTVolatilityForecaster

            forecaster = EVTVolatilityForecaster()

            # Use first symbol's data
            first_df = next(iter(data.values())) if data else None
            if first_df is not None and not first_df.empty:
                returns = first_df["close"].pct_change().dropna().values
                forecaster.fit(returns)
                logger.info("S7 trained successfully")
                return forecaster

        except ImportError:
            logger.warning("S7 module not available, returning placeholder")

        return self._create_placeholder_model("S7")

    def validate_all(
        self,
        models: Dict[str, object],
        data: Dict[str, pd.DataFrame],
    ) -> Dict[str, List[WalkForwardResult]]:
        """
        Validate all strategies using walk-forward analysis.

        Parameters
        ----------
        models : Dict[str, object]
            {strategy_id: model}
        data : Dict[str, pd.DataFrame]
            OHLCV data

        Returns
        -------
        Dict[str, List[WalkForwardResult]]
            {strategy_id: list of fold results}
        """
        validator = WalkForwardValidator(
            train_window=180,
            test_window=30,
            step=30,
        )

        results = {}

        for strate_id in self.STRATE_IDS:
            if strate_id not in models or models[strate_id] is None:
                logger.warning(f"Model {strate_id} not available, skipping validation")
                continue

            logger.info(f"Validating {strate_id}")

            # Use first symbol's data
            first_df = next(iter(data.values())) if data else None
            if first_df is None or first_df.empty:
                logger.warning(f"No data for {strate_id} validation")
                continue

            # Prepare features and returns
            returns = first_df["close"].pct_change().dropna().values
            dates = first_df.index[1:]  # Align with returns

            # Mock features
            n = len(returns)
            features = np.random.randn(n, 10)  # 10 synthetic features

            try:
                fold_results = validator.run(
                    models[strate_id],
                    features,
                    returns,
                    dates,
                    horizon=5,
                )
                results[strate_id] = fold_results
                logger.info(f"{strate_id} validation complete: {len(fold_results)} folds")

            except Exception as e:
                logger.error(f"Validation failed for {strate_id}: {e}")

        return results

    def save_all(self, models: Dict[str, object]) -> None:
        """
        Save all trained models to disk.

        Parameters
        ----------
        models : Dict[str, object]
            {strategy_id: model}
        """
        for strate_id, model in models.items():
            if model is None:
                continue

            path = self.models_dir / f"{strate_id}.pkl"
            try:
                with open(path, "wb") as f:
                    pickle.dump(model, f)
                logger.info(f"Saved {strate_id} to {path}")
            except Exception as e:
                logger.error(f"Failed to save {strate_id}: {e}")

    def load_all(self) -> Dict[str, object]:
        """
        Load all trained models from disk.

        Returns
        -------
        Dict[str, object]
            {strategy_id: model}
        """
        models = {}

        for strate_id in self.STRATE_IDS:
            path = self.models_dir / f"{strate_id}.pkl"

            if not path.exists():
                logger.warning(f"Model file not found: {path}")
                models[strate_id] = None
                continue

            try:
                with open(path, "rb") as f:
                    model = pickle.load(f)
                models[strate_id] = model
                logger.info(f"Loaded {strate_id} from {path}")
            except Exception as e:
                logger.error(f"Failed to load {strate_id}: {e}")
                models[strate_id] = None

        return models

    @staticmethod
    def report(validation_results: Dict[str, List[WalkForwardResult]]) -> None:
        """
        Print comprehensive validation report.

        Parameters
        ----------
        validation_results : Dict[str, List[WalkForwardResult]]
            {strategy_id: fold_results}
        """
        print("\n" + "=" * 80)
        print("VALIDATION REPORT — ALL STRATEGIES")
        print("=" * 80)

        for strate_id, fold_results in validation_results.items():
            print(f"\n{strate_id}:")
            print("-" * 40)

            summary = WalkForwardValidator.summary(fold_results)

            if summary:
                print(f"  Folds: {summary['n_folds']}")
                print(f"  Sharpe (mean): {summary['sharpe']['mean']:.3f} ± {summary['sharpe']['std']:.3f}")
                print(f"  Win Rate (mean): {summary['win_rate']['mean']:.1%}")
                print(f"  Max DD (mean): {summary['max_dd']['mean']:.1%}")
                print(f"  Total Return (mean): {summary['total_return']['mean']:.1%}")
                print(f"  Total Trades: {summary['n_trades']['total']}")
            else:
                print(f"  No results")

        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def _generate_synthetic_data(len_days: int = 1000) -> pd.DataFrame:
        """Generate synthetic OHLCV data for testing."""
        dates = pd.date_range(end=pd.Timestamp.now(), periods=len_days, freq="D")
        close = 100 * np.exp(np.cumsum(np.random.randn(len_days) * 0.02))

        return pd.DataFrame(
            {
                "open": close * (1 + np.random.randn(len_days) * 0.01),
                "high": close * (1 + np.abs(np.random.randn(len_days) * 0.02)),
                "low": close * (1 - np.abs(np.random.randn(len_days) * 0.02)),
                "close": close,
                "volume": np.random.randint(1000000, 10000000, len_days),
            },
            index=dates,
        )

    @staticmethod
    def _create_placeholder_model(strate_id: str) -> object:
        """Create a placeholder model that returns neutral predictions."""
        class PlaceholderModel:
            def __init__(self, strate_id):
                self.strate_id = strate_id

            def fit(self, X, y=None):
                return self

            def predict(self, X):
                return np.zeros(len(X))

        return PlaceholderModel(strate_id)
