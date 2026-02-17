"""Comprehensive unit tests for Sentry configuration - 100% coverage."""

import pytest
import os
from unittest.mock import patch, MagicMock

from Agent_Guru.reasoning.config.sentry_config import (
    SentryConfig,
    configure_sentry,
    before_send_filter,
    before_breadcrumb_filter,
    SentryContextManager,
    sentry_context,
)


class TestSentryConfig:
    """Test SentryConfig class."""
    
    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        config = SentryConfig(
            dsn="https://test@sentry.io/123",
            environment="production",
            release="1.0.0",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.3,
            send_default_pii=True,
            attach_stacktrace=False,
            max_breadcrumbs=100,
            debug=True,
        )
        
        assert config.dsn == "https://test@sentry.io/123"
        assert config.environment == "production"
        assert config.release == "1.0.0"
        assert config.traces_sample_rate == 0.5
        assert config.profiles_sample_rate == 0.3
        assert config.send_default_pii is True
        assert config.attach_stacktrace is False
        assert config.max_breadcrumbs == 100
        assert config.debug is True
    
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        config = SentryConfig()
        
        assert config.environment == "development"
        assert config.traces_sample_rate == 0.1
        assert config.profiles_sample_rate == 0.1
        assert config.send_default_pii is False
        assert config.attach_stacktrace is True
        assert config.max_breadcrumbs == 50
        assert config.debug is False
    
    def test_init_with_env_vars(self):
        """Test initialization with environment variables."""
        with patch.dict(os.environ, {"SENTRY_DSN": "https://env@sentry.io/456", "SENTRY_RELEASE": "2.0.0"}):
            config = SentryConfig()
            
            assert config.dsn == "https://env@sentry.io/456"
            assert config.release == "2.0.0"


class TestConfigureSentry:
    """Test configure_sentry function."""
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_configure_sentry_with_dsn(self, mock_sentry):
        """Test configuring Sentry with DSN."""
        config = SentryConfig(dsn="https://test@sentry.io/123")
        configure_sentry(config)
        
        mock_sentry.init.assert_called_once()
        call_kwargs = mock_sentry.init.call_args[1]
        assert call_kwargs["dsn"] == "https://test@sentry.io/123"
        assert call_kwargs["environment"] == "development"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_configure_sentry_without_dsn(self, mock_sentry):
        """Test configuring Sentry without DSN skips initialization."""
        config = SentryConfig(dsn=None)
        configure_sentry(config)
        
        mock_sentry.init.assert_not_called()


class TestBeforeSendFilter:
    """Test before_send_filter function."""
    
    def test_before_send_filter_adds_tags(self):
        """Test filter adds custom tags."""
        event = {}
        hint = {}
        
        result = before_send_filter(event, hint)
        
        assert result["tags"]["component"] == "reasoning_engine"
    
    def test_before_send_filter_removes_sensitive_headers(self):
        """Test filter removes sensitive headers."""
        event = {
            "request": {
                "headers": {
                    "authorization": "Bearer token",
                    "cookie": "session=123",
                    "x-api-key": "secret",
                    "content-type": "application/json",
                }
            }
        }
        hint = {}
        
        result = before_send_filter(event, hint)
        
        assert "authorization" not in result["request"]["headers"]
        assert "cookie" not in result["request"]["headers"]
        assert "x-api-key" not in result["request"]["headers"]
        assert "content-type" in result["request"]["headers"]
    
    def test_before_send_filter_groups_timeout_errors(self):
        """Test filter groups timeout errors."""
        event = {
            "exception": {
                "values": [
                    {"type": "TimeoutError", "value": "Request timed out"}
                ]
            }
        }
        hint = {}
        
        result = before_send_filter(event, hint)
        
        assert result["fingerprint"] == ["timeout-error"]
    
    def test_before_send_filter_no_request(self):
        """Test filter handles events without request."""
        event = {}
        hint = {}
        
        result = before_send_filter(event, hint)
        
        assert result is not None


class TestBeforeBreadcrumbFilter:
    """Test before_breadcrumb_filter function."""
    
    def test_before_breadcrumb_filter_skips_select_queries(self):
        """Test filter skips SELECT queries."""
        crumb = {
            "category": "query",
            "message": "SELECT * FROM users",
        }
        hint = {}
        
        result = before_breadcrumb_filter(crumb, hint)
        
        assert result is None
    
    def test_before_breadcrumb_filter_keeps_other_queries(self):
        """Test filter keeps non-SELECT queries."""
        crumb = {
            "category": "query",
            "message": "INSERT INTO users VALUES (1)",
        }
        hint = {}
        
        result = before_breadcrumb_filter(crumb, hint)
        
        assert result is not None
    
    def test_before_breadcrumb_filter_keeps_other_categories(self):
        """Test filter keeps other categories."""
        crumb = {
            "category": "http",
            "message": "GET /api/users",
        }
        hint = {}
        
        result = before_breadcrumb_filter(crumb, hint)
        
        assert result is not None


