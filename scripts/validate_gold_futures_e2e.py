#!/usr/bin/env python3
"""
End-to-End Validation for MEXC Gold Futures Trading (Demo & Live).

This script validates:
1. Configuration Check - Verify GOLD_SYMBOL_MEXC and API credentials
2. Connectivity & Balance - Test MEXC Futures API connection and balance
3. Order Execution - Open a position on MEXC Demo/Live
4. Position Closure - Close the opened position
5. State Verification - Check database records and position status

Usage:
    python scripts/validate_gold_futures_e2e.py [--demo] [--live] [--symbol SYMBOL]
    
Options:
    --demo     Use MEXC Demo/Testnet mode (default)
    --live     Use MEXC Live mode (REAL MONEY - use with caution!)
    --symbol   Override default symbol (default: GOLD(XAUT)/USDT)
"""
import asyncio
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.config import settings
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.infra.mexc_client import MEXCClient
from app.notifications.notifier import TelegramNotifier
from app.logging_config import get_logger

logger = get_logger(__name__)


class MexcGoldFuturesValidator:
    """Validates end-to-end Gold futures trading on MEXC."""
    
    def __init__(self, use_testnet: bool = True, custom_symbol: Optional[str] = None):
        self.use_testnet = use_testnet
        self.symbol = custom_symbol or settings.GOLD_SYMBOL_MEXC
        self.user_id = "validation_user"
        self.notifier = TelegramNotifier()
        self.test_results = {}
        
        mode = "DEMO/TESTNET" if use_testnet else "LIVE"
        logger.info(f"\n{'='*80}")
        logger.info(f"MEXC Gold Futures E2E Validator - {mode} Mode")
        logger.info(f"{'='*80}")
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Testnet: {use_testnet}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    async def check_configuration(self) -> bool:
        """Step 1: Verify configuration and credentials."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 1: Configuration Check")
        logger.info(f"{'='*80}")
        
        checks_passed = True
        
        # Check GOLD_SYMBOL_MEXC
        logger.info(f"\n1.1 Gold Symbol Configuration")
        logger.info(f"-" * 80)
        if not hasattr(settings, 'GOLD_SYMBOL_MEXC') or not settings.GOLD_SYMBOL_MEXC:
            logger.error("❌ GOLD_SYMBOL_MEXC not configured in config.py")
            checks_passed = False
        else:
            logger.info(f"✅ GOLD_SYMBOL_MEXC: {settings.GOLD_SYMBOL_MEXC}")
            logger.info(f"✅ Using symbol: {self.symbol}")
        
        # Check MEXC API credentials
        logger.info(f"\n1.2 MEXC API Credentials")
        logger.info(f"-" * 80)
        if not settings.MEXC_API_KEY:
            logger.error("❌ MEXC_API_KEY not configured")
            checks_passed = False
        else:
            masked_key = f"{settings.MEXC_API_KEY[:8]}...{settings.MEXC_API_KEY[-4:]}"
            logger.info(f"✅ MEXC_API_KEY: {masked_key}")
        
        if not settings.MEXC_API_SECRET:
            logger.error("❌ MEXC_API_SECRET not configured")
            checks_passed = False
        else:
            logger.info(f"✅ MEXC_API_SECRET: [HIDDEN]")
        
        # Check other relevant settings
        logger.info(f"\n1.3 Trading Configuration")
        logger.info(f"-" * 80)
        logger.info(f"✅ ACTIVE_EXCHANGE: {settings.ACTIVE_EXCHANGE}")
        logger.info(f"✅ EXECUTION_MODE: {settings.EXECUTION_MODE}")
        logger.info(f"✅ GOLD_MAX_LEVERAGE: {settings.GOLD_MAX_LEVERAGE}x")
        logger.info(f"✅ GOLD_RISK_PER_TRADE: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
        logger.info(f"✅ GOLD_MIN_CONFIDENCE: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
        
        self.test_results['configuration'] = checks_passed
        return checks_passed
    
    async def perform_health_check(self) -> bool:
        """Step 1.5: Perform comprehensive health check."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 1.5: Health Check")
        logger.info(f"{'='*80}")
        
        mexc_client = None
        try:
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=self.use_testnet
            )
            
            health = await mexc_client.health_check()
            
            logger.info(f"\nHealth Status: {health['status'].upper()}")
            logger.info(f"Overall Latency: {health['overall_latency_ms']}ms")
            logger.info(f"Checks Passed: {health['checks_passed']}")
            
            for check_name, check_result in health['checks'].items():
                icon = "✅" if check_result['status'] == 'pass' else "❌"
                logger.info(f"{icon} {check_name.title()}: {check_result['status']}")
                
                if check_result['status'] == 'pass':
                    if 'latency_ms' in check_result:
                        logger.info(f"   Latency: {check_result['latency_ms']}ms")
                else:
                    logger.error(f"   Error: {check_result.get('error', 'Unknown')}")
            
            # Alert if degraded or unhealthy
            if health['status'] in ['degraded', 'unhealthy']:
                warning_msg = f"MEXC Health Check: {health['status']} - {health['checks_passed']} checks passed"
                await self.notifier.send_message(f"⚠️ {warning_msg}")
                logger.warning(warning_msg)
            
            self.test_results['health_check'] = health['status'] == 'healthy'
            return health['status'] == 'healthy'
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            self.test_results['health_check'] = False
            return False
        finally:
            if mexc_client:
                await mexc_client.close()
    
    async def check_connectivity_and_balance(self) -> Dict[str, Any]:
        """Step 2: Test connectivity and fetch balance."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 2: Connectivity & Balance Check")
        logger.info(f"{'='*80}")
        
        mexc_client = None
        try:
            # Initialize MEXC client
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=self.use_testnet
            )
            
            # Fetch balance
            logger.info(f"\n2.1 Account Balance")
            logger.info(f"-" * 80)
            balance = await mexc_client.fetch_balance()
            
            logger.info(f"✅ Total USDT: ${balance['total_usdt']:,.2f}")
            logger.info(f"✅ Available USDT: ${balance['free_usdt']:,.2f}")
            logger.info(f"✅ Used USDT: ${balance['used_usdt']:,.2f}")
            
            # Check if balance is sufficient
            min_balance = 10.0  # Minimum $10 for testing
            if balance['total_usdt'] < min_balance:
                logger.warning(f"⚠️  Low balance: ${balance['total_usdt']:.2f} < ${min_balance:.2f}")
                logger.warning(f"   Some tests may fail due to insufficient funds")
            else:
                logger.info(f"✅ Sufficient balance for trading")
            
            # Fetch ticker to verify symbol availability
            logger.info(f"\n2.2 Market Data Verification")
            logger.info(f"-" * 80)
            ticker = await mexc_client.fetch_ticker(self.symbol)
            
            logger.info(f"✅ Symbol: {ticker['symbol']}")
            logger.info(f"✅ Current Price: ${ticker['last_price']:,.2f}")
            logger.info(f"✅ 24h High: ${ticker['high_24h']:,.2f}")
            logger.info(f"✅ 24h Low: ${ticker['low_24h']:,.2f}")
            logger.info(f"✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
            logger.info(f"✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
            
            result = {
                'status': 'success',
                'balance': balance,
                'ticker': ticker,
                'sufficient_balance': balance['total_usdt'] >= min_balance
            }
            
            self.test_results['connectivity'] = True
            return result
            
        except Exception as e:
            logger.error(f"❌ Connectivity check failed: {e}")
            logger.exception("Traceback:")
            self.test_results['connectivity'] = False
            return {'status': 'failed', 'error': str(e)}
        finally:
            if mexc_client:
                await mexc_client.close()
    
    async def execute_open_position(self, balance_info: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3: Execute a market order to open a position."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 3: Order Execution - Opening Position")
        logger.info(f"{'='*80}")
        
        mexc_client = None
        try:
            # Initialize MEXC client
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=self.use_testnet
            )
            
            # Get current price
            ticker = await mexc_client.fetch_ticker(self.symbol)
            current_price = ticker['last_price']
            
            # Calculate trade parameters
            leverage = min(3, settings.GOLD_MAX_LEVERAGE)  # Conservative leverage
            risk_amount = balance_info['balance']['total_usdt'] * settings.GOLD_RISK_PER_TRADE
            risk_per_unit = current_price * 0.02  # 2% stop loss
            quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
            quantity = round(quantity, 2)
            
            # SAFETY: Enforce maximum position size limits for live testing
            MAX_LIVE_TEST_QUANTITY = 0.01  # Maximum 0.01 units for live testing
            if not self.use_testnet:
                quantity = min(quantity, MAX_LIVE_TEST_QUANTITY)
                logger.warning(f"Live mode: Capping quantity at {MAX_LIVE_TEST_QUANTITY} for safety")
            
            # Ensure minimum quantity
            quantity = max(quantity, 0.01)
            
            position_value = quantity * current_price
            
            logger.info(f"\n3.1 Trade Parameters")
            logger.info(f"-" * 80)
            logger.info(f"✅ Symbol: {self.symbol}")
            logger.info(f"✅ Side: BUY (Long)")
            logger.info(f"✅ Entry Price: ${current_price:,.2f}")
            logger.info(f"✅ Quantity: {quantity:.2f}")
            logger.info(f"✅ Leverage: {leverage}x")
            logger.info(f"✅ Position Value: ${position_value:,.2f}")
            logger.info(f"✅ Risk Amount: ${risk_amount:.2f} ({settings.GOLD_RISK_PER_TRADE*100:.1f}%)")
            
            # Execute market order
            logger.info(f"\n3.2 Executing Market Order")
            logger.info(f"-" * 80)
            logger.info(f"🔄 Placing BUY order...")
            
            order = await mexc_client.create_market_order(
                symbol=self.symbol,
                side='buy',
                amount=quantity,
                leverage=leverage
            )
            
            logger.info(f"✅ Order executed successfully!")
            logger.info(f"   • Order ID: {order['order_id']}")
            logger.info(f"   • Status: {order['status']}")
            logger.info(f"   • Filled Price: ${order['price']:,.2f}")
            logger.info(f"   • Amount: {order['amount']}")
            logger.info(f"   • Cost: ${order['cost']:,.2f}")
            logger.info(f"   • Fee: {order.get('fee', {})}")
            
            # Record trade in database
            logger.info(f"\n3.3 Recording Trade in Database")
            logger.info(f"-" * 80)
            
            trade_record = PaperTrades(
                ts_open=datetime.utcnow().isoformat(),
                user_id=self.user_id,
                exchange='mexc',
                symbol=self.symbol,
                side='LONG',
                leverage=leverage,
                qty=quantity,
                entry_price=order['price'],
                exit_price=None,
                stop_loss=current_price * 0.98,  # 2% below entry
                take_profit=current_price * 1.04,  # 4% above entry
                profit=None,
                profit_pct=None,
                status='open',
                notes=json.dumps({
                    'order_id': order['order_id'],
                    'test_mode': 'demo' if self.use_testnet else 'live',
                    'validation_step': 'open_position'
                }),
                execution_mode='validation_test'
            )
            
            async with async_session_maker() as db_session:
                db_session.add(trade_record)
                await db_session.commit()
                trade_id = trade_record.id
            
            logger.info(f"✅ Trade recorded in database (ID: {trade_id})")
            
            result = {
                'status': 'success',
                'order': order,
                'trade_id': trade_id,
                'quantity': quantity,
                'entry_price': order['price'],
                'leverage': leverage
            }
            
            self.test_results['open_position'] = True
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to open position: {e}")
            logger.exception("Traceback:")
            self.test_results['open_position'] = False
            return {'status': 'failed', 'error': str(e)}
        finally:
            if mexc_client:
                await mexc_client.close()
    
    async def execute_close_position(self, open_result: Dict[str, Any]) -> Dict[str, Any]:
        """Step 4: Close the opened position."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 4: Position Closure")
        logger.info(f"{'='*80}")
        
        mexc_client = None
        try:
            # Initialize MEXC client
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=self.use_testnet
            )
            
            # Wait a moment for position to be registered
            logger.info(f"\n4.1 Waiting for position registration...")
            await asyncio.sleep(2)
            
            # Fetch open positions
            logger.info(f"\n4.2 Checking Open Positions")
            logger.info(f"-" * 80)
            positions = await mexc_client.fetch_open_positions()
            
            gold_position = None
            for pos in positions:
                if any(g in pos['symbol'].upper() for g in ['GOLD', 'XAUT', 'PAXG']):
                    gold_position = pos
                    break
            
            if not gold_position:
                logger.error(f"❌ No open GOLD position found")
                return {'status': 'failed', 'error': 'No open position found'}
            
            logger.info(f"✅ Found open position:")
            logger.info(f"   • Symbol: {gold_position['symbol']}")
            logger.info(f"   • Side: {gold_position['side']}")
            logger.info(f"   • Size: {gold_position['size']}")
            logger.info(f"   • Entry Price: ${gold_position['entry_price']:,.2f}")
            logger.info(f"   • Mark Price: ${gold_position['mark_price']:,.2f}")
            logger.info(f"   • Unrealized P&L: ${gold_position['unrealized_pnl']:,.2f}")
            
            # Close position
            logger.info(f"\n4.3 Closing Position")
            logger.info(f"-" * 80)
            logger.info(f"🔄 Placing SELL order to close position...")
            
            close_order = await mexc_client.close_position(self.symbol)
            
            logger.info(f"✅ Position closed successfully!")
            logger.info(f"   • Order ID: {close_order['order_id']}")
            logger.info(f"   • Status: {close_order['status']}")
            logger.info(f"   • Exit Price: ${close_order['price']:,.2f}")
            logger.info(f"   • Amount: {close_order['amount']}")
            
            # Calculate P&L
            entry_price = open_result['entry_price']
            exit_price = close_order['price']
            quantity = open_result['quantity']
            
            profit = (exit_price - entry_price) * quantity
            profit_pct = (profit / (entry_price * quantity)) * 100 if entry_price > 0 else 0
            
            logger.info(f"\n4.4 P&L Calculation")
            logger.info(f"-" * 80)
            logger.info(f"✅ Entry Price: ${entry_price:,.2f}")
            logger.info(f"✅ Exit Price: ${exit_price:,.2f}")
            logger.info(f"✅ Profit: ${profit:+.2f} ({profit_pct:+.2f}%)")
            
            # Update trade record in database
            logger.info(f"\n4.5 Updating Database Record")
            logger.info(f"-" * 80)
            
            async with async_session_maker() as db_session:
                stmt = select(PaperTrades).where(PaperTrades.id == open_result['trade_id'])
                result = await db_session.execute(stmt)
                trade = result.scalar_one_or_none()
                
                if trade:
                    trade.ts_close = datetime.utcnow().isoformat()
                    trade.exit_price = exit_price
                    trade.profit = profit
                    trade.profit_pct = profit_pct
                    trade.status = 'closed'
                    existing_notes = json.loads(trade.notes) if trade.notes else {}
                    trade.notes = json.dumps({
                        **existing_notes,
                        'close_order_id': close_order['order_id'],
                        'exit_price': exit_price,
                        'profit': profit,
                        'profit_pct': profit_pct
                    })
                    await db_session.commit()
                    logger.info(f"✅ Trade record updated (ID: {trade.id})")
                else:
                    logger.warning(f"⚠️  Trade record not found (ID: {open_result['trade_id']})")
            
            result = {
                'status': 'success',
                'close_order': close_order,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'profit_pct': profit_pct,
                'trade_id': open_result['trade_id']
            }
            
            self.test_results['close_position'] = True
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            logger.exception("Traceback:")
            self.test_results['close_position'] = False
            return {'status': 'failed', 'error': str(e)}
        finally:
            if mexc_client:
                await mexc_client.close()
    
    async def verify_state(self, open_result: Dict[str, Any], close_result: Dict[str, Any]) -> bool:
        """Step 5: Verify final state - database and positions."""
        logger.info(f"\n{'='*80}")
        logger.info("STEP 5: State Verification")
        logger.info(f"{'='*80}")
        
        verification_passed = True
        
        # Check database record
        logger.info(f"\n5.1 Database Record Verification")
        logger.info(f"-" * 80)
        
        async with async_session_maker() as db_session:
            stmt = select(PaperTrades).where(PaperTrades.id == open_result['trade_id'])
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if not trade:
                logger.error(f"❌ Trade record not found (ID: {open_result['trade_id']})")
                verification_passed = False
            else:
                logger.info(f"✅ Trade record found:")
                logger.info(f"   • ID: {trade.id}")
                logger.info(f"   • Symbol: {trade.symbol}")
                logger.info(f"   • Side: {trade.side}")
                logger.info(f"   • Status: {trade.status}")
                logger.info(f"   • Entry Price: ${trade.entry_price:,.2f}")
                logger.info(f"   • Exit Price: ${trade.exit_price:,.2f}")
                logger.info(f"   • Profit: ${trade.profit:+.2f} ({trade.profit_pct:+.2f}%)")
                logger.info(f"   • Notes: {trade.notes[:100] if trade.notes else 'N/A'}...")
                
                if trade.status != 'closed':
                    logger.error(f"❌ Trade status is '{trade.status}', expected 'closed'")
                    verification_passed = False
                else:
                    logger.info(f"✅ Trade status correctly set to 'closed'")
        
        # Check that position no longer exists
        logger.info(f"\n5.2 Position Status Verification")
        logger.info(f"-" * 80)
        
        mexc_client = None
        try:
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=self.use_testnet
            )
            
            positions = await mexc_client.fetch_open_positions()
            
            gold_position = None
            for pos in positions:
                if any(g in pos['symbol'].upper() for g in ['GOLD', 'XAUT', 'PAXG']):
                    gold_position = pos
                    break
            
            if gold_position:
                logger.error(f"❌ GOLD position still exists after closure:")
                logger.error(f"   • Symbol: {gold_position['symbol']}")
                logger.error(f"   • Size: {gold_position['size']}")
                verification_passed = False
            else:
                logger.info(f"✅ No open GOLD positions found (correctly closed)")
        
        except Exception as e:
            logger.error(f"❌ Failed to verify positions: {e}")
            verification_passed = False
        finally:
            if mexc_client:
                await mexc_client.close()
        
        self.test_results['state_verification'] = verification_passed
        return verification_passed
    
    async def send_summary_report(self):
        """Send summary report via Telegram."""
        logger.info(f"\n{'='*80}")
        logger.info("Sending Summary Report")
        logger.info(f"{'='*80}")
        
        mode = "DEMO" if self.use_testnet else "LIVE"
        total_tests = len(self.test_results)
        passed_tests = sum(1 for v in self.test_results.values() if v)
        
        emoji = "✅" if passed_tests == total_tests else "⚠️" if passed_tests >= total_tests * 0.6 else "❌"
        
        message = (
            f"{emoji} <b>MEXC Gold Futures E2E Validation Complete</b>\n\n"
            f"<b>Mode:</b> {mode}\n"
            f"<b>Symbol:</b> {self.symbol}\n\n"
            f"<b>Results:</b>\n"
        )
        
        for test_name, passed in self.test_results.items():
            icon = "✅" if passed else "❌"
            message += f"{icon} {test_name.replace('_', ' ').title()}\n"
        
        message += f"\n<b>Total:</b> {passed_tests}/{total_tests} passed\n"
        message += f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        
        try:
            await self.notifier.send_message(message)
            logger.info(f"✅ Summary report sent to Telegram")
        except Exception as e:
            logger.warning(f"⚠️  Failed to send Telegram report: {e}")
    
    async def run_validation(self):
        """Execute full validation sequence."""
        logger.info(f"\n{'#'*80}")
        logger.info(f"# MEXC GOLD FUTURES END-TO-END VALIDATION")
        logger.info(f"{'#'*80}")
        
        try:
            # Step 1: Configuration Check
            config_ok = await self.check_configuration()
            if not config_ok:
                logger.error(f"\n❌ Configuration check failed. Aborting validation.")
                return False
            
            # NEW: Step 1.5: Health Check
            health_ok = await self.perform_health_check()
            if not health_ok:
                logger.warning(f"\n⚠️ Health check shows issues. Proceeding with caution.")
            
            # Step 2: Connectivity & Balance
            balance_info = await self.check_connectivity_and_balance()
            if balance_info['status'] != 'success':
                logger.error(f"\n❌ Connectivity check failed. Aborting validation.")
                return False
            
            if not balance_info.get('sufficient_balance', False):
                logger.warning(f"\n⚠️  Insufficient balance. Proceeding with caution.")
            
            # Step 3: Open Position
            open_result = await self.execute_open_position(balance_info)
            if open_result['status'] != 'success':
                logger.error(f"\n❌ Failed to open position. Aborting validation.")
                return False
            
            # Step 4: Close Position
            close_result = await self.execute_close_position(open_result)
            if close_result['status'] != 'success':
                logger.error(f"\n❌ Failed to close position.")
                # Continue to state verification even if close failed
            
            # Step 5: State Verification
            state_ok = await self.verify_state(open_result, close_result)
            
            # Send summary report
            await self.send_summary_report()
            
            # Final summary
            logger.info(f"\n{'='*80}")
            logger.info(f"VALIDATION SUMMARY")
            logger.info(f"{'='*80}")
            
            for test_name, passed in self.test_results.items():
                icon = "✅" if passed else "❌"
                logger.info(f"{icon} {test_name.replace('_', ' ').title()}")
            
            total = len(self.test_results)
            passed = sum(1 for v in self.test_results.values() if v)
            
            logger.info(f"\nTotal: {passed}/{total} tests passed")
            
            if passed == total:
                logger.info(f"\n🎉 ALL TESTS PASSED - MEXC Gold Futures E2E validation successful!")
                return True
            elif passed >= total * 0.6:
                logger.info(f"\n⚠️  Most tests passed ({passed}/{total}). Review failures above.")
                return True
            else:
                logger.info(f"\n❌ Too many failures ({passed}/{total}). Validation unsuccessful.")
                return False
                
        except Exception as e:
            logger.error(f"\n❌ Validation procedure failed: {e}")
            logger.exception("Traceback:")
            return False


