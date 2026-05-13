"""
Trading Service - Orchestrates complete E2E trading cycle.
Ensures safe demo-mode operation with full lifecycle tracking.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.states import ExecutionState, is_valid_transition
from app.services.position_monitor import PositionMonitor
from app.risk.risk_engine import RiskEngine
from app.infra.exchange_manager import UnifiedExchangeManager
from app.events.event_bus import EventBus
from app.logging_config import get_logger

logger = get_logger(__name__)


class TradingService:
    """
    Orchestrates complete trading cycle with strict state management.
    
    Lifecycle:
    IDLE → FETCHING_DATA → ANALYZING → PROPOSING → VALIDATING → 
    EXECUTING → MONITORING → RECONCILING → IDLE
    """
    
    def __init__(
        self,
        exchange_manager: UnifiedExchangeManager,
        event_bus: EventBus,
        position_monitor: PositionMonitor,
        risk_engine: RiskEngine,
        db_session: AsyncSession
    ):
        self.exchange_manager = exchange_manager
        self.event_bus = event_bus
        self.position_monitor = position_monitor
        self.risk_engine = risk_engine
        self.db_session = db_session
        
        # State machine
        self.current_state = ExecutionState.IDLE
        self.state_history = []
        
    async def execute_trading_cycle(
        self,
        symbol: str = "BTC/USDT",
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Execute complete trading cycle with validation."""
        cycle_result = {
            'symbol': symbol,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'failed',
            'stages': {}
        }
        
        try:
            # Stage 1: Fetch market data
            await self._transition_to(ExecutionState.FETCHING_DATA)
            market_data = await self._fetch_market_data(symbol)
            cycle_result['stages']['data_fetch'] = {'success': True}
            
            # Stage 2: Analyze and generate proposal
            await self._transition_to(ExecutionState.ANALYZING)
            proposal = await self._analyze_and_propose(market_data, symbol)
            if not proposal:
                await self._transition_to(ExecutionState.IDLE)
                cycle_result['status'] = 'no_signal'
                return cycle_result
            
            cycle_result['stages']['analysis'] = {'success': True, 'proposal': proposal}
            
            # Stage 3: Validate proposal
            await self._transition_to(ExecutionState.VALIDATING)
            validation = await self._validate_proposal(proposal, user_id)
            if not validation.approved:
                await self._transition_to(ExecutionState.IDLE)
                cycle_result['status'] = 'rejected'
                cycle_result['rejection_reasons'] = validation.violations
                return cycle_result
            
            cycle_result['stages']['validation'] = {'success': True}
            
            # Stage 4: Execute trade
            await self._transition_to(ExecutionState.EXECUTING)
            trade_record = await self._execute_trade(proposal, user_id)
            cycle_result['stages']['execution'] = {
                'success': True,
                'trade_id': trade_record.id
            }
            
            # Stage 5: Start monitoring
            await self._transition_to(ExecutionState.MONITORING)
            await self.position_monitor.start_monitoring(
                trade_id=trade_record.id,
                symbol=symbol,
                side=proposal['side'],
                entry_price=proposal['entry_price'],
                quantity=proposal['quantity'],
                stop_loss=proposal.get('stop_loss'),
                take_profit=proposal.get('take_profit'),
                db_session=self.db_session
            )
            
            cycle_result['status'] = 'monitoring'
            logger.info(f"✅ Trading cycle completed for {symbol}")
            
        except Exception as e:
            logger.error(f"Trading cycle failed: {e}")
            await self._transition_to(ExecutionState.ERROR)
            cycle_result['error'] = str(e)
        
        return cycle_result
    
    async def _transition_to(self, new_state: ExecutionState):
        """Validate and execute state transition."""
        old_state = self.current_state
        
        if not is_valid_transition(old_state, new_state):
            raise ValueError(
                f"Invalid state transition: {old_state.value} → {new_state.value}"
            )
        
        self.current_state = new_state
        self.state_history.append({
            'from': old_state.value,
            'to': new_state.value,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.debug(f"State transition: {old_state.value} → {new_state.value}")
    
    async def _fetch_market_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch OHLCV and ticker data."""
        ticker = await self.exchange_manager.fetch_ticker(symbol)
        ohlcv = await self.exchange_manager.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        return {'ticker': ticker, 'ohlcv': ohlcv}
    
    async def _analyze_and_propose(
        self,
        market_data: Dict[str, Any],
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Generate trade proposal from market analysis."""
        # Integration point with strategy layer
        # For now, use simple heuristic or call strategy manager
        from app.strategy.strategy_manager import StrategyManager
        
        manager = StrategyManager()
        signals = await manager.generate_signals(market_data)
        
        if not signals:
            return None
        
        # Select highest confidence signal
        best_signal = max(signals, key=lambda s: s.confidence)
        
        return {
            'symbol': symbol,
            'side': best_signal.side,
            'entry_price': best_signal.entry_price,
            'quantity': best_signal.quantity,
            'stop_loss': best_signal.stop_loss,
            'take_profit': best_signal.take_profit,
            'leverage': best_signal.leverage,
            'confidence': best_signal.confidence,
            'strategy': best_signal.strategy_name
        }
    
    async def _validate_proposal(
        self,
        proposal: Dict[str, Any],
        user_id: str
    ):
        """Validate proposal against risk engine."""
        return await self.risk_engine.check_trade_approval(
            proposal=proposal,
            user_id=user_id
        )
    
    async def _execute_trade(
        self,
        proposal: Dict[str, Any],
        user_id: str
    ):
        """Execute trade and persist to database."""
        from app.database.models import PaperTrades
        
        trade = PaperTrades(
            user_id=user_id,
            symbol=proposal['symbol'],
            side=proposal['side'],
            entry_price=proposal['entry_price'],
            qty=proposal['quantity'],
            leverage=proposal.get('leverage', 1),
            stop_loss=proposal.get('stop_loss'),
            take_profit=proposal.get('take_profit'),
            status='open',
            ts_open=datetime.utcnow().isoformat(),
            strategy=proposal.get('strategy', 'unknown')
        )
        
        self.db_session.add(trade)
        await self.db_session.commit()
        await self.db_session.refresh(trade)
        
        logger.info(f"Trade executed: {trade.id} - {proposal['symbol']}")
        return trade
