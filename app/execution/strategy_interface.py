"""
Strategy Interface - Clean separation between signal generation and execution.

Inspired by Freqtrade's IStrategy pattern, this module provides an abstract
base class for trading strategies, ensuring clean architecture where:
- Strategies focus ONLY on signal generation
- Execution service handles order placement
- Risk engine validates proposals
- No coupling between strategy logic and exchange operations

This enables:
- Easy strategy testing without exchange dependencies
- Strategy hot-swapping at runtime
- Consistent signal format across all strategies
- Clear audit trail of which strategy generated each signal
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TradeSignal:
    """
    Standardized trade signal from strategy.
    
    This is the contract between strategy and execution service.
    All strategies must return signals in this format.
    """
    symbol: str
    side: str  # 'buy' or 'sell', 'long' or 'short'
    entry_price: float
    quantity: float
    leverage: int = 1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.5
    strategy_name: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for execution service."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'confidence': self.confidence,
            'strategy_name': self.strategy_name,
            **self.metadata
        }
    
    def validate(self) -> List[str]:
        """
        Validate signal parameters.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.symbol:
            errors.append("Symbol is required")
        
        if self.side.lower() not in ['buy', 'sell', 'long', 'short']:
            errors.append(f"Invalid side: {self.side}")
        
        if self.entry_price <= 0:
            errors.append("Entry price must be positive")
        
        if self.quantity <= 0:
            errors.append("Quantity must be positive")
        
        if self.leverage < 1:
            errors.append("Leverage must be at least 1")
        
        if self.confidence < 0 or self.confidence > 1:
            errors.append("Confidence must be between 0 and 1")
        
        return errors


