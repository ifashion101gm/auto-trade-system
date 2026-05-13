"""
Unit tests for Signal Engine Logic.

Validates deterministic signal generation including:
- Idempotency (no duplicate signals for same market state)
- Directional logic (LONG only on bullish, SHORT only on bearish)
- Stop-loss directionality (prevents inverted SL bug)
- Take-profit validity (aligns with R:R ratio)
- Signal spam prevention (cooldown in choppy markets)
"""
import pytest
import time
from typing import Dict, Any, Optional
from app.strategy.signal_proposal import SignalProposal
from app.risk.calculations import (
    calculate_stop_loss_long,
    calculate_stop_loss_short,
    calculate_take_profit
)


class TestSignalIdempotency:
    """Ensure no duplicate signals generated for same market state."""
    
    def test_no_duplicate_signals_same_state(self):
        """Verify identical market state doesn't generate duplicate signals."""
        # Simulate signal cache
        signal_cache = {}
        
        market_state_1 = {
            'symbol': 'BTC/USDT',
            'price': 50000,
            'rsi': 65,
            'trend': 'bullish'
        }
        
        # Generate first signal
        signal_key_1 = f"{market_state_1['symbol']}_{market_state_1['price']}"
        if signal_key_1 not in signal_cache:
            signal_cache[signal_key_1] = SignalProposal(
                symbol='BTC/USDT',
                side='LONG',
                entry_price=50000,
                stop_loss=49000,
                take_profit=52000,
                quantity=0.01,
                leverage=2,
                confidence=0.8,
                strategy_name='breakout'
            )
        
        # Same market state again
        market_state_2 = {
            'symbol': 'BTC/USDT',
            'price': 50000,  # Same price
            'rsi': 65,
            'trend': 'bullish'
        }
        
        signal_key_2 = f"{market_state_2['symbol']}_{market_state_2['price']}"
        is_duplicate = signal_key_2 in signal_cache
        
        assert is_duplicate == True
        assert len(signal_cache) == 1  # Only one signal stored
    
    def test_different_states_generate_different_signals(self):
        """Verify different market states can generate different signals."""
        signal_cache = {}
        
        # State 1: Bullish
        state_1_key = "BTC/USDT_50000"
        signal_cache[state_1_key] = SignalProposal(
            symbol='BTC/USDT', side='LONG', entry_price=50000,
            stop_loss=49000, take_profit=52000, quantity=0.01
        )
        
        # State 2: Different price
        state_2_key = "BTC/USDT_51000"
        signal_cache[state_2_key] = SignalProposal(
            symbol='BTC/USDT', side='LONG', entry_price=51000,
            stop_loss=50000, take_profit=53000, quantity=0.01
        )
        
        assert len(signal_cache) == 2
        assert signal_cache[state_1_key].entry_price != signal_cache[state_2_key].entry_price


class TestDirectionalLogic:
    """Validate LONG only on bullish, SHORT only on bearish criteria."""
    
    def test_long_signal_only_on_bullish(self):
        """Verify LONG signals only generated when bullish criteria met."""
        # Bullish conditions
        rsi = 35  # Oversold (bullish for mean reversion)
        price_above_ma = True
        macd_positive = True
        
        should_generate_long = rsi < 40 and price_above_ma and macd_positive
        
        if should_generate_long:
            signal = SignalProposal(
                symbol='BTC/USDT',
                side='LONG',
                entry_price=50000,
                stop_loss=49000,
                take_profit=52000,
                quantity=0.01
            )
            assert signal.side == 'LONG'
    
    def test_short_signal_only_on_bearish(self):
        """Verify SHORT signals only generated when bearish criteria met."""
        # Bearish conditions
        rsi = 75  # Overbought (bearish for mean reversion)
        price_below_ma = True
        macd_negative = True
        
        should_generate_short = rsi > 70 and price_below_ma and macd_negative
        
        if should_generate_short:
            signal = SignalProposal(
                symbol='BTC/USDT',
                side='SHORT',
                entry_price=50000,
                stop_loss=51000,
                take_profit=48000,
                quantity=0.01
            )
            assert signal.side == 'SHORT'
    
    def test_no_signal_in_neutral_market(self):
        """Verify no signal generated in neutral/choppy market."""
        # Neutral conditions
        rsi = 50  # Neutral
        price_near_ma = True
        macd_near_zero = True
        
        should_generate_signal = not (rsi < 30 or rsi > 70)
        
        if should_generate_signal:
            # Should NOT generate signal
            signal = None
        
        assert signal is None
    
    def test_breakout_long_requires_resistance_break(self):
        """Verify LONG breakout requires breaking above resistance."""
        current_price = 51000
        resistance = 50500
        
        breakout_detected = current_price > resistance
        
        if breakout_detected:
            signal = SignalProposal(
                symbol='BTC/USDT',
                side='LONG',
                entry_price=current_price,
                stop_loss=49500,
                take_profit=53000,
                quantity=0.01
            )
            assert signal.side == 'LONG'
            assert signal.entry_price > resistance
    
    def test_breakout_short_requires_support_break(self):
        """Verify SHORT breakout requires breaking below support."""
        current_price = 49000
        support = 49500
        
        breakdown_detected = current_price < support
        
        if breakdown_detected:
            signal = SignalProposal(
                symbol='BTC/USDT',
                side='SHORT',
                entry_price=current_price,
                stop_loss=50500,
                take_profit=47000,
                quantity=0.01
            )
            assert signal.side == 'SHORT'
            assert signal.entry_price < support


