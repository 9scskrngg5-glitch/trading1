from .message_bus_local  import LocalMessageBus
from .obsidian_client    import ObsidianClient, ObsidianNote
from .base_agent         import BaseAgent
from .learning_engine    import LearningEngine
from .performance_tracker import PerformanceTracker

# Alias pour compatibilité (MessageBus = LocalMessageBus en mode démo)
MessageBus = LocalMessageBus

# CHANNELS définis localement (pas besoin de Redis)
CHANNELS = {
    "signals_technical":    "signals:technical",
    "signals_fundamental":  "signals:fundamental",
    "orders_validated":     "orders:validated",
    "orders_executed":      "orders:executed",
    "portfolio_update":     "portfolio:update",
    "heartbeat":            "system:heartbeat",
    "error":                "system:error",
    "decisions":            "decisions:convergence",
}

__all__ = [
    "MessageBus", "LocalMessageBus", "CHANNELS",
    "ObsidianClient", "ObsidianNote",
    "BaseAgent",
    "LearningEngine",
    "PerformanceTracker",
]
