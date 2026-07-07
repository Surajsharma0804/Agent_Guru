"""
Tests for Input Normalizer.

Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
from datetime import datetime, timezone

from Agent_Guru.reasoning.input.normalizer import (
    InputNormalizer,
    InputSource,
    NormalizedInput,
    RawInput,
)


class TestInputNormalizer:
    """Unit tests for InputNormalizer."""
    
    def test_initialization(self):
        """Test normalizer initialization."""
        normalizer = InputNormalizer()
        assert normalizer.max_length == InputNormalizer.MAX_INPUT_LENGTH  # nosec B101
        
        # Custom max length
        normalizer = InputNormalizer(max_length=1000)
        assert normalizer.max_length == 1000  # nosec B101
    
    def test_normalize_text_basic(self):
        """Test basic text normalization."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="  Set a timer for 5 minutes  ",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        assert normalized.text == "Set a timer for 5 minutes"  # nosec B101
        assert normalized.source == InputSource.TEXT  # nosec B101
        assert normalized.user_id == "user_123"  # nosec B101
        assert isinstance(normalized.timestamp, datetime)  # nosec B101
        assert "original_length" in normalized.metadata  # nosec B101
        assert "normalized_length" in normalized.metadata  # nosec B101
    
    def test_normalize_text_whitespace(self):
        """Test whitespace normalization."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="Set   a    timer\n\nfor   5   minutes",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        # Multiple spaces should be collapsed to single space
        assert "  " not in normalized.text  # nosec B101
        assert normalized.text == "Set a timer for 5 minutes"  # nosec B101
    
    def test_normalize_text_empty_input(self):
        """Test empty text input raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="empty after normalization"):
            normalizer.normalize(raw)
    
    def test_normalize_text_whitespace_only(self):
        """Test whitespace-only input raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="   \n\t   ",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="empty after normalization"):
            normalizer.normalize(raw)
    
    def test_normalize_text_max_length(self):
        """Test input exceeding max length raises error."""
        normalizer = InputNormalizer(max_length=100)
        raw = RawInput(
            content="a" * 101,
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="exceeds maximum length"):
            normalizer.normalize(raw)
    
    def test_normalize_text_invalid_type(self):
        """Test non-string text input raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content=12345,  # Not a string
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="must be string"):
            normalizer.normalize(raw)
    
    def test_normalize_text_sanitization(self):
        """Test input sanitization for security."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="<script>alert('xss')</script>Hello",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        # Script tags should be removed
        assert "<script>" not in normalized.text  # nosec B101
        assert "alert" not in normalized.text  # nosec B101
        # Safe content should remain
        assert "Hello" in normalized.text  # nosec B101
    
    def test_normalize_text_metadata_extraction(self):
        """Test metadata extraction from text."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="Set timer for 5 minutes!",
            source=InputSource.TEXT,
            user_id="user_123",
            metadata={"custom_key": "custom_value"}
        )
        
        normalized = normalizer.normalize(raw)
        
        # Check extracted metadata
        assert normalized.metadata["has_uppercase"] is True  # nosec B101
        assert normalized.metadata["has_numbers"] is True  # nosec B101
        assert normalized.metadata["has_special_chars"] is True  # nosec B101
        assert normalized.metadata["original_length"] > 0  # nosec B101
        assert normalized.metadata["normalized_length"] > 0  # nosec B101
        
        # Check preserved metadata
        assert normalized.metadata["custom_key"] == "custom_value"  # nosec B101
    
    def test_normalize_voice_basic(self):
        """Test basic voice input normalization."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="set a timer for five minutes",
            source=InputSource.VOICE,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        assert normalized.text == "set a timer for five minutes"  # nosec B101
        assert normalized.source == InputSource.VOICE  # nosec B101
        assert normalized.metadata["transcribed"] is True  # nosec B101
    
    def test_normalize_voice_empty(self):
        """Test empty voice input raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="",
            source=InputSource.VOICE,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="empty after normalization"):
            normalizer.normalize(raw)
    
    def test_normalize_voice_invalid_type(self):
        """Test non-string voice input raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content=b"audio bytes",  # Not transcribed
            source=InputSource.VOICE,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="must be transcribed string"):
            normalizer.normalize(raw)
    
    def test_normalize_system_event_dict(self):
        """Test system event dict normalization."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content={"type": "timer_expired", "name": "cooking"},
            source=InputSource.SYSTEM_EVENT,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        assert "timer" in normalized.text.lower()  # nosec B101
        assert "cooking" in normalized.text.lower()  # nosec B101
        assert normalized.source == InputSource.SYSTEM_EVENT  # nosec B101
        assert normalized.metadata["system_generated"] is True  # nosec B101
        assert normalized.metadata["event_type"] == "timer_expired"  # nosec B101
    
    def test_normalize_system_event_string(self):
        """Test system event string normalization."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content="System notification: Battery low",
            source=InputSource.SYSTEM_EVENT,
            user_id="user_123"
        )
        
        normalized = normalizer.normalize(raw)
        
        assert normalized.text == "System notification: Battery low"  # nosec B101
        assert normalized.metadata["system_generated"] is True  # nosec B101
    
    def test_normalize_system_event_empty(self):
        """Test empty system event raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content={},
            source=InputSource.SYSTEM_EVENT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="System event dictionary is empty"):
            normalizer.normalize(raw)
    
    def test_normalize_system_event_invalid_type(self):
        """Test invalid system event type raises error."""
        normalizer = InputNormalizer()
        raw = RawInput(
            content=12345,  # Not dict or string
            source=InputSource.SYSTEM_EVENT,
            user_id="user_123"
        )
        
        with pytest.raises(ValueError, match="must be dict or string"):
            normalizer.normalize(raw)
    
    def test_normalize_unknown_source(self):
        """Test unknown input source raises error."""
        normalizer = InputNormalizer()
        
        # Create raw input with invalid source (bypass enum validation)
        raw = RawInput(
            content="test",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        raw.source = "invalid_source"  # Bypass enum
        
        with pytest.raises(ValueError, match="Unknown input source"):
            normalizer.normalize(raw)
    
    def test_event_dict_to_text_timer(self):
        """Test timer event conversion."""
        normalizer = InputNormalizer()
        event = {"type": "timer_expired", "name": "workout"}
        
        text = normalizer._event_dict_to_text(event)
        
        assert "timer" in text.lower()  # nosec B101
        assert "workout" in text.lower()  # nosec B101
    
    def test_event_dict_to_text_alarm(self):
        """Test alarm event conversion."""
        normalizer = InputNormalizer()
        event = {"type": "alarm_triggered", "name": "morning"}
        
        text = normalizer._event_dict_to_text(event)
        
        assert "alarm" in text.lower()  # nosec B101
        assert "morning" in text.lower()  # nosec B101
    
    def test_event_dict_to_text_reminder(self):
        """Test reminder event conversion."""
        normalizer = InputNormalizer()
        event = {"type": "reminder", "message": "Take medicine"}
        
        text = normalizer._event_dict_to_text(event)
        
        assert "reminder" in text.lower()  # nosec B101
        assert "Take medicine" in text  # nosec B101
    
    def test_event_dict_to_text_notification(self):
        """Test notification event conversion."""
        normalizer = InputNormalizer()
        event = {"type": "notification", "app": "Email", "message": "New message"}
        
        text = normalizer._event_dict_to_text(event)
        
        assert "notification" in text.lower()  # nosec B101
        assert "Email" in text  # nosec B101
        assert "New message" in text  # nosec B101
    
    def test_event_dict_to_text_generic(self):
        """Test generic event conversion."""
        normalizer = InputNormalizer()
        event = {"type": "custom_event", "key1": "value1", "key2": "value2"}
        
        text = normalizer._event_dict_to_text(event)
        
        assert "custom_event" in text  # nosec B101
        assert "key1" in text  # nosec B101
        assert "value1" in text  # nosec B101


class TestRawInput:
    """Tests for RawInput model."""
    
    def test_raw_input_creation(self):
        """Test RawInput creation."""
        raw = RawInput(
            content="test",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        assert raw.content == "test"  # nosec B101
        assert raw.source == InputSource.TEXT  # nosec B101
        assert raw.user_id == "user_123"  # nosec B101
        assert isinstance(raw.timestamp, datetime)  # nosec B101
        assert raw.metadata == {}  # nosec B101
    
    def test_raw_input_with_metadata(self):
        """Test RawInput with metadata."""
        metadata = {"key": "value"}
        raw = RawInput(
            content="test",
            source=InputSource.TEXT,
            user_id="user_123",
            metadata=metadata
        )
        
        assert raw.metadata == metadata  # nosec B101
    
    def test_raw_input_empty_user_id(self):
        """Test RawInput with empty user_id raises error."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            RawInput(
                content="test",
                source=InputSource.TEXT,
                user_id=""
            )
    
    def test_raw_input_whitespace_user_id(self):
        """Test RawInput with whitespace user_id raises error."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            RawInput(
                content="test",
                source=InputSource.TEXT,
                user_id="   "
            )


class TestNormalizedInput:
    """Tests for NormalizedInput model."""
    
    def test_normalized_input_creation(self):
        """Test NormalizedInput creation."""
        normalized = NormalizedInput(
            text="test",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.now(tz=timezone.utc)
        )
        
        assert normalized.text == "test"  # nosec B101
        assert normalized.source == InputSource.TEXT  # nosec B101
        assert normalized.user_id == "user_123"  # nosec B101
        assert isinstance(normalized.timestamp, datetime)  # nosec B101
        assert normalized.metadata == {}  # nosec B101
        assert normalized.original_content is None  # nosec B101
    
    def test_normalized_input_with_metadata(self):
        """Test NormalizedInput with metadata."""
        metadata = {"key": "value"}
        normalized = NormalizedInput(
            text="test",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.now(tz=timezone.utc),
            metadata=metadata,
            original_content="original"
        )
        
        assert normalized.metadata == metadata  # nosec B101
        assert normalized.original_content == "original"  # nosec B101
    
    def test_normalized_input_empty_text(self):
        """Test NormalizedInput with empty text raises error."""
        with pytest.raises(ValueError, match="Normalized text cannot be empty"):
            NormalizedInput(
                text="",
                source=InputSource.TEXT,
                user_id="user_123",
                timestamp=datetime.now(tz=timezone.utc)
            )
    
    def test_normalized_input_whitespace_text(self):
        """Test NormalizedInput with whitespace text raises error."""
        with pytest.raises(ValueError, match="Normalized text cannot be empty"):
            NormalizedInput(
                text="   ",
                source=InputSource.TEXT,
                user_id="user_123",
                timestamp=datetime.now(tz=timezone.utc)
            )
    
    def test_normalized_input_empty_user_id(self):
        """Test NormalizedInput with empty user_id raises error."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            NormalizedInput(
                text="test",
                source=InputSource.TEXT,
                user_id="",
                timestamp=datetime.now(tz=timezone.utc)
            )


@pytest.mark.integration
class TestInputNormalizerIntegration:
    """Integration tests for InputNormalizer."""
    
    def test_end_to_end_text_normalization(self):
        """Test complete text normalization flow."""
        normalizer = InputNormalizer()
        
        # Simulate user text input
        raw = RawInput(
            content="  Set a timer for 5 minutes!  ",
            source=InputSource.TEXT,
            user_id="user_123",
            metadata={"device": "mobile"}
        )
        
        normalized = normalizer.normalize(raw)
        
        # Verify all aspects
        assert normalized.text == "Set a timer for 5 minutes!"  # nosec B101
        assert normalized.source == InputSource.TEXT  # nosec B101
        assert normalized.user_id == "user_123"  # nosec B101
        assert normalized.metadata["device"] == "mobile"  # nosec B101
        assert normalized.metadata["has_numbers"] is True  # nosec B101
        assert normalized.original_content is not None  # nosec B101
    
    def test_end_to_end_voice_normalization(self):
        """Test complete voice normalization flow."""
        normalizer = InputNormalizer()
        
        # Simulate voice input (already transcribed)
        raw = RawInput(
            content="play my favorite music",
            source=InputSource.VOICE,
            user_id="user_456",
            metadata={"confidence": 0.95}
        )
        
        normalized = normalizer.normalize(raw)
        
        # Verify all aspects
        assert normalized.text == "play my favorite music"  # nosec B101
        assert normalized.source == InputSource.VOICE  # nosec B101
        assert normalized.user_id == "user_456"  # nosec B101
        assert normalized.metadata["confidence"] == 0.95  # nosec B101
        assert normalized.metadata["transcribed"] is True  # nosec B101
    
    def test_end_to_end_system_event_normalization(self):
        """Test complete system event normalization flow."""
        normalizer = InputNormalizer()
        
        # Simulate system event
        raw = RawInput(
            content={"type": "alarm_triggered", "name": "wake up", "time": "07:00"},
            source=InputSource.SYSTEM_EVENT,
            user_id="user_789"
        )
        
        normalized = normalizer.normalize(raw)
        
        # Verify all aspects
        assert "alarm" in normalized.text.lower()  # nosec B101
        assert "wake up" in normalized.text.lower()  # nosec B101
        assert normalized.source == InputSource.SYSTEM_EVENT  # nosec B101
        assert normalized.user_id == "user_789"  # nosec B101
        assert normalized.metadata["system_generated"] is True  # nosec B101
        assert normalized.metadata["event_type"] == "alarm_triggered"  # nosec B101
