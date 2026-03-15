# Implementation Plan: Goal Manager

## Overview

This plan implements the Goal Manager system for Agent_Guru, enabling persistent autonomous goal management across sessions. The implementation follows the design document and includes comprehensive property-based testing to verify correctness properties.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create goal_manager/ directory structure
  - Set up Python package with __init__.py
  - Install dependencies: SQLite3, GitPython, Pydantic, asyncio, Hypothesis
  - Create requirements.txt
  - Set up pytest configuration for property-based testing
  - _Requirements: 1.1, 12.1_

- [x] 2. Implement core data models
  - [x] 2.1 Create Goal data model with Pydantic
    - Define GoalStatus enum
    - Define Priority enum
    - Define Goal dataclass with all fields
    - Add validation for progress (0.0 to 1.0)
    - Add validation for timestamp ordering
    - _Requirements: 1.1, 1.5, 3.5_
  
  - [x] 2.2 Write property test for Goal model validation
    - **Property 1: Goal Creation Initialization**
    - **Validates: Requirements 1.1, 1.4, 1.5**
  
  - [x] 2.3 Write property test for timestamp ordering
    - **Property 9: Timestamp Chronological Order**
    - **Validates: Requirements 3.5**

- [x] 3. Implement Goal Storage layer
  - [x] 3.1 Create GoalStorage class with SQLite backend
    - Initialize database schema with tables and indexes
    - Implement store_goal() with immediate persistence
    - Implement update_goal() with immediate persistence
    - Implement get_goal() for retrieval by ID
    - Implement query_goals() with status and priority filters
    - _Requirements: 1.2, 8.1, 8.2, 8.3_
  
  - [x] 3.2 Implement JSON serialization methods
    - Implement _goal_to_dict() for serialization
    - Implement _dict_to_goal() for deserialization
    - Implement export_to_json() for backup
    - Implement import_from_json() for restore
    - Add schema validation on deserialization
    - _Requirements: 12.1, 12.2, 12.3, 12.5_
  
  - [x] 3.3 Write property test for immediate persistence
    - **Property 2: Immediate Persistence**
    - **Validates: Requirements 1.2, 3.4, 4.6**
  
  - [x] 3.4 Write property test for serialization round-trip
    - **Property 21: Serialization Round-Trip**
    - **Validates: Requirements 12.1, 12.2**
  
  - [x] 3.5 Write property test for query filtering correctness
    - **Property 19: Query Filtering Correctness**
    - **Validates: Requirements 8.2, 8.3**
  
  - [x] 3.6 Write property test for schema validation
    - **Property 22: Schema Validation**
    - **Validates: Requirements 12.3, 12.5**
  
  - [x] 3.7 Write unit tests for storage error handling
    - Test retry logic on write failures
    - Test corruption detection and recovery
    - _Requirements: 11.1, 11.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Goal Decomposer
  - [x] 5.1 Create GoalDecomposer class
    - Implement decompose() method with LLM Runtime integration
    - Implement _get_context() to query Memory System
    - Implement _build_prompt() for LLM decomposition
    - Implement _call_llm_with_retry() with exponential backoff
    - Implement _parse_response() to extract sub-goals from LLM response
    - Implement _validate_subgoals() for quality checks
    - _Requirements: 2.1, 2.3, 10.1, 10.4, 11.4_
  
  - [x] 5.2 Write property test for parent-child reference consistency
    - **Property 6: Parent-Child Reference Consistency**
    - **Validates: Requirements 2.3**
  
  - [x] 5.3 Write property test for retry with exponential backoff
    - **Property 23: Retry with Exponential Backoff**
    - **Validates: Requirements 11.1, 11.4, 11.5**
  
  - [x] 5.4 Write unit tests for decomposition edge cases
    - Test with empty goal description
    - Test with very long goal description
    - Test LLM failure scenarios
    - _Requirements: 2.1, 11.4_

