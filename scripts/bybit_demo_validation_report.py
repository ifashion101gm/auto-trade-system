#!/usr/bin/env python3
"""
Bybit Demo Validation Report Generator.
Queries database and live API, then sends structured report to Telegram.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime
from app.database.connection import async_session_maker
from app.database.models import PaperTrades
from app.notifications.notifier import TelegramNotifier
from app.config import settings
from sqlalchemy import select, func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BybitDemoValidator:
    """Validates Bybit Demo environment and sends report to Telegram."""
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.db_stats = {}
        self.api_stats = {}
        self.config_checks = {}
    
    async def query_database(self):
        """Query PostgreSQL database for PaperTrades statistics."""
        logger.info("📊 Querying database for Bybit demo trades...")
        
        async with async_session_maker() as db:
            # Total trades
            result = await db.execute(
                select(func.count(PaperTrades.id))
                .where(PaperTrades.exchange == 'bybit')
            )
            total_trades = result.scalar() or 0
            
            # Closed trades
            result = await db.execute(
                select(func.count(PaperTrades.id))
                .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
            )
            closed_trades = result.scalar() or 0
            
            # Open trades
            result = await db.execute(
                select(func.count(PaperTrades.id))
                .where(PaperTrades.exchange == 'bybit', PaperTrades.status.in_(['open', 'OPEN']))
            )
            open_trades = result.scalar() or 0
            
            # All closed trades for performance metrics
            if closed_trades > 0:
                result = await db.execute(
                    select(PaperTrades)
                    .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                    .order_by(PaperTrades.ts_close)
                )
                all_closed = result.scalars().all()
                
                # Calculate metrics
                initial_balance = 100.0
                current_balance = initial_balance
                wins = 0
                losses = 0
                gross_profit = 0.0
                gross_loss = 0.0
                peak_balance = initial_balance
                max_drawdown = 0.0
                
                for trade in all_closed:
                    if trade.profit:
                        current_balance += trade.profit
                        
                        if trade.profit > 0:
                            wins += 1
                            gross_profit += trade.profit
                        else:
                            losses += 1
                            gross_loss += abs(trade.profit)
                        
                        # Track drawdown
                        if current_balance > peak_balance:
                            peak_balance = current_balance
                        
                        drawdown = (peak_balance - current_balance) / peak_balance * 100
                        if drawdown > max_drawdown:
                            max_drawdown = drawdown
                
                cumulative_profit = current_balance - initial_balance
                win_rate = (wins / len(all_closed)) * 100 if all_closed else 0
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                self.db_stats = {
                    'total_trades': total_trades,
                    'closed_trades': closed_trades,
                    'open_trades': open_trades,
                    'initial_balance': initial_balance,
                    'current_balance': current_balance,
                    'cumulative_profit': cumulative_profit,
                    'progress_pct': (cumulative_profit / 100) * 100,
                    'wins': wins,
                    'losses': losses,
                    'win_rate': win_rate,
                    'gross_profit': gross_profit,
                    'gross_loss': gross_loss,
                    'profit_factor': profit_factor,
                    'max_drawdown': max_drawdown,
                    'peak_balance': peak_balance
                }
                
                logger.info(f"✅ Database query complete: {total_trades} trades, ${cumulative_profit:.2f} profit")
            else:
                self.db_stats = {
                    'total_trades': total_trades,
                    'closed_trades': 0,
                    'open_trades': open_trades,
                    'initial_balance': 100.0,
                    'current_balance': 100.0,
                    'cumulative_profit': 0.0,
                    'progress_pct': 0.0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0.0,
                    'gross_profit': 0.0,
                    'gross_loss': 0.0,
                    'profit_factor': 0.0,
                    'max_drawdown': 0.0,
                    'peak_balance': 100.0
                }
                
                logger.info(f"⚠️ No closed trades yet. Starting balance: $100.00")
    
    async def query_bybit_api(self):
        """Query Bybit Demo API for account balance and open positions."""
        logger.info("🔗 Querying Bybit Demo API...")
        
        try:
            # Check if demo keys are configured
            if not settings.BYBIT_DEMO_API_KEY or not settings.BYBIT_DEMO_API_SECRET:
                logger.warning("⚠️ Bybit Demo API keys not configured")
                self.api_stats = {
                    'success': False,
                    'error': 'API keys not configured'
                }
                return
            
            # Import pybit for Bybit API
            try:
                from pybit.unified_trading import HTTP
            except ImportError:
                logger.warning("⚠️ pybit not installed, skipping API query")
                self.api_stats = {'success': False, 'error': 'pybit not installed'}
                return
            
            # Initialize client for demo trading
            # Bybit demo uses testnet=True with demo API keys
            session = HTTP(
                testnet=True,
                api_key=settings.BYBIT_DEMO_API_KEY,
                api_secret=settings.BYBIT_DEMO_API_SECRET
            )
            
            # Get wallet balance
            balance_response = session.get_wallet_balance(accountType="UNIFIED")
            
            if balance_response.get('retCode') == 0:
                coin_list = balance_response['result']['list'][0]['coin']
                usdt_coin = next((c for c in coin_list if c['coin'] == 'USDT'), None)
                
                if usdt_coin:
                    wallet_balance = float(usdt_coin['walletBalance'])
                    available_balance = float(usdt_coin['availableToWithdraw'])
                    
                    self.api_stats = {
                        'success': True,
                        'wallet_balance': wallet_balance,
                        'available_balance': available_balance,
                        'demo_mode': settings.BYBIT_USE_DEMO_DOMAIN
                    }
                    
                    logger.info(f"✅ API query complete: Balance ${wallet_balance:,.2f}")
                else:
                    self.api_stats = {'success': False, 'error': 'USDT not found in wallet'}
            else:
                self.api_stats = {
                    'success': False,
                    'error': f"API error: {balance_response.get('retMsg', 'Unknown')}"
                }
            
            # Get open positions
            try:
                positions_response = session.get_positions(
                    category="linear",
                    settleCoin="USDT"
                )
                
                if positions_response.get('retCode') == 0:
                    positions_list = positions_response['result']['list']
                    open_positions = []
                    
                    for pos in positions_list:
                        if float(pos.get('size', 0)) > 0:
                            open_positions.append({
                                'symbol': pos['symbol'],
                                'side': pos['side'],
                                'size': float(pos['size']),
                                'entry_price': float(pos['avgPrice']),
                                'mark_price': float(pos['markPrice']),
                                'unrealized_pnl': float(pos['unrealisedPnl']),
                                'leverage': pos['leverage'],
                                'liquidation_price': pos.get('liqPrice', 'N/A')
                            })
                    
                    self.api_stats['open_positions'] = open_positions
                    logger.info(f"📊 Found {len(open_positions)} open position(s)")
            
            except Exception as pos_err:
                logger.warning(f"️ Could not fetch positions: {pos_err}")
                self.api_stats['open_positions'] = []
        
        except Exception as e:
            logger.error(f"❌ Bybit API query failed: {e}")
            self.api_stats = {
                'success': False,
                'error': str(e)
            }
    
    def check_configuration(self):
        """Validate current .env configuration."""
        logger.info("⚙️ Checking configuration...")
        
        self.config_checks = {
            'bybit_use_demo_domain': settings.BYBIT_USE_DEMO_DOMAIN,
            'active_exchange': settings.ACTIVE_EXCHANGE,
            'execution_mode': settings.EXECUTION_MODE,
            'gold_risk_per_trade': settings.GOLD_RISK_PER_TRADE,
            'gold_max_leverage': settings.GOLD_MAX_LEVERAGE,
            'gold_min_confidence': settings.GOLD_MIN_CONFIDENCE,
            'warnings': []
        }
        
        # Validate settings
        if not settings.BYBIT_USE_DEMO_DOMAIN:
            self.config_checks['warnings'].append("❌ BYBIT_USE_DEMO_DOMAIN=false (should be true for demo)")
        
        if settings.ACTIVE_EXCHANGE != 'bybit':
            self.config_checks['warnings'].append(
                f"❌ ACTIVE_EXCHANGE='{settings.ACTIVE_EXCHANGE}' (should be 'bybit')"
            )
        
        if settings.EXECUTION_MODE != 'semi-auto':
            self.config_checks['warnings'].append(
                f"⚠️ EXECUTION_MODE='{settings.EXECUTION_MODE}' (recommended: 'semi-auto')"
            )
        
        if settings.GOLD_RISK_PER_TRADE > 0.005:
            self.config_checks['warnings'].append(
                f"⚠️ GOLD_RISK_PER_TRADE={settings.GOLD_RISK_PER_TRADE*100:.1f}% (elite target: 0.5%)"
            )
        
        if settings.GOLD_MAX_LEVERAGE > 3:
            self.config_checks['warnings'].append(
                f"⚠️ GOLD_MAX_LEVERAGE={settings.GOLD_MAX_LEVERAGE}x (elite target: 3x)"
            )
        
        if not self.config_checks['warnings']:
            self.config_checks['warnings'].append("✅ All configuration checks passed")
        
        logger.info(f"✅ Configuration check complete: {len(self.config_checks['warnings'])} items")
    
    def format_telegram_report(self) -> str:
        """Format comprehensive validation report for Telegram."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Header
        report = f""" <b>Bybit Demo Validation Report</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Timestamp: {now}

 <b>Financial Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Financials from API (more accurate)
        if self.api_stats.get('success'):
            wallet_balance = self.api_stats['wallet_balance']
            available_balance = self.api_stats['available_balance']
            
            # Calculate net profit from starting balance ($100)
            starting_balance = 100.0
            net_profit = wallet_balance - starting_balance
            progress_pct = (net_profit / 100) * 100
            
            report += f"""Starting Balance: $100.00
