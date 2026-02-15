# Design Document: Guru Policy Engine

## Overview

The Guru Policy Engine is a Python-based governance and access control system that provides policy evaluation, RBAC/ABAC enforcement, conflict resolution, audit logging, and performance optimization for the AGENT_GURU AI operating system.

The design follows a modular architecture with clear separation of concerns:
- **Policy Storage Layer**: SQLite-based persistent storage with efficient indexing
- **Evaluation Engine**: Rule evaluation using the `business-rules` library with custom extensions
- **Access Control Layer**: RBAC and ABAC implementations with role hierarchy support
- **Conflict Resolution**: Priority-based resolution with configurable strategies
- **Audit System**: Immutable audit trail with efficient querying
- **Performance Layer**: Multi-level caching and memoization for optimal performance

The system is designed to be:
- **Fast**: Sub-millisecond policy evaluations through aggressive caching
- **Flexible**: Support for complex policies through expressive rule language
- **Auditable**: Comprehensive logging of all decisions for compliance
- **Scalable**: Efficient storage and retrieval for thousands of policies
- **Testable**: Property-based testing ensures correctness across all scenarios

## Integration Points

This system is the ONLY policy evaluation system in AGENT_GURU. All policy decisions must go through this system.

### Dependencies

**Upstream Dependencies** (systems this component depends on):
- **Security System** (guru-security-cryptography): Uses TrustManager for trust scores in trust-based policies

**Downstream Dependencies** (systems that depend on this component):
- **All AGENT_GURU systems**: Use Policy Engine for access control and authorization decisions

### API Contracts

**Security System Integration:**
```python
class PolicyEngine:
    """Policy evaluation engine with trust-based policy support."""
    
    def evaluate_trust_policy(
        self,
        profile_id: str,
        trust_score: TrustScore,
        required_level: float,
        required_relationships: Optional[List[str]] = None
    ) -> AccessDecision:
        """
        Evaluate trust-based policy.
        
        Args:
            profile_id: Identity to evaluate
            trust_score: Trust score from Security System TrustManager
            required_level: Minimum trust score required
            required_relationships: Optional required trust relationships
            
        Returns:
            AccessDecision (ALLOW/DENY)
        """
        pass
```

### Data Flow

1. **Trust-Based Policy Evaluation Flow:**
   - Application requests access for identity
   - Policy Engine calls Security System TrustManager.compute_trust_score()
   - TrustManager returns trust score
   - Policy Engine evaluates trust-based policy rules
   - Policy Engine returns ALLOW/DENY decision
   - Audit Logger records decision

2. **Standard Policy Evaluation Flow:**
   - Application calls PolicyEngine.evaluate_policy()
   - Policy Engine retrieves applicable policies
   - Rule Evaluator evaluates conditions
   - Conflict Resolver handles multiple policies
   - Audit Logger records decision
   - Decision returned to application

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT_GURU Components                     │
│         (LLM Runtime, Memory, Agents, Avatar, etc.)         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Policy Engine API                          │
│  evaluate_policy() / check_access() / test_policy()         │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Cache      │  │   Access     │  │   Audit      │
│   Manager    │  │  Controller  │  │   Logger     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └────────┬────────┴────────┬─────────┘
                ▼                 ▼
        ┌──────────────┐  ┌──────────────┐
        │     Rule     │  │   Conflict   │
        │  Evaluator   │  │   Resolver   │
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┬────────┘
                        ▼
                ┌──────────────┐
                │   Policy     │
                │   Storage    │
                │  (SQLite)    │
                └──────────────┘