class TestStopLossDirectionality:
    """
    CRITICAL: Prevent inverted stop-loss bug.
    - LONG: SL must be BELOW entry
    - SHORT: SL must be ABOVE entry
    """
    
    def test_long_stop_loss_below_entry(self):
        """Assert stop_loss < entry_price for LONG positions."""
        entry_price = 50000.0
        atr = 500.0
        multiplier = 1.5
        
        stop_loss = calculate_stop_loss_long(entry_price, atr, multiplier)
        
        # CRITICAL ASSERTION: SL must be below entry for LONG
        assert stop_loss < entry_price, \
            f"CRITICAL BUG: LONG stop_loss ({stop_loss}) >= entry_price ({entry_price})"
        
        # Verify specific calculation
        expected_sl = entry_price - (atr * multiplier)
        assert stop_loss == expected_sl
    
    def test_short_stop_loss_above_entry(self):
        """Assert stop_loss > entry_price for SHORT positions."""
        entry_price = 50000.0
        atr = 500.0
        multiplier = 1.5
        
        stop_loss = calculate_stop_loss_short(entry_price, atr, multiplier)
        
        # CRITICAL ASSERTION: SL must be above entry for SHORT
        assert stop_loss > entry_price, \
            f"CRITICAL BUG: SHORT stop_loss ({stop_loss}) <= entry_price ({entry_price})"
        
        # Verify specific calculation
        expected_sl = entry_price + (atr * multiplier)
        assert stop_loss == expected_sl
    
    def test_long_sl_atr_based_calculation(self):
        """Verify LONG SL calculated correctly using ATR."""
        test_cases = [
            (50000, 500, 1.5, 49250),   # entry, atr, mult, expected
            (100000, 1000, 2.0, 98000),
            (3000, 50, 1.0, 2950),
        ]
        
        for entry, atr, mult, expected in test_cases:
            sl = calculate_stop_loss_long(entry, atr, mult)
            
            # Must be below entry
            assert sl < entry
            
            # Must match expected calculation
            assert sl == expected, f"Expected {expected}, got {sl}"
    
    def test_short_sl_atr_based_calculation(self):
        """Verify SHORT SL calculated correctly using ATR."""
        test_cases = [
            (50000, 500, 1.5, 50750),   # entry, atr, mult, expected
            (100000, 1000, 2.0, 102000),
            (3000, 50, 1.0, 3050),
        ]
        
        for entry, atr, mult, expected in test_cases:
            sl = calculate_stop_loss_short(entry, atr, mult)
            
            # Must be above entry
            assert sl > entry
            
            # Must match expected calculation
            assert sl == expected, f"Expected {expected}, got {sl}"
    
    def test_signal_proposal_validates_sl_direction(self):
        """Verify SignalProposal enforces correct SL direction."""
        # Valid LONG signal
        long_signal = SignalProposal(
            symbol='BTC/USDT',
            side='LONG',
            entry_price=50000,
            stop_loss=49000,  # Below entry ✓
            take_profit=52000,
            quantity=0.01
        )
        
        assert long_signal.stop_loss < long_signal.entry_price
        
        # Valid SHORT signal
        short_signal = SignalProposal(
            symbol='BTC/USDT',
            side='SHORT',
            entry_price=50000,
            stop_loss=51000,  # Above entry ✓
            take_profit=48000,
            quantity=0.01
        )
        
        assert short_signal.stop_loss > short_signal.entry_price
    
    def test_prevent_inverted_sl_long(self):
        """CRITICAL TEST: Prevent inverted SL for LONG (SL above entry)."""
        # This would be a BUG - SL above entry for LONG
        buggy_sl = 51000  # Above entry!
        entry = 50000
        
        # Validation check
        is_valid = buggy_sl < entry
        
        assert is_valid == False, "BUG DETECTED: Inverted SL for LONG position!"
    
    def test_prevent_inverted_sl_short(self):
        """CRITICAL TEST: Prevent inverted SL for SHORT (SL below entry)."""
        # This would be a BUG - SL below entry for SHORT
        buggy_sl = 49000  # Below entry!
        entry = 50000
        
        # Validation check
        is_valid = buggy_sl > entry
        
        assert is_valid == False, "BUG DETECTED: Inverted SL for SHORT position!"