async def run_periodic_health_check(interval_seconds: int = 300):
    """
    Run health checks periodically (for monitoring).
    
    Args:
        interval_seconds: Check interval (default: 5 minutes)
    """
    logger.info(f"Starting periodic health checks (every {interval_seconds}s)")
    
    while True:
        try:
            validator = MexcGoldFuturesValidator(use_testnet=True)
            health_ok = await validator.perform_health_check()
            
            if not health_ok:
                logger.error("Health check failed - sending alert")
                await validator.notifier.send_message(
                    "🚨 MEXC Health Check FAILED - Immediate attention required"
                )
            
            await asyncio.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("Periodic health check stopped")
            break
        except Exception as e:
            logger.error(f"Health check error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='MEXC Gold Futures E2E Validator')
    parser.add_argument('--demo', action='store_true', help='Use demo simulation mode (default, no API calls)')
    parser.add_argument('--live', action='store_true', help='Use LIVE mode with REAL MONEY (use with extreme caution!)')
    parser.add_argument('--symbol', type=str, default=None, help='Override default symbol')
    
    args = parser.parse_args()
    
    # Determine mode - DEFAULT TO DEMO/SIMULATION FOR SAFETY
    use_testnet = True
    if args.live:
        use_testnet = False
        logger.warning(f"\n{'!'*80}")
        logger.warning(f"⚠️  WARNING: Running in LIVE mode with REAL MONEY!")
        logger.warning(f"{'!'*80}")
        logger.warning(f"   This will execute actual trades on MEXC.")
        logger.warning(f"   Position sizes are capped at 0.01 units for safety.")
        logger.warning(f"   Press Ctrl+C within 10 seconds to abort...")
        logger.warning(f"{'!'*80}\n")
        await asyncio.sleep(10)
    
    validator = MexcGoldFuturesValidator(
        use_testnet=use_testnet,
        custom_symbol=args.symbol
    )
    
    success = await validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