```

### Component Interaction Flow

1. **Policy Evaluation Request**: Component calls `evaluate_policy(principal, resource, action, context)`
2. **Cache Check**: Cache_Manager checks for cached result
3. **Cache Hit**: Return cached result immediately
4. **Cache Miss**: Proceed to evaluation
5. **Policy Retrieval**: Fetch applicable policies from storage
6. **Rule Evaluation**: Evaluate each policy's rules against context
7. **Conflict Resolution**: Resolve conflicts if multiple policies apply
8. **Audit Logging**: Log the decision
9. **Cache Update**: Store result in cache
10. **Return Decision**: Return ALLOW/DENY to caller

## Components and Interfaces

### 1. Policy Storage (`policy_storage.py`)

**Responsibility**: Persistent storage and retrieval of policies using SQLite.

**Schema**:
```python
CREATE TABLE policies (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    effect TEXT NOT NULL CHECK(effect IN ('ALLOW', 'DENY')),
    priority INTEGER NOT NULL DEFAULT 0,
    principals TEXT,  -- JSON array
    resources TEXT,   -- JSON array
    actions TEXT,     -- JSON array
    conditions TEXT,  -- JSON rule conditions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_policies_principals ON policies(principals);
CREATE INDEX idx_policies_resources ON policies(resources);
CREATE INDEX idx_policies_actions ON policies(actions);
CREATE INDEX idx_policies_priority ON policies(priority DESC);

CREATE TABLE policy_versions (
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    policy_data TEXT NOT NULL,  -- JSON snapshot
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (policy_id, version)
);

CREATE TABLE roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_role_id TEXT,
    permissions TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_role_id) REFERENCES roles(id)
);

