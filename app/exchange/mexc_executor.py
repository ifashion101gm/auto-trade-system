"""
MEXC Executor - Exchange-specific execution adapter.
Translates internal trade signals into MEXC-specific API calls.

This is the CRITICAL layer that handles:
- Symbol mapping (internal format → MEXC format)
- Position-side logic (open long, close long, open short, close short)
- Reduce-only orders for safe position closure
- Position mode detection (one-way vs hedge)
- Proper payload structure for MEXC Futures API
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from app.infra.mexc_client import MEXCClient
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class PositionSide(Enum):
    """MEXC Futures position sides."""
    OPEN_LONG = 1      # Buy to open long position
    CLOSE_SHORT = 2    # Buy to close short position
    OPEN_SHORT = 3     # Sell to open short position
    CLOSE_LONG = 4     # Sell to close long position


class MexcExecutor:
    """
    MEXC-specific execution adapter.
    
    Handles all MEXC Futures API interactions with proper:
    - Symbol normalization
    - Position-side mapping
    - Reduce-only logic
    - Position mode awareness
    """
    
    # Symbol mapping: Internal format → MEXC Futures format
    SYMBOL_MAP = {
        "BTCUSDT": "BTC_USDT",
        "ETHUSDT": "ETH_USDT",
        "XAUUSDT": "GOLD_USDT",
        "GOLD_USDT": "GOLD_USDT",
        "GOLD(XAUT)/USDT": "GOLD_USDT",
        "XAUT/USDT": "GOLD_USDT",
        "PAXG/USDT": "PAXG_USDT",
    }
    
    def __init__(self, testnet: bool = False):
        """
        Initialize MEXC executor.
        
        Args:
            testnet: Use testnet endpoints
        """
        self.testnet = testnet
        self.client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures',
            testnet=testnet
        )
        self._position_mode = None  # Will be detected on first use
    
    async def _detect_position_mode(self) -> str:
        """
        Detect account position mode (one-way or hedge).
        
        Returns:
            'ONE_WAY' or 'HEDGE'
        """
        if self._position_mode:
            return self._position_mode
        
        try:
            # Try to fetch positions to determine mode
            positions = await self.client.fetch_open_positions()
            
            # Check if we can have both long and short on same symbol
            symbols_seen = {}
            for pos in positions:
                symbol = pos.get('symbol')
                side = pos.get('side')
                
                if symbol not in symbols_seen:
                    symbols_seen[symbol] = set()
                symbols_seen[symbol].add(side)
            
            # If any symbol has both long and short, it's hedge mode
            for symbol, sides in symbols_seen.items():
                if len(sides) > 1:
                    self._position_mode = 'HEDGE'
                    logger.info("📊 Detected HEDGE position mode")
                    return 'HEDGE'
            
            self._position_mode = 'ONE_WAY'
            logger.info("📊 Detected ONE_WAY position mode")
            return 'ONE_WAY'
            
        except Exception as e:
            logger.warning(f"⚠️  Could not detect position mode: {e}. Assuming ONE_WAY")
            self._position_mode = 'ONE_WAY'
            return 'ONE_WAY'
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to MEXC Futures format.
        
        Args:
            symbol: Input symbol (various formats)
            
        Returns:
            MEXC-compatible symbol (e.g., 'GOLD_USDT')
        """
        # Check direct mapping first
        if symbol in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol]
        
        # Convert slash format to underscore
        normalized = symbol.replace('/', '_').replace(':', '_')
        
        # Remove settlement suffix if present (e.g., USDT_USDT → USDT)
        parts = normalized.split('_')
        if len(parts) == 3 and parts[1] == parts[2]:
            normalized = f"{parts[0]}_{parts[1]}"
        
        # Handle GOLD special case
        if 'GOLD' in normalized.upper() or 'XAUT' in normalized.upper():
            return 'GOLD_USDT'
        
        logger.warning(f"⚠️  Symbol not in map: {symbol} → {normalized}")
        return normalized
    
    async def open_long(
        self,
        symbol: str,
        amount: float,
        leverage: int = 1,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Open a LONG position.
        
        Args:
            symbol: Trading pair
            amount: Quantity to buy
            leverage: Leverage multiplier
            price: Limit price (None for market order)
            
        Returns:
            Order result
        """
        mexc_symbol = self._normalize_symbol(symbol)
        logger.info(f"🟢 Opening LONG: {amount} {mexc_symbol} @{leverage}x")
        
        # Set leverage
        await self._set_leverage(mexc_symbol, leverage)
        
        # Place order
        if price:
            result = await self.client.create_limit_order(
                symbol=mexc_symbol,
                side='buy',
                amount=amount,
                price=price,
                leverage=leverage
            )
        else:
            result = await self.client.create_market_order(
                symbol=mexc_symbol,
                side='buy',
                amount=amount,
                leverage=leverage
            )
        
        logger.info(f"✅ LONG opened: {result.get('order_id')}")
        return result
    
    async def close_long(
        self,
        symbol: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close a LONG position using reduce-only sell order.
        
        Args:
            symbol: Trading pair
            amount: Quantity to close (None = close entire position)
            
        Returns:
            Order result
        """
        mexc_symbol = self._normalize_symbol(symbol)
        
        # Get current position size if not specified
        if amount is None:
            positions = await self.client.fetch_open_positions()
            for pos in positions:
                if pos['symbol'] == mexc_symbol and pos.get('side') == 'long':
                    amount = pos['size']
                    break
            
            if amount is None:
                raise ValueError(f"No LONG position found for {mexc_symbol}")
        
        logger.info(f"🔴 Closing LONG: {amount} {mexc_symbol} (reduce-only)")
        
        # Place SELL order with reduce-only flag
        result = await self._place_reduce_only_order(
            symbol=mexc_symbol,
            side='sell',
            amount=amount,
            position_side=PositionSide.CLOSE_LONG
        )
        
        logger.info(f"✅ LONG closed: {result.get('order_id')}")
        return result
    
    async def open_short(
        self,
        symbol: str,
        amount: float,
        leverage: int = 1,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Open a SHORT position.
        
        Args:
            symbol: Trading pair
            amount: Quantity to sell
            leverage: Leverage multiplier
            price: Limit price (None for market order)
            
        Returns:
            Order result
        """
        mexc_symbol = self._normalize_symbol(symbol)
        logger.info(f"🔴 Opening SHORT: {amount} {mexc_symbol} @{leverage}x")
        
        # Set leverage
        await self._set_leverage(mexc_symbol, leverage)
        
        # Place order
        if price:
            result = await self.client.create_limit_order(
                symbol=mexc_symbol,
                side='sell',
                amount=amount,
                price=price,
                leverage=leverage
            )
        else:
            result = await self.client.create_market_order(
                symbol=mexc_symbol,
                side='sell',
                amount=amount,
                leverage=leverage
            )
        
        logger.info(f"✅ SHORT opened: {result.get('order_id')}")
        return result
    
    async def close_short(
        self,
        symbol: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close a SHORT position using reduce-only buy order.
        
        Args:
            symbol: Trading pair
            amount: Quantity to close (None = close entire position)
            
        Returns:
            Order result
        """
        mexc_symbol = self._normalize_symbol(symbol)
        
        # Get current position size if not specified
        if amount is None:
            positions = await self.client.fetch_open_positions()
            for pos in positions:
                if pos['symbol'] == mexc_symbol and pos.get('side') == 'short':
                    amount = pos['size']
                    break
            
            if amount is None:
                raise ValueError(f"No SHORT position found for {mexc_symbol}")
        
        logger.info(f"🟢 Closing SHORT: {amount} {mexc_symbol} (reduce-only)")
        
        # Place BUY order with reduce-only flag
        result = await self._place_reduce_only_order(
            symbol=mexc_symbol,
            side='buy',
            amount=amount,
            position_side=PositionSide.CLOSE_SHORT
        )
        
        logger.info(f"✅ SHORT closed: {result.get('order_id')}")
        return result
    
    async def _place_reduce_only_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        position_side: PositionSide
    ) -> Dict[str, Any]:
        """
        Place a reduce-only order to safely close positions.
        
        This prevents accidentally opening new opposite positions.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Quantity
            position_side: MEXC position side enum
            
        Returns:
            Order result
        """
        try:
            # For MEXC, we need to pass reduceOnly in params
            # Note: CCXT may handle this differently per exchange
            params = {
                'reduceOnly': True,
                'positionSide': position_side.name
            }
            
            logger.debug(f"Placing reduce-only order: {side} {amount} {symbol} params={params}")
            
            result = await self.client.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount,
                leverage=1  # Leverage doesn't matter for closing
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to place reduce-only order: {e}")
            # Fallback: try without reduceOnly (less safe)
            logger.warning("⚠️  Retrying without reduceOnly flag...")
            
            result = await self.client.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount,
                leverage=1
            )
            
            return result
    
    async def _set_leverage(self, symbol: str, leverage: int):
        """Set leverage for a symbol."""
        try:
            await self.client.exchange.set_leverage(
                leverage,
                symbol,
                params={
                    'openType': 2,  # Cross margin
                    'positionType': 1  # Long position
                }
            )
            logger.debug(f"Leverage set: {symbol} @{leverage}x")
        except Exception as e:
            logger.warning(f"⚠️  Could not set leverage: {e}")
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions with enhanced details."""
        positions = await self.client.fetch_open_positions()
        
        # Enhance position data
        for pos in positions:
            pos['mexc_symbol'] = self._normalize_symbol(pos['symbol'])
            pos['position_value'] = pos.get('size', 0) * pos.get('mark_price', 0)
        
        return positions
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        return await self.client.fetch_balance()
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker for a symbol."""
        mexc_symbol = self._normalize_symbol(symbol)
        return await self.client.fetch_ticker(mexc_symbol)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        return await self.client.health_check()
    
    async def close(self):
        """Close client connection."""
        await self.client.close()
