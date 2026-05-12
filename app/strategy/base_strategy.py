"""
Base strategy class for future strategy pattern implementation.
Currently, strategies are handled by the AI orchestrator.
TODO: Implement concrete strategy classes that inherit from this base.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    @abstractmethod
    def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate trade signals.
        
        Args:
            market_data: Market indicators and price data
            
        Returns:
            Strategy analysis results with signals
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        pass
