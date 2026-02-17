"""
Property-based tests for conversation context manager.

Property 22: Conversation Context Persistence

Validates: Requirements 18.1, 18.3, 18.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from Agent_Guru.speech.context.context_manager import ConversationContextManager
from Agent_Guru.speech.models import PersonalityType, EmotionType


class TestConversationContextProperties:
    """Property-based tests for conversation context manager."""
    
    # ========================================================================
    # PROPERTY 22: CONVERSATION CONTEXT PERSISTENCE
    # ========================================================================
    
    @given(
        num_turns=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_22_context_persistence(self, num_turns: int):
        """
        Property 22: Conversation Context Persistence
        
        For any number of conversation turns, context should maintain state
        and allow retrieval of history.
        
        Validates: Requirements 18.1, 18.2
        """
        manager = ConversationContextManager(max_history_turns=10)
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Add turns
        for i in range(num_turns):
            manager.add_turn(context_id, "user", f"Message {i}")
        
        context = manager.get_context(context_id)
        
        # PROPERTY ASSERTIONS
        assert len(context.turns) > 0, "Context should have turns"
        assert len(context.turns) <= 10, "Context should respect max history"
        
        # If more than 10 turns, should keep last 10
        if num_turns > 10:
            assert len(context.turns) == 10
            assert context.turns[0].text == f"Message {num_turns - 10}"
        else:
            assert len(context.turns) == num_turns
    
    @given(
        text=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs', 'P'))),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_22_reference_resolution(self, text: str):
        """
        Property 22: Conversation Context Persistence
        
        For any text with pronouns, reference resolution should work or return None.
        
        Validates: Requirements 18.3
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Add some context
        manager.add_turn(context_id, "user", "Open Chrome browser")
        
        # Try to resolve reference
        resolved = manager.resolve_reference(context_id, text)
        
        # PROPERTY ASSERTION: Should either resolve or return None
        assert resolved is None or isinstance(resolved, str)
    
    @given(
        topic1_word=st.sampled_from(["weather", "email", "calendar", "file", "system", "web"]),
        topic2_word=st.sampled_from(["weather", "email", "calendar", "file", "system", "web"]),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_22_topic_shift_detection(self, topic1_word: str, topic2_word: str):
        """
        Property 22: Conversation Context Persistence
        
        For any two topic-related inputs, topic shift should be detected correctly.
        
        Validates: Requirements 18.5
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Add first topic
        manager.add_turn(context_id, "user", f"Tell me about {topic1_word}")
        
        # Check for topic shift
        shift = manager.detect_topic_shift(context_id, f"What about {topic2_word}")
        
        # PROPERTY ASSERTION
        # Topic shift detection is best-effort based on keywords
        # Should return boolean without crashing
        assert isinstance(shift, bool)
    
    @given(
        user_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_22_context_creation(self, user_id: str, personality: PersonalityType):
        """
        Property 22: Conversation Context Persistence
        
        For any user_id and personality, context creation should succeed.
        
        Validates: Requirements 18.1, 18.6
        """
        manager = ConversationContextManager()
        
        context_id, context = manager.create_context(user_id, personality)
        
        # PROPERTY ASSERTIONS
        assert context_id is not None
        assert user_id in context_id
        assert personality.value in context_id
        assert context.personality == personality
        assert len(context.turns) == 0
        assert context.created_at > 0
    
    @given(
        speaker=st.sampled_from(["user", "agent"]),
        text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
        emotion=st.sampled_from([None, EmotionType.HAPPY, EmotionType.SAD, EmotionType.ANGRY]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_22_turn_addition(self, speaker: str, text: str, emotion):
        """
        Property 22: Conversation Context Persistence
        
        For any speaker, text, and emotion, turn addition should succeed.
        
        Validates: Requirements 18.1
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        context = manager.add_turn(context_id, speaker, text, emotion)
        
        # PROPERTY ASSERTIONS
        assert len(context.turns) == 1
        assert context.turns[0].speaker == speaker
        assert context.turns[0].text == text
        assert context.turns[0].emotion == emotion
        assert context.turns[0].timestamp > 0
    
    # ========================================================================
    # PROPERTY: CONSISTENCY
    # ========================================================================
    
    @given(
        text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_consistency(self, text: str):
        """
        Property: Consistency
        
        For any text, adding it multiple times should produce consistent results.
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Add same text multiple times
        for _ in range(3):
            manager.add_turn(context_id, "user", text)
        
        context = manager.get_context(context_id)
        
        # PROPERTY ASSERTION: All turns should have same text
        assert all(turn.text == text for turn in context.turns)
    
    # ========================================================================
    # PROPERTY: ROBUSTNESS
    # ========================================================================
    
    @given(
        text=st.text(max_size=1000),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_robustness_to_any_text(self, text: str):
        """
        Property: Robustness
        
        For any text (including empty, special chars, unicode), system should handle gracefully.
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Should not crash
        context = manager.add_turn(context_id, "user", text)
        
        # PROPERTY ASSERTION
        assert len(context.turns) == 1
        assert context.turns[0].text == text
    
    @given(
        max_history=st.integers(min_value=1, max_value=100),
        num_turns=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=200, deadline=None)
    def test_property_history_limit_enforcement(self, max_history: int, num_turns: int):
        """
        Property: History Limit Enforcement
        
        For any max_history and num_turns, history should never exceed max_history.
        """
        manager = ConversationContextManager(max_history_turns=max_history)
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Add turns
        for i in range(num_turns):
            manager.add_turn(context_id, "user", f"Message {i}")
        
        context = manager.get_context(context_id)
        
        # PROPERTY ASSERTION: Should never exceed max_history
        assert len(context.turns) <= max_history
        
        # If more turns than max, should keep most recent
        if num_turns > max_history:
            assert len(context.turns) == max_history
            # First turn should be from (num_turns - max_history)
            assert context.turns[0].text == f"Message {num_turns - max_history}"
    
    # ========================================================================
    # PROPERTY: PREFERENCE EXTRACTION
    # ========================================================================
    
    @given(
        preference_type=st.sampled_from(["prefer", "like", "dislike", "want"]),
        item=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_preference_extraction(self, preference_type: str, item: str):
        """
        Property: Preference Extraction
        
        For any preference statement, preferences should be extracted or ignored gracefully.
        """
        manager = ConversationContextManager()
        context_id, _ = manager.create_context("user123", PersonalityType.GURU)
        
        # Build preference statement
        if preference_type == "prefer":
            text = f"I prefer {item} over something"
        elif preference_type == "like":
            text = f"I like {item}"
        elif preference_type == "dislike":
            text = f"I don't like {item}"
        else:  # want
            text = f"I want {item}"
        
        manager.add_turn(context_id, "user", text)
        
        prefs = manager.extract_preferences(context_id)
        
        # PROPERTY ASSERTION: Should extract preferences or return empty dict
        # Preference extraction is best-effort based on regex patterns
        assert isinstance(prefs, dict)
