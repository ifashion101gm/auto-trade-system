"""
Unit tests for risk calculation functions.

Tests cover:
- Stop-loss calculation (LONG and SHORT)
- Take-profit calculation with reward-to-risk ratios
- Dynamic position sizing based on risk percentage
- Risk percentage validation
- Drawdown calculation
- Maximum position value calculation

All tests use deterministic, static data with known expected outputs.
"""
import pytest
from app.risk.calculations import (
    calculate_stop_loss_long,
    calculate_stop_loss_short,
    calculate_take_profit,
    calculate_position_size,
    validate_risk_percentage,
    calculate_max_position_value,
    calculate_drawdown
)
from tests.conftest import assert_approx_equal


class TestStopLossCalculation:
    """Test stop-loss price calculations."""
    
    def test_sl_long_atr_based(self):
        """Test LONG stop-loss below entry using ATR."""
        sl = calculate_stop_loss_long(entry_price=50000, atr=500, multiplier=1.5)
        assert sl == 49250.0  # 50000 - (500 * 1.5)
        assert sl < 50000
    
    def test_sl_short_atr_based(self):
        """Test SHORT stop-loss above entry using ATR."""
        sl = calculate_stop_loss_short(entry_price=50000, atr=500, multiplier=1.5)
        assert sl == 50750.0  # 50000 + (500 * 1.5)
        assert sl > 50000
    
    def test_sl_long_different_multipliers(self):
        """Test LONG stop-loss with different ATR multipliers."""
        entry = 50000
        atr = 500
        
        sl_conservative = calculate_stop_loss_long(entry, atr, multiplier=2.0)
        sl_aggressive = calculate_stop_loss_long(entry, atr, multiplier=1.0)
        
        assert sl_conservative < sl_aggressive  # Wider stop is lower
        assert sl_conservative == 49000.0
        assert sl_aggressive == 49500.0
    
    def test_sl_short_different_multipliers(self):
        """Test SHORT stop-loss with different ATR multipliers."""
        entry = 50000
        atr = 500
        
        sl_conservative = calculate_stop_loss_short(entry, atr, multiplier=2.0)
        sl_aggressive = calculate_stop_loss_short(entry, atr, multiplier=1.0)
        
        assert sl_conservative > sl_aggressive  # Wider stop is higher
        assert sl_conservative == 51000.0
        assert sl_aggressive == 50500.0
    
    def test_sl_zero_atr(self):
        """Test stop-loss with zero ATR (no volatility)."""
        sl_long = calculate_stop_loss_long(50000, 0, 1.5)
        sl_short = calculate_stop_loss_short(50000, 0, 1.5)
        
        assert sl_long == 50000.0
        assert sl_short == 50000.0


class TestTakeProfitCalculation:
    """Test take-profit price calculations."""
    
    def test_tp_long_reward_risk(self):
        """Test LONG take-profit with 2:1 R:R ratio."""
        entry = 50000
        sl = 49000  # $1000 risk
        tp = calculate_take_profit(entry, sl, reward_risk_ratio=2.0, side='LONG')
        assert tp == 52000.0  # $2000 reward
    
    def test_tp_short_reward_risk(self):
        """Test SHORT take-profit with 2:1 R:R ratio."""
        entry = 50000
        sl = 51000  # $1000 risk
        tp = calculate_take_profit(entry, sl, reward_risk_ratio=2.0, side='SHORT')
        assert tp == 48000.0  # $2000 reward below entry
    
    def test_tp_different_ratios(self):
        """Test take-profit with different R:R ratios."""
        entry = 50000
        sl = 49000  # $1000 risk
        
        tp_1_5 = calculate_take_profit(entry, sl, reward_risk_ratio=1.5, side='LONG')
        tp_2_0 = calculate_take_profit(entry, sl, reward_risk_ratio=2.0, side='LONG')
        tp_3_0 = calculate_take_profit(entry, sl, reward_risk_ratio=3.0, side='LONG')
        
        assert tp_1_5 == 51500.0
        assert tp_2_0 == 52000.0
        assert tp_3_0 == 53000.0
    
    def test_tp_invalid_ratio_raises(self):
        """Test invalid R:R ratio raises error."""
        with pytest.raises(ValueError):
            calculate_take_profit(50000, 49000, reward_risk_ratio=-1.0)
        
        with pytest.raises(ValueError):
            calculate_take_profit(50000, 49000, reward_risk_ratio=0)
    
    def test_tp_symmetry(self):
        """Test that LONG and SHORT TP are symmetric around entry."""
        entry = 50000
        risk = 1000
        
        sl_long = entry - risk
        sl_short = entry + risk
        
        tp_long = calculate_take_profit(entry, sl_long, 2.0, 'LONG')
        tp_short = calculate_take_profit(entry, sl_short, 2.0, 'SHORT')
        
        # Both should be equidistant from entry
        assert abs(tp_long - entry) == abs(tp_short - entry)
        assert tp_long == 52000.0
        assert tp_short == 48000.0


