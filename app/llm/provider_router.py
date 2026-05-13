"""
Provider Router - Intelligent model selection with automatic failover.
Implements tiered provider strategy for reliability and cost optimization.

Architecture:
- Tier 1: Premium models (Claude, GPT-4o) for high-stakes decisions
- Tier 2: Balanced models (GPT-4o-mini) for routine analysis
- Tier 3: Emergency fallback (heuristic mode) when all providers fail

Features:
- Dynamic health scoring per provider
- Automatic failover on timeout/error
- Cost-aware routing
- Latency monitoring
"""
import time
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from collections import deque

from app.logging_config import get_logger

logger = get_logger(__name__)


class ProviderHealth:
    """Track health metrics for a single provider."""
    
    def __init__(self, name: str, tier: int):
        self.name = name
        self.tier = tier
        self.total_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0.0
        self.recent_latencies: deque = deque(maxlen=50)
        self.last_failure_time: Optional[float] = None
        self.consecutive_failures = 0
        self.is_healthy = True
    
    def record_success(self, latency_ms: float):
        """Record successful request."""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        self.recent_latencies.append(latency_ms)
        self.consecutive_failures = 0
        self.last_failure_time = None
        
        # Update health status
        error_rate = self.error_rate
        avg_latency = self.avg_latency_ms
        
        # Unhealthy if error rate > 20% or avg latency > 10s
        self.is_healthy = (error_rate < 0.20) and (avg_latency < 10000)
    
    def record_failure(self):
        """Record failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        
        # Mark unhealthy after 3 consecutive failures
        if self.consecutive_failures >= 3:
            self.is_healthy = False
            logger.warning(f"⚠️  Provider {self.name} marked unhealthy ({self.consecutive_failures} consecutive failures)")
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency from recent requests."""
        if not self.recent_latencies:
            return 0.0
        return sum(self.recent_latencies) / len(self.recent_latencies)
    
    @property
    def health_score(self) -> float:
        """
        Calculate composite health score (0-1).
        
        Formula:
        - 40% based on error rate (lower is better)
        - 30% based on latency (lower is better)
        - 20% based on consecutive failures (lower is better)
        - 10% based on tier (lower tier number is better)
        """
        # Error rate component (0-1, higher is better)
        error_component = max(0, 1 - (self.error_rate * 5))  # 20% error = 0
        
        # Latency component (0-1, lower latency = higher score)
        latency_score = max(0, 1 - (self.avg_latency_ms / 10000))  # 10s = 0
        latency_component = latency_score
        
        # Consecutive failures component
        failure_component = max(0, 1 - (self.consecutive_failures * 0.2))  # 5 failures = 0
        
        # Tier component (Tier 1 = 1.0, Tier 2 = 0.8, Tier 3 = 0.6)
        tier_component = max(0.4, 1.0 - ((self.tier - 1) * 0.2))
        
        # Weighted composite
        health = (
            0.40 * error_component +
            0.30 * latency_component +
            0.20 * failure_component +
            0.10 * tier_component
        )
        
        return round(health, 3)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'tier': self.tier,
            'is_healthy': self.is_healthy,
            'health_score': self.health_score,
            'error_rate': round(self.error_rate * 100, 2),
            'avg_latency_ms': round(self.avg_latency_ms, 2),
            'total_requests': self.total_requests,
            'consecutive_failures': self.consecutive_failures
        }


class ProviderRouter:
    """
    Route LLM requests to optimal provider based on health and cost.
    
    Features:
    - Tiered provider selection (Premium → Balanced → Fallback)
    - Health-based routing
    - Automatic failover
    - Cost tracking
    """
    
    def __init__(self):
        """Initialize provider router with default configuration."""
        # Define providers by tier
        self.providers: Dict[str, ProviderHealth] = {
            'openrouter': ProviderHealth('openrouter', tier=1),
            'direct_openai': ProviderHealth('direct_openai', tier=2),
            'heuristic': ProviderHealth('heuristic', tier=3)
        }
        
        # Priority order (can be dynamic based on health)
        self.default_priority = ['openrouter', 'direct_openai', 'heuristic']
        
        # Request timeout settings
        self.timeout_settings = {
            'openrouter': 15.0,  # 15 seconds
            'direct_openai': 10.0,  # 10 seconds
            'heuristic': 0.1  # Instant
        }
        
        logger.info("✅ ProviderRouter initialized with 3 tiers")
    
    def get_priority_list(self, agent_type: str = 'default') -> List[str]:
        """
        Get prioritized provider list based on health scores.
        
        Args:
            agent_type: Type of agent making request (for future customization)
        
        Returns:
            Ordered list of provider names
        """
        # Sort providers by health score (descending)
        healthy_providers = [
            name for name, health in self.providers.items()
            if health.is_healthy
        ]
        
        unhealthy_providers = [
            name for name, health in self.providers.items()
            if not health.is_healthy
        ]
        
        # Sort healthy providers by health score
        healthy_providers.sort(
            key=lambda name: self.providers[name].health_score,
            reverse=True
        )
        
        # Return healthy first, then unhealthy as last resort
        return healthy_providers + unhealthy_providers
    
    def get_timeout(self, provider_name: str) -> float:
        """Get timeout for specific provider."""
        return self.timeout_settings.get(provider_name, 10.0)
    
    def record_success(self, provider_name: str, latency_ms: float):
        """Record successful request for provider."""
        if provider_name in self.providers:
            self.providers[provider_name].record_success(latency_ms)
    
    def record_failure(self, provider_name: str):
        """Record failed request for provider."""
        if provider_name in self.providers:
            self.providers[provider_name].record_failure()
    
    def get_provider_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report for all providers."""
        return {
            'providers': {
                name: health.to_dict()
                for name, health in self.providers.items()
            },
            'recommended_order': self.get_priority_list(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def execute_with_fallback(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with automatic provider fallback.
        
        Args:
            func: Async function to execute (should accept provider_name as kwarg)
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Result from first successful provider
        
        Raises:
            Exception: If all providers fail
        """
        priority_list = self.get_priority_list()
        last_error = None
        
        for provider_name in priority_list:
            timeout = self.get_timeout(provider_name)
            
            try:
                logger.debug(f"🔄 Trying provider: {provider_name} (timeout={timeout}s)")
                
                # Execute with timeout
                start_time = time.time()
                result = await asyncio.wait_for(
                    func(*args, **kwargs, provider_name=provider_name),
                    timeout=timeout
                )
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Record success
                self.record_success(provider_name, elapsed_ms)
                
                logger.info(f"✅ Provider {provider_name} succeeded ({elapsed_ms:.0f}ms)")
                return result
                
            except asyncio.TimeoutError:
                elapsed_ms = timeout * 1000
                self.record_failure(provider_name)
                last_error = TimeoutError(f"Provider {provider_name} timed out after {timeout}s")
                logger.warning(f"⚠️  Provider {provider_name} timed out")
                
            except Exception as e:
                self.record_failure(provider_name)
                last_error = e
                logger.warning(f"⚠️  Provider {provider_name} failed: {e}")
        
        # All providers failed
        logger.error(f"❌ All providers failed. Last error: {last_error}")
        raise last_error
