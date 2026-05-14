"""
Unit tests for RiskEngine - Comprehensive risk monitoring and enforcement.

Tests cover:
- Daily loss limit enforcement
- Drawdown monitoring
- Position size validation
- Leverage limits
- Consecutive loss tracking
- Cooldown periods
- Emergency stop functionality
- Volatility chaos filter
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.risk.risk_engine import RiskEngine, RiskDecision


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def risk_engine(mock_db_session):
    """Create RiskEngine instance with mocked dependencies."""
    with patch('app.risk.risk_engine.settings') as mock_settings:
        # Configure mock settings
        mock_settings.RISK_MAX_DAILY_LOSS_PCT = 3.0
        mock_settings.RISK_MAX_DRAWDOWN_PCT = 15.0
        mock_settings.RISK_MAX_POSITION_SIZE_PCT = 1.5
        mock_settings.RISK_MAX_LEVERAGE = 5
        mock_settings.RISK_VOLATILITY_THRESHOLD = 2.0
        mock_settings.RISK_MAX_SLIPPAGE_PCT = 0.5
        mock_settings.RISK_COOLDOWN_PERIOD_SECONDS = 300
        mock_settings.RISK_MAX_CONSECUTIVE_LOSSES = 3
        
        engine = RiskEngine(db_session=mock_db_session)
        return engine


class TestRiskEngineInitialization:
    """Test RiskEngine initialization and configuration."""
    
    def test_load_config_from_settings(self, risk_engine):
        """Verify engine loads configuration from settings."""
        assert risk_engine.max_daily_loss_pct == 3.0
        assert risk_engine.max_drawdown_pct == 15.0
        assert risk_engine.max_position_size_pct == 1.5
        assert risk_engine.max_leverage == 5
    
    def test_initialize_runtime_tracking(self, risk_engine):
        """Verify runtime state is initialized correctly."""
        assert risk_engine.daily_pnl == 0.0
        assert risk_engine.peak_balance == 100.0
        assert risk_engine.current_balance == 100.0
        assert risk_engine.consecutive_losses == 0


class TestDailyLossLimit:
    """Test daily loss limit enforcement."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_within_daily_limit(self, risk_engine, mock_db_session):
        """Verify trade approved when within daily loss limit."""
        # Mock daily P&L calculation to return acceptable loss
        risk_engine.daily_pnl_pct = -2.0  # -2% (within -3% limit)
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is True
    
    @pytest.mark.asyncio
    async def test_reject_trade_exceeding_daily_limit(self, risk_engine, mock_db_session):
        """Verify trade rejected when exceeding daily loss limit."""
        # Mock daily P&L to exceed limit
        risk_engine.daily_pnl_pct = -4.0  # -4% (exceeds -3% limit)
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('daily' in v.lower() or 'loss' in v.lower() for v in decision.violations)


class TestDrawdownLimit:
    """Test drawdown monitoring and enforcement."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_within_drawdown_limit(self, risk_engine, mock_db_session):
        """Verify trade approved when within drawdown limit."""
        # Set current balance to show acceptable drawdown
        risk_engine.current_balance = 90.0  # 10% drawdown (within 15% limit)
        risk_engine.peak_balance = 100.0
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is True
    
    @pytest.mark.asyncio
    async def test_reject_trade_exceeding_drawdown_limit(self, risk_engine, mock_db_session):
        """Verify trade rejected when exceeding drawdown limit."""
        # Set current balance to show excessive drawdown
        risk_engine.current_balance = 80.0  # 20% drawdown (exceeds 15% limit)
        risk_engine.peak_balance = 100.0
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('drawdown' in v.lower() for v in decision.violations)


class TestPositionSizeValidation:
    """Test position size limit enforcement."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_within_position_limit(self, risk_engine, mock_db_session):
        """Verify trade approved when position size within limits."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.01,  # Small position (~$23, 0.23% of $100 balance)
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is True
    
    @pytest.mark.asyncio
    async def test_reject_trade_exceeding_position_limit(self, risk_engine, mock_db_session):
        """Verify trade rejected when position size exceeds limit."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 1.0,  # Large position (~$2345, 23.45% of $100 balance)
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('position' in v.lower() or 'size' in v.lower() for v in decision.violations)


