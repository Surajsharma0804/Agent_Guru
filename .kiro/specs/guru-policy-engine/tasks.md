# Implementation Plan: Guru Policy Engine

## Overview

This implementation plan breaks down the Guru Policy Engine into incremental, testable components. The approach follows a bottom-up strategy: build core data models and storage first, then evaluation logic, then access control, then optimization layers, and finally integration. Each major component includes property-based tests to ensure correctness.

The implementation uses Python with the following key libraries:
- **SQLite**: Persistent storage for policies, roles, and audit logs
- **hypothesis**: Property-based testing framework
- **pytest**: Test runner and framework
- **dataclasses**: Type-safe data models
- **typing**: Type hints for all interfaces

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create directory structure: `guru_policy_engine/` with subdirectories for `storage/`, `evaluation/`, `access/`, `audit/`, `cache/`, `models/`
  - Create `pyproject.toml` with dependencies: `hypothesis`, `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-benchmark`
  - Create `conftest.py` with shared fixtures and hypothesis strategies
  - Set up `.gitignore` for Python project
  - _Requirements: All_

- [ ] 2. Implement core data models
  - [ ] 2.1 Create data models in `models.py`
    - Define `Policy`, `Role`, `Principal`, `Resource`, `EvaluationContext` dataclasses
    - Define `AccessDecision`, `PolicyDecision`, `AuditRecord` dataclasses
    - Define `TestCase`, `TestResults`, `CacheStats` dataclasses
    - Implement `EvaluationContext.get_attribute()` method for dot-notation attribute access
    - Add type hints and docstrings for all models
    - _Requirements: 1.1, 3.1, 4.1, 4.2, 6.1, 7.6, 9.2_

  - [ ]* 2.2 Write property test for attribute path resolution
    - **Property 7: Attribute Resolution Correctness**
    - **Validates: Requirements 2.4**
    - Generate random attribute paths and contexts, verify correct value retrieval

- [ ] 3. Implement policy storage layer
  - [ ] 3.1 Create `PolicyStorage` class in `storage/policy_storage.py`
    - Implement SQLite schema creation with indexes
    - Implement `create_policy()`, `get_policy()`, `update_policy()`, `delete_policy()`
    - Implement `find_policies()` with filtering by principal, resource, action
    - Implement policy versioning in `policy_versions` table
    - Add connection pooling and error handling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 3.2 Write property test for policy storage round trip
    - **Property 1: Policy Storage Round Trip**
    - **Validates: Requirements 1.1, 1.4**
    - Generate random policies, store and retrieve, verify equivalence

  - [ ]* 3.3 Write property test for policy versioning
    - **Property 3: Policy Versioning Monotonicity**
    - **Validates: Requirements 1.5**
    - Generate random policies, update multiple times, verify version increments

  - [ ]* 3.4 Write property test for policy query correctness
    - **Property 4: Policy Query Correctness**
    - **Validates: Requirements 1.6, 5.1**
    - Generate random policies and queries, verify all matching policies returned

  - [ ] 3.5 Implement role storage in `PolicyStorage`
    - Implement `create_role()`, `get_role()`, `assign_role()`, `get_principal_roles()`
    - Support role hierarchy with parent_role_id
    - Add indexes for efficient role lookups
    - _Requirements: 3.1, 3.3_

  - [ ]* 3.6 Write property test for role permission inheritance
    - **Property 10: Role Permission Inheritance**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
    - Generate random role hierarchies, verify permission union

