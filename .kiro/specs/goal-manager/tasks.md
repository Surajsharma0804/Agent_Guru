# Implementation Plan: Goal Manager

## Overview

This plan implements the Goal Manager system for Agent_Guru, enabling persistent autonomous goal management across sessions. The implementation follows the design document and includes comprehensive property-based testing to verify correctness properties.

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create goal_manager/ directory structure
  - Set up Python package with __init__.py
  - Install dependencies: SQLite3, GitPython, Pydantic, asyncio, Hypothesis
  - Create requirements.txt
  - Set up pytest configuration for property-based testing
  - _Requirements: 1.1, 12.1_

- [ ] 2. Implement core data models
  - [ ] 2.1 Create Goal data model with Pydantic
    - Define GoalStatus enum
    - Define Priority enum
    - Define Goal dataclass with all fields
    - Add validation for progress (0.0 to 1.0)
    - Add validation for timestamp ordering
    - _Requirements: 1.1, 1.5, 3.5_
  
  - [ ]* 2.2 Write property test for Goal model validation
    - **Property 1: Goal Creation Initialization**
    - **Validates: Requirements 1.1, 1.4, 1.5**
  
  - [ ]* 2.3 Write property test for timestamp ordering
    - **Property 9: Timestamp Chronological Order**
    - **Validates: Requirements 3.5**

- [ ] 3. Implement Goal Storage layer
  - [ ] 3.1 Create GoalStorage class with SQLite backend
    - Initialize database schema with tables and indexes
    - Implement store_goal() with immediate persistence
    - Implement update_goal() with immediate persistence
    - Implement get_goal() for retrieval by ID
    - Implement query_goals() with status and priority filters
    - _Requirements: 1.2, 8.1, 8.2, 8.3_
  
  - [ ] 3.2 Implement JSON serialization methods
    - Implement _goal_to_dict() for serialization
    - Implement _dict_to_goal() for deserialization
    - Implement export_to_json() for backup
    - Implement import_from_json() for restore
    - Add schema validation on deserialization
    - _Requirements: 12.1, 12.2, 12.3, 12.5_
  
  - [ ]* 3.3 Write property test for immediate persistence
    - **Property 2: Immediate Persistence**
    - **Validates: Requirements 1.2, 3.4, 4.6**
  
  - [ ]* 3.4 Write property test for serialization round-trip
    - **Property 21: Serialization Round-Trip**
    - **Validates: Requirements 12.1, 12.2**
  
  - [ ]* 3.5 Write property test for query filtering correctness
    - **Property 19: Query Filtering Correctness**
    - **Validates: Requirements 8.2, 8.3**
  
  - [ ]* 3.6 Write unit tests for storage error handling
    - Test retry logic on write failures
    - Test corruption detection and recovery
    - _Requirements: 11.1, 11.3_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Goal Decomposer
  - [ ] 5.1 Create GoalDecomposer class
    - Implement decompose() method with LLM Runtime integration
    - Implement _get_context() to query Memory System
    - Implement _build_prompt() for LLM decomposition
    - Implement _call_llm_with_retry() with exponential backoff
    - Implement _parse_response() to extract sub-goals from LLM response
    - Implement _validate_subgoals() for quality checks
    - _Requirements: 2.1, 2.3, 10.1, 10.4, 11.4_
  
  - [ ]* 5.2 Write property test for parent-child reference consistency
    - **Property 6: Parent-Child Reference Consistency**
    - **Validates: Requirements 2.3**
  
  - [ ]* 5.3 Write property test for retry with exponential backoff
    - **Property 23: Retry with Exponential Backoff**
    - **Validates: Requirements 11.1, 11.4, 11.5**
  
  - [ ]* 5.4 Write unit tests for decomposition edge cases
    - Test with empty goal description
    - Test with very long goal description
    - Test LLM failure scenarios
    - _Requirements: 2.1, 11.4_

- [ ] 6. Implement Progress Tracker
  - [ ] 6.1 Create ProgressTracker class
    - Implement mark_complete() with parent update
    - Implement mark_failed() with error recording
    - Implement mark_in_progress() with timestamp
    - Implement _update_parent_progress() with recursive propagation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_
  
  - [ ]* 6.2 Write property test for progress calculation
    - **Property 7: Progress Calculation Correctness**
    - **Validates: Requirements 3.2**
  
  - [ ]* 6.3 Write property test for completion propagation
    - **Property 8: Completion Propagation**
    - **Validates: Requirements 3.3**
  
  - [ ]* 6.4 Write unit tests for progress edge cases
    - Test goal with no sub-goals
    - Test goal with single sub-goal
    - Test deep hierarchy (5+ levels)
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 7. Implement Priority Manager
  - [ ] 7.1 Create PriorityManager class
    - Implement update_priority() with immediate persistence
    - Implement select_next_goal() with priority and age sorting
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6_
  
  - [ ]* 7.2 Write property test for priority selection
    - **Property 10: Priority Selection Correctness**
    - **Validates: Requirements 4.3, 4.4**
  
  - [ ]* 7.3 Write property test for priority validity
    - **Property 11: Priority Validity**
    - **Validates: Requirements 4.2**