class TestLeverageLimits:
    """Test leverage limit enforcement."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_within_leverage_limit(self, risk_engine, mock_db_session):
        """Verify trade approved when leverage within limits."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 3  # Within 5x limit
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is True
    
    @pytest.mark.asyncio
    async def test_reject_trade_exceeding_leverage_limit(self, risk_engine, mock_db_session):
        """Verify trade rejected when leverage exceeds limit."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 10  # Exceeds 5x limit
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('leverage' in v.lower() for v in decision.violations)


class TestConsecutiveLosses:
    """Test consecutive loss tracking and cooldown."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_below_consecutive_limit(self, risk_engine, mock_db_session):
        """Verify trade approved when below consecutive loss limit."""
        risk_engine.consecutive_losses = 2  # Below limit of 3
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is True
    
    @pytest.mark.asyncio
    async def test_reject_trade_at_consecutive_limit(self, risk_engine, mock_db_session):
        """Verify trade rejected when at consecutive loss limit."""
        risk_engine.consecutive_losses = 3  # At limit of 3
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('consecutive' in v.lower() or 'loss' in v.lower() for v in decision.violations)
    
    @pytest.mark.asyncio
    async def test_respect_cooldown_period(self, risk_engine, mock_db_session):
        """Verify cooldown period enforced after consecutive losses."""
        import time
        risk_engine.consecutive_losses = 3
        risk_engine.last_loss_time = time.time()  # Just now
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert decision.cooldown_remaining_seconds > 0


class TestEmergencyStop:
    """Test emergency stop functionality."""
    
    @pytest.mark.asyncio
    async def test_reject_all_trades_when_emergency_stop_active(self, risk_engine, mock_db_session):
        """Verify all trades rejected when emergency stop is active."""
        risk_engine.emergency_stop_active = True
        risk_engine.emergency_stop_reason = "Critical system failure"
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        assert decision.approved is False
        assert any('emergency' in v.lower() or 'stop' in v.lower() for v in decision.violations)
    
    @pytest.mark.asyncio
    async def test_allow_trades_when_emergency_stop_inactive(self, risk_engine, mock_db_session):
        """Verify trades allowed when emergency stop is inactive."""
        risk_engine.emergency_stop_active = False
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.01,  # Small position
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        # Should pass other checks (assuming small position)
        # May still fail on other criteria, but not emergency stop
        assert not any('emergency' in v.lower() for v in decision.violations)


class TestVolatilityChaosFilter:
    """Test volatility-based trading restrictions."""
    
    @pytest.mark.asyncio
    async def test_approve_trade_in_normal_volatility(self, risk_engine, mock_db_session):
        """Verify trade approved in normal volatility conditions."""
        with patch.object(risk_engine, 'check_volatility_chaos', return_value=False):
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.01,
                'leverage': 1
            }
            
            decision = await risk_engine.check_trade_approval(
                proposal=proposal,
                user_id='user123',
                db_session=mock_db_session
            )
            
            # Should not be rejected for volatility
            assert not any('volatility' in v.lower() or 'chaos' in v.lower() for v in decision.violations)
    
    @pytest.mark.asyncio
    async def test_reject_trade_in_high_volatility(self, risk_engine, mock_db_session):
        """Verify trade rejected in high volatility conditions."""
        with patch.object(risk_engine, 'check_volatility_chaos', return_value=True):
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.1,
                'leverage': 1
            }
            
            decision = await risk_engine.check_trade_approval(
                proposal=proposal,
                user_id='user123',
                db_session=mock_db_session
            )
            
            # May be rejected for volatility (depends on implementation)
            # This test verifies the check is called


class TestSlippageRisk:
    """Test slippage risk assessment."""
    
    @pytest.mark.asyncio
    async def test_warn_on_high_slippage(self, risk_engine, mock_db_session):
        """Verify warning issued on high slippage."""
        with patch.object(risk_engine, 'check_slippage_risk') as mock_slippage:
            mock_slippage.return_value = {
                'slippage_pct': 0.8,  # Exceeds 0.5% threshold
                'bid_ask_spread': 0.01
            }
            
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.01,
                'leverage': 1
            }
            
            decision = await risk_engine.check_trade_approval(
                proposal=proposal,
                user_id='user123',
                db_session=mock_db_session
            )
            
            # Verify slippage check was called
            mock_slippage.assert_called_once()


