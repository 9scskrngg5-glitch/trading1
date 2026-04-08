"""
Pipeline 8 agents :
1. ScanAgent       — Scanner de marché (technique + indicateurs adaptatifs)
2. ResearchAgent   — Recherche fondamentale + sentiment + on-chain
3. PredictAgent    — Fusion ML des signaux + prédiction directionnelle
4. RiskAgent       — Sizing, SL/TP, drawdown, analyse contrefactuelle
5. ExecuteAgent    — Exécution ordres Binance/OANDA + slippage tracking
6. CompoundAgent   — Compounding, scaling, Kelly criterion
7. SynthesisAgent  — DataSheet institutionnelle (S/R, OB, Liquidité, Biais)
8. SupervisorAgent — Chef d'orchestre : monitoring, cohérence vault, alertes
"""

from .scan_agent       import ScanAgent
from .research_agent   import ResearchAgent
from .predict_agent    import PredictAgent
from .risk_agent       import RiskAgent
from .execute_agent    import ExecuteAgent
from .compound_agent   import CompoundAgent
from .synthesis_agent  import SynthesisAgent
from .supervisor_agent import SupervisorAgent

__all__ = [
    "ScanAgent", "ResearchAgent", "PredictAgent",
    "RiskAgent", "ExecuteAgent", "CompoundAgent",
    "SynthesisAgent", "SupervisorAgent",
]
