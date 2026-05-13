"""
Duplicate Order Protection Engine.

Prevents duplicate trade execution by tracking signal hashes and order IDs.
Uses Redis for distributed deduplication across multiple instances.
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class DuplicateProtectionEngine:
    """
    Prevents duplicate order execution through signal deduplication.
    
    Features:
    - Signal hash generation from trade parameters
    - Redis-based deduplication cache
    - Configurable TTL for signal hashes
    - Order ID tracking to prevent re-execution
    """
    
    def __init__(
        self,
        redis_client=None,
        signal_ttl_seconds: int = 3600,  # 1 hour default
        order_ttl_seconds: int = 86400   # 24 hours default
    ):
        """
        Initialize duplicate protection engine.
        
        Args:
            redis_client: Redis client instance (async)
            signal_ttl_seconds: How long to track signal hashes
            order_ttl_seconds: How long to track executed order IDs
        """
        self.redis = redis_client
        self.signal_ttl = signal_ttl_seconds
        self.order_ttl = order_ttl_seconds
        self.logger = logging.getLogger("dedup_engine")
        
        # Fallback in-memory cache if Redis not available
        self._memory_cache: Dict[str, datetime] = {}
        self._order_cache: Dict[str, datetime] = {}
    
    def generate_signal_hash(self, signal_data: Dict[str, Any]) -> str:
        """
        Generate unique hash from signal parameters.
        
        Hash includes:
        - Symbol
        - Side (BUY/SELL)
        - Entry price
        - Quantity
        - Stop loss
        - Take profit
        
        Args:
            signal_data: Trade signal dictionary
            
        Returns:
            SHA256 hash string
        """
        # Normalize signal data for consistent hashing
        normalized = {
            'symbol': signal_data.get('symbol', ''),
            'side': signal_data.get('side', '').upper(),
            'entry_price': signal_data.get('entry_price', 0),
            'quantity': signal_data.get('quantity', 0),
            'stop_loss': signal_data.get('stop_loss', 0),
            'take_profit': signal_data.get('take_profit', 0),
            'leverage': signal_data.get('leverage', 1)
        }
        
        # Create deterministic JSON string
        signal_str = json.dumps(normalized, sort_keys=True)
        
        # Generate SHA256 hash
        signal_hash = hashlib.sha256(signal_str.encode()).hexdigest()
        
        self.logger.debug(f"Generated signal hash: {signal_hash[:16]}... for {normalized['symbol']} {normalized['side']}")
        
        return signal_hash
    
    async def is_duplicate_signal(self, signal_hash: str) -> bool:
        """
        Check if signal has already been processed.
        
        Args:
            signal_hash: Hash of the signal to check
            
        Returns:
            True if duplicate, False if new
        """
        try:
            if self.redis:
                # Check Redis cache
                exists = await self.redis.exists(f"signal:{signal_hash}")
                return bool(exists)
            else:
                # Check memory cache
                if signal_hash in self._memory_cache:
                    # Check if TTL expired
                    if datetime.utcnow() - self._memory_cache[signal_hash] < timedelta(seconds=self.signal_ttl):
                        return True
                    else:
                        # Expired, remove from cache
                        del self._memory_cache[signal_hash]
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking duplicate signal: {e}")
            # Fail-safe: allow signal if check fails
            return False
    
    async def mark_signal_processed(self, signal_hash: str) -> bool:
        """
        Mark signal as processed to prevent future duplicates.
        
        Args:
            signal_hash: Hash of the signal to mark
            
        Returns:
            True if marked successfully
        """
        try:
            if self.redis:
                # Set in Redis with TTL
                await self.redis.setex(
                    f"signal:{signal_hash}",
                    self.signal_ttl,
                    datetime.utcnow().isoformat()
                )
            else:
                # Store in memory cache
                self._memory_cache[signal_hash] = datetime.utcnow()
            
            self.logger.info(f"Marked signal {signal_hash[:16]}... as processed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking signal processed: {e}")
            return False
    
    async def is_duplicate_order(self, order_id: str) -> bool:
        """
        Check if order ID has already been executed.
        
        Args:
            order_id: Exchange order ID
            
        Returns:
            True if duplicate, False if new
        """
        try:
            if self.redis:
                exists = await self.redis.exists(f"order:{order_id}")
                return bool(exists)
            else:
                if order_id in self._order_cache:
                    if datetime.utcnow() - self._order_cache[order_id] < timedelta(seconds=self.order_ttl):
                        return True
                    else:
                        del self._order_cache[order_id]
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking duplicate order: {e}")
            return False
    
    async def mark_order_executed(self, order_id: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Mark order as executed to prevent re-execution.
        
        Args:
            order_id: Exchange order ID
            metadata: Optional metadata to store with order
            
        Returns:
            True if marked successfully
        """
        try:
            if self.redis:
                # Store order ID with metadata
                order_data = {
                    'executed_at': datetime.utcnow().isoformat(),
                    'metadata': metadata or {}
                }
                await self.redis.setex(
                    f"order:{order_id}",
                    self.order_ttl,
                    json.dumps(order_data)
                )
            else:
                self._order_cache[order_id] = datetime.utcnow()
            
            self.logger.info(f"Marked order {order_id} as executed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking order executed: {e}")
            return False
    
    async def check_and_mark_signal(
        self,
        signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Atomic check-and-mark operation for signal deduplication.
        
        This prevents race conditions where two instances might process
        the same signal simultaneously.
        
        Args:
            signal_data: Trade signal dictionary
            
        Returns:
            Dictionary with 'is_duplicate' and 'signal_hash'
        """
        signal_hash = self.generate_signal_hash(signal_data)
        
        # Check if duplicate
        is_dup = await self.is_duplicate_signal(signal_hash)
        
        if is_dup:
            self.logger.warning(f"⚠️ Duplicate signal detected: {signal_hash[:16]}...")
            return {
                'is_duplicate': True,
                'signal_hash': signal_hash,
                'action': 'rejected'
            }
        
        # Mark as processed (atomic operation)
        marked = await self.mark_signal_processed(signal_hash)
        
        if not marked:
            self.logger.error(f"Failed to mark signal {signal_hash[:16]}... as processed")
            return {
                'is_duplicate': False,
                'signal_hash': signal_hash,
                'action': 'error_marking'
            }
        
        return {
            'is_duplicate': False,
            'signal_hash': signal_hash,
            'action': 'accepted'
        }
    
    async def cleanup_expired_entries(self) -> Dict[str, int]:
        """
        Clean up expired entries from memory cache.
        
        Note: Redis handles TTL automatically.
        
        Returns:
            Count of cleaned entries
        """
        now = datetime.utcnow()
        cleaned_signals = 0
        cleaned_orders = 0
        
        # Clean signal cache
        expired_signals = [
            hash_val for hash_val, timestamp in self._memory_cache.items()
            if now - timestamp >= timedelta(seconds=self.signal_ttl)
        ]
        for hash_val in expired_signals:
            del self._memory_cache[hash_val]
            cleaned_signals += 1
        
        # Clean order cache
        expired_orders = [
            order_id for order_id, timestamp in self._order_cache.items()
            if now - timestamp >= timedelta(seconds=self.order_ttl)
        ]
        for order_id in expired_orders:
            del self._order_cache[order_id]
            cleaned_orders += 1
        
        if cleaned_signals > 0 or cleaned_orders > 0:
            self.logger.info(
                f"Cleaned up {cleaned_signals} expired signals and "
                f"{cleaned_orders} expired orders from memory cache"
            )
        
        return {
            'cleaned_signals': cleaned_signals,
            'cleaned_orders': cleaned_orders
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get deduplication statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'active_signals': len(self._memory_cache),
            'active_orders': len(self._order_cache),
            'signal_ttl_seconds': self.signal_ttl,
            'order_ttl_seconds': self.order_ttl
        }
        
        if self.redis:
            try:
                # Get Redis stats
                signal_keys = await self.redis.keys("signal:*")
                order_keys = await self.redis.keys("order:*")
                stats['redis_active_signals'] = len(signal_keys)
                stats['redis_active_orders'] = len(order_keys)
            except Exception as e:
                self.logger.error(f"Error getting Redis stats: {e}")
        
        return stats
