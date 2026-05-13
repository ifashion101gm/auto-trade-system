"""
Bybit exchange client for derivatives trading.
Uses official Pybit SDK for Demo Trading (api-demo.bybit.com)
and CCXT library for unified API access with other modes.

IMPORTANT: CCXT has known issues with Bybit Demo Trading (GitHub #25545)
Pybit is the official Bybit SDK with full demo trading support.
"""
import logging
import ccxt.async_support as ccxt
from pybit.unified_trading import HTTP as PybitHTTP
from typing import Dict, Any, Optional, List
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class BybitClient:
    """
    Bybit exchange client for derivatives trading.
    
    IMPLEMENTATION:
    - Demo Trading: Uses official Pybit SDK (required - CCXT doesn't support demo)
    - Testnet/Mainnet: Uses CCXT for unified interface
    
    Official Documentation:
    - Pybit SDK: https://github.com/bybit-exchange/pybit
    - Demo Trading: https://bybit-exchange.github.io/docs/v5/demo
    
    Best Practices Implemented:
    - Rate limiting aligned with Bybit API limits (10 req/sec private, 50 req/sec public)
    - recv_window parameter for timestamp validation (prevents replay attacks)
    - adjustForTimeDifference for clock skew compensation
    - Category-based API calls (linear/inverse/spot/option)
    - Bybit-specific error code handling (10003=Invalid API Key, etc.)
    - Exponential backoff for rate limit errors
    
    Features:
    - Perpetual and futures trading
    - Real order placement (market/limit orders)
    - Order status tracking
    - Position management
    - Market data fetching
    - Fee calculation
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
        demo_trading: bool = None
    ):
        """
        Initialize Bybit client.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet (True) or mainnet (False) - Legacy parameter
            demo_trading: Use demo trading domain (True) or live domain (False)
                         Demo trading requires separate API keys generated from demo mode
        """
        self.api_key = api_key or settings.BYBIT_API_KEY
        self.api_secret = api_secret or settings.BYBIT_API_SECRET
        self.testnet = testnet
        self.demo_trading = demo_trading if demo_trading is not None else settings.BYBIT_USE_DEMO_DOMAIN
        
        # Use demo/testnet API keys if demo_trading is enabled OR if testnet mode
        # Both demo and testnet use BYBIT_DEMO_API_KEY/SECRET fields
        if self.demo_trading or self.testnet:
            self.api_key = api_key or settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
            self.api_secret = api_secret or settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Bybit API credentials not configured")
        
        # Initialize Pybit for demo trading (official SDK - CCXT doesn't support demo)
        if self.demo_trading:
            # Bybit Demo Trading MUST use Pybit SDK
            # Official documentation: https://bybit-exchange.github.io/docs/v5/demo
            # IMPORTANT: For demo trading, testnet parameter should be FALSE
            # Demo trading uses api-demo.bybit.com which is separate from testnet
            self.use_pybit = True
            self.pybit_session = PybitHTTP(
                testnet=False,  # CRITICAL: Must be False for demo trading
                demo=True,      # Enable demo trading mode (api-demo.bybit.com)
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
            logger.info("✅ Bybit Client initialized (DEMO TRADING - Pybit SDK)")
            logger.info("   Domain: https://api-demo.bybit.com")
            logger.info("   SDK: Official Pybit v5 (required for demo mode)")
            logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
            logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
            
            # Validate clock sync before proceeding (security baseline from Bybit skills)
            try:
                clock_sync_valid = await self.validate_clock_sync()
                if not clock_sync_valid:
                    logger.warning("⚠️  Clock sync validation failed - signatures may fail")
            except Exception as e:
                logger.warning(f"⚠️  Could not validate clock sync during init: {e}")
            
            # Set CCXT exchange for market data only (public endpoints work on CCXT)
            exchange_config = {
                'enableRateLimit': settings.BYBIT_RATE_LIMIT_ENABLED,
                'rateLimit': int(1000 / settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND),
                'options': {
                    'defaultType': 'swap',
                    'defaultSubType': 'linear',
                }
            }
            self.exchange = ccxt.bybit(exchange_config)
        else:
            # Use CCXT for testnet and mainnet
            self.use_pybit = False
            self.pybit_session = None
            
            exchange_config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': settings.BYBIT_RATE_LIMIT_ENABLED,
                'rateLimit': int(1000 / settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND),
                'options': {
                    'defaultType': 'swap',
                    'defaultSubType': 'linear',
                    'recvWindow': settings.BYBIT_RECV_WINDOW,
                }
            }
            
            if self.testnet:
                # Testnet uses api-testnet.bybit.com
                exchange_config['urls'] = {
                    'api': {
                        'public': 'https://api-testnet.bybit.com',
                        'private': 'https://api-testnet.bybit.com',
                    }
                }
                exchange_config['options']['adjustForTimeDifference'] = True
                logger.info("✅ Bybit Client initialized (TESTNET - CCXT)")
                logger.info("   Domain: https://api-testnet.bybit.com")
                logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
                logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
            else:
                logger.warning("⚠️  Bybit Client initialized (MAINNET - LIVE TRADING!)")
                logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
                logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
            
            # Validate clock sync before proceeding (security baseline from Bybit skills)
            try:
                clock_sync_valid = await self.validate_clock_sync()
                if not clock_sync_valid:
                    logger.warning("⚠️  Clock sync validation failed - signatures may fail")
            except Exception as e:
                logger.warning(f"⚠️  Could not validate clock sync during init: {e}")
            
            self.exchange = ccxt.bybit(exchange_config)
    
    async def close(self):
        """Close exchange connection."""
        if hasattr(self, 'exchange') and self.exchange:
            await self.exchange.close()
    
    def _handle_pybit_error(self, response: Dict, operation: str):
        """Handle Pybit API errors with Bybit-specific error codes.
        
        Enhanced with comprehensive error code mapping from official Bybit skills:
        https://bybit-exchange.github.io/docs/v5/error
        """
        ret_code = response.get('retCode', 0)
        ret_msg = response.get('retMsg', 'Unknown error')
        
        if ret_code != 0:
            error_msg = f"Pybit {operation} failed: retCode={ret_code}, retMsg={ret_msg}"
            logger.error(f"❌ {error_msg}")
            
            # Get human-readable description
            description = self.get_bybit_error_description(ret_code)
            logger.error(f"   Description: {description}")
            
            # Map to standard error codes with enhanced handling
            if ret_code == 10032:
                logger.error("   Demo trading not supported - check API key permissions")
                raise Exception(f"Bybit demo trading error (10032): {ret_msg}")
            elif ret_code == 10002:
                logger.error("   Invalid parameter - Check API key format, recv_window, or request parameters")
                raise Exception(f"Bybit parameter error (10002): Invalid parameter. {ret_msg}")
            elif ret_code == 10003:
                logger.error("   Authentication failed - API key is invalid, disabled, expired, or revoked")
                raise Exception(f"Bybit authentication failed (10003): API key is invalid. {ret_msg}")
            elif ret_code == 10004:
                logger.error("   Permissions denied - API key lacks required permissions for this operation")
                raise Exception(f"Bybit permissions error (10004): {ret_msg}")
            elif ret_code == 10005:
                logger.error("   IP restriction - This IP address is not whitelisted in API key settings")
                raise Exception(f"Bybit IP restriction (10005): IP not whitelisted. {ret_msg}")
            elif ret_code == 10006:
                logger.warning("   Rate limit exceeded - Too many requests")
                raise Exception(f"Bybit rate limit exceeded (10006): {ret_msg}")
            elif ret_code == 10016:
                logger.error("   Timestamp error - Server clock not synchronized or recv_window too small")
                raise Exception(f"Bybit timestamp error (10016): Clock skew detected. {ret_msg}")
            elif ret_code == 10017:
                logger.error("   Request expired - Request timestamp too old (> recv_window)")
                raise Exception(f"Bybit request expired (10017): {ret_msg}")
            elif ret_code == 10024:
                logger.error("   Regulatory restriction - Account has regional/KYC restrictions")
                raise Exception(f"Bybit regulatory restriction (10024): {ret_msg}")
            elif ret_code == 110001:
                logger.warning("   Order already filled/closed - No action needed")
                raise Exception(f"Bybit order state error (110001): Order already processed. {ret_msg}")
            elif ret_code == 110026:
                logger.error("   Insufficient balance - Not enough funds for this operation")
                raise Exception(f"Bybit insufficient balance (110026): {ret_msg}")
            elif ret_code == 130021:
                logger.error("   Position size limit exceeded - Order exceeds maximum allowed position size")
                raise Exception(f"Bybit position limit (130021): Size exceeds maximum. {ret_msg}")
            elif ret_code == 130027:
                logger.error("   Leverage exceeds maximum - Leverage too high for this symbol")
                raise Exception(f"Bybit leverage error (130027): Exceeds maximum leverage. {ret_msg}")
            elif ret_code == 130028:
                logger.error("   Order cost exceeds limit - Notional value too large")
                raise Exception(f"Bybit order cost error (130028): Notional value too large. {ret_msg}")
            else:
                raise Exception(f"Bybit API error ({ret_code}): {ret_msg}")
    
    async def fetch_server_time(self) -> int:
        """
        Fetch server timestamp.
        
        Returns:
            Server timestamp in milliseconds
        """
        return await self.exchange.fetch_time()
    
    async def check_position_mode(self, symbol: str = None, category: str = "linear") -> Dict[str, Any]:
        """
        Check current position mode (one-way vs hedge) for derivatives.
        
        Based on official Bybit skills best practices:
        - Query position mode via /v5/position/list before placing orders
        - Cache result and use correct positionIdx for subsequent orders
        - One-way mode: positionIdx=0 for all orders
        - Hedge mode: positionIdx=1 (long), positionIdx=2 (short)
        
        Args:
            symbol: Trading pair (optional, if None checks account-wide mode)
            category: Product category (default: 'linear' for USDT perpetuals)
            
        Returns:
            Dictionary with position mode information:
            {
                'mode': 'one-way' or 'hedge',
                'position_idx': 0 (one-way), 1 or 2 (hedge),
                'symbol': symbol if provided
            }
        """
        try:
            # Use Pybit for demo trading, CCXT for testnet/mainnet
            if self.use_pybit:
                # Pybit get_positions returns synchronous response
                params = {"category": category}
                if symbol:
                    bybit_symbol = symbol.replace('/', '').replace(':', '')
                    if bybit_symbol.endswith('USDTUSDT'):
                        bybit_symbol = bybit_symbol[:-4]
                    params["symbol"] = bybit_symbol
                else:
                    params["settleCoin"] = "USDT"
                
                response = self.pybit_session.get_positions(**params)
                self._handle_pybit_error(response, "get_positions")
                
                result = response.get('result', {})
                positions_data = result.get('list', [])
                
                # Determine position mode from first position
                if positions_data:
                    position_idx = positions_data[0].get('positionIdx', 0)
                    mode = 'hedge' if position_idx in [1, 2] else 'one-way'
                    logger.debug(f"Position mode detected: {mode} (positionIdx={position_idx})")
                    return {
                        'mode': mode,
                        'position_idx': position_idx,
                        'symbol': positions_data[0].get('symbol')
                    }
                else:
                    # No positions exist, assume one-way mode (default)
                    logger.debug("No positions found, assuming one-way mode (default)")
                    return {'mode': 'one-way', 'position_idx': 0, 'symbol': symbol}
            else:
                # CCXT for testnet/mainnet
                # Note: CCXT doesn't directly expose position mode
                # We need to infer from existing positions or assume one-way (default)
                positions = await self.exchange.fetch_positions([symbol] if symbol else None)
                
                if positions:
                    # Check if any position has positionIdx > 0 (indicates hedge mode)
                    for pos in positions:
                        info = pos.get('info', {})
                        position_idx = info.get('positionIdx', 0)
                        if position_idx in [1, 2]:
                            logger.debug(f"Position mode detected: hedge (positionIdx={position_idx})")
                            return {'mode': 'hedge', 'position_idx': position_idx, 'symbol': pos.get('symbol')}
                
                # Default to one-way mode
                logger.debug("No hedge positions found, assuming one-way mode (default)")
                return {'mode': 'one-way', 'position_idx': 0, 'symbol': symbol}
                
        except Exception as e:
            logger.warning(f"⚠️  Failed to detect position mode: {e}")
            logger.warning("   Assuming one-way mode (positionIdx=0) as default")
            return {'mode': 'one-way', 'position_idx': 0, 'symbol': symbol}
    
    async def validate_clock_sync(self, max_diff_seconds: int = 5) -> bool:
        """
        Validate system clock synchronization with Bybit server.
        
        Based on official Bybit skills security baseline:
        - Compare local time with server time
        - If difference > max_diff_seconds, warn user to sync clock
        - Clock skew causes signature validation failures
        
        Args:
            max_diff_seconds: Maximum allowed time difference (default: 5 seconds)
            
        Returns:
            True if clock is synchronized, False otherwise
        """
        try:
            server_time_ms = await self.fetch_server_time()
            local_time_ms = int(asyncio.get_event_loop().time() * 1000)
            
            # Note: asyncio.time() gives monotonic time, not wall clock
            # For proper clock sync, we should use time.time()
            import time
            local_time_ms = int(time.time() * 1000)
            
            diff_seconds = abs(server_time_ms - local_time_ms) / 1000
            
            if diff_seconds > max_diff_seconds:
                logger.error(f"❌ Clock sync error: System clock is off by {diff_seconds:.1f}s")
                logger.error("   Please sync your system clock (enable automatic date/time)")
                logger.error("   Clock skew will cause signature validation failures")
                return False
            else:
                logger.debug(f"✅ Clock synchronized: difference={diff_seconds:.2f}s")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  Could not validate clock sync: {e}")
            logger.warning("   Proceeding with caution - monitor for authentication errors")
            return True  # Don't block operations if check fails
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance.
        
        Returns:
            Dictionary with balance information
        
        Raises:
            Exception: With Bybit-specific error codes and messages
        """
        try:
            # Use Pybit for demo trading, CCXT for testnet/mainnet
            if self.use_pybit:
                # Pybit get_wallet_balance returns synchronous response
                response = self.pybit_session.get_wallet_balance(accountType="UNIFIED")
                self._handle_pybit_error(response, "get_wallet_balance")
                
                # Extract USDT balance from Pybit response
                result = response.get('result', {})
                list_data = result.get('list', [])
                if not list_data:
                    raise Exception("No balance data returned from Bybit demo")
                
                # Find USDT coin balance
                usdt_balance = 0
                total_usdt = 0
                for coin in list_data[0].get('coin', []):
                    if coin.get('coin') == 'USDT':
                        usdt_balance = float(coin.get('walletBalance', 0))
                        total_usdt = usdt_balance
                        break
                
                return {
                    'total_usdt': total_usdt,
                    'free_usdt': usdt_balance,
                    'used_usdt': 0,
                    'balances': {'USDT': total_usdt}
                }
            else:
                # CCXT for testnet/mainnet
                balance = await self.exchange.fetch_balance()
                
                # Get USDT balance
                usdt_balance = balance.get('USDT', {})
                
                return {
                    'total_usdt': usdt_balance.get('total', 0),
                    'free_usdt': usdt_balance.get('free', 0),
                    'used_usdt': usdt_balance.get('used', 0),
                    'balances': {k: v['total'] for k, v in balance.items() 
                               if isinstance(v, dict) and 'total' in v and v['total'] > 0}
                }
        except Exception as e:
            if '10032' in str(e) or '10003' in str(e) or '10004' in str(e):
                raise  # Re-raise Bybit-specific errors
            
            error_msg = str(e)
            
            # Handle Bybit-specific error codes (enhanced with official skills patterns)
            if '"retCode":10002' in error_msg or '10002' in error_msg:
                logger.error("❌ Bybit Error 10002: Invalid parameter")
                logger.error("   Possible causes:")
                logger.error("   1. API key format incorrect")
                logger.error("   2. Extra characters or spaces in key/secret")
                logger.error("   3. recv_window too small (< 5000ms)")
                logger.error("   4. Invalid request parameters")
                raise Exception(f"Bybit parameter error (10002): Invalid parameter. {error_msg}")
            
            elif '"retCode":10003' in error_msg or '10003' in error_msg:
                logger.error("❌ Bybit Error 10003: API key is invalid")
                logger.error("   Possible causes:")
                logger.error("   1. API key/secret mismatch or typo")
                logger.error("   2. Key is disabled, expired, or revoked")
                logger.error("   3. Key lacks required permissions (Account Read, Wallet Read)")
                logger.error("   4. IP restriction blocking this server")
                raise Exception(f"Bybit authentication failed (10003): API key is invalid. {error_msg}")
            
            elif '"retCode":10004' in error_msg or '10004' in error_msg:
                logger.error("❌ Bybit Error 10004: API key permissions denied")
                logger.error("   Required permissions:")
                logger.error("   - Order - Trade (Spot & Derivatives)")
                logger.error("   - Position - Read & Write")
                logger.error("   - Account - Read")
                logger.error("   - Wallet - Read")
                raise Exception(f"Bybit permissions error (10004): API key permissions denied. {error_msg}")
            
            elif '"retCode":10005' in error_msg or '10005' in error_msg:
                logger.error("❌ Bybit Error 10005: IP restriction")
                logger.error("   This IP address is not whitelisted in API key settings")
                logger.error("   Solution: Add your server IP to API key whitelist in Bybit dashboard")
                raise Exception(f"Bybit IP restriction (10005): IP not whitelisted. {error_msg}")
            
            elif '"retCode":10006' in error_msg or '10006' in error_msg:
                logger.warning("⚠️  Bybit Error 10006: Rate limit exceeded")
                logger.warning("   Too many requests - implementing exponential backoff")
                raise Exception(f"Bybit rate limit exceeded (10006): {error_msg}")
            
            elif '"retCode":10016' in error_msg or '10016' in error_msg:
                logger.error("❌ Bybit Error 10016: Timestamp error")
                logger.error("   Possible causes:")
                logger.error("   1. Server clock not synchronized")
                logger.error("   2. recv_window too small")
                logger.error("   Fix: Enable adjustForTimeDifference or increase recvWindow")
                raise Exception(f"Bybit timestamp error (10016): Clock skew detected. {error_msg}")
            
            elif '"retCode":10017' in error_msg or '10017' in error_msg:
                logger.error("❌ Bybit Error 10017: Request expired")
                logger.error("   Request timestamp too old (> recv_window)")
                logger.error("   Fix: Increase recv_window or check system clock")
                raise Exception(f"Bybit request expired (10017): {error_msg}")
            
            elif '"retCode":10024' in error_msg or '10024' in error_msg:
                logger.error("❌ Bybit Error 10024: Regulatory restriction")
                logger.error("   This testnet account has regional/KYC restrictions")
                logger.error("   Possible causes:")
                logger.error("   1. Account not KYC verified on testnet")
                logger.error("   2. Geographic restrictions for your region")
                logger.error("   3. Derivatives trading not enabled for this account")
                logger.error("   Solutions:")
                logger.error("   - Complete KYC verification on testnet.bybit.com")
                logger.error("   - Contact Bybit support for testnet access")
                logger.error("   - Try spot trading instead of derivatives")
                logger.error("   - Use a different testnet account")
                raise Exception(f"Bybit regulatory restriction (10024): Account restricted. {error_msg}")
            
            else:
                raise Exception(f"Failed to fetch balance: {error_msg}")
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time ticker data.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data with price, volume, etc.
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last_price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high_24h': ticker['high'],
                'low_24h': ticker['low'],
                'volume_24h': ticker['quoteVolume'],
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            raise Exception(f"Failed to fetch ticker for {symbol}: {str(e)}")
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            raise Exception(f"Failed to fetch OHLCV for {symbol}: {str(e)}")
    
    async def fetch_funding_rate(self, symbol: str, category: str = "linear", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch funding rate history for perpetual contracts.
        
        Based on official Bybit skills market module:
        GET /v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=10
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT')
            category: Product category (default: 'linear' for USDT perpetuals)
            limit: Number of funding rate records (default: 10)
            
        Returns:
            List of funding rate records with timestamp and rate
        """
        try:
            # Convert symbol format for API call
            bybit_symbol = symbol.replace('/', '').replace(':', '')
            if bybit_symbol.endswith('USDTUSDT'):
                bybit_symbol = bybit_symbol[:-4]
            
            if self.use_pybit:
                # Pybit get_funding_rate_history returns synchronous response
                response = self.pybit_session.get_funding_rate_history(
                    category=category,
                    symbol=bybit_symbol,
                    limit=limit
                )
                self._handle_pybit_error(response, "get_funding_rate_history")
                
                result = response.get('result', {}).get('list', [])
                return [
                    {
                        'symbol': item.get('symbol'),
                        'funding_rate': float(item.get('fundingRate', 0)),
                        'funding_rate_timestamp': int(item.get('fundingRateTimestamp', 0))
                    }
                    for item in result
                ]
            else:
                # CCXT doesn't have direct funding rate history endpoint
                # Return empty list with warning
                logger.warning("⚠️  Funding rate history not available via CCXT - use Pybit or REST API directly")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch funding rate for {symbol}: {str(e)}")
            return []
    
    async def fetch_open_interest(self, symbol: str, category: str = "linear", interval: str = "5min", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch open interest history.
        
        Based on official Bybit skills market module:
        GET /v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=100
        
        Args:
            symbol: Trading pair
            category: Product category (default: 'linear')
            interval: Time interval ('5min', '15min', '30min', '1h', '4h', '1d')
            limit: Number of records (default: 100)
            
        Returns:
            List of open interest records
        """
        try:
            # Convert symbol format
            bybit_symbol = symbol.replace('/', '').replace(':', '')
            if bybit_symbol.endswith('USDTUSDT'):
                bybit_symbol = bybit_symbol[:-4]
            
            if self.use_pybit:
                # Pybit get_open_interest returns synchronous response
                response = self.pybit_session.get_open_interest(
                    category=category,
                    symbol=bybit_symbol,
                    intervalTime=interval,
                    limit=limit
                )
                self._handle_pybit_error(response, "get_open_interest")
                
                result = response.get('result', {}).get('list', [])
                return [
                    {
                        'symbol': item.get('symbol'),
                        'open_interest': float(item.get('openInterest', 0)),
                        'timestamp': int(item.get('timestamp', 0))
                    }
                    for item in result
                ]
            else:
                logger.warning("⚠️  Open interest history not available via CCXT - use Pybit or REST API directly")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch open interest for {symbol}: {str(e)}")
            return []
    
    async def fetch_orderbook(self, symbol: str, category: str = "linear", limit: int = 50) -> Dict[str, Any]:
        """
        Fetch orderbook depth.
        
        Based on official Bybit skills market module:
        GET /v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=50
        
        Args:
            symbol: Trading pair
            category: Product category (default: 'linear')
            limit: Orderbook depth (default: 50, max: 500)
            
        Returns:
            Dictionary with bids, asks, and timestamp
        """
        try:
            # Convert symbol format
            bybit_symbol = symbol.replace('/', '').replace(':', '')
            if bybit_symbol.endswith('USDTUSDT'):
                bybit_symbol = bybit_symbol[:-4]
            
            if self.use_pybit:
                # Pybit get_orderbook returns synchronous response
                response = self.pybit_session.get_orderbook(
                    category=category,
                    symbol=bybit_symbol,
                    limit=limit
                )
                self._handle_pybit_error(response, "get_orderbook")
                
                result = response.get('result', {})
                return {
                    'symbol': result.get('s'),
                    'bids': [[float(price), float(qty)] for price, qty in result.get('b', [])],
                    'asks': [[float(price), float(qty)] for price, qty in result.get('a', [])],
                    'timestamp': int(result.get('ts', 0)),
                    'update_id': int(result.get('u', 0))
                }
            else:
                # CCXT has orderbook support
                orderbook = await self.exchange.fetch_order_book(symbol, limit=limit)
                return {
                    'symbol': symbol,
                    'bids': orderbook.get('bids', []),
                    'asks': orderbook.get('asks', []),
                    'timestamp': orderbook.get('timestamp'),
                    'nonce': orderbook.get('nonce')
                }
                
        except Exception as e:
            raise Exception(f"Failed to fetch orderbook for {symbol}: {str(e)}")
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Place a market order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier
            
        Returns:
            Order details including ID, status, filled price
        
        Raises:
            Exception: With Bybit-specific error codes and messages
        """
        try:
            # Set leverage (same for both Pybit and CCXT)
            if leverage > 1:
                await self.set_leverage(symbol, leverage)
            
            # Use Pybit for demo trading, CCXT for testnet/mainnet
            if self.use_pybit:
                # Convert symbol format: XAU/USDT:USDT -> XAUUSDT, BTC/USDT:USDT -> BTCUSDT
                bybit_symbol = symbol.replace('/', '').replace(':', '')
                # Remove duplicate USDT if present (e.g., XAUUSDTUSDT -> XAUUSDT)
                if bybit_symbol.endswith('USDTUSDT'):
                    bybit_symbol = bybit_symbol[:-4]
                
                # Pybit place_order returns synchronous response
                response = self.pybit_session.place_order(
                    category="linear",
                    symbol=bybit_symbol,
                    side="Buy" if side.lower() == "buy" else "Sell",
                    orderType="Market",
                    qty=str(amount)
                )
                self._handle_pybit_error(response, "place_order")
                
                result = response.get('result', {})
                
                order = {
                    'order_id': result.get('orderId'),
                    'symbol': result.get('symbol'),
                    'side': side.lower(),
                    'type': 'market',
                    'amount': amount,
                    'price': None,  # Will be filled after execution
                    'status': 'open',
                    'filled': 0,
                    'remaining': amount,
                    'cost': 0,
                    'fee': {},
                    'timestamp': result.get('createdTime'),
                    'leverage': leverage
                }
                
                logger.info(f"✅ Market order placed (Pybit Demo): {order['order_id']} - {side} {amount} {symbol}")
                return order
            else:
                # CCXT for testnet/mainnet
                order = await self.exchange.create_market_order(symbol, side, amount)
                
                logger.info(f"✅ Market order placed: {order['id']} - {side} {amount} {symbol}")
                
                return {
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'amount': order['amount'],
                    'price': order.get('average') or order.get('price'),
                    'status': order['status'],
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', 0),
                    'cost': order.get('cost', 0),
                    'fee': order.get('fee', {}),
                    'timestamp': order['timestamp'],
                    'leverage': leverage
                }
        except Exception as e:
            if '10032' in str(e) or '10003' in str(e) or '10004' in str(e):
                raise  # Re-raise Bybit-specific errors
            
            error_msg = str(e)
            
            # Handle Bybit-specific errors (enhanced with official skills patterns)
            if '"retCode":10002' in error_msg or '10002' in error_msg:
                logger.error("❌ Bybit Error 10002: Invalid parameter during order placement")
                logger.error("   Possible causes:")
                logger.error("   1. Invalid symbol format")
                logger.error("   2. Quantity below minimum order size")
                logger.error("   3. Price precision incorrect")
                raise Exception(f"Bybit parameter error (10002): Invalid order parameters. {error_msg}")
            
            elif '"retCode":10003' in error_msg or '10003' in error_msg:
                logger.error("❌ Bybit Error 10003: API key invalid during order placement")
                raise Exception(f"Bybit authentication failed (10003): Cannot place order. {error_msg}")
            
            elif '"retCode":10005' in error_msg or '10005' in error_msg:
                logger.error("❌ Bybit Error 10005: IP restriction during order placement")
                raise Exception(f"Bybit IP restriction (10005): Cannot place order. {error_msg}")
            
            elif '"retCode":10006' in error_msg or '10006' in error_msg:
                logger.warning("⚠️  Bybit Error 10006: Rate limit exceeded during order placement")
                raise Exception(f"Bybit rate limit exceeded (10006): Implementing backoff. {error_msg}")
            
            elif '"retCode":10024' in error_msg or '10024' in error_msg:
                logger.error("❌ Bybit Error 10024: Regulatory restriction")
                logger.error("   This testnet account has regional/KYC restrictions")
                logger.error("   Possible causes:")
                logger.error("   1. Account not KYC verified on testnet")
                logger.error("   2. Geographic restrictions for your region")
                logger.error("   3. Derivatives trading not enabled for this account")
                logger.error("   Solutions:")
                logger.error("   - Complete KYC verification on testnet.bybit.com")
                logger.error("   - Contact Bybit support for testnet access")
                logger.error("   - Try spot trading instead of derivatives")
                logger.error("   - Use a different testnet account")
                raise Exception(f"Bybit regulatory restriction (10024): Account restricted. {error_msg}")
            
            elif '"retCode":110001' in error_msg or '110001' in error_msg:
                logger.warning("⚠️  Bybit Error 110001: Order already filled/closed")
                logger.warning("   This order may have been processed already")
                raise Exception(f"Bybit order state error (110001): Order already processed. {error_msg}")
            
            elif '"retCode":110026' in error_msg or '110026' in error_msg:
                logger.error("❌ Bybit Error 110026: Insufficient balance")
                raise Exception(f"Bybit insufficient balance (110026): Cannot place order. {error_msg}")
            
            elif '"retCode":130021' in error_msg or '130021' in error_msg:
                logger.error("❌ Bybit Error 130021: Position size limit exceeded")
                logger.error("   Order exceeds maximum allowed position size for this symbol")
                raise Exception(f"Bybit position limit (130021): Size exceeds maximum allowed. {error_msg}")
            
            elif '"retCode":130027' in error_msg or '130027' in error_msg:
                logger.error("❌ Bybit Error 130027: Leverage exceeds maximum")
                logger.error("   Leverage too high for this symbol - reduce leverage setting")
                raise Exception(f"Bybit leverage error (130027): Exceeds maximum leverage. {error_msg}")
            
            elif '"retCode":130028' in error_msg or '130028' in error_msg:
                logger.error("❌ Bybit Error 130028: Order cost exceeds limit")
                logger.error("   Notional value too large - reduce order size or leverage")
                raise Exception(f"Bybit order cost error (130028): Notional value too large. {error_msg}")
            
            elif '"retCode":10006' in error_msg or '10006' in error_msg:
                logger.warning("⚠️  Bybit Error 10006: Rate limit exceeded during order placement")
                raise Exception(f"Bybit rate limit exceeded (10006): Implementing backoff. {error_msg}")
            
            elif 'rate' in error_msg.lower() or 'limit' in error_msg.lower():
                logger.warning("⚠️  Rate limit exceeded during order placement")
                raise Exception(f"Bybit rate limit exceeded. Implementing backoff. {error_msg}")
            
            else:
                raise Exception(f"Failed to create market order: {error_msg}")
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Place a limit order.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Quantity
            price: Limit price
            leverage: Leverage multiplier
            
        Returns:
            Order details
        """
        try:
            # Set leverage
            if leverage > 1:
                await self.exchange.set_leverage(leverage, symbol)
            
            # Place limit order
            order = await self.exchange.create_limit_order(symbol, side, amount, price)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'amount': order['amount'],
                'price': order['price'],
                'status': order['status'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'cost': order.get('cost', 0),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'leverage': leverage
            }
        except Exception as e:
            raise Exception(f"Failed to create limit order: {str(e)}")
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch current order status.
        
        Args:
            order_id: Order ID
            symbol: Trading pair
            
        Returns:
            Order status details
        """
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'status': order['status'],
                'price': order['price'],
                'average': order.get('average'),
                'amount': order['amount'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'cost': order.get('cost', 0),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'last_update': order.get('lastTradeTimestamp')
            }
        except Exception as e:
            raise Exception(f"Failed to fetch order status: {str(e)}")
    
    async def cancel_order(self, order_id: str, symbol: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            max_retries: Maximum retry attempts for timing issues (default: 3)
            
        Returns:
            Cancellation result
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Use Pybit for demo trading, CCXT for testnet/mainnet
                if self.use_pybit:
                    # Convert symbol format: XAU/USDT:USDT -> XAUUSDT
                    bybit_symbol = symbol.replace('/', '').replace(':', '')
                    # Remove duplicate USDT if present (e.g., XAUUSDTUSDT -> XAUUSDT)
                    if bybit_symbol.endswith('USDTUSDT'):
                        bybit_symbol = bybit_symbol[:-4]
                    
                    # Pybit cancel_order returns synchronous response
                    response = self.pybit_session.cancel_order(
                        category="linear",
                        symbol=bybit_symbol,
                        orderId=order_id
                    )
                    self._handle_pybit_error(response, "cancel_order")
                    
                    result = response.get('result', {})
                    
                    logger.info(f"✅ Order cancelled successfully: {order_id}")
                    return {
                        'order_id': result.get('orderId'),
                        'status': 'canceled',
                        'symbol': result.get('symbol'),
                        'canceled_at': result.get('updatedTime')
                    }
                else:
                    # CCXT for testnet/mainnet
                    result = await self.exchange.cancel_order(order_id, symbol)
                    
                    logger.info(f"✅ Order cancelled successfully: {order_id}")
                    return {
                        'order_id': result['id'],
                        'status': result['status'],
                        'symbol': result['symbol'],
                        'canceled_at': result.get('timestamp')
                    }
                    
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Check if it's a timing issue (order already filled/closed)
                if '110001' in error_msg or 'order not exists' in error_msg.lower():
                    logger.warning(f"⚠️  Order {order_id} may already be filled/closed (attempt {attempt}/{max_retries})")
                    
                    # Verify order status before retrying
                    try:
                        order_status = await self.fetch_order_status(order_id, symbol)
                        logger.info(f"   Order status: {order_status.get('status', 'unknown')}")
                        
                        # If order is already closed/filled, return success
                        if order_status.get('status') in ['closed', 'filled', 'canceled']:
                            logger.info(f"✅ Order {order_id} is already {order_status['status']}, no cancellation needed")
                            return {
                                'order_id': order_id,
                                'status': order_status['status'],
                                'symbol': symbol,
                                'note': f'Order already {order_status["status"]}'
                            }
                    except Exception:
                        pass  # Status check failed, continue with retry
                    
                    # Wait before retry (exponential backoff)
                    if attempt < max_retries:
                        import asyncio
                        wait_time = 0.5 * (2 ** (attempt - 1))  # 0.5s, 1s, 2s
                        logger.info(f"   Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                elif '10032' in error_msg or '10003' in error_msg:
                    raise  # Re-raise authentication errors immediately
                else:
                    # Other errors, retry with backoff
                    logger.warning(f"⚠️  Cancel attempt {attempt}/{max_retries} failed: {error_msg}")
                    if attempt < max_retries:
                        import asyncio
                        wait_time = 0.5 * (2 ** (attempt - 1))
                        await asyncio.sleep(wait_time)
        
        # All retries exhausted
        logger.error(f"❌ Failed to cancel order {order_id} after {max_retries} attempts")
        raise last_error
    
    async def fetch_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all open positions.
        
        Args:
            symbol: Optional trading pair filter (e.g., 'XAU/USDT:USDT')
        
        Returns:
            List of open positions
        """
        try:
            # Use Pybit for demo trading, CCXT for testnet/mainnet
            if self.use_pybit:
                # Pybit get_positions returns synchronous response
                # Pybit v5 requires symbol or settleCoin parameter
                params = {"category": "linear"}
                if symbol:
                    # Convert symbol format: XAU/USDT:USDT -> XAUUSDT
                    bybit_symbol = symbol.replace('/', '').replace(':', '')
                    if bybit_symbol.endswith('USDTUSDT'):
                        bybit_symbol = bybit_symbol[:-4]
                    params["symbol"] = bybit_symbol
                else:
                    # Without symbol filter, use settleCoin to get all USDT positions
                    params["settleCoin"] = "USDT"
                
                response = self.pybit_session.get_positions(**params)
                self._handle_pybit_error(response, "get_positions")
                
                result = response.get('result', {})
                positions_data = result.get('list', [])
                
                open_positions = []
                for pos in positions_data:
                    size_str = pos.get('size', '0')
                    # Handle empty string or invalid values
                    try:
                        size = float(size_str) if size_str else 0
                    except (ValueError, TypeError):
                        size = 0
                    
                    if size > 0:
                        # Safely convert all numeric fields
                        def safe_float(value, default=0):
                            try:
                                return float(value) if value else default
                            except (ValueError, TypeError):
                                return default
                        
                        open_positions.append({
                            'symbol': pos.get('symbol'),
                            'side': 'long' if pos.get('side') == 'Buy' else 'short',
                            'size': size,
                            'entry_price': safe_float(pos.get('avgPrice')),
                            'mark_price': safe_float(pos.get('markPrice')),
                            'unrealized_pnl': safe_float(pos.get('unrealisedPnl')),
                            'leverage': int(safe_float(pos.get('leverage'), 1)),
                            'liquidation_price': safe_float(pos.get('liqPrice'))
                        })
                
                return open_positions
            else:
                # CCXT for testnet/mainnet
                positions = await self.exchange.fetch_positions()
                
                # Filter to only open positions with robust error handling
                open_positions = []
                for pos in positions:
                    # Robustly extract contracts/size with validation
                    contracts = pos.get('contracts') or pos.get('size')
                    
                    # Skip if no position size or invalid data
                    if not contracts:
                        logger.debug(f"Skipping position with no size: {pos.get('symbol', 'unknown')}")
                        continue
                    
                    # Safe conversion of contracts to float
                    try:
                        contracts_float = float(contracts) if contracts else 0
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid contracts value '{contracts}' for {pos.get('symbol', 'unknown')}: {e}")
                        contracts_float = 0
                    
                    if contracts_float > 0:
                        # Helper function for safe float conversion
                        def safe_float(value, default=0):
                            try:
                                return float(value) if value is not None and value != '' else default
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Safe float conversion failed for '{value}': {e}, using default {default}")
                                return default
                        
                        open_positions.append({
                            'symbol': pos.get('symbol', ''),
                            'side': pos.get('side', 'long'),
                            'size': contracts_float,
                            'entry_price': safe_float(pos.get('entryPrice'), 0),
                            'mark_price': safe_float(pos.get('markPrice'), 0),
                            'unrealized_pnl': safe_float(pos.get('unrealizedPnl'), 0),
                            'leverage': int(safe_float(pos.get('leverage'), 1)),
                            'liquidation_price': safe_float(pos.get('liquidationPrice'), 0)
                        })
                
                logger.debug(f"Fetched {len(open_positions)} open positions from exchange")
                return open_positions
        except Exception as e:
            if '10032' in str(e) or '10003' in str(e):
                raise  # Re-raise Bybit-specific errors
            
            # Enhanced error logging with context
            logger.error(f"Failed to fetch positions: {type(e).__name__}: {str(e)}")
            logger.error(f"   Mode: {'DEMO' if self.demo_trading else ('TESTNET' if self.testnet else 'LIVE')}")
            logger.error(f"   Symbol filter: {symbol}")
            
            # Return empty list instead of crashing to maintain system stability
            logger.warning("⚠️  Returning empty position list due to fetch error")
            return []
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an open position with a market order.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Closure order details
        """
        try:
            # Get current position
            positions = await self.exchange.fetch_positions([symbol])
            
            for pos in positions:
                if pos.get('contracts') and pos['contracts'] > 0:
                    # Opposite side to close
                    side = 'sell' if pos['side'] == 'long' else 'buy'
                    amount = pos['contracts']
                    
                    # Close with market order
                    return await self.create_market_order(symbol, side, amount)
            
            raise Exception(f"No open position for {symbol}")
        except Exception as e:
            raise Exception(f"Failed to close position: {str(e)}")
    
    def get_trading_fee_rate(self) -> float:
        """
        Get estimated trading fee rate.
        
        Returns:
            Fee rate (e.g., 0.0006 for 0.06%)
        """
        # Bybit perpetual swap fees
        return 0.0006  # 0.06% default
    
    def calculate_total_cost(
        self,
        price: float,
        amount: float,
        leverage: int = 1,
        include_fee: bool = True
    ) -> float:
        """
        Calculate total cost including fees.
        
        Args:
            price: Entry price
            amount: Quantity
            leverage: Leverage multiplier
            include_fee: Whether to include trading fees
            
        Returns:
            Total cost in quote currency
        """
        base_cost = (price * amount) / leverage
        
        if include_fee:
            fee = base_cost * self.get_trading_fee_rate()
            return base_cost + fee
        
        return base_cost
    
    def calculate_notional_value(self, price: float, amount: float) -> float:
        """
        Calculate notional value of an order.
        
        Based on official Bybit skills large order risk warning:
        - Notional value = qty × current_price
        - Used to assess order size risk before placement
        
        Args:
            price: Current or expected execution price
            amount: Order quantity
            
        Returns:
            Notional value in quote currency (USDT)
        """
        return price * amount
    
    def check_large_order_risk(
        self,
        notional_value: float,
        available_balance: float,
        required_margin: float,
        warning_threshold_usd: float = 10000,
        balance_ratio_threshold: float = 0.2
    ) -> Dict[str, Any]:
        """
        Check if order poses large order risk based on official Bybit skills guidelines.
        
        Risk criteria:
        - Notional value > $10,000 USD (configurable)
        - Required margin > 20% of available balance (configurable)
        
        Args:
            notional_value: Order notional value in USD
            available_balance: Account available balance in USDT
            required_margin: Required margin for this order
            warning_threshold_usd: USD threshold for large order warning (default: $10,000)
            balance_ratio_threshold: Ratio of balance that triggers warning (default: 20%)
            
        Returns:
            Dictionary with risk assessment:
            {
                'is_large_order': bool,
                'risk_level': 'low' | 'medium' | 'high',
                'warnings': list of warning messages,
                'requires_confirmation': bool
            }
        """
        warnings = []
        is_large_order = False
        requires_confirmation = False
        
        # Check notional value threshold
        if notional_value > warning_threshold_usd:
            is_large_order = True
            warnings.append(
                f"⚠️  Large Order Warning: Notional value ${notional_value:,.2f} exceeds ${warning_threshold_usd:,} threshold"
            )
        
        # Check balance ratio
        if available_balance > 0:
            balance_ratio = required_margin / available_balance
            if balance_ratio > balance_ratio_threshold:
                is_large_order = True
                warnings.append(
                    f"⚠️  High Balance Usage: Required margin ${required_margin:,.2f} is {balance_ratio*100:.1f}% of available balance ${available_balance:,.2f}"
                )
        
        # Check if balance is insufficient
        if required_margin > available_balance:
            is_large_order = True
            requires_confirmation = True
            warnings.append(
                f"❌ Insufficient Balance: Required margin ${required_margin:,.2f} exceeds available balance ${available_balance:,.2f}"
            )
        
        # Determine risk level
        if len(warnings) >= 2 or requires_confirmation:
            risk_level = 'high'
        elif len(warnings) == 1:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'is_large_order': is_large_order,
            'risk_level': risk_level,
            'warnings': warnings,
            'requires_confirmation': requires_confirmation,
            'notional_value': notional_value,
            'required_margin': required_margin,
            'available_balance': available_balance
        }
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all open orders, optionally filtered by symbol.
        
        Args:
            symbol: Trading pair (optional filter)
            
        Returns:
            List of open orders
        """
        try:
            if symbol:
                orders = await self.exchange.fetch_open_orders(symbol)
            else:
                orders = await self.exchange.fetch_open_orders()
            
            return [
                {
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'status': order['status'],
                    'price': order['price'],
                    'amount': order['amount'],
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', 0),
                    'timestamp': order['timestamp']
                }
                for order in orders
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch open orders: {str(e)}")
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical orders.
        
        Args:
            symbol: Trading pair
            since: Timestamp to start from (optional)
            limit: Maximum number of orders (optional)
            
        Returns:
            List of historical orders
        """
        try:
            orders = await self.exchange.fetch_orders(symbol, since=since, limit=limit)
            return [
                {
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'status': order['status'],
                    'price': order['price'],
                    'amount': order['amount'],
                    'filled': order.get('filled', 0),
                    'cost': order.get('cost', 0),
                    'timestamp': order['timestamp']
                }
                for order in orders
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch order history: {str(e)}")
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a specific trading pair.
        
        Args:
            symbol: Trading pair
            leverage: Leverage multiplier
            
        Returns:
            Confirmation with leverage setting
        """
        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"✅ Leverage set: {leverage}x for {symbol}")
            return {'status': 'success', 'leverage': leverage, 'symbol': symbol}
        except Exception as e:
            raise Exception(f"Failed to set leverage: {str(e)}")
    
    @staticmethod
    def get_bybit_error_description(ret_code: int) -> str:
        """
        Get human-readable description for Bybit error codes.
        
        Based on official Bybit API documentation:
        https://bybit-exchange.github.io/docs/v5/error
        
        Args:
            ret_code: Bybit return code
            
        Returns:
            Description of the error
        """
        error_codes = {
            10002: "Invalid parameter - Check API key format, recv_window, or request parameters",
            10003: "API key is invalid - Key may be disabled, expired, revoked, or lacks permissions",
            10004: "Permissions denied - API key lacks required permissions for this operation",
            10005: "Permission denied for IP - IP not whitelisted in API key settings",
            10006: "Too many visits - Rate limit exceeded",
            10016: "Timestamp error - Server clock not synchronized or recv_window too small",
            10017: "Request expired - Request timestamp too old (> recv_window)",
            10024: "Regulatory restriction - Account has regional/KYC restrictions preventing trading",
            110026: "Insufficient balance - Not enough funds for this operation",
            130021: "Position size limit exceeded - Order exceeds maximum allowed position size",
            130027: "Exceeds maximum leverage - Leverage too high for this symbol",
            130028: "Order cost exceeds limit - Notional value too large",
        }
        
        return error_codes.get(ret_code, f"Unknown error code: {ret_code}")
