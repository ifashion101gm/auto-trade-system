"""
Three-tier cache implementation with orjson for L3 disk cache.
Zone D Optimization: Replace pickle with orjson for security and performance.
"""
import json
import time
import os
from pathlib import Path
from typing import Any, Optional
import orjson


class ThreeTierCache:
    """
    Three-tier caching system:
    - L1: In-memory (fastest, volatile)
    - L2: Redis (fast, shared across processes)
    - L3: Disk with orjson (persistent, slower)
    
    Zone D Optimization:
    - Replaced pickle with orjson for L3 cache
    - Prevents deserialization attacks
    - 2-4x faster than stdlib json
    - Human-readable cache files
    """
    
    def __init__(self, redis_client=None, disk_cache_dir: str = "./data/cache"):
        """
        Initialize three-tier cache.
        
        Args:
            redis_client: Redis client instance for L2 cache
            disk_cache_dir: Directory for L3 disk cache
        """
        # L1: In-memory cache
        self._l1_cache: dict = {}
        self._l1_ttl: dict = {}
        
        # L2: Redis cache
        self._redis = redis_client
        
        # L3: Disk cache with orjson
        self._disk_cache_dir = Path(disk_cache_dir)
        self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache TTLs by data type (adaptive based on volatility)
        self._cache_ttls = {
            "positions": 2,      # seconds
            "orders": 3,
            "trades": 10,
            "ohlcv": 10,
            "default": 5
        }
    
    async def get(self, key: str, data_type: str = "default") -> Optional[Any]:
        """
        Get value from cache (L1 → L2 → L3).
        
        Args:
            key: Cache key
            data_type: Type of data for TTL lookup
            
        Returns:
            Cached value or None if not found/expired
        """
        # L1: Check in-memory cache
        if key in self._l1_cache:
            if not self._is_expired(key, self._l1_ttl):
                return self._l1_cache[key]
            else:
                del self._l1_cache[key]
                del self._l1_ttl[key]
        
        # L2: Check Redis cache
        if self._redis:
            try:
                import redis.asyncio as redis
                value = await self._redis.get(f"cache:{key}")
                if value:
                    # Deserialize from orjson format
                    result = orjson.loads(value)
                    # Store in L1 for next access
                    self._set_l1(key, result, data_type)
                    return result
            except Exception as e:
                print(f"L2 cache error: {e}")
        
        # L3: Check disk cache
        disk_file = self._disk_cache_dir / f"{key}.json"
        if disk_file.exists():
            try:
                # Read and deserialize with orjson (faster than json)
                value = orjson.loads(disk_file.read_bytes())
                
                # Check if expired
                if not self._is_disk_expired(disk_file, data_type):
                    # Promote to L1 and L2
                    self._set_l1(key, value, data_type)
                    await self._set_l2(key, value, data_type)
                    return value
                else:
                    # Remove expired file
                    disk_file.unlink()
            except Exception as e:
                print(f"L3 cache error: {e}")
                # Corrupted file - remove it
                if disk_file.exists():
                    disk_file.unlink()
        
        return None
    
    async def set(self, key: str, value: Any, data_type: str = "default"):
        """
        Set value in all cache tiers (L1 + L2 + L3).
        
        Args:
            key: Cache key
            value: Value to cache
            data_type: Type of data for TTL configuration
        """
        ttl = self._cache_ttls.get(data_type, self._cache_ttls["default"])
        
        # L1: Set in-memory
        self._set_l1(key, value, data_type)
        
        # L2: Set in Redis
        await self._set_l2(key, value, data_type)
        
        # L3: Set on disk with orjson
        self._set_l3(key, value)
    
    def _set_l1(self, key: str, value: Any, data_type: str):
        """Set value in L1 (in-memory) cache."""
        self._l1_cache[key] = value
        self._l1_ttl[key] = time.time() + self._cache_ttls.get(data_type, 5)
    
    async def _set_l2(self, key: str, value: Any, data_type: str):
        """Set value in L2 (Redis) cache."""
        if not self._redis:
            return
        
        try:
            import redis.asyncio as redis
            ttl = self._cache_ttls.get(data_type, 5)
            # Serialize with orjson (faster than json)
            serialized = orjson.dumps(value)
            await self._redis.setex(f"cache:{key}", ttl, serialized)
        except Exception as e:
            print(f"L2 set error: {e}")
    
    def _set_l3(self, key: str, value: Any):
        """Set value in L3 (disk) cache using orjson."""
        disk_file = self._disk_cache_dir / f"{key}.json"
        try:
            # Serialize with orjson (faster and safer than pickle)
            serialized = orjson.dumps(value)
            disk_file.write_bytes(serialized)
        except Exception as e:
            print(f"L3 set error: {e}")
    
    def _is_expired(self, key: str, ttl_dict: dict) -> bool:
        """Check if L1 cache entry is expired."""
        if key not in ttl_dict:
            return True
        return time.time() > ttl_dict[key]
    
    def _is_disk_expired(self, disk_file: Path, data_type: str) -> bool:
        """Check if L3 disk cache file is expired."""
        ttl = self._cache_ttls.get(data_type, 5)
        file_mtime = disk_file.stat().st_mtime
        return (time.time() - file_mtime) > ttl
    
    async def invalidate(self, key: str):
        """
        Invalidate cache entry across all tiers.
        
        Args:
            key: Cache key to invalidate
        """
        # L1: Remove from memory
        self._l1_cache.pop(key, None)
        self._l1_ttl.pop(key, None)
        
        # L2: Remove from Redis
        if self._redis:
            try:
                await self._redis.delete(f"cache:{key}")
            except Exception:
                pass
        
        # L3: Remove from disk
        disk_file = self._disk_cache_dir / f"{key}.json"
        if disk_file.exists():
            try:
                disk_file.unlink()
            except Exception:
                pass
    
    def update_ttls(self, scenario: str):
        """
        Update cache TTLs based on market volatility scenario.
        
        Zone D Optimization: Adaptive TTLs by Market Volatility
        
        Args:
            scenario: Market scenario tag ("Low-vol", "Normal", "High-vol")
        """
        SCENARIO_TTL = {
            "Low-vol": {
                "positions": 5,
                "orders": 8,
                "trades": 30,
                "ohlcv": 30
            },
            "Normal": {
                "positions": 2,
                "orders": 3,
                "trades": 10,
                "ohlcv": 10
            },
            "High-vol": {
                "positions": 1,
                "orders": 2,
                "trades": 5,
                "ohlcv": 5
            }
        }
        
        if scenario in SCENARIO_TTL:
            self._cache_ttls.update(SCENARIO_TTL[scenario])
            print(f"✅ Cache TTLs updated for {scenario} scenario")
    
    def clear_all(self):
        """Clear all cache tiers."""
        # L1
        self._l1_cache.clear()
        self._l1_ttl.clear()
        
        # L2
        if self._redis:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._redis.flushdb())
            except Exception:
                pass
        
        # L3
        for file in self._disk_cache_dir.glob("*.json"):
            try:
                file.unlink()
            except Exception:
                pass
    
    @property
    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "l1_entries": len(self._l1_cache),
            "l3_files": len(list(self._disk_cache_dir.glob("*.json"))),
            "ttl_config": self._cache_ttls.copy()
        }
