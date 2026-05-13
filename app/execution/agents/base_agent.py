"""Base class for all trading agents with common functionality."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging


class BaseAgent(ABC):
    """Abstract base class for trading agents."""
    
    def __init__(self, name: str):
        self.name = name
        self.is_active = False
        self.last_run = None
        self.error_count = 0
        self.logger = logging.getLogger(f"agent.{name}")
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent logic."""
        pass
    
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper with error handling and metrics."""
        try:
            self.last_run = datetime.utcnow()
            result = await self.execute(context)
            result['agent'] = self.name
            result['success'] = True
            return result
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Agent {self.name} failed: {e}")
            return {
                'agent': self.name,
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'is_active': self.is_active,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'error_count': self.error_count
        }
