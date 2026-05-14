"""
Hybrid Exchange Manager for simultaneous multi-exchange trading.
Supports demo trading on MEXC Futures and paper trading on Binance Testnet.
Enables dual execution for Gold futures comparison and validation.
Primary exchange is now MEXC Demo Futures for XAUT/USDT.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class HybridExchangeManager:
    """
    Manages simultaneous connections to multiple exchanges for hybrid trading.
    
    Features:
    - Parallel connections to MEXC Demo Futures (primary) and Binance Testnet (comparison)
    - Symbol-aware routing (XAUT/USDT for MEXC, PAXG/USDT for Binance)
    - Dual trade execution with result comparison
    - Independent balance and position tracking per exchange
    """
    
    def __init__(self):
        """Initialize both exchange clients."""
        self.binance_client = None
        self.mexc_client = None
        self._initialize_clients()
        
        logger.info("✅ Hybrid Exchange Manager initialized")
        logger.info(f"   MEXC (Primary/Demo): {settings.GOLD_SYMBOL_MEXC}")
        logger.info(f"   Binance (Comparison/Paper): {settings.GOLD_SYMBOL_BINANCE}")
    
    def _initialize_clients(self):
        """Create exchange client instances."""
        # Initialize MEXC Demo Futures client for primary trading
        try:
            from app.infra.mexc_client import MEXCClient
            self.mexc_client = MEXCClient(
                api_key=settings.MEXC_API_KEY,
                api_secret=settings.MEXC_API_SECRET,
                market_type='futures'
            )
            logger.info("   ✅ MEXC Demo Futures client ready")
        except Exception as e:
            logger.warning(f"   ⚠️  MEXC client initialization failed: {e}")
            self.mexc_client = None
        
        # Initialize Binance Testnet client for comparison/paper trading
        try:
            from app.infra.binance_client import BinanceClient
            self.binance_client = BinanceClient(
                api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
                api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
                testnet=True,
                demo_mode='futures_demo'
            )
            logger.info("   ✅ Binance Testnet client ready")
        except Exception as e:
            logger.warning(f"   ⚠️  Binance client initialization failed: {e}")
            self.binance_client = None
    
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
        Execute trade on BOTH exchanges simultaneously with task isolation.
        
        CRITICAL: Uses asyncio.gather with return_exceptions=True to ensure
        one failing exchange does NOT crash the other. This is production-grade
        error isolation for dual-exchange trading.
        
        Primary execution is on MEXC Demo Futures (XAUT/USDT).
        Secondary execution is on Binance Testnet (PAXG/USDT) for comparison.
        
        Args:
            side: 'buy' or 'sell'
            amount_binance: Quantity for Binance (PAXG)
            amount_mexc: Quantity for MEXC (XAUT) - PRIMARY
            leverage: Leverage multiplier
            
        Returns:
            Dictionary with execution results from both exchanges
        """
        import asyncio
        
        # Define isolated tasks for each exchange
        async def execute_on_mexc():
            """Execute on MEXC with full isolation."""
            try:
                if not self.mexc_client:
                    return {
                        'status': 'failed',
                        'error': 'MEXC client not available',
                        'type': 'demo_futures'
                    }
                
                mexc_result = await self.mexc_client.create_market_order(
                    symbol=settings.GOLD_SYMBOL_MEXC,
                    side=side,
                    amount=amount_mexc,
                    leverage=leverage
                )
                return {
                    'status': 'success',
                    'order': mexc_result,
                    'type': 'demo_futures'
                }
            except Exception as e:
                logger.error(f"MEXC trade execution failed: {e}")
                return {
                    'status': 'failed',
                    'error': str(e),
                    'type': 'demo_futures'
                }
        
        async def execute_on_binance():
            """Execute on Binance with full isolation."""
            try:
                if not self.binance_client:
                    return {
                        'status': 'failed',
                        'error': 'Binance client not available',
                        'type': 'paper_testnet'
                    }
                
                binance_result = await self.binance_client.create_market_order(
                    symbol=settings.GOLD_SYMBOL_BINANCE,
                    side=side,
                    amount=amount_binance,
                    leverage=leverage
                )
                return {
                    'status': 'success',
                    'order': binance_result,
                    'type': 'paper_testnet'
                }
            except Exception as e:
                logger.error(f"Binance trade execution failed: {e}")
                return {
                    'status': 'failed',
                    'error': str(e),
                    'type': 'paper_testnet'
                }
        
        # Execute both trades in parallel with exception isolation
        # CRITICAL: return_exceptions=True prevents one failure from crashing the other
        logger.info(f"🔄 Executing dual trade on MEXC and Binance (isolated tasks)...")
        
        mexc_task = asyncio.create_task(execute_on_mexc())
        binance_task = asyncio.create_task(execute_on_binance())
        
        results_list = await asyncio.gather(
            mexc_task,
            binance_task,
            return_exceptions=True
        )
        
        # Unpack results
        mexc_result = results_list[0]
        binance_result = results_list[1]
        
        # Handle unexpected exceptions from gather (shouldn't happen due to inner try/except)
        if isinstance(mexc_result, Exception):
            logger.error(f"Unexpected MEXC task exception: {mexc_result}")
            mexc_result = {
                'status': 'failed',
                'error': f'Unexpected exception: {str(mexc_result)}',
                'type': 'demo_futures'
            }
        
        if isinstance(binance_result, Exception):
            logger.error(f"Unexpected Binance task exception: {binance_result}")
            binance_result = {
                'status': 'failed',
                'error': f'Unexpected exception: {str(binance_result)}',
                'type': 'paper_testnet'
            }
        
        # Build final result
        results = {
            'binance': binance_result,
            'mexc': mexc_result,
            'status': 'partial'
        }
        
        # Determine overall status
        if (results['binance'] and results['binance']['status'] == 'success' and 
            results['mexc'] and results['mexc']['status'] == 'success'):
            results['status'] = 'success'
            logger.info("✅ Dual trade executed successfully on both exchanges")
        elif (results['binance'] and results['binance']['status'] == 'failed' and 
              results['mexc'] and results['mexc']['status'] == 'failed'):
            results['status'] = 'failed'
            logger.error("❌ Dual trade failed on both exchanges")
        else:
            # Partial success - log which one succeeded
            if results['mexc'] and results['mexc']['status'] == 'success':
                logger.warning("⚠️  MEXC succeeded but Binance failed (partial execution)")
            elif results['binance'] and results['binance']['status'] == 'success':
                logger.warning("⚠️  Binance succeeded but MEXC failed (partial execution)")
        
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
            exchange: 'mexc' (primary) or 'binance' (comparison)
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier
            
        Returns:
            Execution result
        """
        if exchange.lower() == 'mexc':
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
                'type': 'demo_futures'
            }
        
        elif exchange.lower() == 'binance':
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
                'type': 'paper_testnet'
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
