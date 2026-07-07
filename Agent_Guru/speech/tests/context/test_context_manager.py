"""
ZERO COMPROMISE unit tests for conversation context manager.

Tests cover:
- Context creation and management
- Turn tracking with history limits
- Reference resolution (pronouns)
- Topic shift detection
- User preference extraction
- Conversation summarization
- Error handling
- Edge cases and security
"""

import pytest
import time

from Agent_Guru.speech.context.context_manager import (
    ConversationContextManager,
    ContextNotFoundError
)
from Agent_Guru.speech.models import PersonalityType, EmotionType


class TestConversationContextManager:
    """Comprehensive tests for conversation context manager."""
    
    @pytest.fixture
    def manager(self) -> ConversationContextManager:
        """Create context manager instance."""
        return ConversationContextManager(max_history_turns=10)
    
    # ========================================================================
    # CONTEXT CREATION AND MANAGEMENT
    # ========================================================================
    
    def test_create_context(self, manager: ConversationContextManager):
        """Test creating new conversation context."""
        context_id, context = manager.create_context("user123", PersonalityType.GURU)
        
        assert context_id is not None  # nosec B101
        assert "user123" in context_id  # nosec B101
        assert "guru" in context_id  # nosec B101
        assert context.personality == PersonalityType.GURU  # nosec B101
        assert len(context.turns) == 0  # nosec B101
        assert context.current_topic is None  # nosec B101
        assert len(context.user_preferences) == 0  # nosec B101
        assert context.created_at > 0  # nosec B101
        assert context.updated_at > 0  # nosec B101
    
    def test_create_multiple_contexts(self, manager: ConversationContextManager):
        """Test creating multiple independent contexts."""
        ctx1_id, ctx1 = manager.create_context("user1", PersonalityType.GURU)
        ctx2_id, ctx2 = manager.create_context("user2", PersonalityType.MAYA)
        
        assert ctx1_id != ctx2_id  # nosec B101
        assert ctx1.personality == PersonalityType.GURU  # nosec B101
        assert ctx2.personality == PersonalityType.MAYA  # nosec B101
    
    def test_get_context(self, manager: ConversationContextManager):
        """Test retrieving existing context."""
        context_id, original = manager.create_context("user123", PersonalityType.GURU)
        
        retrieved = manager.get_context(context_id)
        
        assert retrieved.personality == original.personality  # nosec B101
        assert retrieved.created_at == original.created_at  # nosec B101
    
    def test_get_nonexistent_context(self, manager: ConversationContextManager):
        """Test retrieving non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.get_context("nonexistent_id")
    
    def test_clear_context(self, manager: ConversationContextManager):
        """Test clearing conversation context."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.clear_context(context_id)
        
        with pytest.raises(ContextNotFoundError):
            manager.get_context(context_id)
    
    def test_clear_nonexistent_context(self, manager: ConversationContextManager):
        """Test clearing non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.clear_context("nonexistent_id")
    
    # ========================================================================
    # TURN TRACKING
    # ========================================================================
    
    def test_add_turn(self, manager: ConversationContextManager):
        """Test adding conversation turn."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        context = manager.add_turn(context_id, "user", "Hello Guru")
        
        assert len(context.turns) == 1  # nosec B101
        assert context.turns[0].speaker == "user"  # nosec B101
        assert context.turns[0].text == "Hello Guru"  # nosec B101
        assert context.turns[0].timestamp > 0  # nosec B101
    
    def test_add_multiple_turns(self, manager: ConversationContextManager):
        """Test adding multiple conversation turns."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "Hello")
        manager.add_turn(context_id, "agent", "Hi there!")
        manager.add_turn(context_id, "user", "How are you?")
        
        context = manager.get_context(context_id)
        
        assert len(context.turns) == 3  # nosec B101
        assert context.turns[0].speaker == "user"  # nosec B101
        assert context.turns[1].speaker == "agent"  # nosec B101
        assert context.turns[2].speaker == "user"  # nosec B101
    
    def test_add_turn_with_emotion(self, manager: ConversationContextManager):
        """Test adding turn with emotion."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        context = manager.add_turn(
            context_id,
            "user",
            "I'm so happy!",
            emotion=EmotionType.HAPPY
        )
        
        assert context.turns[0].emotion == EmotionType.HAPPY  # nosec B101
    
    def test_history_limit(self, manager: ConversationContextManager):
        """Test that history is limited to max_history_turns."""
        manager_small = ConversationContextManager(max_history_turns=5)
        context_id, _ = manager_small.create_context("user123", PersonalityType.GURU)
        
        # Add 10 turns
        for i in range(10):
            manager_small.add_turn(context_id, "user", f"Message {i}")
        
        context = manager_small.get_context(context_id)
        
        # Should only keep last 5
        assert len(context.turns) == 5  # nosec B101
        assert context.turns[0].text == "Message 5"  # nosec B101
        assert context.turns[-1].text == "Message 9"  # nosec B101
    
    def test_add_turn_to_nonexistent_context(self, manager: ConversationContextManager):
        """Test adding turn to non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.add_turn("nonexistent_id", "user", "Hello")
    
    # ========================================================================
    # REFERENCE RESOLUTION
    # ========================================================================
    
    def test_resolve_reference_it(self, manager: ConversationContextManager):
        """Test resolving 'it' reference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "Open Chrome browser")
        manager.add_turn(context_id, "agent", "Opening Chrome")
        
        resolved = manager.resolve_reference(context_id, "close it")
        
        # Should resolve to some entity from previous context
        assert resolved is not None  # nosec B101
        assert isinstance(resolved, str)  # nosec B101
        assert len(resolved) > 0  # nosec B101
    
    def test_resolve_reference_that(self, manager: ConversationContextManager):
        """Test resolving 'that' reference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "Create a new file called report.txt")
        
        resolved = manager.resolve_reference(context_id, "delete that")
        
        assert resolved is not None  # nosec B101
    
    def test_resolve_reference_no_pronoun(self, manager: ConversationContextManager):
        """Test that non-pronoun text returns None."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "Open Chrome")
        
        resolved = manager.resolve_reference(context_id, "close Chrome")
        
        # No pronoun, should return None
        assert resolved is None  # nosec B101
    
    def test_resolve_reference_empty_history(self, manager: ConversationContextManager):
        """Test resolving reference with no history."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        resolved = manager.resolve_reference(context_id, "close it")
        
        # No history to resolve from
        assert resolved is None  # nosec B101
    
    def test_resolve_reference_nonexistent_context(self, manager: ConversationContextManager):
        """Test resolving reference in non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.resolve_reference("nonexistent_id", "close it")
    
    # ========================================================================
    # TOPIC SHIFT DETECTION
    # ========================================================================
    
    def test_detect_topic_shift_same_topic(self, manager: ConversationContextManager):
        """Test no topic shift when staying on same topic."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "What's the weather today?")
        
        shift = manager.detect_topic_shift(context_id, "Will it rain tomorrow?")
        
        # Both about weather
        assert shift is False  # nosec B101
    
    def test_detect_topic_shift_different_topic(self, manager: ConversationContextManager):
        """Test topic shift detection when topic changes."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "What's the weather today?")
        
        shift = manager.detect_topic_shift(context_id, "Check my email")
        
        # Weather -> email
        assert shift is True  # nosec B101
    
    def test_detect_topic_shift_no_initial_topic(self, manager: ConversationContextManager):
        """Test topic shift with no initial topic."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        shift = manager.detect_topic_shift(context_id, "What's the weather?")
        
        # No initial topic
        assert shift is False  # nosec B101
    
    def test_detect_topic_shift_nonexistent_context(self, manager: ConversationContextManager):
        """Test topic shift detection in non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.detect_topic_shift("nonexistent_id", "Hello")
    
    # ========================================================================
    # PREFERENCE EXTRACTION
    # ========================================================================
    
    def test_extract_preference_prefer_over(self, manager: ConversationContextManager):
        """Test extracting 'prefer X over Y' preference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I prefer email over calls")
        
        prefs = manager.extract_preferences(context_id)
        
        assert "prefer_email_over_calls" in prefs  # nosec B101
        assert prefs["prefer_email_over_calls"] is True  # nosec B101
    
    def test_extract_preference_like(self, manager: ConversationContextManager):
        """Test extracting 'I like X' preference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I like morning meetings")
        
        prefs = manager.extract_preferences(context_id)
        
        assert "likes_morning_meetings" in prefs or "likes_morning" in prefs  # nosec B101
    
    def test_extract_preference_dislike(self, manager: ConversationContextManager):
        """Test extracting 'I don't like X' preference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I don't like spam")
        
        prefs = manager.extract_preferences(context_id)
        
        assert "dislikes_spam" in prefs  # nosec B101
    
    def test_extract_preference_want(self, manager: ConversationContextManager):
        """Test extracting 'I want X' preference."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I want daily summaries")
        
        prefs = manager.extract_preferences(context_id)
        
        assert "wants_daily_summaries" in prefs or "wants_daily" in prefs  # nosec B101
    
    def test_extract_multiple_preferences(self, manager: ConversationContextManager):
        """Test extracting multiple preferences over time."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I prefer email over calls")
        manager.add_turn(context_id, "user", "I like morning meetings")
        manager.add_turn(context_id, "user", "I don't like spam")
        
        prefs = manager.extract_preferences(context_id)
        
        # Should have all preferences
        assert len(prefs) >= 3  # nosec B101
    
    def test_extract_preferences_nonexistent_context(self, manager: ConversationContextManager):
        """Test extracting preferences from non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.extract_preferences("nonexistent_id")
    
    # ========================================================================
    # CONVERSATION SUMMARY
    # ========================================================================
    
    def test_get_summary_empty_context(self, manager: ConversationContextManager):
        """Test getting summary of empty context."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        summary = manager.get_context_summary(context_id)
        
        assert "No conversation history" in summary  # nosec B101
    
    def test_get_summary_with_turns(self, manager: ConversationContextManager):
        """Test getting summary with conversation turns."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "Hello")
        manager.add_turn(context_id, "agent", "Hi there!")
        manager.add_turn(context_id, "user", "How are you?")
        
        summary = manager.get_context_summary(context_id)
        
        assert "Guru" in summary  # nosec B101
        assert "Total turns: 3" in summary  # nosec B101
        assert "Recent conversation" in summary  # nosec B101
    
    def test_get_summary_with_topic(self, manager: ConversationContextManager):
        """Test summary includes current topic."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "What's the weather today?")
        
        summary = manager.get_context_summary(context_id)
        
        assert "Current topic" in summary  # nosec B101
        assert "weather" in summary.lower()  # nosec B101
    
    def test_get_summary_with_preferences(self, manager: ConversationContextManager):
        """Test summary includes user preferences."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "I prefer email over calls")
        
        summary = manager.get_context_summary(context_id)
        
        assert "User preferences" in summary  # nosec B101
    
    def test_get_summary_nonexistent_context(self, manager: ConversationContextManager):
        """Test getting summary of non-existent context raises error."""
        with pytest.raises(ContextNotFoundError):
            manager.get_context_summary("nonexistent_id")
    
    # ========================================================================
    # EDGE CASES
    # ========================================================================
    
    def test_empty_text_turn(self, manager: ConversationContextManager):
        """Test adding turn with empty text."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        context = manager.add_turn(context_id, "user", "")
        
        assert len(context.turns) == 1  # nosec B101
        assert context.turns[0].text == ""  # nosec B101
    
    def test_very_long_text_turn(self, manager: ConversationContextManager):
        """Test adding turn with very long text."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        long_text = "A" * 10000
        context = manager.add_turn(context_id, "user", long_text)
        
        assert len(context.turns) == 1  # nosec B101
        assert len(context.turns[0].text) == 10000  # nosec B101
    
    def test_special_characters_in_text(self, manager: ConversationContextManager):
        """Test handling special characters in text."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        special_text = "Hello! @#$%^&*() <script>alert('xss')</script>"
        context = manager.add_turn(context_id, "user", special_text)
        
        assert context.turns[0].text == special_text  # nosec B101
    
    def test_unicode_in_text(self, manager: ConversationContextManager):
        """Test handling unicode characters."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        unicode_text = "Hello 你好 مرحبا שלום"
        context = manager.add_turn(context_id, "user", unicode_text)
        
        assert context.turns[0].text == unicode_text  # nosec B101
    
    def test_concurrent_context_access(self, manager: ConversationContextManager):
        """Test accessing multiple contexts concurrently."""
        ctx1_id, _ = manager.create_context("user1", PersonalityType.GURU)
        ctx2_id, _ = manager.create_context("user2", PersonalityType.MAYA)
        
        manager.add_turn(ctx1_id, "user", "Hello from user1")
        manager.add_turn(ctx2_id, "user", "Hello from user2")
        
        ctx1 = manager.get_context(ctx1_id)
        ctx2 = manager.get_context(ctx2_id)
        
        assert ctx1.turns[0].text == "Hello from user1"  # nosec B101
        assert ctx2.turns[0].text == "Hello from user2"  # nosec B101
    
    def test_timestamp_ordering(self, manager: ConversationContextManager):
        """Test that timestamps are in order."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        manager.add_turn(context_id, "user", "First")
        time.sleep(0.01)  # Small delay
        manager.add_turn(context_id, "user", "Second")
        time.sleep(0.01)
        manager.add_turn(context_id, "user", "Third")
        
        context = manager.get_context(context_id)
        
        assert context.turns[0].timestamp < context.turns[1].timestamp  # nosec B101
        assert context.turns[1].timestamp < context.turns[2].timestamp  # nosec B101
    
    # ========================================================================
    # SECURITY TESTS
    # ========================================================================
    
    def test_sql_injection_in_text(self, manager: ConversationContextManager):
        """Test handling SQL injection attempts in text."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        sql_injection = "'; DROP TABLE users; --"
        context = manager.add_turn(context_id, "user", sql_injection)
        
        # Should store as-is without executing
        assert context.turns[0].text == sql_injection  # nosec B101
    
    def test_xss_in_text(self, manager: ConversationContextManager):
        """Test handling XSS attempts in text."""
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        xss = "<script>alert('XSS')</script>"
        context = manager.add_turn(context_id, "user", xss)
        
        # Should store as-is
        assert context.turns[0].text == xss  # nosec B101
    
    def test_path_traversal_in_context_id(self, manager: ConversationContextManager):
        """Test handling path traversal in context ID."""
        # Create normal context
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Try to access with path traversal
        malicious_id = "../../../etc/passwd"
        
        with pytest.raises(ContextNotFoundError):
            manager.get_context(malicious_id)
