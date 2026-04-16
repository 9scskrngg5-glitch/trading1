class AgentError(Exception):
    """Base class for agent-related exceptions."""
    pass

class TradingError(Exception):
    """Base class for trading-related exceptions."""
    pass

class DataError(Exception):
    """Base class for data-related exceptions."""
    pass

class APIError(Exception):
    """Base class for API-related exceptions."""
    pass

class ConfigurationError(Exception):
    """Base class for configuration-related exceptions."""
    pass

class BacktestError(Exception):
    """Base class for backtest-related exceptions."""
    pass
