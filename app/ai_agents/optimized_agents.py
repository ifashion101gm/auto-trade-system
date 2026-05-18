"""
Optimized Agents - Cost Reduction Implementation
Replaces LLM-based agents with deterministic code for maximum cost savings.

BIGGEST SAVINGS:
- MonitoringAgent: Pure metrics calculation (NO LLM)
- ExecutionAgent: Deterministic order execution (NO LLM)
- RiskManagerAgent: Formula-based risk management (NO LLM except complex cases)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class MonitoringAgent:
    """
    System monitoring using pure metrics - NO LLM NEEDED.
    
    Monitors:
    - CPU usage
    - Memory usage
    - API latency
    - Error rates
    - P&L tracking
    - Drawdown calculation
    """
    
    def __init__(self):
        self.metrics_history = []
        self.error_count = 0
        self.total_requests = 0
    
    def calculate_system_health(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate system health from raw metrics - DETERMINISTIC.
        
        Args:
            metrics: Raw system metrics
            
        Returns:
            Health assessment dictionary
        """
        cpu_usage = metrics.get('cpu', 0)
        memory_usage = metrics.get('memory', 0)
        latency_ms = metrics.get('latency', 0)
        error_rate = metrics.get('error_rate', 0)
        
        # Determine health status based on thresholds
        if cpu_usage > 90 or memory_usage > 90:
            health_status = 'critical'
        elif cpu_usage > 75 or memory_usage > 75 or latency_ms > 1000:
            health_status = 'warning'
        else:
            health_status = 'healthy'
        
        return {
            'status': health_status,
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'latency_ms': latency_ms,
            'error_rate': error_rate,
            'recommendation': self._get_health_recommendation(health_status),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_health_recommendation(self, status: str) -> str:
        """Get recommendation based on health status."""
        recommendations = {
            'healthy': 'System operating normally',
            'warning': 'Monitor closely, consider scaling',
            'critical': 'Immediate action required - scale or restart'
        }
        return recommendations.get(status, 'Unknown status')
    
    def track_pnl(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Track P&L from trade history - FORMULA BASED.
        
        Args:
            trades: List of completed trades
            
        Returns:
            P&L statistics
        """
        if not trades:
            return {
                'total_pnl': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
        
        # Calculate P&L metrics
        total_pnl = sum(trade.get('pnl', 0) for trade in trades)
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in trades:
            running_total += trade.get('pnl', 0)
            cumulative_pnl.append(running_total)
        
        peak = cumulative_pnl[0] if cumulative_pnl else 0
        max_dd = 0
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return {
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(win_rate, 4),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown': round(max_dd, 4),
            'num_trades': len(trades),
            'num_wins': len(winning_trades),
            'num_losses': len(losing_trades)
        }
    
    def record_error(self):
        """Record an error occurrence."""
        self.error_count += 1
        self.total_requests += 1
    
    def record_success(self):
        """Record a successful request."""
        self.total_requests += 1
    
    def get_error_rate(self) -> float:
        """Calculate current error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests


class ExecutionAgent:
    """
    Deterministic order execution - NO LLM NEEDED.
    
    Handles:
    - Spread checking
    - Slippage validation
    - Order placement
    - Retry logic
    - Cancel/replace
    """
    
    def __init__(self, max_slippage_pct: float = 0.01, max_retries: int = 3):
        self.max_slippage_pct = max_slippage_pct
        self.max_retries = max_retries
    
    async def execute_order(
        self,
        exchange_manager,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        leverage: int = 1,
        order_type: str = 'MARKET'
    ) -> Dict[str, Any]:
        """
        Execute order with deterministic checks - NO LLM.
        
        Args:
            exchange_manager: Exchange client
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            expected_price: Expected execution price
            leverage: Leverage multiplier
            order_type: MARKET or LIMIT
            
        Returns:
            Execution result
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Step 1: Check spread (for limit orders)
                if order_type == 'LIMIT':
                    spread_check = await self._check_spread(exchange_manager, symbol, expected_price)
                    if not spread_check['acceptable']:
                        return {
                            'success': False,
                            'error': f"Spread too wide: {spread_check['spread_pct']:.2%}",
                            'attempt': attempt
                        }
                
                # Step 2: Place order
                if order_type == 'MARKET':
                    order_result = await exchange_manager.create_market_order(
                        symbol=symbol,
                        side=side,
                        amount=quantity,
                        leverage=leverage
                    )
                else:
                    order_result = await exchange_manager.create_limit_order(
                        symbol=symbol,
                        side=side,
                        amount=quantity,
                        price=expected_price,
                        leverage=leverage
                    )
                
                # Step 3: Check slippage
                filled_price = order_result.get('price', expected_price)
                slippage = abs(filled_price - expected_price) / expected_price
                
                if slippage > self.max_slippage_pct:
                    # Slippage too high - cancel order
                    await self._cancel_order(exchange_manager, symbol, order_result.get('order_id'))
                    
                    return {
                        'success': False,
                        'error': f"Slippage too high: {slippage:.2%} (max: {self.max_slippage_pct:.2%})",
                        'slippage': slippage,
                        'attempt': attempt
                    }
                
                # Success!
                return {
                    'success': True,
                    'order_id': order_result.get('order_id'),
                    'filled_price': filled_price,
                    'slippage': slippage,
                    'attempt': attempt,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                last_error = str(e)
                print(f"⚠️  Execution attempt {attempt}/{self.max_retries} failed: {e}")
                
                if attempt < self.max_retries:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        # All retries exhausted
        return {
            'success': False,
            'error': f"All {self.max_retries} attempts failed. Last error: {last_error}",
            'attempt': self.max_retries
        }
    
    async def _check_spread(
        self,
        exchange_manager,
        symbol: str,
        expected_price: float
    ) -> Dict[str, Any]:
        """Check if spread is acceptable."""
        try:
            ticker = await exchange_manager.fetch_ticker(symbol)
            bid = ticker.get('bid', expected_price)
            ask = ticker.get('ask', expected_price)
            
            spread = ask - bid
            spread_pct = spread / expected_price
            
            # Acceptable spread threshold: 0.1%
            acceptable = spread_pct < 0.001
            
            return {
                'acceptable': acceptable,
                'spread': spread,
                'spread_pct': spread_pct,
                'bid': bid,
                'ask': ask
            }
        except Exception as e:
            print(f"⚠️  Spread check failed: {e}")
            return {'acceptable': True, 'spread_pct': 0}  # Allow to proceed
    
    async def _cancel_order(self, exchange_manager, symbol: str, order_id: str):
        """Cancel an order."""
        try:
            await exchange_manager.cancel_order(symbol, order_id)
        except Exception as e:
            print(f"⚠️  Failed to cancel order {order_id}: {e}")


class RiskManagerAgent:
    """
    Formula-based risk management - MINIMAL LLM USAGE.
    
    Uses formulas for:
    - Maximum risk percentage
    - Position sizing
    - Loss streak detection
    - Daily drawdown limits
    
    LLM only for complex portfolio interpretation.
    """
    
    def __init__(
        self,
        max_risk_per_trade_pct: float = 0.02,  # 2% max risk per trade
        max_daily_loss_pct: float = 0.05,      # 5% max daily loss
        max_position_size_usd: float = 1000,   # $1000 max position
        max_leverage: int = 5,                  # 5x max leverage
        loss_streak_limit: int = 3              # Stop after 3 consecutive losses
    ):
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_usd = max_position_size_usd
        self.max_leverage = max_leverage
        self.loss_streak_limit = loss_streak_limit
        
        # Tracking
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.trades_today = 0
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_per_trade_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate position size using risk formulas - NO LLM.
        
        Args:
            account_balance: Total account balance
            entry_price: Entry price
            stop_loss_price: Stop loss price
            risk_per_trade_pct: Risk percentage (default: class default)
            
        Returns:
            Position sizing details
        """
        risk_pct = risk_per_trade_pct or self.max_risk_per_trade_pct
        
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        if risk_per_unit == 0:
            return {
                'allowed': False,
                'reason': 'Stop loss equals entry price',
                'position_size': 0,
                'risk_amount': 0
            }
        
        # Calculate maximum risk amount
        max_risk_amount = account_balance * risk_pct
        
        # Calculate position size
        position_size = max_risk_amount / risk_per_unit
        
        # Calculate position value
        position_value = position_size * entry_price
        
        # Apply maximum position size limit
        if position_value > self.max_position_size_usd:
            position_size = self.max_position_size_usd / entry_price
            position_value = self.max_position_size_usd
        
        # Calculate leverage needed
        leverage_needed = position_value / account_balance if account_balance > 0 else 1
        leverage_capped = min(int(leverage_needed) + 1, self.max_leverage)
        
        return {
            'allowed': True,
            'position_size': round(position_size, 8),
            'position_value_usd': round(position_value, 2),
            'risk_amount_usd': round(max_risk_amount, 2),
            'risk_per_unit': round(risk_per_unit, 2),
            'leverage_recommended': leverage_capped,
            'stop_loss_distance_pct': round(risk_per_unit / entry_price, 4)
        }
    
    def check_trade_allowed(self, current_pnl: float) -> Dict[str, Any]:
        """
        Check if trading is allowed based on risk limits - FORMULA BASED.
        
        Args:
            current_pnl: Current day's P&L
            
        Returns:
            Permission decision with reasoning
        """
        # Check daily loss limit
        if current_pnl < -(self.max_daily_loss_pct * 10000):  # Assuming $10k base
            return {
                'allowed': False,
                'reason': f'Daily loss limit reached: {current_pnl:.2f}',
                'limit': self.max_daily_loss_pct
            }
        
        # Check loss streak
        if self.consecutive_losses >= self.loss_streak_limit:
            return {
                'allowed': False,
                'reason': f'Loss streak limit reached: {self.consecutive_losses} consecutive losses',
                'limit': self.loss_streak_limit
            }
        
        return {
            'allowed': True,
            'reason': 'Within risk limits',
            'daily_pnl': current_pnl,
            'consecutive_losses': self.consecutive_losses
        }
    
    def update_after_trade(self, pnl: float):
        """
        Update risk tracking after a trade completes.
        
        Args:
            pnl: Trade P&L
        """
        self.daily_pnl += pnl
        self.trades_today += 1
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0  # Reset on win
    
    def reset_daily_tracking(self):
        """Reset daily tracking at start of new day."""
        self.daily_pnl = 0
        self.trades_today = 0
        self.consecutive_losses = 0
    
    def assess_complex_portfolio(
        self,
        openrouter_client,
        portfolio_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM ONLY for complex portfolio interpretation.
        
        Args:
            openrouter_client: OpenRouter client instance
            portfolio_data: Complex portfolio state
            
        Returns:
            Portfolio assessment from LLM
        """
        # This is the ONLY place where LLM is used in RiskManager
        # Only call when portfolio complexity warrants it
        return openrouter_client.assess_risk(
            position=portfolio_data.get('proposed_position', {}),
            market_data=portfolio_data.get('market_context')
        )


# ============================================================================
# Stub Classes for Orchestrator Compatibility
# These are placeholder implementations to satisfy import requirements
# ============================================================================

class OptimizedAgentRouter:
    """
    Routes requests to appropriate agents based on task type.
    Stub implementation for compatibility.
    """
    
    def __init__(self):
        self.router_map = {}
    
    def route(self, task_type: str, data: Dict[str, Any]) -> Optional[Any]:
        """Route task to appropriate handler."""
        return None


class DeterministicRiskManager:
    """
    Deterministic risk management without LLM.
    Stub implementation for compatibility.
    """
    
    def __init__(self):
        pass
    
    def assess_trade(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Assess trade risk deterministically."""
        return {'approved': True, 'risk_score': 0.5}


class CodeBasedExecutionEngine:
    """
    Code-based execution engine (no LLM).
    Executes orders through exchange manager with retry logic.
    """
    
    def __init__(
        self,
        max_slippage_pct: float = 0.5,
        max_spread_pct: float = 0.1,
        max_retries: int = 3
    ):
        """
        Initialize execution engine.
        
        Args:
            max_slippage_pct: Maximum acceptable slippage percentage
            max_spread_pct: Maximum acceptable spread percentage
            max_retries: Maximum retry attempts for failed orders
        """
        self.max_slippage_pct = max_slippage_pct
        self.max_spread_pct = max_spread_pct
        self.max_retries = max_retries
    
    async def execute_with_retry(
        self,
        exchange_manager,
        symbol: str,
        side: str,
        quantity: float,
        leverage: int,
        expected_price: float
    ) -> Dict[str, Any]:
        """
        Execute order with retry logic.
        
        Args:
            exchange_manager: Exchange manager instance
            symbol: Trading symbol
            side: 'buy' or 'sell'
            quantity: Order quantity
            leverage: Leverage multiplier
            expected_price: Expected execution price
            
        Returns:
            Dictionary with execution result:
            {
                'success': bool,
                'order': dict (if successful),
                'reason': str (if failed),
                'retries_needed': int
            }
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"⚡ Executing {side.upper()} order for {symbol} (attempt {attempt}/{self.max_retries})")
                logger.debug(f"   Quantity: {quantity}, Leverage: {leverage}, Expected Price: {expected_price}")
                
                # Place market order through exchange manager
                order_result = await exchange_manager.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    leverage=leverage
                )
                
                logger.info(f"✅ Order executed successfully: {order_result.get('order_id')}")
                logger.debug(f"   Order details: {order_result}")
                
                return {
                    'success': True,
                    'order': order_result,
                    'retries_needed': attempt - 1
                }
                
            except KeyError as e:
                # Handle missing dictionary keys specifically
                last_error = e
                key_name = str(e).strip("'\"")
                logger.error(f"❌ KeyError on attempt {attempt}: Missing key '{key_name}'")
                logger.error(f"   This usually means the API response is missing expected field: {key_name}")
                
                if attempt < self.max_retries:
                    import asyncio
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.info(f"⏳ Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Order execution attempt {attempt} failed: {type(e).__name__}: {e}")
                
                if attempt < self.max_retries:
                    # Wait before retry with exponential backoff
                    import asyncio
                    delay = 1.0 * (2 ** (attempt - 1))  # 1s, 2s, 4s...
                    logger.info(f"⏳ Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(f"❌ Order execution failed after {self.max_retries} attempts")
        error_type = type(last_error).__name__ if last_error else "Unknown"
        error_msg = str(last_error) if last_error else "No error details"
        
        return {
            'success': False,
            'reason': f"{error_type}: {error_msg}",
            'retries_needed': self.max_retries
        }
    
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute order (legacy method)."""
        return {'status': 'executed'}


class CodeBasedMonitor:
    """
    Code-based monitoring system (no LLM).
    Stub implementation for compatibility.
    """
    
    def __init__(self):
        pass
    
    def check_health(self) -> Dict[str, Any]:
        """Check system health."""
        return {'status': 'healthy'}
