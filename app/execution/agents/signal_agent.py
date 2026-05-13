"""Signal Agent - Generates trade signals with deterministic safety rules."""
from typing import Dict, Any
from app.execution.agents.base_agent import BaseAgent
from app.ai_agents.optimized_orchestrator import OptimizedAIAgentOrchestrator
from app.risk.risk_engine import RiskEngine
from app.risk.validator import TradeValidator


class SignalAgent(BaseAgent):
    """Generates and validates trade signals."""
    
    def __init__(self, orchestrator: OptimizedAIAgentOrchestrator, 
                 risk_engine: RiskEngine, validator: TradeValidator):
        super().__init__("SignalAgent")
        self.orchestrator = orchestrator
        self.risk_engine = risk_engine
        self.validator = validator
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate signal and validate against risk rules."""
        market_data = context.get('market_data')
        user_id = context.get('user_id', 'default_user')
        
        # Stage 1: AI Analysis
        ai_result = await self.orchestrator.run_optimized_cycle(
            market_data=market_data,
            user_id=user_id,
            db_session=context.get('db_session')
        )
        
        if ai_result.get('status') != 'success':
            return {'signal': None, 'reason': ai_result.get('reason')}
        
        proposal = ai_result.get('proposal')
        
        # Stage 2: Risk Engine Validation
        risk_decision = await self.risk_engine.check_trade_approval(
            proposal=proposal,
            user_id=user_id
        )
        
        if not risk_decision.approved:
            return {
                'signal': None,
                'reason': 'Risk rejected',
                'violations': risk_decision.violations
            }
        
        return {
            'signal': proposal,
            'risk_metrics': risk_decision.to_dict(),
            'ai_analysis': ai_result
        }
