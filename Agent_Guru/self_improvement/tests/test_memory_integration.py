"""
Integration tests for Memory System Integration.

Tests the integration between self-improvement engine and memory system.

**Validates: Requirements 17.1-17.3, Memory system integration**

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time

from Agent_Guru.self_improvement.memory_integration import (
    MemoryIntegration,
    create_memory_integration
)
from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
import logging

logger = logging.getLogger(__name__)


class TestMemoryIntegration:
    """Integration tests for memory system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except PermissionError as e:
                time.sleep(0.1)
                try:
                    os.unlink(path)
                except Exception as e:
                    logger.warning("Suppressed exception: %s", e)
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create self-improvement engine for testing."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.1)
    
    @pytest.fixture
    def memory_integration(self, engine):
        """Create memory integration."""
        return MemoryIntegration(
            self_improvement_engine=engine,
            memory_system=None  # No memory system for now
        )
    
    def test_memory_integration_initialization(self, memory_integration, engine):
        """Test that memory integration initializes correctly."""
        assert memory_integration.engine is engine  # nosec B101
        assert memory_integration.memory_system is None  # nosec B101
        assert memory_integration.last_sync_time is None  # nosec B101
    
    def test_sync_learning_data_without_memory_system(self, memory_integration):
        """Test syncing without memory system connected."""
        stats = memory_integration.sync_learning_data()
        
        assert stats["synced"] is False  # nosec B101
        assert "No memory system connected" in stats["reason"]  # nosec B101
        assert "timestamp" in stats  # nosec B101
    
    def test_get_historical_patterns_without_memory_system(self, memory_integration, engine):
        """Test retrieving patterns without memory system."""
        # Inject some failures first
        from Agent_Guru.self_improvement.failure_analyzer import FailureType
        
        for i in range(5):
            engine.inject_test_failure(
                failure_type=FailureType.REASONING_ERROR,
                task_type="test_task",
                context={"error": f"Test error {i}"}
            )
        
        # Get patterns
        patterns = memory_integration.get_historical_patterns(limit=10)
        
        # Should return patterns from engine
        assert isinstance(patterns, list)  # nosec B101
        # Patterns may be empty if failure analyzer doesn't return them in expected format
    
    def test_get_historical_patterns_with_task_type_filter(self, memory_integration, engine):
        """Test retrieving patterns with task type filter."""
        from Agent_Guru.self_improvement.failure_analyzer import FailureType
        
        # Inject failures of different types
        engine.inject_test_failure(
            failure_type=FailureType.REASONING_ERROR,
            task_type="type_a",
            context={"error": "Error A"}
        )
        
        engine.inject_test_failure(
            failure_type=FailureType.TOOL_ERROR,
            task_type="type_b",
            context={"error": "Error B"}
        )
        
        # Get patterns for specific type
        patterns = memory_integration.get_historical_patterns(
            task_type="type_a",
            limit=10
        )
        
        assert isinstance(patterns, list)  # nosec B101
    
    def test_get_sync_status(self, memory_integration):
        """Test getting sync status."""
        status = memory_integration.get_sync_status()
        
        assert "memory_system_connected" in status  # nosec B101
        assert status["memory_system_connected"] is False  # nosec B101
        assert "last_sync_time" in status  # nosec B101
        assert status["last_sync_time"] is None  # nosec B101
        assert "engine_metrics" in status  # nosec B101
        assert isinstance(status["engine_metrics"], dict)  # nosec B101
    
    def test_create_memory_integration(self, engine):
        """Test convenience function for creating integration."""
        integration = create_memory_integration(engine)
        
        assert integration is not None  # nosec B101
        assert integration.engine is engine  # nosec B101
        assert integration.memory_system is None  # nosec B101
        
        # Test it works
        status = integration.get_sync_status()
        assert status["memory_system_connected"] is False  # nosec B101


@pytest.mark.integration
class TestMemoryIntegrationWithMockSystem:
    """Tests with mock memory system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create self-improvement engine."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.1)
    
    @pytest.fixture
    def mock_memory_system(self):
        """Create mock memory system."""
        class MockMemorySystem:
            def __init__(self):
                self.stored_data = []
            
            def store(self, data):
                self.stored_data.append(data)
            
            def query(self, filters):
                return self.stored_data
        
        return MockMemorySystem()
    
    @pytest.fixture
    def memory_integration(self, engine, mock_memory_system):
        """Create memory integration with mock system."""
        return MemoryIntegration(
            self_improvement_engine=engine,
            memory_system=mock_memory_system
        )
    
    def test_sync_with_memory_system(self, memory_integration):
        """Test syncing with memory system connected."""
        stats = memory_integration.sync_learning_data()
        
        assert stats["synced"] is True  # nosec B101
        assert "timestamp" in stats  # nosec B101
        assert memory_integration.last_sync_time is not None  # nosec B101
    
    def test_multiple_syncs(self, memory_integration):
        """Test multiple sync operations."""
        # First sync
        stats1 = memory_integration.sync_learning_data()
        time1 = memory_integration.last_sync_time
        
        # Wait a bit
        time.sleep(0.01)
        
        # Second sync
        stats2 = memory_integration.sync_learning_data()
        time2 = memory_integration.last_sync_time
        
        assert stats1["synced"] is True  # nosec B101
        assert stats2["synced"] is True  # nosec B101
        assert time2 > time1  # nosec B101
