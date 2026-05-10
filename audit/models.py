"""Core data models for the Agent Guru audit system.

This module defines all dataclasses and enums used throughout the audit
pipeline. All models use complete type annotations with `from __future__
import annotations` for forward references.

Models:
    Severity: Enum for finding severity levels
    FindingCategory: Enum for finding categories
    Finding: A single audit finding with full traceability
    ModuleInventory: Inventory entry for a single Python module
    DependencyEdge: A directed dependency edge in the module DAG
    PerformanceMetric: A before/after performance measurement
    RemediationItem: A prioritized remediation backlog item
    IntegrationCheckResult: Result of a single integration validation check
    AuditReport: The complete audit report state

Author: Agent Guru Team
Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Severity levels for audit findings.

    Attributes:
        CRITICAL: Critical issue requiring immediate attention
        HIGH: High-priority issue
        MEDIUM: Medium-priority issue
        LOW: Low-priority issue
        INFO: Informational finding

    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingCategory(str, Enum):
    """Categories for audit findings.

    Attributes:
        COMPILE_ERROR: Python compilation error
        TYPE_ERROR: Type checking error (mypy)
        LINT_VIOLATION: Linting violation (ruff)
        SECURITY_ISSUE: Security vulnerability (bandit)
        CIRCULAR_IMPORT: Circular import dependency
        BROKEN_IMPORT: Import of non-existent module/symbol
        ASYNC_ANTIPATTERN: Async/await anti-pattern
        RACE_CONDITION: Potential race condition
        RESOURCE_LEAK: Resource leak (file, connection, memory)
        UNUSED_CODE: Unused import or variable
        DUPLICATE_IMPL: Duplicate implementation
        PLATFORM_GUARD: Missing platform-specific import guard
        PERFORMANCE: Performance issue
        DEAD_CODE: Dead code (unreachable)
        MISSING_DOCSTRING: Missing docstring
        LAYER_VIOLATION: Architectural layer violation
        HARDCODED_SECRET: Hardcoded secret or credential

    """

    COMPILE_ERROR = "COMPILE_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    LINT_VIOLATION = "LINT_VIOLATION"
    SECURITY_ISSUE = "SECURITY_ISSUE"
    CIRCULAR_IMPORT = "CIRCULAR_IMPORT"
    BROKEN_IMPORT = "BROKEN_IMPORT"
    ASYNC_ANTIPATTERN = "ASYNC_ANTIPATTERN"
    RACE_CONDITION = "RACE_CONDITION"
    RESOURCE_LEAK = "RESOURCE_LEAK"
    UNUSED_CODE = "UNUSED_CODE"
    DUPLICATE_IMPL = "DUPLICATE_IMPL"
    PLATFORM_GUARD = "PLATFORM_GUARD"
    PERFORMANCE = "PERFORMANCE"
    DEAD_CODE = "DEAD_CODE"
    MISSING_DOCSTRING = "MISSING_DOCSTRING"
    LAYER_VIOLATION = "LAYER_VIOLATION"
    HARDCODED_SECRET = "HARDCODED_SECRET"


@dataclass
class Finding:
    """A single audit finding with full traceability.

    Each finding represents a specific issue detected during the audit,
    with complete information for remediation and tracking.

    Attributes:
        id: Unique finding identifier (e.g., "BUG-001")
        phase: Audit phase number (1-9)
        category: Finding category
        severity: Finding severity
        file_path: Relative path to the affected file
        line_number: Line number of the finding (0 if file-level)
        rule: Tool rule code (e.g., "E501", "B101", "mypy:error")
        description: Human-readable description of the finding
        remediation: Specific remediation action taken or required
        fixed: Whether the finding has been fixed

    Example:
        >>> finding = Finding(
        ...     id="BUG-001",
        ...     phase=3,
        ...     category=FindingCategory.TYPE_ERROR,
        ...     severity=Severity.HIGH,
        ...     file_path="Agent_Guru/speech/wake_word.py",
        ...     line_number=42,
        ...     rule="mypy:error",
        ...     description="Missing return type annotation",
        ...     remediation="Add -> bool return type",
        ...     fixed=False
        ... )

    """

    id: str
    phase: int
    category: FindingCategory
    severity: Severity
    file_path: str
    line_number: int
    rule: str
    description: str
    remediation: str = ""
    fixed: bool = False


@dataclass
class ModuleInventory:
    """Inventory entry for a single Python module.

    Captures complete metadata about a Python module including its size,
    public API surface, and dependencies.

    Attributes:
        file_path: Relative path from repo root
        line_count: Total lines including blanks and comments
        public_class_count: Number of public classes (not prefixed with _)
        public_function_count: Number of public functions
        import_count: Number of import statements
        imports: List of imported module paths

    Example:
        >>> inventory = ModuleInventory(
        ...     file_path="Agent_Guru/speech/wake_word.py",
        ...     line_count=250,
        ...     public_class_count=2,
        ...     public_function_count=5,
        ...     import_count=8,
        ...     imports=["numpy", "pvporcupine", "Agent_Guru.speech.audio"]
        ... )

    """

    file_path: str
    line_count: int
    public_class_count: int
    public_function_count: int
    import_count: int
    imports: list[str] = field(default_factory=list)


@dataclass
class DependencyEdge:
    """A directed dependency edge in the module DAG.

    Represents a single import dependency between two modules, used to
    construct the module dependency graph and detect circular imports.

    Attributes:
        source: Importing module path
        target: Imported module path
        import_type: "import" or "from"
        symbol: Specific symbol imported (empty for module-level import)

    Example:
        >>> edge = DependencyEdge(
        ...     source="Agent_Guru/speech/wake_word.py",
        ...     target="Agent_Guru/speech/audio/capture.py",
        ...     import_type="from",
        ...     symbol="MicrophoneCapture"
        ... )

    """

    source: str
    target: str
    import_type: str
    symbol: str = ""


@dataclass
class PerformanceMetric:
    """A before/after performance measurement.

    Tracks performance improvements from optimization work, comparing
    measured values against targets from quality.md.

    Attributes:
        metric_name: Human-readable metric name
        unit: Measurement unit (e.g., "ms", "MB", "%")
        before_p95: P95 value before optimization
        after_p95: P95 value after optimization
        target: Target value from quality.md
        meets_target: Whether after_p95 meets the target

    Example:
        >>> metric = PerformanceMetric(
        ...     metric_name="Wake word detection latency",
        ...     unit="ms",
        ...     before_p95=250.0,
        ...     after_p95=180.0,
        ...     target=200.0,
        ...     meets_target=True
        ... )

    """

    metric_name: str
    unit: str
    before_p95: float
    after_p95: float
    target: float
    meets_target: bool


@dataclass
class RemediationItem:
    """A prioritized remediation backlog item.

    Represents a required change identified during the audit, with
    priority scoring based on competitive impact.

    Attributes:
        id: Unique item identifier
        phase: Audit phase that identified this item
        severity: Item severity
        affected_module: Module path affected
        description: Description of the required change
        expected_improvement: Expected metric improvement with unit
        estimated_effort_hours: Estimated effort in hours
        competitive_impact_score: Gap magnitude x platforms affected

    Example:
        >>> item = RemediationItem(
        ...     id="REM-001",
        ...     phase=2,
        ...     severity=Severity.HIGH,
        ...     affected_module="Agent_Guru/speech/wake_word.py",
        ...     description="Replace Vosk with pvporcupine",
        ...     expected_improvement="-70ms at P95 wake word latency",
        ...     estimated_effort_hours=8.0,
        ...     competitive_impact_score=42.5
        ... )

    """

    id: str
    phase: int
    severity: Severity
    affected_module: str
    description: str
    expected_improvement: str
    estimated_effort_hours: float
    competitive_impact_score: float


@dataclass
class IntegrationCheckResult:
    """Result of a single integration validation check.

    Records the outcome of one of the 12 integration validation checks
    from Phase 6.

    Attributes:
        check_id: Check identifier (1-12)
        description: Human-readable check description
        passed: Whether the check passed
        details: Additional details or error message

    Example:
        >>> result = IntegrationCheckResult(
        ...     check_id=1,
        ...     description="Integration orchestrator startup",
        ...     passed=True,
        ...     details="All 11 subsystems initialized successfully"
        ... )

    """

    check_id: int
    description: str
    passed: bool
    details: str = ""


@dataclass
class AuditReport:
    """The complete audit report state, written to AUDIT_REPORT_MASTER.md.

    Aggregates all findings, metrics, and results from all 9 audit phases
    into a single comprehensive report.

    Attributes:
        findings: All findings across all phases
        inventory: Module inventory from Phase 1
        dependency_edges: Module dependency DAG edges
        performance_metrics: Before/after performance table
        remediation_backlog: Prioritized remediation items
        integration_results: Integration validation check results
        coverage_by_module: Per-module test coverage percentages
        phase1_detailed_content: Detailed Phase 1 content (DAG, pipeline, etc.)

    Example:
        >>> report = AuditReport(
        ...     findings=[finding1, finding2],
        ...     inventory=[inv1, inv2],
        ...     dependency_edges=[edge1, edge2],
        ...     performance_metrics=[metric1],
        ...     remediation_backlog=[item1],
        ...     integration_results=[result1],
        ...     coverage_by_module={"Agent_Guru/speech/wake_word.py": 85.5}
        ... )

    """

    findings: list[Finding] = field(default_factory=list)
    inventory: list[ModuleInventory] = field(default_factory=list)
    dependency_edges: list[DependencyEdge] = field(default_factory=list)
    performance_metrics: list[PerformanceMetric] = field(default_factory=list)
    remediation_backlog: list[RemediationItem] = field(default_factory=list)
    integration_results: list[IntegrationCheckResult] = field(default_factory=list)
    coverage_by_module: dict[str, float] = field(default_factory=dict)
    phase1_detailed_content: str = ""  # Detailed Phase 1 markdown content
