"""
Module: Agent_Guru.platform.integration
Purpose: Component integration clients for Platform Integration System

This module provides client interfaces for integrating with other Agent_Guru
components including Goal Manager, Memory System, Verifier System, and
Self-Improvement Engine.

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

from Agent_Guru.platform.integration.goal_manager_client import (
    GoalManagerClient,
    TaskCompletionNotification,
    OperationResult,
    NotificationStatus,
)

__all__ = [
    "GoalManagerClient",
    "TaskCompletionNotification",
    "OperationResult",
    "NotificationStatus",
]
