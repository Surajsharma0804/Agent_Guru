# Implementation Plan: Guru Deployment System

## Overview

This implementation plan breaks down the Guru Deployment System into incremental, testable components. The approach follows a bottom-up strategy: build core services first (Package Manager, Crypto Verifier, Dependency Resolver, Rollback Manager), then build the orchestration layer (Update Orchestrator, Transaction Manager), and finally wire everything together with the public API. Each task includes property-based tests to validate correctness properties from the design document.

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create directory structure: `guru_deployment/` with subdirectories for core services, storage, and API
  - Set up `pyproject.toml` with dependencies: cryptography, pip-tools, requests, packaging, hypothesis, pytest
  - Configure pytest with coverage and hypothesis settings
  - Create base exception classes for the deployment system
  - _Requirements: All (foundational)_

- [ ] 2. Implement Package Registry storage layer
  - [ ] 2.1 Create SQLite-based Package Registry
    - Implement `PackageRegistry` class with SQLite backend
    - Define schema for packages table (name, version, install_path, dependencies, metadata, timestamp, checksum)
    - Implement methods: `add_package()`, `remove_package()`, `get_package()`, `list_packages()`
    - Implement transaction support for atomic registry updates
    - _Requirements: 1.4, 1.5_
  
  - [ ]* 2.2 Write property tests for Package Registry
    - **Property 1 (partial): Package Installation Round Trip** - Test registry recording
    - **Property 2 (partial): Package Removal Cleanup** - Test registry removal
    - _Requirements: 1.4, 1.5_

- [ ] 3. Implement Trust Store for cryptographic keys
  - [ ] 3.1 Create SQLite-based Trust Store
    - Implement `TrustStore` class with SQLite backend
    - Define schema for keys table (key_id, public_key, owner, added_timestamp, expiry, metadata)
    - Implement methods: `add_key()`, `remove_key()`, `get_key()`, `list_keys()`
    - _Requirements: 2.4, 2.7_
  
  - [ ]* 3.2 Write property tests for Trust Store
    - **Property 6: Trust Store Key Validation** - Test key format validation
    - **Property 8: Trust Store Persistence** - Test persistence across restarts
    - _Requirements: 2.4, 2.7_

- [ ] 4. Implement Crypto Verifier component
  - [ ] 4.1 Create CryptoVerifier class with Ed25519 support
    - Implement signature verification using `cryptography` library
    - Implement `verify_package_signature()` method with streaming file reading
    - Implement `compute_package_hash()` method with SHA-256 streaming
    - Integrate with Trust Store for key management
    - Handle unsigned packages based on configuration
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_
  
  - [ ]* 4.2 Write property tests for Crypto Verifier
    - **Property 5: Signature Verification Correctness** - Test valid/invalid signatures
    - **Property 7: Unsigned Package Rejection** - Test unsigned package handling
    - **Property 35: Streaming Cryptographic Verification** - Test memory-bounded verification
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 10.2_
  
  - [ ]* 4.3 Write unit tests for cryptographic edge cases
    - Test with corrupted signatures
    - Test with wrong public keys
    - Test with expired keys
    - Test with very large files (1 GB)
    - _Requirements: 2.1, 2.2, 10.7_

- [ ] 5. Implement Package Manager component
  - [ ] 5.1 Create PackageManager class with download and installation
    - Implement `download_package()` with streaming to disk
    - Implement `verify_checksum()` with SHA-256
    - Implement `install_package()` using pip subprocess
    - Implement `remove_package()` using pip subprocess
    - Implement `get_installed_packages()` using pip list
    - Add retry logic with exponential backoff for network operations
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 7.2, 10.1_
  
  - [ ]* 5.2 Write property tests for Package Manager
    - **Property 1: Package Installation Round Trip** - Test complete installation flow
    - **Property 2: Package Removal Cleanup** - Test complete removal
    - **Property 3: Package Update Version Replacement** - Test version updates
    - **Property 26: Network Retry with Exponential Backoff** - Test retry behavior
    - **Property 34: Streaming Large Package Downloads** - Test memory-bounded downloads
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 7.2, 10.1_
  
  - [ ]* 5.3 Write unit tests for Package Manager error cases
    - Test network failures and retries
    - Test checksum mismatches
    - Test installation failures
    - Test cleanup of partial installations
    - _Requirements: 7.2, 7.4_

