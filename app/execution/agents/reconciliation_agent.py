"""Reconciliation Agent - Periodic cross-validation of exchange vs database state."""
from typing import Dict, Any
from datetime import datetime
from app.execution.agents.base_agent import BaseAgent
from app.services.reconciliation_service import PositionReconciliationService
from app.execution.reconciliation_engine import PositionReconciliationEngine


class ReconciliationAgent(BaseAgent):
    """Ensures data integrity between exchange and database."""
    
    def __init__(self, reconciliation_service: PositionReconciliationService,
                 reconciliation_engine: PositionReconciliationEngine):
        super().__init__("ReconciliationAgent")
        self.reconciliation_service = reconciliation_service
        self.reconciliation_engine = reconciliation_engine
        self.last_reconciliation = None
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run reconciliation cycle."""
        user_id = context.get('user_id', 'default_user')
        db_session = context.get('db_session')
        
        if not db_session:
            return {
                'reconciliation_skipped': True,
                'reason': 'No database session provided'
            }
        
        # Run reconciliation
        result = await self.reconciliation_service.reconcile_positions(
            user_id=user_id,
            db_session=db_session,
            auto_repair=True
        )
        
        self.last_reconciliation = datetime.utcnow()
        
        return {
            'is_synced': result.is_synced,
            'repaired_count': result.repaired_count,
            'orphaned_positions': len(result.orphaned_positions),
            'ghost_positions': len(result.ghost_positions),
            'details': result.to_dict()
        }
