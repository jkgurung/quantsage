"""
Pytest configuration and fixtures for QuantSage tests.

This file is automatically loaded by pytest and provides:
- Path setup to import from src/
- Common fixtures used across tests
- Test configuration
"""

import sys
import os
from pathlib import Path

# Add project root to Python path so imports work consistently
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
import tempfile
import shutil


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    yield db_path
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def db_manager(temp_db_path):
    """Create a DatabaseManager instance with a temporary database."""
    from src.data.storage import DatabaseManager
    db = DatabaseManager(db_path=temp_db_path)
    yield db
    db.close()


# ============================================================================
# Event System Fixtures
# ============================================================================

@pytest.fixture
def event_bus():
    """Create a fresh EventBus instance for testing."""
    from src.core.event_bus import EventBus
    bus = EventBus(mode='backtest')
    yield bus


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus for isolated testing."""
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.subscribe = MagicMock()
    bus.get_history = MagicMock(return_value=[])
    return bus


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = MagicMock()
    config.get = MagicMock(side_effect=lambda key, default=None: {
        'system.mode': 'backtest',
        'portfolio.initial_capital': 100000.0,
        'risk.position.max_position_size': 0.1,
        'risk.position.min_stop_loss': 0.005,
        'risk.position.max_stop_loss': 0.1,
        'risk.symbol.max_symbol_exposure': 0.15,
        'risk.portfolio.max_portfolio_exposure': 0.8,
        'risk.circuit_breakers.daily_loss_limit': -0.05,
        'risk.circuit_breakers.max_drawdown': -0.2,
    }.get(key, default))
    return config


@pytest.fixture
def risk_config():
    """Return default risk configuration dictionary."""
    return {
        'position': {
            'max_position_size': 0.1,
            'min_stop_loss': 0.005,
            'max_stop_loss': 0.1
        },
        'symbol': {
            'max_symbol_exposure': 0.15
        },
        'portfolio': {
            'max_portfolio_exposure': 0.8
        },
        'circuit_breakers': {
            'daily_loss_limit': -0.05,
            'max_drawdown': -0.2
        }
    }


# ============================================================================
# Market Data Fixtures
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    from src.core.events import MarketDataEvent
    return MarketDataEvent(
        symbol='BTC/USD',
        timestamp=datetime.now(),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=1000.0,
        asset_type='CRYPTO'
    )


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV DataFrame for testing."""
    import pandas as pd
    import numpy as np

    dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
    np.random.seed(42)

    data = {
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(100) * 100),
        'high': None,
        'low': None,
        'close': None,
        'volume': np.random.uniform(100, 1000, 100)
    }

    df = pd.DataFrame(data)
    df['high'] = df['open'] + np.abs(np.random.randn(100) * 50)
    df['low'] = df['open'] - np.abs(np.random.randn(100) * 50)
    df['close'] = df['open'] + np.random.randn(100) * 30

    return df


# ============================================================================
# Signal and Order Fixtures
# ============================================================================

@pytest.fixture
def sample_signal():
    """Create a sample SignalEvent for testing."""
    from src.core.events import SignalEvent
    return SignalEvent(
        symbol='BTC/USD',
        signal_type='BUY',
        price=50000.0,
        timestamp=datetime.now(),
        strategy_id='mean_reversion_crypto',
        confidence=0.85,
        position_size=0.05,
        stop_loss=49000.0,
        take_profit=52000.0
    )


@pytest.fixture
def sample_order():
    """Create a sample OrderEvent for testing."""
    from src.core.events import OrderEvent
    return OrderEvent(
        symbol='BTC/USD',
        order_type='MARKET',
        side='BUY',
        quantity=0.1,
        price=50000.0,
        timestamp=datetime.now(),
        strategy_id='mean_reversion_crypto',
        stop_loss=49000.0,
        take_profit=52000.0
    )


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_db: marks tests that require database access"
    )
