"""
Hybrid Exchange Manager for simultaneous multi-exchange trading.
Supports paper trading on Binance Testnet and live trading on MEXC Futures.
Enables dual execution for Gold futures comparison and validation.
"""
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings


class HybridExchangeManager:
    """
    Manages simultaneous connections to multiple exchanges for hybrid trading.
    
    Features:
    - Parallel connections to Binance Testnet (paper) and MEXC (live)
    - Symbol-aware routing (PAXG/USDT for Binance, XAU/USDT for MEXC)
    - Dual trade execution with result comparison
    - Independent balance and position tracking per exchange
    """
    
    def __init__(self):
        """Initialize both exchange clients."""
        self.binance_client = None
        self.mexc_client = None
        self._initialize_clients()
        
        print(f"✅ Hybrid Exchange Manager initialized")
        print(f"   Binance (Paper): {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   MEXC (Live): {settings.GOLD_SYMBOL_MEXC}")
    
    def _initialize_clients(self):
        """Create exchange client instances."""
        # Initialize Binance Testnet client for paper trading
        try:
            from app.infra.binance_client import BinanceClient
            self.binance_client = BinanceClient(
                api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
                api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
                testnet=True,
                demo_mode='futures_demo'
            )
            print(f"   ✅ Binance Testnet client ready")
        except Exception as e:
            print(f"   ⚠️  Binance client initialization failed: {e}")
            self.binance_client = None
        
        # Initialize MEXC live client for real trading
        try:
            from app.infra.mexc_client import MEXCClient
            self.mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures'
            )
            print(f"   ✅ MEXC Live client ready")
        except Exception as e:
            print(f"   ⚠️  MEXC client initialization failed: {e}")
            self.mexc_client = None
    
    async def close(self):
        """Close all exchange connections."""
        if self.binance_client:
            await self.binance_client.close()
        if self.mexc_client:
            await self.mexc_client.close()
    
    async def fetch_balances(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch balances from both exchanges.
        
        Returns:
            Dictionary with 'binance' and 'mexc' balance data
        """
        results = {}
        
        if self.binance_client:
            try:
                results['binance'] = await self.binance_client.fetch_balance()
            except Exception as e:
                results['binance'] = {'error': str(e)}
        
        if self.mexc_client:
            try:
                results['mexc'] = await self.mexc_client.fetch_balance()
            except Exception as e:
                results['mexc'] = {'error': str(e)}
        
        return results
    
    async def fetch_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch ticker data from both exchanges.
        
        Returns:
            Dictionary with 'binance' and 'mexc' ticker data
        """
        results = {}
        
        if self.binance_client:
            try:
                results['binance'] = await self.binance_client.fetch_ticker(
                    settings.GOLD_SYMBOL_BINANCE
                )
            except Exception as e:
                results['binance'] = {'error': str(e)}
        
        if self.mexc_client:
            try:
                results['mexc'] = await self.mexc_client.fetch_ticker(
                    settings.GOLD_SYMBOL_MEXC
                )
            except Exception as e:
                results['mexc'] = {'error': str(e)}
        
        return results
    
    async def execute_dual_trade(
        self,
        side: str,
        amount_binance: float,
        amount_mexc: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Execute trade on BOTH exchanges simultaneously.
        
        Args:
            side: 'buy' or 'sell'
            amount_binance: Quantity for Binance (PAXG)
            amount_mexc: Quantity for MEXC (XAU)
            leverage: Leverage multiplier
            
        Returns:
            Dictionary with execution results from both exchanges
        """
        results = {
            'binance': None,
            'mexc': None,
            'status': 'partial'
        }
        
        # Execute on Binance Testnet (paper trade)
        if self.binance_client:
            try:
                binance_result = await self.binance_client.create_market_order(
                    symbol=settings.GOLD_SYMBOL_BINANCE,
                    side=side,
                    amount=amount_binance,
                    leverage=leverage
                )
                results['binance'] = {
                    'status': 'success',
                    'order': binance_result,
                    'type': 'paper'
                }
            except Exception as e:
                results['binance'] = {
                    'status': 'failed',
                    'error': str(e),
                    'type': 'paper'
                }
        
        # Execute on MEXC Live (real trade)
        if self.mexc_client:
            try:
                mexc_result = await self.mexc_client.create_market_order(
                    symbol=settings.GOLD_SYMBOL_MEXC,
                    side=side,
                    amount=amount_mexc,
                    leverage=leverage
                )
                results['mexc'] = {
                    'status': 'success',
                    'order': mexc_result,
                    'type': 'live'
                }
            except Exception as e:
                results['mexc'] = {
                    'status': 'failed',
                    'error': str(e),
                    'type': 'live'
                }
        
        # Determine overall status
        if results['binance'] and results['binance']['status'] == 'success' and \
           results['mexc'] and results['mexc']['status'] == 'success':
            results['status'] = 'success'
        elif results['binance'] and results['binance']['status'] == 'failed' and \
             results['mexc'] and results['mexc']['status'] == 'failed':
            results['status'] = 'failed'
        
        return results
    
    async def execute_single_trade(
        self,
        exchange: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Execute trade on a single exchange.
        
        Args:
            exchange: 'binance' or 'mexc'
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier
            
        Returns:
            Execution result
        """
        if exchange.lower() == 'binance':
            if not self.binance_client:
                raise ValueError("Binance client not available")
            
            order = await self.binance_client.create_market_order(
                symbol=settings.GOLD_SYMBOL_BINANCE,
                side=side,
                amount=amount,
                leverage=leverage
            )
            return {
                'exchange': 'binance',
                'symbol': settings.GOLD_SYMBOL_BINANCE,
                'order': order,
                'type': 'paper'
            }
        
        elif exchange.lower() == 'mexc':
            if not self.mexc_client:
                raise ValueError("MEXC client not available")
            
            order = await self.mexc_client.create_market_order(
                symbol=settings.GOLD_SYMBOL_MEXC,
                side=side,
                amount=amount,
                leverage=leverage
            )
            return {
                'exchange': 'mexc',
                'symbol': settings.GOLD_SYMBOL_MEXC,
                'order': order,
                'type': 'live'
            }
        
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
    
    async def fetch_positions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch open positions from both exchanges.
        
        Returns:
            Dictionary with 'binance' and 'mexc' position lists
        """
        results = {}
        
        if self.binance_client:
            try:
                results['binance'] = await self.binance_client.fetch_open_positions()
            except Exception as e:
                results['binance'] = []
        
        if self.mexc_client:
            try:
                results['mexc'] = await self.mexc_client.fetch_open_positions()
            except Exception as e:
                results['mexc'] = []
        
        return results
    
    def get_symbols(self) -> Dict[str, str]:
        """
        Get configured symbols for each exchange.
        
        Returns:
            Dictionary mapping exchange to symbol
        """
        return {
            'binance': settings.GOLD_SYMBOL_BINANCE,
            'mexc': settings.GOLD_SYMBOL_MEXC
        }
    
    @property
    def info(self) -> Dict[str, Any]:
        """Get hybrid manager status information."""
        return {
            'binance_available': self.binance_client is not None,
            'mexc_available': self.mexc_client is not None,
            'symbols': self.get_symbols(),
            'mode': 'hybrid'
        }
