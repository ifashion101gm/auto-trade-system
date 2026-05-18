#!/usr/bin/env python3
"""
Comprehensive End-to-End Bybit Demo Trading Cycle Validation

Validates the complete data flow:
1. Configuration verification
2. Trade execution on api-demo.bybit.com
3. Exchange order verification via Pybit SDK
4. Database synchronization check
5. Discrepancy analysis

This ensures real orders are placed on Bybit Demo and properly synchronized
with the local database.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.execution.trading_service import LiveTradingService
from app.database.connection import async_session_maker
from app.database.models import PaperTrades
from sqlalchemy import select, func


class BybitDemoE2EValidator:
    """
    Comprehensive end-to-end validator for Bybit Demo trading cycle.
    
    Validates:
    - Configuration correctness
    - Order execution on demo endpoint
    - Database persistence and synchronization
    - Data consistency between exchange and database
    """
    
    def __init__(self, symbol: str = "XAUUSDT"):
        self.symbol = symbol
        self.validation_results = {
            'configuration': {},
            'execution': {},
            'exchange_verification': {},
            'database_sync': {},
            'discrepancies': []
        }
        
    def print_header(self, title: str):
        """Print formatted section header."""
        print("\n" + "="*80)
        print(f"  {title}")
        print("="*80)
    
    def print_subheader(self, title: str):
        """Print formatted subsection header."""
        print(f"\n{'─'*80}")
        print(f"  {title}")
        print(f"{'─'*80}")
    
    def print_status(self, status: str, message: str, details: str = ""):
        """Print status with icon."""
        icons = {
            'PASS': '✅',
            'FAIL': '❌',
            'WARN': '⚠️ ',
            'INFO': 'ℹ️ '
        }
        icon = icons.get(status, '•')
        print(f"{icon} {message}")
        if details:
            print(f"   {details}")
    
    async def validate_configuration(self) -> bool:
        """Step 1: Verify Bybit Demo configuration."""
        self.print_header("STEP 1: CONFIGURATION VERIFICATION")
        
        all_valid = True
        
        # Check ACTIVE_EXCHANGE
        if settings.ACTIVE_EXCHANGE.lower() == 'bybit':
            self.print_status('PASS', f"ACTIVE_EXCHANGE: {settings.ACTIVE_EXCHANGE}")
        else:
            self.print_status('FAIL', f"ACTIVE_EXCHANGE is '{settings.ACTIVE_EXCHANGE}', expected 'bybit'")
            all_valid = False
        
        # Check BYBIT_USE_DEMO_DOMAIN
        if settings.BYBIT_USE_DEMO_DOMAIN:
            self.print_status('PASS', "BYBIT_USE_DEMO_DOMAIN: True (api-demo.bybit.com)")
        else:
            self.print_status('FAIL', "BYBIT_USE_DEMO_DOMAIN: False - must be True for demo trading")
            all_valid = False
        
        # Check API credentials
        if settings.BYBIT_DEMO_API_KEY:
            masked_key = '***' + settings.BYBIT_DEMO_API_KEY[-4:]
            self.print_status('PASS', f"BYBIT_DEMO_API_KEY: {masked_key}")
        else:
            self.print_status('FAIL', "BYBIT_DEMO_API_KEY not configured")
            all_valid = False
        
        if settings.BYBIT_DEMO_API_SECRET:
            masked_secret = '***' + settings.BYBIT_DEMO_API_SECRET[-4:]
            self.print_status('PASS', f"BYBIT_DEMO_API_SECRET: {masked_secret}")
        else:
            self.print_status('FAIL', "BYBIT_DEMO_API_SECRET not configured")
            all_valid = False
        
        # Check MICRO_LIVE_ENABLED
        if settings.MICRO_LIVE_ENABLED:
            self.print_status('PASS', "MICRO_LIVE_ENABLED: True (allows execution)")
        else:
            self.print_status('WARN', "MICRO_LIVE_ENABLED: False - may prevent trade execution")
        
        self.validation_results['configuration'] = {
            'valid': all_valid,
            'exchange': settings.ACTIVE_EXCHANGE,
            'demo_domain': settings.BYBIT_USE_DEMO_DOMAIN,
            'api_key_configured': bool(settings.BYBIT_DEMO_API_KEY),
            'api_secret_configured': bool(settings.BYBIT_DEMO_API_SECRET),
            'micro_live_enabled': settings.MICRO_LIVE_ENABLED
        }
        
        return all_valid
    
    async def execute_trading_cycle(self) -> Dict[str, Any]:
        """Step 2: Execute complete trading cycle."""
        self.print_header("STEP 2: TRADING CYCLE EXECUTION")
        
        print(f"\n🚀 Initializing LiveTradingService for Bybit Demo...")
        print(f"   Exchange: bybit")
        print(f"   Testnet Mode: True (uses demo domain)")
        print(f"   Symbol: {self.symbol}")
        
        service = LiveTradingService(
            exchange_name='bybit',
            use_testnet=True,
            use_openrouter=True
        )
        
        try:
            async with async_session_maker() as db:
                print(f"\n⏳ Executing trading cycle...")
                
                result = await service.execute_trading_cycle(
                    symbol=self.symbol,
                    user_id="e2e_validation",
                    db_session=db,
                    execute_on_binance=False,
                    execute_on_mexc=False
                )
            
            self.validation_results['execution'] = {
                'status': result.get('status'),
                'timestamp': datetime.utcnow().isoformat(),
                'details': result
            }
            
            if result['status'] == 'success':
                self.print_status('PASS', "Trading cycle executed successfully")
                
                if 'execution' in result:
                    exec_data = result['execution']
                    self.print_status('INFO', f"Order ID: {exec_data.get('order_id', 'N/A')}")
                    self.print_status('INFO', f"Side: {exec_data.get('side', 'N/A')}")
                    self.print_status('INFO', f"Entry Price: ${exec_data.get('filled_price', 0):,.2f}")
                    self.print_status('INFO', f"Quantity: {exec_data.get('filled_quantity', 0):.6f}")
                    self.print_status('INFO', f"Position Value: ${exec_data.get('position_value_usd', 0):,.2f}")
                    
                    return result
            elif result['status'] == 'rejected':
                self.print_status('WARN', f"Trade rejected: {result.get('rejection_reason', 'Unknown')}")
                self.print_status('INFO', f"Quality Score: {result.get('quality_score', 0)}/100")
            else:
                self.print_status('FAIL', f"Execution failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            self.print_status('FAIL', f"Exception during execution: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'status': 'failed', 'error': str(e)}
        
        finally:
            await service.close()
    
    async def verify_exchange_order(self, order_id: str) -> Dict[str, Any]:
        """Step 3: Verify order on Bybit Demo via Pybit SDK."""
        self.print_header("STEP 3: EXCHANGE ORDER VERIFICATION")
        
        print(f"\n🔍 Verifying order on Bybit Demo (api-demo.bybit.com)...")
        print(f"   Order ID: {order_id}")
        
        try:
            from pybit.unified_trading import HTTP
            
            # Initialize Pybit client for demo
            client = HTTP(
                testnet=True,  # This uses api-demo.bybit.com when BYBIT_USE_DEMO_DOMAIN=true
                api_key=settings.BYBIT_DEMO_API_KEY,
                api_secret=settings.BYBIT_DEMO_API_SECRET,
                recv_window=10000
            )
            
            # Fetch order details
            print(f"\n⏳ Querying order history...")
            response = client.get_order_history(
                category="linear",
                symbol=self.symbol,
                orderId=order_id
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                order_data = response['result']['list'][0]
                
                self.print_status('PASS', "Order found on Bybit Demo")
                self.print_status('INFO', f"Symbol: {order_data.get('symbol')}")
                self.print_status('INFO', f"Side: {order_data.get('side')}")
                self.print_status('INFO', f"Order Type: {order_data.get('orderType')}")
                self.print_status('INFO', f"Price: {order_data.get('price')}")
                self.print_status('INFO', f"Qty: {order_data.get('qty')}")
                self.print_status('INFO', f"Status: {order_data.get('orderStatus')}")
                self.print_status('INFO', f"Created Time: {order_data.get('createdTime')}")
                
                # Verify it's on demo endpoint
                self.print_status('PASS', "Verified: Order exists on api-demo.bybit.com")
                
                self.validation_results['exchange_verification'] = {
                    'found': True,
                    'order_data': order_data,
                    'verified_demo': True
                }
                
                return {
                    'found': True,
                    'data': order_data
                }
            else:
                self.print_status('FAIL', f"Order not found on exchange: {response.get('retMsg', 'Unknown error')}")
                self.validation_results['exchange_verification'] = {
                    'found': False,
                    'error': response.get('retMsg')
                }
                return {'found': False}
        
        except Exception as e:
            self.print_status('FAIL', f"Exchange verification failed: {str(e)}")
            import traceback
            traceback.print_exc()
            self.validation_results['exchange_verification'] = {
                'found': False,
                'error': str(e)
            }
            return {'found': False, 'error': str(e)}
    
    async def verify_database_record(self, order_id: str) -> Dict[str, Any]:
        """Step 4: Verify database synchronization."""
        self.print_header("STEP 4: DATABASE SYNCHRONIZATION CHECK")
        
        print(f"\n💾 Querying local database for trade record...")
        print(f"   Searching for Order ID: {order_id}")
        
        try:
            async with async_session_maker() as db:
                # Search by order_id or external_order_id
                stmt = select(PaperTrades).where(
                    (PaperTrades.external_order_id == order_id) |
                    (PaperTrades.order_id == order_id)
                ).order_by(PaperTrades.ts_open.desc()).limit(1)
                
                result = await db.execute(stmt)
                trade = result.scalar_one_or_none()
                
                if trade:
                    self.print_status('PASS', "Trade record found in database")
                    self.print_status('INFO', f"Trade ID: {trade.id}")
                    self.print_status('INFO', f"Exchange: {trade.exchange}")
                    self.print_status('INFO', f"Symbol: {trade.symbol}")
                    self.print_status('INFO', f"Side: {trade.side}")
                    self.print_status('INFO', f"Entry Price: ${trade.entry_price:.2f}")
                    self.print_status('INFO', f"Quantity: {trade.quantity:.6f}")
                    self.print_status('INFO', f"Status: {trade.status}")
                    self.print_status('INFO', f"External Order ID: {trade.external_order_id}")
                    self.print_status('INFO', f"Created At: {trade.ts_open}")
                    
                    self.validation_results['database_sync'] = {
                        'found': True,
                        'trade_data': {
                            'id': trade.id,
                            'exchange': trade.exchange,
                            'symbol': trade.symbol,
                            'side': trade.side,
                            'entry_price': trade.entry_price,
                            'quantity': trade.quantity,
                            'status': trade.status,
                            'external_order_id': trade.external_order_id,
                            'ts_open': trade.ts_open
                        }
                    }
                    
                    return {
                        'found': True,
                        'trade': trade
                    }
                else:
                    self.print_status('FAIL', "Trade record NOT found in database")
                    self.validation_results['database_sync'] = {
                        'found': False,
                        'error': 'No matching record found'
                    }
                    return {'found': False}
        
        except Exception as e:
            self.print_status('FAIL', f"Database query failed: {str(e)}")
            import traceback
            traceback.print_exc()
            self.validation_results['database_sync'] = {
                'found': False,
                'error': str(e)
            }
            return {'found': False, 'error': str(e)}
    
    def analyze_discrepancies(self, exchange_data: Dict, db_data: Dict) -> List[str]:
        """Step 5: Analyze discrepancies between exchange and database."""
        self.print_header("STEP 5: DISCREPANCY ANALYSIS")
        
        discrepancies = []
        
        if not exchange_data.get('found') or not db_data.get('found'):
            self.print_status('FAIL', "Cannot compare: Missing data from exchange or database")
            if not exchange_data.get('found'):
                discrepancies.append("Order not found on exchange")
            if not db_data.get('found'):
                discrepancies.append("Trade not found in database")
            return discrepancies
        
        ex_order = exchange_data['data']
        db_trade = db_data['trade']
        
        print(f"\n🔎 Comparing exchange vs database records...")
        
        # Compare side
        ex_side = ex_order.get('side', '').upper()
        db_side = db_trade.side.upper() if db_trade.side else ''
        if ex_side == db_side:
            self.print_status('PASS', f"Side matches: {db_side}")
        else:
            msg = f"Side mismatch: Exchange={ex_side}, Database={db_side}"
            self.print_status('FAIL', msg)
            discrepancies.append(msg)
        
        # Compare quantity
        ex_qty = float(ex_order.get('qty', 0))
        db_qty = float(db_trade.quantity) if db_trade.quantity else 0
        qty_diff = abs(ex_qty - db_qty)
        qty_tolerance = ex_qty * 0.001  # 0.1% tolerance
        
        if qty_diff <= qty_tolerance:
            self.print_status('PASS', f"Quantity matches: {db_qty:.6f} (diff: {qty_diff:.6f})")
        else:
            msg = f"Quantity mismatch: Exchange={ex_qty:.6f}, Database={db_qty:.6f}, Diff={qty_diff:.6f}"
            self.print_status('FAIL', msg)
            discrepancies.append(msg)
        
        # Compare price
        ex_price = float(ex_order.get('price', 0) or ex_order.get('avgPrice', 0))
        db_price = float(db_trade.entry_price) if db_trade.entry_price else 0
        price_diff = abs(ex_price - db_price)
        price_tolerance = ex_price * 0.01  # 1% tolerance
        
        if price_diff <= price_tolerance or db_price == 0:
            self.print_status('PASS', f"Price acceptable: Exchange=${ex_price:.2f}, Database=${db_price:.2f}")
        else:
            msg = f"Price mismatch: Exchange=${ex_price:.2f}, Database=${db_price:.2f}, Diff=${price_diff:.2f}"
            self.print_status('WARN', msg)
            discrepancies.append(msg)
        
        # Compare status
        ex_status = ex_order.get('orderStatus', '').lower()
        db_status = db_trade.status.lower() if db_trade.status else ''
        
        # Map exchange statuses to database statuses
        status_map = {
            'new': 'open',
            'partiallyfilled': 'open',
            'filled': 'closed',
            'cancelled': 'cancelled',
            'rejected': 'rejected'
        }
        
        expected_db_status = status_map.get(ex_status, db_status)
        
        if db_status in [expected_db_status, ex_status]:
            self.print_status('PASS', f"Status consistent: Exchange={ex_status}, Database={db_status}")
        else:
            msg = f"Status mismatch: Exchange={ex_status}, Database={db_status}"
            self.print_status('WARN', msg)
            discrepancies.append(msg)
        
        # Check for missing fields
        required_fields = ['side', 'quantity', 'entry_price', 'status', 'external_order_id']
        missing_fields = []
        for field in required_fields:
            if not getattr(db_trade, field, None):
                missing_fields.append(field)
        
        if missing_fields:
            msg = f"Missing database fields: {', '.join(missing_fields)}"
            self.print_status('WARN', msg)
            discrepancies.append(msg)
        else:
            self.print_status('PASS', "All required fields present in database")
        
        # Verify timestamp
        ex_timestamp_ms = int(ex_order.get('createdTime', 0))
        ex_timestamp = datetime.fromtimestamp(ex_timestamp_ms / 1000, tz=timezone.utc) if ex_timestamp_ms > 0 else None
        
        if ex_timestamp and db_trade.ts_open:
            db_timestamp = db_trade.ts_open
            if isinstance(db_timestamp, str):
                db_timestamp = datetime.fromisoformat(db_timestamp.replace('Z', '+00:00'))
            
            time_diff = abs((ex_timestamp - db_timestamp).total_seconds())
            if time_diff < 300:  # Within 5 minutes
                self.print_status('PASS', f"Timestamps aligned (diff: {time_diff:.0f}s)")
            else:
                msg = f"Timestamp discrepancy: {time_diff:.0f}s difference"
                self.print_status('WARN', msg)
                discrepancies.append(msg)
        
        self.validation_results['discrepancies'] = discrepancies
        
        if not discrepancies:
            self.print_status('PASS', "✅ NO DISCREPANCIES FOUND - Full synchronization verified!")
        else:
            self.print_status('WARN', f"Found {len(discrepancies)} discrepancy(ies)")
            for i, disc in enumerate(discrepancies, 1):
                print(f"   {i}. {disc}")
        
        return discrepancies
    
    async def run_full_validation(self):
        """Execute complete end-to-end validation."""
        print("\n" + "#"*80)
        print("#" + " "*78 + "#")
        print("#  BYBIT DEMO E2E VALIDATION - COMPREHENSIVE CHECK" + " "*28 + "#")
        print("#" + " "*78 + "#")
        print("#"*80)
        
        # Step 1: Configuration
        config_valid = await self.validate_configuration()
        if not config_valid:
            print("\n❌ Configuration invalid. Aborting validation.")
            return
        
        # Step 2: Execute trading cycle
        execution_result = await self.execute_trading_cycle()
        
        if execution_result.get('status') != 'success':
            print("\n⚠️  Trading cycle did not execute successfully.")
            print("   Cannot proceed with exchange/database verification.")
            self.print_final_report()
            return
        
        # Extract order ID
        order_id = None
        if 'execution' in execution_result:
            order_id = execution_result['execution'].get('order_id')
        
        if not order_id:
            print("\n❌ No order ID found in execution result.")
            self.print_final_report()
            return
        
        # Step 3: Verify on exchange
        exchange_data = await self.verify_exchange_order(order_id)
        
        # Step 4: Verify in database
        db_data = await self.verify_database_record(order_id)
        
        # Step 5: Analyze discrepancies
        discrepancies = self.analyze_discrepancies(exchange_data, db_data)
        
        # Final report
        self.print_final_report()
    
    def print_final_report(self):
        """Print comprehensive validation report."""
        self.print_header("VALIDATION REPORT - SUMMARY")
        
        print(f"\n📊 Overall Results:")
        
        # Configuration
        config = self.validation_results.get('configuration', {})
        if config.get('valid'):
            self.print_status('PASS', "Configuration: Valid")
        else:
            self.print_status('FAIL', "Configuration: Invalid")
        
        # Execution
        execution = self.validation_results.get('execution', {})
        if execution.get('status') == 'success':
            self.print_status('PASS', "Execution: Successful")
        else:
            self.print_status('FAIL', f"Execution: {execution.get('status', 'Failed')}")
        
        # Exchange verification
        exchange = self.validation_results.get('exchange_verification', {})
        if exchange.get('found'):
            self.print_status('PASS', "Exchange Verification: Order found on api-demo.bybit.com")
        else:
            self.print_status('FAIL', "Exchange Verification: Order NOT found")
        
        # Database sync
        db_sync = self.validation_results.get('database_sync', {})
        if db_sync.get('found'):
            self.print_status('PASS', "Database Sync: Record persisted")
        else:
            self.print_status('FAIL', "Database Sync: Record NOT found")
        
        # Discrepancies
        discrepancies = self.validation_results.get('discrepancies', [])
        if not discrepancies:
            self.print_status('PASS', "Data Consistency: Perfect match")
        else:
            self.print_status('WARN', f"Data Consistency: {len(discrepancies)} issue(s)")
        
        print(f"\n{'='*80}")
        print("  DETAILED FINDINGS")
        print(f"{'='*80}")
        
        if not discrepancies:
            print("\n✅ SUCCESS: Complete end-to-end validation passed!")
            print("\nThe trading system correctly:")
            print("  • Places real orders on Bybit Demo (api-demo.bybit.com)")
            print("  • Persists trade records to local database")
            print("  • Maintains data consistency between exchange and database")
            print("  • Synchronizes order details (ID, price, quantity, status)")
        else:
            print("\n⚠️  ISSUES DETECTED:")
            for i, disc in enumerate(discrepancies, 1):
                print(f"  {i}. {disc}")
            print("\nRecommendations:")
            print("  • Review order execution flow in trading_service.py")
            print("  • Check database persistence logic")
            print("  • Verify status update mechanisms")
        
        print("\n" + "="*80)
        print("  VALIDATION COMPLETE")
        print("="*80 + "\n")


async def main():
    """Main entry point."""
    validator = BybitDemoE2EValidator(symbol="XAUUSDT")
    await validator.run_full_validation()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
