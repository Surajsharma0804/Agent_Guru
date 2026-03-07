"""
Validation module for self-improvement engine.

Provides validation scripts and utilities for testing the self-improvement
engine's learning capabilities and improvement guarantees.
"""

from Agent_Guru.self_improvement.validation.run_100_task_cycle import (
    run_100_task_cycle,
    ValidationReport,
    TaskResult,
)

__all__ = [
    "run_100_task_cycle",
    "ValidationReport",
    "TaskResult",
]
