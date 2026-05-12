"""
Strategy Agent - Market analysis and trade signal generation.
Wraps existing AIAgentOrchestrator with event publishing.
"""
from app.ai_agents.orchestrator import AIAgentOrchestrator
from app.events.event_bus import event_bus
from app.events.event_types import ORDER_PROPOSED
import logging

logger = logging.getLogger(__name__)


class StrategyAgent:
    """
    Responsible for market analysis and trade signal generation.
    Wraps existing AIAgentOrchestrator with event publishing.
    """
    
    def __init__(self):
        self.orchestrator = AIAgentOrchestrator(use_openrouter=True)
    
    async def analyze_and_propose(self, market_data, user_id="system"):
        """Run AI analysis cycle and publish trade proposal event."""
        logger.info("🧠 Strategy Agent: Analyzing market...")
        
        result = await self.orchestrator.run_paper_trade_cycle(
            market_data=market_data,
            user_id=user_id
        )
        
        if result.get('status') == 'success' and result.get('trade_proposal'):
            # Publish proposal event
            await event_bus.publish(ORDER_PROPOSED, {
                'proposal': result['trade_proposal'],
                'regime': result['regime'],
                'strategy': result['strategy'],
                'risk': result['risk']
            })
            logger.info("✅ Trade proposal published to event bus")
        
        return result
