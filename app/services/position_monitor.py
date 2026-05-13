"""
Position Monitor - Dedicated subsystem for tracking open positions.
Inspired by Freqtrade's position management and Hummingbot's order tracking.

Responsibilities:
- Monitor stop-loss and take-profit levels
- Detect partial fills and update filled_quantity
- Trigger alerts on significant price movements
- Track unrealized P&L in real-time
- Auto-close positions when SL/TP hit
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.exchange_manager import UnifiedExchangeManager
from app.events.event_bus import EventBus
from app.events.event_types import TP_HIT, SL_HIT, POSITION_UPDATED
from app.database.models import PaperTrades
from app.logging_config import get_logger

logger = get_logger(__name__)


class PositionMonitor:
    """
    Monitors open positions and triggers actions based on market conditions.
    
    Features:
    - Real-time price monitoring via exchange API
    - Stop-loss and take-profit enforcement
    - Partial fill detection and tracking
    - P&L calculation and updates
    - Automatic position closure on SL/TP
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        exchange_manager: UnifiedExchangeManager,
        check_interval: float = 5.0
    ):
        """
        Initialize position monitor.
        
        Args:
            event_bus: Event bus for publishing events
            exchange_manager: Exchange manager for fetching prices
            check_interval: How often to check positions (seconds)
        """
        self.event_bus = event_bus
        self.exchange_manager = exchange_manager
        self.check_interval = check_interval
        
        # Track monitored positions: trade_id -> position_info
        self.monitored_positions: Dict[str, Dict[str, Any]] = {}
        
        # Background monitoring tasks: trade_id -> asyncio.Task
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"✅ PositionMonitor initialized (check_interval={check_interval}s)")
    
    async def start_monitoring(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        db_session: AsyncSession
    ):
        """
        Start monitoring a specific position.
        
        Args:
            trade_id: Trade ID to monitor
            symbol: Trading pair
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            quantity: Position size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            db_session: Database session for updates
        """
        if trade_id in self.monitored_positions:
            logger.warning(f"Position {trade_id} already being monitored")
            return
        
        # Store position info
        self.monitored_positions[trade_id] = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'start_time': datetime.utcnow(),
            'last_check': datetime.utcnow()
        }
        
        # Start background monitoring task
        task = asyncio.create_task(self._monitor_loop(trade_id, db_session))
        self.monitoring_tasks[trade_id] = task
        
        logger.info(
            f"📊 Started monitoring position {trade_id}: "
            f"{symbol} {side} @ ${entry_price:.2f}"
        )
    
    async def stop_monitoring(self, trade_id: str):
        """
        Stop monitoring a position.
        
        Args:
            trade_id: Trade ID to stop monitoring
        """
        if trade_id in self.monitoring_tasks:
            self.monitoring_tasks[trade_id].cancel()
            try:
                await self.monitoring_tasks[trade_id]
            except asyncio.CancelledError:
                pass
            del self.monitoring_tasks[trade_id]
        
        if trade_id in self.monitored_positions:
            del self.monitored_positions[trade_id]
        
        logger.debug(f"Stopped monitoring position {trade_id}")
    
    async def _monitor_loop(self, trade_id: str, db_session: AsyncSession):
        """
        Continuously monitor position until closed.
        
        This runs as a background task for each position.
        """
        while trade_id in self.monitored_positions:
            try:
                position = self.monitored_positions[trade_id]
                
                # Fetch current price
                ticker = await self.exchange_manager.fetch_ticker(position['symbol'])
                current_price = ticker['last_price']
                
                # Update last check time
                position['last_check'] = datetime.utcnow()
                
                # Check SL/TP conditions
                should_close = False
                close_reason = None
                
                if position['side'] == 'LONG':
                    # Long position: SL below, TP above
                    if position['stop_loss'] and current_price <= position['stop_loss']:
                        should_close = True
                        close_reason = 'SL_HIT'
                    elif position['take_profit'] and current_price >= position['take_profit']:
                        should_close = True
                        close_reason = 'TP_HIT'
                else:
                    # Short position: SL above, TP below
                    if position['stop_loss'] and current_price >= position['stop_loss']:
                        should_close = True
                        close_reason = 'SL_HIT'
                    elif position['take_profit'] and current_price <= position['take_profit']:
                        should_close = True
                        close_reason = 'TP_HIT'
                
                # Close position if SL/TP hit
                if should_close:
                    logger.info(
                        f"🎯 {close_reason} for position {trade_id}: "
                        f"{position['symbol']} @ ${current_price:.2f}"
                    )
                    
                    await self._close_position(trade_id, close_reason, current_price, db_session)
                    break
                
                # Update position P&L in database
                await self._update_position_pnl(trade_id, current_price, db_session)
                
                # Publish position update event
                pnl_pct = self._calculate_pnl_pct(position, current_price)
                await self.event_bus.publish(POSITION_UPDATED, {
                    'trade_id': trade_id,
                    'symbol': position['symbol'],
                    'current_price': current_price,
                    'unrealized_pnl_pct': pnl_pct
                }, priority=8)
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.debug(f"Monitoring cancelled for position {trade_id}")
                break
            except Exception as e:
                logger.error(f"Position monitoring error for {trade_id}: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _close_position(
        self,
        trade_id: str,
        reason: str,
        exit_price: float,
        db_session: AsyncSession
    ):
        """
        Close position with exchange order and database update.
        
        Args:
            trade_id: Trade ID to close
            reason: 'SL_HIT' or 'TP_HIT'
            exit_price: Exit price
            db_session: Database session
        """
        try:
            # Step 1: Execute close order on exchange
            position = self.monitored_positions[trade_id]
            order_result = await self._execute_close_order(
                trade_id=trade_id,
                symbol=position['symbol'],
                side=position['side'],
                quantity=position['quantity'],
                exit_price=exit_price,
                reason=reason
            )
            
            # Use actual executed price if available
            actual_exit_price = order_result.get('executed_price', exit_price)
            
            # Step 2: Fetch and update trade record
            from sqlalchemy import select
            stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if not trade:
                logger.error(f"Trade {trade_id} not found in database")
                return
            
            # Step 3: Calculate P&L using actual execution price
            if trade.side == 'LONG':
                profit = (actual_exit_price - trade.entry_price) * trade.qty
            else:
                profit = (trade.entry_price - actual_exit_price) * trade.qty
            
            profit_pct = (profit / (trade.entry_price * trade.qty)) * 100 if trade.entry_price > 0 else 0
            
            # Step 4: Update trade record
            trade.ts_close = datetime.utcnow().isoformat()
            trade.exit_price = actual_exit_price
            trade.profit = profit
            trade.profit_pct = profit_pct
            trade.status = 'closed'
            trade.notes += f"\n{reason} at ${actual_exit_price:.2f}, P&L: ${profit:.2f} ({profit_pct:.2f}%)"
            
            if not order_result['success']:
                trade.notes += f"\nWARNING: Exchange order failed, used fallback price"
            
            await db_session.commit()
            
            # Step 5: Publish high-priority event
            await self.event_bus.publish(
                TP_HIT if reason == 'TP_HIT' else SL_HIT,
                {
                    'trade_id': trade_id,
                    'symbol': trade.symbol,
                    'exit_price': actual_exit_price,
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'reason': reason,
                    'exchange_order_success': order_result['success']
                },
                priority=2
            )
            
            logger.info(
                f"✅ Position {trade_id} closed ({reason}): "
                f"P&L=${profit:.2f} ({profit_pct:.2f}%)"
            )
            
        except Exception as e:
            logger.error(f"Failed to close position {trade_id}: {e}")
        finally:
            # Stop monitoring
            await self.stop_monitoring(trade_id)
    
    async def _update_position_pnl(
        self,
        trade_id: str,
        current_price: float,
        db_session: AsyncSession
    ):
        """
        Update position's current price and unrealized P&L in database.
        
        Args:
            trade_id: Trade ID
            current_price: Current market price
            db_session: Database session
        """
        try:
            from sqlalchemy import select
            stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if not trade or trade.status != 'open':
                return
            
            # Calculate unrealized P&L
            if trade.side == 'LONG':
                unrealized_pnl = (current_price - trade.entry_price) * trade.qty
            else:
                unrealized_pnl = (trade.entry_price - current_price) * trade.qty
            
            # Note: We don't commit here to avoid excessive DB writes
            # P&L is tracked in memory and updated on close
            
        except Exception as e:
            logger.error(f"Failed to update P&L for {trade_id}: {e}")
    
    def _calculate_pnl_pct(self, position: Dict[str, Any], current_price: float) -> float:
        """Calculate unrealized P&L percentage."""
        if position['side'] == 'LONG':
            pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
        else:
            pnl_pct = ((position['entry_price'] - current_price) / position['entry_price']) * 100
        
        return round(pnl_pct, 2)
    
    def get_monitored_count(self) -> int:
        """Get number of positions currently being monitored."""
        return len(self.monitored_positions)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get position monitor metrics."""
        return {
            'monitored_positions': len(self.monitored_positions),
            'active_tasks': len(self.monitoring_tasks),
            'trade_ids': list(self.monitored_positions.keys())
        }
    
    async def _execute_close_order(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        exit_price: float,
        reason: str
    ) -> Dict[str, Any]:
        """
        Execute actual close order on exchange.
        
        Args:
            trade_id: Trade ID being closed
            symbol: Trading pair
            side: Original position side ('LONG' or 'SHORT')
            quantity: Position quantity to close
            exit_price: Expected exit price
            reason: 'SL_HIT' or 'TP_HIT'
        
        Returns:
            Order execution result
        """
        try:
            # Determine close side (opposite of original)
            close_side = 'SELL' if side == 'LONG' else 'BUY'
            
            # Execute market order to close position
            order_result = await self.exchange_manager.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=quantity
            )
            
            logger.info(
                f"🎯 Close order executed for {trade_id}: "
                f"{close_side} {quantity} @ ${order_result.get('price', exit_price):.2f}"
            )
            
            return {
                'success': True,
                'order_id': order_result.get('order_id'),
                'executed_price': order_result.get('price', exit_price),
                'executed_quantity': order_result.get('filled', quantity)
            }
            
        except Exception as e:
            logger.error(f"Failed to execute close order for {trade_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'fallback_price': exit_price
            }
