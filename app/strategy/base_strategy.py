"""
Base strategy class for all trading strategies.
Enforces consistent interface for signal generation across all strategy modules.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.strategy.signal_proposal import SignalProposal


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    @abstractmethod
    async def generate_signal(self, market_data: Dict[str, Any]) -> Optional[SignalProposal]:
        """
        Analyze market data and generate a trade signal.
        
        Args:
            market_data: Market snapshot with OHLCV, indicators, etc.
            
        Returns:
            SignalProposal if conditions met, None otherwise
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy-specific parameters."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name identifier."""
        pass
