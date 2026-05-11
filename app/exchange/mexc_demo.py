"""
MEXC DEMO/Paper trading exchange.
Simulates trades without real money.
Tracks virtual balance and positions.
"""
from app.exchange.base_exchange import BaseExchange
from app.infra.mexc_client import MEXCClient
from app.config import settings
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class MEXCDemoExchange(BaseExchange):
    """
    MEXC DEMO/Paper trading exchange.
    Simulates trades without real money.
    Tracks virtual balance and positions.
    """
    
    def __init__(self, testnet: bool = False):
        # Use testnet credentials if testnet mode is enabled
        # Testnet typically uses the same keys but connects to testnet endpoints
        self.testnet = testnet
        
        if testnet:
            # For MEXC testnet, use the same API keys but connect to testnet
            self.client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures',
                testnet=True
            )
        else:
            # Use paper trading credentials for local simulation
            self.client = MEXCClient(
                api_key=settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY,
                api_secret=settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET,
                market_type='futures'
            )
        
        self._mode = 'DEMO'
        self._virtual_balance = 1000.0  # Starting virtual balance (local sim only)
        self._demo_positions = {}  # {order_id: position_data} (local sim only)
    
    async def open_position(self, symbol, side, amount, leverage=1,
                           stop_loss=None, take_profit=None):
        """Simulate order execution with realistic fills."""
        logger.info(f"🟢 DEMO ORDER: {side} {amount} {symbol} @{leverage}x")
        
        # Get real market price for realistic simulation
        ticker = await self.client.fetch_ticker(symbol)
        entry_price = ticker['last_price']
        
        # Simulate slippage (0.01-0.05%)
        import random
        slippage = entry_price * random.uniform(0.0001, 0.0005)
        if side.upper() == 'BUY':
            filled_price = entry_price + slippage
        else:
            filled_price = entry_price - slippage
        
        # Calculate fee
        fee_rate = 0.0006  # 0.06% for futures
        fee_cost = (filled_price * amount) * fee_rate
        
        # Create simulated order
        order_id = f"demo_{uuid.uuid4().hex[:12]}"
        
        # Store position
        self._demo_positions[order_id] = {
            'symbol': symbol,
            'side': side.upper(),
            'size': amount,
            'entry_price': filled_price,
            'leverage': leverage,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'opened_at': datetime.utcnow().isoformat()
        }
        
        # Update virtual balance
        margin_required = (filled_price * amount) / leverage
        self._virtual_balance -= fee_cost
        
        return {
            'order_id': order_id,
            'symbol': symbol,
            'side': side.upper(),
            'filled_price': filled_price,
            'filled_amount': amount,
            'fee': {'cost': fee_cost, 'currency': 'USDT'},
            'timestamp': datetime.utcnow().isoformat(),
            'simulated': True
        }
    
    async def close_position(self, symbol, trade_id):
        """Simulate position closure."""
        logger.info(f"🟢 DEMO CLOSE: {symbol} (trade: {trade_id})")
        
        if trade_id not in self._demo_positions:
            raise ValueError(f"Demo position {trade_id} not found")
        
        position = self._demo_positions[trade_id]
        
        # Get current market price
        ticker = await self.client.fetch_ticker(symbol)
        exit_price = ticker['last_price']
        
        # Calculate P&L
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size']
        
        # Fee for closing
        fee_cost = (exit_price * position['size']) * 0.0006
        
        # Update virtual balance
        self._virtual_balance += pnl - fee_cost
        
        # Remove position
        del self._demo_positions[trade_id]
        
        return {
            'order_id': f"close_{trade_id}",
            'symbol': symbol,
            'exit_price': exit_price,
            'pnl': pnl,
            'fee': fee_cost,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_positions(self):
        """Get positions - from testnet API if testnet mode, otherwise simulated."""
        if self.testnet:
            # Fetch real positions from MEXC testnet
            return await self.client.fetch_open_positions()
        else:
            # Return simulated positions for local simulation
            positions = []
            for order_id, pos in self._demo_positions.items():
                ticker = await self.client.fetch_ticker(pos['symbol'])
                current_price = ticker['last_price']
                
                # Calculate unrealized P&L
                if pos['side'] == 'LONG':
                    unrealized_pnl = (current_price - pos['entry_price']) * pos['size']
                else:
                    unrealized_pnl = (pos['entry_price'] - current_price) * pos['size']
                
                positions.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': pos['size'],
                    'entry_price': pos['entry_price'],
                    'current_price': current_price,
                    'unrealized_pnl': unrealized_pnl,
                    'leverage': pos['leverage'],
                    'order_id': order_id
                })
            
            return positions
    
    async def get_balance(self):
        """Get balance - from testnet API if testnet mode, otherwise virtual."""
        if self.testnet:
            # Fetch real balance from MEXC testnet
            return await self.client.fetch_balance()
        else:
            # Return virtual balance for local simulation
            return {
                'total_usdt': self._virtual_balance,
                'free_usdt': self._virtual_balance,
                'used_usdt': 0,
                'balances': {'USDT': self._virtual_balance},
                'virtual': True
            }
    
    async def get_ticker(self, symbol):
        """Get real market ticker (for realistic simulation)."""
        return await self.client.fetch_ticker(symbol)
    
    async def cancel_order(self, order_id, symbol):
        """Cancel demo order."""
        if order_id in self._demo_positions:
            del self._demo_positions[order_id]
        return {'order_id': order_id, 'status': 'cancelled'}
    
    @property
    def mode(self):
        return 'DEMO'