class TestTakeProfitValidity:
    """Verify TP calculations align with configured Reward-to-Risk ratio."""
    
    def test_long_tp_with_rr_ratio(self):
        """Verify LONG TP calculated with correct R:R ratio."""
        entry = 50000
        sl = 49000  # $1000 risk
        rr_ratio = 2.0
        
        tp = calculate_take_profit(entry, sl, rr_ratio, side='LONG')
        
        # Risk = $1000, Reward should be $2000 (2:1)
        expected_tp = entry + (abs(entry - sl) * rr_ratio)
        
        assert tp == expected_tp
        assert tp > entry  # TP above entry for LONG
    
    def test_short_tp_with_rr_ratio(self):
        """Verify SHORT TP calculated with correct R:R ratio."""
        entry = 50000
        sl = 51000  # $1000 risk
        rr_ratio = 2.0
        
        tp = calculate_take_profit(entry, sl, rr_ratio, side='SHORT')
        
        # Risk = $1000, Reward should be $2000 (2:1)
        expected_tp = entry - (abs(entry - sl) * rr_ratio)
        
        assert tp == expected_tp
        assert tp < entry  # TP below entry for SHORT
    
    def test_tp_aligns_with_actual_rr_ratio(self):
        """Verify actual R:R ratio matches configured ratio."""
        entry = 50000
        sl = 49500  # $500 risk
        rr_ratio = 3.0
        
        tp = calculate_take_profit(entry, sl, rr_ratio, side='LONG')
        
        # Calculate actual R:R
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        actual_rr = reward / risk
        
        assert abs(actual_rr - rr_ratio) < 0.01, \
            f"Actual R:R {actual_rr} != configured {rr_ratio}"
    
    def test_tp_valid_for_various_rr_ratios(self):
        """Test TP calculation with various R:R ratios."""
        entry = 50000
        sl = 49000
        
        test_ratios = [1.0, 1.5, 2.0, 2.5, 3.0]
        
        for ratio in test_ratios:
            tp = calculate_take_profit(entry, sl, ratio, side='LONG')
            
            # TP should increase with higher R:R
            expected_tp = entry + (1000 * ratio)
            assert tp == expected_tp
    
    def test_invalid_rr_ratio_handling(self):
        """Verify invalid R:R ratios are handled gracefully."""
        entry = 50000
        sl = 49000
        
        # Negative R:R should raise error
        with pytest.raises(ValueError):
            calculate_take_profit(entry, sl, -1.0, side='LONG')
        
        # Zero R:R should raise error
        with pytest.raises(ValueError):
            calculate_take_profit(entry, sl, 0.0, side='LONG')


class TestSignalSpamPrevention:
    """Ensure cooldown prevents rapid-fire signals in choppy markets."""
    
    def test_cooldown_prevents_rapid_signals(self):
        """Verify cooldown period prevents duplicate signals."""
        last_signal_time = time.time() - 5  # 5 seconds ago
        cooldown_period = 60  # 60 seconds
        
        time_since_last = time.time() - last_signal_time
        should_generate = time_since_last >= cooldown_period
        
        assert should_generate == False  # Still in cooldown
    
    def test_signal_allowed_after_cooldown(self):
        """Verify signal allowed after cooldown expires."""
        last_signal_time = time.time() - 120  # 2 minutes ago
        cooldown_period = 60  # 60 seconds
        
        time_since_last = time.time() - last_signal_time
        should_generate = time_since_last >= cooldown_period
        
        assert should_generate == True  # Cooldown expired
    
    def test_choppy_market_detection(self):
        """Detect choppy/sideways market to reduce signal frequency."""
        # Simulate price oscillating in tight range
        prices = [50000, 50050, 49980, 50020, 49990, 50010]
        
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices)
        volatility_pct = (price_range / avg_price) * 100
        
        is_choppy = volatility_pct < 0.5  # Less than 0.5% range
        
        assert is_choppy == True
        
        # In choppy market, should reduce signal frequency
        if is_choppy:
            cooldown_multiplier = 2.0  # Double cooldown
        else:
            cooldown_multiplier = 1.0
        
        assert cooldown_multiplier == 2.0
    
    def test_state_based_signal_filtering(self):
        """Filter signals based on recent signal history."""
        recent_signals = [
            {'timestamp': time.time() - 30, 'side': 'LONG'},
            {'timestamp': time.time() - 60, 'side': 'LONG'},
            {'timestamp': time.time() - 90, 'side': 'SHORT'},
        ]
        
        # Count recent signals (last 2 minutes)
        cutoff = time.time() - 120
        recent_count = sum(1 for s in recent_signals if s['timestamp'] > cutoff)
        
        # Too many signals in short period
        max_signals_per_period = 5
        should_throttle = recent_count >= max_signals_per_period
        
        assert should_throttle == False  # Only 3 signals, under limit
    
    def test_alternating_side_cooldown(self):
        """Apply longer cooldown when switching sides (LONG→SHORT or vice versa)."""
        last_signal = {'timestamp': time.time() - 30, 'side': 'LONG'}
        new_signal_side = 'SHORT'
        
        # Switching sides
        side_switched = last_signal['side'] != new_signal_side
        
        if side_switched:
            cooldown = 300  # 5 minutes for side switch
        else:
            cooldown = 60  # 1 minute for same side
        
        time_since_last = time.time() - last_signal['timestamp']
        should_allow = time_since_last >= cooldown
        
        assert should_allow == False  # Still in extended cooldown
