"""
Test script for Trade Validation Mechanism.
Tests all validation rules and Telegram notification integration.
"""
import asyncio
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infra.trade_validator import TradeValidator, ValidationResult
from app.infra.telegram_notifier import TelegramNotifier
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
from sqlalchemy import select


async def test_validation_rules():
    """Test all validation rules with sample trade proposals."""
    print("=" * 70)
    print("TRADE VALIDATION MECHANISM - TEST SUITE")
    print("=" * 70)
    print(f"\nTrading Profile: {settings.TRADING_PROFILE}")
    print(f"Execution Mode: {settings.EXECUTION_MODE}")
    print(f"Active Exchange: {settings.ACTIVE_EXCHANGE}")
    print("\n" + "-" * 70)
    
    validator = TradeValidator()
    notifier = TelegramNotifier()
    
    async with async_session_maker() as db_session:
        # Test 1: Valid trade proposal (should be APPROVED)
        print("\n📋 TEST 1: Valid Trade Proposal (Should be APPROVED)")
        print("-" * 70)
        
        valid_proposal = {
            'symbol': 'XAUT/USDT',
            'side': 'LONG',
            'entry_price': 2450.00,
            'stop_loss': 2425.00,  # 1% risk
            'take_profit': 2500.00,  # 2% reward
            'quantity': 0.01,
            'leverage': 3,
            'confidence': 0.80,  # Above threshold
            'strategy_name': 'London Breakout',
            'regime': 'trending'
        }
        
        result = await validator.validate_trade(
            proposal=valid_proposal,
            user_id='test_user',
            db_session=db_session,
            exchange='mexc',
            symbol='XAUT/USDT'
        )
        
        print(f"✅ Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
        print(f" Confidence: {valid_proposal['confidence']:.0%} (threshold: {result.confidence_threshold:.0%})")
        print(f"💰 Position Value: ${result.position_value:,.2f}")
        print(f"️  Risk Amount: ${result.risk_amount:.2f} ({result.risk_threshold:.0%} limit)")
        print(f"📈 Open Positions: {result.open_positions_count}")
        print(f"📉 Daily Drawdown: {result.daily_drawdown_pct:.2f}%")
        
        if result.violations:
            print(f"\n❌ Violations:")
            for v in result.violations:
                print(f"   - {v}")
        
        if result.warnings:
            print(f"\n️  Warnings:")
            for w in result.warnings:
                print(f"   - {w}")
        
        # Send Telegram report for this test
        await notifier.send_trade_validation_report(result, valid_proposal)
        print("\n📱 Telegram report sent for Test 1")
        
        # Test 2: Low confidence trade (should be REJECTED)
        print("\n" + "-" * 70)
        print("\n📋 TEST 2: Low Confidence Trade (Should be REJECTED)")
        print("-" * 70)
        
        low_confidence_proposal = {
            'symbol': 'XAUT/USDT',
            'side': 'LONG',
            'entry_price': 2450.00,
            'stop_loss': 2425.00,
            'take_profit': 2500.00,
            'quantity': 0.01,
            'leverage': 3,
            'confidence': 0.60,  # Below threshold (0.74 for safer_growth)
            'strategy_name': 'Scalping',
            'regime': 'ranging'
        }
        
        result = await validator.validate_trade(
            proposal=low_confidence_proposal,
            user_id='test_user',
            db_session=db_session,
            exchange='mexc',
            symbol='XAUT/USDT'
        )
        
        print(f"✅ Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
        print(f"📊 Confidence: {low_confidence_proposal['confidence']:.0%} (threshold: {result.confidence_threshold:.0%})")
        
        if result.violations:
            print(f"\n❌ Violations:")
            for v in result.violations:
                print(f"   - {v}")
        
        # Send Telegram report for this test
        await notifier.send_trade_validation_report(result, low_confidence_proposal)
        print("\n📱 Telegram report sent for Test 2")
        
        # Test 3: High leverage trade (should be REJECTED for Gold)
        print("\n" + "-" * 70)
        print("\n📋 TEST 3: High Leverage Gold Trade (Should be REJECTED)")
        print("-" * 70)
        
        high_leverage_proposal = {
            'symbol': 'XAUT/USDT',
            'side': 'SHORT',
            'entry_price': 2450.00,
            'stop_loss': 2475.00,
            'take_profit': 2400.00,
            'quantity': 0.01,
            'leverage': 10,  # Exceeds GOLD_MAX_LEVERAGE (5)
            'confidence': 0.85,
            'strategy_name': 'Mean Reversion',
            'regime': 'ranging'
        }
        
        result = await validator.validate_trade(
            proposal=high_leverage_proposal,
            user_id='test_user',
            db_session=db_session,
            exchange='mexc',
            symbol='XAUT/USDT'
        )
        
        print(f"✅ Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
        print(f" Leverage: {high_leverage_proposal['leverage']}x (max: {settings.GOLD_MAX_LEVERAGE}x for Gold)")
        
        if result.violations:
            print(f"\n❌ Violations:")
            for v in result.violations:
                print(f"   - {v}")
        
        # Send Telegram report for this test
        await notifier.send_trade_validation_report(result, high_leverage_proposal)
        print("\n Telegram report sent for Test 3")
        
        # Test 4: Excessive risk trade
        print("\n" + "-" * 70)
        print("\n📋 TEST 4: Excessive Risk Trade (Should be REJECTED)")
        print("-" * 70)
        
        high_risk_proposal = {
            'symbol': 'XAUT/USDT',
            'side': 'LONG',
            'entry_price': 2450.00,
            'stop_loss': 2350.00,  # ~4% risk
            'take_profit': 2550.00,
            'quantity': 0.02,
            'leverage': 5,
            'confidence': 0.90,
            'strategy_name': 'Breakout',
            'regime': 'trending'
        }
        
        result = await validator.validate_trade(
            proposal=high_risk_proposal,
            user_id='test_user',
            db_session=db_session,
            exchange='mexc',
            symbol='XAUT/USDT'
        )
        
        print(f"✅ Approval Status: {'APPROVED' if result.approved else 'REJECTED'}")
        print(f" Position Value: ${result.position_value:,.2f}")
        print(f"⚠️  Risk Amount: ${result.risk_amount:.2f}")
        print(f"📊 Risk %: {(result.risk_amount / result.position_value * 100):.2f}% (limit: {result.risk_threshold:.0%})")
        
        if result.violations:
            print(f"\n❌ Violations:")
            for v in result.violations:
                print(f"   - {v}")
        
        # Send Telegram report for this test
        await notifier.send_trade_validation_report(result, high_risk_proposal)
        print("\n📱 Telegram report sent for Test 4")
    
    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETED")
    print("=" * 70)
    print("\n✅ All validation tests executed")
    print("📱 Check Telegram for validation reports")
    print("\nValidation Rules Summary:")
    print(f"  • Confidence Threshold: {settings.SAFER_GROWTH_CONFIDENCE_THRESHOLD:.0%} (safer_growth)")
    print(f"  • Risk Per Trade: {settings.SAFER_GROWTH_RISK_PER_TRADE:.1%}")
    print(f"  • Max Daily Drawdown: {settings.SAFER_GROWTH_MAX_DAILY_DRAWDOWN:.1%}")
    print(f"  • Max Open Positions: {settings.SAFER_GROWTH_MAX_POSITIONS}")
    print(f"  • Gold Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"  • Auto-Execute Threshold: ${settings.AUTO_EXECUTE_THRESHOLD_USD:.2f}")


async def test_existing_trades():
    """Test validation against existing open trades in database."""
    print("\n" + "=" * 70)
    print("EXISTING TRADES VALIDATION CHECK")
    print("=" * 70)
    
    async with async_session_maker() as db_session:
        # Count open trades
        result = await db_session.execute(
            select(PaperTrades).where(PaperTrades.status == 'open')
        )
        open_trades = result.scalars().all()
        
        print(f"\n📊 Open Trades: {len(open_trades)}")
        
        if open_trades:
            print("\nCurrent Open Positions:")
            for trade in open_trades[:5]:  # Show first 5
                print(f"  • #{trade.id}: {trade.symbol} {trade.side} @ ${trade.entry_price:,.2f} "
                      f"({trade.exchange})")
        
        # Count closed trades today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        result = await db_session.execute(
            select(PaperTrades).where(
                PaperTrades.status == 'closed',
                PaperTrades.ts_close >= today_start.isoformat()
            )
        )
        today_trades = result.scalars().all()
        
        print(f"\n📅 Closed Trades Today: {len(today_trades)}")
        
        if today_trades:
            total_pnl = sum(t.profit or 0 for t in today_trades)
            print(f" Today's P&L: ${total_pnl:+.2f}")


if __name__ == "__main__":
    print("\n Starting Trade Validation Mechanism Tests\n")
    
    # Run validation tests
    asyncio.run(test_validation_rules())
    
    # Check existing trades
    asyncio.run(test_existing_trades())
    
    print("\n✨ All tests completed successfully!")
    print("📱 Please check your Telegram for validation reports\n")
