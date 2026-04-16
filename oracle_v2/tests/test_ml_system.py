"""
Quick test suite for ORACLE v2 ML system.
Validates that all modules load and basic functionality works.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Add oracle_v2 to path
oracle_path = Path(__file__).parent.parent
sys.path.insert(0, str(oracle_path))

def test_walk_forward_validator():
    """Test WalkForwardValidator module."""
    print("\nTesting WalkForwardValidator...")

    try:
        from training.walk_forward import WalkForwardValidator, WalkForwardResult

        validator = WalkForwardValidator(train_window=50, test_window=10, step=10)

        # Generate mock folds
        folds = validator.generate_folds(n=100)
        assert len(folds) > 0, "No folds generated"
        assert all(isinstance(f, tuple) and len(f) == 2 for f in folds), "Invalid fold format"

        print(f"  ✓ Generated {len(folds)} folds")

        # Test label generation
        returns = np.random.randn(100) * 0.02
        labels = validator._generate_labels(returns, horizon=5)
        assert len(labels) == 100 - 5, "Labels length mismatch"
        assert set(labels).issubset({-1, 0, 1}), "Invalid label values"

        print(f"  ✓ Generated labels with {len(set(labels))} unique classes")

        # Test metrics computation
        y_true = np.array([1, -1, 0, 1, -1])
        y_pred = np.array([0.9, -0.8, 0.1, 0.7, -0.9])
        returns_test = np.array([0.01, -0.02, 0.005, 0.015, -0.01])

        metrics = validator._compute_metrics(y_true, y_pred, returns_test)
        assert all(k in metrics for k in ["sharpe", "win_rate", "max_dd", "total_return", "n_trades"]), "Missing metrics"

        print(f"  ✓ Computed metrics: Sharpe={metrics['sharpe']:.2f}, WinRate={metrics['win_rate']:.1%}")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_ml_trainer():
    """Test MLTrainer module."""
    print("\nTesting MLTrainer...")

    try:
        from training.trainer import MLTrainer

        config = {"test": True}
        trainer = MLTrainer(config, data_dir="/tmp/data", models_dir="/tmp/models")

        # Test synthetic data generation
        synthetic = trainer._generate_synthetic_data(100)
        assert len(synthetic) == 100, "Synthetic data length mismatch"
        assert all(col in synthetic.columns for col in ["open", "high", "low", "close", "volume"]), "Missing columns"

        print(f"  ✓ Generated {len(synthetic)} rows synthetic OHLCV data")

        # Test placeholder model
        placeholder = trainer._create_placeholder_model("S0_TEST")
        X = np.random.randn(50, 10)
        y = np.random.randn(50)

        placeholder.fit(X, y)
        preds = placeholder.predict(X)
        assert len(preds) == len(X), "Prediction length mismatch"

        print(f"  ✓ Placeholder model fit and predict work")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_s11_brier_calibrator():
    """Test S11BrierCalibrator module."""
    print("\nTesting S11BrierCalibrator...")

    try:
        from ml.s11_brier_calibrator import S11BrierCalibrator, BrierTracking

        calibrator = S11BrierCalibrator(
            strate_ids=["S0", "S2", "S3", "S5", "S7"],
            min_weight=0.1,
            max_weight=3.0
        )

        # Test update
        calibrator.update("S0", prediction_proba=0.7, actual_outcome=1)
        calibrator.update("S0", prediction_proba=0.4, actual_outcome=0)

        weights = calibrator.get_weights()
        assert "S0" in weights, "S0 weight missing"
        assert 0.1 <= weights["S0"] <= 3.0, "Weight out of bounds"

        print(f"  ✓ Updated Brier scores, S0 weight = {weights['S0']:.2f}x")

        # Test parliament vote
        signals = {"S0": 0.8, "S2": 0.5, "S3": -0.3, "S5": 0.0, "S7": 0.6}
        vote = calibrator.parliament_vote(signals)
        assert -1 <= vote <= 1, "Vote out of bounds"

        print(f"  ✓ Parliament vote = {vote:.3f}")

        # Test decision
        decision, strength, reasoning = calibrator.get_parliament_decision(signals, quorum=0.6)
        assert decision in ["LONG", "SHORT", "NEUTRAL"], "Invalid decision"
        assert 0 <= strength <= 1, "Strength out of bounds"

        print(f"  ✓ Parliament decision: {decision} ({strength:.1%})")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_ml_council():
    """Test MLCouncil module."""
    print("\nTesting MLCouncil...")

    try:
        from parliament.ml_council import MLCouncil, Vote

        council = MLCouncil(models_dir="/tmp/models", slippage_pct=0.0005)

        # Test Vote dataclass
        vote = Vote(
            strategy_id="S0",
            decision="LONG",
            strength=0.8,
            confidence=0.7,
            reasoning="Test vote"
        )
        assert vote.strategy_id == "S0", "Vote creation failed"

        print(f"  ✓ Vote created: {vote.strategy_id} → {vote.decision} ({vote.strength:.1%})")

        # Test S0 gate
        returns = np.array([0.01, -0.005, 0.002, 0.015, -0.01] * 6)
        volume = np.ones(30) * 1e6

        gate = council._s0_gate(returns, volume)
        assert isinstance(gate, bool), "Gate result not bool"

        print(f"  ✓ S0 gate status: {'OPEN' if gate else 'CLOSED'}")

        # Test predictions
        test_returns = np.random.randn(30) * 0.02

        s0_pred = council._predict_s0(test_returns)
        assert s0_pred in ["LONG", "SHORT", "NEUTRAL"], "Invalid S0 prediction"

        print(f"  ✓ S0 prediction: {s0_pred}")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("ORACLE v2 ML SYSTEM — QUICK TEST SUITE")
    print("=" * 70)

    tests = [
        ("WalkForwardValidator", test_walk_forward_validator),
        ("MLTrainer", test_ml_trainer),
        ("S11BrierCalibrator", test_s11_brier_calibrator),
        ("MLCouncil", test_ml_council),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ {test_name} — Fatal error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for test_name, passed_flag in results:
        status = "PASS" if passed_flag else "FAIL"
        print(f"  {test_name}: {status}")

    print(f"\nResult: {passed}/{total} tests passed")
    print("=" * 70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
