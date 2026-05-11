#!/usr/bin/env python3
"""
Cleanup and Restart Procedure for MEXC Paper Trading Validation Cycle.

This script:
1. Closes all open MEXC paper trades (XAUT/USDT)
2. Sends closure reports via Telegram
3. Resets validation state
4. Initiates a new validation cycle
5. Sends new trade report

Usage:
    python scripts/cleanup_and_restart_mexc_cycle.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func

from app.config import settings
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.infra.telegram_notifier import TelegramNotifier
from app.infra.exchange_manager import UnifiedExchangeManager
from app.services.live_trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)


class MexcCycleManager:
    """Manages the cleanup and restart of MEXC paper trading cycles."""
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.exchange_manager = UnifiedExchangeManager(
            exchange_name="mexc",
            use_testnet=False  # MEXC Demo Futures doesn't use testnet flag
        )
        self.user_id = "default_user"
        
    async def close(self):
        """Close all connections."""
        await self.exchange_manager.close()
    
    async def step1_close_open_trades(self) -> List[Dict[str, Any]]:
        """
        Step 1: Identify and close all open MEXC paper trades.
        
        Returns:
            List of closed trade details
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Closing Open MEXC Paper Trades")
        logger.info("="*80)
        
        closed_trades = []
        
        async with async_session_maker() as db_session:
            # Query open MEXC trades for Gold symbols (various formats)
            gold_symbols = ['XAUT/USDT', 'PAXG/USDT', 'GOLD(XAUT)USDT', 'GOLDUSDT']
            
            stmt = select(PaperTrades).where(
                PaperTrades.user_id == self.user_id,
                PaperTrades.exchange == "mexc",
                PaperTrades.status == "open",
                PaperTrades.symbol.in_(gold_symbols)
            ).order_by(PaperTrades.ts_open)
            
            result = await db_session.execute(stmt)
            open_trades = result.scalars().all()
            
            if not open_trades:
                logger.info("✅ No open MEXC paper trades found")
                return closed_trades
            
            logger.info(f"📊 Found {len(open_trades)} open MEXC trade(s)")
            
            for trade in open_trades:
                try:
                    # Get current market price
                    ticker = await self.exchange_manager.fetch_ticker(trade.symbol)
                    exit_price = ticker['last_price']
                    
                    # Calculate P&L
                    if trade.side == 'LONG':
                        profit = (exit_price - trade.entry_price) * trade.qty
                    else:
                        profit = (trade.entry_price - exit_price) * trade.qty
                    
                    profit_pct = (profit / (trade.entry_price * trade.qty)) * 100 if trade.entry_price > 0 else 0
                    
                    # Update trade record
                    trade.ts_close = datetime.utcnow().isoformat()
                    trade.exit_price = exit_price
                    trade.profit = profit
                    trade.profit_pct = profit_pct
                    trade.status = 'closed'
                    trade.notes += f"\nClosed by cleanup script at ${exit_price:,.2f}"
                    
                    await db_session.flush()
                    
                    closed_trade_info = {
                        'trade_id': trade.id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'entry_price': trade.entry_price,
                        'exit_price': exit_price,
                        'quantity': trade.qty,
                        'profit': profit,
                        'profit_pct': profit_pct,
                        'duration': trade.ts_close,
                        'leverage': trade.leverage
                    }
                    
                    closed_trades.append(closed_trade_info)
                    
                    logger.info(f"   ✅ Closed Trade #{trade.id}: {trade.side} {trade.symbol}")
                    logger.info(f"      Entry: ${trade.entry_price:,.2f} → Exit: ${exit_price:,.2f}")
                    logger.info(f"      P&L: ${profit:+.2f} ({profit_pct:+.2f}%)")
                    
                except Exception as e:
                    logger.error(f"   ❌ Failed to close Trade #{trade.id}: {e}")
                    logger.exception("Details:")
            
            # Commit all changes
            await db_session.commit()
            logger.info(f"\n✅ Committed {len(closed_trades)} trade closures to database")
        
        return closed_trades
    
    async def step2_send_closure_reports(self, closed_trades: List[Dict[str, Any]]):
        """
        Step 2: Send Telegram closure reports for each closed trade.
        
        Args:
            closed_trades: List of closed trade details
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Sending Closure Reports via Telegram")
        logger.info("="*80)
        
        if not closed_trades:
            logger.info("ℹ️  No trades to report")
            return
        
        for trade in closed_trades:
            try:
                # Build notification message
                emoji = "✅" if trade['profit'] >= 0 else "❌"
                
                message = (
                    f"{emoji} <b>Trade Closed</b>\n\n"
                    f"<b>Trade ID:</b> #{trade['trade_id']}\n"
                    f"<b>Symbol:</b> {trade['symbol']}\n"
                    f"<b>Side:</b> {trade['side']}\n"
                    f"<b>Leverage:</b> {trade['leverage']}x\n\n"
                    f"<b>Entry Price:</b> ${trade['entry_price']:,.2f}\n"
                    f"<b>Exit Price:</b> ${trade['exit_price']:,.2f}\n"
                    f"<b>Quantity:</b> {trade['quantity']:.6f}\n\n"
                    f"<b>P&L:</b> ${trade['profit']:+.2f} ({trade['profit_pct']:+.2f}%)\n"
                    f"<b>Status:</b> {'Profit' if trade['profit'] >= 0 else 'Loss'}\n\n"
                    f"<i>Closed by cleanup script</i>\n"
                    f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
                )
                
                success = await self.notifier.send_message(message)
                
                if success:
                    logger.info(f"   ✅ Sent closure report for Trade #{trade['trade_id']}")
                else:
                    logger.warning(f"   ⚠️  Failed to send closure report for Trade #{trade['trade_id']}")
                    
            except Exception as e:
                logger.error(f"   ❌ Error sending closure report for Trade #{trade['trade_id']}: {e}")
    
    async def step3_reset_validation_state(self) -> bool:
        """
        Step 3: Verify no active positions remain for the test user.
        
        Returns:
            True if reset successful, False otherwise
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 3: Resetting Validation State")
        logger.info("="*80)
        
        async with async_session_maker() as db_session:
            # Check for any remaining open trades
            stmt = select(func.count(PaperTrades.id)).where(
                PaperTrades.user_id == self.user_id,
                PaperTrades.exchange == "mexc",
                PaperTrades.status == "open"
            )
            
            result = await db_session.execute(stmt)
            open_count = result.scalar() or 0
            
            if open_count == 0:
                logger.info("✅ Validation state reset complete - no open positions")
                
                # Get summary statistics
                stmt_total = select(func.count(PaperTrades.id)).where(
                    PaperTrades.user_id == self.user_id,
                    PaperTrades.exchange == "mexc"
                )
                result_total = await db_session.execute(stmt_total)
                total_trades = result_total.scalar() or 0
                
                stmt_closed = select(func.count(PaperTrades.id)).where(
                    PaperTrades.user_id == self.user_id,
                    PaperTrades.exchange == "mexc",
                    PaperTrades.status == "closed"
                )
                result_closed = await db_session.execute(stmt_closed)
                closed_trades = result_closed.scalar() or 0
                
                logger.info(f"   📊 Total MEXC trades: {total_trades}")
                logger.info(f"   📊 Closed trades: {closed_trades}")
                logger.info(f"   📊 Open trades: {open_count}")
                
                return True
            else:
                logger.error(f"❌ Still have {open_count} open positions!")
                return False
    
    async def step4_initiate_new_cycle(self) -> Dict[str, Any]:
        """
        Step 4: Initiate a new paper trade validation cycle.
        
        Returns:
            New trade execution results
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 4: Initiating New Validation Cycle")
        logger.info("="*80)
        
        try:
            # Initialize live trading service for MEXC
            trading_service = LiveTradingService(
                exchange_name="mexc",
                use_testnet=False,
                use_openrouter=True
            )
            
            # Execute trading cycle for Gold
            symbol = settings.GOLD_SYMBOL_MEXC  # XAUT/USDT
            
            logger.info(f"🚀 Starting new trading cycle for {symbol}...")
            
            async with async_session_maker() as db_session:
                result = await trading_service.execute_trading_cycle(
                    symbol=symbol,
                    user_id=self.user_id,
                    db_session=db_session
                )
            
            await trading_service.close()
            
            if result['status'] == 'success':
                logger.info("✅ New validation cycle completed successfully")
                
                # Extract key information
                execution = result.get('execution', {})
                proposal = result.get('ai_result', {}).get('trade_proposal', {})
                
                new_trade_info = {
                    'status': result['status'],
                    'cycle_time_ms': result.get('cycle_time_ms', 0),
                    'regime': result.get('ai_result', {}).get('regime'),
                    'strategy': proposal.get('strategy_name'),
                    'confidence': proposal.get('confidence'),
                    'side': proposal.get('side'),
                    'entry_price': proposal.get('entry_price'),
                    'stop_loss': proposal.get('stop_loss'),
                    'take_profit': proposal.get('take_profit'),
                    'leverage': proposal.get('leverage'),
                    'execution_status': execution.get('status'),
                    'trade_id': execution.get('trade_id'),
                    'order_id': execution.get('order_id')
                }
                
                return new_trade_info
            
            elif result['status'] == 'rejected':
                # Quality filter rejection - this is NORMAL behavior, not an error
                reason = result.get('rejection_reason', 'Unknown')
                quality_score = result.get('quality_score', 0)
                
                logger.info("⚠️  Trade rejected by quality filter")
                logger.info(f"   Quality Score: {quality_score}/100")
                logger.info(f"   Reason: {reason}")
                logger.info(f"   This is normal - system protecting capital from low-quality trades")
                
                new_trade_info = {
                    'status': 'rejected',
                    'cycle_time_ms': result.get('cycle_time_ms', 0),
                    'rejection_reason': reason,
                    'quality_score': quality_score
                }
                
                return new_trade_info
            
            else:
                # Actual failure - unexpected error
                logger.error(f" Validation cycle failed: {result.get('error')}")
                return {
                    'status': 'failed',
                    'error': result.get('error')
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to initiate new cycle: {e}")
            logger.exception("Traceback:")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def step5_send_new_trade_report(self, new_trade_info: Dict[str, Any]):
        """
        Step 5: Send Telegram report for the new trade.
            
        Args:
            new_trade_info: Details of the new trade
        """
        logger.info("\n" + "="*80)
        logger.info("STEP 5: Sending New Trade Report via Telegram")
        logger.info("="*80)
            
        # Handle quality filter rejection
        if new_trade_info.get('status') == 'rejected':
            reason = new_trade_info.get('rejection_reason', 'Unknown')
            quality_score = new_trade_info.get('quality_score', 0)
            cycle_time = new_trade_info.get('cycle_time_ms', 0)
                
            # Determine severity and emoji based on score
            if quality_score >= 80:
                emoji = "⚠️"
                severity = "MARGINAL"
            elif quality_score >= 60:
                emoji = ""
                severity = "LOW QUALITY"
            else:
                emoji = "🔴"
                severity = "POOR QUALITY"
                
            message = (
                f"{emoji} <b>Trade Proposal REJECTED by Quality Filter</b>\n\n"
                f"<b>Symbol:</b> {settings.GOLD_SYMBOL_MEXC}\n"
                f"<b>Severity:</b> {severity}\n"
                f"<b>Quality Score:</b> {quality_score}/100\n\n"
                f"<b>Rejection Reason:</b>\n"
                f"{reason}\n\n"
                f"<b>Cycle Time:</b> {cycle_time:.0f}ms\n"
                f"<b>Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                f"<i>This trade did not meet minimum quality standards and was blocked before validation.</i>"
            )
                
            await self.notifier.send_message(message)
            logger.info("✅ Sent quality filter rejection report to Telegram")
            return
            
        # Handle actual failures
        if new_trade_info.get('status') == 'failed':
            error_msg = new_trade_info.get('error', 'Unknown error')
            message = (
                f" <b>Validation Cycle Failed</b>\n\n"
                f"<b>Error:</b> {error_msg}\n\n"
                f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )
            await self.notifier.send_message(message)
            logger.warning("⚠️  Sent failure notification")
            return
        
        # Build success notification
        execution_status = new_trade_info.get('execution_status', 'unknown')
        
        if execution_status == 'executed':
            emoji = "✅"
            title = "New Trade Executed"
        elif execution_status in ['proposal_only', 'awaiting_confirmation']:
            emoji = "⏸️"
            title = "Trade Proposal Generated"
        elif execution_status == 'rejected':
            emoji = "❌"
            title = "Trade Rejected by Validator"
        else:
            emoji = "ℹ️"
            title = "Validation Complete"
        
        message = (
            f"{emoji} <b>{title}</b>\n\n"
            f"<b>Regime:</b> {new_trade_info.get('regime', 'N/A')}\n"
            f"<b>Strategy:</b> {new_trade_info.get('strategy', 'N/A')}\n"
            f"<b>Confidence:</b> {new_trade_info.get('confidence', 0):.2%}\n\n"
            f"<b>Side:</b> {new_trade_info.get('side', 'N/A')}\n"
            f"<b>Entry Price:</b> ${new_trade_info.get('entry_price', 0):,.2f}\n"
            f"<b>Stop Loss:</b> ${new_trade_info.get('stop_loss', 0):,.2f}\n"
            f"<b>Take Profit:</b> ${new_trade_info.get('take_profit', 0):,.2f}\n"
            f"<b>Leverage:</b> {new_trade_info.get('leverage', 1)}x\n\n"
        )
        
        if execution_status == 'executed':
            message += (
                f"<b>Trade ID:</b> #{new_trade_info.get('trade_id', 'N/A')}\n"
                f"<b>Order ID:</b> {new_trade_info.get('order_id', 'N/A')}\n"
                f"<b>Status:</b> EXECUTED ✅\n\n"
            )
        elif execution_status == 'rejected':
            message += (
                f"<b>Status:</b> REJECTED ❌\n"
                f"<i>Trade violated validation rules</i>\n\n"
            )
        else:
            message += (
                f"<b>Status:</b> {execution_status.upper()}\n\n"
            )
        
        message += (
            f"<b>Cycle Time:</b> {new_trade_info.get('cycle_time_ms', 0):.0f}ms\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        )
        
        success = await self.notifier.send_message(message)
        
        if success:
            logger.info("✅ Sent new trade report to Telegram")
        else:
            logger.warning("⚠️  Failed to send new trade report")
    
    async def run_full_procedure(self):
        """Execute the complete cleanup and restart procedure."""
        logger.info("\n" + "#"*80)
        logger.info("# MEXC PAPER TRADING VALIDATION CYCLE - CLEANUP & RESTART")
        logger.info("#"*80)
        logger.info(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"User ID: {self.user_id}")
        logger.info(f"Exchange: MEXC (Demo Futures)")
        logger.info(f"Symbol: {settings.GOLD_SYMBOL_MEXC}")
        
        try:
            # Step 1: Close open trades
            closed_trades = await self.step1_close_open_trades()
            
            # Step 2: Send closure reports
            await self.step2_send_closure_reports(closed_trades)
            
            # Step 3: Reset validation state
            reset_success = await self.step3_reset_validation_state()
            
            if not reset_success:
                logger.error("❌ Cannot proceed - validation state not clean")
                return False
            
            # Step 4: Initiate new cycle
            new_trade_info = await self.step4_initiate_new_cycle()
            
            # Step 5: Send new trade report
            await self.step5_send_new_trade_report(new_trade_info)
            
            # Summary
            logger.info("\n" + "="*80)
            logger.info("PROCEDURE COMPLETE")
            logger.info("="*80)
            logger.info(f"✅ Closed trades: {len(closed_trades)}")
            logger.info(f"✅ New trade status: {new_trade_info.get('status', 'unknown')}")
            logger.info(f"✅ Completed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Procedure failed: {e}")
            logger.exception("Traceback:")
            
            # Send error notification
            try:
                await self.notifier.send_message(
                    f"🚨 <b>Cleanup & Restart Procedure Failed</b>\n\n"
                    f"<b>Error:</b> {str(e)}\n\n"
                    f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
                )
            except:
                pass
            
            return False
        
        finally:
            await self.close()


async def main():
    """Main entry point."""
    manager = MexcCycleManager()
    success = await manager.run_full_procedure()
    
    if success:
        logger.info("\n🎉 Cleanup and restart procedure completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n💥 Cleanup and restart procedure failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
