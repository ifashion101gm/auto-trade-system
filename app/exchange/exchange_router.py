"""
Routes trade requests to appropriate exchange based on mode.
Supports simultaneous LIVE and DEMO execution.
"""
from app.exchange.mexc_live import MEXCLiveExchange
from app.exchange.mexc_demo import MEXCDemoExchange
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ExchangeRouter:
    """
    Routes trade requests to appropriate exchange based on mode.
    Supports simultaneous LIVE and DEMO execution.
    """
    
    def __init__(self):
        self.live_exchange = MEXCLiveExchange()
        self.demo_exchange = MEXCDemoExchange()
    
    def get_exchange(self, mode: str = None):
        """Get exchange instance by mode."""
        if mode == 'LIVE':
            return self.live_exchange
        elif mode == 'DEMO':
            return self.demo_exchange
        else:
            # Default based on config
            return self.demo_exchange if settings.APP_ENV == 'development' else self.live_exchange
    
    async def execute_dual_trade(self, proposal, mode='BOTH'):
        """Execute trade on both LIVE and DEMO for comparison."""
        results = {}
        
        if mode in ['LIVE', 'BOTH']:
            try:
                results['live'] = await self.live_exchange.open_position(
                    symbol=proposal['symbol'],
                    side=proposal['side'],
                    amount=proposal['quantity'],
                    leverage=proposal['leverage'],
                    stop_loss=proposal.get('stop_loss'),
                    take_profit=proposal.get('take_profit')
                )
            except Exception as e:
                logger.error(f"LIVE trade failed: {e}")
                results['live'] = {'error': str(e)}
        
        if mode in ['DEMO', 'BOTH']:
            try:
                results['demo'] = await self.demo_exchange.open_position(
                    symbol=proposal['symbol'],
                    side=proposal['side'],
                    amount=proposal['quantity'],
                    leverage=proposal['leverage'],
                    stop_loss=proposal.get('stop_loss'),
                    take_profit=proposal.get('take_profit')
                )
            except Exception as e:
                logger.error(f"DEMO trade failed: {e}")
                results['demo'] = {'error': str(e)}
        
        return results
