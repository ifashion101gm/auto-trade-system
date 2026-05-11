"""
Abstract base class for all exchange implementations.
Ensures consistent interface across LIVE and DEMO modes.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseExchange(ABC):
    """
    Abstract base class for all exchange implementations.
    Ensures consistent interface across LIVE and DEMO modes.
    """
    
    @abstractmethod
    async def open_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """Open a position (market order)."""
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str, trade_id: str) -> Dict[str, Any]:
        """Close an existing position."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get real-time ticker data."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order."""
        pass
    
    @property
    @abstractmethod
    def mode(self) -> str:
        """Return exchange mode: 'LIVE' or 'DEMO'."""
        pass
