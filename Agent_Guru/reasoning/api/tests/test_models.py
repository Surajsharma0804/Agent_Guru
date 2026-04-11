"""
Tests for API models.

This module tests the Pydantic models used for API requests and responses.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from Agent_Guru.reasoning.api.models import (
    ProcessRequest,
    ProcessResponse,
    ConversationResponse,
    TaskStatusResponse,
    ErrorResponse,
)


class TestProcessRequest:
    """Tests for ProcessRequest model."""
    
    def test_valid_request(self):
        """Test valid process request."""
        request = ProcessRequest(
            text="set a timer for 5 minutes",
            user_id="user_123",
            source="text",
        )
        
        assert request.text == "set a timer for 5 minutes"
        assert request.user_id == "user_123"
        assert request.source == "text"
        assert request.conversation_id is None
        assert request.metadata == {}
    
    def test_request_with_conversation(self):
        """Test request with conversation ID."""
        request = ProcessRequest(
            text="make it 10 minutes",
            user_id="user_123",
            conversation_id="conv_456",
            source="voice",
        )
        
        assert request.conversation_id == "conv_456"
        assert request.source == "voice"
    
    def test_empty_text_fails(self):
        """Test that empty text fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessRequest(
                text="",
                user_id="user_123",
            )
        
        assert "text" in str(exc_info.value).lower()
    
    def test_whitespace_text_fails(self):
        """Test that whitespace-only text fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessRequest(
                text="   ",
                user_id="user_123",
            )
        
        assert "text" in str(exc_info.value).lower()
    
    def test_invalid_source_fails(self):
        """Test that invalid source fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessRequest(
                text="hello",
                user_id="user_123",
                source="invalid",
            )
        
        assert "source" in str(exc_info.value).lower()
    
    def test_text_stripped(self):
        """Test that text is stripped of whitespace."""
        request = ProcessRequest(
            text="  hello world  ",
            user_id="user_123",
        )
        
        assert request.text == "hello world"


class TestProcessResponse:
    """Tests for ProcessResponse model."""
    
    def test_valid_response(self):
        """Test valid process response."""
        response = ProcessResponse(
            response="Timer set for 5 minutes",
            confidence=0.98,
            intent_type="set_timer",
            success=True,
            fast_path=True,
            latency_ms=234.5,
            stage_latencies={"intent_detection": 50.2},
        )
        
        assert response.response == "Timer set for 5 minutes"
        assert response.confidence == 0.98
        assert response.intent_type == "set_timer"
        assert response.success is True
        assert response.fast_path is True
        assert response.latency_ms == 234.5
    
    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid confidence
        response = ProcessResponse(
            response="test",
            confidence=0.5,
            success=True,
            latency_ms=100.0,
        )
        assert response.confidence == 0.5
        
        # Invalid confidence (too low)
        with pytest.raises(ValidationError):
            ProcessResponse(
                response="test",
                confidence=-0.1,
                success=True,
                latency_ms=100.0,
            )
        
        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            ProcessResponse(
                response="test",
                confidence=1.1,
                success=True,
                latency_ms=100.0,
            )
    
    def test_negative_latency_fails(self):
        """Test that negative latency fails validation."""
        with pytest.raises(ValidationError):
            ProcessResponse(
                response="test",
                confidence=0.9,
                success=True,
                latency_ms=-10.0,
            )


class TestConversationResponse:
    """Tests for ConversationResponse model."""
    
    def test_valid_conversation(self):
        """Test valid conversation response."""
        now = datetime.utcnow()
        response = ConversationResponse(
            conversation_id="conv_456",
            user_id="user_123",
            turn_count=5,
            recent_turns=[],
            entities={},
            created_at=now,
            updated_at=now,
        )
        
        assert response.conversation_id == "conv_456"
        assert response.user_id == "user_123"
        assert response.turn_count == 5
    
    def test_negative_turn_count_fails(self):
        """Test that negative turn count fails validation."""
        now = datetime.utcnow()
        with pytest.raises(ValidationError):
            ConversationResponse(
                conversation_id="conv_456",
                user_id="user_123",
                turn_count=-1,
                created_at=now,
                updated_at=now,
            )


class TestTaskStatusResponse:
    """Tests for TaskStatusResponse model."""
    
    def test_valid_task_status(self):
        """Test valid task status response."""
        now = datetime.utcnow()
        response = TaskStatusResponse(
            task_id="task_789",
            status="running",
            progress=0.65,
            created_at=now,
            updated_at=now,
        )
        
        assert response.task_id == "task_789"
        assert response.status == "running"
        assert response.progress == 0.65
    
    def test_invalid_status_fails(self):
        """Test that invalid status fails validation."""
        now = datetime.utcnow()
        with pytest.raises(ValidationError):
            TaskStatusResponse(
                task_id="task_789",
                status="invalid",
                created_at=now,
                updated_at=now,
            )
    
    def test_progress_bounds(self):
        """Test progress must be between 0 and 1."""
        now = datetime.utcnow()
        
        # Valid progress
        response = TaskStatusResponse(
            task_id="task_789",
            status="running",
            progress=0.5,
            created_at=now,
            updated_at=now,
        )
        assert response.progress == 0.5
        
        # Invalid progress (too low)
        with pytest.raises(ValidationError):
            TaskStatusResponse(
                task_id="task_789",
                status="running",
                progress=-0.1,
                created_at=now,
                updated_at=now,
            )
        
        # Invalid progress (too high)
        with pytest.raises(ValidationError):
            TaskStatusResponse(
                task_id="task_789",
                status="running",
                progress=1.1,
                created_at=now,
                updated_at=now,
            )


class TestErrorResponse:
    """Tests for ErrorResponse model."""
    
    def test_valid_error(self):
        """Test valid error response."""
        response = ErrorResponse(
            error="Invalid request",
            error_code="VALIDATION_ERROR",
            details={"field": "text"},
        )
        
        assert response.error == "Invalid request"
        assert response.error_code == "VALIDATION_ERROR"
        assert response.details == {"field": "text"}
        assert response.trace_id is None
