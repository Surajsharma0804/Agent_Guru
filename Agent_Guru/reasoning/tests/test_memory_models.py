"""
Comprehensive tests for Memory data models.

Tests cover:
- Base Memory class validation
- MemoryType enum
- EpisodicMemory class
- SemanticMemory class
- PreferenceMemory class
- TaskMemory class
- Field validators
- JSON serialization/deserialization
- Edge cases and error conditions

Target Coverage: 100%
"""

import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    Memory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)


class TestMemoryType:
    """Tests for MemoryType enum."""
    
    def test_memory_type_values(self):
        """Test that MemoryType has all expected values."""
        assert MemoryType.EPISODIC == "episodic"
        assert MemoryType.SEMANTIC == "semantic"
        assert MemoryType.PREFERENCE == "preference"
        assert MemoryType.TASK == "task"
    
    def test_memory_type_iteration(self):
        """Test that all memory types can be iterated."""
        types = list(MemoryType)
        assert len(types) == 4
        assert MemoryType.EPISODIC in types
        assert MemoryType.SEMANTIC in types
        assert MemoryType.PREFERENCE in types
        assert MemoryType.TASK in types


class TestMemoryBaseClass:
    """Tests for base Memory class."""

    
    def test_memory_creation_with_defaults(self):
        """Test creating Memory with minimal required fields."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory content",
            user_id="user_123"
        )
        
        assert isinstance(memory.memory_id, UUID)
        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.content == "Test memory content"
        assert memory.embedding is None
        assert memory.metadata == {}
        assert memory.relevance_score == 1.0
        assert isinstance(memory.timestamp, datetime)
        assert memory.user_id == "user_123"
    
    def test_memory_creation_with_all_fields(self):
        """Test creating Memory with all fields specified."""
        memory_id = uuid4()
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        embedding = [0.1] * 768
        
        memory = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.SEMANTIC,
            content="Full memory content",
            embedding=embedding,
            metadata={"key": "value"},
            relevance_score=0.8,
            timestamp=timestamp,
            user_id="user_456"
        )
        
        assert memory.memory_id == memory_id
        assert memory.memory_type == MemoryType.SEMANTIC
        assert memory.content == "Full memory content"
        assert memory.embedding == embedding
        assert memory.metadata == {"key": "value"}
        assert memory.relevance_score == 0.8
        assert memory.timestamp == timestamp
        assert memory.user_id == "user_456"

    
    def test_memory_content_validation_empty(self):
        """Test that empty content raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("content" in str(e) for e in errors)
    
    def test_memory_content_validation_whitespace(self):
        """Test that whitespace-only content raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="   \n\t  ",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("whitespace" in str(e).lower() for e in errors)
    
    def test_memory_content_strips_whitespace(self):
        """Test that content whitespace is stripped."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="  Test content  ",
            user_id="user_123"
        )
        
        assert memory.content == "Test content"
    
    def test_memory_content_max_length(self):
        """Test that content exceeding max length raises ValidationError."""
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content=long_content,
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("content" in str(e) for e in errors)

    
    def test_memory_embedding_validation_wrong_dimension(self):
        """Test that embedding with wrong dimension raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                embedding=[0.1] * 512,  # Wrong dimension
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("768" in str(e) for e in errors)
    
    def test_memory_embedding_validation_correct_dimension(self):
        """Test that embedding with correct dimension is accepted."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            embedding=[0.1] * 768,
            user_id="user_123"
        )
        
        assert len(memory.embedding) == 768
    
    def test_memory_embedding_validation_infinite_values(self):
        """Test that embedding with infinite values raises ValidationError."""
        embedding = [0.1] * 767 + [float('inf')]
        
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                embedding=embedding,
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("finite" in str(e).lower() for e in errors)
    
    def test_memory_relevance_score_validation_range(self):
        """Test that relevance_score must be between 0.0 and 1.0."""
        # Test below range
        with pytest.raises(ValidationError):
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                relevance_score=-0.1,
                user_id="user_123"
            )
        
        # Test above range
        with pytest.raises(ValidationError):
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                relevance_score=1.1,
                user_id="user_123"
            )
        
        # Test valid values
        memory1 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            relevance_score=0.0,
            user_id="user_123"
        )
        assert memory1.relevance_score == 0.0
        
        memory2 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            relevance_score=1.0,
            user_id="user_123"
        )
        assert memory2.relevance_score == 1.0

    
    def test_memory_user_id_validation_empty(self):
        """Test that empty user_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                user_id=""
            )
        
        errors = exc_info.value.errors()
        assert any("user_id" in str(e) for e in errors)
    
    def test_memory_user_id_validation_whitespace(self):
        """Test that whitespace-only user_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Memory(
                memory_type=MemoryType.EPISODIC,
                content="Test content",
                user_id="   "
            )
        
        errors = exc_info.value.errors()
        assert any("whitespace" in str(e).lower() for e in errors)
    
    def test_memory_user_id_strips_whitespace(self):
        """Test that user_id whitespace is stripped."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            user_id="  user_123  "
        )
        
        assert memory.user_id == "user_123"
    
    def test_memory_json_serialization(self):
        """Test that Memory can be serialized to JSON."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            user_id="user_123"
        )
        
        json_str = memory.model_dump_json()
        data = json.loads(json_str)
        
        assert data["memory_type"] == "episodic"
        assert data["content"] == "Test content"
        assert data["user_id"] == "user_123"
        assert "memory_id" in data
        assert "timestamp" in data
    
    def test_memory_json_deserialization(self):
        """Test that Memory can be deserialized from JSON."""
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test content",
            user_id="user_123"
        )
        
        json_str = memory.model_dump_json()
        restored = Memory.model_validate_json(json_str)
        
        assert restored.memory_id == memory.memory_id
        assert restored.memory_type == memory.memory_type
        assert restored.content == memory.content
        assert restored.user_id == memory.user_id


