"""
Signal Proposal - Standardized trade signal data structure.

This module defines the canonical format for all trading signals generated
by any strategy module. It ensures consistency across the system and enables
easy interchangeability between different strategies.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class SignalProposal:
    """Standardized trade signal proposal from any strategy."""
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    quantity: float
    leverage: int = 1
    confidence: float = 0.5  # 0.0 to 1.0
    strategy_name: str = "unknown"
    regime: str = "Normal"
    indicators: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for downstream processing."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'confidence': self.confidence,
            'strategy_name': self.strategy_name,
            'regime': self.regime,
            'indicators': self.indicators,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata
        }
