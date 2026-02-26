"""
Module: agent_guru.platform.monitoring
Purpose: Real-time resource monitoring with alerting and throttling

This module provides comprehensive system resource monitoring including:
- CPU usage (per-core and aggregate)
- Memory usage (RSS, VMS, swap)
- Disk usage (all volumes)
- Network bandwidth tracking
- GPU usage (when available)
- Alert system with history tracking
- Self-Improvement Engine integration

Performance Characteristics:
    - Time Complexity: O(1) per metric query
    - Space Complexity: O(history_size) for historical data
    - Sampling Overhead: <1% CPU usage
    - Latency: <10ms per snapshot

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

from .resource_monitor import (
    ResourceMonitor,
    ResourceMonitorConfig,
    ResourceSnapshot,
    ResourceLimits,
    ResourceAlert,
    ResourceType,
    AlertSeverity,
    ProcessResourceUsage,
    DiskUsage,
    NetworkIO,
    GPUUsage,
)

from .self_improvement_integration import (
    SelfImprovementIntegration,
    SelfImprovementMetric,
    MetricType,
)

__all__ = [
    "ResourceMonitor",
    "ResourceMonitorConfig",
    "ResourceSnapshot",
    "ResourceLimits",
    "ResourceAlert",
    "ResourceType",
    "AlertSeverity",
    "ProcessResourceUsage",
    "DiskUsage",
    "NetworkIO",
    "GPUUsage",
    "SelfImprovementIntegration",
    "SelfImprovementMetric",
    "MetricType",
]
