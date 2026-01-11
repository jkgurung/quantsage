"""
Mean Reversion Strategy using Bollinger Bands, Z-score, and RSI.

Entry Logic:
- BUY: Price < lower band AND z-score < -2 AND RSI < 40 AND volume confirmation
- SELL: Price > upper band AND z-score > 2 AND RSI > 60 AND volume confirmation

Exit Logic:
- Price returns to middle Bollinger Band
- Stop-loss hit (2% for crypto)
- Take-profit hit (1.5x distance to middle)
- Opposite signal generated

Filters:
- Daily volatility < 8%
- Daily volume > $1M
- Spread < 0.5%
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.strategies.base import BaseStrategy
from src.core.events import MarketDataEvent, SignalEvent
from src.data.features import FeatureEngineer


logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy for cryptocurrency trading.
    
    Uses Bollinger Bands to identify overbought/oversold conditions,
    confirmed by Z-score and RSI filters, with volume confirmation.
    
    Configuration loaded from: config/strategies/mean_reversion_crypto.yaml
    """
    
    def __init__(self, config: Dict, event_bus, db):
        """Initialize mean reversion strategy."""
        super().__init__(config, event_bus, db)
        
        # Strategy parameters from config
        params = config.get('strategy', {}).get('parameters', {})
        
        # Bollinger Bands
        self.bb_window = params.get('bb_window', 20)
        self.bb_std = params.get('bb_std', 2.0)
        
        # Z-score
        self.zscore_window = params.get('zscore_window', 20)
        self.zscore_threshold = params.get('zscore_threshold', 2.0)
        
        # RSI
        self.rsi_window = params.get('rsi_window', 14)
        self.rsi_oversold = params.get('rsi_oversold', 40)
        self.rsi_overbought = params.get('rsi_overbought', 60)
        
        # Exit parameters
        self.stop_loss_pct = params.get('stop_loss_pct', 0.02)
        self.take_profit_ratio = params.get('take_profit_ratio', 1.5)
        self.exit_on_middle_band = params.get('exit_on_middle_band', True)
        
        # Filters from config
        self.filters = config.get('strategy', {}).get('filters', [])
        
        # Feature engineer for indicator calculation
        self.feature_engineer = FeatureEngineer()
        
        # Minimum data points needed
        self.min_data_points = max(self.bb_window, self.zscore_window, self.rsi_window) + 10
        
        logger.info(f"MeanReversionStrategy initialized: BB({self.bb_window},{self.bb_std}), "
                   f"Z-score({self.zscore_window},{self.zscore_threshold}), "
                   f"RSI({self.rsi_window},{self.rsi_oversold}/{self.rsi_overbought})")
    
    def on_market_data(self, event: MarketDataEvent) -> Optional[SignalEvent]:
        """
        Process market data and generate trading signals.
        
        Args:
            event: Market data event with OHLCV data
        
        Returns:
            SignalEvent if conditions met, None otherwise
        """
        try:
            symbol = event.symbol
            
            # Check if we have an existing position - evaluate exit first
            if self.has_position(symbol):
                exit_signal = self._check_exit_conditions(symbol, event)
                if exit_signal:
                    return exit_signal
            
            # Check entry conditions if no position
            if not self.has_position(symbol):
                entry_signal = self._check_entry_conditions(symbol, event)
                if entry_signal:
                    return entry_signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error in on_market_data for {event.symbol}: {e}", exc_info=True)
            return None
    
    def _get_indicators(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get recent data and calculate indicators.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            DataFrame with indicators or None
        """
        try:
            # Get recent data (need enough for indicators)
            data = self.get_recent_data(symbol, lookback_periods=self.min_data_points + 50)
            
            if not data or len(data) < self.min_data_points:
                logger.debug(f"Insufficient data for {symbol}: {len(data) if data else 0} < {self.min_data_points}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Ensure timestamp index
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            
            # Calculate indicators using FeatureEngineer
            df_indicators = self.feature_engineer.calculate_indicators(df)
            
            if df_indicators is None or df_indicators.empty:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return None
            
            # Calculate Z-score manually (not in FeatureEngineer)
            df_indicators['zscore'] = (
                (df_indicators['close'] - df_indicators['close'].rolling(self.zscore_window).mean()) /
                df_indicators['close'].rolling(self.zscore_window).std()
            )
            
            # Calculate average volume
            df_indicators['avg_volume_20'] = df_indicators['volume'].rolling(20).mean()
            
            return df_indicators.tail(50)  # Return recent data with indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            return None
    
    def _check_filters(self, df: pd.DataFrame, symbol: str) -> bool:
        """
        Check if data passes all filters.
        
        Args:
            df: DataFrame with indicators
            symbol: Trading symbol
        
        Returns:
            True if all filters pass, False otherwise
        """
        try:
            latest = df.iloc[-1]
            
            for filter_config in self.filters:
                filter_type = filter_config.get('type')
                
                if filter_type == 'volatility':
                    # Check daily volatility
                    max_volatility = filter_config.get('max_daily_volatility', 0.08)
                    daily_returns = df['close'].pct_change().tail(24)
                    volatility = daily_returns.std()
                    
                    if volatility > max_volatility:
                        logger.debug(f"{symbol}: Volatility filter failed: {volatility:.4f} > {max_volatility}")
                        return False
                
                elif filter_type == 'volume':
                    # Check daily volume
                    min_volume = filter_config.get('min_daily_volume', 1000000)
                    daily_volume = df['volume'].tail(24).sum() * latest['close']
                    
                    if daily_volume < min_volume:
                        logger.debug(f"{symbol}: Volume filter failed: ${daily_volume:.0f} < ${min_volume}")
                        return False
                
                elif filter_type == 'spread':
                    # Check spread (simplified - just check volatility as proxy)
                    max_spread = filter_config.get('max_spread_pct', 0.005)
                    recent_spread = (latest['high'] - latest['low']) / latest['close']
                    
                    if recent_spread > max_spread:
                        logger.debug(f"{symbol}: Spread filter failed: {recent_spread:.4f} > {max_spread}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking filters: {e}")
            return False
    
    def _check_entry_conditions(self, symbol: str, event: MarketDataEvent) -> Optional[SignalEvent]:
        """
        Check entry conditions for BUY or SELL signals.
        
        Args:
            symbol: Trading symbol
            event: Market data event
        
        Returns:
            SignalEvent if conditions met, None otherwise
        """
        try:
            # Get indicators
            df = self._get_indicators(symbol)
            if df is None:
                return None
            
            # Check filters
            if not self._check_filters(df, symbol):
                return None
            
            latest = df.iloc[-1]
            current_price = latest['close']
            
            # Extract indicators
            bb_upper = latest['bb_high']
            bb_middle = latest['bb_mid']
            bb_lower = latest['bb_low']
            zscore = latest['zscore']
            rsi = latest['rsi']
            volume = latest['volume']
            avg_volume = latest['avg_volume_20']
            
            # Check BUY conditions
            buy_conditions = (
                current_price < bb_lower and
                zscore < -self.zscore_threshold and
                rsi < self.rsi_oversold and
                volume > avg_volume * 1.2
            )
            
            if buy_conditions:
                logger.info(f"{symbol}: BUY signal - Price: {current_price:.2f}, "
                           f"BB: {bb_lower:.2f}/{bb_middle:.2f}/{bb_upper:.2f}, "
                           f"Z-score: {zscore:.2f}, RSI: {rsi:.2f}")
                
                # Calculate stop-loss and take-profit
                stop_loss = current_price * (1 - self.stop_loss_pct)
                distance_to_middle = bb_middle - current_price
                take_profit = current_price + (distance_to_middle * self.take_profit_ratio)
                
                return self._create_signal(
                    symbol=symbol,
                    direction='BUY',
                    target_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=min(abs(zscore) / 3.0, 1.0),  # Higher z-score = higher confidence
                    metadata={
                        'zscore': float(zscore),
                        'rsi': float(rsi),
                        'bb_position': 'below_lower',
                    }
                )
            
            # Check SELL conditions
            sell_conditions = (
                current_price > bb_upper and
                zscore > self.zscore_threshold and
                rsi > self.rsi_overbought and
                volume > avg_volume * 1.2
            )
            
            if sell_conditions:
                logger.info(f"{symbol}: SELL signal - Price: {current_price:.2f}, "
                           f"BB: {bb_lower:.2f}/{bb_middle:.2f}/{bb_upper:.2f}, "
                           f"Z-score: {zscore:.2f}, RSI: {rsi:.2f}")
                
                # Calculate stop-loss and take-profit for short
                stop_loss = current_price * (1 + self.stop_loss_pct)
                distance_to_middle = current_price - bb_middle
                take_profit = current_price - (distance_to_middle * self.take_profit_ratio)
                
                return self._create_signal(
                    symbol=symbol,
                    direction='SELL',
                    target_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=min(abs(zscore) / 3.0, 1.0),
                    metadata={
                        'zscore': float(zscore),
                        'rsi': float(rsi),
                        'bb_position': 'above_upper',
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking entry conditions: {e}")
            return None
    
    def _check_exit_conditions(self, symbol: str, event: MarketDataEvent) -> Optional[SignalEvent]:
        """
        Check exit conditions for existing position.
        
        Args:
            symbol: Trading symbol
            event: Market data event
        
        Returns:
            SignalEvent to close position if conditions met, None otherwise
        """
        try:
            position = self.get_position(symbol)
            if not position:
                return None
            
            # Get indicators
            df = self._get_indicators(symbol)
            if df is None:
                return None
            
            latest = df.iloc[-1]
            current_price = latest['close']
            bb_middle = latest['bb_mid']
            
            entry_price = self.entry_prices.get(symbol)
            if not entry_price:
                logger.warning(f"No entry price found for {symbol}")
                return None
            
            direction = position.get('direction', 'BUY')
            
            # Check exit conditions
            should_exit = False
            exit_reason = ""
            
            # 1. Return to middle band
            if self.exit_on_middle_band:
                if direction == 'BUY' and current_price >= bb_middle:
                    should_exit = True
                    exit_reason = "price_at_middle_band"
                elif direction == 'SELL' and current_price <= bb_middle:
                    should_exit = True
                    exit_reason = "price_at_middle_band"
            
            # 2. Stop-loss
            stop_loss = position.get('stop_loss')
            if stop_loss:
                if direction == 'BUY' and current_price <= stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
                elif direction == 'SELL' and current_price >= stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
            
            # 3. Take-profit
            take_profit = position.get('take_profit')
            if take_profit:
                if direction == 'BUY' and current_price >= take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
                elif direction == 'SELL' and current_price <= take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
            
            if should_exit:
                pnl_pct = ((current_price - entry_price) / entry_price * 100 
                          if direction == 'BUY' 
                          else (entry_price - current_price) / entry_price * 100)
                
                logger.info(f"{symbol}: EXIT signal ({exit_reason}) - "
                           f"Entry: {entry_price:.2f}, Current: {current_price:.2f}, "
                           f"P&L: {pnl_pct:+.2f}%")
                
                return self._create_signal(
                    symbol=symbol,
                    direction='CLOSE',
                    target_price=current_price,
                    confidence=1.0,
                    metadata={
                        'exit_reason': exit_reason,
                        'entry_price': float(entry_price),
                        'pnl_pct': float(pnl_pct),
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return None