class TestEpisodicMemory:
    """Tests for EpisodicMemory class."""

    
    def test_episodic_memory_creation(self):
        """Test creating EpisodicMemory with required fields."""
        memory = EpisodicMemory(
            content="User set a timer for 5 minutes",
            action_taken="set_timer",
            result="Timer set successfully",
            success=True,
            user_id="user_123"
        )
        
        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.content == "User set a timer for 5 minutes"
        assert memory.action_taken == "set_timer"
        assert memory.result == "Timer set successfully"
        assert memory.success is True
        assert memory.context == {}
        assert memory.user_id == "user_123"
    
    def test_episodic_memory_with_context(self):
        """Test creating EpisodicMemory with context."""
        memory = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            context={"location": "kitchen", "time": "evening"},
            user_id="user_123"
        )
        
        assert memory.context == {"location": "kitchen", "time": "evening"}
    
    def test_episodic_memory_type_enforcement(self):
        """Test that memory_type is enforced to be EPISODIC."""
        # Default should be EPISODIC
        memory = EpisodicMemory(
            content="Test",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123"
        )
        assert memory.memory_type == MemoryType.EPISODIC
        
        # Trying to set different type should fail
        with pytest.raises(ValidationError) as exc_info:
            EpisodicMemory(
                memory_type=MemoryType.SEMANTIC,
                content="Test",
                action_taken="test",
                result="success",
                success=True,
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("EPISODIC" in str(e) for e in errors)
    
    def test_episodic_memory_action_taken_validation(self):
        """Test action_taken field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            EpisodicMemory(
                content="Test",
                action_taken="",
                result="success",
                success=True,
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            EpisodicMemory(
                content="Test",
                action_taken="   ",
                result="success",
                success=True,
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = EpisodicMemory(
            content="Test",
            action_taken="  set_timer  ",
            result="success",
            success=True,
            user_id="user_123"
        )
        assert memory.action_taken == "set_timer"

    
    def test_episodic_memory_result_validation(self):
        """Test result field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            EpisodicMemory(
                content="Test",
                action_taken="test",
                result="",
                success=True,
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            EpisodicMemory(
                content="Test",
                action_taken="test",
                result="   ",
                success=True,
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = EpisodicMemory(
            content="Test",
            action_taken="test",
            result="  Success  ",
            success=True,
            user_id="user_123"
        )
        assert memory.result == "Success"
    
    def test_episodic_memory_json_serialization(self):
        """Test EpisodicMemory JSON serialization."""
        memory = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            context={"location": "kitchen"},
            user_id="user_123"
        )
        
        json_str = memory.model_dump_json()
        data = json.loads(json_str)
        
        assert data["memory_type"] == "episodic"
        assert data["action_taken"] == "set_timer"
        assert data["result"] == "Success"
        assert data["success"] is True
        assert data["context"] == {"location": "kitchen"}


class TestSemanticMemory:
    """Tests for SemanticMemory class."""
    
    def test_semantic_memory_creation(self):
        """Test creating SemanticMemory with required fields."""
        memory = SemanticMemory(
            content="User's favorite color is blue",
            fact="favorite_color=blue",
            source="user_stated",
            confidence=1.0,
            user_id="user_123"
        )
        
        assert memory.memory_type == MemoryType.SEMANTIC
        assert memory.content == "User's favorite color is blue"
        assert memory.fact == "favorite_color=blue"
        assert memory.source == "user_stated"
        assert memory.confidence == 1.0
        assert memory.user_id == "user_123"

    
    def test_semantic_memory_type_enforcement(self):
        """Test that memory_type is enforced to be SEMANTIC."""
        # Default should be SEMANTIC
        memory = SemanticMemory(
            content="Test",
            fact="test=true",
            source="test",
            confidence=1.0,
            user_id="user_123"
        )
        assert memory.memory_type == MemoryType.SEMANTIC
        
        # Trying to set different type should fail
        with pytest.raises(ValidationError) as exc_info:
            SemanticMemory(
                memory_type=MemoryType.EPISODIC,
                content="Test",
                fact="test=true",
                source="test",
                confidence=1.0,
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("SEMANTIC" in str(e) for e in errors)
    
    def test_semantic_memory_fact_validation(self):
        """Test fact field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="",
                source="test",
                confidence=1.0,
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="   ",
                source="test",
                confidence=1.0,
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = SemanticMemory(
            content="Test",
            fact="  test=true  ",
            source="test",
            confidence=1.0,
            user_id="user_123"
        )
        assert memory.fact == "test=true"
    
    def test_semantic_memory_source_validation(self):
        """Test source field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="test=true",
                source="",
                confidence=1.0,
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="test=true",
                source="   ",
                confidence=1.0,
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = SemanticMemory(
            content="Test",
            fact="test=true",
            source="  user_stated  ",
            confidence=1.0,
            user_id="user_123"
        )
        assert memory.source == "user_stated"

    
    def test_semantic_memory_confidence_validation(self):
        """Test confidence field validation."""
        # Below range
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="test=true",
                source="test",
                confidence=-0.1,
                user_id="user_123"
            )
        
        # Above range
        with pytest.raises(ValidationError):
            SemanticMemory(
                content="Test",
                fact="test=true",
                source="test",
                confidence=1.1,
                user_id="user_123"
            )
        
        # Valid values
        memory1 = SemanticMemory(
            content="Test",
            fact="test=true",
            source="test",
            confidence=0.0,
            user_id="user_123"
        )
        assert memory1.confidence == 0.0
        
        memory2 = SemanticMemory(
            content="Test",
            fact="test=true",
            source="test",
            confidence=1.0,
            user_id="user_123"
        )
        assert memory2.confidence == 1.0


class TestPreferenceMemory:
    """Tests for PreferenceMemory class."""
    
    def test_preference_memory_creation(self):
        """Test creating PreferenceMemory with required fields."""
        memory = PreferenceMemory(
            content="User prefers morning notifications",
            preference_key="notification_time",
            preference_value="morning",
            learned_from="explicit",
            user_id="user_123"
        )
        
        assert memory.memory_type == MemoryType.PREFERENCE
        assert memory.content == "User prefers morning notifications"
        assert memory.preference_key == "notification_time"
        assert memory.preference_value == "morning"
        assert memory.learned_from == "explicit"
        assert memory.user_id == "user_123"
    
    def test_preference_memory_type_enforcement(self):
        """Test that memory_type is enforced to be PREFERENCE."""
        # Default should be PREFERENCE
        memory = PreferenceMemory(
            content="Test",
            preference_key="test_key",
            preference_value="test_value",
            learned_from="explicit",
            user_id="user_123"
        )
        assert memory.memory_type == MemoryType.PREFERENCE
        
        # Trying to set different type should fail
        with pytest.raises(ValidationError) as exc_info:
            PreferenceMemory(
                memory_type=MemoryType.EPISODIC,
                content="Test",
                preference_key="test_key",
                preference_value="test_value",
                learned_from="explicit",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("PREFERENCE" in str(e) for e in errors)

    
    def test_preference_memory_key_validation(self):
        """Test preference_key field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            PreferenceMemory(
                content="Test",
                preference_key="",
                preference_value="test",
                learned_from="explicit",
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            PreferenceMemory(
                content="Test",
                preference_key="   ",
                preference_value="test",
                learned_from="explicit",
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = PreferenceMemory(
            content="Test",
            preference_key="  test_key  ",
            preference_value="test",
            learned_from="explicit",
            user_id="user_123"
        )
        assert memory.preference_key == "test_key"
    
    def test_preference_memory_value_validation(self):
        """Test preference_value field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            PreferenceMemory(
                content="Test",
                preference_key="test",
                preference_value="",
                learned_from="explicit",
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            PreferenceMemory(
                content="Test",
                preference_key="test",
                preference_value="   ",
                learned_from="explicit",
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = PreferenceMemory(
            content="Test",
            preference_key="test",
            preference_value="  test_value  ",
            learned_from="explicit",
            user_id="user_123"
        )
        assert memory.preference_value == "test_value"
    
    def test_preference_memory_learned_from_validation(self):
        """Test learned_from field validation."""
        # Valid values
        for value in ["explicit", "inferred", "observed", "default"]:
            memory = PreferenceMemory(
                content="Test",
                preference_key="test",
                preference_value="test",
                learned_from=value,
                user_id="user_123"
            )
            assert memory.learned_from == value
        
        # Case insensitive
        memory = PreferenceMemory(
            content="Test",
            preference_key="test",
            preference_value="test",
            learned_from="EXPLICIT",
            user_id="user_123"
        )
        assert memory.learned_from == "explicit"
        
        # Invalid value
        with pytest.raises(ValidationError) as exc_info:
            PreferenceMemory(
                content="Test",
                preference_key="test",
                preference_value="test",
                learned_from="invalid",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("explicit" in str(e).lower() for e in errors)



class TestTaskMemory:
    """Tests for TaskMemory class."""
    
    def test_task_memory_creation(self):
        """Test creating TaskMemory with required fields."""
        memory = TaskMemory(
            content="Multi-step task to book restaurant",
            task_id="task_456",
            task_description="Book restaurant for 7pm",
            outcome="success",
            user_id="user_123"
        )
        
        assert memory.memory_type == MemoryType.TASK
        assert memory.content == "Multi-step task to book restaurant"
        assert memory.task_id == "task_456"
        assert memory.task_description == "Book restaurant for 7pm"
        assert memory.outcome == "success"
        assert memory.lessons_learned == []
        assert memory.user_id == "user_123"
    
    def test_task_memory_with_lessons(self):
        """Test creating TaskMemory with lessons learned."""
        lessons = ["User prefers Italian", "Needs 1 hour prep time"]
        memory = TaskMemory(
            content="Task completed",
            task_id="task_456",
            task_description="Book restaurant",
            outcome="success",
            lessons_learned=lessons,
            user_id="user_123"
        )
        
        assert memory.lessons_learned == lessons
    
    def test_task_memory_type_enforcement(self):
        """Test that memory_type is enforced to be TASK."""
        # Default should be TASK
        memory = TaskMemory(
            content="Test",
            task_id="task_1",
            task_description="Test task",
            outcome="success",
            user_id="user_123"
        )
        assert memory.memory_type == MemoryType.TASK
        
        # Trying to set different type should fail
        with pytest.raises(ValidationError) as exc_info:
            TaskMemory(
                memory_type=MemoryType.EPISODIC,
                content="Test",
                task_id="task_1",
                task_description="Test task",
                outcome="success",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("TASK" in str(e) for e in errors)
    
    def test_task_memory_task_id_validation(self):
        """Test task_id field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="",
                task_description="Test",
                outcome="success",
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="   ",
                task_description="Test",
                outcome="success",
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = TaskMemory(
            content="Test",
            task_id="  task_1  ",
            task_description="Test",
            outcome="success",
            user_id="user_123"
        )
        assert memory.task_id == "task_1"

    
    def test_task_memory_description_validation(self):
        """Test task_description field validation."""
        # Empty string
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="",
                outcome="success",
                user_id="user_123"
            )
        
        # Whitespace only
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="   ",
                outcome="success",
                user_id="user_123"
            )
        
        # Strips whitespace
        memory = TaskMemory(
            content="Test",
            task_id="task_1",
            task_description="  Test task  ",
            outcome="success",
            user_id="user_123"
        )
        assert memory.task_description == "Test task"
    
    def test_task_memory_outcome_validation(self):
        """Test outcome field validation."""
        # Valid values
        for outcome in ["success", "failure", "partial", "cancelled", "timeout"]:
            memory = TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="Test",
                outcome=outcome,
                user_id="user_123"
            )
            assert memory.outcome == outcome
        
        # Case insensitive
        memory = TaskMemory(
            content="Test",
            task_id="task_1",
            task_description="Test",
            outcome="SUCCESS",
            user_id="user_123"
        )
        assert memory.outcome == "success"
        
        # Invalid value
        with pytest.raises(ValidationError) as exc_info:
            TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="Test",
                outcome="invalid",
                user_id="user_123"
            )
        
        errors = exc_info.value.errors()
        assert any("success" in str(e).lower() for e in errors)
    
    def test_task_memory_lessons_validation(self):
        """Test lessons_learned field validation."""
        # Empty lessons should be filtered out
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="Test",
                outcome="success",
                lessons_learned=["Valid lesson", "", "Another lesson"],
                user_id="user_123"
            )
        
        # Whitespace-only lessons should be filtered out
        with pytest.raises(ValidationError):
            TaskMemory(
                content="Test",
                task_id="task_1",
                task_description="Test",
                outcome="success",
                lessons_learned=["Valid lesson", "   ", "Another lesson"],
                user_id="user_123"
            )
        
        # Valid lessons with whitespace should be stripped
        memory = TaskMemory(
            content="Test",
            task_id="task_1",
            task_description="Test",
            outcome="success",
            lessons_learned=["  Lesson 1  ", "  Lesson 2  "],
            user_id="user_123"
        )
        assert memory.lessons_learned == ["Lesson 1", "Lesson 2"]
    
    def test_task_memory_json_serialization(self):
        """Test TaskMemory JSON serialization."""
        memory = TaskMemory(
            content="Task completed",
            task_id="task_456",
            task_description="Book restaurant",
            outcome="success",
            lessons_learned=["Lesson 1", "Lesson 2"],
            user_id="user_123"
        )
        
        json_str = memory.model_dump_json()
        data = json.loads(json_str)
        
        assert data["memory_type"] == "task"
        assert data["task_id"] == "task_456"
        assert data["task_description"] == "Book restaurant"
        assert data["outcome"] == "success"
        assert data["lessons_learned"] == ["Lesson 1", "Lesson 2"]

    
    def test_task_memory_empty_lessons(self):
        """Test TaskMemory with empty lessons_learned list."""
        memory = TaskMemory(
            content="Task completed",
            task_id="task_456",
            task_description="Book restaurant",
            outcome="success",
            lessons_learned=[],
            user_id="user_123"
        )
        
        assert memory.lessons_learned == []
