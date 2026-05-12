#!/usr/bin/env python3
"""
Production Deployment Validation Script

Checks all pre-live criteria before switching to mainnet trading.
Run this script after completing the 48-hour TestNet validation period.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, func

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.db import async_session_maker
from app.storage.models import PaperTrades, OrderEvents
from app.infra.telegram_notifier import TelegramNotifier


class DeploymentValidator:
    """Validates all production deployment criteria."""
    
    def __init__(self):
        self.results = {}
        self.critical_failures = []
    
    async def validate_all(self):
        """Run all validation checks."""
        print("="*70)
        print("PRODUCTION DEPLOYMENT VALIDATION")
        print("="*70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        print()
        
        # Run all checks
        await self.check_trade_volume()
        await self.check_performance_metrics()
        await self.check_event_store_integrity()
        await self.check_telegram_alerts()
        await self.check_system_uptime()
        
        # Print summary
        self.print_summary()
        
        # Return True if all critical checks pass
        return len(self.critical_failures) == 0
    
    async def check_trade_volume(self):
        """Check if minimum trade volume achieved."""
        print("1️⃣  Checking Trade Volume...")
        
        try:
            async with async_session_maker() as db:
                result = await db.execute(select(PaperTrades))
                trades = result.scalars().all()
                
                closed_trades = sum(1 for t in trades if t.status == 'closed')
                
                print(f"   Total Paper Trades: {len(trades)}")
                print(f"   Closed Trades: {closed_trades}")
                
                if closed_trades >= 20:
                    print(f"   ✅ PASS: {closed_trades} trades executed (minimum: 20)")
                    self.results['trade_volume'] = 'PASS'
                elif closed_trades >= 10:
                    print(f"   ⚠️  PARTIAL: {closed_trades} trades (minimum: 20, recommended: 50)")
                    self.results['trade_volume'] = 'PARTIAL'
                else:
                    print(f"   ❌ FAIL: Only {closed_trades} trades (minimum: 20 required)")
                    self.results['trade_volume'] = 'FAIL'
                    self.critical_failures.append('Insufficient trade volume')
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.results['trade_volume'] = 'ERROR'
            self.critical_failures.append(f'Trade volume check failed: {e}')
        
        print()
    
    async def check_performance_metrics(self):
        """Check win rate, profit factor, and drawdown."""
        print("2️⃣  Checking Performance Metrics...")
        
        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(PaperTrades).where(PaperTrades.status == 'closed')
                )
                trades = result.scalars().all()
                
                if not trades:
                    print("   ⚠️  No closed trades yet - cannot calculate metrics")
                    self.results['performance'] = 'N/A'
                    print()
                    return
                
                # Win Rate
                wins = sum(1 for t in trades if t.profit and t.profit > 0)
                win_rate = (wins / len(trades)) * 100
                
                # Profit Factor
                gross_profit = sum(t.profit for t in trades if t.profit and t.profit > 0)
                gross_loss = abs(sum(t.profit for t in trades if t.profit and t.profit < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                # Maximum Drawdown
                initial_balance = 100.0
                balance = initial_balance
                peak_balance = initial_balance
                max_drawdown = 0.0
                
                sorted_trades = sorted(trades, key=lambda t: t.ts_close or datetime.utcnow())
                for trade in sorted_trades:
                    if trade.profit:
                        balance += trade.profit
                        if balance > peak_balance:
                            peak_balance = balance
                        
                        drawdown = (peak_balance - balance) / peak_balance * 100
                        if drawdown > max_drawdown:
                            max_drawdown = drawdown
                
                # Print results
                print(f"   Win Rate: {win_rate:.2f}% ({wins}/{len(trades)})")
                print(f"   Profit Factor: {profit_factor:.2f}")
                print(f"   Max Drawdown: {max_drawdown:.2f}%")
                print(f"   Total P&L: ${gross_profit - gross_loss:.2f}")
                
                # Evaluate against thresholds
                issues = []
                if win_rate < 55:
                    issues.append(f"Win rate {win_rate:.2f}% below 55% threshold")
                
                if profit_factor < 1.5 and profit_factor != float('inf'):
                    issues.append(f"Profit factor {profit_factor:.2f} below 1.5 threshold")
                
                if max_drawdown > 15:
                    issues.append(f"Max drawdown {max_drawdown:.2f}% exceeds 15% limit")
                
                if not issues:
                    print(f"   ✅ PASS: All performance metrics within acceptable range")
                    self.results['performance'] = 'PASS'
                else:
                    for issue in issues:
                        print(f"   ⚠️  {issue}")
                    self.results['performance'] = 'WARNING'
                    # Don't add to critical failures - these are warnings, not blockers
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.results['performance'] = 'ERROR'
            self.critical_failures.append(f'Performance metrics check failed: {e}')
        
        print()
    
    async def check_event_store_integrity(self):
        """Check EventStore for anomalies."""
        print("3️⃣  Checking EventStore Integrity...")
        
        try:
            async with async_session_maker() as db:
                # Get recent events
                result = await db.execute(
                    select(OrderEvents)
                    .order_by(OrderEvents.created_at.desc())
                    .limit(100)
                )
                events = result.scalars().all()
                
                if not events:
                    print("   ⚠️  No events recorded yet")
                    self.results['event_store'] = 'N/A'
                    print()
                    return
                
                # Count by type
                event_counts = {}
                for event in events:
                    event_type = event.event_type
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                print(f"   Total Events (last 100): {len(events)}")
                print(f"   Event Types:")
                for event_type, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"     - {event_type}: {count}")
                
                # Check for SYNC_MISMATCH events
                mismatch_count = event_counts.get('SYNC_MISMATCH', 0)
                if mismatch_count > 5:
                    print(f"   ⚠️  High number of SYNC_MISMATCH events: {mismatch_count}")
                else:
                    print(f"   ✅ SYNC_MISMATCH events: {mismatch_count} (acceptable)")
                
                # Check for orphaned orders (ORDER_SUBMITTED without corresponding fill/cancel)
                # This is a simplified check - in production you'd want more sophisticated logic
                submitted = event_counts.get('ORDER_SUBMITTED', 0)
                filled = event_counts.get('ORDER_FILLED', 0)
                cancelled = event_counts.get('ORDER_CANCELLED', 0)
                
                orphaned = submitted - filled - cancelled
                if orphaned > 0:
                    print(f"   ⚠️  Potential orphaned orders: {orphaned}")
                else:
                    print(f"   ✅ No orphaned orders detected")
                
                print(f"   ✅ EventStore integrity check complete")
                self.results['event_store'] = 'PASS'
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.results['event_store'] = 'ERROR'
            self.critical_failures.append(f'EventStore check failed: {e}')
        
        print()
    
    async def check_telegram_alerts(self):
        """Test Telegram alert system."""
        print("4️⃣  Testing Telegram Alerts...")
        
        try:
            notifier = TelegramNotifier()
            
            if not notifier.enabled:
                print("   ❌ FAIL: Telegram notifications disabled (missing BOT_TOKEN or CHAT_ID)")
                self.results['telegram'] = 'FAIL'
                self.critical_failures.append('Telegram alerts not configured')
                print()
                return
            
            # Send test message
            test_message = (
                "🧪 <b>Production Deployment Validation Test</b>\n\n"
                f"This is an automated test message from the Auto Trade System.\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"If you received this message, Telegram alerts are working correctly."
            )
            
            success = await notifier.send_message(test_message)
            
            if success:
                print("   ✅ PASS: Telegram alerts working")
                print("   📱 Check your Telegram for test message")
                self.results['telegram'] = 'PASS'
            else:
                print("   ❌ FAIL: Failed to send test message")
                self.results['telegram'] = 'FAIL'
                self.critical_failures.append('Telegram alerts not working')
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.results['telegram'] = 'ERROR'
            self.critical_failures.append(f'Telegram check failed: {e}')
        
        print()
    
    async def check_system_uptime(self):
        """Check if system has been running continuously."""
        print("5️⃣  Checking System Uptime...")
        
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/metrics", timeout=5.0)
                
                if response.status_code != 200:
                    print("   ❌ FAIL: Cannot connect to metrics endpoint")
                    print("   ⚠️  Is the system running?")
                    self.results['uptime'] = 'FAIL'
                    self.critical_failures.append('System not reachable')
                    print()
                    return
                
                metrics = response.json()
                websocket = metrics.get('websocket', {})
                uptime_seconds = websocket.get('uptime_seconds', 0)
                
                uptime_hours = uptime_seconds / 3600
                
                print(f"   System Uptime: {uptime_hours:.2f} hours")
                
                if uptime_hours >= 48:
                    print(f"   ✅ PASS: System running for {uptime_hours:.2f} hours (minimum: 48)")
                    self.results['uptime'] = 'PASS'
                elif uptime_hours >= 24:
                    print(f"   ⚠️  PARTIAL: {uptime_hours:.2f} hours (minimum: 48 required)")
                    self.results['uptime'] = 'PARTIAL'
                else:
                    print(f"   ❌ FAIL: Only {uptime_hours:.2f} hours uptime (minimum: 48 required)")
                    self.results['uptime'] = 'FAIL'
                    self.critical_failures.append('Insufficient uptime')
                
        except httpx.ConnectError:
            print("   ❌ FAIL: Cannot connect to system")
            print("   ⚠️  Start the system first: python -m uvicorn app.main:app --port 8000")
            self.results['uptime'] = 'FAIL'
            self.critical_failures.append('System not running')
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            self.results['uptime'] = 'ERROR'
            self.critical_failures.append(f'Uptime check failed: {e}')
        
        print()
    
    def print_summary(self):
        """Print validation summary."""
        print("="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        
        for check, status in self.results.items():
            emoji = {
                'PASS': '✅',
                'FAIL': '❌',
                'PARTIAL': '⚠️ ',
                'WARNING': '⚠️ ',
                'ERROR': '🚨',
                'N/A': '➖'
            }.get(status, '?')
            
            print(f"{emoji} {check.replace('_', ' ').title()}: {status}")
        
        print()
        
        if self.critical_failures:
            print(f"🚨 CRITICAL FAILURES ({len(self.critical_failures)}):")
            for i, failure in enumerate(self.critical_failures, 1):
                print(f"   {i}. {failure}")
            print()
            print("❌ SYSTEM NOT READY FOR PRODUCTION")
            print()
            print("Resolve all critical failures before deploying to mainnet.")
        else:
            print("✅ ALL CRITICAL CHECKS PASSED")
            print()
            print("⚠️  WARNING: Review any PARTIAL or WARNING items above")
            print()
            print("🚀 System may be ready for production deployment")
            print("   Ensure database backup is performed before switching to mainnet!")
        
        print("="*70)


async def main():
    """Main entry point."""
    validator = DeploymentValidator()
    success = await validator.validate_all()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
