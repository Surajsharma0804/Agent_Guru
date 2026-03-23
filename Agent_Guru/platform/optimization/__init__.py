"""
Optimization module for Agent Guru Platform Integration.

This module provides optimization utilities including duplicate operation detection,
caching strategies, and performance enhancements.
"""

from Agent_Guru.platform.optimization.duplicate_detector import (
    CacheEntry,
    CacheStats,
    DuplicateOperationDetector,
    Operation,
    OperationResult,
    OperationType,
)
from Agent_Guru.platform.optimization.integration import (
    DuplicateAwareCommandExecutor,
    DuplicateAwareFileOperations,
    DuplicateAwareGitOperations,
    DuplicateStats,
)
from Agent_Guru.platform.optimization.lru_cache import (
    CacheStatistics,
    LRUCache,
    get_global_cache,
)

__all__ = [
    "DuplicateOperationDetector",
    "CacheEntry",
    "CacheStats",
    "Operation",
    "OperationType",
    "OperationResult",
    "LRUCache",
    "CacheStatistics",
    "get_global_cache",
    "DuplicateAwareFileOperations",
    "DuplicateAwareCommandExecutor",
    "DuplicateAwareGitOperations",
    "DuplicateStats",
]
