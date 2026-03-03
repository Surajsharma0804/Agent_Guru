"""
Self-Improvement Engine for Agent Guru.

This module implements autonomous learning and continuous optimization,
enabling the agent to learn from failures, optimize strategies, evolve prompts,
and measurably improve performance over time.

Key Components:
- Database Schema: SQLite storage for failures, strategies, prompts, metrics
- Failure Analyzer: Captures and categorizes failures for learning
- Strategy Optimizer: Learns optimal approaches for different task types
- Prompt Evolution: Automatically refines prompts based on outcomes
- Performance Tracker: Measures improvement over time
- Meta-Learner: Identifies patterns in success and failure
- Degradation Detector: Detects performance degradation for rollback
- Rollback Manager: Automatically reverts changes when performance degrades

Performance Characteristics:
- Time Complexity: O(1) for recording, O(log n) for querying
- Space Complexity: O(n) where n is number of task executions
- Storage: SQLite with indexed queries for fast retrieval
- Rollback: O(n) where n is changes to rollback
"""

__version__ = "1.0.0"
__all__ = [
    "database_schema",
    "migrations",
    "connection_pool",
    "failure_analyzer",
    "git_integration",
    "degradation_detector",
    "rollback_manager",
    "FailureAnalyzer",
    "FailureType",
    "TaskExecution",
    "FailurePattern",
    "GitIntegration",
    "AuthMethod",
    "CommitData",
    "DegradationDetector",
    "DegradationSeverity",
    "DegradationMetric",
    "DegradationAlert",
    "RollbackManager",
    "ChangeType",
    "ChangeRecord",
    "RollbackResult",
]

# Import key classes for convenience
from Agent_Guru.self_improvement.failure_analyzer import (
    FailureAnalyzer,
    FailureType,
    TaskExecution,
    FailurePattern,
)

from Agent_Guru.self_improvement.git_integration import (
    GitIntegration,
    AuthMethod,
    CommitData,
)

from Agent_Guru.self_improvement.degradation_detector import (
    DegradationDetector,
    DegradationSeverity,
    DegradationMetric,
    DegradationAlert,
)

from Agent_Guru.self_improvement.rollback_manager import (
    RollbackManager,
    ChangeType,
    ChangeRecord,
    RollbackResult,
)

