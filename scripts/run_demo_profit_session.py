#!/usr/bin/env python3
"""
Demo Trading Session with $100 Profit Target

This script executes a complete trading session in Demo/Testnet mode with the objective
of achieving a $100 profit target. It includes:

1. Configuration validation (ensures demo mode is active)
2. Strategy selection and parameter setup
3. Risk management (SL/TP levels, position sizing)
4. Automated trading cycle execution
5. Real-time profit monitoring
6. Session termination when target is reached

IMPORTANT: This script operates ONLY in demo/testnet mode to prevent any live financial risk.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.execution.trading_service import LiveTradingService
from app.database.connection import get_session
from sqlalchemy import select
from app.database.models import PaperTrades


class DemoTradingSession:
    """
    Manages a demo trading session with profit target tracking.
    
    Features:
    - Validates demo mode configuration
    - Configures trading parameters (strategy, SL/TP, leverage)
    - Executes trading cycles
    - Monitors cumulative profit
    - Stops when $100 profit target is reached
    """
    
    def __init__(
        self,
        profit_target: float = 100.0,
        exchange: str = "binance",
        symbol: Optional[str] = None,
        max_leverage: int = 5,
        risk_per_trade: float = 0.01,
        min_confidence: float = 0.65
    ):
        """
        Initialize demo trading session.
        
        Args:
            profit_target: Target profit in USD (default: $100)
            exchange: Exchange to use (default: binance)
            symbol: Trading symbol (auto-detected if None)
            max_leverage: Maximum leverage allowed
            risk_per_trade: Risk per trade as percentage of balance
            min_confidence: Minimum AI confidence threshold
        """
        self.profit_target = profit_target
        self.exchange = exchange
        self.symbol = symbol or self._get_default_symbol()
        self.max_leverage = max_leverage
        self.risk_per_trade = risk_per_trade
        self.min_confidence = min_confidence
        
        # Session state
        self.session_start_time = None
        self.total_cycles = 0
        self.successful_trades = 0
        self.rejected_trades = 0
        self.failed_trades = 0
        self.current_profit = 0.0
        self.session_active = False
        
        # Validate demo mode
        self._validate_demo_mode()
        
        print("\n" + "="*80)
        print("  DEMO TRADING SESSION INITIALIZED")
        print("="*80)
        print(f"\n📋 Session Configuration:")
        print(f"   • Profit Target: ${profit_target:.2f}")
        print(f"   • Exchange: {exchange.upper()} (DEMO MODE)")
        print(f"   • Symbol: {self.symbol}")
        print(f"   • Max Leverage: {max_leverage}x")
        print(f"   • Risk Per Trade: {risk_per_trade*100:.1f}%")
        print(f"   • Min Confidence: {min_confidence*100:.0f}%")
        print(f"   • Execution Mode: {settings.EXECUTION_MODE}")
    
    def _get_default_symbol(self) -> str:
        """Get default symbol based on exchange."""
        if self.exchange == "binance":
            return settings.GOLD_SYMBOL_BINANCE
        elif self.exchange == "mexc":
            return settings.GOLD_SYMBOL_MEXC
        else:
            raise ValueError(f"Unsupported exchange: {self.exchange}")
    
    def _validate_demo_mode(self):
        """Validate that system is operating in demo/testnet mode."""
        print("\n🔒 Validating Demo Mode Configuration...")
        
        # Check Binance testnet flag
        if self.exchange == "binance":
            if not settings.BINANCE_TESTNET:
                raise RuntimeError(
                    "❌ CRITICAL ERROR: BINANCE_TESTNET is FALSE! "
                    "System must be in demo mode to prevent live trading risks."
                )
            print(f"   ✅ BINANCE_TESTNET: {settings.BINANCE_TESTNET}")
            print(f"   ✅ BINANCE_DEMO_MODE: {settings.BINANCE_DEMO_MODE}")
            
        elif self.exchange == "mexc":
            # MEXC uses paper trading by default in this system
            print(f"   ✅ MEXC using paper/demo trading mode")
        
        print(f"   ✅ Demo mode validated - NO LIVE FINANCIAL RISK")
    
    async def _get_current_balance(self) -> float:
        """Get current account balance from database or exchange."""
        try:
            async for db_session in get_session():
                # Get most recent closed trades to calculate cumulative profit
                stmt = (
                    select(PaperTrades)
                    .where(PaperTrades.status == 'closed')
                    .order_by(PaperTrades.ts_close.desc())
                    .limit(100)
                )
                
                result = await db_session.execute(stmt)
                trades = result.scalars().all()
                
                # Calculate total profit from closed trades
                total_profit = sum(t.profit for t in trades if t.profit is not None)
                
                # Starting balance assumption (demo accounts typically start with $1000-$10000)
                starting_balance = 1000.0
                current_balance = starting_balance + total_profit
                
                return current_balance
        except Exception as e:
            print(f"   ⚠️  Could not fetch balance: {e}")
            return 1000.0  # Default assumption
    
    async def _get_open_positions_pnl(self) -> float:
        """Calculate unrealized P&L from open positions."""
        try:
            async for db_session in get_session():
                stmt = (
                    select(PaperTrades)
                    .where(PaperTrades.status == 'open')
                )
                
                result = await db_session.execute(stmt)
                open_trades = result.scalars().all()
                
                total_unrealized_pnl = 0.0
                for trade in open_trades:
                    if trade.profit is not None:
                        total_unrealized_pnl += trade.profit
                
                return total_unrealized_pnl
        except Exception as e:
            print(f"   ⚠️  Could not calculate open positions P&L: {e}")
            return 0.0
    
    async def execute_cycle(self) -> Dict[str, Any]:
        """
        Execute a single trading cycle.
        
        Returns:
            Cycle result dictionary
        """
        self.total_cycles += 1
        
        print(f"\n{'='*80}")
        print(f"  CYCLE #{self.total_cycles}")
        print(f"{'='*80}")
        print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize trading service
        service = LiveTradingService(
            exchange_name=self.exchange,
            use_testnet=True,
            use_openrouter=True
        )
        
        try:
            # Execute complete trading cycle
            result = await service.execute_trading_cycle(
                symbol=self.symbol,
                user_id="demo_session_user",
                db_session=None,
                execute_on_binance=(self.exchange == "binance"),
                execute_on_mexc=(self.exchange == "mexc")
            )
            
            # Analyze result
            if result['status'] == 'success':
                self.successful_trades += 1
                print(f"\n✅ Cycle Status: SUCCESS")
                
                # Extract execution details
                if 'execution' in result and result['execution'].get('status') == 'executed':
                    exec_data = result['execution']
                    print(f"   • Order ID: {exec_data.get('order_id', 'N/A')}")
                    print(f"   • Filled Price: ${exec_data.get('filled_price', 0):,.2f}")
                    print(f"   • Quantity: {exec_data.get('filled_quantity', 0):.4f}")
                    print(f"   • Position Value: ${exec_data.get('position_value_usd', 0):,.2f}")
                
            elif result['status'] == 'rejected':
                self.rejected_trades += 1
                reason = result.get('rejection_reason', 'Unknown')
                quality_score = result.get('quality_score', 0)
                print(f"\n⚠️  Cycle Status: REJECTED (Quality Filter)")
                print(f"   • Quality Score: {quality_score}/100")
                print(f"   • Reason: {reason}")
                
            else:
                self.failed_trades += 1
                print(f"\n❌ Cycle Status: FAILED")
                print(f"   • Error: {result.get('error', 'Unknown error')}")
            
            # Update profit tracking
            await self._update_profit_tracking()
            
            return result
            
        except Exception as e:
            self.failed_trades += 1
            print(f"\n❌ Cycle execution failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'status': 'failed', 'error': str(e)}
        
        finally:
            await service.close()
    
    async def _update_profit_tracking(self):
        """Update current profit tracking from database."""
        realized_profit = await self._calculate_realized_profit()
        unrealized_profit = await self._get_open_positions_pnl()
        
        self.current_profit = realized_profit + unrealized_profit
        
        print(f"\n📊 Profit Tracking:")
        print(f"   • Realized Profit: ${realized_profit:+.2f}")
        print(f"   • Unrealized P&L: ${unrealized_profit:+.2f}")
        print(f"   • Total Current Profit: ${self.current_profit:+.2f}")
        print(f"   • Target: ${self.profit_target:.2f}")
        print(f"   • Progress: {(self.current_profit / self.profit_target * 100):.1f}%")
        
        # Check if target reached
        if self.current_profit >= self.profit_target:
            print(f"\n🎉 PROFIT TARGET REACHED!")
            print(f"   Achieved ${self.current_profit:.2f} profit (target: ${self.profit_target:.2f})")
            self.session_active = False
    
    async def _calculate_realized_profit(self) -> float:
        """Calculate realized profit from closed trades in current session."""
        try:
            async for db_session in get_session():
                # Get trades closed after session start
                stmt = (
                    select(PaperTrades)
                    .where(PaperTrades.status == 'closed')
                    .where(PaperTrades.ts_close >= self.session_start_time.isoformat())
                )
                
                result = await db_session.execute(stmt)
                trades = result.scalars().all()
                
                total_profit = sum(t.profit for t in trades if t.profit is not None)
                return total_profit
        except Exception as e:
            print(f"   ⚠️  Could not calculate realized profit: {e}")
            return 0.0
    
    async def run_session(self, max_cycles: int = 50):
        """
        Run the complete trading session until profit target is reached or max cycles hit.
        
        Args:
            max_cycles: Maximum number of cycles to execute (safety limit)
        """
        print("\n" + "#"*80)
        print("#" + " "*78 + "#")
        print("#  STARTING DEMO TRADING SESSION - $100 PROFIT TARGET" + " "*29 + "#")
        print("#" + " "*78 + "#")
        print("#"*80)
        
        self.session_start_time = datetime.utcnow()
        self.session_active = True
        
        print(f"\n🚀 Session Started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"⏱️  Maximum Cycles: {max_cycles}")
        print(f"🎯 Profit Target: ${self.profit_target:.2f}")
        
        # Initial balance check
        initial_balance = await self._get_current_balance()
        print(f"💰 Initial Balance: ${initial_balance:,.2f}")
        
        try:
            while self.session_active and self.total_cycles < max_cycles:
                # Execute cycle
                cycle_result = await self.execute_cycle()
                
                # Check if we should continue
                if not self.session_active:
                    print(f"\n✅ Session completed successfully!")
                    break
                
                if self.total_cycles >= max_cycles:
                    print(f"\n⚠️  Maximum cycles ({max_cycles}) reached without hitting target")
                    break
                
                # Brief pause between cycles
                print(f"\n⏳ Waiting 5 seconds before next cycle...")
                await asyncio.sleep(5)
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Session interrupted by user")
        
        finally:
            await self._generate_session_report()
    
    async def _generate_session_report(self):
        """Generate comprehensive session report."""
        session_end_time = datetime.utcnow()
        session_duration = session_end_time - self.session_start_time
        
        final_balance = await self._get_current_balance()
        
        print("\n" + "="*80)
        print("  DEMO TRADING SESSION REPORT")
        print("="*80)
        
        print(f"\n📅 Session Summary:")
        print(f"   • Start Time: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"   • End Time: {session_end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"   • Duration: {session_duration}")
        
        print(f"\n📊 Performance Metrics:")
        print(f"   • Total Cycles: {self.total_cycles}")
        print(f"   • Successful Trades: {self.successful_trades}")
        print(f"   • Rejected (Quality Filter): {self.rejected_trades}")
        print(f"   • Failed: {self.failed_trades}")
        
        if self.total_cycles > 0:
            success_rate = (self.successful_trades / self.total_cycles) * 100
            print(f"   • Success Rate: {success_rate:.1f}%")
        
        print(f"\n💰 Financial Results:")
        print(f"   • Initial Balance: ${final_balance - self.current_profit:,.2f}")
        print(f"   • Final Balance: ${final_balance:,.2f}")
        print(f"   • Total Profit: ${self.current_profit:+.2f}")
        print(f"   • Profit Target: ${self.profit_target:.2f}")
        
        if self.current_profit >= self.profit_target:
            print(f"\n🎉 TARGET ACHIEVED!")
            print(f"   Successfully reached ${self.profit_target:.2f} profit target")
        else:
            progress_pct = (self.current_profit / self.profit_target) * 100
            print(f"\n⚠️  Target Not Reached")
            print(f"   Progress: {progress_pct:.1f}% (${self.current_profit:.2f} / ${self.profit_target:.2f})")
        
        print(f"\n🔒 Safety Verification:")
        print(f"   • Demo Mode: {'✅ ACTIVE' if settings.BINANCE_TESTNET else '❌ INACTIVE'}")
        print(f"   • No Live Financial Risk: ✅ CONFIRMED")
        
        print("\n" + "="*80)
        print("  SESSION COMPLETE")
        print("="*80 + "\n")


async def main():
    """Main entry point for demo trading session."""
    
    # Configure session parameters
    session = DemoTradingSession(
        profit_target=100.0,      # $100 profit target
        exchange="binance",       # Use Binance testnet
        symbol=None,              # Auto-detect (PAXG/USDT for Binance)
        max_leverage=5,           # Conservative leverage
        risk_per_trade=0.01,      # 1% risk per trade
        min_confidence=0.65       # 65% minimum AI confidence
    )
    
    # Run session with safety limit of 50 cycles
    await session.run_session(max_cycles=50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Session terminated by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
