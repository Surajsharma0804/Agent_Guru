"""Tests for Goal Manager.

This package contains comprehensive tests for the Goal Manager system:
- Unit tests: Specific examples and edge cases
- Property-based tests: Universal correctness properties
- Integration tests: End-to-end functionality
- Adversarial tests: Resilience to failures

Test Organization:
- test_models.py: Data model validation tests
- test_storage.py: Storage layer tests
- test_decomposer.py: Goal decomposition tests
- test_progress_tracker.py: Progress tracking tests
- test_priority_manager.py: Priority management tests
- test_dependency_resolver.py: Dependency resolution tests
- test_executor.py: Goal execution tests
- test_session_manager.py: Session persistence tests
- test_goal_manager.py: Main API tests
- test_integration.py: End-to-end integration tests
- test_properties.py: Property-based tests for all correctness properties

Test Markers:
- @pytest.mark.unit: Unit tests
- @pytest.mark.property: Property-based tests
- @pytest.mark.integration: Integration tests
- @pytest.mark.slow: Long-running tests

Property Test Format:
Each property test is tagged with:
# Feature: goal-manager, Property N: [property description]
"""