- [ ] 6. Checkpoint - Core services functional
  - Ensure all tests pass for Package Registry, Trust Store, Crypto Verifier, and Package Manager
  - Verify that basic package operations work end-to-end
  - Ask the user if questions arise

- [ ] 7. Implement Dependency Resolver component
  - [ ] 7.1 Create DependencyResolver class with pip-tools integration
    - Implement `resolve_dependencies()` using pip-tools resolver
    - Implement `check_conflicts()` for version conflict detection
    - Implement `get_installation_order()` with topological sort
    - Implement `find_dependents()` for reverse dependency lookup
    - Implement circular dependency detection using DFS
    - Add caching for resolution results
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 10.3_
  
  - [ ]* 7.2 Write property tests for Dependency Resolver
    - **Property 9: Complete Dependency Resolution** - Test transitive dependencies
    - **Property 10: Version Conflict Resolution** - Test compatible version selection
    - **Property 11: Unresolvable Conflict Detection** - Test conflict reporting
    - **Property 12: Circular Dependency Detection** - Test cycle detection
    - **Property 13: Topological Installation Order** - Test dependency ordering
    - **Property 14: Dependent Package Identification** - Test reverse dependencies
    - **Property 36: Dependency Resolution Caching** - Test caching performance
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 10.3_
  
  - [ ]* 7.3 Write unit tests for complex dependency scenarios
    - Test diamond dependencies
    - Test deep dependency chains (10+ levels)
    - Test packages with many dependencies (50+)
    - Test version constraint edge cases
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 8. Implement Snapshot Storage layer
  - [ ] 8.1 Create SnapshotStorage class with filesystem backend
    - Implement snapshot directory structure in `.guru/snapshots/`
    - Implement `create_snapshot()` with hard links for unchanged files
    - Implement `restore_snapshot()` with file restoration
    - Implement `delete_snapshot()` with cleanup
    - Implement `list_snapshots()` with metadata
    - Store package registry state in snapshots
    - _Requirements: 4.1, 4.2, 4.3, 10.4_
  
  - [ ]* 8.2 Write property tests for Snapshot Storage
    - **Property 15: Snapshot Completeness** - Test snapshot captures all state
    - **Property 37: Snapshot Storage Efficiency** - Test hard link usage
    - _Requirements: 4.1, 4.2, 4.3, 10.4_

- [ ] 9. Implement Rollback Manager component
  - [ ] 9.1 Create RollbackManager class with snapshot coordination
    - Implement `create_snapshot()` coordinating storage and registry
    - Implement `restore_snapshot()` with verification
    - Implement `verify_snapshot()` for integrity checking
    - Implement `prune_snapshots()` with retention policy
    - Integrate with Package Registry for state capture
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_
  
  - [ ]* 9.2 Write property tests for Rollback Manager
    - **Property 16: Rollback Round Trip** - Test snapshot → modify → restore
    - **Property 17: Multi-Snapshot Rollback** - Test rollback to any snapshot
    - **Property 18: Snapshot Pruning Policy** - Test retention policy enforcement
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.8_
  
  - [ ]* 9.3 Write unit tests for rollback edge cases
    - Test rollback with disk full
    - Test rollback with corrupted snapshot
    - Test rollback with missing files
    - _Requirements: 4.4, 4.5_

- [ ] 10. Checkpoint - Storage and rollback functional
  - Ensure all tests pass for Dependency Resolver, Snapshot Storage, and Rollback Manager
  - Verify that snapshots can be created and restored correctly
  - Ask the user if questions arise

