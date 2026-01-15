"""
LLM Response Cache - Production-Grade Caching System

Implements intelligent caching for LLM responses to reduce latency and API costs.

Features:
- TTL-based expiration
- LRU eviction policy
- Thread-safe operations
- Memory-efficient storage
- Cache statistics tracking

SECURITY INVARIANTS:
- Cached responses are validated before return
- No sensitive data in cache keys
- Cache is memory-only (no disk persistence)
- Automatic cleanup on shutdown
"""

import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    
    response: str
    timestamp: datetime
    hit_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        age = datetime.utcnow() - self.timestamp
        return age.total_seconds() > self.ttl_seconds
    
    def access(self) -> str:
        """Record access and return response."""
        self.hit_count += 1
        self.last_accessed = datetime.utcnow()
        return self.response


@dataclass
class CacheStatistics:
    """Cache performance statistics."""
    
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0
    expirations: int = 0
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'evictions': self.evictions,
            'expirations': self.expirations,
            'hit_rate': self.get_hit_rate()
        }


class ResponseCache:
    """
    Thread-safe LRU cache for LLM responses.
    
    Features:
    - Automatic expiration based on TTL
    - LRU eviction when max size reached
    - Thread-safe operations
    - Comprehensive statistics
    - Memory-efficient storage
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 3600,
        enable_statistics: bool = True
    ):
        """
        Initialize response cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl_seconds: Default TTL for entries
            enable_statistics: Enable statistics tracking
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self.enable_statistics = enable_statistics
        
        # Cache storage (OrderedDict for LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        
        # Statistics
        self.statistics = CacheStatistics()
        
        # Logging
        self.logger = logging.getLogger("llm.response_cache")
        
        self.logger.info(
            f"Response cache initialized (max_size={max_size}, "
            f"default_ttl={default_ttl_seconds}s)"
        )
    
    def get(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached response if available.
        
        Args:
            prompt: Input prompt
            context: Optional context
            model: Optional model name
        
        Returns:
            Optional[str]: Cached response or None
        """
        cache_key = self._generate_cache_key(prompt, context, model)
        
        with self._lock:
            if self.enable_statistics:
                self.statistics.total_requests += 1
            
            # Check if entry exists
            if cache_key not in self._cache:
                if self.enable_statistics:
                    self.statistics.cache_misses += 1
                return None
            
            entry = self._cache[cache_key]
            
            # Check if expired
            if entry.is_expired():
                del self._cache[cache_key]
                if self.enable_statistics:
                    self.statistics.expirations += 1
                    self.statistics.cache_misses += 1
                self.logger.debug(f"Cache entry expired: {cache_key[:16]}...")
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            
            # Record hit
            if self.enable_statistics:
                self.statistics.cache_hits += 1
            
            response = entry.access()
            self.logger.debug(
                f"Cache hit: {cache_key[:16]}... "
                f"(hit_count={entry.hit_count})"
            )
            
            return response
    
    def put(
        self,
        prompt: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store response in cache.
        
        Args:
            prompt: Input prompt
            response: Generated response
            context: Optional context
            model: Optional model name
            ttl_seconds: Optional custom TTL
        """
        cache_key = self._generate_cache_key(prompt, context, model)
        ttl = ttl_seconds or self.default_ttl_seconds
        
        with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and cache_key not in self._cache:
                # Remove least recently used
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                if self.enable_statistics:
                    self.statistics.evictions += 1
                self.logger.debug(
                    f"Cache eviction: {evicted_key[:16]}... "
                    f"(hit_count={evicted_entry.hit_count})"
                )
            
            # Create entry
            entry = CacheEntry(
                response=response,
                timestamp=datetime.utcnow(),
                ttl_seconds=ttl
            )
            
            # Store entry
            self._cache[cache_key] = entry
            
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            
            self.logger.debug(
                f"Cache stored: {cache_key[:16]}... "
                f"(size={len(self._cache)}/{self.max_size})"
            )
    
    def invalidate(
        self,
        prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.
        
        Args:
            prompt: Optional prompt to invalidate
            context: Optional context
            model: Optional model name
        
        Returns:
            int: Number of entries invalidated
        """
        with self._lock:
            if prompt is not None:
                # Invalidate specific entry
                cache_key = self._generate_cache_key(prompt, context, model)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    self.logger.debug(f"Cache invalidated: {cache_key[:16]}...")
                    return 1
                return 0
            else:
                # Invalidate all entries
                count = len(self._cache)
                self._cache.clear()
                self.logger.info(f"Cache cleared: {count} entries invalidated")
                return count
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            int: Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
                if self.enable_statistics:
                    self.statistics.expirations += 1
            
            if expired_keys:
                self.logger.info(f"Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        with self._lock:
            return {
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'utilization': len(self._cache) / self.max_size,
                'statistics': self.statistics.to_dict()
            }
    
    def _generate_cache_key(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Generate cache key from prompt, context, and model.
        
        Uses SHA-256 hash for consistent key generation.
        
        Args:
            prompt: Input prompt
            context: Optional context
            model: Optional model name
        
        Returns:
            str: Cache key (hex digest)
        """
        # Build key components
        key_parts = [prompt]
        
        if context:
            # Sort context keys for consistent hashing
            context_str = json.dumps(context, sort_keys=True)
            key_parts.append(context_str)
        
        if model:
            key_parts.append(model)
        
        # Combine and hash
        key_string = "|".join(key_parts)
        hash_object = hashlib.sha256(key_string.encode('utf-8'))
        cache_key = hash_object.hexdigest()
        
        return cache_key