Current Balance: ${wallet_balance:,.2f}
Net Profit: <b>${net_profit:+,.2f}</b>
Progress to $100 Goal: <b>{progress_pct:.1f}%</b>

"""
        else:
            # Fallback to database stats
            db = self.db_stats
            report += f"""Starting Balance: ${db['initial_balance']:.2f}
Current Balance: ${db['current_balance']:.2f} (from DB)
Net Profit: <b>${db['cumulative_profit']:+,.2f}</b>
Progress to $100 Goal: <b>{db['progress_pct']:.1f}%</b>

"""
        
        # Performance metrics
        db = self.db_stats
        report += f""" <b>Performance Metrics</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Trades: {db['total_trades']}
  • Closed: {db['closed_trades']}
  • Open: {db['open_trades']}
Win Rate: <b>{db['win_rate']:.1f}%</b> ({db['wins']}W / {db['losses']}L)
Profit Factor: <b>{db['profit_factor']:.2f}</b>
Max Drawdown: <b>{db['max_drawdown']:.2f}%</b>

"""
        
        # Open positions from API
        report += f"""📊 <b>Open Positions</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        open_positions = self.api_stats.get('open_positions', [])
        if open_positions:
            for i, pos in enumerate(open_positions, 1):
                pnl = pos['unrealized_pnl']
                pnl_emoji = "🟢" if pnl > 0 else "🔴"
                
                report += f"""
<b>Position #{i}:</b>
Symbol: {pos['symbol']}
Side: {pos['side'].upper()}
Size: {pos['size']}
Entry: ${pos['entry_price']:,.2f}
Mark: ${pos['mark_price']:,.2f}
P&L: {pnl_emoji} ${pnl:+,.2f}
Leverage: {pos['leverage']}x

"""
        else:
            report += """No Open Positions ✅

"""
        
        # Configuration check
        config = self.config_checks
        report += f"""️ <b>Configuration Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        for warning in config['warnings']:
            report += f"{warning}\n"
        
        # Progress indicator
        if self.api_stats.get('success'):
            net_profit = self.api_stats['wallet_balance'] - 100.0
            if net_profit >= 100:
                report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 <b>GOAL ACHIEVED!</b> Ready for live trading validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            elif net_profit >= 50:
                report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ <b>HALFWAY THERE!</b> Keep pushing toward $100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            else:
                remaining = 100 - net_profit
                report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>Need ${remaining:,.2f} more profit</b> to reach $100 goal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        return report
    
    async def send_report(self):
        """Send formatted report to Telegram."""
        logger.info("📱 Sending validation report to Telegram...")
        
        report = self.format_telegram_report()
        
        try:
            success = await self.notifier.send_message(report)
            
            if success:
                logger.info("✅ Validation report sent to Telegram successfully")
            else:
                logger.error("❌ Failed to send validation report to Telegram")
                
        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}")
            # Log report to file as backup
            with open('/tmp/bybit_validation_report.txt', 'w') as f:
                f.write(report)
            logger.info(f"📄 Report saved to /tmp/bybit_validation_report.txt")
    
    async def run_full_validation(self):
        """Execute complete validation workflow."""
        logger.info("="*80)
        logger.info("STARTING BYBIT DEMO VALIDATION")
        logger.info("="*80)
        
        # Step 1: Database query
        await self.query_database()
        
        # Step 2: API query
        await self.query_bybit_api()
        
        # Step 3: Configuration check
        self.check_configuration()
        
        # Step 4: Send Telegram report
        await self.send_report()
        
        logger.info("="*80)
        logger.info("VALIDATION COMPLETE")
        logger.info("="*80)


async def main():
    """Main entry point."""
    validator = BybitDemoValidator()
    await validator.run_full_validation()


if __name__ == "__main__":
    asyncio.run(main())
