"""
Trend Following Strategy - Captures sustained directional moves.

Logic:
- Use moving average crossovers (MA20/MA50) to identify trend direction
- Enter LONG when MA20 crosses above MA50 (golden cross)
- Enter SHORT when MA20 crosses below MA50 (death cross)
- Use trailing stop-loss based on ATR
"""
from typing import Dict, Any, Optional
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)

class TrendStrategy(BaseStrategy):
    """Trend following strategy using moving averages."""
    
    def __init__(self, ma_fast: int = 20, ma_slow: int = 50, 
                 atr_multiplier: float = 2.0, min_trend_strength: float = 0.3):
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.atr_multiplier = atr_multiplier
        self.min_trend_strength = min_trend_strength
    
    @property
    def name(self) -> str:
        return "trend"
    
    async def generate_signal(self, market_data: Dict[str, Any]) -> Optional[SignalProposal]:
        """Generate trend following signal."""
        try:
            current_price = market_data.get('current_price', 0)
            ma_20 = market_data.get('ma_20', None)
            ma_50 = market_data.get('ma_50', None)
            atr = market_data.get('atr', None)
            macd = market_data.get('macd', 0)
            
            if not all([ma_20, ma_50]):
                logger.debug("Moving average data not available")
                return None
            
            # Calculate trend strength
            trend_strength = abs(ma_20 - ma_50) / ma_50 if ma_50 > 0 else 0
            
            if trend_strength < self.min_trend_strength:
                logger.debug(f"Trend too weak: {trend_strength:.2%}")
                return None
            
            side = None
            entry_price = current_price
            
            # Golden cross (bullish)
            if ma_20 > ma_50 and macd > 0:
                side = 'LONG'
                
                if atr:
                    stop_loss = entry_price - (atr * self.atr_multiplier)
                else:
                    stop_loss = ma_50  # Use slow MA as support
                
                take_profit = entry_price + (entry_price - stop_loss) * 2.5
            
            # Death cross (bearish)
            elif ma_20 < ma_50 and macd < 0:
                side = 'SHORT'
                
                if atr:
                    stop_loss = entry_price + (atr * self.atr_multiplier)
                else:
                    stop_loss = ma_50  # Use slow MA as resistance
                
                take_profit = entry_price - (stop_loss - entry_price) * 2.5
            
            else:
                # No clear trend signal
                return None
            
            if not side:
                return None
            
            confidence = min(0.85, 0.6 + trend_strength)
            quantity = 0.01  # Placeholder
            
            return SignalProposal(
                symbol=market_data.get('symbol', 'BTC/USDT'),
                side=side,
                entry_price=entry_price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                quantity=quantity,
                leverage=1,
                confidence=round(confidence, 2),
                strategy_name=self.name,
                regime=market_data.get('regime', 'Normal'),
                indicators={
                    'ma_20': round(ma_20, 2),
                    'ma_50': round(ma_50, 2),
                    'macd': round(macd, 2),
                    'trend_strength': round(trend_strength, 4)
                },
                metadata={
                    'ma_fast': self.ma_fast,
                    'ma_slow': self.ma_slow
                }
            )
            
        except Exception as e:
            logger.error(f"Trend strategy error: {e}")
            return None
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'ma_fast': self.ma_fast,
            'ma_slow': self.ma_slow,
            'atr_multiplier': self.atr_multiplier,
            'min_trend_strength': self.min_trend_strength
        }
