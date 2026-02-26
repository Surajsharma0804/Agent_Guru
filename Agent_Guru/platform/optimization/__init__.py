"""
Optimization module for Agent Guru Platform Integration.

This module provides optimization utilities including duplicate operation detection,
caching strategies, and performance enhancements.
"""

from Agent_Guru.platform.optimization.duplicate_detector import (
    DuplicateOperationDetector,
    CacheEntry,
    CacheStats,
    Operation,
    OperationType,
    OperationResult,
)
from Agent_Guru.platform.optimization.lru_cache import (
    LRUCache,
    CacheStatistics,
    get_global_cache,
)
from Agent_Guru.platform.optimization.integration import (
    DuplicateAwareFileOperations,
    DuplicateAwareCommandExecutor,
    DuplicateAwareGitOperations,
    DuplicateStats,
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
