"""
Unit tests for Provider Router with automatic failover.

Tests:
1. Tier 1 timeout → Tier 2 succeeds
2. All providers fail → Safe degrade to heuristic
3. High latency triggers reroute
4. Health score updates correctly
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.llm.provider_router import ProviderRouter, ProviderHealth


@pytest.fixture
def provider_router():
    """Create provider router for testing."""
    return ProviderRouter()


class TestProviderFallback:
    """Test provider fallback mechanisms."""
    
    @pytest.mark.asyncio
    async def test_tier1_timeout_falls_back_to_tier2(self, provider_router):
        """If Tier 1 times out, should automatically try Tier 2."""
        call_count = {'openrouter': 0, 'direct_openai': 0}
        
        async def mock_func(provider_name=None, **kwargs):
            call_count[provider_name] += 1
            
            if provider_name == 'openrouter':
                # Simulate timeout
                await asyncio.sleep(20)  # Will timeout
            elif provider_name == 'direct_openai':
                # Succeed on second try
                return {'result': 'success', 'provider': provider_name}
        
        # Execute with fallback
        result = await provider_router.execute_with_fallback(
            mock_func,
            timeout=0.1  # Very short timeout for testing
        )
        
        # Should have tried openrouter first, then direct_openai
        assert call_count['openrouter'] >= 1
        assert call_count['direct_openai'] >= 1
        assert result['provider'] == 'direct_openai'
    
    @pytest.mark.asyncio
    async def test_all_providers_fail_safe_degrade(self, provider_router):
        """If all providers fail, should raise last error (safe degrade)."""
        async def failing_func(provider_name=None, **kwargs):
            raise Exception(f"Provider {provider_name} failed")
        
        # Should raise exception after all providers fail
        with pytest.raises(Exception) as exc_info:
            await provider_router.execute_with_fallback(failing_func)
        
        assert "failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_high_latency_triggers_reroute(self, provider_router):
        """High latency should mark provider unhealthy and reroute."""
        # Record high latency for openrouter
        provider_router.providers['openrouter'].record_success(15000)  # 15s
        provider_router.providers['openrouter'].record_success(15000)
        provider_router.providers['openrouter'].record_success(15000)
        
        # Should now prefer direct_openai (lower latency)
        priority = provider_router.get_priority_list()
        
        # OpenRouter should be deprioritized due to high latency
        assert priority[0] != 'openrouter' or provider_router.providers['openrouter'].is_healthy == False
    
    @pytest.mark.asyncio
    async def test_health_score_updates_correctly(self, provider_router):
        """Health score should reflect provider performance."""
        health = provider_router.providers['openrouter']
        
        # Initial state
        assert health.health_score > 0
        
        # Record successes
        health.record_success(100)  # 100ms
        health.record_success(200)  # 200ms
        
        initial_score = health.health_score
        
        # Record failures
        health.record_failure()
        health.record_failure()
        
        # Score should decrease
        assert health.health_score < initial_score
        
        # Verify metrics
        assert health.error_rate > 0
        assert health.consecutive_failures == 2
    
    @pytest.mark.asyncio
    async def test_provider_becomes_unhealthy_after_consecutive_failures(self, provider_router):
        """Provider should be marked unhealthy after 3 consecutive failures."""
        health = provider_router.providers['openrouter']
        
        # Record 3 consecutive failures
        health.record_failure()
        health.record_failure()
        health.record_failure()
        
        assert health.is_healthy == False
        assert health.consecutive_failures == 3
    
    @pytest.mark.asyncio
    async def test_provider_recovers_after_success(self, provider_router):
        """Unhealthy provider should recover after successful requests."""
        health = provider_router.providers['openrouter']
        
        # Make unhealthy with 3 consecutive failures
        health.record_failure()
        health.record_failure()
        health.record_failure()
        assert health.is_healthy == False
        
        # Record multiple successes to bring error rate down
        # After 3 failures + 10 successes: error_rate = 3/13 = 23% (still high)
        # After 3 failures + 12 successes: error_rate = 3/15 = 20% (borderline)
        # After 3 failures + 15 successes: error_rate = 3/18 = 16.7% (healthy)
        for _ in range(15):
            health.record_success(100)  # Low latency
        
        # Should recover after enough successes
        assert health.is_healthy == True
        assert health.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_get_priority_list_sorts_by_health(self, provider_router):
        """Priority list should sort providers by health score."""
        # Make one provider unhealthy
        provider_router.providers['openrouter'].record_failure()
        provider_router.providers['openrouter'].record_failure()
        provider_router.providers['openrouter'].record_failure()
        
        priority = provider_router.get_priority_list()
        
        # Healthy providers should come first
        assert priority[0] != 'openrouter'
    
    @pytest.mark.asyncio
    async def test_health_report_contains_all_metrics(self, provider_router):
        """Health report should contain comprehensive metrics."""
        # Record some activity
        provider_router.providers['openrouter'].record_success(100)
        provider_router.providers['openrouter'].record_failure()
        
        report = provider_router.get_provider_health_report()
        
        assert 'providers' in report
        assert 'recommended_order' in report
        assert 'timestamp' in report
        
        # Check individual provider metrics
        openrouter_health = report['providers']['openrouter']
        assert 'health_score' in openrouter_health
        assert 'error_rate' in openrouter_health
        assert 'avg_latency_ms' in openrouter_health
