"""
Execution Service - Centralized trade execution with proper layering.

This service implements the professional execution architecture:
API → Execution Service → Risk Engine → Exchange Connector → Event Bus → Database

Features:
- Atomic trade execution with proper state management
- Integrated risk validation before order placement
- Event-driven architecture for observability
- Comprehensive error handling and recovery
- Support for multiple execution modes
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.exchange_manager import UnifiedExchangeManager
from app.risk.risk_engine import RiskEngine
from app.risk.validator import TradeValidator
from app.notifications.notifier import TelegramNotifier
from app.events.event_bus import event_bus
from app.database.models import PaperTrades, TradeProposals
from app.logging_config import get_logger
from app.infra.circuit_breaker import SystemCircuitBreaker

logger = get_logger(__name__)


@dataclass
class ExecutionRequest:
    """Trade execution request with all required parameters."""
    symbol: str
    side: str  # 'buy' or 'sell', 'long' or 'short'
    entry_price: float
    quantity: float
    leverage: int = 1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_name: Optional[str] = None
    confidence: Optional[float] = None
    user_id: str = "default_user"
    execution_mode: str = "fully-auto"  # proposal, semi-auto, fully-auto


@dataclass
class ExecutionResult:
    """Trade execution result with comprehensive status information."""
    success: bool
    order_id: Optional[str] = None
    trade_id: Optional[int] = None
    filled_price: Optional[float] = None
    filled_quantity: Optional[float] = None
    fee: Optional[float] = None
    status: str = "pending"  # pending, executed, rejected, failed
    error: Optional[str] = None
    warnings: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'success': self.success,
            'order_id': self.order_id,
            'trade_id': self.trade_id,
            'filled_price': self.filled_price,
            'filled_quantity': self.filled_quantity,
            'fee': self.fee,
            'status': self.status,
            'error': self.error,
            'warnings': self.warnings,
            **self.metadata
        }


class ExecutionService:
    """
    Centralized trade execution service implementing professional architecture.
    
    Execution Flow:
    1. Validate request parameters
    2. Run risk engine checks
    3. Create pending proposal record
    4. Place order on exchange (with timeout/retry)
    5. Update database records atomically
    6. Publish execution events
    7. Send notifications
    
    All steps are wrapped in proper error handling with rollback capability.
    """
    
    def __init__(
        self,
        exchange_name: str = "binance",
        use_testnet: bool = True,
        db_session_factory = None
    ):
        """
        Initialize execution service.
        
        Args:
            exchange_name: Exchange to execute on
            use_testnet: Use testnet mode
            db_session_factory: Factory function to create DB sessions
        """
        self.exchange_name = exchange_name
        self.use_testnet = use_testnet
        self.db_session_factory = db_session_factory
        
        # Initialize components
        self.exchange_manager = UnifiedExchangeManager(
            exchange_name=exchange_name,
            use_testnet=use_testnet
        )
        self.risk_engine = RiskEngine(db_session=None)
        self.validator = TradeValidator()
        self.notifier = TelegramNotifier()
        
        # NEW: Circuit breaker for system-wide health monitoring
        self.circuit_breaker = SystemCircuitBreaker(notifier=self.notifier)
        logger.info("✅ Circuit Breaker integrated into ExecutionService")
        
        logger.info(f"✅ Execution Service initialized ({exchange_name.upper()} {'TESTNET' if use_testnet else 'LIVE'})")
    
    async def execute_trade(
        self,
        request: ExecutionRequest,
        db_session: Optional[AsyncSession] = None
    ) -> ExecutionResult:
        """
        Execute trade through complete validation and execution pipeline.
        
        This is the main entry point for trade execution, implementing
        the full professional workflow with proper error handling.
        
        Args:
            request: Trade execution request with all parameters
            db_session: Database session (optional, will create if not provided)
            
        Returns:
            ExecutionResult with comprehensive status information
        """
        # Use provided session or create new one
        should_close_session = False
        if db_session is None:
            if self.db_session_factory:
                db_session = await self.db_session_factory()
                should_close_session = True
            else:
                return ExecutionResult(
                    success=False,
                    status='failed',
                    error='No database session available'
                )
        
        try:
            # STEP 0: Circuit breaker health check (NEW - Freqtrade pattern)
            circuit_state = await self.circuit_breaker.check_system_health()
            if not circuit_state.can_trade:
                logger.warning(f"🚫 Trade blocked by circuit breaker: {circuit_state.reason}")
                return ExecutionResult(
                    success=False,
                    status='blocked_by_circuit_breaker',
                    error=f"Circuit breaker OPEN: {circuit_state.reason}"
                )
            
            # STEP 1: Validate request parameters
            validation_result = await self._validate_request(request)
            if not validation_result.success:
                return validation_result
            
            # STEP 2: Run risk engine checks
            risk_result = await self._check_risk(request, db_session)
            if not risk_result.success:
                return risk_result
            
            # STEP 3: Create pending proposal record
            proposal_result = await self._create_proposal(request, db_session)
            if not proposal_result.success:
                return proposal_result
            
            proposal_id = proposal_result.metadata.get('proposal_id')
            
            # STEP 4: Place order on exchange (with timeout/retry)
            order_result = await self._place_order(request, db_session, proposal_id)
            if not order_result.success:
                # Rollback: Mark proposal as failed
                await self._mark_proposal_failed(proposal_id, db_session, order_result.error)
                return order_result
            
            # STEP 5: Create trade record AFTER successful order
            trade_result = await self._create_trade_record(
                request, order_result, db_session, proposal_id
            )
            if not trade_result.success:
                return trade_result
            
            # STEP 6: Publish execution event
            await self._publish_execution_event(order_result, trade_result)
            
            # STEP 7: Send notification
            await self._send_notification(order_result, trade_result)
            
            # Success!
            return ExecutionResult(
                success=True,
                order_id=order_result.order_id,
                trade_id=trade_result.trade_id,
                filled_price=order_result.filled_price,
                filled_quantity=order_result.filled_quantity,
                fee=order_result.fee,
                status='executed',
                metadata={
                    'proposal_id': proposal_id,
                    'execution_time': datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                status='failed',
                error=str(e)
            )
        
        finally:
            # Close session if we created it
            if should_close_session and db_session:
                await db_session.close()
    
    async def _validate_request(self, request: ExecutionRequest) -> ExecutionResult:
        """Validate execution request parameters."""
        errors = []
        
        # CRITICAL: Enforce XAUUSDT-only trading
        from app.config import settings
        normalized_symbol = request.symbol.upper().replace('/', '').replace(':', '')
        allowed_symbols = [s.upper().replace('/', '').replace(':', '') for s in settings.ENABLED_TRADING_SYMBOLS]
        
        if normalized_symbol not in allowed_symbols:
            return ExecutionResult(
                success=False,
                status='rejected',
                error=f"Symbol '{request.symbol}' NOT ALLOWED. Trading is EXCLUSIVELY restricted to XAUUSDT (Gold). Allowed symbols: {settings.ENABLED_TRADING_SYMBOLS}"
            )
        
        # Check required fields
        if not request.symbol:
            errors.append("Symbol is required")
        
        if request.side.lower() not in ['buy', 'sell', 'long', 'short']:
            errors.append(f"Invalid side: {request.side}")
        
        if request.entry_price <= 0:
            errors.append("Entry price must be positive")
        
        if request.quantity <= 0:
            errors.append("Quantity must be positive")
        
        if request.leverage < 1:
            errors.append("Leverage must be at least 1")
        
        if errors:
            return ExecutionResult(
                success=False,
                status='rejected',
                error=f"Validation failed: {'; '.join(errors)}"
            )
        
        return ExecutionResult(success=True, status='validated')
    
    async def _check_risk(
        self,
        request: ExecutionRequest,
        db_session: AsyncSession
    ) -> ExecutionResult:
        """Run risk engine validation."""
        try:
            # Create proposal dict for risk engine
            proposal = {
                'symbol': request.symbol,
                'side': request.side.upper(),
                'entry_price': request.entry_price,
                'quantity': request.quantity,
                'leverage': request.leverage,
                'stop_loss': request.stop_loss,
                'take_profit': request.take_profit,
                'confidence': request.confidence or 0.5,
                'strategy_name': request.strategy_name or 'manual'
            }
            
            # Run risk checks
            risk_decision = await self.risk_engine.check_trade_approval(
                proposal=proposal,
                user_id=request.user_id
            )
            
            if not risk_decision.approved:
                return ExecutionResult(
                    success=False,
                    status='rejected',
                    error=f"Risk check failed: {'; '.join(risk_decision.violations)}",
                    metadata={'risk_violations': risk_decision.violations}
                )
            
            # Add warnings if any
            warnings = []
            if risk_decision.warnings:
                warnings.extend(risk_decision.warnings)
            
            return ExecutionResult(
                success=True,
                status='risk_approved',
                warnings=warnings,
                metadata={'risk_score': risk_decision.risk_score}
            )
            
        except Exception as e:
            logger.error(f"Risk check failed: {e}")
            return ExecutionResult(
                success=False,
                status='failed',
                error=f"Risk check error: {str(e)}"
            )
    
    async def _create_proposal(
        self,
        request: ExecutionRequest,
        db_session: AsyncSession
    ) -> ExecutionResult:
        """Create pending trade proposal record."""
        try:
            from sqlalchemy import select
            
            # Check if proposal already exists (idempotency)
            stmt = select(TradeProposals).where(
                TradeProposals.user_id == request.user_id,
                TradeProposals.symbol == request.symbol,
                TradeProposals.side == request.side.upper(),
                TradeProposals.entry_price == request.entry_price,
                TradeProposals.status == 'pending'
            )
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"Using existing proposal: {existing.id}")
                return ExecutionResult(
                    success=True,
                    status='proposal_exists',
                    metadata={'proposal_id': existing.id}
                )
            
            # Create new proposal
            proposal = TradeProposals(
                ts=datetime.utcnow().isoformat(),
                user_id=request.user_id,
                exchange=self.exchange_name,
                symbol=request.symbol,
                side=request.side.upper(),
                entry_price=request.entry_price,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                quantity=request.quantity,
                confidence=request.confidence,
                strategy_name=request.strategy_name,
                status='pending',
                ai_metadata='{}'
            )
            
            db_session.add(proposal)
            await db_session.flush()  # Get ID, but don't commit yet
            
            logger.info(f"Created proposal: {proposal.id}")
            
            return ExecutionResult(
                success=True,
                status='proposal_created',
                metadata={'proposal_id': proposal.id}
            )
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            return ExecutionResult(
                success=False,
                status='failed',
                error=f"Proposal creation failed: {str(e)}"
            )
    
    async def _place_order(
        self,
        request: ExecutionRequest,
        db_session: AsyncSession,
        proposal_id: int
    ) -> ExecutionResult:
        """Place order on exchange with timeout and retry."""
        max_retries = 3
        timeout_seconds = 10
        
        for attempt in range(max_retries):
            try:
                # Place order with timeout
                order_result = await asyncio.wait_for(
                    self.exchange_manager.create_market_order(
                        symbol=request.symbol,
                        side=request.side.lower(),
                        amount=request.quantity,
                        leverage=request.leverage
                    ),
                    timeout=timeout_seconds
                )
                
                # Update proposal status
                from sqlalchemy import select
                stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                result = await db_session.execute(stmt)
                proposal = result.scalar_one_or_none()
                
                if proposal:
                    proposal.status = 'executed'
                    await db_session.flush()
                
                logger.info(f"Order placed successfully: {order_result.get('order_id')}")
                
                return ExecutionResult(
                    success=True,
                    order_id=order_result.get('order_id'),
                    filled_price=order_result.get('price') or request.entry_price,
                    filled_quantity=order_result.get('filled', request.quantity),
                    fee=order_result.get('fee', {}).get('cost', 0),
                    status='order_placed'
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"Order placement timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return ExecutionResult(
                        success=False,
                        status='failed',
                        error=f"Order placement timed out after {max_retries} attempts"
                    )
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"Order placement error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return ExecutionResult(
                        success=False,
                        status='failed',
                        error=f"Order placement failed: {str(e)}"
                    )
                await asyncio.sleep(1)
        
        # Should never reach here
        return ExecutionResult(
            success=False,
            status='failed',
            error="Unexpected error in order placement"
        )
    
    async def _create_trade_record(
        self,
        request: ExecutionRequest,
        order_result: ExecutionResult,
        db_session: AsyncSession,
        proposal_id: int
    ) -> ExecutionResult:
        """Create trade record after successful order placement."""
        try:
            trade = PaperTrades(
                ts_open=datetime.utcnow().isoformat(),
                user_id=request.user_id,
                exchange=self.exchange_name,
                symbol=request.symbol,
                side=request.side.upper(),
                leverage=request.leverage,
                qty=request.quantity,
                entry_price=order_result.filled_price,
                exit_price=None,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                profit=None,
                profit_pct=None,
                status='open',
                trade_status='POSITION_OPEN',
                notes=f"Order ID: {order_result.order_id}, Fee: ${order_result.fee:.4f}",
                execution_mode=request.execution_mode
            )
            
            db_session.add(trade)
            await db_session.flush()  # Get ID, parent manages commit
            
            logger.info(f"Trade record created: {trade.id}")
            
            return ExecutionResult(
                success=True,
                trade_id=trade.id,
                status='trade_created'
            )
            
        except Exception as e:
            logger.error(f"Failed to create trade record: {e}")
            return ExecutionResult(
                success=False,
                status='failed',
                error=f"Trade record creation failed: {str(e)}"
            )
    
    async def _mark_proposal_failed(
        self,
        proposal_id: int,
        db_session: AsyncSession,
        error: str
    ):
        """Mark proposal as failed when order placement fails."""
        try:
            from sqlalchemy import select
            stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
            result = await db_session.execute(stmt)
            proposal = result.scalar_one_or_none()
            
            if proposal:
                proposal.status = 'failed'
                await db_session.flush()
                logger.info(f"Proposal {proposal_id} marked as failed")
                
        except Exception as e:
            logger.error(f"Failed to update proposal status: {e}")
    
    async def _publish_execution_event(
        self,
        order_result: ExecutionResult,
        trade_result: ExecutionResult
    ):
        """Publish execution event to event bus."""
        try:
            await event_bus.publish('TRADE_EXECUTED', {
                'order_id': order_result.order_id,
                'trade_id': trade_result.trade_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to publish execution event: {e}")
    
    async def _send_notification(
        self,
        order_result: ExecutionResult,
        trade_result: ExecutionResult
    ):
        """Send trade execution notification."""
        try:
            await self.notifier.send_trade_entry({
                'order_id': order_result.order_id,
                'trade_id': trade_result.trade_id,
                'filled_price': order_result.filled_price,
                'filled_quantity': order_result.filled_quantity,
                'fee': order_result.fee,
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
    
    async def close(self):
        """Close exchange connections."""
        await self.exchange_manager.close()
