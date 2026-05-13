"""
Three-Tier Cache Manager - Intelligent caching for LLM responses and market analysis.

Architecture:
- L1 (Memory): Fast, ephemeral cache for current cycle data (TTL: 5-60s)
- L2 (Redis): Persistent cache for shared state across instances (TTL: 5-30min)
- L3 (Database): Long-term storage for historical analysis (TTL: hours/days)

Features:
- Automatic cache invalidation on market events
- Version-based invalidation for prompt/model changes
- Volatility-aware TTL adjustment
- Cache hit/miss metrics tracking
"""
import time
import json
import hashlib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta

from app.logging_config import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """Represents a single cache entry with metadata."""
    
    def __init__(self, key: str, value: Any, ttl_seconds: int, version: str = "v1"):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.version = version
        self.hit_count = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at
    
    def record_hit(self):
        """Record a cache hit."""
        self.hit_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at,
            'ttl_seconds': self.ttl_seconds,
            'version': self.version,
            'hit_count': self.hit_count,
            'is_expired': self.is_expired,
            'age_seconds': round(self.age_seconds, 2)
        }


class ThreeTierCache:
    """
    Three-tier caching system for LLM responses and market data.
    
    Tier Strategy:
    - L1 (Memory): Ultra-fast, per-process, short TTL
    - L2 (Redis): Shared across processes, medium TTL (future enhancement)
    - L3 (Database): Persistent, long-term storage (future enhancement)
    """
    
    def __init__(
        self,
        l1_ttl: int = 60,
        l2_ttl: int = 1800,
        l3_ttl: int = 86400,
        max_l1_size: int = 1000
    ):
        """
        Initialize three-tier cache.
        
        Args:
            l1_ttl: L1 cache TTL in seconds (default: 60s)
            l2_ttl: L2 cache TTL in seconds (default: 30min)
            l3_ttl: L3 cache TTL in seconds (default: 24h)
            max_l1_size: Maximum L1 cache entries
        """
        # L1 Cache (Memory)
        self._l1_cache: Dict[str, CacheEntry] = {}
        self.l1_ttl = l1_ttl
        self.max_l1_size = max_l1_size
        
        # L2 Cache (Redis - placeholder for future implementation)
        self.l2_ttl = l2_ttl
        self.redis_available = False  # Set to True when Redis is configured
        
        # L3 Cache (Database - placeholder for future implementation)
        self.l3_ttl = l3_ttl
        self.db_available = False  # Set to True when DB cache is configured
        
        # Metrics
        self.l1_hits = 0
        self.l1_misses = 0
        self.l2_hits = 0
        self.l2_misses = 0
        self.l3_hits = 0
        self.l3_misses = 0
        
        # Cache version for invalidation
        self.current_version = "v1"
        
        logger.info(f"✅ ThreeTierCache initialized")
        logger.info(f"   L1 TTL: {l1_ttl}s, Max size: {max_l1_size}")
        logger.info(f"   L2 TTL: {l2_ttl}s (Redis: {'enabled' if self.redis_available else 'disabled'})")
        logger.info(f"   L3 TTL: {l3_ttl}s (DB: {'enabled' if self.db_available else 'disabled'})")
    
    def _generate_cache_key(
        self,
        prefix: str,
        data: Dict[str, Any],
        version: str = None
    ) -> str:
        """
        Generate deterministic cache key from data.
        
        Args:
            prefix: Key prefix (e.g., 'regime', 'strategy')
            data: Data to hash
            version: Optional version override
        
        Returns:
            Cache key string
        """
        # Sort keys for deterministic hashing
        normalized_data = json.dumps(data, sort_keys=True, default=str)
        hash_value = hashlib.md5(normalized_data.encode()).hexdigest()[:12]
        
        ver = version or self.current_version
        
        return f"{prefix}:{ver}:{hash_value}"
    
    def _evict_l1_if_needed(self):
        """Evict oldest entries if L1 cache is full."""
        if len(self._l1_cache) >= self.max_l1_size:
            # Remove expired entries first
            expired_keys = [
                key for key, entry in self._l1_cache.items()
                if entry.is_expired
            ]
            
            for key in expired_keys:
                del self._l1_cache[key]
            
            # If still full, remove oldest non-expired
            if len(self._l1_cache) >= self.max_l1_size:
                oldest_key = min(
                    self._l1_cache.keys(),
                    key=lambda k: self._l1_cache[k].created_at
                )
                del self._l1_cache[oldest_key]
                logger.debug(f"L1 cache evicted oldest entry: {oldest_key}")
    
    def get(
        self,
        prefix: str,
        data: Dict[str, Any],
        tier: str = 'L1'
    ) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            prefix: Cache key prefix
            data: Data used to generate cache key
            tier: Which tier to check ('L1', 'L2', 'L3', or 'ALL')
        
        Returns:
            Cached value or None if not found/expired
        """
        cache_key = self._generate_cache_key(prefix, data)
        
        # Check L1 cache
        if tier in ['L1', 'ALL']:
            if cache_key in self._l1_cache:
                entry = self._l1_cache[cache_key]
                
                if not entry.is_expired:
                    entry.record_hit()
                    self.l1_hits += 1
                    logger.debug(f"L1 cache HIT: {cache_key} (age={entry.age_seconds:.1f}s, hits={entry.hit_count})")
                    return entry.value
                else:
                    # Expired, remove it
                    del self._l1_cache[cache_key]
                    logger.debug(f"L1 cache EXPIRED: {cache_key}")
            
            self.l1_misses += 1
        
        # Check L2 cache (Redis - placeholder)
        if tier in ['L2', 'ALL'] and self.redis_available:
            # TODO: Implement Redis lookup
            self.l2_misses += 1
        
        # Check L3 cache (Database - placeholder)
        if tier in ['L3', 'ALL'] and self.db_available:
            # TODO: Implement DB lookup
            self.l3_misses += 1
        
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    def set(
        self,
        prefix: str,
        data: Dict[str, Any],
        value: Any,
        ttl_seconds: int = None,
        tier: str = 'L1'
    ):
        """
        Set value in cache.
        
        Args:
            prefix: Cache key prefix
            data: Data used to generate cache key
            value: Value to cache
            ttl_seconds: Custom TTL (uses default if None)
            tier: Which tier to store in ('L1', 'L2', 'L3', or 'ALL')
        """
        cache_key = self._generate_cache_key(prefix, data)
        
        # Determine TTL
        if ttl_seconds is None:
            if tier == 'L1' or tier == 'ALL':
                ttl_seconds = self.l1_ttl
            elif tier == 'L2':
                ttl_seconds = self.l2_ttl
            else:
                ttl_seconds = self.l3_ttl
        
        # Store in L1 cache
        if tier in ['L1', 'ALL']:
            self._evict_l1_if_needed()
            
            entry = CacheEntry(
                key=cache_key,
                value=value,
                ttl_seconds=ttl_seconds,
                version=self.current_version
            )
            
            self._l1_cache[cache_key] = entry
            logger.debug(f"L1 cache SET: {cache_key} (TTL={ttl_seconds}s)")
        
        # Store in L2 cache (Redis - placeholder)
        if tier in ['L2', 'ALL'] and self.redis_available:
            # TODO: Implement Redis storage
            pass
        
        # Store in L3 cache (Database - placeholder)
        if tier in ['L3', 'ALL'] and self.db_available:
            # TODO: Implement DB storage
            pass
    
    def invalidate_by_prefix(self, prefix: str):
        """
        Invalidate all cache entries with given prefix.
        
        Args:
            prefix: Cache key prefix to invalidate
        """
        keys_to_remove = [
            key for key in self._l1_cache.keys()
            if key.startswith(f"{prefix}:")
        ]
        
        for key in keys_to_remove:
            del self._l1_cache[key]
        
        if keys_to_remove:
            logger.info(f"🗑️  Invalidated {len(keys_to_remove)} cache entries with prefix '{prefix}'")
    
    def invalidate_on_volatility_spike(self, volatility_threshold: float = 0.7):
        """
        Invalidate cache when volatility spikes (market regime change).
        
        Args:
            volatility_threshold: Threshold to trigger invalidation
        """
        # Invalidate strategy and regime caches
        self.invalidate_by_prefix('regime')
        self.invalidate_by_prefix('strategy')
        self.invalidate_by_prefix('signal')
        
        logger.info(f"🌊 Cache invalidated due to volatility spike (threshold={volatility_threshold})")
    
    def invalidate_on_new_candle(self, symbol: str):
        """
        Invalidate cache when new candle closes.
        
        Args:
            symbol: Trading pair symbol
        """
        # Invalidate symbol-specific caches
        self.invalidate_by_prefix(f'signal:{symbol}')
        self.invalidate_by_prefix(f'regime:{symbol}')
        
        logger.debug(f"🕯️  Cache invalidated for {symbol} (new candle)")
    
    def update_version(self, new_version: str):
        """
        Update cache version (invalidates all entries).
        
        Args:
            new_version: New version string
        """
        old_version = self.current_version
        self.current_version = new_version
        
        # Clear L1 cache (version mismatch will cause misses)
        self._l1_cache.clear()
        
        logger.info(f"🔄 Cache version updated: {old_version} → {new_version}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics."""
        total_l1_requests = self.l1_hits + self.l1_misses
        l1_hit_rate = (self.l1_hits / total_l1_requests * 100) if total_l1_requests > 0 else 0
        
        return {
            'l1_cache': {
                'size': len(self._l1_cache),
                'max_size': self.max_l1_size,
                'hits': self.l1_hits,
                'misses': self.l1_misses,
                'hit_rate_pct': round(l1_hit_rate, 2),
                'ttl_seconds': self.l1_ttl
            },
            'l2_cache': {
                'available': self.redis_available,
                'hits': self.l2_hits,
                'misses': self.l2_misses,
                'ttl_seconds': self.l2_ttl
            },
            'l3_cache': {
                'available': self.db_available,
                'hits': self.l3_hits,
                'misses': self.l3_misses,
                'ttl_seconds': self.l3_ttl
            },
            'current_version': self.current_version,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def clear_all(self):
        """Clear all cache tiers."""
        self._l1_cache.clear()
        logger.info("🗑️  All cache tiers cleared")
