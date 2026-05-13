#!/usr/bin/env python3
"""
Bybit Demo - Close Manual Position and Start New Bot Cycle.

This script handles the scenario where a position was opened manually
on Bybit Demo via the web interface (not through the bot's paper trading).

Steps:
1. Close the manual XAUUSDT position via Bybit API
2. Record the closure in database with P&L details
3. Send Telegram closure report
4. Initiate new trading cycle with Gold Bot V2 Elite parameters
5. Execute and report new trade

Usage:
    python scripts/close_manual_position_and_restart.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime
from pybit.unified_trading import HTTP
from sqlalchemy import select

from app.config import settings
from app.database.connection import async_session_maker
from app.database.models import PaperTrades
from app.notifications.notifier import TelegramNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BybitDemoManualCleanup:
    """Handles manual position closure and new cycle initiation."""
    
    def __init__(self):
        self.api_key = settings.BYBIT_DEMO_API_KEY
        self.api_secret = settings.BYBIT_DEMO_API_SECRET
        self.notifier = TelegramNotifier()
        
        # Initialize Bybit Demo API client
        # Using correct configuration: testnet=False, demo=True
        self.session = HTTP(
            testnet=False,
            demo=True,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
    async def step1_close_manual_position(self):
        """Step 1: Close the manual XAUUSDT position via API."""
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Closing Manual XAUUSDT Position")
        logger.info("="*80)
        
        try:
            # Get current position details
            positions_response = self.session.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if positions_response.get('retCode') != 0:
                logger.error(f"❌ Failed to fetch positions: {positions_response.get('retMsg')}")
                return None
            
            positions = positions_response['result']['list']
            xau_position = None
            
            for pos in positions:
                if pos['symbol'] == 'XAUUSDT' and float(pos.get('size', 0)) > 0:
                    xau_position = pos
                    break
            
            if not xau_position:
                logger.info("✅ No open XAUUSDT position found (already closed)")
                return None
            
            # Extract position details
            side = xau_position['side']
            size = float(xau_position['size'])
            entry_price = float(xau_position['avgPrice'])
            mark_price = float(xau_position['markPrice'])
            unrealized_pnl = float(xau_position.get('unrealisedPnl', 0))
            leverage = xau_position.get('leverage', 'N/A')
            
            logger.info(f"📊 Found manual position:")
            logger.info(f"   Side: {side}")
            logger.info(f"   Size: {size} XAU")
            logger.info(f"   Entry: ${entry_price:,.2f}")
            logger.info(f"   Mark: ${mark_price:,.2f}")
            logger.info(f"   Unrealized P&L: ${unrealized_pnl:+,.2f}")
            logger.info(f"   Leverage: {leverage}x")
            
            # Close the position with a market order
            # If side is Buy (Long), we need to Sell to close
            # If side is Sell (Short), we need to Buy to close
            close_side = "Sell" if side == "Buy" else "Buy"
            
            logger.info(f"\n🔄 Closing position with market {close_side} order...")
            
            close_response = self.session.place_order(
                category="linear",
                symbol="XAUUSDT",
                side=close_side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True  # Important: only reduce existing position
            )
            
            if close_response.get('retCode') == 0:
                result = close_response['result']
                order_id = result.get('orderId', 'N/A')
                
                logger.info(f"✅ Position closed successfully!")
                logger.info(f"   Order ID: {order_id}")
                
                # Get actual exit price from order result
                exit_price = mark_price  # Use mark price as approximation
                
                return {
                    'symbol': 'XAUUSDT',
                    'side': side,
                    'size': size,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'close_side': close_side,
                    'pnl': unrealized_pnl,
                    'leverage': leverage,
                    'order_id': order_id,
                    'closed_at': datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"❌ Failed to close position: {close_response.get('retMsg')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def step2_record_in_database(self, trade_info):
        """Step 2: Record the manual trade closure in database."""
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Recording Trade in Database")
        logger.info("="*80)
        
        if not trade_info:
            logger.info("ℹ️  No trade info to record")
            return False
        
        try:
            async with async_session_maker() as db:
                # Create a PaperTrades record for this manual trade
                # Note: PaperTrades model has these fields:
                # id, ts_open, ts_close, user_id, exchange, symbol, side, leverage, 
                # qty, entry_price, exit_price, stop_loss, take_profit, profit, 
                # profit_pct, status, notes, execution_mode
                
                trade_record = PaperTrades(
                    user_id="default_user",
                    exchange="bybit",
                    symbol=f"{trade_info['symbol']}/USDT:USDT",
                    side=trade_info['side'].upper(),
                    entry_price=trade_info['entry_price'],
                    exit_price=trade_info['exit_price'],
                    qty=trade_info['size'],
                    leverage=float(trade_info['leverage']) if trade_info['leverage'] != 'N/A' else 10.0,
                    status="closed",
                    profit=trade_info['pnl'],
                    profit_pct=(trade_info['pnl'] / (trade_info['entry_price'] * trade_info['size'])) * 100 if trade_info['entry_price'] > 0 else 0,
                    ts_open=datetime.utcnow().isoformat(),
                    ts_close=trade_info['closed_at'],
                    notes=f"Manual position closed via cleanup script. Order ID: {trade_info['order_id']}"
                )
                
                db.add(trade_record)
                await db.commit()
                
                logger.info(f"✅ Trade recorded in database")
                logger.info(f"   Trade ID: {trade_record.id}")
                logger.info(f"   P&L: ${trade_info['pnl']:+,.2f}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to record trade: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def step3_send_closure_report(self, trade_info):
        """Step 3: Send Telegram closure report."""
        logger.info("\n" + "="*80)
        logger.info("STEP 3: Sending Closure Report via Telegram")
        logger.info("="*80)
        
        if not trade_info:
            logger.info("ℹ️  No trade info to report")
            return
        
        try:
            emoji = "✅" if trade_info['pnl'] >= 0 else "🔴"
            
            message = (
                f"{emoji} <b>Manual Position Closed</b>\n\n"
                f"<b>Symbol:</b> {trade_info['symbol']}\n"
                f"<b>Side:</b> {trade_info['side']} (Long)\n"
                f"<b>Size:</b> {trade_info['size']} XAU\n"
                f"<b>Leverage:</b> {trade_info['leverage']}x\n\n"
                f"<b>Entry Price:</b> ${trade_info['entry_price']:,.2f}\n"
                f"<b>Exit Price:</b> ${trade_info['exit_price']:,.2f}\n\n"
                f"<b>P&L:</b> ${trade_info['pnl']:+,.2f}\n"
                f"<b>Status:</b> {'Profit' if trade_info['pnl'] >= 0 else 'Loss'}\n\n"
                f"<b>Closed At:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"<i>Closed by automated cleanup script</i>"
            )
            
            success = await self.notifier.send_message(message)
            
            if success:
                logger.info("✅ Closure report sent to Telegram")
            else:
                logger.warning("⚠️  Failed to send closure report")
                
        except Exception as e:
            logger.error(f"❌ Error sending closure report: {e}")
    
    async def step4_initiate_new_cycle(self):
        """Step 4: Initiate new trading cycle with Gold Bot V2 Elite parameters."""
        logger.info("\n" + "="*80)
        logger.info("STEP 4: Initiating New Trading Cycle")
        logger.info("="*80)
        
        try:
            from app.infra.exchange_manager import UnifiedExchangeManager
            from app.services.live_trading_service import LiveTradingService
            
            # Initialize trading service with Bybit Demo
            trading_service = LiveTradingService(
                exchange_name="bybit",
                use_testnet=False,
                use_openrouter=True
            )
            
            symbol = settings.GOLD_SYMBOL_BYBIT
            user_id = "default_user"
            
            logger.info(f"🚀 Starting new trading cycle for {symbol}")
            logger.info(f"   Using Gold Bot V2 Elite parameters:")
            logger.info(f"   - Risk per trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
            logger.info(f"   - Max leverage: {settings.GOLD_MAX_LEVERAGE}x")
            logger.info(f"   - Min confidence: {settings.GOLD_MIN_CONFIDENCE:.0%}")
            
            async with async_session_maker() as db_session:
                result = await trading_service.execute_trading_cycle(
                    symbol=symbol,
                    user_id=user_id,
                    db_session=db_session
                )
            
            await trading_service.close()
            
            if result['status'] == 'success':
                logger.info("✅ New trading cycle completed successfully")
                
                execution = result.get('execution', {})
                proposal = result.get('ai_result', {}).get('trade_proposal', {})
                
                return {
                    'status': 'success',
                    'execution': execution,
                    'proposal': proposal,
                    'cycle_time_ms': result.get('cycle_time_ms', 0)
                }
            elif result['status'] == 'rejected':
                reason = result.get('rejection_reason', 'Unknown')
                quality_score = result.get('quality_score', 0)
                
                logger.info("⚠️  Trade rejected by quality filter")
                logger.info(f"   Quality Score: {quality_score}/100")
                logger.info(f"   Reason: {reason}")
                
                return {
                    'status': 'rejected',
                    'rejection_reason': reason,
                    'quality_score': quality_score,
                    'cycle_time_ms': result.get('cycle_time_ms', 0)
                }
            else:
                logger.error(f"❌ Trading cycle failed: {result.get('error')}")
                return {
                    'status': 'failed',
                    'error': result.get('error')
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to initiate new cycle: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def step5_send_new_trade_report(self, new_trade_info):
        """Step 5: Send Telegram report for new trade."""
        logger.info("\n" + "="*80)
        logger.info("STEP 5: Sending New Trade Report")
        logger.info("="*80)
        
        if not new_trade_info:
            logger.info("ℹ️  No trade info to report")
            return
        
        try:
            status = new_trade_info.get('status')
            
            if status == 'rejected':
                reason = new_trade_info.get('rejection_reason', 'Unknown')
                quality_score = new_trade_info.get('quality_score', 0)
                
                message = (
                    f"⚠️ <b>Trade Rejected by Quality Filter</b>\n\n"
                    f"<b>Symbol:</b> {settings.GOLD_SYMBOL_BYBIT}\n"
                    f"<b>Quality Score:</b> {quality_score}/100\n"
                    f"<b>Reason:</b> {reason}\n\n"
                    f"<i>System protecting capital from low-quality trade</i>\n"
                    f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
                )
                
                await self.notifier.send_message(message)
                logger.info("✅ Rejection report sent to Telegram")
                return
            
            elif status == 'failed':
                error_msg = new_trade_info.get('error', 'Unknown error')
                
                message = (
                    f"🚨 <b>Trading Cycle Failed</b>\n\n"
                    f"<b>Error:</b> {error_msg}\n\n"
                    f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
                )
                
                await self.notifier.send_message(message)
                logger.warning("⚠️  Failure notification sent")
                return
            
            # Success - new trade executed or proposed
            execution = new_trade_info.get('execution', {})
            proposal = new_trade_info.get('proposal', {})
            execution_status = execution.get('status', 'unknown')
            
            emoji_map = {
                'executed': '✅',
                'proposal_only': '⏸️',
                'awaiting_confirmation': '⏸️',
                'rejected': '❌'
            }
            emoji = emoji_map.get(execution_status, 'ℹ️')
            
            message = (
                f"{emoji} <b>New Trade {'Executed' if execution_status == 'executed' else 'Generated'}</b>\n\n"
                f"<b>Symbol:</b> {settings.GOLD_SYMBOL_BYBIT}\n"
                f"<b>Strategy:</b> {proposal.get('strategy_name', 'N/A')}\n"
                f"<b>Confidence:</b> {proposal.get('confidence', 0):.2%}\n\n"
                f"<b>Side:</b> {proposal.get('side', 'N/A')}\n"
                f"<b>Entry:</b> ${proposal.get('entry_price', 0):,.2f}\n"
                f"<b>Stop Loss:</b> ${proposal.get('stop_loss', 0):,.2f}\n"
                f"<b>Take Profit:</b> ${proposal.get('take_profit', 0):,.2f}\n"
                f"<b>Leverage:</b> {proposal.get('leverage', 1)}x\n"
                f"<b>Risk:</b> {settings.GOLD_RISK_PER_TRADE*100:.1f}%\n\n"
            )
            
            if execution_status == 'executed':
                message += (
                    f"<b>Trade ID:</b> #{execution.get('trade_id', 'N/A')}\n"
                    f"<b>Order ID:</b> {execution.get('order_id', 'N/A')}\n"
                    f"<b>Status:</b> EXECUTED ✅\n\n"
                )
            else:
                message += f"<b>Status:</b> {execution_status.upper()}\n\n"
            
            message += (
                f"<b>Cycle Time:</b> {new_trade_info.get('cycle_time_ms', 0):.0f}ms\n"
                f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )
            
            success = await self.notifier.send_message(message)
            
            if success:
                logger.info("✅ New trade report sent to Telegram")
            else:
                logger.warning("⚠️  Failed to send new trade report")
                
        except Exception as e:
            logger.error(f"❌ Error sending new trade report: {e}")
    
    async def run_full_procedure(self):
        """Execute the complete cleanup and restart procedure."""
        logger.info("\n" + "#"*80)
        logger.info("# BYBIT DEMO - MANUAL POSITION CLEANUP & NEW CYCLE")
        logger.info("#"*80)
        logger.info(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"Exchange: Bybit Demo")
        logger.info(f"Symbol: {settings.GOLD_SYMBOL_BYBIT}")
        
        try:
            # Step 1: Close manual position
            trade_info = await self.step1_close_manual_position()
            
            # Step 2: Record in database
            if trade_info:
                await self.step2_record_in_database(trade_info)
            
            # Step 3: Send closure report
            if trade_info:
                await self.step3_send_closure_report(trade_info)
            
            # Step 4: Initiate new cycle
            new_trade_info = await self.step4_initiate_new_cycle()
            
            # Step 5: Send new trade report
            if new_trade_info:
                await self.step5_send_new_trade_report(new_trade_info)
            
            # Summary
            logger.info("\n" + "="*80)
            logger.info("PROCEDURE COMPLETE")
            logger.info("="*80)
            logger.info(f"✅ Manual position closed: {'Yes' if trade_info else 'No (none found)'}")
            logger.info(f"✅ New cycle status: {new_trade_info.get('status', 'unknown') if new_trade_info else 'N/A'}")
            logger.info(f"✅ Completed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Procedure failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            logger.info("\n✅ Cleanup procedure finished")


async def main():
    """Main entry point."""
    manager = BybitDemoManualCleanup()
    success = await manager.run_full_procedure()
    
    if success:
        logger.info("\n🎉 Cleanup and restart procedure completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n💥 Cleanup and restart procedure failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
