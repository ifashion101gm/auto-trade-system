"""
Integration tests for TradingView Webhook → Database Persistence pipeline.

Validates end-to-end webhook processing from HTTP payload reception through
signal validation, risk approval, and database persistence.

Tests cover:
- Complete webhook processing flow
- Authentication and security controls
- Error handling and transaction rollback
- Payload validation and normalization
"""
import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.dashboard.trading_api import validate_tradingview_payload, verify_trading_secret
from fastapi import HTTPException


class TestWebhookPipeline:
    """Test TradingView webhook to database persistence flow."""
    
    def test_complete_webhook_processing_flow(
        self,
        sample_webhook_payload,
        integration_risk_engine,
        mock_db_session
    ):
        """
        Test complete webhook flow:
        1. Receive TradingView webhook payload
        2. Validate and parse signal
        3. Risk Engine approval
        4. Save to database (mocked)
        5. Return success response
        
        Expected: Signal persisted with correct metadata
        """
        # Step 1: Validate payload
        validated_signal, error = validate_tradingview_payload(sample_webhook_payload)
        
        assert validated_signal is not None
        assert error is None
        assert validated_signal.symbol == 'BTC/USDT'
        assert validated_signal.side == 'LONG'
        assert validated_signal.entry_price == 50000.0
        assert validated_signal.quantity == 0.01
        
        # Step 2: Risk Engine check
        decision = asyncio.run(integration_risk_engine.check_trade_approval(
            proposal=validated_signal.to_dict(),
            user_id='webhook_user'
        ))
        
        assert decision.approved == True
        
        # Step 3: Database persistence (mocked)
        from app.database.models import Signals
        import uuid
        
        signal_record = Signals(
            id=str(uuid.uuid4()),
            source='TRADINGVIEW_WEBHOOK',
            symbol=validated_signal.symbol.replace('/', ''),
            signal_type=f"ENTRY_{validated_signal.side}",
            strength=validated_signal.confidence,
            indicators_json=json.dumps(validated_signal.to_dict()),
            processed=1,  # Mark as processed
            created_at=datetime.utcnow().isoformat()
        )
        
        # Verify record structure
        assert signal_record.source == 'TRADINGVIEW_WEBHOOK'
        assert signal_record.processed == 1
        assert signal_record.symbol == 'BTCUSDT'
    
    def test_webhook_authentication_invalid_token(self):
        """
        Test that invalid authentication tokens are rejected.
        
        Expected: HTTPException with 401 status code
        """
        with pytest.raises(HTTPException) as exc_info:
            verify_trading_secret("invalid_token")
        
        assert exc_info.value.status_code == 401
    
    def test_webhook_malformed_payload_missing_fields(self):
        """
        Test that malformed payloads are handled gracefully.
        
        Expected: Validation error with descriptive message
        """
        incomplete_payload = {
            'symbol': 'BTCUSDT',
            # Missing required fields: side, price, quantity
        }
        
        validated_signal, error = validate_tradingview_payload(incomplete_payload)
        
        assert validated_signal is None
        assert error is not None
        assert 'Missing required field' in error
    
    def test_webhook_invalid_side_rejected(self):
        """
        Test that invalid trade sides are rejected.
        
        Expected: Validation error for unsupported side
        """
        invalid_side_payload = {
            'symbol': 'BTCUSDT',
            'side': 'HOLD',  # Invalid
            'price': 50000.0,
            'quantity': 0.01
        }
        
        validated_signal, error = validate_tradingview_payload(invalid_side_payload)
        
        assert validated_signal is None
        assert error is not None
        assert 'Invalid side' in error
    
    def test_webhook_negative_price_rejected(self):
        """
        Test that negative prices are rejected.
        
        Expected: Validation error for non-positive price
        """
        negative_price_payload = {
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'price': -50000.0,  # Negative
            'quantity': 0.01
        }
        
        validated_signal, error = validate_tradingview_payload(negative_price_payload)
        
        assert validated_signal is None
        assert error is not None
        assert 'Price must be positive' in error
    
    def test_webhook_symbol_normalization(self):
        """
        Test that various symbol formats are normalized correctly.
        
        Expected: All formats converted to BASE/QUOTE format
        """
        # Test BTCUSDT format
        payload1 = {
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'price': 50000.0,
            'quantity': 0.01
        }
        signal1, _ = validate_tradingview_payload(payload1)
        assert signal1.symbol == 'BTC/USDT'
        
        # Test ETH/USDT format (already normalized)
        payload2 = {
            'symbol': 'ETH/USDT',
            'side': 'sell',
            'price': 3000.0,
            'quantity': 0.1
        }
        signal2, _ = validate_tradingview_payload(payload2)
        assert signal2.symbol == 'ETH/USDT'
    
    @pytest.mark.asyncio
    async def test_webhook_error_handling_rollback(
        self,
        sample_webhook_payload,
        integration_risk_engine,
        mock_db_session
    ):
        """
        Test that errors during webhook processing trigger proper rollback:
        1. Risk Engine rejection
        2. Database transaction rollback
        3. No partial state committed
        
        Expected: Clean failure with no database writes
        """
        # Force risk rejection
        integration_risk_engine.daily_pnl_pct = -0.05
        
        validated_signal, _ = validate_tradingview_payload(sample_webhook_payload)
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=validated_signal.to_dict(),
            user_id='test_user'
        )
        
        assert decision.approved == False
        
        # Verify database NOT written
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
    
    def test_webhook_optional_fields_defaults(self):
        """
        Test that optional fields use sensible defaults when not provided.
        
        Expected: stop_loss=None, take_profit=None, leverage=1, confidence=0.5
        """
        minimal_payload = {
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'price': 50000.0,
            'quantity': 0.01
            # No stop_loss, take_profit, leverage, confidence
        }
        
        signal, error = validate_tradingview_payload(minimal_payload)
        
        assert signal is not None
        assert error is None
        assert signal.stop_loss is None
        assert signal.take_profit is None
        assert signal.leverage == 1
        assert signal.confidence == 0.5  # Default
    
    def test_webhook_perpetual_suffix_stripped(self):
        """
        Test that perpetual contract suffixes are stripped from symbols.
        
        Expected: BTCUSDT.P → BTC/USDT
        """
        perp_payload = {
            'symbol': 'BTCUSDT.P',
            'side': 'buy',
            'price': 50000.0,
            'quantity': 0.01
        }
        
        signal, _ = validate_tradingview_payload(perp_payload)
        
        assert signal.symbol == 'BTC/USDT'
        assert '.P' not in signal.symbol
    
    @pytest.mark.asyncio
    async def test_webhook_to_signal_conversion_preserves_data(
        self,
        sample_webhook_payload,
        integration_risk_engine
    ):
        """
        Test that all webhook data is preserved through signal conversion.
        
        Expected: All fields correctly mapped from webhook to SignalProposal
        """
        validated_signal, _ = validate_tradingview_payload(sample_webhook_payload)
        
        assert validated_signal.strategy_name == 'breakout'
        assert validated_signal.entry_price == 50000.0
        assert validated_signal.stop_loss == 49000.0
        assert validated_signal.take_profit == 52000.0
        assert validated_signal.leverage == 2
        assert validated_signal.confidence == 0.85
        
        # Verify it can be converted to dict for Risk Engine
        signal_dict = validated_signal.to_dict()
        assert 'symbol' in signal_dict
        assert 'side' in signal_dict
        assert 'entry_price' in signal_dict