- [ ] 8. Implement Dependency Resolver
  - [ ] 8.1 Create DependencyResolver class
    - Implement validate_dependencies() with cycle detection
    - Implement _has_cycle() using depth-first search
    - Implement _has_cycle_util() recursive helper
    - Implement is_ready() to check dependency satisfaction
    - Implement mark_blocked() with recursive propagation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 8.2 Write property test for circular dependency detection
    - **Property 16: Circular Dependency Detection**
    - **Validates: Requirements 7.4**
  
  - [ ]* 8.3 Write property test for dependency blocking
    - **Property 15: Dependency Blocking**
    - **Validates: Requirements 7.2**
  
  - [ ]* 8.4 Write property test for dependency satisfaction
    - **Property 17: Dependency Satisfaction**
    - **Validates: Requirements 7.5**
  
  - [ ]* 8.5 Write unit tests for complex dependency graphs
    - Test linear dependencies (A -> B -> C)
    - Test diamond dependencies (A -> B,C -> D)
    - Test multiple independent chains
    - _Requirements: 7.1, 7.2, 7.4_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement Goal Executor
  - [ ] 10.1 Create GoalExecutor class
    - Implement execute_goal() with sequential sub-goal execution
    - Implement _execute_sub_goal() with Agent Orchestration integration
    - Implement _commit_to_github() using GitPython
    - Implement _report_completion() to Self-Improvement Engine
    - Implement stop_execution() for cancellation
    - Implement resume_goal() for interrupted goals
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.2, 10.3_
  
  - [ ]* 10.2 Write property test for sequential execution
    - **Property 12: Sequential Sub-Goal Execution**
    - **Validates: Requirements 5.6**
  
  - [ ]* 10.3 Write property test for task creation
    - **Property 13: Task Creation for Execution**
    - **Validates: Requirements 5.1, 10.2**
  
  - [ ]* 10.4 Write property test for GitHub commit
    - **Property 14: GitHub Commit on Completion**
    - **Validates: Requirements 5.5**
  
  - [ ]* 10.5 Write unit tests for execution scenarios
    - Test successful execution flow
    - Test execution with failures
    - Test execution cancellation
    - Test execution resumption
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

- [ ] 11. Implement Session Manager
  - [ ] 11.1 Create SessionManager class
    - Implement load_goals() with integrity validation
    - Implement _validate_goal_integrity() for corruption detection
    - Implement _attempt_recovery() for corrupted goals
    - Implement persist_all() for shutdown
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 11.2 Write property test for session persistence
    - **Property 3: Session Persistence Round-Trip**
    - **Validates: Requirements 1.3, 6.1, 6.2, 6.5**
  
  - [ ]* 11.3 Write property test for corruption recovery
    - **Property 25: Corruption Recovery**
    - **Validates: Requirements 6.4, 11.3**
  
  - [ ]* 11.4 Write unit tests for session scenarios
    - Test normal startup and shutdown
    - Test recovery from crash (interrupted goals)
    - Test handling of corrupted data
    - _Requirements: 6.1, 6.3, 6.4_

- [ ] 12. Implement Goal Manager API
  - [ ] 12.1 Create GoalManager class
    - Implement __init__() to initialize all components
    - Implement create_goal() with validation and decomposition
    - Implement get_goal() for retrieval
    - Implement query_goals() with filters
    - Implement update_priority() delegation
    - Implement cancel_goal() with propagation
    - Implement get_summary() with statistics
    - Implement start() for system startup
    - Implement shutdown() for system shutdown
    - Implement _decompose_goal() async helper
    - _Requirements: 1.1, 1.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3_
  
  - [ ]* 12.2 Write property test for unique identifier invariant
    - **Property 4: Unique Identifier Invariant**
    - **Validates: Requirements 1.4**
  
  - [ ]* 12.3 Write property test for hierarchical tree structure
    - **Property 5: Hierarchical Tree Structure**
    - **Validates: Requirements 2.6**
  
  - [ ]* 12.4 Write property test for cancellation propagation
    - **Property 18: Cancellation Propagation**
    - **Validates: Requirements 9.1**
  
  - [ ]* 12.5 Write property test for hierarchical retrieval
    - **Property 20: Hierarchical Retrieval Completeness**
    - **Validates: Requirements 8.4**

- [ ] 13. Implement error handling and logging
  - [ ] 13.1 Create exception hierarchy
    - Define GoalManagerError base exception
    - Define StorageError, DecompositionError, ValidationError, ExecutionError
    - _Requirements: 11.1, 11.2_
  
  - [ ] 13.2 Add error logging throughout system
    - Add logging to all error paths
    - Include context (goal ID, operation, timestamp)
    - _Requirements: 11.2, 11.6_
  
  - [ ]* 13.3 Write property test for error logging
    - **Property 24: Error Logging Completeness**
    - **Validates: Requirements 11.2, 11.6**

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Integration and end-to-end testing
  - [ ] 15.1 Write integration tests
    - Test full goal lifecycle (create -> decompose -> execute -> complete)
    - Test goal with dependencies
    - Test goal cancellation during execution
    - Test system restart and recovery
    - Test GitHub integration
    - _Requirements: 1.1, 2.1, 5.1, 6.1, 9.1_
  
  - [ ]* 15.2 Write adversarial tests
    - Test with corrupted database
    - Test with extremely deep hierarchies (100+ levels)
    - Test with large numbers of sub-goals (100+ per goal)
    - Test with concurrent modifications
    - Test with simulated LLM failures
    - Test with simulated Agent Orchestration failures
    - _Requirements: 6.4, 11.1, 11.3, 11.4, 11.5_

- [ ] 16. Create README documentation
  - Document Goal Manager architecture
  - Document API usage examples
  - Document integration with other Agent_Guru components
  - Document property-based testing approach
  - _Requirements: 10.5_

- [ ] 17. Final checkpoint - Ensure all tests pass
  - Run full test suite with property tests (100+ iterations each)
  - Verify all 25 correctness properties pass
  - Verify all integration tests pass
  - Verify all adversarial tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end functionality
- Adversarial tests verify resilience to failures and edge cases
- All property tests are tagged with feature name and property number