class TestPositionSizing:
    """Test dynamic position sizing calculations."""
    
    def test_basic_position_size(self):
        """Test basic position sizing with 2% risk."""
        result = calculate_position_size(
            account_balance=10000,
            risk_per_trade_pct=0.02,
            entry_price=50000,
            stop_loss_price=49000
        )
        assert result['risk_amount'] == 200.0  # 2% of $10k
        assert result['quantity'] > 0
        assert result['leverage'] >= 1
    
    def test_position_size_with_confidence(self):
        """Test position sizing adjusts with confidence."""
        full_conf = calculate_position_size(
            10000, 0.02, 50000, 49000, confidence=1.0
        )
        half_conf = calculate_position_size(
            10000, 0.02, 50000, 49000, confidence=0.5
        )
        
        assert half_conf['risk_amount'] == full_conf['risk_amount'] * 0.5
        assert half_conf['quantity'] < full_conf['quantity']
    
    def test_position_size_leverage_cap(self):
        """Test leverage is capped at maximum."""
        result = calculate_position_size(
            account_balance=1000,
            risk_per_trade_pct=0.02,
            entry_price=50000,
            stop_loss_price=49900,  # Very tight SL = large position
            max_leverage=5
        )
        assert result['leverage'] <= 5
    
    def test_position_size_zero_sl_raises(self):
        """Test error when SL equals entry."""
        with pytest.raises(ValueError, match="cannot equal"):
            calculate_position_size(10000, 0.02, 50000, 50000)
    
    def test_position_size_negative_price_raises(self):
        """Test error with negative prices."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_position_size(10000, 0.02, -50000, 49000)
    
    def test_position_size_tight_stop_large_position(self):
        """Test that tight stop-loss results in larger position."""
        tight_sl = calculate_position_size(10000, 0.02, 50000, 49900)
        wide_sl = calculate_position_size(10000, 0.02, 50000, 49000)
        
        assert tight_sl['quantity'] > wide_sl['quantity']
        assert tight_sl['risk_amount'] == wide_sl['risk_amount']  # Same risk amount
    
    def test_position_size_complete_output(self):
        """Test all fields in position size output."""
        result = calculate_position_size(
            account_balance=10000,
            risk_per_trade_pct=0.02,
            entry_price=50000,
            stop_loss_price=49000
        )
        
        assert 'quantity' in result
        assert 'position_value' in result
        assert 'risk_amount' in result
        assert 'leverage' in result
        assert 'risk_per_unit' in result
        
        assert result['risk_per_unit'] == 1000.0  # |50000 - 49000|
        assert result['position_value'] == result['quantity'] * 50000


class TestRiskValidation:
    """Test risk percentage validation."""
    
    def test_valid_risk_percentage(self):
        """Test valid risk percentages pass validation."""
        assert validate_risk_percentage(0.02) == True
        assert validate_risk_percentage(0.01) == True
        assert validate_risk_percentage(0.001) == True  # Minimum
        assert validate_risk_percentage(0.05) == True   # Maximum
    
    def test_risk_too_low_raises(self):
        """Test error when risk is too low."""
        with pytest.raises(ValueError, match="out of bounds"):
            validate_risk_percentage(0.0005)  # 0.05%
    
    def test_risk_too_high_raises(self):
        """Test error when risk is too high."""
        with pytest.raises(ValueError, match="out of bounds"):
            validate_risk_percentage(0.10)  # 10%
    
    def test_custom_bounds(self):
        """Test validation with custom min/max bounds."""
        # Should pass with wider bounds
        assert validate_risk_percentage(0.08, min_pct=0.001, max_pct=0.10) == True
        
        # Should fail with tighter bounds
        with pytest.raises(ValueError):
            validate_risk_percentage(0.08, min_pct=0.001, max_pct=0.05)


class TestMaxPositionValue:
    """Test maximum position value calculation."""
    
    def test_max_position_basic(self):
        """Test basic max position calculation."""
        max_pos = calculate_max_position_value(10000, 0.015)
        assert max_pos == 150.0  # 1.5% of $10k
    
    def test_max_position_different_percentages(self):
        """Test with different percentage values."""
        assert calculate_max_position_value(10000, 0.01) == 100.0
        assert calculate_max_position_value(10000, 0.02) == 200.0
        assert calculate_max_position_value(10000, 0.05) == 500.0


class TestDrawdownCalculation:
    """Test drawdown calculation."""
    
    def test_drawdown_basic(self):
        """Test basic drawdown calculation."""
        drawdown = calculate_drawdown(9000, 10000)
        assert drawdown == 0.10  # 10% drawdown
    
    def test_drawdown_no_loss(self):
        """Test zero drawdown when at peak."""
        drawdown = calculate_drawdown(10000, 10000)
        assert drawdown == 0.0
    
    def test_drawdown_profit(self):
        """Test no negative drawdown when above peak."""
        drawdown = calculate_drawdown(11000, 10000)
        assert drawdown == 0.0  # Never negative
    
    def test_drawdown_major_loss(self):
        """Test large drawdown calculation."""
        drawdown = calculate_drawdown(5000, 10000)
        assert drawdown == 0.50  # 50% drawdown
    
    def test_drawdown_zero_peak(self):
        """Test drawdown with zero peak balance."""
        drawdown = calculate_drawdown(1000, 0)
        assert drawdown == 0.0
