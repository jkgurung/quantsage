"""
Configuration management using OmegaConf.

Centralized configuration with:
- YAML-based configuration files
- Environment variable substitution
- Configuration validation
- Hot-reload support (future)
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from omegaconf import OmegaConf, DictConfig
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class ConfigManager:
    """
    Centralized configuration management.

    Features:
    - Load configuration from YAML files
    - Environment variable substitution
    - Configuration validation
    - Easy access to nested config values
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to main configuration file
        """
        self.config_path = Path(config_path)
        self.config: Optional[DictConfig] = None
        self.strategies: Dict[str, DictConfig] = {}

        self.load_config()

    def load_config(self):
        """Load and merge all configuration files."""
        # Load main config
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        self.config = OmegaConf.load(self.config_path)

        # Resolve environment variables
        OmegaConf.resolve(self.config)

        # Load risk config
        if hasattr(self.config, 'risk_config'):
            risk_path = Path(self.config.risk_config)
            if risk_path.exists():
                self.config.risk = OmegaConf.load(risk_path)
                logger.info(f"Loaded risk config from {risk_path}")

        # Load strategy configs
        if hasattr(self.config, 'strategies_config'):
            strategies_dir = Path(self.config.strategies_config)
            if strategies_dir.exists():
                self._load_strategies(strategies_dir)

        logger.info(f"Configuration loaded from {self.config_path}")

    def _load_strategies(self, strategies_dir: Path):
        """Load all strategy configuration files."""
        for file in strategies_dir.glob("*.yaml"):
            try:
                strategy_name = file.stem
                strategy_config = OmegaConf.load(file)
                self.strategies[strategy_name] = strategy_config
                logger.info(f"Loaded strategy config: {strategy_name}")
            except Exception as e:
                logger.error(f"Error loading strategy config {file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'system.mode', 'portfolio.initial_capital')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        try:
            return OmegaConf.select(self.config, key, default=default)
        except Exception as e:
            logger.warning(f"Error getting config key '{key}': {e}")
            return default

    def get_strategy_config(self, strategy_name: str) -> Optional[DictConfig]:
        """Get configuration for specific strategy."""
        return self.strategies.get(strategy_name)

    def get_enabled_strategies(self) -> Dict[str, DictConfig]:
        """Get all enabled strategies."""
        enabled = {}
        for name, config in self.strategies.items():
            if config.get('strategy', {}).get('enabled', False):
                enabled[name] = config
        return enabled

    def get_enabled_symbols(self, asset_type: str = None) -> list:
        """
        Get list of enabled trading symbols.

        Args:
            asset_type: Filter by 'CRYPTO' or 'STOCK', None for all

        Returns:
            List of enabled symbols
        """
        symbols = []

        # Get crypto symbols
        if asset_type is None or asset_type == 'CRYPTO':
            crypto_symbols = self.get('data.crypto_symbols', [])
            for symbol_config in crypto_symbols:
                if symbol_config.get('enabled', False):
                    symbols.append(symbol_config['symbol'])

        # Get stock symbols
        if asset_type is None or asset_type == 'STOCK':
            stock_symbols = self.get('data.stock_symbols', [])
            for symbol_config in stock_symbols:
                if symbol_config.get('enabled', False):
                    symbols.append(symbol_config['symbol'])

        return symbols

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if valid, False otherwise
        """
        required_keys = [
            'system.mode',
            'database.type',
            'portfolio.initial_capital'
        ]

        for key in required_keys:
            if self.get(key) is None:
                logger.error(f"Missing required config key: {key}")
                return False

        # Validate system mode
        mode = self.get('system.mode')
        if mode not in ['backtest', 'paper', 'live']:
            logger.error(f"Invalid system mode: {mode}")
            return False

        # Validate portfolio
        initial_capital = self.get('portfolio.initial_capital')
        if initial_capital <= 0:
            logger.error(f"Invalid initial capital: {initial_capital}")
            return False

        logger.info("Configuration validation passed")
        return True

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary."""
        return OmegaConf.to_container(self.config, resolve=True)

    def __repr__(self) -> str:
        return f"ConfigManager(config_path='{self.config_path}')"


# Global config instance
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: str = "config/config.yaml") -> ConfigManager:
    """
    Get global configuration instance (singleton pattern).

    Args:
        config_path: Path to configuration file

    Returns:
        ConfigManager instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigManager(config_path)

    return _config_instance


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Load config
    config = ConfigManager()

    # Validate
    if not config.validate():
        print("Configuration validation failed!")
        exit(1)

    # Access values
    print(f"System mode: {config.get('system.mode')}")
    print(f"Initial capital: {config.get('portfolio.initial_capital')}")
    print(f"Database path: {config.get('database.path')}")

    # Get enabled symbols
    print(f"\nEnabled crypto symbols: {config.get_enabled_symbols('CRYPTO')}")

    # Get enabled strategies
    print(f"\nEnabled strategies: {list(config.get_enabled_strategies().keys())}")

    # Get specific strategy config
    mean_rev_config = config.get_strategy_config('mean_reversion_crypto')
    if mean_rev_config:
        print(f"\nMean Reversion BB Window: {mean_rev_config.strategy.parameters.bb_window}")

    # Print full config
    print("\n" + "="*50)
    print("Full Configuration:")
    print("="*50)
    print(OmegaConf.to_yaml(config.config))
