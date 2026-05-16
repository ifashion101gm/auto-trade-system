#!/usr/bin/env python3
"""
Telegram Notification Monitor for Bybit Demo Paper Trading.
Displays recent notifications and their status.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.notifications.notifier import TelegramNotifier
from app.config import settings
from app.database.connection import async_session_maker
from sqlalchemy import select, func
from app.database.models import PaperTrades


async def monitor_telegram_notifications():
    """Monitor and display Telegram notification status."""
    
    print("\n" + "="*80)
    print("📱 TELEGRAM NOTIFICATION MONITOR")
    print("="*80)
    print(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*80)
    
    # Check Telegram configuration
    notifier = TelegramNotifier()
    
    print("\n🔧 Configuration Status:")
    print(f"  • Bot Token: {'✅ Configured' if settings.TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    print(f"  • Chat ID: {settings.TELEGRAM_CHAT_ID}")
    print(f"  • Notifier Enabled: {'✅ Yes' if notifier.enabled else '❌ No'}")
    
    if not notifier.enabled:
        print("\n⚠️  WARNING: Telegram notifications are DISABLED!")
        print("   Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    # Check database for recent activity
    print("\n" + "-"*80)
    print("📊 Recent Trading Activity (Last 24 Hours)")
    print("-"*80)
    
    async with async_session_maker() as db:
        # Get trades from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        result = await db.execute(
            select(func.count(PaperTrades.id)).where(
                PaperTrades.user_id == 'default_user',
                PaperTrades.exchange == 'bybit',
                PaperTrades.ts_open >= cutoff_time.isoformat()
            )
        )
        total_trades_24h = result.scalar() or 0
        
        result = await db.execute(
            select(func.count(PaperTrades.id)).where(
                PaperTrades.user_id == 'default_user',
                PaperTrades.exchange == 'bybit',
                PaperTrades.status == 'open'
            )
        )
        open_positions = result.scalar() or 0
        
        result = await db.execute(
            select(func.count(PaperTrades.id)).where(
                PaperTrades.user_id == 'default_user',
                PaperTrades.exchange == 'bybit',
                PaperTrades.status == 'closed',
                PaperTrades.ts_close >= cutoff_time.isoformat()
            )
        )
        closed_trades_24h = result.scalar() or 0
        
        print(f"  • Total Trades (24h): {total_trades_24h}")
        print(f"  • Open Positions: {open_positions}")
        print(f"  • Closed Trades (24h): {closed_trades_24h}")
    
    # Check logs for recent notifications
    print("\n" + "-"*80)
    print("📨 Recent Telegram Notifications (from logs)")
    print("-"*80)
    
    import subprocess
    try:
        # Get recent trade cycle attempts
        result = subprocess.run(
            ['grep', '-h', 'STEP 5: Sending New Trade Report', 
             '/home/admin/.openclaw/workspace/auto-trade-system/logs/trades_*.log'],
            capture_output=True, text=True
        )
        
        lines = result.stdout.strip().split('\n')
        recent_lines = lines[-10:] if len(lines) > 10 else lines
        
        if recent_lines and recent_lines[0]:
            print(f"\n  Last {len(recent_lines)} notification attempts:")
            for i, line in enumerate(recent_lines, 1):
                if line:
                    # Extract timestamp
                    parts = line.split('|')
                    if len(parts) >= 2:
                        timestamp = parts[0].strip().split(' ')[0] + ' ' + parts[0].strip().split(' ')[1]
                        print(f"    {i}. {timestamp} - Trade report sent")
        else:
            print("\n  ℹ️  No recent notification attempts found in logs")
            
    except Exception as e:
        print(f"\n  ⚠️  Could not read logs: {e}")
    
    # Check for rejection notifications
    print("\n" + "-"*80)
    print("❌ Recent Trade Rejections")
    print("-"*80)
    
    try:
        result = subprocess.run(
            ['grep', '-h', 'Trade rejected by risk engine', 
             '/home/admin/.openclaw/workspace/auto-trade-system/logs/trades_*.log'],
            capture_output=True, text=True
        )
        
        lines = result.stdout.strip().split('\n')
        recent_rejections = lines[-5:] if len(lines) > 5 else lines
        
        if recent_rejections and recent_rejections[0]:
            print(f"\n  Last {len(recent_rejections)} rejections:")
            for i, line in enumerate(recent_rejections, 1):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        timestamp = parts[0].strip().split(' ')[0] + ' ' + parts[0].strip().split(' ')[1]
                        print(f"    {i}. {timestamp} - Rejected by risk engine")
                        
                        # Get the reason from next line
                        if i < len(recent_rejections):
                            reason_line = recent_rejections[i] if i < len(recent_rejections) else ""
                            if 'Position size' in reason_line:
                                print(f"       Reason: Position size exceeded limit")
        else:
            print("\n  ✅ No recent rejections found")
            
    except Exception as e:
        print(f"\n  ⚠️  Could not read rejection logs: {e}")
    
    # Summary
    print("\n" + "="*80)
    print("📋 Summary & Recommendations")
    print("="*80)
    
    if total_trades_24h == 0:
        print("\n  ℹ️  No trades executed in the last 24 hours")
        print("  • This is normal if outside trading sessions")
        print("  • London Session: 07:50-10:30 UTC")
        print("  • New York Session: 13:20-16:30 UTC")
    elif open_positions == 0 and closed_trades_24h == 0:
        print("\n  ⚠️  All trades were rejected by risk engine")
        print("  • Issue: Position sizing too large for $100 demo balance")
        print("  • Action Required: Fix AI orchestrator position size calculation")
    else:
        print("\n  ✅ Trading activity detected")
        print(f"  • Monitor open positions: {open_positions}")
        print(f"  • Review closed trades: {closed_trades_24h}")
    
    print("\n" + "="*80)
    print("🔍 What to Check in Telegram:")
    print("="*80)
    print("\n  1. Trade Rejection Reports")
    print("     - Quality filter rejections")
    print("     - Risk engine rejections (position size)")
    print("\n  2. Successful Trade Executions")
    print("     - Entry notifications with trade details")
    print("     - Exit notifications with P&L")
    print("\n  3. System Alerts")
    print("     - WebSocket connection status")
    print("     - Circuit breaker activations")
    print("     - Reconciliation warnings")
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(monitor_telegram_notifications())
