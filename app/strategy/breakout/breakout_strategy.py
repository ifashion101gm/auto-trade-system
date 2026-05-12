"""
Breakout Strategy - Detects price breakouts from consolidation patterns.

Logic:
- Identify support/resistance levels using recent highs/lows
- Generate LONG signal when price breaks above resistance with volume confirmation
- Generate SHORT signal when price breaks below support with volume confirmation
- Use ATR-based stop-loss and reward:risk ratio for targets
"""
from typing import Dict, Any, Optional
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)

class BreakoutStrategy(BaseStrategy):
    """Breakout detection strategy."""
    
    def __init__(self, lookback_period: int = 20, volume_multiplier: float = 1.5, 
                 atr_multiplier: float = 1.5, reward_risk_ratio: float = 2.0):
        self.lookback_period = lookback_period
        self.volume_multiplier = volume_multiplier
        self.atr_multiplier = atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
    
    @property
    def name(self) -> str:
        return "breakout"
    
    async def generate_signal(self, market_data: Dict[str, Any]) -> Optional[SignalProposal]:
        """Generate breakout signal based on price action."""
        try:
            current_price = market_data.get('current_price', 0)
            ohlcv = market_data.get('ohlcv', [])
            volume_24h = market_data.get('volume_24h', 0)
            atr = market_data.get('atr', None)
            
            if len(ohlcv) < self.lookback_period:
                logger.debug(f"Not enough data for breakout analysis")
                return None
            
            # Calculate resistance (highest high) and support (lowest low)
            highs = [candle[2] for candle in ohlcv[-self.lookback_period:]]
            lows = [candle[3] for candle in ohlcv[-self.lookback_period:]]
            volumes = [candle[5] for candle in ohlcv[-self.lookback_period:]]
            
            resistance = max(highs[:-1])  # Exclude current candle
            support = min(lows[:-1])
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
            current_volume = volumes[-1]
            
            # Check for breakout with volume confirmation
            volume_confirmation = current_volume > (avg_volume * self.volume_multiplier)
            
            if not volume_confirmation:
                logger.debug(f"No volume confirmation for breakout")
                return None
            
            # Determine breakout direction
            if current_price > resistance:
                # Bullish breakout
                side = 'LONG'
                entry_price = current_price
                
                # Calculate stop-loss using ATR
                if atr:
                    stop_loss = entry_price - (atr * self.atr_multiplier)
                else:
                    stop_loss = entry_price * 0.98  # Fallback 2%
                
                # Calculate take-profit using reward:risk ratio
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * self.reward_risk_ratio)
                
                confidence = min(0.9, 0.6 + (current_volume / avg_volume - 1) * 0.1)
                
            elif current_price < support:
                # Bearish breakout
                side = 'SHORT'
                entry_price = current_price
                
                if atr:
                    stop_loss = entry_price + (atr * self.atr_multiplier)
                else:
                    stop_loss = entry_price * 1.02
                
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * self.reward_risk_ratio)
                
                confidence = min(0.9, 0.6 + (current_volume / avg_volume - 1) * 0.1)
            else:
                # No breakout detected
                return None
            
            # Calculate quantity based on position sizing (will be refined by Risk Engine)
            quantity = 0.01  # Placeholder, Risk Engine will adjust
            
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
                    'resistance': round(resistance, 2),
                    'support': round(support, 2),
                    'volume_ratio': round(current_volume / avg_volume if avg_volume > 0 else 0, 2),
                    'atr': atr
                },
                metadata={
                    'lookback_period': self.lookback_period,
                    'breakout_type': 'bullish' if side == 'LONG' else 'bearish'
                }
            )
            
        except Exception as e:
            logger.error(f"Breakout strategy error: {e}")
            return None
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'lookback_period': self.lookback_period,
            'volume_multiplier': self.volume_multiplier,
            'atr_multiplier': self.atr_multiplier,
            'reward_risk_ratio': self.reward_risk_ratio
        }