- [ ] 4. Implement rule evaluator
  - [ ] 4.1 Create `RuleEvaluator` class in `evaluation/rule_evaluator.py`
    - Implement boolean operators: AND, OR, NOT
    - Implement comparison operators: equals, not_equals, greater_than, less_than, greater_or_equal, less_or_equal
    - Implement collection operators: in, not_in, contains, not_contains
    - Implement string operators: starts_with, ends_with, matches (regex)
    - Implement existence operators: exists, not_exists
    - Support nested rule conditions with recursive evaluation
    - Add error handling with descriptive messages
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 4.2 Write property test for boolean logic correctness
    - **Property 5: Boolean Logic Correctness**
    - **Validates: Requirements 2.2, 4.4**
    - Generate random boolean expressions, verify truth table consistency

  - [ ]* 4.3 Write property test for comparison operators
    - **Property 6: Comparison Operator Correctness**
    - **Validates: Requirements 2.3**
    - Generate random values and operators, verify mathematical correctness

  - [ ]* 4.4 Write property test for nested rule evaluation
    - **Property 8: Nested Rule Evaluation**
    - **Validates: Requirements 2.5**
    - Generate rules with varying nesting depths, verify correct evaluation

  - [ ]* 4.5 Write property test for error handling
    - **Property 9: Rule Evaluation Error Handling**
    - **Validates: Requirements 2.6**
    - Generate invalid rules and contexts, verify descriptive errors returned

  - [ ] 4.6 Add memoization support to `RuleEvaluator`
    - Implement `evaluate_with_memoization()` method
    - Support per-context memoization cache
    - Support opt-out for rules with side effects
    - Clear memoization when context changes
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 4.7 Write property test for memoization consistency
    - **Property 27: Memoization Consistency**
    - **Validates: Requirements 8.1, 8.2, 8.5**
    - Evaluate same rule multiple times, verify memoized results match non-memoized

  - [ ]* 4.8 Write property test for memoization context isolation
    - **Property 28: Memoization Context Isolation**
    - **Validates: Requirements 8.3**
    - Verify memoization doesn't leak between contexts

  - [ ]* 4.9 Write property test for selective memoization
    - **Property 29: Selective Memoization**
    - **Validates: Requirements 8.4**
    - Verify non-memoizable rules are evaluated fresh each time

  - [ ] 4.10 Implement policy schema validation
    - Create JSON schema for policy structure
    - Implement `validate_policy()` function
    - Validate required fields, types, enum values
    - Return detailed validation errors
    - _Requirements: 1.2, 9.5_

  - [ ]* 4.11 Write property test for schema validation
    - **Property 2: Policy Schema Validation**
    - **Validates: Requirements 1.2**
    - Generate valid and invalid policies, verify validation correctness

  - [ ]* 4.12 Write property test for validation error messages
    - **Property 33: Validation Error Messages**
    - **Validates: Requirements 9.5**
    - Generate invalid policies, verify error messages include specific failures

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement conflict resolver
  - [ ] 6.1 Create `ConflictResolver` class in `evaluation/conflict_resolver.py`
    - Implement `resolve()` method with strategy selection
    - Implement `resolve_by_priority()` for priority-based resolution
    - Implement `resolve_deny_overrides()` for deny-overrides strategy
    - Implement `resolve_allow_overrides()` for allow-overrides strategy
    - Implement `resolve_first_applicable()` for first-applicable strategy
    - Log conflicts and resolutions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.2 Write property test for priority-based resolution
    - **Property 14: Priority-Based Conflict Resolution**
    - **Validates: Requirements 5.2**
    - Generate policies with different priorities, verify highest priority wins

  - [ ]* 6.3 Write property test for deny-overrides strategy
    - **Property 15: Deny-Overrides Strategy**
    - **Validates: Requirements 5.3, 5.6**
    - Generate equal-priority policies with mixed effects, verify DENY wins

  - [ ]* 6.4 Write property test for allow-overrides strategy
    - **Property 16: Allow-Overrides Strategy**
    - **Validates: Requirements 5.3**
    - Generate equal-priority policies with mixed effects, verify ALLOW wins

  - [ ]* 6.5 Write property test for conflict logging
    - **Property 17: Conflict Resolution Logging**
    - **Validates: Requirements 5.5**
    - Verify conflicts are logged with all required details

- [ ] 7. Implement access controller
  - [ ] 7.1 Create `AccessController` class in `access/access_controller.py`
    - Implement `check_access()` method orchestrating RBAC and ABAC
    - Implement `check_rbac()` for role-based permission checking
    - Implement `check_abac()` for attribute-based policy evaluation
    - Implement `get_effective_permissions()` with role hierarchy traversal
    - Support dynamic attribute retrieval from external providers
    - Handle missing attributes according to policy strategy
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 7.2 Write property test for RBAC permission check
    - **Property 11: RBAC Permission Check**
    - **Validates: Requirements 3.4**
    - Generate principals with roles, verify access granted when permission exists

  - [ ]* 7.3 Write property test for ABAC evaluation
    - **Property 12: Attribute-Based Policy Evaluation**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5**
    - Generate policies with attribute conditions, verify correct evaluation

  - [ ]* 7.4 Write property test for missing attribute strategy
    - **Property 13: Missing Attribute Strategy**
    - **Validates: Requirements 4.6**
    - Generate contexts with missing attributes, verify strategy is followed

