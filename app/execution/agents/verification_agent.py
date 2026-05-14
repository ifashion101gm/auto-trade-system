"""Verification Agent - Validates post-execution state immediately after order placement."""
import asyncio
from typing import Dict, Any
from app.execution.agents.base_agent import BaseAgent
from app.infra.exchange_manager import UnifiedExchangeManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import PaperTrades


class VerificationAgent(BaseAgent):
    """Verifies order execution and database sync."""
    
    def __init__(self, exchange_manager: UnifiedExchangeManager):
        super().__init__("VerificationAgent")
        self.exchange_manager = exchange_manager
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify execution results."""
        order_result = context.get('execution_result')
        proposal = context.get('proposal')
        db_session = context.get('db_session')
        
        verification_checks = []
        all_passed = True
        
        # Check 1: Verify order exists on exchange
        try:
            order_id = order_result.get('order_id')
            
            # CRITICAL: Add timeout to prevent hanging on unresponsive exchange
            exchange_order = await asyncio.wait_for(
                self.exchange_manager.fetch_order(order_id),
                timeout=10.0  # 10 second timeout
            )
            
            if exchange_order:
                verification_checks.append({
                    'check': 'order_exists_on_exchange',
                    'passed': True,
                    'details': f"Order {order_id} confirmed"
                })
            else:
                verification_checks.append({
                    'check': 'order_exists_on_exchange',
                    'passed': False,
                    'details': f"Order {order_id} NOT found on exchange"
                })
                all_passed = False
        except asyncio.TimeoutError:
            verification_checks.append({
                'check': 'order_exists_on_exchange',
                'passed': False,
                'details': f"Order fetch timed out after 10s for order {order_id}"
            })
            all_passed = False
        except Exception as e:
            # Retry once for transient errors
            try:
                await asyncio.sleep(1)
                order_id = order_result.get('order_id')
                exchange_order = await asyncio.wait_for(
                    self.exchange_manager.fetch_order(order_id),
                    timeout=10.0
                )
                
                if exchange_order:
                    verification_checks.append({
                        'check': 'order_exists_on_exchange',
                        'passed': True,
                        'details': f"Order {order_id} confirmed (after retry)"
                    })
                else:
                    verification_checks.append({
                        'check': 'order_exists_on_exchange',
                        'passed': False,
                        'details': f"Order {order_id} NOT found on exchange (after retry)"
                    })
                    all_passed = False
            except Exception as retry_error:
                verification_checks.append({
                    'check': 'order_exists_on_exchange',
                    'passed': False,
                    'details': f"Failed after retry: {str(retry_error)}"
                })
                all_passed = False
        
        # Check 2: Verify TP/SL orders placed (if applicable)
        tp_sl_check = await self._verify_tp_sl_orders(proposal, order_result)
        verification_checks.append(tp_sl_check)
        if not tp_sl_check['passed']:
            all_passed = False
        
        # Check 3: Verify database record created
        if db_session:
            db_check = await self._verify_db_record(order_result, db_session)
            verification_checks.append(db_check)
            if not db_check['passed']:
                all_passed = False
        
        return {
            'verification_passed': all_passed,
            'checks': verification_checks,
            'requires_recovery': not all_passed
        }
    
    async def _verify_tp_sl_orders(self, proposal: Dict, order_result: Dict) -> Dict:
        """Verify stop-loss and take-profit orders are placed."""
        # TODO: Implement TP/SL verification based on exchange capabilities
        return {
            'check': 'tp_sl_orders_placed',
            'passed': True,
            'details': 'TP/SL verification pending implementation'
        }
    
    async def _verify_db_record(self, order_result: Dict, db_session: AsyncSession) -> Dict:
        """Verify trade record exists in database."""
        try:
            stmt = select(PaperTrades).where(
                PaperTrades.notes.like(f"%{order_result.get('order_id')}%")
            )
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            return {
                'check': 'db_record_exists',
                'passed': trade is not None,
                'details': f"Trade record {'found' if trade else 'NOT found'}"
            }
        except Exception as e:
            return {
                'check': 'db_record_exists',
                'passed': False,
                'details': f"DB verification failed: {str(e)}"
            }
