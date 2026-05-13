"""
Unit tests for Risk Engine validation logic.

Tests cover all risk management rules:
- Daily loss limit enforcement (-3%)
- Max drawdown monitoring (15%)
- Position size caps (1.5% per trade)
- Leverage limits (5x max)
- Cooldown periods after consecutive losses
- Risk score calculation
- Trade approval when all checks pass

Uses asyncio.run() to test async check_trade_approval methods.
"""
import pytest
import asyncio
import time
from app.risk.risk_engine import RiskEngine


class TestRiskEngineValidation:
    """Test RiskEngine trade approval logic."""
    
    @pytest.fixture
    def risk_engine(self):
        """Create risk engine without DB session."""
        return RiskEngine(db_session=None)
    
    def test_daily_loss_limit_rejection(self, risk_engine):
        """Test trade rejected when daily loss limit reached."""
        risk_engine.daily_pnl_pct = -0.035  # -3.5% (limit is -3%)
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={'entry_price': 50000, 'quantity': 0.01, 'leverage': 1}
        ))
        
        assert decision.approved == False
        assert any('Daily loss limit' in v for v in decision.violations)
    
    def test_drawdown_limit_rejection(self, risk_engine):
        """Test trade rejected when drawdown exceeds limit."""
        risk_engine.current_balance = 85
        risk_engine.peak_balance = 100  # 15% drawdown
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={'entry_price': 50000, 'quantity': 0.01, 'leverage': 1}
        ))
        
        assert decision.approved == False
        assert any('drawdown' in v.lower() for v in decision.violations)
    
    def test_position_size_rejection(self, risk_engine):
        """Test trade rejected when position too large."""
        risk_engine.current_balance = 1000
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={
                'entry_price': 50000,
                'quantity': 1.0,  # $50k position
                'leverage': 5     # $250k notional
            }
        ))
        
        assert decision.approved == False
        assert any('Position size' in v for v in decision.violations)
    
    def test_leverage_limit_rejection(self, risk_engine):
        """Test trade rejected when leverage exceeds max."""
        risk_engine.current_balance = 10000  # Set realistic balance
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={
                'entry_price': 50000,
                'quantity': 0.0001,  # Very small position ($5 value, 0.05% of balance)
                'leverage': 10  # Exceeds 5x limit
            }
        ))
        
        assert decision.approved == False
        assert any('Leverage' in v for v in decision.violations)
    
    def test_cooldown_period_enforcement(self, risk_engine):
        """Test trade rejected during cooldown after consecutive losses."""
        risk_engine.current_balance = 10000  # Set realistic balance
        risk_engine.consecutive_losses = 3
        risk_engine.last_loss_time = time.time() - 100  # 100s ago
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={'entry_price': 50000, 'quantity': 0.0001, 'leverage': 1}  # Tiny position
        ))
        
        # Should be in cooldown (300s default)
        assert decision.approved == False
        assert decision.cooldown_remaining_seconds > 0
        assert any('Cooldown' in v for v in decision.violations)
    
    def test_approved_when_all_checks_pass(self, risk_engine):
        """Test trade approved when all risk checks pass."""
        risk_engine.current_balance = 10000
        risk_engine.peak_balance = 10000
        risk_engine.daily_pnl_pct = 0.0
        risk_engine.consecutive_losses = 0
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={
                'entry_price': 50000,
                'quantity': 0.0001,  # Very small position ($5 value)
                'leverage': 2
            }
        ))
        
        assert decision.approved == True
        assert len(decision.violations) == 0
        assert 0 <= decision.risk_score <= 100
    
    def test_risk_score_calculation(self, risk_engine):
        """Test risk score increases with risk factors."""
        # Low risk scenario
        risk_engine.daily_pnl_pct = 0.0
        risk_engine.current_balance = 10000
        risk_engine.peak_balance = 10000
        risk_engine.consecutive_losses = 0
        
        decision_low = asyncio.run(risk_engine.check_trade_approval({
            'entry_price': 50000, 'quantity': 0.0001, 'leverage': 1
        }))
        
        # High risk scenario
        risk_engine.daily_pnl_pct = -0.02  # Approaching limit
        risk_engine.current_balance = 9000
        risk_engine.consecutive_losses = 2
        
        decision_high = asyncio.run(risk_engine.check_trade_approval({
            'entry_price': 50000, 'quantity': 0.0001, 'leverage': 3
        }))
        
        assert decision_high.risk_score > decision_low.risk_score
    
    def test_warnings_for_approaching_limits(self, risk_engine):
        """Test warnings generated when approaching risk limits."""
        risk_engine.daily_pnl_pct = -0.025  # 2.5% loss (75% of 3% limit)
        risk_engine.current_balance = 8700
        risk_engine.peak_balance = 10000  # 13% drawdown (approaching 15%)
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={'entry_price': 50000, 'quantity': 0.0001, 'leverage': 1}  # Tiny position
        ))
        
        assert decision.approved == True  # Still approved
        assert len(decision.warnings) > 0  # But has warnings
    
    def test_consecutive_losses_tracking(self, risk_engine):
        """Test consecutive loss tracking and reset on win."""
        # Record 2 losses
        asyncio.run(risk_engine.record_trade_outcome(won=False, strategy_name='test'))
        asyncio.run(risk_engine.record_trade_outcome(won=False, strategy_name='test'))
        
        assert risk_engine.consecutive_losses == 2
        
        # Win resets counter
        asyncio.run(risk_engine.record_trade_outcome(won=True, strategy_name='test'))
        
        assert risk_engine.consecutive_losses == 0
    
    def test_daily_pnl_update(self, risk_engine):
        """Test daily P&L tracking updates correctly."""
        initial_balance = risk_engine.current_balance
        
        asyncio.run(risk_engine.update_daily_pnl({
            'profit': 100,
            'profit_pct': 0.01
        }))
        
        assert risk_engine.current_balance == initial_balance + 100
        assert risk_engine.daily_pnl == 100
    
    def test_peak_balance_tracking(self, risk_engine):
        """Test peak balance updates on new highs."""
        risk_engine.current_balance = 10000
        risk_engine.peak_balance = 10000
        
        # Profit increases both current and peak
        asyncio.run(risk_engine.update_daily_pnl({'profit': 500, 'profit_pct': 0.05}))
        
        assert risk_engine.current_balance == 10500
        assert risk_engine.peak_balance == 10500
        
        # Loss decreases current but not peak
        asyncio.run(risk_engine.update_daily_pnl({'profit': -200, 'profit_pct': -0.02}))
        
        assert risk_engine.current_balance == 10300
        assert risk_engine.peak_balance == 10500  # Unchanged
    
    def test_risk_metrics_retrieval(self, risk_engine):
        """Test risk metrics dashboard retrieval."""
        risk_engine.current_balance = 10000
        risk_engine.peak_balance = 10500
        risk_engine.daily_pnl = -200
        risk_engine.daily_pnl_pct = -0.02
        risk_engine.consecutive_losses = 1
        
        metrics = asyncio.run(risk_engine.get_risk_metrics())
        
        assert 'daily_pnl' in metrics
        assert 'current_balance' in metrics
        assert 'peak_balance' in metrics
        assert 'consecutive_losses' in metrics
        assert 'cooldown_active' in metrics
        assert 'limits' in metrics
        
        assert metrics['current_balance'] == 10000
        assert metrics['consecutive_losses'] == 1
    
    def test_cooldown_expires_after_timeout(self, risk_engine):
        """Test cooldown period expires after configured timeout."""
        risk_engine.current_balance = 10000  # Set realistic balance
        risk_engine.consecutive_losses = 3
        risk_engine.last_loss_time = time.time() - 400  # 400s ago (> 300s timeout)
        
        decision = asyncio.run(risk_engine.check_trade_approval(
            proposal={'entry_price': 50000, 'quantity': 0.0001, 'leverage': 1}  # Tiny position
        ))
        
        # Cooldown should have expired
        assert decision.approved == True
        assert risk_engine.consecutive_losses == 0  # Reset after expiry
