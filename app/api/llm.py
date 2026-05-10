"""
LLM optimization API endpoints for cost tracking and model routing.
Zone B: Complete LLM cost control implementation.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.llm.spend_tracker import LLMSpendTracker
from app.llm.provider_pool import LLMProviderPool
from app.config import settings

router = APIRouter()

def get_spend_tracker() -> LLMSpendTracker:
    """Dependency for getting the spend tracker instance."""
    return LLMSpendTracker(daily_budget_usd=2.0)

def get_provider_pool() -> LLMProviderPool:
    """Dependency for getting the provider pool instance."""
    return LLMProviderPool()


@router.get("/llm/usage")
async def get_llm_usage(spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)):
    """
    Get current LLM usage and spend summary.
    
    Zone B: Real-time cost monitoring
    """
    return await spend_tracker.get_usage_summary()


@router.post("/llm/record-spend")
async def record_llm_spend(
    model_tier: str,
    cost_usd: float,
    tokens: int = 0,
    spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)
):
    """
    Record LLM API spend.
    
    Args:
        model_tier: Model tier (e.g., "gemini-flash-free", "gpt-4o-mini")
        cost_usd: Cost in USD
        tokens: Number of tokens used
    """
    await spend_tracker.record_spend(model_tier, cost_usd, tokens)
    
    # Check if over budget
    over_budget = await spend_tracker.is_over_budget()
    
    return {
        "status": "recorded",
        "model_tier": model_tier,
        "cost_usd": cost_usd,
        "over_budget": over_budget,
        "budget_remaining": await spend_tracker.get_budget_remaining()
    }


@router.post("/llm/reset-spend")
async def reset_spend_counter(spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)):
    """
    Reset daily spend counter (admin operation).
    
    Zone B: Manual budget reset capability
    """
    await spend_tracker.reset_daily_spend()
    return {"status": "reset", "message": "Daily spend counter reset"}


@router.get("/llm/budget-status")
async def get_budget_status(spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)):
    """Get current budget status."""
    total = await spend_tracker.get_total_today_spend()
    remaining = await spend_tracker.get_budget_remaining()
    over = await spend_tracker.is_over_budget()
    
    return {
        "total_spent_usd": round(total, 4),
        "budget_remaining_usd": round(remaining, 4),
        "daily_budget_usd": spend_tracker.daily_budget,
        "over_budget": over,
        "budget_used_pct": round((total / spend_tracker.daily_budget * 100) if spend_tracker.daily_budget > 0 else 0, 2)
    }


@router.post("/llm/set-budget")
async def set_daily_budget(budget_usd: float, spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)):
    """
    Set daily budget limit.
    
    Args:
        budget_usd: New daily budget in USD
    """
    if budget_usd <= 0:
        raise HTTPException(status_code=400, detail="Budget must be positive")
    
    spend_tracker.daily_budget = budget_usd
    return {
        "status": "updated",
        "new_budget_usd": budget_usd
    }


@router.get("/llm/provider-stats")
async def get_provider_stats(provider_pool: LLMProviderPool = Depends(get_provider_pool)):
    """
    Get LLM provider connection pool statistics.
    
    Zone B: HTTP connection pooling monitoring
    """
    return provider_pool.stats


@router.post("/llm/test-call")
async def test_llm_call(provider: str = "openai", provider_pool: LLMProviderPool = Depends(get_provider_pool)):
    """
    Test LLM provider connectivity.
    
    Args:
        provider: Provider name ("openai", "anthropic", "google")
    """
    if provider not in provider_pool._clients:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    return {
        "provider": provider,
        "status": "configured",
        "pool_stats": provider_pool.stats.get(provider, {})
    }


@router.get("/llm/cost-analysis")
async def get_cost_analysis(spend_tracker: LLMSpendTracker = Depends(get_spend_tracker)):
    """
    Get detailed cost analysis by model tier.
    
    Shows spending patterns and optimization opportunities.
    """
    spends = await spend_tracker.get_today_spend()
    total = sum(spends.values())
    usage_summary = await spend_tracker.get_usage_summary()
    
    # Calculate cost distribution
    distribution = {}
    for tier, amount in spends.items():
        pct = (amount / total * 100) if total > 0 else 0
        distribution[tier] = {
            "spend_usd": round(amount, 4),
            "percentage": round(pct, 2)
        }
    
    # Optimization recommendations
    recommendations = []
    
    # Check if using expensive models excessively
    premium_models = ["gpt-4", "claude-sonnet"]
    premium_spend = sum(spends.get(m, 0) for m in premium_models)
    
    if premium_spend > total * 0.5 and total > 0.5:
        recommendations.append({
            "type": "cost_reduction",
            "message": "Consider shifting more traffic to cheaper models (Gemini Flash, GPT-4o-mini)",
            "potential_savings_pct": 40
        })
    
    # Check if approaching budget
    if total > spend_tracker.daily_budget * 0.8:
        recommendations.append({
            "type": "budget_alert",
            "message": f"Approaching daily budget ({total:.2f}/{spend_tracker.daily_budget:.2f} USD)",
            "action": "Reduce premium model usage or increase budget"
        })
    
    return {
        "date": usage_summary["date"],
        "total_spend_usd": round(total, 4),
        "spend_distribution": distribution,
        "recommendations": recommendations,
        "optimization_potential": {
            "current_daily_avg": round(total, 4),
            "estimated_monthly": round(total * 30, 2),
            "with_optimization": round(total * 0.6 * 30, 2),  # 40% savings potential
            "monthly_savings": round(total * 0.4 * 30, 2)
        }
    }
