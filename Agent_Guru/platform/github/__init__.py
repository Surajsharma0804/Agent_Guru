"""
GitHub Integration Module

This module provides automated Git operations for Agent Guru, including:
- Repository operations (status, add, commit, push, pull)
- Automatic commit and push after task completion
- Conflict resolution with pull-rebase
- Commit message generation
- Branch management
- Commit batching (max 1 push per minute)
- Task completion detection

Performance Characteristics:
    - Time Complexity: O(n) where n is number of changed files
    - Space Complexity: O(n) for file list storage
    - Latency: <1s for status check, <5s for commit+push

Author: Agent Guru Platform Team
Date: 2025
Version: 1.0.0
"""

from Agent_Guru.platform.github.auto_commit import (
    AutoCommitConfig,
    AutoCommitManager,
    PendingCommit,
    TaskContext,
)
from Agent_Guru.platform.github.integrator import (
    GitAuthenticationError,
    GitConflictError,
    GitHubIntegrator,
    GitOperationResult,
    GitRemoteError,
    GitRepositoryStatus,
)

__all__ = [
    # Integrator
    "GitHubIntegrator",
    "GitOperationResult",
    "GitRepositoryStatus",
    "GitConflictError",
    "GitAuthenticationError",
    "GitRemoteError",
    # Auto-commit
    "AutoCommitManager",
    "AutoCommitConfig",
    "TaskContext",
    "PendingCommit",
]
