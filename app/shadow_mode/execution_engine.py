"""
Shadow Mode Execution Engine - Layer 5: Live-data simulation without real orders.

Runs parallel to live market data, generating signals and simulating execution
to validate strategy accuracy before deploying live capital.

Features:
- Zero-risk validation (NO orders sent to exchanges)
- Divergence tracking (simulated vs actual market movements)
- Accuracy score calculation (direction prediction quality)
- Comprehensive performance metrics (win rate, Sharpe ratio, drawdown)
- Database persistence for all shadow trades

Architecture:
    Live WebSocket Feed → Signal Generation → Risk Check → Virtual Orders → Divergence Analysis
"""
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from collections import deque

from app.logging_config import get_logger
from app.config import settings
from app.database.models import ShadowTrades, ShadowPerformanceMetrics
from app.database.connection import get_session

logger = get_logger(__name__)


class ShadowTrade:
    """Represents a single shadow trade with simulated and actual tracking."""
    
    def __init__(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price_simulated: float,
        entry_price_actual: float,
        quantity: float,
        leverage: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_name: str = 'unknown',
        regime: str = 'unknown',
        confidence: float = 0.5,
        session: str = 'unknown'
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side  # 'LONG' or 'SHORT'
        self.entry_price_simulated = entry_price_simulated
        self.entry_price_actual = entry_price_actual
        self.slippage_applied = abs(entry_price_simulated - entry_price_actual) / entry_price_actual * 100
        self.quantity = quantity
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.strategy_name = strategy_name
        self.regime = regime
        self.confidence = confidence
        self.session = session
        
        # Exit tracking
        self.status = 'open'  # open, closed, tp_hit, sl_hit
        self.exit_price_simulated = None
        self.exit_price_actual = None
        self.exit_reason = None
        self.pnl_simulated = None
        self.pnl_actual = None
        self.divergence_pct = None
        self.accuracy_score = None
        
        # Timing
        self.opened_at = datetime.now(timezone.utc)
        self.closed_at = None
        self.duration_seconds = None
    
    def check_exit_conditions(self, current_price: float) -> Optional[str]:
        """
        Check if exit conditions are met (TP/SL hit).
        
        Args:
            current_price: Current market price
        
        Returns:
            Exit reason if triggered, None otherwise
        """
        if self.side == 'LONG':
            if self.take_profit and current_price >= self.take_profit:
                return 'TAKE_PROFIT'
            elif self.stop_loss and current_price <= self.stop_loss:
                return 'STOP_LOSS'
        else:  # SHORT
            if self.take_profit and current_price <= self.take_profit:
                return 'TAKE_PROFIT'
            elif self.stop_loss and current_price >= self.stop_loss:
                return 'STOP_LOSS'
        
        return None
    
    def close_trade(
        self,
        exit_price_simulated: float,
        exit_price_actual: float,
        exit_reason: str
    ):
        """Close the shadow trade and calculate P&L."""
        self.exit_price_simulated = exit_price_simulated
        self.exit_price_actual = exit_price_actual
        self.exit_reason = exit_reason
        self.closed_at = datetime.now(timezone.utc)
        self.duration_seconds = int((self.closed_at - self.opened_at).total_seconds())
        
        # Calculate simulated P&L
        if self.side == 'LONG':
            self.pnl_simulated = (exit_price_simulated - self.entry_price_simulated) * self.quantity * self.leverage
            self.pnl_actual = (exit_price_actual - self.entry_price_actual) * self.quantity * self.leverage
        else:  # SHORT
            self.pnl_simulated = (self.entry_price_simulated - exit_price_simulated) * self.quantity * self.leverage
            self.pnl_actual = (self.entry_price_actual - exit_price_actual) * self.quantity * self.leverage
        
        # Calculate divergence
        if self.pnl_actual != 0:
            self.divergence_pct = abs(self.pnl_simulated - self.pnl_actual) / abs(self.pnl_actual) * 100
        else:
            self.divergence_pct = 0.0
        
        # Calculate accuracy score (direction prediction)
        predicted_direction = 1 if self.pnl_simulated > 0 else -1
        actual_direction = 1 if self.pnl_actual > 0 else -1
        self.accuracy_score = 100.0 if predicted_direction == actual_direction else 0.0
        
        self.status = exit_reason
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database persistence."""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price_simulated': self.entry_price_simulated,
            'entry_price_actual': self.entry_price_actual,
            'slippage_applied': self.slippage_applied,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'status': self.status,
            'exit_price_simulated': self.exit_price_simulated,
            'exit_price_actual': self.exit_price_actual,
            'exit_reason': self.exit_reason,
            'pnl_simulated': self.pnl_simulated,
            'pnl_actual': self.pnl_actual,
            'divergence_pct': self.divergence_pct,
            'accuracy_score': self.accuracy_score,
            'strategy_name': self.strategy_name,
            'regime': self.regime,
            'confidence': self.confidence,
            'session': self.session,
            'opened_at': self.opened_at,
            'closed_at': self.closed_at,
            'duration_seconds': self.duration_seconds
        }


class ShadowExecutionEngine:
    """
    Execute shadow trades against live market data without placing real orders.
    
    Features:
    - Simulates order fills with realistic slippage
    - Tracks divergence between simulated and actual outcomes
    - Calculates accuracy scores for direction predictions
    - Persists all shadow trades to database
    - Provides comprehensive performance metrics
    
    Usage:
        engine = ShadowExecutionEngine(user_id='test_user', exchange='binance')
        await engine.start()
        
        # Process market data and generate shadow trades
        await engine.process_signal(signal_proposal, current_market_data)
        
        # Update open positions with latest prices
        await engine.update_positions(live_prices)
        
        # Get performance metrics
        metrics = engine.get_performance_metrics()
    """
    
    def __init__(
        self,
        user_id: str = 'default_user',
        exchange: str = 'binance',
        slippage_model: str = 'fixed_pct',
        slippage_pct: float = 0.001  # 0.1% default
    ):
        """
        Initialize shadow execution engine.
        
        Args:
            user_id: User identifier for tracking
            exchange: Primary exchange being shadowed
            slippage_model: Slippage calculation model ('fixed_pct' or 'volatility_based')
            slippage_pct: Fixed slippage percentage (if using fixed_pct model)
        """
        self.user_id = user_id
        self.exchange = exchange
        self.slippage_model = slippage_model
        self.slippage_pct = slippage_pct
        
        # Active shadow positions
        self.open_positions: Dict[str, ShadowTrade] = {}
        self.closed_trades: List[ShadowTrade] = []
        
        # Performance tracking
        self.total_signals = 0
        self.trades_executed = 0
        
        logger.info(f"✅ ShadowExecutionEngine initialized")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Exchange: {exchange}")
        logger.info(f"   Slippage Model: {slippage_model} ({slippage_pct*100:.2f}%)")
    
    async def start(self):
        """Start the shadow execution engine."""
        logger.info(f"🟢 Shadow mode STARTED - NO REAL ORDERS WILL BE SENT")
    
    async def stop(self):
        """Stop the shadow execution engine."""
        logger.info(f"🔴 Shadow mode STOPPED")
        logger.info(f"   Total signals processed: {self.total_signals}")
        logger.info(f"   Trades executed: {self.trades_executed}")
        logger.info(f"   Open positions: {len(self.open_positions)}")
    
    async def process_signal(
        self,
        signal: Dict[str, Any],
        market_data: Dict[str, Any],
        db_session: Any = None
    ) -> Optional[ShadowTrade]:
        """
        Process a trading signal and create a shadow trade.
        
        Args:
            signal: Signal proposal from AI orchestrator
            market_data: Current market data snapshot
            db_session: Optional database session for persistence
        
        Returns:
            Created shadow trade, or None if signal rejected
        """
        self.total_signals += 1
        
        # Extract signal parameters
        symbol = signal.get('symbol', '')
        side = signal.get('side', '').upper()
        entry_price_actual = market_data.get('current_price', 0)
        quantity = signal.get('quantity', 0)
        leverage = signal.get('leverage', 1)
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        strategy_name = signal.get('strategy_name', 'unknown')
        regime = signal.get('regime', 'unknown')
        confidence = signal.get('confidence', 0.5)
        session = signal.get('session', 'unknown')
        
        # Apply slippage model to simulate fill price
        entry_price_simulated = self._apply_slippage(entry_price_actual, side)
        
        # Create shadow trade
        trade_id = str(uuid.uuid4())
        shadow_trade = ShadowTrade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            entry_price_simulated=entry_price_simulated,
            entry_price_actual=entry_price_actual,
            quantity=quantity,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy_name,
            regime=regime,
            confidence=confidence,
            session=session
        )
        
        # Track position
        self.open_positions[trade_id] = shadow_trade
        self.trades_executed += 1
        
        # Persist to database
        if db_session:
            await self._persist_shadow_trade(db_session, shadow_trade)
        
        logger.info(f"👻 Shadow trade created: {side} {quantity} {symbol}")
        logger.info(f"   Simulated fill: ${entry_price_simulated:.2f}, Actual: ${entry_price_actual:.2f}")
        logger.info(f"   Slippage: {shadow_trade.slippage_applied:.3f}%")
        
        return shadow_trade
    
    def _apply_slippage(self, market_price: float, side: str) -> float:
        """
        Apply slippage model to simulate realistic fill prices.
        
        Args:
            market_price: Current market price
            side: Trade side ('LONG' or 'SHORT')
        
        Returns:
            Simulated fill price with slippage
        """
        if self.slippage_model == 'fixed_pct':
            slippage = market_price * self.slippage_pct
        elif self.slippage_model == 'volatility_based':
            # Simplified volatility-based slippage (would use ATR in production)
            slippage = market_price * (self.slippage_pct * 1.5)
        else:
            slippage = market_price * self.slippage_pct
        
        # Longs buy at ask (higher), shorts sell at bid (lower)
        if side == 'LONG':
            return market_price + slippage
        else:  # SHORT
            return market_price - slippage
    
    async def update_positions(
        self,
        live_prices: Dict[str, float],
        db_session: Any = None
    ) -> List[ShadowTrade]:
        """
        Update all open shadow positions with latest live prices.
        Checks for TP/SL triggers and closes trades accordingly.
        
        Args:
            live_prices: Dictionary of {symbol: current_price}
            db_session: Optional database session for persistence
        
        Returns:
            List of trades that were closed
        """
        closed_trades = []
        
        for trade_id, trade in list(self.open_positions.items()):
            current_price = live_prices.get(trade.symbol)
            if not current_price:
                continue
            
            # Check exit conditions
            exit_reason = trade.check_exit_conditions(current_price)
            
            if exit_reason:
                # Close the trade
                trade.close_trade(
                    exit_price_simulated=current_price,
                    exit_price_actual=current_price,
                    exit_reason=exit_reason
                )
                
                # Move from open to closed
                self.open_positions.pop(trade_id)
                self.closed_trades.append(trade)
                closed_trades.append(trade)
                
                # Update database
                if db_session:
                    await self._update_shadow_trade_in_db(db_session, trade)
                
                logger.info(f"🎯 Shadow trade closed: {trade.trade_id[:8]}...")
                logger.info(f"   Reason: {exit_reason}")
                logger.info(f"   Simulated P&L: ${trade.pnl_simulated:+,.2f}")
                logger.info(f"   Actual P&L: ${trade.pnl_actual:+,.2f}")
                logger.info(f"   Divergence: {trade.divergence_pct:.2f}%")
        
        return closed_trades
    
    async def _persist_shadow_trade(self, db_session: Any, trade: ShadowTrade):
        """Persist new shadow trade to database."""
        shadow_record = ShadowTrades(
            id=trade.trade_id,
            user_id=self.user_id,
            exchange=self.exchange,
            symbol=trade.symbol,
            side=trade.side,
            status=trade.status,
            entry_price_simulated=trade.entry_price_simulated,
            entry_price_actual=trade.entry_price_actual,
            slippage_applied=trade.slippage_applied,
            quantity=trade.quantity,
            leverage=trade.leverage,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            strategy_name=trade.strategy_name,
            regime=trade.regime,
            confidence=trade.confidence,
            session=trade.session,
            opened_at=trade.opened_at
        )
        
        db_session.add(shadow_record)
        await db_session.flush()
    
    async def _update_shadow_trade_in_db(self, db_session: Any, trade: ShadowTrade):
        """Update existing shadow trade in database with exit details."""
        from sqlalchemy import select
        
        stmt = select(ShadowTrades).where(ShadowTrades.id == trade.trade_id)
        result = await db_session.execute(stmt)
        shadow_record = result.scalar_one_or_none()
        
        if shadow_record:
            shadow_record.status = trade.status
            shadow_record.exit_price_simulated = trade.exit_price_simulated
            shadow_record.exit_price_actual = trade.exit_price_actual
            shadow_record.exit_reason = trade.exit_reason
            shadow_record.pnl_simulated = trade.pnl_simulated
            shadow_record.pnl_actual = trade.pnl_actual
            shadow_record.divergence_pct = trade.divergence_pct
            shadow_record.accuracy_score = trade.accuracy_score
            shadow_record.closed_at = trade.closed_at
            shadow_record.duration_seconds = trade.duration_seconds
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive shadow mode performance metrics."""
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'message': 'No closed trades yet'
            }
        
        # Basic statistics
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.pnl_simulated > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl_simulated < 0]
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = sum(t.pnl_simulated for t in self.closed_trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # Accuracy metrics
        accuracy_scores = [t.accuracy_score for t in self.closed_trades if t.accuracy_score is not None]
        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
        
        divergences = [t.divergence_pct for t in self.closed_trades if t.divergence_pct is not None]
        avg_divergence = sum(divergences) / len(divergences) if divergences else 0
        
        # Risk metrics
        pnls = [t.pnl_simulated for t in self.closed_trades]
        max_drawdown = self._calculate_max_drawdown(pnls)
        
        # Sharpe ratio (simplified)
        import statistics
        if len(pnls) > 1 and statistics.stdev(pnls) > 0:
            sharpe_ratio = statistics.mean(pnls) / statistics.stdev(pnls)
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl_per_trade': round(avg_pnl, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'avg_accuracy_score': round(avg_accuracy, 2),
            'avg_divergence_pct': round(avg_divergence, 2),
            'open_positions': len(self.open_positions),
            'total_signals_processed': self.total_signals,
            'execution_rate': round(self.trades_executed / self.total_signals * 100, 2) if self.total_signals > 0 else 0
        }
    
    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Calculate maximum drawdown from P&L series."""
        if not pnls:
            return 0.0
        
        cumulative = []
        running_sum = 0
        for pnl in pnls:
            running_sum += pnl
            cumulative.append(running_sum)
        
        peak = cumulative[0]
        max_dd = 0
        
        for value in cumulative:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100 if peak != 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def get_validation_status(self) -> Dict[str, Any]:
        """Check if shadow mode meets go-live validation criteria."""
        metrics = self.get_performance_metrics()
        
        # Validation criteria
        min_trades = getattr(settings, 'SHADOW_MIN_TRADES', 100)
        min_win_rate = 55.0
        min_sharpe = 1.5
        max_drawdown = 10.0
        min_accuracy = getattr(settings, 'SHADOW_MIN_ACCURACY_SCORE', 90.0)
        
        checks = {
            'min_trades_met': metrics.get('total_trades', 0) >= min_trades,
            'win_rate_acceptable': metrics.get('win_rate', 0) >= min_win_rate,
            'sharpe_ratio_acceptable': metrics.get('sharpe_ratio', 0) >= min_sharpe,
            'drawdown_acceptable': metrics.get('max_drawdown_pct', 100) <= max_drawdown,
            'accuracy_acceptable': metrics.get('avg_accuracy_score', 0) >= min_accuracy
        }
        
        all_passed = all(checks.values())
        
        return {
            'validation_passed': all_passed,
            'checks': checks,
            'metrics': metrics,
            'recommendation': 'READY FOR LIVE' if all_passed else 'CONTINUE SHADOW TESTING'
        }
