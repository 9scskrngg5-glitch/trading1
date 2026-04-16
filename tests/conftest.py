import pytest
from unittest.mock import Mock

# Sample OHLCV data
SAMPLE_OHLCV = [
    {'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.0, 'volume': 100},
    {'open': 1.0, 'high': 1.2, 'low': 0.8, 'close': 1.1, 'volume': 150},
]

# Mock message bus
@pytest.fixture
def mock_message_bus():
    return Mock()

# Mock Obsidian client
@pytest.fixture
def mock_obsidian_client():
    return Mock()

# Mock technical signals
@pytest.fixture
def mock_technical_signals():
    return {'signal': 'buy', 'confidence': 0.9}

# Mock trade outcomes
@pytest.fixture
def mock_trade_outcomes():
    return {'profit': 10.0, 'loss': 5.0}

# Use the sample OHLCV data in tests
@pytest.fixture
def sample_ohlcv_data():
    return SAMPLE_OHLCV
