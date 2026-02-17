"""Comprehensive unit tests for result models - 100% coverage."""

import pytest
from datetime import datetime

from Agent_Guru.reasoning.models.result import (
    ExecutionResult,
    Response,
    ResponseModality,
)


class TestExecutionResult:
    """Test ExecutionResult model."""
    
    def test_execution_result_success(self):
        """Test creating a successful execution result."""
        result = ExecutionResult(
            success=True,
            result_data={"timer_id": "timer_123", "duration": 300},
            error=None,
            execution_time=0.045,
            action_id="action_123",
            tool_id="set_timer",
            metadata={"user_id": "user_456"},
        )
        
        assert result.success
        assert result.result_data == {"timer_id": "timer_123", "duration": 300}
        assert result.error is None
        assert result.execution_time == 0.045
        assert result.action_id == "action_123"
        assert result.tool_id == "set_timer"
        assert result.metadata == {"user_id": "user_456"}
    
    def test_execution_result_failure(self):
        """Test creating a failed execution result."""
        result = ExecutionResult(
            success=False,
            result_data=None,
            error="Timeout occurred",
            execution_time=3.0,
            action_id="action_123",
            tool_id="set_timer",
        )
        
        assert not result.success
        assert result.result_data is None
        assert result.error == "Timeout occurred"
    
    def test_execution_time_validation_invalid(self):
        """Test execution time validation fails for negative value."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExecutionResult(
                success=True,
                execution_time=-1.0,
                action_id="action_123",
                tool_id="test",
            )
    
    def test_action_id_validation_invalid(self):
        """Test action ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Action ID cannot be empty"):
            ExecutionResult(
                success=True,
                execution_time=0.1,
                action_id="",
                tool_id="test",
            )
    
    def test_tool_id_validation_invalid(self):
        """Test tool ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Tool ID cannot be empty"):
            ExecutionResult(
                success=True,
                execution_time=0.1,
                action_id="action_123",
                tool_id="",
            )
    
    def test_is_timeout_true(self):
        """Test is_timeout returns True for timeout errors."""
        result = ExecutionResult(
            success=False,
            error="Execution timeout occurred",
            execution_time=3.0,
            action_id="action_123",
            tool_id="test",
        )
        
        assert result.is_timeout()
    
    def test_is_timeout_false(self):
        """Test is_timeout returns False for non-timeout errors."""
        result = ExecutionResult(
            success=False,
            error="Invalid parameter",
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        
        assert not result.is_timeout()
    
    def test_is_timeout_success(self):
        """Test is_timeout returns False for successful execution."""
        result = ExecutionResult(
            success=True,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        
        assert not result.is_timeout()
    
    def test_execution_result_equality(self):
        """Test execution result equality comparison."""
        result1 = ExecutionResult(
            success=True,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        result2 = ExecutionResult(
            success=True,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        result3 = ExecutionResult(
            success=False,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        
        assert result1 == result2
        assert result1 != result3
        assert result1 != "not a result"
    
    def test_execution_result_hash(self):
        """Test execution result hashing."""
        result1 = ExecutionResult(
            success=True,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        result2 = ExecutionResult(
            success=True,
            execution_time=0.1,
            action_id="action_123",
            tool_id="test",
        )
        
        assert hash(result1) == hash(result2)


class TestResponse:
    """Test Response model."""
    
    def test_response_creation_valid(self):
        """Test creating a valid response."""
        response = Response(
            text="Timer set for 5 minutes",
            modality=ResponseModality.BOTH,
            metadata={"intent_type": "set_timer"},
            suggestions=["Set another timer", "Cancel timer"],
            rich_content={"type": "card", "title": "Timer Active"},
            requires_user_action=False,
            action_options=[],
        )
        
        assert response.text == "Timer set for 5 minutes"
        assert response.modality == ResponseModality.BOTH
        assert response.metadata == {"intent_type": "set_timer"}
        assert len(response.suggestions) == 2
        assert response.rich_content["type"] == "card"
        assert not response.requires_user_action
    
    def test_response_text_validation_invalid_empty(self):
        """Test response text validation fails for empty text."""
        with pytest.raises(ValueError, match="Response text cannot be empty"):
            Response(text="")
    
    def test_response_text_validation_invalid_whitespace(self):
        """Test response text validation fails for whitespace-only text."""
        with pytest.raises(ValueError, match="Response text cannot be empty"):
            Response(text="   ")
    
    def test_response_suggestions_validation_invalid(self):
        """Test suggestions validation fails for empty strings."""
        with pytest.raises(ValueError, match="Suggestions cannot contain empty strings"):
            Response(
                text="Test",
                suggestions=["Valid suggestion", ""],
            )
    
    def test_response_action_options_validation_invalid(self):
        """Test action options validation fails for empty strings."""
        with pytest.raises(ValueError, match="Action options cannot contain empty strings"):
            Response(
                text="Test",
                action_options=["Valid option", "  "],
            )
    
    def test_response_is_voice_compatible_voice(self):
        """Test is_voice_compatible for voice modality."""
        response = Response(text="Test", modality=ResponseModality.VOICE)
        assert response.is_voice_compatible()
    
    def test_response_is_voice_compatible_both(self):
        """Test is_voice_compatible for both modality."""
        response = Response(text="Test", modality=ResponseModality.BOTH)
        assert response.is_voice_compatible()
    
    def test_response_is_voice_compatible_multimodal(self):
        """Test is_voice_compatible for multimodal."""
        response = Response(text="Test", modality=ResponseModality.MULTIMODAL)
        assert response.is_voice_compatible()
    
    def test_response_is_voice_compatible_text_only(self):
        """Test is_voice_compatible returns False for text-only."""
        response = Response(text="Test", modality=ResponseModality.TEXT)
        assert not response.is_voice_compatible()
    
    def test_response_is_text_compatible_text(self):
        """Test is_text_compatible for text modality."""
        response = Response(text="Test", modality=ResponseModality.TEXT)
        assert response.is_text_compatible()
    
    def test_response_is_text_compatible_both(self):
        """Test is_text_compatible for both modality."""
        response = Response(text="Test", modality=ResponseModality.BOTH)
        assert response.is_text_compatible()
    
    def test_response_is_text_compatible_multimodal(self):
        """Test is_text_compatible for multimodal."""
        response = Response(text="Test", modality=ResponseModality.MULTIMODAL)
        assert response.is_text_compatible()
    
    def test_response_is_text_compatible_visual_only(self):
        """Test is_text_compatible returns False for visual-only."""
        response = Response(text="Test", modality=ResponseModality.VISUAL)
        assert not response.is_text_compatible()
    
    def test_response_has_rich_content_true(self):
        """Test has_rich_content returns True when rich content exists."""
        response = Response(
            text="Test",
            rich_content={"type": "card", "title": "Test"},
        )
        assert response.has_rich_content()
    
    def test_response_has_rich_content_false_none(self):
        """Test has_rich_content returns False when rich content is None."""
        response = Response(text="Test", rich_content=None)
        assert not response.has_rich_content()
    
    def test_response_has_rich_content_false_empty(self):
        """Test has_rich_content returns False when rich content is empty."""
        response = Response(text="Test", rich_content={})
        assert not response.has_rich_content()
    
    def test_response_equality(self):
        """Test response equality comparison."""
        response1 = Response(text="Test", modality=ResponseModality.TEXT)
        response2 = Response(text="Test", modality=ResponseModality.TEXT)
        response3 = Response(text="Different", modality=ResponseModality.TEXT)
        
        assert response1 == response2
        assert response1 != response3
        assert response1 != "not a response"
    
    def test_response_hash(self):
        """Test response hashing."""
        response1 = Response(text="Test", modality=ResponseModality.TEXT)
        response2 = Response(text="Test", modality=ResponseModality.TEXT)
        
        assert hash(response1) == hash(response2)
    
    def test_response_modality_enum(self):
        """Test response modality enum values."""
        assert ResponseModality.VOICE == "voice"
        assert ResponseModality.TEXT == "text"
        assert ResponseModality.BOTH == "both"
        assert ResponseModality.VISUAL == "visual"
        assert ResponseModality.MULTIMODAL == "multimodal"


    def test_execution_time_validation_valid(self):
        """Test execution time validation passes for valid positive value."""
        result = ExecutionResult(
            success=True,
            execution_time=0.5,
            action_id="action_123",
            tool_id="test",
        )
        assert result.execution_time == 0.5
