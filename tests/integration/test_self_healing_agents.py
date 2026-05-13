"""Integration tests for self-healing agent architecture."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
# Import only agents that don't have circular dependencies
from app.execution.agents.base_agent import BaseAgent
from app.execution.agents.execution_agent import ExecutionAgent
from app.execution.agents.verification_agent import VerificationAgent
from app.execution.agents.monitoring_agent import MonitoringAgent
from app.execution.agents.recovery_agent import RecoveryAgent
from app.execution.agents.reconciliation_agent import ReconciliationAgent


class TestSelfHealingAgents:
    """Test self-healing agent behaviors."""
    
    @pytest.mark.asyncio
    async def test_verification_detects_missing_order(self):
        """Verification agent should detect when order doesn't exist on exchange."""
        # Setup mock exchange that returns None for order
        mock_exchange = AsyncMock()
        mock_exchange.fetch_order.return_value = None
        
        agent = VerificationAgent(mock_exchange)
        
        result = await agent.run({
            'execution_result': {'order_id': 'test_123'},
            'proposal': {},
            'db_session': None
        })
        
        assert result['success'] == True
        assert result['verification_passed'] == False
        assert result['requires_recovery'] == True
    
    @pytest.mark.asyncio
    async def test_verification_confirms_existing_order(self):
        """Verification agent should confirm when order exists on exchange."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_order.return_value = {
            'id': 'test_123',
            'status': 'closed',
            'price': 50000.0
        }
        
        agent = VerificationAgent(mock_exchange)
        
        result = await agent.run({
            'execution_result': {'order_id': 'test_123'},
            'proposal': {},
            'db_session': None
        })
        
        assert result['success'] == True
        assert result['verification_passed'] == True
        assert result['requires_recovery'] == False
    
    @pytest.mark.asyncio
    async def test_recovery_resets_stuck_state_machine(self):
        """Recovery agent should reset state machine if stuck."""
        from app.execution.state_validator import state_validator
        from app.execution.states import ExecutionState
        
        # Set state to non-IDLE
        state_validator.current_state = ExecutionState.ERROR
        
        mock_startup_recovery = AsyncMock()
        # Mock successful recovery result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_dict.return_value = {'success': True}
        mock_startup_recovery.execute_recovery.return_value = mock_result
        mock_event_bus = AsyncMock()
        
        agent = RecoveryAgent(mock_startup_recovery, mock_event_bus)
        
        result = await agent.run({
            'issues': [{'type': 'state_mismatch'}],
            'user_id': 'test_user',
            'db_session': None
        })
        
        # Recovery should have been attempted
        assert result['recovery_attempted'] == True
        assert any(a.get('action') == 'full_recovery' for a in result['actions_taken'])
    
    @pytest.mark.asyncio
    async def test_monitoring_blocks_trading_on_circuit_breaker(self):
        """Monitoring agent should block trading when circuit breaker is open."""
        mock_cb = AsyncMock()
        mock_cb.check_system_health.return_value = MagicMock(
            can_trade=False,
            reason='API failures exceeded threshold'
        )
        
        mock_position_monitor = AsyncMock()
        mock_position_monitor.get_monitored_count.return_value = 0
        mock_position_monitor.get_metrics.return_value = {}
        
        agent = MonitoringAgent(mock_cb, mock_position_monitor)
        
        result = await agent.run({'user_id': 'test'})
        
        assert result['can_continue_trading'] == False
        assert len(result['issues']) > 0
    
    @pytest.mark.asyncio
    async def test_monitoring_allows_trading_when_healthy(self):
        """Monitoring agent should allow trading when system is healthy."""
        mock_cb = AsyncMock()
        mock_cb.check_system_health.return_value = MagicMock(
            can_trade=True,
            reason=None
        )
        
        mock_position_monitor = AsyncMock()
        mock_position_monitor.get_monitored_count.return_value = 0
        mock_position_monitor.get_metrics.return_value = {}
        
        agent = MonitoringAgent(mock_cb, mock_position_monitor)
        
        result = await agent.run({'user_id': 'test', 'daily_pnl_pct': -2.0})
        
        assert result['can_continue_trading'] == True
        assert len(result['issues']) == 0
    
    @pytest.mark.asyncio
    async def test_execution_retries_on_failure(self):
        """Execution agent should retry failed orders with exponential backoff."""
        mock_exchange = AsyncMock()
        # Fail twice, succeed on third attempt
        mock_exchange.create_market_order.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            {'order_id': 'order_123', 'price': 50000.0, 'filled': 1.0}
        ]
        
        agent = ExecutionAgent(mock_exchange, max_retries=3)
        
        result = await agent.run({
            'proposal': {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'quantity': 1.0,
                'entry_price': 49950.0,
                'leverage': 1
            }
        })
        
        assert result['success'] == True
        assert result['order_id'] == 'order_123'
        assert result['attempts'] == 3
    
    @pytest.mark.asyncio
    async def test_execution_detects_high_slippage(self):
        """Execution agent should detect and warn about high slippage."""
        mock_exchange = AsyncMock()
        mock_exchange.create_market_order.return_value = {
            'order_id': 'order_123',
            'price': 52000.0,  # 4% slippage from expected 50000
            'filled': 1.0
        }
        
        agent = ExecutionAgent(mock_exchange, max_slippage_pct=0.5)
        
        result = await agent.run({
            'proposal': {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'quantity': 1.0,
                'entry_price': 50000.0,
                'leverage': 1
            }
        })
        
        assert result['success'] == True
        assert result['slippage_pct'] > 0.5  # Should detect high slippage
    
    @pytest.mark.asyncio
    async def test_reconciliation_detects_sync_issues(self):
        """Reconciliation agent should detect position sync issues."""
        mock_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.is_synced = False
        mock_result.repaired_count = 2
        mock_result.orphaned_positions = ['pos_1']
        mock_result.ghost_positions = ['pos_2']
        mock_result.to_dict.return_value = {
            'is_synced': False,
            'repaired_count': 2
        }
        mock_service.reconcile_positions.return_value = mock_result
        
        mock_engine = AsyncMock()
        
        agent = ReconciliationAgent(mock_service, mock_engine)
        
        mock_db_session = AsyncMock()
        
        result = await agent.run({
            'user_id': 'test_user',
            'db_session': mock_db_session
        })
        
        assert result['success'] == True
        assert result['is_synced'] == False
        assert result['repaired_count'] == 2


class TestAgentErrorHandling:
    """Test agent error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_base_agent_handles_exceptions(self):
        """Base agent should catch exceptions and return structured error."""
        from app.execution.agents.base_agent import BaseAgent
        
        class FailingAgent(BaseAgent):
            async def execute(self, context):
                raise ValueError("Intentional failure")
        
        agent = FailingAgent("FailingAgent")
        
        result = await agent.run({})
        
        assert result['success'] == False
        assert result['agent'] == 'FailingAgent'
        assert 'Intentional failure' in result['error']
        assert agent.error_count == 1
    
    @pytest.mark.asyncio
    async def test_recovery_handles_unknown_issue_types(self):
        """Recovery agent should handle unknown issue types gracefully."""
        mock_startup_recovery = AsyncMock()
        mock_event_bus = AsyncMock()
        
        agent = RecoveryAgent(mock_startup_recovery, mock_event_bus)
        
        result = await agent.run({
            'issues': [{'type': 'unknown_issue_type'}],
            'user_id': 'test_user',
            'db_session': None
        })
        
        # Base agent sets success=True if no exception, but actions should show failure
        assert result['success'] == True  # No exception raised
        assert any(a.get('action') == 'unknown' for a in result['actions_taken'])
        assert any(a.get('success') == False for a in result['actions_taken'])


class TestAgentMetrics:
    """Test agent metrics collection."""
    
    def test_base_agent_tracks_metrics(self):
        """Base agent should track execution metrics."""
        from app.execution.agents.base_agent import BaseAgent
        
        class SimpleAgent(BaseAgent):
            async def execute(self, context):
                return {'result': 'ok'}
        
        agent = SimpleAgent("SimpleAgent")
        
        metrics = agent.get_metrics()
        
        assert metrics['name'] == 'SimpleAgent'
        assert metrics['is_active'] == False
        assert metrics['last_run'] is None
        assert metrics['error_count'] == 0
    
    @pytest.mark.asyncio
    async def test_agent_updates_last_run_timestamp(self):
        """Agent should update last_run timestamp after execution."""
        from app.execution.agents.base_agent import BaseAgent
        
        class SimpleAgent(BaseAgent):
            async def execute(self, context):
                return {'result': 'ok'}
        
        agent = SimpleAgent("SimpleAgent")
        
        before_run = agent.last_run
        await agent.run({})
        after_run = agent.last_run
        
        assert before_run is None
        assert after_run is not None
        assert isinstance(after_run, datetime)
