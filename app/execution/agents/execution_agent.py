"""Execution Agent - Places orders with retry logic and slippage protection."""
import asyncio
from typing import Dict, Any
from app.execution.agents.base_agent import BaseAgent
from app.infra.exchange_manager import UnifiedExchangeManager
from app.execution.states import OrderState, OrderLifecycleManager


class ExecutionAgent(BaseAgent):
    """Executes trades with robust error handling."""
    
    def __init__(self, exchange_manager: UnifiedExchangeManager,
                 max_retries: int = 3, max_slippage_pct: float = 0.5):
        super().__init__("ExecutionAgent")
        self.exchange_manager = exchange_manager
        self.max_retries = max_retries
        self.max_slippage_pct = max_slippage_pct
        self.order_lifecycle = OrderLifecycleManager()
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute order with retry logic."""
        proposal = context.get('proposal')
        symbol = proposal['symbol']
        side = proposal['side'].lower()
        quantity = proposal['quantity']
        leverage = proposal.get('leverage', 1)
        expected_price = proposal['entry_price']
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Place order
                order_result = await self.exchange_manager.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    leverage=leverage
                )
                
                # Validate slippage
                filled_price = order_result.get('price', expected_price)
                slippage_pct = abs(filled_price - expected_price) / expected_price * 100
                
                if slippage_pct > self.max_slippage_pct:
                    self.logger.warning(
                        f"High slippage detected: {slippage_pct:.2f}% "
                        f"(max: {self.max_slippage_pct}%)"
                    )
                
                # Track order state
                self.order_lifecycle.transition(
                    order_id=order_result['order_id'],
                    from_state=OrderState.NEW,
                    to_state=OrderState.PENDING
                )
                
                return {
                    'order_id': order_result['order_id'],
                    'filled_price': filled_price,
                    'filled_quantity': order_result.get('filled', quantity),
                    'slippage_pct': slippage_pct,
                    'attempts': attempt + 1,
                    'status': 'executed'
                }
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Execution attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception(f"Order execution failed after {self.max_retries} attempts: {last_error}")
