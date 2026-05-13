"""
Paper Trading Session Manager - Layer 4: Real API validation with safety guards.

Orchestrates complete paper trading sessions on demo/testnet accounts with:
- Hard-coded balance caps ($100/trade max)
- Daily loss limits (-5% max)
- Position size limits (1% of account)
- Rate limit handling with exponential backoff
- Latency benchmarking for order execution
- Slippage analysis and fill price validation

Safety First: NO LIVE FINANCIAL RISK - Uses demo/testnet accounts only.
"""
import time
import asyncio
import random
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN

from app.logging_config import get_logger
from app.config import settings
from app.database.models import PaperTrades
from app.database.connection import get_session
from sqlalchemy import select

logger = get_logger(__name__)


class SafetyGuardViolation(Exception):
    """Raised when a safety guard is violated."""
    pass


class PaperTradingSessionManager:
    """
    Manage paper trading sessions with comprehensive safety guards.
    
    Features:
    - Balance protection (hard caps on trade size, daily losses)
    - Rate limit management (exponential backoff)
    - Performance tracking (latency, slippage, win rate)
    - Automatic session pause on violations
    
    Usage:
        manager = PaperTradingSessionManager(exchange='binance', user_id='test_user')
        await manager.start_session()
        
        # Execute trades (automatically checked against safety limits)
        result = await manager.execute_paper_trade(proposal, exchange_client)
        
        # Monitor session
        metrics = manager.get_session_metrics()
    """
    
    def __init__(
        self,
        exchange: str = 'binance',
        user_id: str = 'default_user',
        starting_balance: float = 1000.0
    ):
        """
        Initialize paper trading session manager.
        
        Args:
            exchange: Exchange to use for paper trading ('binance', 'mexc', 'bybit')
            user_id: User identifier for tracking
            starting_balance: Virtual starting balance for P&L calculation
        """
        self.exchange = exchange
        self.user_id = user_id
        self.starting_balance = starting_balance
        
        # Safety limits (from config or defaults)
        self.max_trade_size = getattr(settings, 'PAPER_MAX_TRADE_SIZE', 100.0)
        self.daily_loss_limit_pct = getattr(settings, 'PAPER_DAILY_LOSS_LIMIT', -5.0)
        self.max_position_pct = getattr(settings, 'PAPER_MAX_POSITION_PCT', 1.0)
        self.max_leverage = getattr(settings, 'PAPER_MAX_LEVERAGE', 5)
        
        # Session state
        self.session_active = False
        self.session_start_time = None
        self.current_balance = starting_balance
        self.daily_pnl = 0.0
        self.daily_trades = []
        self.total_trades_executed = 0
        
        # Performance tracking
        self.latencies = []  # Order execution latencies (ms)
        self.slippages = []  # Fill price slippages (%)
        self.rate_limit_hits = 0
        
        logger.info(f"✅ PaperTradingSessionManager initialized")
        logger.info(f"   Exchange: {exchange}")
        logger.info(f"   Starting Balance: ${starting_balance:,.2f}")
        logger.info(f"   Max Trade Size: ${self.max_trade_size:.2f}")
        logger.info(f"   Daily Loss Limit: {self.daily_loss_limit_pct}%")
    
    async def start_session(self):
        """Start a new paper trading session."""
        if self.session_active:
            logger.warning("⚠️  Session already active")
            return
        
        self.session_active = True
        self.session_start_time = datetime.now(timezone.utc)
        self.current_balance = self.starting_balance
        self.daily_pnl = 0.0
        self.daily_trades = []
        self.latencies = []
        self.slippages = []
        
        logger.info(f"🟢 Paper trading session STARTED at {self.session_start_time.isoformat()}")
        logger.info(f"   Safety guards enabled:")
        logger.info(f"   • Max trade size: ${self.max_trade_size:.2f}")
        logger.info(f"   • Daily loss limit: {self.daily_loss_limit_pct}%")
        logger.info(f"   • Max position: {self.max_position_pct}% of balance")
    
    async def stop_session(self, reason: str = "Manual stop"):
        """Stop the current paper trading session."""
        if not self.session_active:
            logger.warning("⚠️  No active session to stop")
            return
        
        self.session_active = False
        session_duration = datetime.now(timezone.utc) - self.session_start_time if self.session_start_time else timedelta(0)
        
        logger.info(f"🔴 Paper trading session STOPPED")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   Duration: {session_duration}")
        logger.info(f"   Total trades: {self.total_trades_executed}")
        logger.info(f"   Final balance: ${self.current_balance:,.2f}")
        logger.info(f"   Daily P&L: ${self.daily_pnl:+,.2f} ({self._calculate_daily_pnl_pct():+.2f}%)")
    
    async def execute_paper_trade(
        self,
        proposal: Optional[Dict[str, Any]] = None,
        exchange_client: Any = None,
        db_session: Any = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        leverage: int = 1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        confidence: float = 0.85,
        strategy_name: str = 'test',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a paper trade with comprehensive safety checks.
        
        Supports TWO calling conventions:
        1. Proposal-based (production): execute_paper_trade(proposal, exchange_client)
        2. Keyword-based (testing): execute_paper_trade(symbol='XAUUSDT', side='BUY', ...)
        
        Args:
            proposal: Trade proposal dict from AI orchestrator (optional)
            exchange_client: Exchange client instance (demo/testnet mode)
            db_session: Optional database session for persistence
            symbol: Trading pair symbol (keyword mode)
            side: 'BUY' or 'SELL' (keyword mode)
            quantity: Order quantity (keyword mode)
            price: Entry/reference price (keyword mode)
            leverage: Leverage multiplier (default 1)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            confidence: Signal confidence (0-1)
            strategy_name: Strategy identifier
            **kwargs: Additional parameters
        
        Returns:
            Execution result with latency and slippage data
        
        Raises:
            SafetyGuardViolation: If any safety limit is exceeded
        """
        # Normalize inputs: support both proposal and keyword APIs
        if proposal is None:
            # Keyword-based API (used by tests)
            if not all([symbol, side, quantity]):
                raise ValueError("Must provide symbol, side, and quantity when not using proposal")
            
            proposal = {
                'symbol': symbol,
                'side': side,
                'entry_price': price or 2000.0,
                'quantity': quantity,
                'leverage': leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': confidence,
                'strategy_name': strategy_name
            }
        
        # Use provided exchange_client or create mock if None
        if exchange_client is None:
            # For testing without real exchange, use simulation
            return await self._execute_simulated_trade(
                proposal=proposal,
                db_session=db_session
            )
        
        # Production path: use real exchange client
        return await self._execute_real_trade(
            proposal=proposal,
            exchange_client=exchange_client,
            db_session=db_session
        )
    
    async def _execute_simulated_trade(
        self,
        proposal: Dict[str, Any],
        db_session: Any = None
    ) -> Dict[str, Any]:
        """
        Execute simulated trade for testing (no real exchange required).
        
        Args:
            proposal: Trade proposal
            db_session: Optional database session
            
        Returns:
            Simulated execution result
        """
        if not self.session_active:
            raise SafetyGuardViolation("No active paper trading session")
        
        # Extract parameters
        symbol = proposal.get('symbol', '')
        side = proposal.get('side', '').upper()
        entry_price = proposal.get('entry_price', 2000.0)
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        stop_loss = proposal.get('stop_loss')
        take_profit = proposal.get('take_profit')
        confidence = proposal.get('confidence', 0.5)
        strategy_name = proposal.get('strategy_name', 'unknown')
        
        # === SAFETY CHECKS ===
        position_value = quantity * entry_price
        if position_value > self.max_trade_size:
            raise SafetyGuardViolation(
                f"Trade size ${position_value:.2f} exceeds maximum ${self.max_trade_size:.2f}"
            )
        
        if leverage > self.max_leverage:
            raise SafetyGuardViolation(
                f"Leverage {leverage}x exceeds maximum {self.max_leverage}x"
            )
        
        max_position_value = self.current_balance * (self.max_position_pct / 100.0)
        if position_value > max_position_value:
            raise SafetyGuardViolation(
                f"Position value ${position_value:.2f} exceeds {self.max_position_pct}% of balance (${max_position_value:.2f})"
            )
        
        # === SAFETY CHECK 4: Check daily loss limit ===
        daily_pnl_pct = self._calculate_daily_pnl_pct()
        if daily_pnl_pct <= self.daily_loss_limit_pct:
            # Auto-pause session on daily loss limit violation
            logger.warning(f"⚠️  Daily loss limit reached: {daily_pnl_pct:.2f}% <= {self.daily_loss_limit_pct}%")
            await self.stop_session(reason=f"Daily loss limit exceeded ({daily_pnl_pct:.2f}%)")
            raise SafetyGuardViolation(
                f"Daily loss limit reached: {daily_pnl_pct:.2f}% <= {self.daily_loss_limit_pct}%"
            )
        
        # === SIMULATE EXECUTION ===
        start_time = time.time()
        
        try:
            # Simulate order execution with realistic spread/slippage
            execution_result = self._simulate_order_execution(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=entry_price
            )
            
            elapsed_ms = execution_result['latency_ms']
            self.latencies.append(elapsed_ms)
            
            fill_price = execution_result['fill_price']
            slippage_pct = abs(fill_price - entry_price) / entry_price * 100
            self.slippages.append(slippage_pct)
            
            # Update session state
            self.total_trades_executed += 1
            
            # Track trade in daily list
            trade_record = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': fill_price,
                'pnl': 0,  # Will be updated on close
                'status': 'open'
            }
            self.daily_trades.append(trade_record)
            
            # Persist to database if session provided
            if db_session:
                await self._persist_paper_trade(
                    db_session=db_session,
                    symbol=symbol,
                    side=side,
                    entry_price=fill_price,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_name=strategy_name,
                    confidence=confidence,
                    latency_ms=elapsed_ms,
                    slippage_pct=slippage_pct
                )
            
            logger.info(f"✅ Paper trade executed (simulated): {side} {quantity} {symbol} @ ${fill_price:.2f}")
            logger.info(f"   Latency: {elapsed_ms:.0f}ms, Slippage: {slippage_pct:.3f}%")
            
            return {
                'status': 'executed',
                'order_id': execution_result.get('order_id'),
                'fill_price': fill_price,
                'quantity': quantity,
                'execution_time_ms': elapsed_ms,
                'latency_ms': round(elapsed_ms, 2),
                'slippage_pct': round(slippage_pct, 4),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Simulated trade failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'latency_ms': round(elapsed_ms, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _execute_real_trade(
        self,
        proposal: Dict[str, Any],
        exchange_client: Any,
        db_session: Any = None
    ) -> Dict[str, Any]:
        """
        Execute real trade on demo/testnet exchange.
        
        Args:
            proposal: Trade proposal
            exchange_client: Real exchange client
            db_session: Optional database session
            
        Returns:
            Real execution result
        """
        if not self.session_active:
            raise SafetyGuardViolation("No active paper trading session")
        
        # Extract trade parameters
        symbol = proposal.get('symbol', '')
        side = proposal.get('side', '').upper()
        entry_price = proposal.get('entry_price', 0)
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        stop_loss = proposal.get('stop_loss')
        take_profit = proposal.get('take_profit')
        confidence = proposal.get('confidence', 0.5)
        strategy_name = proposal.get('strategy_name', 'unknown')
        
        # === SAFETY CHECK 1: Validate trade size ===
        position_value = quantity * entry_price
        if position_value > self.max_trade_size:
            raise SafetyGuardViolation(
                f"Trade size ${position_value:.2f} exceeds maximum ${self.max_trade_size:.2f}"
            )
        
        # === SAFETY CHECK 2: Validate leverage ===
        if leverage > self.max_leverage:
            raise SafetyGuardViolation(
                f"Leverage {leverage}x exceeds maximum {self.max_leverage}x"
            )
        
        # === SAFETY CHECK 3: Validate position size as % of balance ===
        max_position_value = self.current_balance * (self.max_position_pct / 100.0)
        if position_value > max_position_value:
            raise SafetyGuardViolation(
                f"Position value ${position_value:.2f} exceeds {self.max_position_pct}% of balance (${max_position_value:.2f})"
            )
        
        # === SAFETY CHECK 4: Check daily loss limit ===
        daily_pnl_pct = self._calculate_daily_pnl_pct()
        if daily_pnl_pct <= self.daily_loss_limit_pct:
            raise SafetyGuardViolation(
                f"Daily loss limit reached: {daily_pnl_pct:.2f}% <= {self.daily_loss_limit_pct}%"
            )
        
        # === EXECUTE TRADE WITH LATENCY TRACKING ===
        start_time = time.time()
        
        try:
            # Execute order on demo/testnet exchange
            order_result = await self._execute_with_retry(
                exchange_client=exchange_client,
                symbol=symbol,
                side=side,
                quantity=quantity,
                leverage=leverage
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            self.latencies.append(elapsed_ms)
            
            # Calculate slippage
            fill_price = order_result.get('price', entry_price)
            slippage_pct = abs(fill_price - entry_price) / entry_price * 100
            self.slippages.append(slippage_pct)
            
            # Update session state
            self.total_trades_executed += 1
            
            # Persist to database if session provided
            if db_session:
                await self._persist_paper_trade(
                    db_session=db_session,
                    symbol=symbol,
                    side=side,
                    entry_price=fill_price,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_name=strategy_name,
                    confidence=confidence,
                    latency_ms=elapsed_ms,
                    slippage_pct=slippage_pct
                )
            
            logger.info(f"✅ Paper trade executed: {side} {quantity} {symbol} @ ${fill_price:.2f}")
            logger.info(f"   Latency: {elapsed_ms:.0f}ms, Slippage: {slippage_pct:.3f}%")
            
            return {
                'status': 'executed',
                'order_id': order_result.get('order_id'),
                'fill_price': fill_price,
                'quantity': quantity,
                'latency_ms': round(elapsed_ms, 2),
                'slippage_pct': round(slippage_pct, 4),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Paper trade failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'latency_ms': round(elapsed_ms, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Extract trade parameters
        symbol = proposal.get('symbol', '')
        side = proposal.get('side', '').upper()
        entry_price = proposal.get('entry_price', 0)
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        stop_loss = proposal.get('stop_loss')
        take_profit = proposal.get('take_profit')
        confidence = proposal.get('confidence', 0.5)
        strategy_name = proposal.get('strategy_name', 'unknown')
        
        # === SAFETY CHECK 1: Validate trade size ===
        position_value = quantity * entry_price
        if position_value > self.max_trade_size:
            raise SafetyGuardViolation(
                f"Trade size ${position_value:.2f} exceeds maximum ${self.max_trade_size:.2f}"
            )
        
        # === SAFETY CHECK 2: Validate leverage ===
        if leverage > self.max_leverage:
            raise SafetyGuardViolation(
                f"Leverage {leverage}x exceeds maximum {self.max_leverage}x"
            )
        
        # === SAFETY CHECK 3: Validate position size as % of balance ===
        max_position_value = self.current_balance * (self.max_position_pct / 100.0)
        if position_value > max_position_value:
            raise SafetyGuardViolation(
                f"Position value ${position_value:.2f} exceeds {self.max_position_pct}% of balance (${max_position_value:.2f})"
            )
        
        # === SAFETY CHECK 4: Check daily loss limit ===
        daily_pnl_pct = self._calculate_daily_pnl_pct()
        if daily_pnl_pct <= self.daily_loss_limit_pct:
            raise SafetyGuardViolation(
                f"Daily loss limit reached: {daily_pnl_pct:.2f}% <= {self.daily_loss_limit_pct}%"
            )
        
        # === EXECUTE TRADE WITH LATENCY TRACKING ===
        start_time = time.time()
        
        try:
            # Execute order on demo/testnet exchange
            order_result = await self._execute_with_retry(
                exchange_client=exchange_client,
                symbol=symbol,
                side=side,
                quantity=quantity,
                leverage=leverage
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            self.latencies.append(elapsed_ms)
            
            # Calculate slippage
            fill_price = order_result.get('price', entry_price)
            slippage_pct = abs(fill_price - entry_price) / entry_price * 100
            self.slippages.append(slippage_pct)
            
            # Update session state
            self.total_trades_executed += 1
            
            # Persist to database if session provided
            if db_session:
                await self._persist_paper_trade(
                    db_session=db_session,
                    symbol=symbol,
                    side=side,
                    entry_price=fill_price,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_name=strategy_name,
                    confidence=confidence,
                    latency_ms=elapsed_ms,
                    slippage_pct=slippage_pct
                )
            
            logger.info(f"✅ Paper trade executed: {side} {quantity} {symbol} @ ${fill_price:.2f}")
            logger.info(f"   Latency: {elapsed_ms:.0f}ms, Slippage: {slippage_pct:.3f}%")
            
            return {
                'status': 'executed',
                'order_id': order_result.get('order_id'),
                'fill_price': fill_price,
                'quantity': quantity,
                'latency_ms': round(elapsed_ms, 2),
                'slippage_pct': round(slippage_pct, 4),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Paper trade failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'latency_ms': round(elapsed_ms, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _execute_with_retry(
        self,
        exchange_client: Any,
        symbol: str,
        side: str,
        quantity: float,
        leverage: int,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Execute order with exponential backoff retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Add realistic latency delay (50-1000ms random)
                delay_ms = random.uniform(50, 1000)
                await asyncio.sleep(delay_ms / 1000.0)
                
                # Execute market order on demo exchange
                if side in ['BUY', 'LONG']:
                    order = await exchange_client.create_market_order(
                        symbol=symbol,
                        side='buy',
                        amount=quantity,
                        leverage=leverage
                    )
                else:
                    order = await exchange_client.create_market_order(
                        symbol=symbol,
                        side='sell',
                        amount=quantity,
                        leverage=leverage
                    )
                
                return order
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️  Order attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.info(f"   Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
        
        # All retries exhausted
        self.rate_limit_hits += 1
        raise last_error
    
    async def _persist_paper_trade(
        self,
        db_session: Any,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        leverage: int,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        strategy_name: str,
        confidence: float,
        latency_ms: float,
        slippage_pct: float
    ):
        """Persist paper trade to database."""
        ts_open = datetime.utcnow().isoformat()
        
        paper_trade = PaperTrades(
            ts_open=ts_open,
            user_id=self.user_id,
            exchange=self.exchange,
            symbol=symbol,
            side=side,
            leverage=leverage,
            qty=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status='open',
            notes=f"Strategy: {strategy_name}, Confidence: {confidence:.2f}, "
                  f"Latency: {latency_ms:.0f}ms, Slippage: {slippage_pct:.3f}%"
        )
        
        db_session.add(paper_trade)
        await db_session.flush()
    
    def _calculate_daily_pnl_pct(self) -> float:
        """Calculate daily P&L as percentage of starting balance."""
        if self.starting_balance == 0:
            return 0.0
        return (self.daily_pnl / self.starting_balance) * 100.0
    
    def get_session_metrics(self) -> Dict[str, Any]:
        """Get comprehensive session performance metrics."""
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        avg_slippage = sum(self.slippages) / len(self.slippages) if self.slippages else 0
        
        p95_latency = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if self.latencies else 0
        max_latency = max(self.latencies) if self.latencies else 0
        
        # Calculate win rate from daily trades
        winning_trades = sum(1 for t in self.daily_trades if t.get('pnl', 0) > 0)
        total_closed = len([t for t in self.daily_trades if t.get('status') == 'closed'])
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0
        
        return {
            'session_active': self.session_active,
            'session_duration': str(datetime.now(timezone.utc) - self.session_start_time) if self.session_start_time else None,
            'total_trades': self.total_trades_executed,
            'current_balance': self.current_balance,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self._calculate_daily_pnl_pct(),
            'avg_latency_ms': round(avg_latency, 2),
            'p95_latency_ms': round(p95_latency, 2),
            'max_latency_ms': round(max_latency, 2),
            'avg_slippage_pct': round(avg_slippage, 4),
            'win_rate': round(win_rate, 2),
            'rate_limit_hits': self.rate_limit_hits,
            'safety_limits': {
                'max_trade_size': self.max_trade_size,
                'daily_loss_limit_pct': self.daily_loss_limit_pct,
                'max_position_pct': self.max_position_pct,
                'max_leverage': self.max_leverage
            }
        }
    
    def _simulate_order_execution(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Simulate order execution with realistic spread, slippage, and latency.
        
        This method is used for testing when no real exchange client is available.
        
        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Reference market price (optional)
            
        Returns:
            Simulated execution result with fill price and latency
        """
        import time
        start = time.time()
        
        # Use provided price or simulate market price
        market_price = price or 2000.0  # Default XAUUSDT price
        
        # Apply spread (0.02% typical)
        spread = market_price * 0.0002
        
        # Apply random slippage (0-0.05%)
        slippage = market_price * random.uniform(0.0, 0.0005)
        
        # Calculate fill price based on side
        if side.upper() in ['BUY', 'LONG']:
            fill_price = market_price + spread + slippage
        else:
            fill_price = market_price - spread - slippage
        
        # Simulate network latency (50-1000ms)
        latency_ms = int((time.time() - start) * 1000) + random.randint(50, 1000)
        
        return {
            'order_id': f'sim_{int(time.time() * 1000)}',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'fill_price': fill_price,
            'latency_ms': latency_ms,
            'status': 'FILLED'
        }
    
    def _load_session_from_db(self, db_session: Any = None) -> bool:
        """
        Load session state from database for recovery.
        
        Args:
            db_session: Database session (optional)
            
        Returns:
            True if session was loaded, False otherwise
        """
        try:
            if not db_session:
                logger.warning("⚠️  No database session provided for recovery")
                return False
            
            # Query for latest paper trade session
            from sqlalchemy import select
            stmt = select(PaperTrades).where(
                PaperTrades.user_id == self.user_id
            ).order_by(PaperTrades.ts_open.desc()).limit(1)
            
            result = db_session.execute(stmt).scalar_one_or_none()
            
            if result:
                # Restore session state from last trade
                self.current_balance = result.balance or self.starting_balance
                self.session_active = result.status != 'closed'
                logger.info(f"✅ Session recovered from database: balance=${self.current_balance:.2f}")
                return True
            else:
                logger.info("ℹ️  No previous session found in database")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to load session from database: {e}")
            return False
    
    def _apply_exponential_backoff(self, attempt: int = 0) -> float:
        """
        Calculate exponential backoff delay for retry logic.
        
        Args:
            attempt: Current retry attempt number (0-indexed)
            
        Returns:
            Delay in seconds (capped at 30s)
        """
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (cap)
        delay = min(2 ** attempt, 30)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, delay * 0.1)
        total_delay = delay + jitter
        
        logger.debug(f"⏱️  Backoff delay: {total_delay:.2f}s (attempt {attempt})")
        return total_delay
