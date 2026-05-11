"""
MEXC LIVE exchange implementation.
Uses real API keys and executes actual trades.
"""
from app.exchange.base_exchange import BaseExchange
from app.infra.mexc_client import MEXCClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class MEXCLiveExchange(BaseExchange):
    """
    MEXC LIVE exchange implementation.
    Uses real API keys and executes actual trades.
    """
    
    def __init__(self):
        self.client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        self._mode = 'LIVE'
    
    async def open_position(self, symbol, side, amount, leverage=1, 
                           stop_loss=None, take_profit=None):
        """Execute real market order on MEXC."""
        logger.info(f"🔴 LIVE ORDER: {side} {amount} {symbol} @{leverage}x")
        
        order = await self.client.create_market_order(
            symbol=symbol,
            side=side.lower(),
            amount=amount,
            leverage=leverage
        )
        
        # TODO: Place stop-loss and take-profit orders if provided
        
        return {
            'order_id': order['order_id'],
            'symbol': order['symbol'],
            'side': side,
            'filled_price': order.get('price'),
            'filled_amount': order.get('filled', amount),
            'fee': order.get('fee', {}),
            'timestamp': order['timestamp']
        }
    
    async def close_position(self, symbol, trade_id):
        """Close real position on MEXC."""
        logger.info(f"🔴 LIVE CLOSE: {symbol} (trade: {trade_id})")
        return await self.client.close_position(symbol)
    
    async def get_positions(self):
        """Fetch real open positions from MEXC."""
        return await self.client.fetch_open_positions()
    
    async def get_balance(self):
        """Fetch real account balance."""
        return await self.client.fetch_balance()
    
    async def get_ticker(self, symbol):
        """Fetch real-time ticker."""
        return await self.client.fetch_ticker(symbol)
    
    async def cancel_order(self, order_id, symbol):
        """Cancel real order."""
        return await self.client.cancel_order(order_id, symbol)
    
    @property
    def mode(self):
        return 'LIVE'
