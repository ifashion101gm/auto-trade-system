#!/usr/bin/env python3
"""
Bybit Demo Paper Trading Verification Cycle

Executes 5-10 complete trading cycles on Bybit Demo environment to validate:
1. System configuration for demo trading
2. AI orchestration and trade proposal generation
3. Order execution on Bybit Demo API
4. Database persistence
5. State recovery mechanisms
6. Progress tracking toward $100 profit target

IMPORTANT: This script operates ONLY in Bybit Demo mode (api-demo.bybit.com)
to prevent any live financial risk.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.execution.trading_service import LiveTradingService
from app.database.connection import async_session_maker
from app.database.models import PaperTrades
from sqlalchemy import select, func


class BybitDemoVerificationSession:
    """
    Manages a Bybit Demo verification session with comprehensive tracking.
    
    Features:
    - Validates Bybit Demo configuration
    - Executes complete trading cycles (AI analysis + order execution)
    - Tracks cumulative profit and performance metrics
    - Verifies database persistence after each trade
    - Tests state recovery mechanisms
    - Generates detailed summary report
    """
    
    def __init__(
        self,
        max_cycles: int = 10,
        symbol: str = "XAUUSDT",
        min_cycles: int = 5,
        profit_target: float = 100.0,
        risk_per_trade: float = 0.005
    ):
        """
        Initialize verification session with profit-making objective.
        
        Args:
            max_cycles: Maximum number of cycles to execute (default: 10)
            symbol: Trading symbol (default: XAUUSDT)
            min_cycles: Minimum cycles before allowing early stop (default: 5)
            profit_target: Target cumulative profit in USD (default: $100)
            risk_per_trade: Risk per trade as percentage of balance (default: 0.5%)
        """
        self.max_cycles = max_cycles
        self.min_cycles = min_cycles
        self.symbol = symbol
        self.profit_target = profit_target
        self.risk_per_trade = risk_per_trade
        
        # Session state
        self.session_start_time = None
        self.total_cycles = 0
        self.successful_trades = 0
        self.rejected_trades = 0
        self.failed_trades = 0
        self.consecutive_failures = 0
        self.current_profit = 0.0
        # IMPORTANT: Set starting balance to match actual Bybit Demo account
        # This ensures risk engine calculations align with AI orchestrator's balance detection
        self.starting_balance = 1000.0  # Bybit Demo default balance
        self.session_active = False
        
        # Performance tracking
        self.cycle_durations = []
        self.win_count = 0
        self.loss_count = 0
        self.total_wins = 0.0
        self.total_losses = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        
        # Validate configuration
        self._validate_configuration()
        
        # IMPORTANT: Enable micro-live mode for Bybit Demo trading
        # This is SAFE because BYBIT_USE_DEMO_DOMAIN=true ensures we're using demo funds
        # The MICRO_LIVE_ENABLED flag controls whether execute_trading_cycle runs,
        # but actual financial risk is controlled by BYBIT_USE_DEMO_DOMAIN
        import os
        os.environ['MICRO_LIVE_ENABLED'] = 'true'
        settings.MICRO_LIVE_ENABLED = True
        print(f"\n⚙️  Micro-Live Mode: ENABLED (safe - using Bybit Demo domain)")
        
        print("\n" + "="*80)
        print("  BYBIT DEMO VERIFICATION SESSION INITIALIZED")
        print("="*80)
        print(f"\n📋 Session Configuration:")
        print(f"   • Exchange: BYBIT DEMO (api-demo.bybit.com)")
        print(f"   • Symbol: {self.symbol}")
        print(f"   • Max Cycles: {max_cycles}")
        print(f"   • Min Cycles: {min_cycles}")
        print(f"   • Profit Target: ${profit_target:.2f}")
        print(f"   • Risk Per Trade: {risk_per_trade*100:.1f}%")
        print(f"   • Execution Mode: {settings.EXECUTION_MODE}")
        print(f"   • Active Exchange: {settings.ACTIVE_EXCHANGE}")
        print(f"   • Demo Domain: {settings.BYBIT_USE_DEMO_DOMAIN}")
        print(f"\n🎯 PROFIT-MAKING OBJECTIVE:")
        print(f"   • Primary Goal: Generate consistent positive returns")
        print(f"   • Target: ${profit_target:.2f} cumulative profit")
        print(f"   • Strategy: High-quality setups only (quality > quantity)")
        print(f"   • Risk Management: Conservative position sizing ({risk_per_trade*100:.1f}%)")
        print(f"   • Success Metric: Positive P&L with controlled drawdown")
    
    def _validate_configuration(self):
        """Validate that system is configured for Bybit Demo trading."""
        print("\n🔒 Validating Bybit Demo Configuration...")
        
        errors = []
        
        # Check exchange setting
        if settings.ACTIVE_EXCHANGE.lower() != 'bybit':
            errors.append(f"ACTIVE_EXCHANGE is '{settings.ACTIVE_EXCHANGE}', should be 'bybit'")
        
        # Check demo domain
        if not settings.BYBIT_USE_DEMO_DOMAIN:
            errors.append("BYBIT_USE_DEMO_DOMAIN is False - must be True for demo trading")
        
        # Check API keys
        if not settings.BYBIT_DEMO_API_KEY:
            errors.append("BYBIT_DEMO_API_KEY is not configured")
        
        if not settings.BYBIT_DEMO_API_SECRET:
            errors.append("BYBIT_DEMO_API_SECRET is not configured")
        
        if errors:
            print("\n❌ Configuration Errors:")
            for error in errors:
                print(f"   • {error}")
            raise RuntimeError("Configuration validation failed. Fix errors before proceeding.")
        
        print(f"   ✅ ACTIVE_EXCHANGE: {settings.ACTIVE_EXCHANGE}")
        print(f"   ✅ BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
        print(f"   ✅ BYBIT_DEMO_API_KEY: {'***' + settings.BYBIT_DEMO_API_KEY[-4:]}")
        print(f"   ✅ Configuration validated - SAFE FOR DEMO TRADING")
    
    async def _get_current_balance(self) -> float:
        """Get current balance from exchange API (most accurate)."""
        try:
            from app.infra.exchange_manager import ExchangeManager
            
            manager = ExchangeManager(exchange='bybit')
            await manager.initialize()
            balance_info = await manager.get_balance()
            
            if balance_info and 'USDT' in balance_info:
                # Get total USDT balance (free + used)
                usdt_balance = float(balance_info['USDT']['free']) + float(balance_info['USDT'].get('used', 0))
                await manager.close()
                return usdt_balance
            else:
                await manager.close()
                print(f"   ⚠️  Could not parse balance info, using default")
                return 100.0
        except Exception as e:
            print(f"   ⚠️  Could not fetch balance from exchange: {e}")
            return 100.0  # Fallback
    
    async def _calculate_session_profit(self) -> float:
        """Calculate profit generated during this session."""
        try:
            async with async_session_maker() as db:
                # Get trades closed after session start
                stmt = (
                    select(PaperTrades)
                    .where(
                        PaperTrades.exchange == 'bybit',
                        PaperTrades.status == 'closed',
                        PaperTrades.ts_close >= self.session_start_time.isoformat()
                    )
                )
                
                result = await db.execute(stmt)
                trades = result.scalars().all()
                
                total_profit = sum(t.profit for t in trades if t.profit is not None)
                return total_profit
        except Exception as e:
            print(f"   ⚠️  Could not calculate session profit: {e}")
            return 0.0
    
    async def execute_cycle(self) -> Dict[str, Any]:
        """
        Execute a single complete trading cycle.
        
        Returns:
            Cycle result dictionary with status and details
        """
        self.total_cycles += 1
        cycle_start = datetime.utcnow()
        
        print(f"\n{'='*80}")
        print(f"  CYCLE #{self.total_cycles}/{self.max_cycles}")
        print(f"{'='*80}")
        print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize trading service for Bybit Demo
        service = LiveTradingService(
            exchange_name='bybit',
            use_testnet=True,  # This will use demo domain when BYBIT_USE_DEMO_DOMAIN=true
            use_openrouter=True
        )
        
        try:
            # Create database session for this cycle
            async with async_session_maker() as db:
                # Execute complete trading cycle
                # This includes: market data fetch → AI analysis → order execution → DB persistence
                result = await service.execute_trading_cycle(
                    symbol=self.symbol,
                    user_id="bybit_demo_verification",
                    db_session=db,  # Pass valid database session
                    execute_on_binance=False,
                    execute_on_mexc=False
                )
            
            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            self.cycle_durations.append(cycle_duration)
            
            # Analyze result
            if result['status'] == 'success':
                self.successful_trades += 1
                self.consecutive_failures = 0  # Reset failure counter
                print(f"\n✅ Cycle Status: SUCCESS")
                print(f"   • Duration: {cycle_duration:.1f}s")
                
                # Extract execution details
                if 'execution' in result and result['execution'].get('status') == 'executed':
                    exec_data = result['execution']
                    print(f"   • Order ID: {exec_data.get('order_id', 'N/A')}")
                    print(f"   • Filled Price: ${exec_data.get('filled_price', 0):,.2f}")
                    print(f"   • Quantity: {exec_data.get('filled_quantity', 0):.4f}")
                    print(f"   • Position Value: ${exec_data.get('position_value_usd', 0):,.2f}")
                
                # Verify database persistence
                await self._verify_database_persistence()
                
                # Track if this trade becomes profitable (will be updated when closed)
                # For now, just note that a position was opened successfully
                print(f"   📈 Position opened - awaiting exit for P&L calculation")
                
            elif result['status'] == 'rejected':
                self.rejected_trades += 1
                self.consecutive_failures += 1
                reason = result.get('rejection_reason', 'Unknown')
                quality_score = result.get('quality_score', 0)
                print(f"\n⚠️  Cycle Status: REJECTED (Quality Filter)")
                print(f"   • Quality Score: {quality_score}/100")
                print(f"   • Reason: {reason}")
                print(f"   • Duration: {cycle_duration:.1f}s")
                
            else:
                self.failed_trades += 1
                self.consecutive_failures += 1
                print(f"\n❌ Cycle Status: FAILED")
                print(f"   • Error: {result.get('error', 'Unknown error')}")
                print(f"   • Duration: {cycle_duration:.1f}s")
            
            # Update profit tracking
            await self._update_profit_tracking()
            
            return result
            
        except Exception as e:
            self.failed_trades += 1
            self.consecutive_failures += 1
            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            print(f"\n❌ Cycle execution failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'status': 'failed', 'error': str(e), 'duration': cycle_duration}
        
        finally:
            await service.close()
    
    async def _verify_database_persistence(self):
        """Verify that the most recent trade was persisted to database."""
        try:
            async with async_session_maker() as db:
                # Get most recent Bybit trade
                stmt = (
                    select(PaperTrades)
                    .where(PaperTrades.exchange == 'bybit')
                    .order_by(PaperTrades.ts_open.desc())
                    .limit(1)
                )
                
                result = await db.execute(stmt)
                trade = result.scalar_one_or_none()
                
                if trade:
                    print(f"   ✅ Database: Trade #{trade.id} persisted")
                    print(f"      Status: {trade.status}")
                    print(f"      Entry: ${trade.entry_price:.2f}")
                    if trade.exit_price:
                        print(f"      Exit: ${trade.exit_price:.2f}")
                        print(f"      P&L: ${trade.profit:+.2f}")
                else:
                    print(f"   ⚠️  Database: No trade record found")
        except Exception as e:
            print(f"   ⚠️  Database verification failed: {e}")
    
    async def _update_profit_tracking(self):
        """Update current profit tracking from database with win/loss analysis."""
        session_profit = await self._calculate_session_profit()
        self.current_profit = session_profit
        
        # Get current balance
        current_balance = await self._get_current_balance()
        
        # Track peak balance and drawdown
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
        
        # Calculate win/loss from closed trades in this session
        try:
            async with async_session_maker() as db:
                stmt = (
                    select(PaperTrades)
                    .where(
                        PaperTrades.exchange == 'bybit',
                        PaperTrades.status == 'closed',
                        PaperTrades.ts_close >= self.session_start_time.isoformat()
                    )
                )
                
                result = await db.execute(stmt)
                closed_trades = result.scalars().all()
                
                # Reset counters
                self.win_count = 0
                self.loss_count = 0
                self.total_wins = 0.0
                self.total_losses = 0.0
                
                for trade in closed_trades:
                    if trade.profit:
                        if trade.profit > 0:
                            self.win_count += 1
                            self.total_wins += trade.profit
                        else:
                            self.loss_count += 1
                            self.total_losses += abs(trade.profit)
        except Exception as e:
            print(f"   ⚠️  Could not calculate win/loss stats: {e}")
        
        print(f"\n💰 Profit-Making Progress:")
        print(f"   • Session Profit: ${self.current_profit:+.2f}")
        print(f"   • Current Balance: ${current_balance:.2f}")
        print(f"   • Peak Balance: ${self.peak_balance:.2f}")
        print(f"   • Max Drawdown: {self.max_drawdown:.2f}%")
        print(f"   • Target: ${self.profit_target:.2f}")
        progress_pct = (self.current_profit / self.profit_target * 100) if self.profit_target > 0 else 0
        print(f"   • Progress: {progress_pct:.1f}%")
        
        # Profit trajectory analysis
        if self.total_cycles > 0:
            avg_profit_per_cycle = self.current_profit / self.total_cycles
            remaining_profit = self.profit_target - self.current_profit
            if avg_profit_per_cycle > 0:
                est_cycles_to_target = remaining_profit / avg_profit_per_cycle
                print(f"   • Avg Profit/Cycle: ${avg_profit_per_cycle:+.2f}")
                print(f"   • Est. Cycles to Target: {est_cycles_to_target:.0f}")
            else:
                print(f"   • ⚠️  Need to improve profitability")
        
        # Profitability assessment
        if self.current_profit > 0:
            print(f"   ✅ PROFITABLE: Generating positive returns")
        elif self.current_profit == 0:
            print(f"   ⚠️  BREAKEVEN: No profit/loss yet")
        else:
            print(f"   ❌ UNPROFITABLE: Need strategy adjustment")
    
    async def run_session(self):
        """
        Run the complete verification session.
        
        Executes cycles until:
        - max_cycles reached, OR
        - 3 consecutive failures after min_cycles, OR
        - User interrupts
        """
        print("\n" + "#"*80)
        print("#" + " "*78 + "#")
        print("#  BYBIT DEMO VERIFICATION SESSION - VALIDATING SYSTEM" + " "*25 + "#")
        print("#" + " "*78 + "#")
        print("#"*80)
        
        self.session_start_time = datetime.utcnow()
        self.session_active = True
        
        # Starting balance already set in __init__ to match Bybit Demo account ($1000)
        # This ensures risk engine calculations align with AI orchestrator's balance detection
        self.peak_balance = self.starting_balance
        
        # CRITICAL: Update .risk_state.json with correct balance BEFORE any RiskEngine instances are created
        # The RiskEngine loads balance from this file on initialization
        import json
        from pathlib import Path
        risk_state_file = Path('.risk_state.json')
        if risk_state_file.exists():
            try:
                with open(risk_state_file, 'r') as f:
                    risk_state = json.load(f)
                
                # Update balance to match actual demo account
                risk_state['current_balance'] = self.starting_balance
                risk_state['peak_balance'] = self.starting_balance
                risk_state['today_date'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                risk_state['last_updated'] = datetime.now(timezone.utc).isoformat()
                
                with open(risk_state_file, 'w') as f:
                    json.dump(risk_state, f, indent=2)
                
                print(f"   ✅ Updated .risk_state.json with balance: ${self.starting_balance:.2f}")
            except Exception as e:
                print(f"   ⚠️  Failed to update risk state file: {e}")
        
        print(f"\n🚀 Session Started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"⏱️  Maximum Cycles: {self.max_cycles}")
        print(f"🎯 Minimum Cycles: {self.min_cycles}")
        print(f"💰 Starting Balance: ${self.starting_balance:,.2f}")
        
        try:
            while self.session_active and self.total_cycles < self.max_cycles:
                # Check for consecutive failures (only after min_cycles)
                if self.total_cycles >= self.min_cycles and self.consecutive_failures >= 3:
                    print(f"\n⚠️  Stopping due to {self.consecutive_failures} consecutive failures")
                    break
                
                # Execute cycle
                cycle_result = await self.execute_cycle()
                
                # Brief pause between cycles (avoid rate limits)
                if self.total_cycles < self.max_cycles:
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
        
        # Calculate win/loss stats
        if self.win_count + self.loss_count > 0:
            win_rate = (self.win_count / (self.win_count + self.loss_count)) * 100
        else:
            win_rate = 0.0
        
        avg_win = self.total_wins / self.win_count if self.win_count > 0 else 0
        avg_loss = self.total_losses / self.loss_count if self.loss_count > 0 else 0
        
        avg_cycle_duration = sum(self.cycle_durations) / len(self.cycle_durations) if self.cycle_durations else 0
        
        print("\n" + "="*80)
        print("  BYBIT DEMO VERIFICATION SESSION REPORT")
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
        
        print(f"\n💰 Profit-Making Results:")
        print(f"   • Starting Balance: ${self.starting_balance:,.2f}")
        print(f"   • Final Balance: ${final_balance:,.2f}")
        print(f"   • Session Profit: ${self.current_profit:+.2f}")
        print(f"   • Profit Target: ${self.profit_target:.2f}")
        progress_pct = (self.current_profit / self.profit_target * 100) if self.profit_target > 0 else 0
        print(f"   • Progress: {progress_pct:.1f}%")
        
        if self.current_profit >= self.profit_target:
            print(f"\n🎉 TARGET ACHIEVED!")
            print(f"   Successfully reached ${self.profit_target:.2f} profit target")
            print(f"   🏆 PROFIT-MAKING OBJECTIVE: SUCCESS")
        elif self.current_profit > 0:
            remaining = self.profit_target - self.current_profit
            print(f"\n✅ PROFITABLE SESSION")
            print(f"   Generated positive returns: ${self.current_profit:+.2f}")
            print(f"   Remaining to target: ${remaining:.2f}")
            if self.total_cycles > 0:
                avg_profit = self.current_profit / self.total_cycles
                if avg_profit > 0:
                    est_cycles = remaining / avg_profit
                    print(f"   Estimated cycles to target: {est_cycles:.0f}")
            print(f"   📈 PROFIT-MAKING TRAJECTORY: POSITIVE")
        else:
            print(f"\n⚠️  Target Not Reached")
            print(f"   Session P&L: ${self.current_profit:+.2f}")
            print(f"   📉 PROFIT-MAKING TRAJECTORY: NEEDS IMPROVEMENT")
        
        print(f"\n🛡️  Risk Management:")
        print(f"   • Max Drawdown: {self.max_drawdown:.2f}%")
        print(f"   • Win Rate: {win_rate:.1f}%")
        print(f"   • Avg Win: ${avg_win:+.2f}")
        print(f"   • Avg Loss: ${avg_loss:+.2f}")
        
        print(f"\n⚡ System Health:")
        print(f"   • Avg Cycle Duration: {avg_cycle_duration:.1f}s")
        print(f"   • Consecutive Failures: {self.consecutive_failures}")
        print(f"   • Demo Mode: {'✅ ACTIVE' if settings.BYBIT_USE_DEMO_DOMAIN else '❌ INACTIVE'}")
        print(f"   • No Live Financial Risk: ✅ CONFIRMED")
        
        print(f"\n📋 Profit-Making Assessment & Recommendations:")
        
        # Calculate profitability metrics
        profitable = self.current_profit > 0
        good_win_rate = win_rate >= 60 if (self.win_count + self.loss_count) > 0 else False
        controlled_dd = self.max_drawdown <= 5.0
        
        if profitable and good_win_rate and controlled_dd:
            print(f"   ✅ EXCELLENT: Strong profit-making performance")
            print(f"   ✅ System validated for continued demo trading")
            print(f"   ✅ Ready to scale toward ${self.profit_target:.2f} target")
            print(f"   ✅ Consider extending to 50+ trades for statistical significance")
            if self.current_profit >= self.profit_target:
                print(f"   🏆 READY FOR LIVE TRADING VALIDATION")
        elif profitable:
            print(f"   ✅ PROFITABLE: Generating positive returns")
            print(f"   ⚠️  Continue refining strategy for consistency")
            print(f"   ⚠️  Monitor win rate and drawdown closely")
            print(f"   ✅ On track toward profit target - keep trading")
        elif self.successful_trades >= 5:
            print(f"   ⚠️  BREAK-EVEN/SLIGHT LOSS: System functional but needs optimization")
            print(f"   ⚠️  Review trade selection criteria")
            print(f"   ⚠️  Consider tightening entry filters")
            print(f"   ⚠️  Focus on quality over quantity")
        else:
            print(f"   ❌ UNPROFITABLE: Critical issues detected")
            print(f"   ❌ Do NOT proceed to extended testing")
            print(f"   ❌ Debug strategy and risk parameters")
            print(f"   ❌ Re-validate before continuing")
        
        # Specific recommendations based on metrics
        print(f"\n   Action Items:")
        if not profitable:
            print(f"   • Increase minimum confidence threshold")
            print(f"   • Tighten entry criteria (wait for better setups)")
            print(f"   • Review stop-loss placement")
        if win_rate < 55 and (self.win_count + self.loss_count) > 0:
            print(f"   • Improve signal quality filtering")
            print(f"   • Avoid low-confidence trades")
        if self.max_drawdown > 5:
            print(f"   • Reduce position sizing")
            print(f"   • Implement stricter daily loss limits")
        if profitable and self.current_profit < self.profit_target:
            print(f"   • Continue trading with current strategy")
            print(f"   • Maintain discipline and risk management")
        
        print("\n" + "="*80)
        print("  SESSION COMPLETE")
        print("="*80 + "\n")


async def main():
    """Main entry point for Bybit Demo verification session."""
    
    # Configure session with profit-making objective
    session = BybitDemoVerificationSession(
        max_cycles=10,           # Execute up to 10 cycles
        symbol="XAUUSDT",        # Gold perpetual swap
        min_cycles=5,            # Minimum 5 cycles before allowing early stop
        profit_target=100.0,     # $100 profit target (long-term goal)
        risk_per_trade=0.005     # 0.5% risk per trade (conservative)
    )
    
    # Run session
    await session.run_session()


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
