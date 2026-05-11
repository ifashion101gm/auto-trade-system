#!/usr/bin/env python3
"""
Close Open MEXC Position and Start Fresh Validation Cycle.

This script:
1. Closes the actual GOLD(XAUT)USDT position on MEXC Testnet
2. Records the closure in the database
3. Sends Telegram notification
4. Starts a new paper trading validation cycle

Usage:
    python scripts/close_mexc_position_and_restart.py
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.config import settings
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.infra.telegram_notifier import TelegramNotifier
from app.infra.mexc_client import MEXCClient
from app.services.live_trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)


class MexcPositionCloser:
    """Manages closing MEXC positions and restarting validation cycle."""
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.user_id = "default_user"
        
    async def close_mexc_position(self) -> Dict[str, Any]:
        """
        Close the open GOLD position on MEXC.
        
        Returns:
            Closure result details
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Closing Open MEXC GOLD Position")
        logger.info("="*80)
        
        mexc_client = None
        try:
            # Initialize MEXC client
            from app.config import settings
            mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures'
            )
            
            # Fetch open positions
            positions = await mexc_client.fetch_open_positions()
            
            gold_position = None
            for pos in positions:
                symbol = pos.get('symbol', '')
                if any(g in symbol.upper() for g in ['GOLD', 'XAUT', 'PAXG']):
                    gold_position = pos
                    break
            
            if not gold_position:
                logger.info("️  No open GOLD position found on MEXC")
                return {
                    'status': 'no_position',
                    'message': 'No open GOLD position found'
                }
            
            logger.info(f"📊 Found open position:")
            logger.info(f"   Symbol: {gold_position['symbol']}")
            logger.info(f"   Side: {gold_position['side']}")
            logger.info(f"   Quantity: {gold_position['contracts']}")
            logger.info(f"   Entry Price: ${gold_position['entryPrice']}")
            logger.info(f"   Mark Price: ${gold_position['markPrice']}")
            logger.info(f"   Leverage: {gold_position.get('leverage', 1)}x")
            
            # Close position using MEXC client's close_position method
            logger.info(f"\n🔄 Closing position with market order...")
            
            close_result = await mexc_client.close_position(gold_position['symbol'])
            
            logger.info(f"✅ Position closed successfully")
            logger.info(f"   Order ID: {close_result.get('order_id', 'N/A')}")
            logger.info(f"   Filled at: ${close_result.get('price', 0):,.2f}")
            
            # Calculate P&L
            entry_price = gold_position['entryPrice']
            exit_price = close_result.get('price', gold_position['markPrice'])
            contracts = gold_position['contracts']
            leverage = gold_position.get('leverage', 1)
            
            if gold_position['side'] == 'long':
                profit = (exit_price - entry_price) * contracts
            else:
                profit = (entry_price - exit_price) * contracts
            
            profit_pct = (profit / (entry_price * contracts)) * 100 if entry_price > 0 else 0
            
            # Record closure in database
            trade_record = PaperTrades(
                ts_open=datetime.utcnow().isoformat(),
                ts_close=datetime.utcnow().isoformat(),
                user_id=self.user_id,
                exchange='mexc',
                symbol=gold_position['symbol'],
                side=gold_position['side'].upper(),
                leverage=leverage,
                qty=contracts,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=None,
                take_profit=None,
                profit=profit,
                profit_pct=profit_pct,
                status='closed',
                notes=json.dumps({
                    'closed_by': 'manual_cleanup_script',
                    'order_id': close_result.get('order_id', 'N/A'),
                    'original_entry': entry_price,
                    'exit_price': exit_price
                }),
                execution_mode='manual_close'
            )
            
            async with async_session_maker() as db_session:
                db_session.add(trade_record)
                await db_session.commit()
            
            logger.info(f"\n💰 P&L: ${profit:+.2f} ({profit_pct:+.2f}%)")
            logger.info(f"   Trade recorded in database (ID: {trade_record.id})")
            
            return {
                'status': 'closed',
                'symbol': gold_position['symbol'],
                'side': gold_position['side'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': contracts,
                'leverage': leverage,
                'profit': profit,
                'profit_pct': profit_pct,
                'order_id': close_result.get('order_id', 'N/A'),
                'trade_id': trade_record.id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            logger.exception("Traceback:")
            return {
                'status': 'failed',
                'error': str(e)
            }
        finally:
            if mexc_client:
                await mexc_client.close()
    
    async def send_closure_report(self, closure_result: Dict[str, Any]):
        """Send Telegram notification for position closure."""
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Sending Closure Report")
        logger.info("="*80)
        
        if closure_result['status'] == 'no_position':
            logger.info("ℹ️  No position to report")
            return
        
        if closure_result['status'] == 'failed':
            message = (
                f" <b>Position Closure Failed</b>\n\n"
                f"<b>Error:</b> {closure_result.get('error')}\n\n"
                f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )
            await self.notifier.send_message(message)
            return
        
        emoji = "✅" if closure_result['profit'] >= 0 else "❌"
        
        message = (
            f"{emoji} <b>MEXC Position Closed</b>\n\n"
            f"<b>Symbol:</b> {closure_result['symbol']}\n"
            f"<b>Side:</b> {closure_result['side'].upper()}\n"
            f"<b>Leverage:</b> {closure_result['leverage']}x\n\n"
            f"<b>Entry Price:</b> ${closure_result['entry_price']:,.2f}\n"
            f"<b>Exit Price:</b> ${closure_result['exit_price']:,.2f}\n"
            f"<b>Quantity:</b> {closure_result['quantity']}\n\n"
            f"<b>P&L:</b> ${closure_result['profit']:+.2f} ({closure_result['profit_pct']:+.2f}%)\n"
            f"<b>Order ID:</b> {closure_result['order_id']}\n"
            f"<b>Trade ID:</b> #{closure_result['trade_id']}\n\n"
            f"<i>Closed by cleanup script</i>\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        )
        
        success = await self.notifier.send_message(message)
        if success:
            logger.info("✅ Closure report sent to Telegram")
        else:
            logger.warning("⚠️  Failed to send closure report")
    
    async def start_new_cycle(self) -> Dict[str, Any]:
        """Start a new paper trading validation cycle."""
        logger.info("\n" + "="*80)
        logger.info("STEP 3: Starting New Validation Cycle")
        logger.info("="*80)
        
        trading_service = None
        try:
            # Initialize trading service
            trading_service = LiveTradingService(
                exchange_name="mexc",
                use_testnet=False,
                use_openrouter=True
            )
            
            symbol = settings.GOLD_SYMBOL_MEXC
            logger.info(f"🚀 Starting cycle for {symbol}...")
            
            async with async_session_maker() as db_session:
                result = await trading_service.execute_trading_cycle(
                    symbol=symbol,
                    user_id=self.user_id,
                    db_session=db_session
                )
            
            if result['status'] == 'success':
                logger.info("✅ New cycle completed successfully")
                execution = result.get('execution', {})
                proposal = result.get('ai_result', {}).get('trade_proposal', {})
                
                return {
                    'status': 'success',
                    'regime': result.get('ai_result', {}).get('regime'),
                    'strategy': proposal.get('strategy_name'),
                    'confidence': proposal.get('confidence'),
                    'side': proposal.get('side'),
                    'entry_price': proposal.get('entry_price'),
                    'execution_status': execution.get('status'),
                    'trade_id': execution.get('trade_id'),
                    'cycle_time_ms': result.get('cycle_time_ms', 0)
                }
            else:
                logger.error(f"❌ Cycle failed: {result.get('error')}")
                return {'status': 'failed', 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"❌ Failed to start new cycle: {e}")
            return {'status': 'failed', 'error': str(e)}
        finally:
            if trading_service:
                await trading_service.close()
    
    async def send_new_trade_report(self, new_trade: Dict[str, Any]):
        """Send Telegram report for new trade."""
        logger.info("\n" + "="*80)
        logger.info("STEP 4: Sending New Trade Report")
        logger.info("="*80)
        
        if new_trade.get('status') != 'success':
            message = (
                f"🚨 <b>New Validation Cycle Failed</b>\n\n"
                f"<b>Error:</b> {new_trade.get('error')}\n\n"
                f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )
            await self.notifier.send_message(message)
            return
        
        execution_status = new_trade.get('execution_status', 'unknown')
        emoji = "✅" if execution_status == 'executed' else "⏸️"
        title = "New Trade Executed" if execution_status == 'executed' else "Trade Proposal"
        
        message = (
            f"{emoji} <b>{title}</b>\n\n"
            f"<b>Regime:</b> {new_trade.get('regime', 'N/A')}\n"
            f"<b>Strategy:</b> {new_trade.get('strategy', 'N/A')}\n"
            f"<b>Confidence:</b> {new_trade.get('confidence', 0):.2%}\n\n"
            f"<b>Side:</b> {new_trade.get('side', 'N/A')}\n"
            f"<b>Entry Price:</b> ${new_trade.get('entry_price', 0):,.2f}\n\n"
            f"<b>Trade ID:</b> #{new_trade.get('trade_id', 'N/A')}\n"
            f"<b>Status:</b> {execution_status.upper()}\n\n"
            f"<b>Cycle Time:</b> {new_trade.get('cycle_time_ms', 0):.0f}ms\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        )
        
        success = await self.notifier.send_message(message)
        if success:
            logger.info("✅ New trade report sent to Telegram")
    
    async def run(self):
        """Execute full procedure."""
        logger.info("\n" + "#"*80)
        logger.info("# CLOSE MEXC POSITION & START FRESH VALIDATION CYCLE")
        logger.info("#"*80)
        logger.info(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        try:
            # Step 1: Close MEXC position
            closure = await self.close_mexc_position()
            
            # Step 2: Send closure report
            await self.send_closure_report(closure)
            
            # Step 3: Start new cycle
            new_trade = await self.start_new_cycle()
            
            # Step 4: Send new trade report
            await self.send_new_trade_report(new_trade)
            
            # Summary
            logger.info("\n" + "="*80)
            logger.info("PROCEDURE COMPLETE")
            logger.info("="*80)
            logger.info(f"✅ Position closure: {closure['status']}")
            logger.info(f"✅ New trade: {new_trade['status']}")
            logger.info(f"✅ Finished: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Procedure failed: {e}")
            try:
                await self.notifier.send_message(
                    f" <b>Procedure Failed</b>\n\nError: {str(e)}"
                )
            except:
                pass
            return False


async def main():
    """Main entry point."""
    manager = MexcPositionCloser()
    success = await manager.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
