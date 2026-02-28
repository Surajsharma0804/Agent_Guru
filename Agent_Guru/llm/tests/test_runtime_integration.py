"""
Integration tests for LLM Runtime with Self-Improvement Engine.

Tests the complete integration between LLM runtime and learning systems.

**Validates: Requirements 16.1-16.6, LLM runtime integration**

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time
from typing import Dict, Any

from Agent_Guru.llm.runtime import (
    LLMRuntime,
    LLMRequest,
    LLMResponse,
    Message,
    ModelProvider,
    create_runtime_with_learning
)
from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine


class TestLLMRuntimeIntegration:
    """Integration tests for LLM runtime with self-improvement."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except PermissionError:
                time.sleep(0.1)
                try:
                    os.unlink(path)
                except:
                    pass
    
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
    def runtime(self, engine):
        """Create runtime with learning enabled."""
        return LLMRuntime(
            self_improvement_engine=engine,
            enable_learning=True
        )
    
    def test_runtime_initialization(self, runtime, engine):
        """Test that runtime initializes with engine."""
        assert runtime.self_improvement_engine is engine
        assert runtime.enable_learning is True
        assert len(runtime.active_sessions) == 0
    
    def test_execute_without_learning(self):
        """Test LLM execution without learning enabled."""
        runtime = LLMRuntime(
            self_improvement_engine=None,
            enable_learning=False
        )
        
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Hello")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute
        response = runtime.execute(request)
        
        # Verify response
        assert response.content is not None
        assert response.latency_ms > 0
        assert response.total_tokens > 0
    
    def test_execute_with_learning(self, runtime, engine):
        """Test LLM execution with learning integration."""
        # Register a prompt type
        engine.prompt_evolution.register_prompt(
            prompt_type="greeting",
            content="You are a helpful assistant."
        )
        
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Hello")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute with prompt type
        response = runtime.execute(request, prompt_type="greeting")
        
        # Verify response
        assert response.content is not None
        assert response.latency_ms > 0
        assert response.total_tokens > 0
        
        # Verify learning recorded
        prompt_version = engine.prompt_evolution.get_active_prompt("greeting")
        assert prompt_version is not None
        assert prompt_version.total_uses == 1
    
    def test_prompt_evolution_integration(self, runtime, engine):
        """Test that runtime uses evolved prompts."""
        # Register original prompt
        engine.prompt_evolution.register_prompt(
            prompt_type="test_prompt",
            content="Original prompt",
            version=1
        )
        
        # Register improved version (automatically becomes active)
        engine.prompt_evolution.register_prompt(
            prompt_type="test_prompt",
            content="Improved prompt",
            version=2
        )
        
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Test")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute - should use improved prompt
        response = runtime.execute(request, prompt_type="test_prompt")
        
        # Verify evolved prompt was used
        prompt_version = engine.prompt_evolution.get_active_prompt("test_prompt")
        assert prompt_version.version == 2
        assert prompt_version.content == "Improved prompt"
    
    def test_hallucination_detection_integration(self, runtime, engine):
        """Test hallucination detection callback."""
        # Create hallucination detector
        def detect_hallucination(content: str) -> bool:
            return "hallucination" in content.lower()
        
        # Create runtime with detector
        runtime_with_detector = LLMRuntime(
            self_improvement_engine=engine,
            enable_learning=True,
            hallucination_detector=detect_hallucination
        )
        
        # Register prompt type
        engine.prompt_evolution.register_prompt(
            prompt_type="test_hallucination",
            content="Test prompt"
        )
        
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Test")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute
        response = runtime_with_detector.execute(
            request,
            prompt_type="test_hallucination"
        )
        
        # Verify response recorded
        prompt_version = engine.prompt_evolution.get_active_prompt("test_hallucination")
        assert prompt_version.total_uses == 1
    
    def test_response_quality_recording(self, runtime, engine):
        """Test that response quality is recorded."""
        # Register prompt type
        engine.prompt_evolution.register_prompt(
            prompt_type="quality_test",
            content="Test prompt"
        )
        
        # Execute multiple requests
        for i in range(5):
            request = LLMRequest(
                messages=[Message(role="user", content=f"Test {i}")],
                model="gpt-3.5-turbo",
                provider=ModelProvider.OPENAI
            )
            
            response = runtime.execute(request, prompt_type="quality_test")
            assert response.content is not None
        
        # Verify all recorded
        prompt_version = engine.prompt_evolution.get_active_prompt("quality_test")
        assert prompt_version.total_uses == 5
    
    def test_session_management(self, runtime):
        """Test session history management."""
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Hello")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute with session
        response = runtime.execute(request, session_id="session_1")
        
        # Verify session history
        history = runtime.get_session_history("session_1")
        assert len(history) == 2  # User message + assistant response
        assert history[0].role == "user"
        assert history[0].content == "Hello"
        assert history[1].role == "assistant"
        
        # Clear session
        runtime.clear_session("session_1")
        history = runtime.get_session_history("session_1")
        assert len(history) == 0
    
    def test_create_runtime_with_learning(self, temp_db):
        """Test convenience function for creating runtime."""
        runtime = create_runtime_with_learning(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100
        )
        
        assert runtime is not None
        assert runtime.self_improvement_engine is not None
        assert runtime.enable_learning is True
        
        # Test it works
        request = LLMRequest(
            messages=[Message(role="user", content="Test")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        response = runtime.execute(request)
        assert response.content is not None
        
        # Cleanup
        runtime.self_improvement_engine.close()
        time.sleep(0.1)
    
    def test_failure_recording(self, runtime, engine):
        """Test that failures are recorded."""
        # Register prompt type
        engine.prompt_evolution.register_prompt(
            prompt_type="failure_test",
            content="Test prompt"
        )
        
        # Mock a failing execution
        original_execute = runtime._execute_llm
        
        def failing_execute(request):
            raise Exception("Test failure")
        
        runtime._execute_llm = failing_execute
        
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Test")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Execute - should fail but record
        with pytest.raises(Exception):
            runtime.execute(request, prompt_type="failure_test")
        
        # Verify failure recorded
        prompt_version = engine.prompt_evolution.get_active_prompt("failure_test")
        assert prompt_version.total_uses == 1
        
        # Restore original
        runtime._execute_llm = original_execute


@pytest.mark.integration
class TestLLMRuntimePerformance:
    """Performance tests for LLM runtime integration."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except:
                pass
    
    @pytest.fixture
    def runtime(self, temp_db):
        """Create runtime with learning."""
        runtime = create_runtime_with_learning(temp_db)
        
        # Register prompt type
        runtime.self_improvement_engine.prompt_evolution.register_prompt(
            prompt_type="perf_test",
            content="Test prompt"
        )
        
        yield runtime
        runtime.self_improvement_engine.close()
        time.sleep(0.1)
    
    def test_runtime_overhead(self, runtime):
        """
        Test that runtime overhead is reasonable.
        
        Validates: Requirement 16.5
        
        Note: This test measures absolute overhead for runtime operations.
        """
        # Create request
        request = LLMRequest(
            messages=[Message(role="user", content="Test")],
            model="gpt-3.5-turbo",
            provider=ModelProvider.OPENAI
        )
        
        # Measure execution time
        start = time.perf_counter()
        for i in range(10):
            response = runtime.execute(
                request,
                session_id=f"perf_{i}",
                prompt_type="perf_test"
            )
        total_time = time.perf_counter() - start
        
        # Calculate average time per request
        avg_time_per_request_ms = (total_time / 10) * 1000
        
        print(f"\nRuntime performance:")
        print(f"Total time: {total_time*1000:.2f}ms")
        print(f"Average per request: {avg_time_per_request_ms:.2f}ms")
        
        # Average time should be reasonable (<500ms per request)
        # This includes prompt evolution, execution, and quality recording
        assert avg_time_per_request_ms < 500, f"Average time {avg_time_per_request_ms:.2f}ms exceeds 500ms threshold"
    
    def test_concurrent_execution(self, runtime):
        """Test that multiple requests can be handled."""
        import threading
        
        results = []
        
        def execute_request(request_id: int):
            request = LLMRequest(
                messages=[Message(role="user", content=f"Test {request_id}")],
                model="gpt-3.5-turbo",
                provider=ModelProvider.OPENAI
            )
            
            response = runtime.execute(
                request,
                session_id=f"concurrent_{request_id}",
                prompt_type="perf_test"
            )
            results.append(response)
        
        # Execute requests concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=execute_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Verify all succeeded
        assert len(results) == 5
        assert all(r.content is not None for r in results)
