"""
Mean Reversion Strategy - Trades based on RSI and Bollinger Bands.

Logic:
- Enter LONG when RSI < 30 (oversold) and price touches lower Bollinger Band
- Enter SHORT when RSI > 70 (overbought) and price touches upper Bollinger Band
- Exit at middle band (mean) or opposite extreme
"""
from typing import Dict, Any, Optional
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)

class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using RSI and Bollinger Bands."""
    
    def __init__(self, rsi_period: int = 14, rsi_oversold: float = 30, 
                 rsi_overbought: float = 70, bb_period: int = 20, 
                 bb_std_dev: float = 2.0):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_std_dev = bb_std_dev
    
    @property
    def name(self) -> str:
        return "mean_reversion"
    
    async def generate_signal(self, market_data: Dict[str, Any]) -> Optional[SignalProposal]:
        """Generate mean reversion signal."""
        try:
            current_price = market_data.get('current_price', 0)
            rsi = market_data.get('rsi', 50)
            bb_upper = market_data.get('bb_upper', None)
            bb_lower = market_data.get('bb_lower', None)
            bb_middle = market_data.get('bb_middle', None)
            
            if not all([bb_upper, bb_lower, bb_middle]):
                logger.debug("Bollinger Bands data not available")
                return None
            
            side = None
            entry_price = current_price
            
            # Check for oversold condition (LONG signal)
            if rsi < self.rsi_oversold and current_price <= bb_lower:
                side = 'LONG'
                stop_loss = bb_lower * 0.99  # Below lower band
                take_profit = bb_middle  # Target mean
                
                confidence = 0.6 + (self.rsi_oversold - rsi) / 100
            
            # Check for overbought condition (SHORT signal)
            elif rsi > self.rsi_overbought and current_price >= bb_upper:
                side = 'SHORT'
                stop_loss = bb_upper * 1.01  # Above upper band
                take_profit = bb_middle  # Target mean
                
                confidence = 0.6 + (rsi - self.rsi_overbought) / 100
            
            else:
                # No mean reversion signal
                return None
            
            if not side:
                return None
            
            quantity = 0.01  # Placeholder
            
            return SignalProposal(
                symbol=market_data.get('symbol', 'BTC/USDT'),
                side=side,
                entry_price=entry_price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                quantity=quantity,
                leverage=1,
                confidence=min(0.85, round(confidence, 2)),
                strategy_name=self.name,
                regime=market_data.get('regime', 'Normal'),
                indicators={
                    'rsi': round(rsi, 2),
                    'bb_upper': round(bb_upper, 2),
                    'bb_middle': round(bb_middle, 2),
                    'bb_lower': round(bb_lower, 2)
                },
                metadata={
                    'rsi_oversold': self.rsi_oversold,
                    'rsi_overbought': self.rsi_overbought
                }
            )
            
        except Exception as e:
            logger.error(f"Mean reversion strategy error: {e}")
            return None
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'rsi_period': self.rsi_period,
            'rsi_oversold': self.rsi_oversold,
            'rsi_overbought': self.rsi_overbought,
            'bb_period': self.bb_period,
            'bb_std_dev': self.bb_std_dev
        }
