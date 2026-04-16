# ORACLE v2 ML System — Complete Index

## Core Modules (Created)

### 1. Walk-Forward Validator
**File:** `training/walk_forward.py` (469 lines)

Time-series cross-validation without look-ahead bias.

**Key Classes:**
- `WalkForwardValidator`: Orchestrator
  - `generate_folds(n)` → List[Tuple[range, range]]
  - `run(model, features, returns, dates, horizon=5)` → List[WalkForwardResult]
  - `_generate_labels(returns, horizon=5)` → np.ndarray {-1, 0, 1}
  - `_compute_metrics(...)` → Dict with Sharpe, WinRate, MaxDD, Total Return
  - `summary(results)` → Aggregated stats + formatted output
  - `plot_equity_curve(results, ...)` → matplotlib/ASCII plot
  - `is_statistically_significant(results, n_bootstrap=1000)` → (bool, p_value)

- `WalkForwardResult`: Dataclass for fold results
  - fold_idx, train_idx, test_idx
  - train_dates, test_dates
  - predictions, actual_labels
  - sharpe, win_rate, max_dd, total_return, n_trades, pnl_per_trade

**Usage:**
```python
validator = WalkForwardValidator(train_window=180, test_window=30, step=30)
folds = validator.generate_folds(n=1000)
results = validator.run(model, features, returns, dates, horizon=5)
summary = WalkForwardValidator.summary(results)
```

---

### 2. ML Trainer
**File:** `training/trainer.py` (452 lines)

Orchestrates training of all ORACLE v2 strategies (S0-S7).

**Key Class:**
- `MLTrainer`: Main orchestrator
  - `load_data(symbols=['BTC-USD', 'ETH-USD'], period='4y')` → Dict[str, DataFrame]
  - `train_all(data)` → Dict {strate_id: model}
  - `train_s0(data)` → RegimeHMM
  - `train_s2(data)` → MinskyPhaseDetector
  - `train_s3(data)` → NarrativeXGB
  - `train_s5(data)` → BehavioralContrarianXGB
  - `train_s7(data)` → EVTVolatilityForecaster
  - `validate_all(models, data)` → Dict {strate_id: List[WalkForwardResult]}
  - `save_all(models)` → Pickle persistence
  - `load_all()` → Dict {strate_id: model}
  - `report(validation_results)` → Print summary

**Features:**
- yfinance support with graceful synthetic data fallback
- Modular training per strategy
- Logging at each step
- Graceful error handling

**Usage:**
```python
trainer = MLTrainer(config, data_dir='data/', models_dir='models/')
data = trainer.load_data(symbols=['BTC-USD', 'ETH-USD'], period='4y')
models = trainer.train_all(data)
results = trainer.validate_all(models, data)
trainer.save_all(models)
```

---

### 3. S11 Brier Calibrator
**File:** `ml/s11_brier_calibrator.py` (347 lines)

Meta-model for dynamic parliament voting weights using Brier Score.

**Key Classes:**
- `S11BrierCalibrator`: Main calibrator
  - `update(strate_id, prediction_proba, actual_outcome)` → Update Brier rolling 30d
  - `_recompute_weights()` → Normalize to bounds [0.1, 3.0]
  - `get_weights()` → Dict[str, float]
  - `parliament_vote(signals)` → float [-1, 1] weighted vote
  - `get_parliament_decision(signals, quorum=0.6)` → (decision, strength, reasoning)
  - `save(filepath)` → JSON
  - `load(filepath)` → S11BrierCalibrator
  - `report()` → Formatted print
  - `get_status_emojis()` → Dict[str, str] visual indicators

- `BrierTracking`: Per-strategy tracking
  - window_size=30, scores (deque)
  - weight, last_updated
  - add_score(score), mean_score(), confidence()

**Features:**
- Rolling Brier Score calculation (30-day window)
- Dynamic weight bounds [0.1, 3.0]
- Quorum-based voting (60% default)
- JSON persistence
- Status emojis for quick health checks

**Usage:**
```python
calibrator = S11BrierCalibrator(
    strate_ids=['S0', 'S2', 'S3', 'S5', 'S7'],
    min_weight=0.1,
    max_weight=3.0
)
calibrator.update('S0', prediction_proba=0.7, actual_outcome=1)
vote = calibrator.parliament_vote({'S0': 0.8, 'S2': 0.5})
decision, strength, reasoning = calibrator.get_parliament_decision(signals)
calibrator.save('s11_calibrator.json')
```

