"""
Trade State Recovery Engine - Recovers trade states after system restart.

Implements Freqtrade-style trade persistence to ensure atomic state recovery
after crashes, preventing phantom trades and ensuring consistency between
local database and exchange state.

Features:
- Detects stuck pending trades
- Verifies order status on exchange
- Atomically updates trade states
- Logs recovery actions for audit trail
- Integrates with reconciliation engine
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import PaperTrades, TradeProposals
from app.logging_config import get_logger
from app.infra.exchange_manager import UnifiedExchangeManager

logger = get_logger(__name__)


class TradeStateRecovery:
    """
    Recovers trade states after system restart or crash.
    
    This engine scans for trades in transitional states (ORDER_SUBMITTING, 
    PENDING_CONFIRMATION) and verifies their actual status on the exchange.
    It then updates the local database to match reality.
    """
    
    def __init__(self, exchange_manager: UnifiedExchangeManager):
        """
        Initialize state recovery engine.
        
        Args:
            exchange_manager: Exchange manager for querying order status
        """
        self.exchange_manager = exchange_manager
        logger.info("✅ Trade State Recovery Engine initialized")
    
    async def recover_pending_trades(
        self,
        db_session: AsyncSession,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Find and recover trades stuck in pending states.
        
        This should be called during system startup to ensure no trades
        are left in inconsistent states after a crash.
        
        Args:
            db_session: Database session
            user_id: User ID to filter trades
            
        Returns:
            Dictionary with recovery results
        """
        logger.info("🔄 Starting trade state recovery...")
        
        recovery_results = {
            'total_checked': 0,
            'recovered': 0,
            'failed': 0,
            'pending_reconciliation': 0,
            'details': []
        }
        
        try:
            # Find trades in transitional states
            stmt = select(PaperTrades).where(
                PaperTrades.user_id == user_id,
                PaperTrades.status.in_([
                    'ORDER_SUBMITTING',
                    'PENDING_CONFIRMATION',
                    'EXECUTING'
                ])
            )
            result = await db_session.execute(stmt)
            pending_trades = result.scalars().all()
            
            recovery_results['total_checked'] = len(pending_trades)
            
            if not pending_trades:
                logger.info("✅ No pending trades found - system state is clean")
                return recovery_results
            
            logger.info(f"Found {len(pending_trades)} pending trades to verify")
            
            # Process each pending trade
            for trade in pending_trades:
                try:
                    recovery_result = await self._recover_single_trade(trade, db_session)
                    recovery_results['details'].append(recovery_result)
                    
                    if recovery_result['action'] == 'recovered_to_open':
                        recovery_results['recovered'] += 1
                    elif recovery_result['action'] == 'marked_failed':
                        recovery_results['failed'] += 1
                    else:
                        recovery_results['pending_reconciliation'] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to recover trade {trade.id}: {e}")
                    recovery_results['failed'] += 1
                    recovery_results['details'].append({
                        'trade_id': trade.id,
                        'action': 'error',
                        'error': str(e)
                    })
            
            # Commit all changes
            await db_session.commit()
            
            logger.info(
                f"✅ Trade state recovery complete: "
                f"{recovery_results['recovered']} recovered, "
                f"{recovery_results['failed']} failed, "
                f"{recovery_results['pending_reconciliation']} pending reconciliation"
            )
            
            return recovery_results
            
        except Exception as e:
            logger.error(f"Trade state recovery failed: {e}")
            await db_session.rollback()
            raise
    
    async def _recover_single_trade(
        self,
        trade: PaperTrades,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Recover a single trade by checking exchange status.
        
        Args:
            trade: Trade record to recover
            db_session: Database session
            
        Returns:
            Recovery action taken
        """
        trade_id = trade.id
        symbol = trade.symbol
        
        logger.info(f"🔍 Verifying trade {trade_id} ({symbol})...")
        
        # Extract order ID from notes if available
        order_id = self._extract_order_id(trade.notes)
        
        if not order_id:
            logger.warning(f"Trade {trade_id} has no order ID - marking as failed")
            await self._mark_trade_failed(trade, db_session, "No order ID found")
            return {
                'trade_id': trade_id,
                'symbol': symbol,
                'action': 'marked_failed',
                'reason': 'no_order_id'
            }
        
        # Check order status on exchange
        try:
            exchange_status = await self._verify_exchange_order(symbol, order_id)
            
            if exchange_status == 'filled' or exchange_status == 'partially_filled':
                # Order exists and is filled - update to OPEN
                await self._update_trade_to_open(trade, db_session, exchange_status)
                logger.info(f"✅ Trade {trade_id} recovered to OPEN state")
                
                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'order_id': order_id,
                    'action': 'recovered_to_open',
                    'exchange_status': exchange_status
                }
                
            elif exchange_status == 'cancelled' or exchange_status == 'rejected':
                # Order was cancelled/rejected - mark as failed
                await self._mark_trade_failed(
                    trade, db_session, f"Order {exchange_status} on exchange"
                )
                logger.warning(f"⚠️  Trade {trade_id} marked as failed ({exchange_status})")
                
                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'order_id': order_id,
                    'action': 'marked_failed',
                    'reason': f'order_{exchange_status}'
                }
                
            elif exchange_status == 'open' or exchange_status == 'new':
                # Order still pending on exchange - keep status but add note
                trade.notes += f"\n[RECOVERY] Verified on exchange at {datetime.utcnow().isoformat()} - Status: {exchange_status}"
                await db_session.flush()
                
                logger.info(f"ℹ️  Trade {trade_id} still pending on exchange")
                
                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'order_id': order_id,
                    'action': 'pending_reconciliation',
                    'exchange_status': exchange_status
                }
                
            else:
                # Order not found - might be very old or deleted
                logger.warning(f"⚠️  Order {order_id} not found on exchange")
                await self._mark_trade_failed(trade, db_session, "Order not found on exchange")
                
                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'order_id': order_id,
                    'action': 'marked_failed',
                    'reason': 'order_not_found'
                }
                
        except Exception as e:
            logger.error(f"Failed to verify order {order_id} on exchange: {e}")
            # Don't update status - let reconciliation handle it later
            return {
                'trade_id': trade_id,
                'symbol': symbol,
                'order_id': order_id,
                'action': 'pending_reconciliation',
                'error': str(e)
            }
    
    async def _verify_exchange_order(self, symbol: str, order_id: str) -> Optional[str]:
        """
        Verify order status on exchange.
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to check
            
        Returns:
            Order status string or None if not found
        """
        try:
            # Use exchange manager to fetch order
            order = await self.exchange_manager.fetch_order(order_id, symbol)
            
            if order:
                status = order.get('status', '').lower()
                
                # Map exchange status to our status
                status_mapping = {
                    'filled': 'filled',
                    'closed': 'filled',
                    'partially_filled': 'partially_filled',
                    'canceled': 'cancelled',
                    'cancelled': 'cancelled',
                    'rejected': 'rejected',
                    'open': 'open',
                    'new': 'open',
                    'pending': 'open'
                }
                
                return status_mapping.get(status, status)
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Could not fetch order {order_id}: {e}")
            return None
    
    async def _update_trade_to_open(
        self,
        trade: PaperTrades,
        db_session: AsyncSession,
        exchange_status: str
    ):
        """Update trade status to OPEN after successful recovery."""
        trade.status = 'open'
        trade.trade_status = 'POSITION_OPEN'
        trade.notes += f"\n[RECOVERY] Recovered to OPEN at {datetime.utcnow().isoformat()} (exchange status: {exchange_status})"
        await db_session.flush()
    
    async def _mark_trade_failed(
        self,
        trade: PaperTrades,
        db_session: AsyncSession,
        reason: str
    ):
        """Mark trade as failed after recovery determines it cannot proceed."""
        trade.status = 'failed'
        trade.trade_status = 'FAILED'
        trade.notes += f"\n[RECOVERY] Marked as FAILED at {datetime.utcnow().isoformat()}. Reason: {reason}"
        await db_session.flush()
    
    def _extract_order_id(self, notes: Optional[str]) -> Optional[str]:
        """
        Extract order ID from trade notes.
        
        Args:
            notes: Trade notes field
            
        Returns:
            Order ID string or None
        """
        if not notes:
            return None
        
        # Look for "Order ID: XXXX" pattern
        import re
        match = re.search(r'Order ID:\s*(\S+)', notes)
        if match:
            return match.group(1)
        
        return None
    
    async def recover_pending_proposals(
        self,
        db_session: AsyncSession,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """
        Recover trade proposals stuck in pending state.
        
        Similar to trade recovery but for proposals that never became trades.
        
        Args:
            db_session: Database session
            user_id: User ID to filter proposals
            
        Returns:
            Recovery results
        """
        logger.info("🔄 Checking for pending proposals...")
        
        try:
            stmt = select(TradeProposals).where(
                TradeProposals.user_id == user_id,
                TradeProposals.status == 'pending'
            )
            result = await db_session.execute(stmt)
            pending_proposals = result.scalars().all()
            
            if not pending_proposals:
                logger.info("✅ No pending proposals found")
                return {'total': 0, 'expired': 0}
            
            expired_count = 0
            cutoff_time = datetime.utcnow().timestamp() - 3600  # 1 hour ago
            
            for proposal in pending_proposals:
                # Parse timestamp
                try:
                    proposal_time = datetime.fromisoformat(proposal.ts.replace('Z', '+00:00')).timestamp()
                    
                    if proposal_time < cutoff_time:
                        # Proposal is older than 1 hour - mark as expired
                        proposal.status = 'expired'
                        expired_count += 1
                        logger.info(f"Expired proposal {proposal.id} (older than 1 hour)")
                        
                except Exception as e:
                    logger.warning(f"Could not parse proposal timestamp: {e}")
            
            if expired_count > 0:
                await db_session.commit()
                logger.info(f"✅ Expired {expired_count} stale proposals")
            
            return {
                'total': len(pending_proposals),
                'expired': expired_count
            }
            
        except Exception as e:
            logger.error(f"Proposal recovery failed: {e}")
            return {'total': 0, 'expired': 0, 'error': str(e)}