- [ ] 8. Implement audit logger
  - [ ] 8.1 Create `AuditLogger` class in `audit/audit_logger.py`
    - Implement SQLite schema for audit_log table with indexes
    - Implement `log_decision()` with tamper-evident hashing
    - Implement `query_logs()` with filtering and pagination
    - Implement `verify_integrity()` for tamper detection
    - Implement `archive_old_records()` for retention policy
    - Support configurable retention period
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 8.2 Write property test for audit record completeness
    - **Property 18: Audit Record Completeness**
    - **Validates: Requirements 6.1**
    - Generate random decisions, verify all required fields in audit records

  - [ ]* 8.3 Write property test for audit query correctness
    - **Property 19: Audit Query Correctness**
    - **Validates: Requirements 6.3**
    - Generate audit records and queries, verify filtering correctness

  - [ ]* 8.4 Write property test for audit integrity
    - **Property 20: Audit Record Integrity**
    - **Validates: Requirements 6.4**
    - Verify integrity checks detect tampering

  - [ ]* 8.5 Write property test for retention policy
    - **Property 21: Audit Retention Policy**
    - **Validates: Requirements 6.5, 6.6**
    - Generate old and new records, verify archival behavior

- [ ] 9. Implement cache manager
  - [ ] 9.1 Create `CacheManager` class in `cache/cache_manager.py`
    - Implement LRU cache with configurable size limit
    - Implement `get()`, `put()`, `invalidate()` methods
    - Implement `compute_cache_key()` using SHA256 hash
    - Implement TTL support with expiration checking
    - Implement `invalidate_for_policy()` for policy-specific invalidation
    - Implement `get_stats()` for cache metrics (hits, misses, evictions, hit rate)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 9.2 Write property test for cache hit consistency
    - **Property 22: Cache Hit Consistency**
    - **Validates: Requirements 7.1, 7.2**
    - Cache decisions, verify identical requests return cached results

  - [ ]* 9.3 Write property test for cache TTL expiration
    - **Property 23: Cache TTL Expiration**
    - **Validates: Requirements 7.3**
    - Cache with TTL, verify expiration after time passes

  - [ ]* 9.4 Write property test for cache invalidation
    - **Property 24: Cache Invalidation on Policy Change**
    - **Validates: Requirements 3.6, 7.4**
    - Modify policies/roles, verify affected cache entries invalidated

  - [ ]* 9.5 Write property test for LRU eviction
    - **Property 25: LRU Cache Eviction**
    - **Validates: Requirements 7.5**
    - Fill cache to capacity, verify LRU eviction behavior

  - [ ]* 9.6 Write property test for cache statistics
    - **Property 26: Cache Statistics Accuracy**
    - **Validates: Requirements 7.6**
    - Perform cache operations, verify statistics accuracy

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement main policy engine API
  - [ ] 11.1 Create `PolicyEngine` class in `policy_engine.py`
    - Initialize all components (storage, evaluator, resolver, audit, cache)
    - Implement `evaluate_policy()` orchestrating all components
    - Implement cache check → policy retrieval → evaluation → conflict resolution → audit → cache update flow
    - Implement `create_policy()`, `update_policy()`, `delete_policy()` with cache invalidation
    - Implement `create_role()`, `assign_role()` with cache invalidation
    - Implement `query_audit_logs()` delegating to audit logger
    - Implement `get_cache_stats()` delegating to cache manager
    - Add comprehensive error handling with fail-safe defaults
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 3.1, 3.6, 6.1, 6.3, 7.4, 7.6, 10.1_

  - [ ] 11.2 Implement async support
    - Create `evaluate_policy_async()` method
    - Use asyncio for non-blocking operations
    - Ensure async and sync versions produce identical results
    - _Requirements: 10.2_

  - [ ]* 11.3 Write property test for async equivalence
    - **Property 34: Async Evaluation Equivalence**
    - **Validates: Requirements 10.2**
    - Verify async and sync evaluation return same results

  - [ ] 11.4 Implement test mode and dry-run mode
    - Add `test_mode` flag to disable side effects (no audit, no cache updates)
    - Implement `test_policy()` method accepting test cases
    - Implement test result comparison and reporting
    - Add `dry_run` flag to evaluate without enforcement
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 11.5 Write property test for test mode isolation
    - **Property 30: Test Mode Isolation**
    - **Validates: Requirements 9.1**
    - Verify test mode makes no persistent changes

  - [ ]* 11.6 Write property test for test case validation
    - **Property 31: Test Case Validation**
    - **Validates: Requirements 9.3**
    - Generate test cases, verify pass/fail detection correctness

  - [ ]* 11.7 Write property test for dry-run mode
    - **Property 32: Dry-Run Mode**
    - **Validates: Requirements 9.4**
    - Verify dry-run evaluates but doesn't enforce

  - [ ] 11.8 Implement event emission for monitoring
    - Create event emitter for policy decisions
    - Emit events with decision details (principal, resource, action, effect, timestamp)
    - Support event subscribers for monitoring and alerting
    - _Requirements: 10.6_

  - [ ]* 11.9 Write property test for event emission
    - **Property 35: Event Emission Completeness**
    - **Validates: Requirements 10.6**
    - Verify events are emitted with complete decision details