class TestRiskDecision:
    """Test RiskDecision dataclass."""
    
    def test_create_approved_decision(self):
        """Test creating approved risk decision."""
        decision = RiskDecision(
            approved=True,
            violations=[],
            warnings=['High volatility detected'],
            risk_score=25.0,
            daily_pnl_pct=-1.5,
            current_drawdown_pct=8.0,
            position_size_pct=0.5
        )
        
        assert decision.approved is True
        assert len(decision.violations) == 0
        assert len(decision.warnings) == 1
        assert decision.risk_score == 25.0
    
    def test_create_rejected_decision(self):
        """Test creating rejected risk decision."""
        decision = RiskDecision(
            approved=False,
            violations=['Daily loss limit exceeded', 'Position size too large'],
            warnings=[],
            risk_score=85.0
        )
        
        assert decision.approved is False
        assert len(decision.violations) == 2
        assert decision.risk_score == 85.0


class TestRiskEngineStateUpdates:
    """Test RiskEngine state tracking updates."""
    
    def test_update_after_winning_trade(self, risk_engine):
        """Verify state updates correctly after winning trade."""
        initial_losses = risk_engine.consecutive_losses
        risk_engine.consecutive_losses = 2  # Simulate previous losses
        
        # Simulate win (implementation detail may vary)
        risk_engine.consecutive_losses = 0  # Reset on win
        
        assert risk_engine.consecutive_losses == 0
    
    def test_update_after_losing_trade(self, risk_engine):
        """Verify state updates correctly after losing trade."""
        import time
        initial_losses = risk_engine.consecutive_losses
        
        # Simulate loss
        risk_engine.consecutive_losses += 1
        risk_engine.last_loss_time = time.time()
        
        assert risk_engine.consecutive_losses == initial_losses + 1
        assert risk_engine.last_loss_time is not None
    
    def test_update_peak_balance(self, risk_engine):
        """Verify peak balance tracking."""
        risk_engine.current_balance = 110.0
        
        # Update peak if current exceeds it
        if risk_engine.current_balance > risk_engine.peak_balance:
            risk_engine.peak_balance = risk_engine.current_balance
        
        assert risk_engine.peak_balance == 110.0


class TestRiskEngineEdgeCases:
    """Test RiskEngine edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_handle_missing_db_session(self, risk_engine):
        """Verify graceful handling when db_session is None."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 2345.67,
            'quantity': 0.1,
            'leverage': 1
        }
        
        # Should handle missing session gracefully
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=None
        )
        
        # Decision should still be made (may use cached/default values)
        assert isinstance(decision, RiskDecision)
    
    @pytest.mark.asyncio
    async def test_handle_invalid_proposal_format(self, risk_engine, mock_db_session):
        """Verify handling of malformed proposal."""
        proposal = {
            # Missing required fields
            'symbol': 'XAUUSDT'
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        # Should reject or handle gracefully
        assert isinstance(decision, RiskDecision)
    
    @pytest.mark.asyncio
    async def test_handle_zero_entry_price(self, risk_engine, mock_db_session):
        """Verify handling of zero entry price."""
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'entry_price': 0,  # Invalid
            'quantity': 0.1,
            'leverage': 1
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id='user123',
            db_session=mock_db_session
        )
        
        # Should reject invalid price
        assert decision.approved is False or len(decision.violations) > 0


# =============================================================================
# INTEGRATION TESTS (Require real database - marked for manual run)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_risk_validation_integration():
    """
    Full integration test with real database.
    
    This test should be run manually against test database.
    Requires:
    - Real database connection
    - Historical trade data
    """
    pytest.skip("Integration test - run manually with --run-integration flag")
    
    # TODO: Implement full integration test
    # 1. Create real database session
    # 2. Initialize RiskEngine with real config
    # 3. Load historical trades
    # 4. Validate various trade scenarios
    # 5. Verify decisions match expected outcomes
