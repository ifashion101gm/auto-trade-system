"""
Gold Opening Reversal Strategy - XAUUSDT specific trading strategy.

Implements session-based trading for gold with:
- London/NY session detection
- ATR-based dynamic risk sizing
- Reversal pattern detection
- SignalProposal generation

This strategy is designed specifically for XAUUSDT perpetual swaps
and focuses on high-probability reversal setups during major session opens.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone, time as dt_time

from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class GoldOpeningReversalStrategy(BaseStrategy):
    """
    Gold-specific strategy that trades reversals at session opens.
    
    Trading Sessions (UTC):
    - London Open: 07:50 - 10:30
    - NY Open: 13:20 - 16:30
    
    Strategy Logic:
    1. Check if current time is within trading session
    2. Calculate ATR for dynamic position sizing
    3. Detect reversal patterns (pin bars, engulfing, divergence)
    4. Generate SignalProposal with confidence score
    """
    
    name = "gold_opening_reversal"
    
    def __init__(self):
        """Initialize gold strategy with configuration."""
        # Session times in UTC
        self.london_session_start = dt_time(7, 50)
        self.london_session_end = dt_time(10, 30)
        self.ny_session_start = dt_time(13, 20)
        self.ny_session_end = dt_time(16, 30)
        
        # Risk parameters
        self.min_confidence = getattr(settings, 'GOLD_MIN_CONFIDENCE', 0.65)
        self.risk_per_trade = getattr(settings, 'GOLD_RISK_PER_TRADE', 0.01)
        self.max_leverage = getattr(settings, 'GOLD_MAX_LEVERAGE', 5)
        
        # ATR thresholds for dynamic sizing
        self.atr_high_threshold = 45.0  # High volatility
        self.atr_low_threshold = 30.0   # Low volatility
        
        logger.info(f"✅ {self.name} initialized")
        logger.info(f"   Min confidence: {self.min_confidence}")
        logger.info(f"   Risk per trade: {self.risk_per_trade:.1%}")
    
    async def generate_signal(self, market_data: Dict[str, Any]) -> Optional[SignalProposal]:
        """
        Analyze gold market data and generate trade signal.
        
        Args:
            market_data: Market snapshot containing:
                - symbol: str (XAUUSDT)
                - price: float
                - ohlcv: list of OHLCV candles
                - indicators: dict with RSI, MACD, ATR, etc.
                - volume: float
        
        Returns:
            SignalProposal if conditions met, None otherwise
        """
        try:
            # Step 1: Check if within trading session
            if not self.is_trading_session():
                return None
            
            # Step 2: Extract indicators
            indicators = market_data.get('indicators', {})
            atr = indicators.get('atr', 0)
            rsi = indicators.get('rsi', 50)
            
            # Step 3: Calculate dynamic risk based on ATR
            risk_pct = self.dynamic_risk_sizing(atr)
            
            # Step 4: Detect reversal patterns
            signal_type, confidence = self.detect_reversal_pattern(market_data)
            
            if signal_type is None or confidence < self.min_confidence:
                return None
            
            # Step 5: Generate SignalProposal
            current_price = market_data.get('price', 0)
            
            # Calculate stop loss and take profit based on ATR
            atr_multiplier = 1.5
            stop_distance = atr * atr_multiplier
            
            if signal_type == 'LONG':
                stop_loss = current_price - stop_distance
                take_profit = current_price + (stop_distance * 2)  # 2:1 R:R
            else:
                stop_loss = current_price + stop_distance
                take_profit = current_price - (stop_distance * 2)
            
            signal = SignalProposal(
                symbol=settings.PRIMARY_TRADING_SYMBOL,
                side=signal_type.lower(),
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                strategy_name=self.name,
                risk_pct=risk_pct,
                leverage=min(self.max_leverage, 3),  # Conservative for gold
                metadata={
                    'session': self._get_current_session(),
                    'atr': atr,
                    'rsi': rsi,
                    'risk_sizing': 'atr_dynamic'
                }
            )
            
            logger.info(
                f"📊 Signal generated: {signal_type} {settings.PRIMARY_TRADING_SYMBOL} "
                f"@ {current_price:.2f} (confidence: {confidence:.2f})"
            )
            
            return signal
        
        except Exception as e:
            logger.error(f"Error generating gold signal: {e}", exc_info=True)
            return None
    
    def is_trading_session(self) -> bool:
        """
        Check if current time is within active trading session.
        
        Returns:
            True if within London or NY session, False otherwise
        """
        now_utc = datetime.now(timezone.utc).time()
        
        # Check London session
        if self.london_session_start <= now_utc <= self.london_session_end:
            return True
        
        # Check NY session
        if self.ny_session_start <= now_utc <= self.ny_session_end:
            return True
        
        return False
    
    def _get_current_session(self) -> str:
        """Get name of current trading session."""
        now_utc = datetime.now(timezone.utc).time()
        
        if self.london_session_start <= now_utc <= self.london_session_end:
            return "london_open"
        elif self.ny_session_start <= now_utc <= self.ny_session_end:
            return "ny_open"
        else:
            return "off_hours"
    
    def dynamic_risk_sizing(self, atr: float) -> float:
        """
        Adjust risk percentage based on ATR (volatility).
        
        Higher ATR = lower risk (reduce position size)
        Lower ATR = higher risk (increase position size)
        
        Args:
            atr: Current Average True Range value
        
        Returns:
            Risk percentage for this trade
        """
        if atr > self.atr_high_threshold:
            # High volatility - reduce risk to 0.3%
            risk = 0.003
            logger.debug(f"High ATR ({atr:.2f}) - reducing risk to 0.3%")
        elif atr < self.atr_low_threshold:
            # Low volatility - can increase risk to 1%
            risk = 0.01
            logger.debug(f"Low ATR ({atr:.2f}) - increasing risk to 1%")
        else:
            # Normal volatility - use default risk
            risk = self.risk_per_trade
        
        return risk
    
    def detect_reversal_pattern(self, market_data: Dict[str, Any]) -> tuple:
        """
        Detect reversal patterns in price action.
        
        Checks for:
        - Pin bar formations
        - Engulfing candles
        - RSI divergence
        - Support/resistance bounces
        
        Args:
            market_data: Market snapshot with OHLCV and indicators
        
        Returns:
            Tuple of (signal_type: 'LONG'|'SHORT'|None, confidence: float)
        """
        # TODO: Implement actual pattern detection logic
        # For now, return None (no signal) as stub implementation
        
        indicators = market_data.get('indicators', {})
        rsi = indicators.get('rsi', 50)
        
        # Simple RSI-based reversal detection (placeholder)
        if rsi < 30:
            # Oversold - potential long reversal
            confidence = 0.70
            return ('LONG', confidence)
        elif rsi > 70:
            # Overbought - potential short reversal
            confidence = 0.70
            return ('SHORT', confidence)
        
        return (None, 0.0)
    
    def calculate_atr(self, market_data: Dict[str, Any]) -> float:
        """
        Extract or calculate ATR from market data.
        
        Args:
            market_data: Market snapshot
        
        Returns:
            ATR value
        """
        indicators = market_data.get('indicators', {})
        return indicators.get('atr', 0)
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy-specific parameters."""
        return {
            'min_confidence': self.min_confidence,
            'risk_per_trade': self.risk_per_trade,
            'max_leverage': self.max_leverage,
            'atr_high_threshold': self.atr_high_threshold,
            'atr_low_threshold': self.atr_low_threshold,
            'london_session': f"{self.london_session_start}-{self.london_session_end}",
            'ny_session': f"{self.ny_session_start}-{self.ny_session_end}"
        }