- [ ] 12. Create hypothesis strategies for property tests
  - [ ] 12.1 Create custom strategies in `tests/conftest.py`
    - Define `policy_strategy` for generating valid policies
    - Define `rule_expression_strategy` for generating nested rule conditions
    - Define `principal_strategy` for generating principals with attributes
    - Define `resource_strategy` for generating resources with attributes
    - Define `context_strategy` for generating evaluation contexts
    - Define `role_strategy` for generating roles with hierarchies
    - Configure hypothesis settings (max_examples=100)

- [ ] 13. Write integration tests
  - [ ]* 13.1 Write integration test for LLM runtime integration
    - Test policy enforcement on LLM provider selection
    - Test policy enforcement on model usage
    - _Requirements: 10.3_

  - [ ]* 13.2 Write integration test for memory system integration
    - Test policy enforcement on data access
    - Test policy enforcement on retention policies
    - _Requirements: 10.4_

  - [ ]* 13.3 Write integration test for agent orchestration integration
    - Test policy enforcement on agent actions
    - Test policy enforcement on resource usage
    - _Requirements: 10.5_

- [ ] 14. Write unit tests for edge cases
  - [ ]* 14.1 Write unit tests for storage edge cases
    - Test empty database initialization
    - Test concurrent policy updates
    - Test database corruption recovery
    - Test large policy sets (1000+ policies)

  - [ ]* 14.2 Write unit tests for evaluation edge cases
    - Test deeply nested rules (10+ levels)
    - Test circular role dependencies detection
    - Test attribute provider timeouts
    - Test malformed rule expressions

  - [ ]* 14.3 Write unit tests for cache edge cases
    - Test cache behavior under memory pressure
    - Test concurrent cache access
    - Test cache corruption recovery

  - [ ]* 14.4 Write unit tests for audit edge cases
    - Test audit log at storage threshold
    - Test audit integrity with corrupted records
    - Test audit queries with large result sets

- [ ] 15. Add performance benchmarks
  - [ ]* 15.1 Create benchmark tests using pytest-benchmark
    - Benchmark policy evaluation latency (target: <1ms with cache, <10ms without)
    - Benchmark cache hit rate (target: >90% for repeated requests)
    - Benchmark storage throughput (target: >1000 policies/sec)
    - Benchmark audit log write throughput (target: >10000 records/sec)
    - Benchmark role hierarchy traversal (target: <1ms for 10-level hierarchy)

- [ ] 16. Create example usage and documentation
  - [ ] 16.1 Create example scripts in `examples/`
    - Create `basic_usage.py` demonstrating policy creation and evaluation
    - Create `rbac_example.py` demonstrating role-based access control
    - Create `abac_example.py` demonstrating attribute-based access control
    - Create `integration_example.py` demonstrating AGENT_GURU integration
    - Add inline documentation and comments

- [ ] 17. Final integration and testing
  - [ ] 17.1 Run full test suite
    - Run all unit tests with coverage report (target: ≥90%)
    - Run all property tests (100 examples each)
    - Run all integration tests
    - Run all benchmarks
    - Verify no test failures

  - [ ] 17.2 Perform code quality checks
    - Run `black` for code formatting
    - Run `flake8` for linting (zero errors)
    - Run `mypy` for type checking (strict mode)
    - Run `pylint` (target score: ≥9.0/10)

  - [ ] 17.3 Git commit and push
    - Commit all changes with descriptive message
    - Push to repository
    - Tag release as `v1.0.0-guru-policy-engine`

- [ ] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- Integration tests validate interaction with other AGENT_GURU components
- All code must pass quality checks (black, flake8, mypy, pylint) before final commit
- Git commit and push after completing all tasks