class TestSentryContextManager:
    """Test SentryContextManager class."""
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_set_user_context(self, mock_sentry):
        """Test setting user context."""
        SentryContextManager.set_user_context(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            custom_field="value",
        )
        
        mock_sentry.set_user.assert_called_once()
        user_data = mock_sentry.set_user.call_args[0][0]
        assert user_data["id"] == "user123"
        assert user_data["username"] == "testuser"
        assert user_data["email"] == "test@example.com"
        assert user_data["custom_field"] == "value"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_set_user_context_partial(self, mock_sentry):
        """Test setting user context with partial data."""
        SentryContextManager.set_user_context(user_id="user123")
        
        mock_sentry.set_user.assert_called_once()
        user_data = mock_sentry.set_user.call_args[0][0]
        assert user_data["id"] == "user123"
        assert "username" not in user_data
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_set_conversation_context(self, mock_sentry):
        """Test setting conversation context."""
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        SentryContextManager.set_conversation_context(
            conversation_id="conv123",
            turn_id="turn456",
            intent_type="set_timer",
        )
        
        mock_scope.set_context.assert_called_once()
        context_name, context_data = mock_scope.set_context.call_args[0]
        assert context_name == "conversation"
        assert context_data["conversation_id"] == "conv123"
        assert context_data["turn_id"] == "turn456"
        assert context_data["intent_type"] == "set_timer"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_set_input_context(self, mock_sentry):
        """Test setting input context."""
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        SentryContextManager.set_input_context(
            input_text="set a timer for 5 minutes",
            input_source="voice",
        )
        
        mock_scope.set_context.assert_called_once()
        context_name, context_data = mock_scope.set_context.call_args[0]
        assert context_name == "input"
        assert context_data["text"] == "set a timer for 5 minutes"
        assert context_data["source"] == "voice"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_set_input_context_truncates_long_input(self, mock_sentry):
        """Test setting input context truncates long input."""
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        long_input = "a" * 300
        SentryContextManager.set_input_context(
            input_text=long_input,
            input_source="text",
        )
        
        context_data = mock_scope.set_context.call_args[0][1]
        assert len(context_data["text"]) == 203  # 200 + "..."
        assert context_data["text"].endswith("...")
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_add_breadcrumb(self, mock_sentry):
        """Test adding breadcrumb."""
        SentryContextManager.add_breadcrumb(
            message="User clicked button",
            category="ui",
            level="info",
            data={"button_id": "submit"},
        )
        
        mock_sentry.add_breadcrumb.assert_called_once()
        call_kwargs = mock_sentry.add_breadcrumb.call_args[1]
        assert call_kwargs["message"] == "User clicked button"
        assert call_kwargs["category"] == "ui"
        assert call_kwargs["level"] == "info"
        assert call_kwargs["data"]["button_id"] == "submit"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_capture_exception(self, mock_sentry):
        """Test capturing exception."""
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__.return_value = mock_scope
        mock_sentry.capture_exception.return_value = "event123"
        
        error = ValueError("Test error")
        event_id = SentryContextManager.capture_exception(
            error,
            level="error",
            tags={"component": "test"},
            extras={"detail": "extra info"},
        )
        
        assert event_id == "event123"
        mock_scope.set_tag.assert_called_once_with("component", "test")
        mock_scope.set_extra.assert_called_once_with("detail", "extra info")
        assert mock_scope.level == "error"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_capture_message(self, mock_sentry):
        """Test capturing message."""
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__.return_value = mock_scope
        mock_sentry.capture_message.return_value = "event456"
        
        event_id = SentryContextManager.capture_message(
            "Test message",
            level="warning",
            tags={"source": "test"},
            extras={"context": "test context"},
        )
        
        assert event_id == "event456"
        mock_scope.set_tag.assert_called_once_with("source", "test")
        mock_scope.set_extra.assert_called_once_with("context", "test context")
        assert mock_scope.level == "warning"
    
    @patch("Agent_Guru.reasoning.config.sentry_config.sentry_sdk")
    def test_clear_context(self, mock_sentry):
        """Test clearing context."""
        mock_scope = MagicMock()
        mock_sentry.configure_scope.return_value.__enter__.return_value = mock_scope
        
        SentryContextManager.clear_context()
        
        mock_sentry.set_user.assert_called_once_with(None)
        mock_scope.clear.assert_called_once()


class TestGlobalSentryContext:
    """Test global sentry_context instance."""
    
    def test_sentry_context_is_instance(self):
        """Test sentry_context is SentryContextManager instance."""
        assert isinstance(sentry_context, SentryContextManager)
