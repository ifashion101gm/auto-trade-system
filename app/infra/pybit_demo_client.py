"""
Bybit Demo Trading Client using official pybit SDK.
Connects to api-demo.bybit.com for virtual fund trading.

Key Differences from Testnet:
- Uses api-demo.bybit.com (not api-testnet.bybit.com)
- Requires demo_trading=True, testnet=False
- Supports same symbols as live trading
- Virtual funds, real market data
"""
import logging
from typing import Dict, Any, Optional, List
from pybit.unified_trading import HTTP
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class PybitDemoClient:
    """
    Bybit Demo Trading client using official pybit SDK.
    
    Features:
    - Connects to api-demo.bybit.com
    - Supports perpetual swaps (linear), spot, inverse, options
    - Real-time order placement and management
    - Position tracking and balance queries
    - Same symbol format as live trading (BTCUSDT, ETHUSDT, etc.)
    
    Usage:
        client = PybitDemoClient()
        balance = await client.fetch_balance()
        order = await client.create_market_order("BTCUSDT", "buy", 0.001)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        Initialize Bybit Demo Trading client.
        
        Args:
            api_key: Bybit Demo API key (generated from demo mode)
            api_secret: Bybit Demo API secret
        """
        # Use demo credentials from config
        self.api_key = api_key or settings.BYBIT_DEMO_API_KEY
        self.api_secret = api_secret or settings.BYBIT_DEMO_API_SECRET
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Demo API credentials required. Set BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET in .env"
            )
        
        # Initialize pybit HTTP session for Demo Trading
        # IMPORTANT: testnet=False, demo=True routes to api-demo.bybit.com
        self.session = HTTP(
            testnet=False,  # NOT testnet
            demo=True,      # Enable demo trading mode
            api_key=self.api_key,
            api_secret=self.api_secret,
            recv_window=settings.BYBIT_RECV_WINDOW,  # Use configurable recv_window
        )
        
        logger.info("✅ PybitDemoClient initialized")
        logger.info(f"   Mode: DEMO TRADING")
        logger.info(f"   Endpoint: https://api-demo.bybit.com")
        logger.info(f"   Category: linear (perpetual swaps)")
        logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch wallet balance from demo account.
        
        Returns:
            Dict with balance information including total_usdt
        """
        try:
            logger.info("Fetching demo account balance...")
            
            response = self.session.get_wallet_balance(
                accountType="UNIFIED"
            )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"❌ Balance fetch failed: {error_msg}")
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            # Parse balance from unified account
            result = response.get('result', {})
            list_data = result.get('list', [])
            
            if not list_data:
                logger.warning("No balance data returned")
                return {'total_usdt': 0.0, 'balances': []}
            
            account = list_data[0]
            coin_list = account.get('coin', [])
            
            # Find USDT balance
            usdt_balance = 0.0
            balances = []
            
            for coin_data in coin_list:
                coin_name = coin_data.get('coin', '')
                wallet_balance_str = coin_data.get('walletBalance', '0')
                available_balance_str = coin_data.get('availableToWithdraw', '0')
                
                # Handle empty strings
                wallet_balance = float(wallet_balance_str) if wallet_balance_str else 0.0
                available_balance = float(available_balance_str) if available_balance_str else 0.0
                
                balances.append({
                    'asset': coin_name,
                    'free': available_balance,
                    'locked': wallet_balance - available_balance,
                    'total': wallet_balance
                })
                
                if coin_name == 'USDT':
                    usdt_balance = wallet_balance
            
            logger.info(f"✅ Demo Balance: {usdt_balance:.2f} USDT")
            
            return {
                'total_usdt': usdt_balance,
                'balances': balances,
                'account_type': 'UNIFIED'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch demo balance: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker price for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT", "ETHUSDT", "XRPUSDT")
        
        Returns:
            Dict with ticker information including last_price
        """
        try:
            logger.info(f"Fetching ticker for {symbol}...")
            
            response = self.session.get_tickers(
                category="linear",  # Perpetual swaps
                symbol=symbol
            )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"❌ Ticker fetch failed: {error_msg}")
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            result = response.get('result', {})
            ticker_list = result.get('list', [])
            
            if not ticker_list:
                raise Exception(f"No ticker data for symbol: {symbol}")
            
            ticker_data = ticker_list[0]
            
            ticker_info = {
                'symbol': ticker_data.get('symbol'),
                'last_price': float(ticker_data.get('lastPrice', 0)),
                'bid_price': float(ticker_data.get('bid1Price', 0)),
                'ask_price': float(ticker_data.get('ask1Price', 0)),
                'volume_24h': float(ticker_data.get('volume24h', 0)),
                'high_24h': float(ticker_data.get('highPrice24h', 0)),
                'low_24h': float(ticker_data.get('lowPrice24h', 0)),
            }
            
            logger.info(f"✅ Ticker: {ticker_info['symbol']} @ ${ticker_info['last_price']:.4f}")
            
            return ticker_info
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch ticker: {e}")
            raise
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Place a market order on demo trading.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT", "ETHUSDT")
            side: 'buy' or 'sell'
            amount: Order quantity
            leverage: Leverage multiplier (default: 1)
        
        Returns:
            Dict with order information including order_id
        """
        try:
            logger.info(f"Placing demo market order: {side.upper()} {amount} {symbol}")
            
            # Fetch instrument info to get qtyStep (minimum increment)
            instrument_response = self.session.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            
            if instrument_response.get('retCode') != 0:
                raise Exception(f"Failed to get instrument info: {instrument_response.get('retMsg')}")
            
            result = instrument_response.get('result', {})
            instrument_list = result.get('list', [])
            
            if not instrument_list:
                raise Exception(f"No instrument info for {symbol}")
            
            instrument = instrument_list[0]
            qty_step = float(instrument.get('lotSizeFilter', {}).get('qtyStep', '0.01'))
            
            # Round amount to match qtyStep precision
            rounded_amount = round(amount / qty_step) * qty_step
            rounded_amount = round(rounded_amount, 8)  # Avoid floating point issues
            
            logger.info(f"   Original qty: {amount}, Rounded qty: {rounded_amount} (step: {qty_step})")
            
            # Set leverage first (only if needed)
            try:
                self.session.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(leverage),
                    sellLeverage=str(leverage)
                )
            except Exception as e:
                # Ignore "leverage not modified" errors
                if '110043' not in str(e):
                    raise
            
            # Place market order
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side.capitalize(),  # 'buy' -> 'Buy', 'sell' -> 'Sell'
                orderType="Market",
                qty=str(rounded_amount),  # Use rounded quantity
                positionIdx=0  # One-way mode
            )
            
            if response.get('retCode') != 0:
                ret_code = response.get('retCode')
                error_msg = response.get('retMsg', 'Unknown error')
                
                # Handle specific error codes
                if ret_code == 10024:
                    logger.error("❌ Error 10024: Regulatory restriction on demo account")
                    logger.error("   Possible causes:")
                    logger.error("   1. Account needs KYC verification")
                    logger.error("   2. Geographic restrictions")
                    logger.error("   3. Derivatives trading not enabled")
                    raise Exception(f"Regulatory restriction (10024): {error_msg}")
                
                elif ret_code == 10003:
                    logger.error("❌ Error 10003: Invalid API key")
                    logger.error("   Ensure you're using DEMO keys (not live/testnet)")
                    raise Exception(f"Invalid API key (10003): {error_msg}")
                
                else:
                    logger.error(f"❌ Order failed: {error_msg}")
                    raise Exception(f"Bybit Demo API Error ({ret_code}): {error_msg}")
            
            result = response.get('result', {})
            
            order_info = {
                'order_id': result.get('orderId'),
                'symbol': result.get('symbol'),
                'side': side,
                'type': 'market',
                'amount': amount,
                'status': result.get('orderStatus', 'New'),
                'created_time': result.get('createdTime'),
            }
            
            logger.info(f"✅ Demo order placed: {order_info['order_id']}")
            
            return order_info
            
        except Exception as e:
            logger.error(f"❌ Failed to place demo order: {e}")
            raise
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch order status.
        
        Args:
            order_id: Order ID to check
            symbol: Trading pair
        
        Returns:
            Dict with order status information
        """
        try:
            logger.info(f"Checking demo order status: {order_id}")
            
            response = self.session.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            result = response.get('result', {})
            order_list = result.get('list', [])
            
            if not order_list:
                raise Exception(f"Order not found: {order_id}")
            
            order_data = order_list[0]
            
            status_info = {
                'order_id': order_data.get('orderId'),
                'symbol': order_data.get('symbol'),
                'side': order_data.get('side').lower(),
                'type': order_data.get('orderType').lower(),
                'status': order_data.get('orderStatus'),
                'filled_qty': float(order_data.get('cumExecQty', 0)),
                'avg_price': float(order_data.get('avgPrice', 0)),
                'leaves_qty': float(order_data.get('leavesQty', 0)),
            }
            
            logger.info(f"✅ Order status: {status_info['status']}")
            
            return status_info
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch order status: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
        
        Returns:
            Dict with cancellation result
        """
        try:
            logger.info(f"Cancelling demo order: {order_id}")
            
            response = self.session.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            result = response.get('result', {})
            
            cancel_info = {
                'order_id': result.get('orderId'),
                'symbol': result.get('symbol'),
                'status': 'cancelled'
            }
            
            logger.info(f"✅ Demo order cancelled: {cancel_info['order_id']}")
            
            return cancel_info
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel order: {e}")
            raise
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an open position by placing opposite market order.
        
        Args:
            symbol: Trading pair
        
        Returns:
            Dict with close order information
        """
        try:
            logger.info(f"Closing demo position: {symbol}")
            
            # Get current position
            response = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            result = response.get('result', {})
            position_list = result.get('list', [])
            
            if not position_list:
                logger.info("No open position to close")
                return {'order_id': None, 'message': 'No position'}
            
            position_data = position_list[0]
            size = float(position_data.get('size', 0))
            side = position_data.get('side')
            
            if size == 0:
                logger.info("Position size is zero, nothing to close")
                return {'order_id': None, 'message': 'Zero position'}
            
            # Place opposite order to close
            close_side = 'Sell' if side == 'Buy' else 'Buy'
            
            close_response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True,
                positionIdx=0
            )
            
            if close_response.get('retCode') != 0:
                error_msg = close_response.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            close_result = close_response.get('result', {})
            
            logger.info(f"✅ Position closed: {close_result.get('orderId')}")
            
            return {
                'order_id': close_result.get('orderId'),
                'symbol': symbol,
                'side': close_side.lower(),
                'amount': size,
                'status': 'closed'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            raise
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get open positions.
        
        Args:
            symbol: Optional symbol filter (required by Bybit API)
        
        Returns:
            List of position dictionaries
        """
        try:
            logger.info("Fetching demo positions...")
            
            # Bybit requires either symbol or settleCoin parameter
            if symbol:
                response = self.session.get_positions(
                    category="linear",
                    symbol=symbol
                )
            else:
                # Use settleCoin=USDT to get all linear positions
                response = self.session.get_positions(
                    category="linear",
                    settleCoin="USDT"
                )
            
            if response.get('retCode') != 0:
                error_msg = response.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit Demo API Error: {error_msg}")
            
            result = response.get('result', {})
            position_list = result.get('list', [])
            
            positions = []
            for pos_data in position_list:
                size = float(pos_data.get('size', 0))
                if size > 0:  # Only include non-zero positions
                    positions.append({
                        'symbol': pos_data.get('symbol'),
                        'side': pos_data.get('side'),
                        'size': size,
                        'entry_price': float(pos_data.get('avgPrice', 0)),
                        'mark_price': float(pos_data.get('markPrice', 0)),
                        'unrealized_pnl': float(pos_data.get('unrealisedPnl', 0)),
                        'leverage': pos_data.get('leverage'),
                    })
            
            logger.info(f"✅ Found {len(positions)} open position(s)")
            
            return positions
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch positions: {e}")
            raise
    
    async def close(self):
        """Close the client session."""
        logger.info("Closing PybitDemoClient session...")
        # pybit HTTP session doesn't require explicit close
        logger.info("✅ Session closed")


# Helper function to match BaseExchange interface
async def create_demo_client() -> PybitDemoClient:
    """Create a PybitDemoClient instance."""
    return PybitDemoClient()
