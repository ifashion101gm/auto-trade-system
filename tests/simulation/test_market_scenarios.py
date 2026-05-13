"""
Market scenario tests using synthetic data generators.

These tests validate that synthetic data generators produce realistic and
expected market patterns for Layer 3 Simulation Testing. They ensure the
generators create proper scenarios before using them for strategy stress testing.

Scenarios tested:
- Trending markets (strong directional moves)
- Ranging markets (sideways consolidation)
- Flash crashes (sudden extreme volatility)
- Low liquidity events (wide spreads, slippage)
- High volatility spikes
"""
import pytest
from tests.simulation.market_data_generator import MarketDataGenerator


class TestMarketScenarios:
    """Test system behavior under various market conditions."""
    
    def test_trending_market_data_generation(self):
        """Verify trending market generator produces expected patterns."""
        ohlcv = MarketDataGenerator.generate_trending_market(
            start_price=50000.0,
            num_candles=100,
            trend_strength=0.02
        )
        
        assert len(ohlcv) == 100
        
        # Verify uptrend (last price > first price)
        first_close = ohlcv[0][4]
        last_close = ohlcv[-1][4]
        assert last_close > first_close * 1.5  # At least 50% gain over 100 candles
    
    def test_trending_market_consistent_direction(self):
        """Verify trending market maintains consistent direction."""
        ohlcv = MarketDataGenerator.generate_trending_market(
            start_price=50000.0,
            num_candles=50,
            trend_strength=0.015  # 1.5% per candle
        )
        
        prices = [candle[4] for candle in ohlcv]
        
        # Overall trend should be up despite noise
        assert prices[-1] > prices[0] * 1.4  # At least 40% gain
    
    def test_ranging_market_stays_in_bounds(self):
        """Verify ranging market stays within defined bounds."""
        ohlcv = MarketDataGenerator.generate_ranging_market(
            start_price=50000.0,
            num_candles=100,
            range_pct=0.02
        )
        
        prices = [candle[4] for candle in ohlcv]
        assert min(prices) >= 49000  # Lower bound (50k - 2%)
        assert max(prices) <= 51000  # Upper bound (50k + 2%)
    
    def test_ranging_market_mean_reversion(self):
        """Verify ranging market exhibits mean reversion behavior."""
        ohlcv = MarketDataGenerator.generate_ranging_market(
            start_price=50000.0,
            num_candles=100,
            range_pct=0.02,
            mean_reversion_speed=0.15
        )
        
        prices = [candle[4] for candle in ohlcv]
        
        # Price should frequently return near the mean
        mean_price = 50000.0
        tolerance = 500  # Within 1% of mean
        
        near_mean_count = sum(1 for p in prices if abs(p - mean_price) < tolerance)
        
        # At least 30% of prices should be near the mean
        assert near_mean_count > len(prices) * 0.3
    
    def test_flash_crash_has_deep_drop(self):
        """Verify flash crash scenario includes significant drop."""
        ohlcv = MarketDataGenerator.generate_flash_crash(
            start_price=50000.0,
            num_candles=100,
            crash_depth=0.15
        )
        
        prices = [candle[4] for candle in ohlcv]
        min_price = min(prices)
        
        # Should drop at least 10%
        assert min_price < 50000 * 0.90
    
    def test_flash_crash_volume_spike(self):
        """Verify flash crash has volume spike during crash period."""
        ohlcv = MarketDataGenerator.generate_flash_crash(
            start_price=50000.0,
            num_candles=100,
            crash_candle=50,
            crash_depth=0.15
        )
        
        # Check volumes around crash candle
        crash_volumes = [ohlcv[i][5] for i in range(48, 56)]  # Candles 48-55
        normal_volumes = [ohlcv[i][5] for i in range(0, 40)]  # Pre-crash
        
        avg_crash_volume = sum(crash_volumes) / len(crash_volumes)
        avg_normal_volume = sum(normal_volumes) / len(normal_volumes)
        
        # Crash volume should be significantly higher
        assert avg_crash_volume > avg_normal_volume * 3
    
    def test_flash_crash_recovery_phase(self):
        """Verify flash crash includes recovery after the drop."""
        ohlcv = MarketDataGenerator.generate_flash_crash(
            start_price=50000.0,
            num_candles=100,
            crash_candle=50,
            crash_depth=0.15,
            recovery_speed=0.3
        )
        
        prices = [candle[4] for candle in ohlcv]
        
        # Find minimum price (crash bottom)
        min_idx = prices.index(min(prices))
        
        # Price should recover somewhat after the crash
        post_crash_prices = prices[min_idx+10:]  # 10 candles after bottom
        
        assert max(post_crash_prices) > min(prices) * 1.05  # At least 5% recovery
    
    def test_low_liquidity_has_wide_spreads(self):
        """Verify low liquidity scenario has wide bid-ask spreads."""
        ohlcv = MarketDataGenerator.generate_low_liquidity(
            start_price=50000.0,
            num_candles=100,
            spread_multiplier=3.0
        )
        
        # Check some candles have wide ranges
        wide_ranges = 0
        for candle in ohlcv:
            high, low = candle[2], candle[3]
            spread_pct = (high - low) / low
            if spread_pct > 0.003:  # >0.3% spread
                wide_ranges += 1
        
        # At least some candles should have wide spreads
        assert wide_ranges > 0
    
    def test_low_liquidity_has_price_gaps(self):
        """Verify low liquidity scenario includes price gaps."""
        ohlcv = MarketDataGenerator.generate_low_liquidity(
            start_price=50000.0,
            num_candles=100,
            gap_frequency=0.15  # 15% gap frequency
        )
        
        # Check for gaps between consecutive candles
        gaps_found = 0
        for i in range(1, len(ohlcv)):
            prev_close = ohlcv[i-1][4]
            curr_open = ohlcv[i][1]
            
            gap_pct = abs(curr_open - prev_close) / prev_close
            if gap_pct > 0.01:  # >1% gap
                gaps_found += 1
        
        # Should find some gaps with 15% frequency
        assert gaps_found > 0
    
    def test_low_liquidity_has_low_volume(self):
        """Verify low liquidity scenario has consistently low volume."""
        ohlcv = MarketDataGenerator.generate_low_liquidity(
            start_price=50000.0,
            num_candles=100
        )
        
        volumes = [candle[5] for candle in ohlcv]
        avg_volume = sum(volumes) / len(volumes)
        
        # Average volume should be very low (<300)
        assert avg_volume < 300
    
    def test_high_volatility_spike_magnitude(self):
        """Verify volatility spike scenario has large price movements."""
        ohlcv = MarketDataGenerator.generate_high_volatility_spike(
            start_price=50000.0,
            num_candles=100,
            spike_candles=[25, 50, 75],
            spike_magnitude=0.10  # 10% spikes
        )
        
        # Check candles at spike indices
        for spike_idx in [25, 50, 75]:
            candle = ohlcv[spike_idx]
            high, low = candle[2], candle[3]
            range_pct = (high - low) / low
            
            # Spike candles should have large ranges
            assert range_pct > 0.08  # At least 8% range
    
    def test_high_volatility_spike_volume_increase(self):
        """Verify volatility spikes coincide with volume increases."""
        ohlcv = MarketDataGenerator.generate_high_volatility_spike(
            start_price=50000.0,
            num_candles=100,
            spike_candles=[50],
            spike_magnitude=0.10
        )
        
        spike_volume = ohlcv[50][5]
        normal_volumes = [ohlcv[i][5] for i in range(0, 40)]
        avg_normal_volume = sum(normal_volumes) / len(normal_volumes)
        
        # Spike volume should be much higher
        assert spike_volume > avg_normal_volume * 3
    
    def test_all_generators_produce_valid_ohlcv_structure(self):
        """Verify all generators produce correctly structured OHLCV data."""
        generators = [
            MarketDataGenerator.generate_trending_market,
            MarketDataGenerator.generate_ranging_market,
            MarketDataGenerator.generate_flash_crash,
            MarketDataGenerator.generate_low_liquidity,
            MarketDataGenerator.generate_high_volatility_spike
        ]
        
        for generator in generators:
            ohlcv = generator(start_price=50000.0, num_candles=50)
            
            # Check structure
            assert len(ohlcv) == 50
            
            for candle in ohlcv:
                assert len(candle) == 6  # [timestamp, open, high, low, close, volume]
                
                timestamp, open_p, high, low, close, volume = candle
                
                # Validate basic constraints
                assert timestamp > 0
                assert open_p > 0
                assert high > 0
                assert low > 0
                assert close > 0
                assert volume > 0
                
                # High >= Low
                assert high >= low
                
                # High >= Open and High >= Close
                assert high >= open_p
                assert high >= close
                
                # Low <= Open and Low <= Close
                assert low <= open_p
                assert low <= close
    
    def test_generator_deterministic_with_seed(self):
        """Verify generators can produce reproducible results with seed."""
        # Set random seed for reproducibility
        random_state = random.getstate()
        
        try:
            random.seed(42)
            ohlcv1 = MarketDataGenerator.generate_trending_market(
                start_price=50000.0,
                num_candles=20
            )
            
            random.seed(42)
            ohlcv2 = MarketDataGenerator.generate_trending_market(
                start_price=50000.0,
                num_candles=20
            )
            
            # Results should be identical with same seed
            assert ohlcv1 == ohlcv2
        
        finally:
            random.setstate(random_state)
    
    def test_generator_handles_extreme_parameters(self):
        """Verify generators handle extreme parameter values gracefully."""
        # Very strong trend
        ohlcv = MarketDataGenerator.generate_trending_market(
            start_price=1000.0,
            num_candles=50,
            trend_strength=0.05  # 5% per candle (very strong)
        )
        
        assert len(ohlcv) == 50
        assert all(candle[4] > 0 for candle in ohlcv)  # All prices positive
        
        # Very wide range
        ohlcv = MarketDataGenerator.generate_ranging_market(
            start_price=50000.0,
            num_candles=50,
            range_pct=0.10  # ±10% range
        )
        
        assert len(ohlcv) == 50
        prices = [candle[4] for candle in ohlcv]
        assert min(prices) >= 45000  # Lower bound
        assert max(prices) <= 55000  # Upper bound
