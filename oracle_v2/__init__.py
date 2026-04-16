"""ORACLE v2 — Neuromorphic Neural Trading System."""
__version__ = "2.1.0"

# ── Dual-import bootstrap ─────────────────────────────────────────────────────
# Garantit que `from brain.X import Y` fonctionne quel que soit le CWD.
# Règle le pattern try/except répété dans tous les modules sans les modifier.
import sys as _sys
import os as _os

_pkg_dir = _os.path.dirname(_os.path.abspath(__file__))
if _pkg_dir not in _sys.path:
    _sys.path.insert(0, _pkg_dir)

# ── Public API ────────────────────────────────────────────────────────────────
# Core (always available — no ML deps)
from oracle_v2.paper_monitor import PaperPositionMonitor  # noqa: E402

# ML stack (optional — requires numpy; torch/scipy/sklearn are graceful)
try:
    from oracle_v2.ml.base_model import OracleModel
    from oracle_v2.ml.s0_regime_hmm import RegimeHMM
    from oracle_v2.ml.s2_minsky_lstm import MinskyPhaseDetector
    from oracle_v2.ml.s3_narrative_xgb import S3NarrativeXGB
    from oracle_v2.ml.s5_behavioral_xgb import S5BehavioralContrarianXGB
    from oracle_v2.ml.s7_volatility_evt import S7EVTVolatilityForecaster
    from oracle_v2.ml.s8_causal_tft import S8CausalTFT
    from oracle_v2.ml.s9_personal_rl import S9PersonalRLAgent
    from oracle_v2.ml.s11_brier_calibrator import S11BrierCalibrator
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

# Parliament extensions
try:
    from oracle_v2.parliament.agents import AgentContext, AgentVerdict, build_agent_panel
    from oracle_v2.parliament.council import ParliamentCouncil
    from oracle_v2.parliament.debate_logger import DebateLogger
    from oracle_v2.parliament.ml_council import MLCouncil
    _PARLIAMENT_EXT_AVAILABLE = True
except ImportError:
    _PARLIAMENT_EXT_AVAILABLE = False

# Training pipeline
try:
    from oracle_v2.training.labeler import TripleBarrierLabeler, ForwardReturnLabeler
    from oracle_v2.training.feature_builder import FeatureBuilder
    from oracle_v2.training.walk_forward import WalkForwardValidator
    from oracle_v2.training.trainer import MLTrainer
    _TRAINING_AVAILABLE = True
except ImportError:
    _TRAINING_AVAILABLE = False

__all__ = [
    "__version__",
    "PaperPositionMonitor",
    # ML
    "OracleModel",
    "RegimeHMM",
    "MinskyPhaseDetector",
    "S3NarrativeXGB",
    "S5BehavioralContrarianXGB",
    "S7EVTVolatilityForecaster",
    "S8CausalTFT",
    "S9PersonalRLAgent",
    "S11BrierCalibrator",
    # Parliament
    "AgentContext",
    "AgentVerdict",
    "build_agent_panel",
    "ParliamentCouncil",
    "DebateLogger",
    "MLCouncil",
    # Training
    "TripleBarrierLabeler",
    "ForwardReturnLabeler",
    "FeatureBuilder",
    "WalkForwardValidator",
    "MLTrainer",
]
