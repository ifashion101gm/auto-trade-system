"""
Synthetic market data generators for simulation testing.

Generates realistic OHLCV data for different market conditions:
- Trending markets (strong directional moves)
- Ranging markets (sideways consolidation)
- Flash crashes (sudden extreme volatility)
- Low liquidity (wide spreads, gaps)

These generators enable Layer 3 Simulation Testing by providing controlled
market scenarios to validate strategy and risk engine behavior.
"""
import random
import math
from typing import List, Dict, Any
from datetime import datetime, timedelta


class MarketDataGenerator:
    """Generate synthetic OHLCV data for various market scenarios."""
    
    @staticmethod
    def generate_trending_market(
        start_price: float = 50000.0,
        num_candles: int = 100,
        trend_strength: float = 0.02,  # 2% per candle
        noise_level: float = 0.005     # 0.5% random noise
    ) -> List[List[float]]:
        """
        Generate trending market data (strong directional movement).
        
        Args:
            start_price: Starting price
            num_candles: Number of candles to generate
            trend_strength: Price change per candle (positive = uptrend)
            noise_level: Random noise percentage
        
        Returns:
            OHLCV data: [[timestamp, open, high, low, close, volume], ...]
        """
        ohlcv = []
        current_price = start_price
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        for i in range(num_candles):
            # Apply trend + noise
            trend_change = current_price * trend_strength
            noise = current_price * random.uniform(-noise_level, noise_level)
            close_price = current_price + trend_change + noise
            
            # Generate OHLC from close
            high = max(current_price, close_price) * (1 + abs(noise))
            low = min(current_price, close_price) * (1 - abs(noise))
            volume = random.uniform(500, 2000)
            
            timestamp = int((base_time + timedelta(hours=i)).timestamp())
            
            ohlcv.append([
                timestamp,
                current_price,  # Open
                high,
                low,
                close_price,    # Close
                volume
            ])
            
            current_price = close_price
        
        return ohlcv
    
    @staticmethod
    def generate_ranging_market(
        start_price: float = 50000.0,
        num_candles: int = 100,
        range_pct: float = 0.02,  # ±2% range
        mean_reversion_speed: float = 0.1
    ) -> List[List[float]]:
        """
        Generate ranging/sideways market data.
        
        Args:
            start_price: Center price of range
            num_candles: Number of candles
            range_pct: Range as percentage of center price
            mean_reversion_speed: How quickly price returns to mean
        
        Returns:
            OHLCV data
        """
        ohlcv = []
        current_price = start_price
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        upper_bound = start_price * (1 + range_pct)
        lower_bound = start_price * (1 - range_pct)
        
        for i in range(num_candles):
            # Mean reversion force
            distance_from_mean = (current_price - start_price) / start_price
            reversion_force = -distance_from_mean * mean_reversion_speed
            
            # Random walk component
            random_move = random.uniform(-range_pct/2, range_pct/2)
            
            # Calculate next price
            change_pct = reversion_force + random_move
            close_price = current_price * (1 + change_pct)
            
            # Keep within bounds
            close_price = max(lower_bound, min(upper_bound, close_price))
            
            high = max(current_price, close_price) * 1.005
            low = min(current_price, close_price) * 0.995
            volume = random.uniform(300, 1000)
            
            timestamp = int((base_time + timedelta(hours=i)).timestamp())
            
            ohlcv.append([
                timestamp,
                current_price,
                high,
                low,
                close_price,
                volume
            ])
            
            current_price = close_price
        
        return ohlcv
    
    @staticmethod
    def generate_flash_crash(
        start_price: float = 50000.0,
        num_candles: int = 100,
        crash_candle: int = 50,
        crash_depth: float = 0.15,  # 15% drop
        recovery_speed: float = 0.3  # 30% recovery per candle
    ) -> List[List[float]]:
        """
        Generate flash crash scenario.
        
        Args:
            start_price: Starting price
            num_candles: Total candles
            crash_candle: Candle index where crash occurs
            crash_depth: Maximum drop percentage
            recovery_speed: Recovery rate per candle
        
        Returns:
            OHLCV data with crash and recovery
        """
        ohlcv = []
        current_price = start_price
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        crashed = False
        bottom_price = start_price
        
        for i in range(num_candles):
            if i < crash_candle:
                # Normal market before crash
                change = random.uniform(-0.005, 0.005)
                close_price = current_price * (1 + change)
                
            elif i == crash_candle:
                # CRASH!
                close_price = current_price * (1 - crash_depth)
                bottom_price = close_price
                crashed = True
                
            else:
                # Recovery phase
                if current_price < start_price * 0.98:  # Not fully recovered
                    recovery = (start_price - current_price) / current_price * recovery_speed
                    close_price = current_price * (1 + recovery + random.uniform(0, 0.01))
                else:
                    # Back to normal
                    change = random.uniform(-0.005, 0.005)
                    close_price = current_price * (1 + change)
            
            # High volatility during crash/recovery
            if crashed and i < crash_candle + 10:
                volatility = 0.03  # 3% intraday range
            else:
                volatility = 0.01  # 1% normal
            
            high = max(current_price, close_price) * (1 + volatility)
            low = min(current_price, close_price) * (1 - volatility)
            
            # Volume spike during crash
            if i >= crash_candle - 2 and i <= crash_candle + 5:
                volume = random.uniform(5000, 10000)  # Spike
            else:
                volume = random.uniform(500, 1500)
            
            timestamp = int((base_time + timedelta(hours=i)).timestamp())
            
            ohlcv.append([
                timestamp,
                current_price,
                high,
                low,
                close_price,
                volume
            ])
            
            current_price = close_price
        
        return ohlcv
    
    @staticmethod
    def generate_low_liquidity(
        start_price: float = 50000.0,
        num_candles: int = 100,
        gap_frequency: float = 0.1,  # 10% of candles have gaps
        spread_multiplier: float = 3.0  # 3x normal spread
    ) -> List[List[float]]:
        """
        Generate low liquidity market with wide spreads and gaps.
        
        Args:
            start_price: Starting price
            num_candles: Number of candles
            gap_frequency: Probability of price gap between candles
            spread_multiplier: Bid-ask spread multiplier
        
        Returns:
            OHLCV data with gaps and wide spreads
        """
        ohlcv = []
        current_price = start_price
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        for i in range(num_candles):
            # Check for gap
            if random.random() < gap_frequency and i > 0:
                gap_pct = random.uniform(-0.05, 0.05)  # ±5% gap
                open_price = current_price * (1 + gap_pct)
            else:
                open_price = current_price
            
            # Wide spread
            spread = open_price * 0.001 * spread_multiplier  # 0.1% * multiplier
            
            # Random close within spread
            close_price = open_price * (1 + random.uniform(-spread, spread))
            
            high = max(open_price, close_price) * (1 + spread)
            low = min(open_price, close_price) * (1 - spread)
            
            # Low volume
            volume = random.uniform(50, 200)  # Very low
            
            timestamp = int((base_time + timedelta(hours=i)).timestamp())
            
            ohlcv.append([
                timestamp,
                open_price,
                high,
                low,
                close_price,
                volume
            ])
            
            current_price = close_price
        
        return ohlcv
    
    @staticmethod
    def generate_high_volatility_spike(
        start_price: float = 50000.0,
        num_candles: int = 100,
        spike_candles: List[int] = None,
        spike_magnitude: float = 0.10  # 10% spikes
    ) -> List[List[float]]:
        """
        Generate market with sudden volatility spikes.
        
        Args:
            start_price: Starting price
            num_candles: Total candles
            spike_candles: Indices where spikes occur (default: [25, 50, 75])
            spike_magnitude: Size of volatility spikes
        
        Returns:
            OHLCV data with volatility spikes
        """
        if spike_candles is None:
            spike_candles = [25, 50, 75]
        
        ohlcv = []
        current_price = start_price
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        for i in range(num_candles):
            # Determine volatility regime
            if i in spike_candles:
                volatility = spike_magnitude  # High volatility
                volume_mult = 5.0  # Volume spike
            else:
                volatility = 0.01  # Normal 1% volatility
                volume_mult = 1.0
            
            # Random price movement
            change_pct = random.uniform(-volatility, volatility)
            close_price = current_price * (1 + change_pct)
            
            high = max(current_price, close_price) * (1 + volatility * 0.5)
            low = min(current_price, close_price) * (1 - volatility * 0.5)
            volume = random.uniform(500, 1500) * volume_mult
            
            timestamp = int((base_time + timedelta(hours=i)).timestamp())
            
            ohlcv.append([
                timestamp,
                current_price,
                high,
                low,
                close_price,
                volume
            ])
            
            current_price = close_price
        
        return ohlcv