- [ ] 11. Implement Audit Log storage layer
  - [ ] 11.1 Create AuditLog class with tamper-evident logging
    - Implement SQLite-based audit log with append-only structure
    - Implement `log_operation()` for operation logging
    - Implement `log_security_event()` for high-priority events
    - Implement cryptographic chaining for tamper evidence (hash of previous entry)
    - Implement `prune_logs()` with retention policy
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [ ]* 11.2 Write property tests for Audit Log
    - **Property 29: Complete Operation Audit Logging** - Test operation logging
    - **Property 28: Security Event Audit Logging** - Test security event logging
    - **Property 30: Rollback Audit Logging** - Test rollback logging
    - **Property 31: Audit Log Tamper Evidence** - Test tamper detection
    - **Property 32: Audit Log Retention** - Test log pruning
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ] 12. Implement Configuration Management
  - [ ] 12.1 Create Configuration class with validation
    - Define configuration schema using Pydantic models
    - Implement `load_configuration()` from YAML/JSON file
    - Implement configuration validation with descriptive errors
    - Implement default values for missing configuration
    - Support repository URLs, priorities, verification policies, retention policies, network parameters
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [ ]* 12.2 Write property tests for Configuration
    - **Property 33: Configuration Validation** - Test validation and error handling
    - _Requirements: 9.2, 9.3_
  
  - [ ]* 12.3 Write unit tests for configuration examples
    - Test loading valid configuration files
    - Test various invalid configurations
    - Test default value fallback
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 13. Implement Repository Management
  - [ ] 13.1 Create RepositoryManager class
    - Implement `add_repository()` with URL validation
    - Implement `query_package()` with priority-based search
    - Implement repository failover logic
    - Implement `download_from_repository()` with retry
    - Integrate with Configuration for repository list
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [ ]* 13.2 Write property tests for Repository Management
    - **Property 23: Repository Priority and Failover** - Test priority and failover
    - **Property 24: Repository Validation** - Test URL validation
    - _Requirements: 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 13.3 Write unit tests for repository edge cases
    - Test all repositories unreachable
    - Test repository returning invalid data
    - Test repository timeout
    - _Requirements: 6.5, 6.6_

- [ ] 14. Checkpoint - Configuration and repositories functional
  - Ensure all tests pass for Audit Log, Configuration, and Repository Management
  - Verify that configuration can be loaded and repositories can be queried
  - Ask the user if questions arise

- [ ] 15. Implement Transaction Manager
  - [ ] 15.1 Create TransactionManager class with two-phase commit
    - Implement `begin_transaction()` with file locking for mutual exclusion
    - Implement transaction state machine (PENDING → EXECUTING → COMMITTED/ROLLED_BACK)
    - Implement transaction log for recovery
    - Implement `commit_transaction()` and `rollback_transaction()`
    - Integrate with Audit Log for transaction logging
    - _Requirements: 5.1, 5.6, 5.7, 5.8_
  
  - [ ]* 15.2 Write property tests for Transaction Manager
    - **Property 22: Transaction Mutual Exclusion** - Test concurrent transaction blocking
    - _Requirements: 5.8_

- [ ] 16. Implement Update Orchestrator component
  - [ ] 16.1 Create UpdateOrchestrator class coordinating all subsystems
    - Implement `begin_update()` creating transaction
    - Implement `execute_transaction()` coordinating: resolve → verify → snapshot → install
    - Implement installation order execution with dependency ordering
    - Implement failure detection and automatic rollback triggering
    - Implement success path with snapshot cleanup
    - Implement parallel installation for independent packages
    - Integrate with all core services: Dependency Resolver, Crypto Verifier, Package Manager, Rollback Manager
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 10.5_
  
  - [ ]* 16.2 Write property tests for Update Orchestrator
    - **Property 19: Transaction Execution Flow** - Test orchestration sequence
    - **Property 20: Transaction Atomicity** - Test rollback on failure
    - **Property 21: Transaction Commit Cleanup** - Test snapshot cleanup
    - **Property 38: Parallel Independent Installations** - Test parallel execution
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 10.5_
  
  - [ ]* 16.3 Write unit tests for orchestration scenarios
    - Test successful multi-package update
    - Test update with dependency resolution
    - Test update with signature verification failure
    - Test update with installation failure mid-transaction
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 17. Checkpoint - Orchestration layer complete
  - Ensure all tests pass for Transaction Manager and Update Orchestrator
  - Verify that complete update transactions work end-to-end
  - Ask the user if questions arise

