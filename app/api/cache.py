"""
Cache management API endpoints.
"""
from fastapi import APIRouter, Depends
from app.cache.three_tier_cache import ThreeTierCache

router = APIRouter()

def get_cache() -> ThreeTierCache:
    """Dependency for getting the cache instance."""
    return ThreeTierCache(disk_cache_dir="./data/cache")


@router.get("/cache/stats")
async def get_cache_stats(cache: ThreeTierCache = Depends(get_cache)):
    """Get cache statistics."""
    return cache.stats


@router.post("/cache/test")
async def test_cache(key: str = "test_key", value: str = "test_value", cache: ThreeTierCache = Depends(get_cache)):
    """
    Test cache set/get operations.
    
    Demonstrates Zone D optimization: orjson for L3 cache.
    """
    # Set in cache
    await cache.set(key, {"value": value, "timestamp": "now"}, data_type="default")
    
    # Get from cache
    result = await cache.get(key, data_type="default")
    
    return {
        "key": key,
        "cached_value": result,
        "stats": cache.stats
    }


@router.delete("/cache/invalidate/{key}")
async def invalidate_cache(key: str, cache: ThreeTierCache = Depends(get_cache)):
    """Invalidate a specific cache entry."""
    await cache.invalidate(key)
    return {"status": "invalidated", "key": key}


@router.post("/cache/update-ttls")
async def update_cache_ttls(scenario: str = "Normal", cache: ThreeTierCache = Depends(get_cache)):
    """
    Update cache TTLs based on market volatility scenario.
    
    Zone D Optimization: Adaptive TTLs by Market Volatility
    
    Args:
        scenario: "Low-vol", "Normal", or "High-vol"
    """
    cache.update_ttls(scenario)
    return {
        "scenario": scenario,
        "current_ttls": cache._cache_ttls
    }


@router.delete("/cache/clear")
async def clear_all_cache(cache: ThreeTierCache = Depends(get_cache)):
    """Clear all cache tiers."""
    cache.clear_all()
    return {"status": "cleared"}
