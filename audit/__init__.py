"""Agent Guru World-Class Audit System.

This package implements a comprehensive, multi-phase audit, optimization,
and validation toolchain for the Agent Guru codebase.

The audit system executes 9 sequential phases:
1. Repository Intelligence Scan
2. Competitive Analysis
3. Bug and Failure Detection
4. Performance Optimization
5. Architectural Cleanup
6. Integration Validation
7. World-Class Code Quality
8. Deployment and Production Readiness
9. Final Master Audit Report

Each phase writes structured findings to AUDIT_REPORT_MASTER.md at the
repository root.

Modules:
    models: Core data models (Finding, AuditReport, etc.)
    runner: Main orchestrator that executes all phases in DAG order
    report: MasterReportWriter for atomic report generation
    enforcement: Enforcement gate (pytest + ruff + mypy)
    phases: Individual phase implementations

Author: Agent Guru Team
Version: 1.0.0
"""

from audit.models import (
    AuditReport,
    DependencyEdge,
    Finding,
    FindingCategory,
    IntegrationCheckResult,
    ModuleInventory,
    PerformanceMetric,
    RemediationItem,
    Severity,
)

__all__ = [
    "AuditReport",
    "DependencyEdge",
    "Finding",
    "FindingCategory",
    "IntegrationCheckResult",
    "ModuleInventory",
    "PerformanceMetric",
    "RemediationItem",
    "Severity",
]