- [ ] 18. Implement Error Handling and Recovery
  - [ ] 18.1 Create comprehensive error handling across all components
    - Implement custom exception hierarchy for all error types
    - Add descriptive error messages with context to all exceptions
    - Implement cleanup logic for partial operations
    - Add error recovery suggestions to error messages
    - _Requirements: 7.1, 7.3, 7.4, 7.6, 7.7_
  
  - [ ]* 18.2 Write property tests for error handling
    - **Property 25: Descriptive Error Messages** - Test error message quality
    - **Property 27: Installation Failure Cleanup** - Test cleanup on failure
    - _Requirements: 7.1, 7.4_
  
  - [ ]* 18.3 Write unit tests for specific error scenarios
    - Test network errors with retry exhaustion
    - Test disk space errors with space reporting
    - Test permission errors
    - Test concurrent access errors
    - _Requirements: 7.2, 7.3, 7.7_

- [ ] 19. Implement Public API layer
  - [ ] 19.1 Create DeploymentAPI class as main entry point
    - Implement `install_package()` public method
    - Implement `remove_package()` public method
    - Implement `update_packages()` public method
    - Implement `list_installed()` public method
    - Implement `add_trusted_key()` public method
    - Implement `configure_repository()` public method
    - Implement `create_manual_snapshot()` public method
    - Implement `rollback_to_snapshot()` public method
    - Wire all components together through API
    - _Requirements: All (API integration)_
  
  - [ ]* 19.2 Write integration tests for public API
    - Test complete installation workflow through API
    - Test complete update workflow through API
    - Test rollback workflow through API
    - Test multi-repository workflow through API
    - _Requirements: All_

- [ ] 20. Implement Performance Optimizations
  - [ ] 20.1 Add performance monitoring and optimization
    - Add timing instrumentation to critical paths
    - Verify streaming implementation for large files
    - Verify parallel installation implementation
    - Verify caching implementation for dependency resolution
    - Add performance assertions to tests
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [ ]* 20.2 Write property tests for performance requirements
    - **Property 39: Installation Performance Bounds** - Test installation timing
    - _Requirements: 10.6_
  
  - [ ]* 20.3 Write unit tests for performance edge cases
    - Test with 1 GB package
    - Test with 100 packages in transaction
    - Test with deep dependency chains
    - _Requirements: 10.6, 10.7_

- [ ] 21. Final integration and end-to-end testing
  - [ ] 21.1 Create comprehensive end-to-end test scenarios
    - Test complete system update with multiple packages
    - Test update failure and automatic rollback
    - Test cryptographic verification in full workflow
    - Test multi-repository failover in full workflow
    - Test audit logging across complete workflows
    - _Requirements: All_
  
  - [ ]* 21.2 Write property test for independent package installation
    - **Property 4: Independent Package Installation** - Test failure isolation
    - _Requirements: 1.7_

- [ ] 22. Final checkpoint - Complete system verification
  - Run full test suite (unit + property + integration)
  - Verify all 39 correctness properties pass
  - Verify code coverage ≥ 90%
  - Verify all requirements are implemented and tested
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based and unit tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical breakpoints
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples, edge cases, and error conditions
- All property tests should run with minimum 100 iterations (configured in pytest)
- Integration tests verify end-to-end workflows through the public API