---

### 4. ML Council
**File:** `parliament/ml_council.py` (423 lines)

Bridges ML models to Parliament oracle. Implements S0 Gate Override rule.

**Key Classes:**
- `MLCouncil`: Adapter
  - `load_models()` → Load S0-S7 from models/
  - `async generate_votes(symbol, features, returns, close, volume)` → List[Vote]
  - `_s0_gate(returns, volume)` → bool (TRUE=gate open)
  - `_apply_s7_sizing(vote, returns)` → Vote with volatility adjustment
  - `_predict_s0/s2/s3/s5/s7(data)` → decision str

- `Vote`: Dataclass
  - strategy_id, decision ('LONG'/'SHORT'/'NEUTRAL')
  - strength [0, 1], confidence [0, 1]
  - reasoning, timestamp

**Features:**
- S0 Gate Override: NOISE → all votes NEUTRAL
- S7 Volatility Sizing Adjustment
- Graceful model absence handling
- Async-ready interface

**Critical Rule:**
```
ABSOLUTE RULE: If S0 detects NOISE regime:
  - Gate is CLOSED
  - All ML votes return NEUTRAL
  - No trading signals processed
```

**Usage:**
```python
council = MLCouncil(models_dir='models/', slippage_pct=0.0005)
council.load_models()
votes = await council.generate_votes(
    symbol='BTC-USD',
    features={'s3_features': X, 's5_features': Y},
    returns=returns,
    close=close,
    volume=volume
)
```

---

## Directory Structure

```
oracle_v2/
├── training/
│   ├── walk_forward.py          # Walk-forward validator
│   ├── trainer.py               # ML trainer orchestrator
│   └── ...                       # Existing files
├── ml/
│   ├── s11_brier_calibrator.py  # Brier calibrator
│   └── ...                       # Existing models (S0-S7)
├── parliament/
│   ├── __init__.py              # Module marker
│   ├── ml_council.py            # ML council adapter
│   └── ...                       # Existing parliament
├── models/                       # Trained model storage
│   └── .gitkeep
├── data/                         # Raw data storage
│   └── .gitkeep
├── tests/
│   └── test_ml_system.py        # Validation suite
└── ...                          # Existing files
```

---

## Integration Points

### 1. Data Pipeline
```
yfinance/synthetic data
    ↓
MLTrainer.load_data()
    ↓
[train/test splits via WalkForwardValidator]
    ↓
train_s0/s2/s3/s5/s7()
```

### 2. Validation Pipeline
```
Trained models
    ↓
validate_all()
    ↓
WalkForwardValidator.run()
    ↓
WalkForwardValidator.summary()
```

### 3. Parliament Integration
```
Live market data
    ↓
MLCouncil.generate_votes()
    ↓
S0 Gate check → NOISE detection
    ↓
S1-S7 predictions
    ↓
S11BrierCalibrator.parliament_vote()
    ↓
Parliament oracle decision
```

---

## Configuration

### Walk-Forward Windows
- train_window: 180 days (default)
- test_window: 30 days (default)
- step: 30 days (default, no overlap)

### Brier Calibrator Bounds
- min_weight: 0.1 (minimum voting power)
- max_weight: 3.0 (maximum voting power)
- window: 30 days rolling Brier Score
- quorum: 60% agreement required (default)

### S0 Gate Thresholds
- Normal volatility: < 5% daily
- Normal volume: > 0 (exists)

---

## Testing

Run validation suite:
```bash
cd oracle_v2
python3 tests/test_ml_system.py
```

Expected output: S11BrierCalibrator PASS, MLCouncil PASS

---

## Dependencies

**Core:**
- numpy
- pandas
- logging
- pickle
- json
- pathlib

**Optional (try/except handled):**
- yfinance (data loading)
- matplotlib (equity plotting)
- ML model modules (S0-S7)

---

## Future Work

1. Implement actual S0-S7 models
2. Connect to backtest pipeline
3. Live calibration framework
4. Parliament oracle testing
5. Production deployment

---

## Notes

- All files are type-hinted and documented
- 100% graceful error handling
- No external dependencies required (fallbacks provided)
- Ready for integration with existing ORACLE v2 system