CREATE TABLE role_assignments (
    principal_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (principal_id, role_id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
```

**Interface**:
```python
class PolicyStorage:
    def __init__(self, db_path: str):
        """Initialize storage with SQLite database."""
        
    def create_policy(self, policy: Policy) -> str:
        """Store a new policy and return its ID."""
        
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Retrieve a policy by ID."""
        
    def update_policy(self, policy: Policy) -> None:
        """Update an existing policy and increment version."""
        
    def delete_policy(self, policy_id: str) -> None:
        """Mark a policy as inactive."""
        
    def find_policies(
        self,
        principal: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None
    ) -> List[Policy]:
        """Find policies matching criteria."""
        
    def create_role(self, role: Role) -> str:
        """Create a new role."""
        
    def get_role(self, role_id: str) -> Optional[Role]:
        """Retrieve a role by ID."""
        
    def assign_role(self, principal_id: str, role_id: str) -> None:
        """Assign a role to a principal."""
        
    def get_principal_roles(self, principal_id: str) -> List[Role]:
        """Get all roles assigned to a principal."""
```

### 2. Rule Evaluator (`rule_evaluator.py`)

**Responsibility**: Evaluate policy rules using the `business-rules` library with custom extensions.

**Rule Expression Format**:
```python
{
    "operator": "AND",
    "conditions": [
        {
            "attribute": "principal.department",
            "operator": "equals",
            "value": "engineering"
        },
        {
            "operator": "OR",
            "conditions": [
                {
                    "attribute": "resource.classification",
                    "operator": "in",
                    "value": ["public", "internal"]
                },
                {
                    "attribute": "principal.clearance_level",
                    "operator": "greater_than",
                    "value": 3
                }
            ]
        }
    ]
}
```

**Interface**:
```python
class RuleEvaluator:
    def __init__(self, enable_memoization: bool = True):
        """Initialize evaluator with optional memoization."""
        
    def evaluate(
        self,
        rule: Dict[str, Any],
        context: EvaluationContext
    ) -> bool:
        """Evaluate a rule against context. Returns True if rule matches."""
        
    def evaluate_with_memoization(
        self,
        rule: Dict[str, Any],
        context: EvaluationContext,
        memo_cache: Dict[str, bool]
    ) -> bool:
        """Evaluate with memoization within a request context."""
        
    def validate_rule(self, rule: Dict[str, Any]) -> List[str]:
        """Validate rule structure. Returns list of errors."""
```

**Supported Operators**:
- Boolean: `AND`, `OR`, `NOT`
- Comparison: `equals`, `not_equals`, `greater_than`, `less_than`, `greater_or_equal`, `less_or_equal`
- Collection: `in`, `not_in`, `contains`, `not_contains`
- String: `starts_with`, `ends_with`, `matches` (regex)
- Existence: `exists`, `not_exists`

### 3. Access Controller (`access_controller.py`)

**Responsibility**: Implement RBAC and ABAC patterns for access control decisions.

**Interface**:
```python
class AccessController:
    def __init__(
        self,
        storage: PolicyStorage,
        evaluator: RuleEvaluator,
        resolver: ConflictResolver
    ):
        """Initialize with dependencies."""
        
    def check_access(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """Check if access should be granted."""
        
    def check_rbac(
        self,
        principal: Principal,
        permission: str
    ) -> bool:
        """Check RBAC permission through role hierarchy."""
        
    def check_abac(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Dict[str, Any]
    ) -> AccessDecision:
        """Check ABAC policy based on attributes."""
        
    def get_effective_permissions(
        self,
        principal: Principal
    ) -> Set[str]:
        """Get all permissions for a principal through role hierarchy."""
```

**Data Models**:
```python
@dataclass
class Principal:
    id: str
    attributes: Dict[str, Any]  # department, clearance_level, etc.
    
@dataclass
class Resource:
    id: str
    type: str
    attributes: Dict[str, Any]  # classification, owner, etc.
    
@dataclass
class AccessDecision:
    effect: Literal["ALLOW", "DENY"]
    reason: str
    applicable_policies: List[str]
    evaluation_time_ms: float
```

### 4. Conflict Resolver (`conflict_resolver.py`)

**Responsibility**: Resolve conflicts when multiple policies apply to the same decision.

**Resolution Strategies**:
- **deny-overrides**: Any DENY policy overrides all ALLOW policies
- **allow-overrides**: Any ALLOW policy overrides all DENY policies
- **first-applicable**: First matching policy wins
- **priority-based**: Highest priority policy wins

**Interface**:
```python
class ConflictResolver:
    def __init__(
        self,
        default_strategy: str = "deny-overrides",
        audit_logger: Optional[AuditLogger] = None
    ):
        """Initialize with default strategy."""
        
    def resolve(
        self,
        policies: List[EvaluatedPolicy],
        strategy: Optional[str] = None
    ) -> PolicyDecision:
        """Resolve conflicts among evaluated policies."""
        
    def resolve_by_priority(
        self,
        policies: List[EvaluatedPolicy]
    ) -> PolicyDecision:
        """Resolve using priority values."""
        
    def resolve_deny_overrides(
        self,
        policies: List[EvaluatedPolicy]
    ) -> PolicyDecision:
        """Apply deny-overrides strategy."""
        
    def resolve_allow_overrides(
        self,
        policies: List[EvaluatedPolicy]
    ) -> PolicyDecision:
        """Apply allow-overrides strategy."""
```

**Data Models**:
```python
@dataclass
class EvaluatedPolicy:
    policy_id: str
    effect: Literal["ALLOW", "DENY"]
    priority: int
    conditions_met: bool
    
@dataclass
class PolicyDecision:
    effect: Literal["ALLOW", "DENY"]
    winning_policy_id: str
    conflicting_policies: List[str]
    resolution_strategy: str
```

### 5. Audit Logger (`audit_logger.py`)

**Responsibility**: Maintain immutable audit trail of all policy decisions.

**Schema**:
```python
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    principal_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    effect TEXT NOT NULL CHECK(effect IN ('ALLOW', 'DENY')),
    applicable_policies TEXT NOT NULL,  -- JSON array
    context_hash TEXT NOT NULL,  -- SHA256 of context for tamper detection
    evaluation_time_ms REAL NOT NULL,
    decision_reason TEXT
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_principal ON audit_log(principal_id);
CREATE INDEX idx_audit_resource ON audit_log(resource_id);
CREATE INDEX idx_audit_effect ON audit_log(effect);
```

**Interface**:
```python
class AuditLogger:
    def __init__(self, db_path: str, retention_days: int = 90):
        """Initialize audit logger with retention policy."""
        
    def log_decision(
        self,
        principal_id: str,
        resource_id: str,
        resource_type: str,
        action: str,
        decision: AccessDecision,
        context: Dict[str, Any]
    ) -> str:
        """Log an access decision. Returns audit record ID."""
        
    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        principal_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        effect: Optional[str] = None,
        limit: int = 1000
    ) -> List[AuditRecord]:
        """Query audit logs with filters."""
        
    def verify_integrity(
        self,
        record_id: str
    ) -> bool:
        """Verify audit record has not been tampered with."""
        
    def archive_old_records(self) -> int:
        """Archive records older than retention period. Returns count."""
```

### 6. Cache Manager (`cache_manager.py`)

**Responsibility**: Optimize performance through caching and cache invalidation.

**Caching Strategy**:
- **L1 Cache**: In-memory LRU cache for hot policy evaluations
- **Cache Key**: `SHA256(principal_id + resource_id + action + context_hash)`
- **TTL**: Configurable per policy (default 300 seconds)
- **Invalidation**: On policy modification, role changes, or explicit flush

**Interface**:
```python
class CacheManager:
    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 300
    ):
        """Initialize cache with size limit and TTL."""
        
    def get(
        self,
        cache_key: str
    ) -> Optional[AccessDecision]:
        """Get cached decision if valid."""
        
    def put(
        self,
        cache_key: str,
        decision: AccessDecision,
        ttl: Optional[int] = None
    ) -> None:
        """Cache a decision with optional custom TTL."""
        
    def invalidate(
        self,
        pattern: Optional[str] = None
    ) -> int:
        """Invalidate cache entries matching pattern. Returns count."""
        
    def invalidate_for_policy(
        self,
        policy_id: str
    ) -> int:
        """Invalidate all entries affected by a policy."""
        
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        
    def compute_cache_key(
        self,
        principal_id: str,
        resource_id: str,
        action: str,
        context: Dict[str, Any]
    ) -> str:
        """Compute cache key from request parameters."""
```

**Data Models**:
```python
@dataclass
class CacheStats:
    hits: int
    misses: int
    evictions: int
    size: int
    hit_rate: float
```

### 7. Policy Engine API (`policy_engine.py`)

**Responsibility**: Main API facade that orchestrates all components.

**Interface**:
```python
class PolicyEngine:
    def __init__(
        self,
        db_path: str,
        cache_size: int = 10000,
        enable_caching: bool = True,
        enable_memoization: bool = True
    ):
        """Initialize policy engine with configuration."""
        
    def evaluate_policy(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """Evaluate policy and return access decision."""
        
    async def evaluate_policy_async(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """Async version of evaluate_policy."""
        
    def test_policy(
        self,
        policy: Policy,
        test_cases: List[TestCase]
    ) -> TestResults:
        """Test a policy against test cases."""
        
    def create_policy(self, policy: Policy) -> str:
        """Create a new policy."""
        
    def update_policy(self, policy: Policy) -> None:
        """Update an existing policy."""
        
    def delete_policy(self, policy_id: str) -> None:
        """Delete a policy."""
        
    def create_role(self, role: Role) -> str:
        """Create a new role."""
        
    def assign_role(self, principal_id: str, role_id: str) -> None:
        """Assign a role to a principal."""
        
    def query_audit_logs(
        self,
        filters: AuditQueryFilters
    ) -> List[AuditRecord]:
        """Query audit logs."""
        
    def get_cache_stats(self) -> CacheStats:
        """Get cache performance statistics."""
```

## Data Models

### Core Models (`models.py`)

```python
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

@dataclass
class Policy:
    id: str
    version: int
    name: str
    description: str
    effect: Literal["ALLOW", "DENY"]
    priority: int
    principals: List[str]  # Can include wildcards
    resources: List[str]   # Can include wildcards
    actions: List[str]     # Can include wildcards
    conditions: Dict[str, Any]  # Rule expression
    created_at: datetime
    updated_at: datetime
    active: bool = True

@dataclass
class Role:
    id: str
    name: str
    parent_role_id: Optional[str]
    permissions: List[str]
    created_at: datetime

@dataclass
class EvaluationContext:
    principal: Principal
    resource: Resource
    action: str
    environment: Dict[str, Any]  # time, location, system state
    
    def get_attribute(self, path: str) -> Any:
        """Get attribute by dot-notation path (e.g., 'principal.department')."""

@dataclass
class TestCase:
    name: str
    principal: Principal
    resource: Resource
    action: str
    context: Dict[str, Any]
    expected_effect: Literal["ALLOW", "DENY"]

@dataclass
class TestResults:
    passed: int
    failed: int
    failures: List[TestFailure]

@dataclass
class TestFailure:
    test_case: TestCase
    expected: str
    actual: str
    reason: str
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Policy Storage Round Trip
*For any* valid policy object, storing it and then retrieving it by ID should produce an equivalent policy with the same attributes and an assigned unique ID.
**Validates: Requirements 1.1, 1.4**

### Property 2: Policy Schema Validation
*For any* policy object, validation should accept it if and only if it conforms to the policy schema (has required fields, correct types, valid enum values).
**Validates: Requirements 1.2**

### Property 3: Policy Versioning Monotonicity
*For any* policy, updating it should increment the version number by exactly 1, and the version history should contain all previous versions in order.
**Validates: Requirements 1.5**

### Property 4: Policy Query Correctness
*For any* set of policies and query criteria (principal, resource, action), all returned policies should match the criteria, and all policies matching the criteria should be returned.
**Validates: Requirements 1.6, 5.1**

### Property 5: Boolean Logic Correctness
*For any* boolean expression (AND, OR, NOT) and evaluation context, the rule evaluator should produce results consistent with standard boolean logic truth tables.
**Validates: Requirements 2.2, 4.4**

### Property 6: Comparison Operator Correctness
*For any* comparison operator (equals, greater_than, less_than, in, etc.) and pair of values, the rule evaluator should produce results consistent with the operator's mathematical definition.
**Validates: Requirements 2.3**

### Property 7: Attribute Resolution Correctness
*For any* attribute path (e.g., "principal.department") and evaluation context, the rule evaluator should retrieve the correct value from the context or return an appropriate error if the attribute doesn't exist.
**Validates: Requirements 2.4**

### Property 8: Nested Rule Evaluation
*For any* rule with nested conditions (up to arbitrary depth), the rule evaluator should correctly evaluate the nested structure according to boolean logic.
**Validates: Requirements 2.5**

### Property 9: Rule Evaluation Error Handling
*For any* invalid rule or context that causes an evaluation error, the rule evaluator should return a descriptive error message and not crash.
**Validates: Requirements 2.6**

### Property 10: Role Permission Inheritance
*For any* principal with multiple roles (including roles with parent roles), the effective permissions should be the union of all permissions from all roles in the hierarchy.
**Validates: Requirements 3.1, 3.2, 3.3, 3.5**

### Property 11: RBAC Permission Check
*For any* principal and required permission, access should be granted if and only if at least one of the principal's roles (or their ancestors) grants that permission.
**Validates: Requirements 3.4**

### Property 12: Attribute-Based Policy Evaluation
*For any* policy with attribute conditions (on principal, resource, or environment) and evaluation context, the policy should match if and only if all attribute conditions are satisfied.
**Validates: Requirements 4.1, 4.2, 4.3, 4.5**

### Property 13: Missing Attribute Strategy
*For any* policy evaluation where an attribute is missing, the result should follow the configured missing attribute strategy (deny, allow, or error).
**Validates: Requirements 4.6**

### Property 14: Priority-Based Conflict Resolution
*For any* set of applicable policies with different priorities, the conflict resolver should select the policy with the highest priority value.
**Validates: Requirements 5.2**

### Property 15: Deny-Overrides Strategy
*For any* set of applicable policies with equal priority using deny-overrides strategy, if any policy has effect DENY, the final decision should be DENY.
**Validates: Requirements 5.3, 5.6**

### Property 16: Allow-Overrides Strategy
*For any* set of applicable policies with equal priority using allow-overrides strategy, if any policy has effect ALLOW, the final decision should be ALLOW.
**Validates: Requirements 5.3**

### Property 17: Conflict Resolution Logging
*For any* conflict resolution, the audit log should contain a record with all conflicting policy IDs and the resolution strategy used.
**Validates: Requirements 5.5**

### Property 18: Audit Record Completeness
*For any* policy decision, the audit record should contain all required fields: timestamp, principal_id, resource_id, action, effect, applicable_policies, and evaluation_time_ms.
**Validates: Requirements 6.1**

### Property 19: Audit Query Correctness
*For any* audit query with filters (time range, principal, resource, action, effect), all returned records should match the filters, and the results should be ordered by timestamp descending.
**Validates: Requirements 6.3**

### Property 20: Audit Record Integrity
*For any* audit record, verifying its integrity should succeed if the record has not been modified, and fail if any field has been tampered with.
**Validates: Requirements 6.4**

### Property 21: Audit Retention Policy
*For any* audit records older than the retention period, running archival should move or delete those records and leave newer records untouched.
**Validates: Requirements 6.5, 6.6**

### Property 22: Cache Hit Consistency
*For any* policy evaluation that is cached, subsequent identical requests (same principal, resource, action, context) should return the same decision from cache without re-evaluation.
**Validates: Requirements 7.1, 7.2**

### Property 23: Cache TTL Expiration
*For any* cached policy evaluation, requesting it after the TTL has expired should result in a cache miss and re-evaluation.
**Validates: Requirements 7.3**

### Property 24: Cache Invalidation on Policy Change
*For any* policy modification or role change, all cache entries that could be affected by that policy or role should be invalidated.
**Validates: Requirements 3.6, 7.4**

### Property 25: LRU Cache Eviction
*For any* cache at maximum size, adding a new entry should evict the least recently used entry, and the cache size should remain at the maximum.
**Validates: Requirements 7.5**

### Property 26: Cache Statistics Accuracy
*For any* sequence of cache operations (hits, misses, evictions), the cache statistics should accurately reflect the counts and hit rate.
**Validates: Requirements 7.6**

### Property 27: Memoization Consistency
*For any* rule evaluation within a single evaluation context, evaluating the same rule multiple times should return the same result, and the result should match non-memoized evaluation.
**Validates: Requirements 8.1, 8.2, 8.5**

### Property 28: Memoization Context Isolation
*For any* two different evaluation contexts, memoization results from one context should not affect evaluations in the other context.
**Validates: Requirements 8.3**

### Property 29: Selective Memoization
*For any* rule marked as non-memoizable (has side effects), the rule should be evaluated fresh each time even within the same context.
**Validates: Requirements 8.4**

### Property 30: Test Mode Isolation
*For any* policy evaluation in test mode, no persistent changes should be made (no audit logs, no cache updates, no policy modifications).
**Validates: Requirements 9.1**

### Property 31: Test Case Validation
*For any* policy and set of test cases, the test results should correctly identify which test cases passed (actual matches expected) and which failed (actual differs from expected).
**Validates: Requirements 9.3**

### Property 32: Dry-Run Mode
*For any* policy evaluation in dry-run mode, the evaluation should complete and return a decision, but the decision should not be enforced or logged as a real decision.
**Validates: Requirements 9.4**

### Property 33: Validation Error Messages
*For any* invalid policy that fails validation, the error message should include the specific field or condition that caused the validation failure.
**Validates: Requirements 9.5**

### Property 34: Async Evaluation Equivalence
*For any* policy evaluation request, the async version should return the same decision as the synchronous version for identical inputs.
**Validates: Requirements 10.2**

### Property 35: Event Emission Completeness
*For any* policy decision, an event should be emitted containing the decision details (principal, resource, action, effect, timestamp).
**Validates: Requirements 10.6**

## Error Handling

### Error Categories

1. **Validation Errors**: Invalid policy structure, missing required fields, type mismatches
   - Return descriptive error with field name and expected format
   - HTTP 400 Bad Request for API calls
   - Do not store invalid policies

2. **Evaluation Errors**: Missing attributes, invalid rule expressions, circular role dependencies
   - Log error with full context
   - Return DENY decision (fail-safe)
   - Include error details in audit log

3. **Storage Errors**: Database connection failures, disk full, corruption
   - Retry with exponential backoff (3 attempts)
   - Fall back to in-memory storage if persistent storage fails
   - Alert monitoring system

4. **Cache Errors**: Cache corruption, memory pressure
   - Clear corrupted cache entries
   - Continue operation without cache (degraded performance)
   - Log warning

5. **Integration Errors**: External attribute provider unavailable, timeout
   - Apply missing attribute strategy from policy
   - Log warning with provider details
   - Continue with available attributes

### Error Recovery Strategies

```python
class ErrorRecovery:
    """Error recovery strategies for policy engine."""
    
    @staticmethod
    def handle_storage_error(error: Exception, operation: str) -> None:
        """Handle storage errors with retry and fallback."""
        # Retry with exponential backoff
        # Fall back to in-memory storage
        # Alert monitoring
        
    @staticmethod
    def handle_evaluation_error(
        error: Exception,
        context: EvaluationContext
    ) -> AccessDecision:
        """Handle evaluation errors with fail-safe deny."""
        # Log error with full context
        # Return DENY decision
        # Include error in audit log
        
    @staticmethod
    def handle_cache_error(error: Exception) -> None:
        """Handle cache errors gracefully."""
        # Clear corrupted entries
        # Continue without cache
        # Log warning
```

### Fail-Safe Defaults

- **Unknown principal**: DENY
- **Unknown resource**: DENY
- **Missing required attribute**: Follow policy's missing attribute strategy (default: DENY)
- **Evaluation error**: DENY
- **Storage unavailable**: Use in-memory fallback, DENY for new requests if fallback fails
- **Cache unavailable**: Continue without cache (performance degradation only)

## Testing Strategy

### Dual Testing Approach

The Guru Policy Engine uses both unit testing and property-based testing for comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Specific policy evaluation scenarios
- Error conditions and edge cases
- Integration with SQLite storage
- Cache behavior with specific sequences
- Audit log querying with known data

**Property-Based Tests**: Verify universal properties across all inputs
- Use `hypothesis` library for Python property-based testing
- Minimum 100 iterations per property test
- Each property test references its design document property
- Tag format: `# Feature: guru-policy-engine, Property {number}: {property_text}`

### Property-Based Testing Configuration

**Library**: `hypothesis` (Python property-based testing library)

**Configuration**:
```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(
    policy=st.builds(Policy, ...),
    context=st.builds(EvaluationContext, ...)
)
def test_property_1_policy_storage_round_trip(policy, context):
    """
    Feature: guru-policy-engine
    Property 1: Policy Storage Round Trip
    
    For any valid policy object, storing it and then retrieving it by ID
    should produce an equivalent policy with the same attributes and an
    assigned unique ID.
    """
    # Test implementation
```

**Strategy Definitions**:
```python
# Custom strategies for generating test data
policy_strategy = st.builds(
    Policy,
    id=st.uuids().map(str),
    version=st.integers(min_value=1),
    name=st.text(min_size=1, max_size=100),
    effect=st.sampled_from(["ALLOW", "DENY"]),
    priority=st.integers(min_value=0, max_value=100),
    principals=st.lists(st.text(min_size=1), min_size=1),
    resources=st.lists(st.text(min_size=1), min_size=1),
    actions=st.lists(st.text(min_size=1), min_size=1),
    conditions=rule_expression_strategy,
    active=st.booleans()
)

rule_expression_strategy = st.recursive(
    st.builds(
        dict,
        attribute=st.text(min_size=1),
        operator=st.sampled_from(["equals", "greater_than", "in"]),
        value=st.one_of(st.integers(), st.text(), st.lists(st.text()))
    ),
    lambda children: st.builds(
        dict,
        operator=st.sampled_from(["AND", "OR", "NOT"]),
        conditions=st.lists(children, min_size=1, max_size=5)
    ),
    max_leaves=10
)
```

### Test Organization

```
tests/
├── unit/
│   ├── test_policy_storage.py
│   ├── test_rule_evaluator.py
│   ├── test_access_controller.py
│   ├── test_conflict_resolver.py
│   ├── test_audit_logger.py
│   ├── test_cache_manager.py
│   └── test_policy_engine.py
├── property/
│   ├── test_properties_storage.py      # Properties 1-4
│   ├── test_properties_evaluation.py   # Properties 5-9
│   ├── test_properties_rbac.py         # Properties 10-11
│   ├── test_properties_abac.py         # Properties 12-13
│   ├── test_properties_conflict.py     # Properties 14-17
│   ├── test_properties_audit.py        # Properties 18-21
│   ├── test_properties_cache.py        # Properties 22-26
│   ├── test_properties_memoization.py  # Properties 27-29
│   ├── test_properties_testing.py      # Properties 30-33
│   └── test_properties_integration.py  # Properties 34-35
├── integration/
│   ├── test_llm_integration.py
│   ├── test_memory_integration.py
│   └── test_agent_integration.py
└── conftest.py  # Shared fixtures and strategies
```

### Coverage Requirements

- **Unit test coverage**: ≥90% line coverage
- **Property test coverage**: All 35 correctness properties must have corresponding tests
- **Integration test coverage**: All AGENT_GURU component integrations
- **Performance tests**: Cache hit rates, evaluation latency, storage throughput

### Testing Tools

- **pytest**: Test runner and framework
- **pytest-cov**: Coverage measurement
- **hypothesis**: Property-based testing
- **pytest-benchmark**: Performance benchmarking
- **pytest-asyncio**: Async test support
- **freezegun**: Time manipulation for TTL testing
- **pytest-mock**: Mocking for external dependencies

### Continuous Testing

- Run unit tests on every commit
- Run property tests on every commit (100 examples each)
- Run integration tests on pull requests
- Run performance benchmarks weekly
- Track coverage trends over time
- Fail CI if coverage drops below 90%