- [x] 6. Implement Progress Tracker
  - [x] 6.1 Create ProgressTracker class
    - Implement mark_complete() with parent update
    - Implement mark_failed() with error recording
    - Implement mark_in_progress() with timestamp
    - Implement _update_parent_progress() with recursive propagation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_
  
  - [x] 6.2 Write property test for progress calculation
    - **Property 7: Progress Calculation Correctness**
    - **Validates: Requirements 3.2**
  
  - [x] 6.3 Write property test for completion propagation
    - **Property 8: Completion Propagation**
    - **Validates: Requirements 3.3**
  
  - [x] 6.4 Write unit tests for progress edge cases
    - Test goal with no sub-goals
    - Test goal with single sub-goal
    - Test deep hierarchy (5+ levels)
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 7. Implement Priority Manager
  - [x] 7.1 Create PriorityManager class
    - Implement update_priority() with immediate persistence
    - Implement select_next_goal() with priority and age sorting
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6_
  
  - [x] 7.2 Write property test for priority selection
    - **Property 10: Priority Selection Correctness**
    - **Validates: Requirements 4.3, 4.4**
  
  - [x] 7.3 Write property test for priority validity
    - **Property 11: Priority Validity**
    - **Validates: Requirements 4.2**

- [x] 8. Implement Dependency Resolver
  - [x] 8.1 Create DependencyResolver class
    - Implement validate_dependencies() with cycle detection
    - Implement _has_cycle() using depth-first search
    - Implement _has_cycle_util() recursive helper
    - Implement is_ready() to check dependency satisfaction
    - Implement mark_blocked() with recursive propagation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x] 8.2 Write property test for circular dependency detection
    - **Property 16: Circular Dependency Detection**
    - **Validates: Requirements 7.4**
  
  - [x] 8.3 Write property test for dependency blocking
    - **Property 15: Dependency Blocking**
    - **Validates: Requirements 7.2**
  
  - [x] 8.4 Write property test for dependency satisfaction
    - **Property 17: Dependency Satisfaction**
    - **Validates: Requirements 7.5**
  
  - [x] 8.5 Write unit tests for complex dependency graphs
    - Test linear dependencies (A -> B -> C)
    - Test diamond dependencies (A -> B,C -> D)
    - Test multiple independent chains
    - _Requirements: 7.1, 7.2, 7.4_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Goal Executor
  - [x] 10.1 Create GoalExecutor class with initialization
    - Implement __init__() with Agent Orchestration, storage, git repo, and Self-Improvement Engine
    - Initialize active_executions dictionary for tracking
    - Set up GitPython Repo object
    - _Requirements: 10.2, 10.3_
  
  - [x] 10.2 Implement execute_goal() method
    - Mark goal as IN_PROGRESS with timestamp
    - Iterate through sub_goal_ids sequentially
    - Handle recursive execution for sub-goals with children
    - Handle leaf sub-goal execution via _execute_sub_goal()
    - Check for failures and propagate to parent
    - Mark goal as COMPLETE when all sub-goals done
    - _Requirements: 5.1, 5.6_
  
  - [x] 10.3 Implement _execute_sub_goal() method
    - Mark sub-goal as IN_PROGRESS
    - Create task in Agent Orchestration with metadata
    - Track task_id in active_executions
    - Wait for task completion
    - Handle success: mark COMPLETE, commit to GitHub
    - Handle failure: mark FAILED with error message
    - Clean up active_executions entry
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 10.4 Implement _commit_to_github() method
    - Stage all changes with git.add(A=True)
    - Create commit with goal description and ID
    - Push to remote origin
    - Handle errors gracefully (log but don't fail goal)
    - _Requirements: 5.5_
  
  - [x] 10.5 Implement _report_completion() method
    - Call Self-Improvement Engine record_task_execution()
    - Include task_id, task_type, strategy, success status
    - Calculate execution_time_ms from timestamps
    - Include error_details if failed
    - Handle errors gracefully (log but don't fail goal)
    - _Requirements: 10.3_
  
  - [x] 10.6 Implement stop_execution() method
    - Check if goal_id in active_executions
    - Cancel task in Agent Orchestration
    - Remove from active_executions
    - _Requirements: 9.2_
  
  - [x] 10.7 Implement resume_goal() method
    - Find last completed sub-goal index
    - Resume from next sub-goal
    - Execute remaining sub-goals sequentially
    - _Requirements: 6.3_
  
  - [x] 10.8 Write property test for sequential execution
    - **Property 12: Sequential Sub-Goal Execution**
    - **Validates: Requirements 5.6**
  
  - [x] 10.9 Write property test for task creation
    - **Property 13: Task Creation for Execution**
    - **Validates: Requirements 5.1, 10.2**
  
  - [x] 10.10 Write property test for GitHub commit
    - **Property 14: GitHub Commit on Completion**
    - **Validates: Requirements 5.5**
  
  - [x] 10.11 Write unit tests for execution scenarios
    - Test successful execution flow (all sub-goals complete)
    - Test execution with sub-goal failure (propagates to parent)
    - Test execution cancellation (stop_execution)
    - Test execution resumption (resume_goal)
    - Test recursive execution (sub-goals with children)
    - Test Agent Orchestration unavailable scenario
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 6.3, 9.2_

- [x] 11. Implement Session Manager
  - [x] 11.1 Create SessionManager class with initialization
    - Implement __init__() with storage dependency
    - _Requirements: 6.1_
  
  - [x] 11.2 Implement load_goals() method
    - Query all goals from storage
    - Validate integrity for each goal
    - Collect corrupted goal IDs
    - Log warning if corrupted goals found
    - Attempt recovery for each corrupted goal
    - _Requirements: 6.1, 6.2, 6.4_
  
  - [x] 11.3 Implement _validate_goal_integrity() method
    - Check required fields (id, description)
    - Validate timestamp ordering (created_at ≤ started_at ≤ completed_at)
    - Validate progress range (0.0 to 1.0)
    - Return boolean indicating validity
    - _Requirements: 6.4_
  
  - [x] 11.4 Implement _attempt_recovery() method
    - Retrieve corrupted goal from storage
    - Mark as FAILED status
    - Set error_message to "Data corruption detected during recovery"
    - Update goal in storage
    - _Requirements: 6.4, 11.3_
  
  - [x] 11.5 Implement persist_all() method
    - No-op implementation (immediate persistence already handled)
    - Keep for API consistency
    - _Requirements: 6.5_
  
  - [x] 11.6 Write property test for session persistence
    - **Property 3: Session Persistence Round-Trip**
    - **Validates: Requirements 1.3, 6.1, 6.2, 6.5**
  
  - [x] 11.7 Write property test for corruption recovery
    - **Property 25: Corruption Recovery**
    - **Validates: Requirements 6.4, 11.3**
  
  - [x] 11.8 Write unit tests for session scenarios
    - Test normal startup (all goals valid)
    - Test startup with corrupted data (recovery triggered)
    - Test recovery from crash (interrupted goals)
    - Test validation of various corruption types (missing fields, invalid timestamps, invalid progress)
    - Test persist_all() no-op behavior
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 12. Implement Goal Manager API
  - [x] 12.1 Create GoalManager class with initialization
    - Implement __init__() to initialize all components
    - Create GoalStorage instance
    - Create GoalDecomposer instance with LLM Runtime and Memory System
    - Create ProgressTracker instance
    - Create PriorityManager instance
    - Create GoalExecutor instance with Agent Orchestration and Self-Improvement Engine
    - Create DependencyResolver instance
    - Create SessionManager instance
    - _Requirements: 10.5_
  
  - [x] 12.2 Implement create_goal() method
    - Create Goal object with unique UUID
    - Set initial status to PENDING, priority to MEDIUM (or user-specified)
    - Set progress to 0.0, created_at to now
    - Validate dependencies if provided (check for cycles)
    - Persist goal immediately to storage
    - Start async decomposition task
    - Return created goal
    - _Requirements: 1.1, 1.5, 7.1, 7.4_
  
  - [x] 12.3 Implement get_goal() method
    - Delegate to storage.get_goal()
    - Return goal with complete hierarchy
    - _Requirements: 8.1, 8.4_
  
  - [x] 12.4 Implement query_goals() method
    - Delegate to storage.query_goals() with filters
    - Support status and priority filters
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [x] 12.5 Implement update_priority() method
    - Delegate to priority_manager.update_priority()
    - _Requirements: 4.5_
  
  - [x] 12.6 Implement cancel_goal() method
    - Retrieve goal from storage
    - Raise error if goal not found
    - Recursively cancel all sub-goals
    - Stop execution if goal is IN_PROGRESS
    - Mark goal as CANCELLED
    - Update goal in storage
    - _Requirements: 9.1, 9.2_
  
  - [x] 12.7 Implement get_summary() method
    - Query all goals from storage
    - Calculate total, completed, in_progress, failed counts
    - Calculate overall progress percentage
    - Return summary dictionary
    - _Requirements: 8.5_
  
  - [x] 12.8 Implement start() method
    - Call session_manager.load_goals()
    - Query all IN_PROGRESS goals
    - Resume each interrupted goal via executor.resume_goal()
    - _Requirements: 6.1, 6.3_
  
  - [x] 12.9 Implement shutdown() method
    - Call session_manager.persist_all()
    - _Requirements: 6.5_
  
  - [x] 12.10 Implement _decompose_goal() async helper
    - Retrieve goal from storage
    - Set status to DECOMPOSING
    - Call decomposer.decompose()
    - Store each sub-goal with parent_id reference
    - Add sub-goal IDs to parent's sub_goal_ids list
    - Set status to PENDING
    - Check if ready for execution (dependencies satisfied)
    - If ready, set status to READY and start execution
    - Handle errors: set status to FAILED with error message
    - _Requirements: 2.1, 2.2, 2.3, 7.5_
  
  - [x] 12.11 Write property test for unique identifier invariant
    - **Property 4: Unique Identifier Invariant**
    - **Validates: Requirements 1.4**
  
  - [x] 12.12 Write property test for hierarchical tree structure
    - **Property 5: Hierarchical Tree Structure**
    - **Validates: Requirements 2.6**
  
  - [x] 12.13 Write property test for cancellation propagation
    - **Property 18: Cancellation Propagation**
    - **Validates: Requirements 9.1**
  
  - [x] 12.14 Write property test for hierarchical retrieval
    - **Property 20: Hierarchical Retrieval Completeness**
    - **Validates: Requirements 8.4**
  
  - [x] 12.15 Write unit tests for GoalManager API
    - Test create_goal with defaults
    - Test create_goal with custom priority and dependencies
    - Test create_goal with circular dependencies (should fail)
    - Test get_goal for existing and non-existing goals
    - Test query_goals with various filters
    - Test update_priority
    - Test cancel_goal (single goal and with sub-goals)
    - Test get_summary with various goal states
    - Test start and shutdown lifecycle
    - Test _decompose_goal success and failure scenarios
    - _Requirements: 1.1, 1.5, 7.4, 8.1, 8.2, 8.3, 8.5, 9.1, 9.2_

- [x] 13. Implement error handling and logging
  - [x] 13.1 Create exception hierarchy
    - Define GoalManagerError base exception
    - Define StorageError for storage failures
    - Define DecompositionError for LLM decomposition failures
    - Define ValidationError for validation failures (circular dependencies, invalid data)
    - Define ExecutionError for goal execution failures
    - Add docstrings for each exception type
    - _Requirements: 11.1, 11.2_
  
  - [x] 13.2 Add structured logging throughout system
    - Set up structlog for structured logging
    - Add logging to all error paths in GoalStorage
    - Add logging to all error paths in GoalDecomposer
    - Add logging to all error paths in GoalExecutor
    - Add logging to all error paths in SessionManager
    - Include context: goal_id, operation, timestamp, error details
    - _Requirements: 11.2, 11.6_
  
  - [x] 13.3 Implement retry_with_backoff utility
    - Create async retry_with_backoff function
    - Support configurable max_retries (default 3)
    - Support configurable base_delay (default 1.0s)
    - Implement exponential backoff (delay = base_delay * 2^attempt)
    - Log each retry attempt
    - Raise exception after max retries exceeded
    - _Requirements: 11.1, 11.4, 11.5_
  
  - [x] 13.4 Write property test for error logging
    - **Property 24: Error Logging Completeness**
    - **Validates: Requirements 11.2, 11.6**
  
  - [x] 13.5 Write unit tests for exception hierarchy
    - Test that all exceptions inherit from GoalManagerError
    - Test exception messages and attributes
    - _Requirements: 11.1, 11.2_
  
  - [x] 13.6 Write unit tests for retry logic
    - Test successful operation (no retries)
    - Test operation succeeds on retry
    - Test operation fails after max retries
    - Test exponential backoff timing
    - _Requirements: 11.1, 11.4, 11.5_

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement goal modification functionality
  - [x] 15.1 Add modify_goal() method to GoalManager
    - Allow modification of goal description for PENDING goals
    - Prevent modification of COMPLETE goals
    - Allow adding notes to COMPLETE goals via metadata
    - Validate goal exists before modification
    - Persist changes immediately
    - _Requirements: 9.3, 9.4, 9.5_
  
  - [x] 15.2 Add re_decompose_goal() method to GoalManager
    - Allow user to request re-decomposition after description change
    - Clear existing sub-goals
    - Trigger new decomposition
    - Only allow for PENDING goals
    - _Requirements: 9.4_
  
  - [x] 15.3 Write unit tests for goal modification
    - Test modify description for PENDING goal
    - Test prevent modification of COMPLETE goal
    - Test add notes to COMPLETE goal
    - Test modify non-existent goal (should fail)
    - Test re-decomposition after modification
    - _Requirements: 9.3, 9.4, 9.5_

- [x] 16. Integration and end-to-end testing
  - [x] 16.1 Write integration test for full goal lifecycle
    - Create goal with description
    - Verify goal is decomposed into sub-goals
    - Verify sub-goals are executed sequentially
    - Verify progress updates propagate to parent
    - Verify goal marked COMPLETE when all sub-goals done
    - Verify GitHub commits created
    - Verify Self-Improvement Engine receives metrics
    - _Requirements: 1.1, 2.1, 3.1, 3.3, 5.1, 5.5, 10.3_
  
  - [x] 16.2 Write integration test for goal with dependencies
    - Create goal A
    - Create goal B with dependency on A
    - Verify B is BLOCKED until A completes
    - Complete goal A
    - Verify B becomes READY
    - Execute goal B
    - Verify B completes successfully
    - _Requirements: 7.1, 7.2, 7.5_
  
  - [x] 16.3 Write integration test for goal cancellation during execution
    - Create and start executing goal
    - Cancel goal while sub-goal is IN_PROGRESS
    - Verify execution stops
    - Verify goal and all sub-goals marked CANCELLED
    - Verify Agent Orchestration task cancelled
    - _Requirements: 9.1, 9.2_
  
  - [x] 16.4 Write integration test for system restart and recovery
    - Create goals and start execution
    - Simulate system shutdown (persist state)
    - Simulate system restart (load state)
    - Verify all goals restored with correct state
    - Verify IN_PROGRESS goals resume execution
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 16.5 Write integration test for GitHub integration
    - Create and execute goal
    - Verify commits created for each sub-goal completion
    - Verify commit messages contain goal description and ID
    - Verify commits pushed to remote
    - Test GitHub failure scenario (log error but don't fail goal)
    - _Requirements: 5.5_
  
  - [x] 16.6 Write integration test for LLM Runtime integration
    - Create goal requiring decomposition
    - Verify LLM Runtime called with correct prompt
    - Verify sub-goals created from LLM response
    - Test LLM failure with retry logic
    - _Requirements: 2.1, 10.1, 11.4_
  
  - [x] 16.7 Write integration test for Agent Orchestration integration
    - Create and execute leaf goal
    - Verify task created in Agent Orchestration
    - Verify task completion updates goal status
    - Test Agent Orchestration unavailable scenario
    - _Requirements: 5.1, 5.2, 10.2, 11.5_
  
  - [x] 16.8 Write integration test for Memory System integration
    - Create goal
    - Verify Memory System queried for context during decomposition
    - Verify similar past goals retrieved
    - _Requirements: 10.4_
  
  - [x] 16.9 Write integration test for Self-Improvement Engine integration
    - Create and complete goal
    - Verify Self-Improvement Engine receives completion metrics
    - Verify metrics include task_id, success, execution_time_ms
    - Test Self-Improvement Engine unavailable scenario
    - _Requirements: 10.3_
  
  - [x] 16.10 Write adversarial test for corrupted database
    - Corrupt SQLite database file
    - Attempt to load goals
    - Verify corruption detected
    - Verify recovery attempted
    - Verify system doesn't crash
    - _Requirements: 6.4, 11.3_
  
  - [x] 16.11 Write adversarial test for extremely deep hierarchies
    - Create goal hierarchy 100+ levels deep
    - Verify system handles without stack overflow
    - Verify progress propagation works correctly
    - Verify execution completes successfully
    - _Requirements: 2.6, 3.1, 5.1_
  
  - [x] 16.12 Write adversarial test for large numbers of sub-goals
    - Create goal with 100+ sub-goals
    - Verify decomposition completes
    - Verify sequential execution works
    - Verify progress tracking accurate
    - _Requirements: 2.2, 3.2, 5.6_
  
  - [x] 16.13 Write adversarial test for concurrent modifications
    - Simulate concurrent goal updates from multiple threads
    - Verify data consistency maintained
    - Verify no race conditions
    - Verify SQLite locking works correctly
    - _Requirements: 1.2, 3.4_
  
  - [x] 16.14 Write adversarial test for simulated LLM failures
    - Simulate LLM timeout
    - Simulate LLM invalid response
    - Simulate LLM rate limiting
    - Verify retry logic works
    - Verify goal marked FAILED after max retries
    - _Requirements: 11.4_
  
  - [x] 16.15 Write adversarial test for simulated Agent Orchestration failures
    - Simulate Agent Orchestration unavailable
    - Simulate task creation failure
    - Simulate task execution failure
    - Verify retry logic works
    - Verify goal marked FAILED appropriately
    - _Requirements: 11.5_
  
  - [x] 16.16 Write performance test for goal creation throughput
    - Create 1000 goals rapidly
    - Measure creation time
    - Verify all goals persisted correctly
    - _Requirements: 1.1, 1.2_
  
  - [x] 16.17 Write performance test for query performance
    - Create 10000 goals with various statuses and priorities
    - Measure query time with filters
    - Verify query results correct
    - Verify indexes used effectively
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 17. Create comprehensive documentation
  - [x] 17.1 Document Goal Manager architecture
    - Create architecture diagram showing all components
    - Document component responsibilities
    - Document data flow between components
    - Document integration points with external systems
    - _Requirements: 10.5_
  
  - [x] 17.2 Document API usage examples
    - Create example: Basic goal creation and execution
    - Create example: Goal with dependencies
    - Create example: Goal cancellation
    - Create example: Querying and filtering goals
    - Create example: System startup and shutdown
    - Create example: Error handling
    - _Requirements: 10.5_
  
  - [x] 17.3 Document integration with other Agent_Guru components
    - Document LLM Runtime integration (goal decomposition)
    - Document Agent Orchestration integration (task execution)
    - Document Memory System integration (context retrieval)
    - Document Self-Improvement Engine integration (metrics reporting)
    - Document GitHub integration (audit trail)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [x] 17.4 Document property-based testing approach
    - Explain dual testing strategy (unit + property tests)
    - Document all 25 correctness properties
    - Provide examples of property test implementation
    - Document test generators and strategies
    - _Requirements: All properties_
  
  - [x] 17.5 Document deployment and operations
    - Document database setup and migration
    - Document configuration options
    - Document monitoring and logging
    - Document backup and restore procedures
    - Document troubleshooting common issues
    - _Requirements: 1.2, 6.1, 11.2, 11.6, 12.1_
  
  - [x] 17.6 Create API reference documentation
    - Document all public classes and methods
    - Include parameter descriptions and return types
    - Include usage examples for each method
    - Document exceptions that can be raised
    - _Requirements: 10.5_

- [x] 18. Final checkpoint - Ensure all tests pass
  - Run full test suite with property tests (100+ iterations each)
  - Verify all 25 correctness properties pass
  - Verify all integration tests pass
  - Verify all adversarial tests pass
  - Verify all performance tests meet targets
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end functionality
- Adversarial tests verify resilience to failures and edge cases
- Performance tests verify throughput and latency targets
- All property tests are tagged with feature name and property number
- Tasks 1-9 are complete, tasks 10-18 are pending
- Task 15 adds goal modification functionality (Requirements 9.3, 9.4, 9.5)
- Task 16 has comprehensive integration and adversarial testing (17 sub-tasks)
- Task 17 has comprehensive documentation (6 sub-tasks)
- Total: 18 top-level tasks with extensive sub-task breakdown for clarity
