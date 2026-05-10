"""
LLM Spend Tracker with Redis persistence.
Zone B Optimization: Track and cap LLM spending across model tiers.
"""
import time
import json
from typing import Dict, Optional
from datetime import datetime, date


class LLMSpendTracker:
    """
    Tracks LLM API spending by model tier with Redis persistence.
    
    Zone B Optimization:
    - Persistent spend tracking in Redis (survives restarts)
    - Daily budget caps per model tier
    - Real-time cost monitoring
    - Automatic alerts when approaching limits
    """
    
    def __init__(self, redis_client=None, daily_budget_usd: float = 2.0):
        """
        Initialize spend tracker.
        
        Args:
            redis_client: Redis client instance for persistence
            daily_budget_usd: Maximum daily spend limit
        """
        self._redis = redis_client
        self._daily_budget = daily_budget_usd
        
        # In-memory fallback if Redis not available
        self._memory_spends: Dict[str, float] = {}
        self._memory_date: Optional[str] = None
    
    async def record_spend(self, model_tier: str, cost_usd: float, tokens: int = 0):
        """
        Record LLM API spend.
        
        Args:
            model_tier: Model tier name (e.g., "gemini-flash-free", "gpt-4o-mini")
            cost_usd: Cost in USD
            tokens: Number of tokens used
        """
        today = date.today().isoformat()
        key = f"llm_spend:{today}:{model_tier}"
        
        if self._redis:
            try:
                import redis.asyncio as redis
                # Increment spend for this model tier today
                await self._redis.incrbyfloat(key, cost_usd)
                
                # Set expiry to 2 days (keep for audit)
                await self._redis.expire(key, 172800)
                
                # Record token usage
                token_key = f"llm_tokens:{today}:{model_tier}"
                await self._redis.incr(token_key, tokens)
                await self._redis.expire(token_key, 172800)
                
            except Exception as e:
                print(f"⚠ Redis spend tracking error: {e}")
                self._record_memory_spend(model_tier, cost_usd, today)
        else:
            self._record_memory_spend(model_tier, cost_usd, today)
    
    def _record_memory_spend(self, model_tier: str, cost_usd: float, today: str):
        """Record spend in memory (fallback)."""
        if self._memory_date != today:
            self._memory_spends.clear()
            self._memory_date = today
        
        self._memory_spends[model_tier] = self._memory_spends.get(model_tier, 0) + cost_usd
    
    async def get_today_spend(self, model_tier: Optional[str] = None) -> Dict[str, float]:
        """
        Get today's spend by model tier.
        
        Args:
            model_tier: Specific tier or None for all tiers
            
        Returns:
            Dictionary of model tier -> spend amount
        """
        today = date.today().isoformat()
        
        if self._redis:
            try:
                import redis.asyncio as redis
                
                if model_tier:
                    # Get specific tier
                    key = f"llm_spend:{today}:{model_tier}"
                    value = await self._redis.get(key)
                    return {model_tier: float(value) if value else 0.0}
                else:
                    # Get all tiers for today
                    pattern = f"llm_spend:{today}:*"
                    spends = {}
                    async for key in self._redis.scan_iter(match=pattern):
                        value = await self._redis.get(key)
                        tier = key.decode().split(":")[-1]
                        spends[tier] = float(value) if value else 0.0
                    return spends
                    
            except Exception as e:
                print(f"⚠ Redis spend retrieval error: {e}")
        
        # Fallback to memory
        if model_tier:
            return {model_tier: self._memory_spends.get(model_tier, 0.0)}
        else:
            return self._memory_spends.copy()
    
    async def get_total_today_spend(self) -> float:
        """Get total spend across all model tiers today."""
        spends = await self.get_today_spend()
        return sum(spends.values())
    
    async def is_over_budget(self) -> bool:
        """Check if today's spend exceeds daily budget."""
        total = await self.get_total_today_spend()
        return total >= self._daily_budget
    
    async def get_budget_remaining(self) -> float:
        """Get remaining budget for today."""
        total = await self.get_total_today_spend()
        return max(0.0, self._daily_budget - total)
    
    async def reset_daily_spend(self):
        """Reset daily spend counter (admin operation)."""
        today = date.today().isoformat()
        
        if self._redis:
            try:
                import redis.asyncio as redis
                pattern = f"llm_spend:{today}:*"
                async for key in self._redis.scan_iter(match=pattern):
                    await self._redis.delete(key)
            except Exception as e:
                print(f"⚠ Redis reset error: {e}")
        
        # Reset memory
        self._memory_spends.clear()
        self._memory_date = today
    
    async def get_usage_summary(self) -> Dict:
        """Get comprehensive usage summary."""
        today = date.today().isoformat()
        spends = await self.get_today_spend()
        total = sum(spends.values())
        
        return {
            "date": today,
            "total_spend_usd": round(total, 4),
            "daily_budget_usd": self._daily_budget,
            "budget_remaining_usd": round(max(0.0, self._daily_budget - total), 4),
            "budget_used_pct": round((total / self._daily_budget * 100) if self._daily_budget > 0 else 0, 2),
            "over_budget": total >= self._daily_budget,
            "spend_by_tier": {tier: round(amount, 4) for tier, amount in spends.items()},
            "model_tiers_used": len(spends)
        }
    
    @property
    def daily_budget(self) -> float:
        return self._daily_budget
    
    @daily_budget.setter
    def daily_budget(self, value: float):
        self._daily_budget = value
