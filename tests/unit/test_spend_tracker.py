"""
Unit tests for Spend Tracker with budget enforcement.

Tests:
1. Daily cap triggers downgrade
2. Weekly cap blocks non-critical agents
3. Cost calculation accuracy
4. Budget reset on new day/week
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from app.llm.spend_tracker import SpendTracker


@pytest.fixture
def spend_tracker():
    """Create spend tracker with test limits."""
    return SpendTracker(
        daily_limit=10.0,
        weekly_limit=50.0,
        monthly_limit=200.0
    )


class TestSpendCap:
    """Test spend cap enforcement mechanisms."""
    
    def test_daily_cap_triggers_downgrade(self, spend_tracker):
        """When daily spend reaches 75%, should recommend downgrade."""
        # Simulate spending 80% of daily limit
        spend_tracker.current_daily_spend = 8.0  # 80% of $10
        
        status = spend_tracker.check_budget_status()
        
        assert status['degradation_level'] == 'DOWNGRADE_TO_MINI'
        assert status['can_use_premium_models'] == False
        assert status['daily']['percentage'] == 80.0
    
    def test_weekly_cap_blocks_non_critical_agents(self, spend_tracker):
        """When weekly spend exceeds limit, should block non-critical requests."""
        # Simulate exceeding weekly limit
        spend_tracker.current_weekly_spend = 55.0  # Over $50 limit
        
        # Should block non-critical
        should_block = spend_tracker.should_block_request(agent_type='non-critical')
        assert should_block == True
        
        # Critical agents might still be allowed depending on degradation level
        status = spend_tracker.check_budget_status()
        assert status['degradation_level'] == 'BLOCK_ALL'
    
    def test_cost_calculation_accuracy(self, spend_tracker):
        """Cost calculation should be accurate for different models."""
        # Test GPT-4o-mini: $0.15 per 1M tokens = $0.00015 per 1K
        cost_mini = spend_tracker.calculate_cost('gpt-4o-mini', 1000)
        assert abs(cost_mini - 0.00015) < 0.00001
        
        # Test GPT-4o: $2.50 per 1M tokens = $0.0025 per 1K
        cost_4o = spend_tracker.calculate_cost('gpt-4o', 1000)
        assert abs(cost_4o - 0.0025) < 0.00001
        
        # Test Claude: $3.00 per 1M tokens = $0.003 per 1K
        cost_claude = spend_tracker.calculate_cost('claude-3.5-sonnet', 1000)
        assert abs(cost_claude - 0.003) < 0.00001
    
    def test_budget_reset_on_new_day(self, spend_tracker):
        """Daily budget should reset when date changes."""
        # Add some spend
        spend_tracker.current_daily_spend = 5.0
        spend_tracker.daily_token_count = 1000
        
        # Simulate new day
        spend_tracker.today = (datetime.now(timezone.utc).date() - timedelta(days=1))
        
        # Check status (should trigger reset)
        spend_tracker._check_and_reset_windows()
        
        assert spend_tracker.current_daily_spend == 0.0
        assert spend_tracker.daily_token_count == 0
    
    def test_record_usage_updates_counters(self, spend_tracker):
        """Recording usage should update all counters correctly."""
        initial_daily = spend_tracker.current_daily_spend
        initial_tokens = spend_tracker.daily_token_count
        initial_requests = spend_tracker.daily_request_count
        
        # Record usage
        spend_tracker.record_usage(
            model='gpt-4o-mini',
            prompt_tokens=500,
            completion_tokens=200,
            agent_type='regime_detection'
        )
        
        # Should increase counters
        assert spend_tracker.current_daily_spend > initial_daily
        assert spend_tracker.daily_token_count == initial_tokens + 700
        assert spend_tracker.daily_request_count == initial_requests + 1
    
    def test_should_block_request_at_limit(self, spend_tracker):
        """Should block requests when at 100% budget."""
        spend_tracker.current_daily_spend = 10.0  # At limit
        
        should_block = spend_tracker.should_block_request(agent_type='non-critical')
        assert should_block == True
    
    def test_get_recommended_model_downgrades_when_needed(self, spend_tracker):
        """Should recommend cheaper models when budget is tight."""
        # Set to DOWNGRADE_TO_MINI level
        spend_tracker.current_daily_spend = 8.0  # 80%
        
        # Premium model should be downgraded
        recommended = spend_tracker.get_recommended_model('gpt-4o')
        assert recommended == 'gpt-4o-mini'
        
        # Mini model stays the same
        recommended = spend_tracker.get_recommended_model('gpt-4o-mini')
        assert recommended == 'gpt-4o-mini'
    
    def test_metrics_contain_all_fields(self, spend_tracker):
        """Metrics should contain comprehensive spend data."""
        # Record some usage
        spend_tracker.record_usage('gpt-4o-mini', 100, 50, 'test')
        
        metrics = spend_tracker.get_metrics()
        
        assert 'current_daily_spend' in metrics
        assert 'current_weekly_spend' in metrics
        assert 'current_monthly_spend' in metrics
        assert 'daily_token_count' in metrics
        assert 'limits' in metrics
        assert metrics['limits']['daily'] == 10.0
    
    @pytest.mark.asyncio
    async def test_send_budget_alert_at_warning_threshold(self, spend_tracker):
        """Should send alert when reaching 80% threshold."""
        mock_notifier = AsyncMock()
        
        # Set to warning level
        spend_tracker.current_daily_spend = 8.5  # 85%
        
        status = spend_tracker.check_budget_status()
        await spend_tracker.send_budget_alert(mock_notifier, status)
        
        # Should have sent message
        mock_notifier.send_message.assert_called_once()
        
        # Verify message content
        call_args = mock_notifier.send_message.call_args[0][0]
        assert 'Budget Alert' in call_args
        assert '85' in call_args or '80' in call_args