class IStrategy(ABC):
    """
    Abstract strategy interface separating signal generation from execution.
    
    Inspired by Freqtrade's IStrategy pattern.
    
    Lifecycle:
    1. Strategy receives market data
    2. Strategy analyzes and generates signal (or None)
    3. Signal is passed to RiskEngine for validation
    4. If approved, ExecutionService places order
    5. Strategy receives feedback for learning
    
    Example:
        class GoldMomentumStrategy(IStrategy):
            async def generate_signal(self, market_data):
                # Analyze market data
                if self._is_bullish(market_data):
                    return TradeSignal(...)
                return None
    """
    
    @abstractmethod
    async def generate_signal(
        self,
        market_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        """
        Generate trading signal based on market data.
        
        This is the core method that strategies must implement.
        It should analyze market data and return a TradeSignal if
        conditions are met, or None if no trade is warranted.
        
        Args:
            market_data: Current market data (price, indicators, etc.)
            context: Additional context (user preferences, risk limits, etc.)
            
        Returns:
            TradeSignal if conditions met, None otherwise
            
        Example:
            signal = await strategy.generate_signal({
                'symbol': 'XAUUSDT',
                'current_price': 2000.0,
                'rsi': 35.0,
                'ma_20': 1990.0,
                ...
            })
        """
        pass
    
    @abstractmethod
    def get_risk_parameters(self) -> Dict[str, Any]:
        """
        Return strategy-specific risk parameters.
        
        These parameters override global defaults for this strategy.
        
        Returns:
            Dictionary with risk parameters
            
        Example:
            {
                'max_leverage': 3,
                'risk_per_trade': 0.01,
                'max_position_size_usd': 500,
                'min_confidence': 0.7
            }
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Strategy name for logging, metrics, and identification.
        
        Returns:
            Unique strategy name
            
        Example:
            return "gold_momentum_v1"
        """
        pass
    
    @property
    def description(self) -> str:
        """
        Human-readable strategy description.
        
        Returns:
            Description string
        """
        return f"Strategy: {self.name}"
    
    async def on_trade_executed(self, signal: TradeSignal, execution_result: Dict[str, Any]):
        """
        Callback when trade is successfully executed.
        
        Override this to implement strategy-specific post-execution logic
        (e.g., updating internal state, logging, learning).
        
        Args:
            signal: The signal that was executed
            execution_result: Result from execution service
        """
        logger.info(f"Trade executed for strategy {self.name}: {signal.symbol} {signal.side}")
    
    async def on_trade_closed(self, signal: TradeSignal, pnl: float, pnl_pct: float):
        """
        Callback when trade is closed (win or loss).
        
        Override this to implement strategy-specific learning logic.
        
        Args:
            signal: Original signal
            pnl: Profit/loss in USD
            pnl_pct: Profit/loss percentage
        """
        result = "WIN" if pnl > 0 else "LOSS"
        logger.info(f"Trade closed for strategy {self.name}: {result} ${pnl:.2f} ({pnl_pct:.2%})")
    
    def can_trade(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if strategy is allowed to trade given current conditions.
        
        Override this to implement strategy-specific filters
        (e.g., time-of-day restrictions, volatility filters).
        
        Args:
            market_data: Current market data
            
        Returns:
            True if strategy can trade, False otherwise
        """
        return True  # Default: always allowed


class StrategyRegistry:
    """
    Registry for managing multiple strategies.
    
    Enables:
    - Dynamic strategy loading/unloading
    - Strategy selection based on market conditions
    - Multi-strategy portfolio management
    """
    
    def __init__(self):
        self.strategies: Dict[str, IStrategy] = {}
        logger.info("✅ Strategy Registry initialized")
    
    def register(self, strategy: IStrategy):
        """
        Register a strategy.
        
        Args:
            strategy: Strategy instance to register
        """
        name = strategy.name
        if name in self.strategies:
            logger.warning(f"Strategy {name} already registered, replacing")
        
        self.strategies[name] = strategy
        logger.info(f"📝 Registered strategy: {name}")
    
    def unregister(self, name: str):
        """
        Unregister a strategy.
        
        Args:
            name: Strategy name to remove
        """
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"❌ Unregistered strategy: {name}")
        else:
            logger.warning(f"Strategy {name} not found")
    
    def get_strategy(self, name: str) -> Optional[IStrategy]:
        """
        Get strategy by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy instance or None
        """
        return self.strategies.get(name)
    
    def list_strategies(self) -> List[str]:
        """
        List all registered strategy names.
        
        Returns:
            List of strategy names
        """
        return list(self.strategies.keys())
    
    async def generate_signals_from_all(
        self,
        market_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[TradeSignal]:
        """
        Generate signals from all registered strategies.
        
        Useful for multi-strategy portfolios.
        
        Args:
            market_data: Market data to analyze
            context: Additional context
            
        Returns:
            List of signals from all strategies
        """
        signals = []
        
        for name, strategy in self.strategies.items():
            try:
                # Check if strategy can trade
                if not strategy.can_trade(market_data):
                    logger.debug(f"Strategy {name} cannot trade currently")
                    continue
                
                # Generate signal
                signal = await strategy.generate_signal(market_data, context)
                
                if signal:
                    # Validate signal
                    errors = signal.validate()
                    if errors:
                        logger.warning(f"Strategy {name} generated invalid signal: {errors}")
                        continue
                    
                    signals.append(signal)
                    logger.info(f"✅ Strategy {name} generated signal: {signal.symbol} {signal.side}")
                    
            except Exception as e:
                logger.error(f"Strategy {name} failed to generate signal: {e}")
        
        logger.info(f"Generated {len(signals)} signals from {len(self.strategies)} strategies")
        return signals


# Example implementation (for reference/testing)
class ExampleMomentumStrategy(IStrategy):
    """
    Example momentum strategy for demonstration.
    
    This is NOT meant for production use - just shows how to implement IStrategy.
    """
    
    def __init__(self, rsi_threshold: float = 30.0):
        self.rsi_threshold = rsi_threshold
    
    @property
    def name(self) -> str:
        return "example_momentum_v1"
    
    @property
    def description(self) -> str:
        return "Simple RSI-based momentum strategy (example only)"
    
    async def generate_signal(
        self,
        market_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        """Generate signal based on RSI oversold condition."""
        rsi = market_data.get('rsi', 50)
        current_price = market_data.get('current_price', 0)
        symbol = market_data.get('symbol', 'XAUUSDT')
        
        # Simple logic: buy when RSI is oversold
        if rsi < self.rsi_threshold and current_price > 0:
            # Calculate position size (1% risk)
            quantity = 0.01  # Placeholder - would calculate properly
            
            return TradeSignal(
                symbol=symbol,
                side='buy',
                entry_price=current_price,
                quantity=quantity,
                leverage=1,
                stop_loss=current_price * 0.98,  # 2% stop
                take_profit=current_price * 1.04,  # 4% target
                confidence=0.6,
                strategy_name=self.name,
                metadata={'rsi': rsi, 'reason': 'RSI oversold'}
            )
        
        return None
    
    def get_risk_parameters(self) -> Dict[str, Any]:
        return {
            'max_leverage': 2,
            'risk_per_trade': 0.01,
            'max_position_size_usd': 100,
            'min_confidence': 0.6
        }
