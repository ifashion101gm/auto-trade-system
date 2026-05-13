"""
Unit tests for Three-Tier Cache Manager.

Tests:
1. Cache hit works correctly
2. TTL expiration clears entry
3. Volatility event invalidates cache
"""
import pytest
import time
from app.llm.cache_manager import ThreeTierCache


@pytest.fixture
def cache():
    """Create cache manager for testing."""
    return ThreeTierCache(
        l1_ttl=60,
        l2_ttl=1800,
        l3_ttl=86400,
        max_l1_size=100
    )


class TestCacheManager:
    """Test three-tier cache functionality."""
    
    def test_cache_hit_works_correctly(self, cache):
        """Setting and getting from cache should work."""
        market_data = {'symbol': 'BTC/USDT', 'volatility': 0.45}
        
        # Set cache
        cache.set(
            prefix='regime',
            data=market_data,
            value='Normal-Trending',
            tier='L1'
        )
        
        # Get from cache
        result = cache.get(
            prefix='regime',
            data=market_data,
            tier='L1'
        )
        
        assert result == 'Normal-Trending'
        assert cache.l1_hits == 1
        assert cache.l1_misses == 0
    
    def test_ttl_expiration_clears_entry(self, cache):
        """Expired entries should not be returned."""
        # Create cache with very short TTL
        short_ttl_cache = ThreeTierCache(l1_ttl=1)  # 1 second TTL
        
        market_data = {'symbol': 'ETH/USDT'}
        
        # Set cache
        short_ttl_cache.set(
            prefix='strategy',
            data=market_data,
            value={'strategy': 'momentum'},
            tier='L1'
        )
        
        # Should hit initially
        result = short_ttl_cache.get('strategy', market_data, tier='L1')
        assert result is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should miss after TTL
        result = short_ttl_cache.get('strategy', market_data, tier='L1')
        assert result is None
        assert short_ttl_cache.l1_misses > 0
    
    def test_volatility_event_invalidates_cache(self, cache):
        """Volatility spike should invalidate relevant caches."""
        # Set multiple cache entries
        cache.set('regime', {'symbol': 'BTC'}, 'High-vol', tier='L1')
        cache.set('strategy', {'symbol': 'BTC'}, 'breakout', tier='L1')
        cache.set('signal', {'symbol': 'BTC'}, 'BUY', tier='L1')
        
        # Verify they exist
        assert cache.get('regime', {'symbol': 'BTC'}, tier='L1') == 'High-vol'
        
        # Trigger volatility invalidation
        cache.invalidate_on_volatility_spike(volatility_threshold=0.7)
        
        # All should be invalidated
        assert cache.get('regime', {'symbol': 'BTC'}, tier='L1') is None
        assert cache.get('strategy', {'symbol': 'BTC'}, tier='L1') is None
        assert cache.get('signal', {'symbol': 'BTC'}, tier='L1') is None
    
    def test_cache_key_generation_is_deterministic(self, cache):
        """Same data should generate same cache key."""
        data1 = {'symbol': 'BTC/USDT', 'price': 50000}
        data2 = {'symbol': 'BTC/USDT', 'price': 50000}
        
        key1 = cache._generate_cache_key('test', data1)
        key2 = cache._generate_cache_key('test', data2)
        
        assert key1 == key2
    
    def test_different_data_generates_different_keys(self, cache):
        """Different data should generate different cache keys."""
        data1 = {'symbol': 'BTC/USDT', 'price': 50000}
        data2 = {'symbol': 'BTC/USDT', 'price': 51000}
        
        key1 = cache._generate_cache_key('test', data1)
        key2 = cache._generate_cache_key('test', data2)
        
        assert key1 != key2
    
    def test_l1_cache_eviction_when_full(self, cache):
        """Should evict oldest entries when cache is full."""
        small_cache = ThreeTierCache(max_l1_size=3)
        
        # Fill cache
        for i in range(5):
            small_cache.set(
                prefix='test',
                data={'index': i},
                value=f'value_{i}',
                tier='L1'
            )
        
        # Should not exceed max size
        assert len(small_cache._l1_cache) <= 3
    
    def test_invalidate_by_prefix_removes_matching_entries(self, cache):
        """Invalidation by prefix should remove only matching entries."""
        # Set entries with different prefixes
        cache.set('regime', {'symbol': 'BTC'}, 'Normal', tier='L1')
        cache.set('regime', {'symbol': 'ETH'}, 'Low-vol', tier='L1')
        cache.set('strategy', {'symbol': 'BTC'}, 'momentum', tier='L1')
        
        # Invalidate regime prefix
        cache.invalidate_by_prefix('regime')
        
        # Regime entries should be gone
        assert cache.get('regime', {'symbol': 'BTC'}, tier='L1') is None
        assert cache.get('regime', {'symbol': 'ETH'}, tier='L1') is None
        
        # Strategy entry should remain
        assert cache.get('strategy', {'symbol': 'BTC'}, tier='L1') == 'momentum'
    
    def test_metrics_contain_all_fields(self, cache):
        """Metrics should contain comprehensive cache data."""
        # Perform some operations
        cache.set('test', {'data': 1}, 'value', tier='L1')
        cache.get('test', {'data': 1}, tier='L1')  # Hit
        cache.get('test', {'data': 2}, tier='L1')  # Miss
        
        metrics = cache.get_metrics()
        
        assert 'l1_cache' in metrics
        assert 'l2_cache' in metrics
        assert 'l3_cache' in metrics
        assert 'current_version' in metrics
        
        l1_metrics = metrics['l1_cache']
        assert 'size' in l1_metrics
        assert 'hits' in l1_metrics
        assert 'misses' in l1_metrics
        assert 'hit_rate_pct' in l1_metrics
    
    def test_update_version_clears_cache(self, cache):
        """Updating version should clear all cache entries."""
        # Set some entries
        cache.set('test', {'data': 1}, 'value1', tier='L1')
        cache.set('test', {'data': 2}, 'value2', tier='L1')
        
        assert len(cache._l1_cache) > 0
        
        # Update version
        cache.update_version('v2')
        
        # Cache should be cleared
        assert len(cache._l1_cache) == 0
        assert cache.current_version == 'v2'
    
    def test_cache_entry_tracks_hit_count(self, cache):
        """Cache entries should track number of hits."""
        market_data = {'symbol': 'XAU/USDT'}
        
        cache.set('signal', market_data, 'BUY', tier='L1')
        
        # Hit multiple times
        cache.get('signal', market_data, tier='L1')
        cache.get('signal', market_data, tier='L1')
        cache.get('signal', market_data, tier='L1')
        
        # Find the entry
        for entry in cache._l1_cache.values():
            if entry.value == 'BUY':
                assert entry.hit_count == 3
                break
