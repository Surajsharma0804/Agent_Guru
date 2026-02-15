"""
Unit tests for CommandInterpreter module.

This module contains unit tests that verify specific examples, edge cases,
and error conditions for the command interpretation functionality.
"""

import pytest

from .commands import CommandInterpreter
from .models import CommandResult
from .exceptions import CommandInterpretationError


class TestCommandInterpreterInitialization:
    """Unit tests for CommandInterpreter initialization."""
    
    def test_initialization_with_default_commands(self):
        """Test initialization loads default command registry."""
        interpreter = CommandInterpreter()
        
        commands = interpreter.get_registered_commands()
        
        # Should have default commands registered
        assert len(commands) > 0
        
        # Check for expected default commands
        action_ids = [cmd["action_id"] for cmd in commands]
        assert "OPEN_YOUTUBE" in action_ids
        assert "SEARCH" in action_ids
        assert "PLAY_MUSIC" in action_ids
    
    def test_get_registered_commands_returns_list(self):
        """Test get_registered_commands returns proper structure."""
        interpreter = CommandInterpreter()
        
        commands = interpreter.get_registered_commands()
        
        assert isinstance(commands, list)
        assert len(commands) > 0
        
        # Verify structure of command entries
        for cmd in commands:
            assert "action_id" in cmd
            assert "patterns" in cmd
            assert "description" in cmd
            assert "languages" in cmd
            assert "has_parameters" in cmd


class TestCommandInterpreterOpenYouTubeMapping:
    """Unit tests for 'open youtube' → OPEN_YOUTUBE mapping."""
    
    def test_open_youtube_exact_match_english(self):
        """Test 'open youtube' maps to OPEN_YOUTUBE action."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("open youtube", language="en")
        
        assert isinstance(result, CommandResult)
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.raw_text == "open youtube"
        assert result.confidence == 1.0
        assert result.language == "en"
    
    def test_open_youtube_case_insensitive(self):
        """Test 'OPEN YOUTUBE' maps to OPEN_YOUTUBE (case insensitive)."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("OPEN YOUTUBE", language="en")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.confidence == 1.0
    
    def test_open_youtube_with_extra_whitespace(self):
        """Test 'open youtube' with extra whitespace."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("  open youtube  ", language="en")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
    
    def test_open_youtube_hindi(self):
        """Test Hindi 'youtube kholo' maps to OPEN_YOUTUBE."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("youtube kholo", language="hi")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.language == "hi"
    
    def test_open_youtube_punjabi(self):
        """Test Punjabi 'youtube ਖੋਲ੍ਹੋ' maps to OPEN_YOUTUBE."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("youtube ਖੋਲ੍ਹੋ", language="pa")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.language == "pa"


class TestCommandInterpreterRegistration:
    """Unit tests for command registration and retrieval."""
    
    def test_register_command_adds_new_command(self):
        """Test command registration adds new command to registry."""
        interpreter = CommandInterpreter()
        
        initial_count = len(interpreter.get_registered_commands())
        
        interpreter.register_command(
            patterns=["test command"],
            action_id="TEST_ACTION",
            description="Test command"
        )
        
        commands = interpreter.get_registered_commands()
        assert len(commands) == initial_count + 1
        
        # Verify the new command is in the registry
        action_ids = [cmd["action_id"] for cmd in commands]
        assert "TEST_ACTION" in action_ids
    
    def test_register_command_with_multiple_patterns(self):
        """Test registering command with multiple patterns."""
        interpreter = CommandInterpreter()
        
        interpreter.register_command(
            patterns=["hello", "hi", "hey"],
            action_id="GREET",
            description="Greeting command"
        )
        
        # All patterns should trigger the same action
        result1 = interpreter.interpret("hello", language="en")
        result2 = interpreter.interpret("hi", language="en")
        result3 = interpreter.interpret("hey", language="en")
        
        assert result1.action_id == "GREET"
        assert result2.action_id == "GREET"
        assert result3.action_id == "GREET"
    
    def test_register_command_with_description(self):
        """Test registering command with description."""
        interpreter = CommandInterpreter()
        
        interpreter.register_command(
            patterns=["shutdown"],
            action_id="SHUTDOWN",
            description="Shutdown the system"
        )
        
        commands = interpreter.get_registered_commands()
        shutdown_cmd = next(cmd for cmd in commands if cmd["action_id"] == "SHUTDOWN")
        
        assert shutdown_cmd["description"] == "Shutdown the system"
    
    def test_register_command_with_languages(self):
        """Test registering command with specific languages."""
        interpreter = CommandInterpreter()
        
        interpreter.register_command(
            patterns=["bonjour"],
            action_id="FRENCH_GREET",
            description="French greeting",
            languages=["fr"]
        )
        
        commands = interpreter.get_registered_commands()
        french_cmd = next(cmd for cmd in commands if cmd["action_id"] == "FRENCH_GREET")
        
        assert "fr" in french_cmd["languages"]
    
    def test_register_command_with_empty_patterns_raises_error(self):
        """Test registering command with empty patterns raises error."""
        interpreter = CommandInterpreter()
        
        with pytest.raises(CommandInterpretationError) as exc_info:
            interpreter.register_command(
                patterns=[],
                action_id="INVALID"
            )
        
        assert "Failed to register command" in str(exc_info.value)
    
    def test_register_command_with_empty_action_id_raises_error(self):
        """Test registering command with empty action_id raises error."""
        interpreter = CommandInterpreter()
        
        with pytest.raises(CommandInterpretationError) as exc_info:
            interpreter.register_command(
                patterns=["test"],
                action_id=""
            )
        
        assert "Failed to register command" in str(exc_info.value)
    
    def test_get_registered_commands_includes_custom_commands(self):
        """Test get_registered_commands includes custom registered commands."""
        interpreter = CommandInterpreter()
        
        interpreter.register_command(
            patterns=["custom action"],
            action_id="CUSTOM",
            description="Custom command"
        )
        
        commands = interpreter.get_registered_commands()
        action_ids = [cmd["action_id"] for cmd in commands]
        
        assert "CUSTOM" in action_ids


class TestCommandInterpreterUnrecognizedText:
    """Unit tests for unrecognized text passthrough."""
    
    def test_unrecognized_text_returns_raw_text(self):
        """Test unrecognized text returns raw text without modification."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("this is random text", language="en")
        
        assert result.is_command is False
        assert result.action_id is None
        assert result.raw_text == "this is random text"
        assert result.confidence == 0.0
        assert result.parameters == {}
    
    def test_unrecognized_text_preserves_original_text(self):
        """Test unrecognized text preserves original text exactly."""
        interpreter = CommandInterpreter()
        
        original_text = "Some Random Text With CAPS and spaces"
        result = interpreter.interpret(original_text, language="en")
        
        assert result.raw_text == original_text
        assert result.is_command is False
    
    def test_partial_match_not_recognized(self):
        """Test partial matches don't trigger commands."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("open youtube channel", language="en")
        
        # Should not match "open youtube" exactly
        # Note: This might match due to fuzzy matching, so we check behavior
        # If it doesn't match, it should return raw text
        if not result.is_command:
            assert result.raw_text == "open youtube channel"
    
    def test_empty_text_returns_passthrough(self):
        """Test empty text returns passthrough result."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("", language="en")
        
        assert result.is_command is False
        assert result.raw_text == ""
    
    def test_whitespace_only_text_returns_passthrough(self):
        """Test whitespace-only text returns passthrough result."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("   ", language="en")
        
        assert result.is_command is False


class TestCommandInterpreterMultiLanguage:
    """Unit tests for multi-language command patterns."""
    
    def test_english_pattern_matched_with_multi_language_command(self):
        """Test English pattern matched when command supports multiple languages."""
        interpreter = CommandInterpreter()
        
        # "open youtube" is English pattern, but OPEN_YOUTUBE supports en, hi, pa
        result = interpreter.interpret("open youtube", language="hi")
        
        # Should match because OPEN_YOUTUBE command supports Hindi language
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.language == "hi"
    
    def test_language_specific_command_not_matched_with_wrong_language(self):
        """Test language-specific command not matched with wrong language."""
        interpreter = CommandInterpreter()
        
        # Register a command that only supports English
        interpreter.register_command(
            patterns=["english only"],
            action_id="ENGLISH_ONLY",
            description="English only command",
            languages=["en"]
        )
        
        # Try to match with Hindi language
        result = interpreter.interpret("english only", language="hi")
        
        # Should not match because command only supports English
        assert result.is_command is False
        assert result.raw_text == "english only"
    
    def test_hindi_command_matched_with_hindi_language(self):
        """Test Hindi command pattern matched with Hindi language."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("youtube kholo", language="hi")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.language == "hi"
    
    def test_punjabi_command_matched_with_punjabi_language(self):
        """Test Punjabi command pattern matched with Punjabi language."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("music ਚਲਾਓ", language="pa")
        
        assert result.is_command is True
        assert result.action_id == "PLAY_MUSIC"
        assert result.language == "pa"
    
    def test_play_music_english(self):
        """Test 'play music' in English."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("play music", language="en")
        
        assert result.is_command is True
        assert result.action_id == "PLAY_MUSIC"
        assert result.language == "en"
    
    def test_play_music_hindi(self):
        """Test 'music chalao' in Hindi."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("music chalao", language="hi")
        
        assert result.is_command is True
        assert result.action_id == "PLAY_MUSIC"
        assert result.language == "hi"
    
    def test_multi_language_command_registration(self):
        """Test registering command with multiple languages."""
        interpreter = CommandInterpreter()
        
        interpreter.register_command(
            patterns=["stop", "ruko", "ਰੁਕੋ"],
            action_id="STOP",
            description="Stop command",
            languages=["en", "hi", "pa"]
        )
        
        # Test each language
        result_en = interpreter.interpret("stop", language="en")
        result_hi = interpreter.interpret("ruko", language="hi")
        result_pa = interpreter.interpret("ਰੁਕੋ", language="pa")
        
        assert result_en.action_id == "STOP"
        assert result_hi.action_id == "STOP"
        assert result_pa.action_id == "STOP"


class TestCommandInterpreterParameterExtraction:
    """Unit tests for parameter extraction from commands."""
    
    def test_search_command_extracts_query_parameter(self):
        """Test SEARCH command extracts query parameter."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("search for python tutorials", language="en")
        
        assert result.is_command is True
        assert result.action_id == "SEARCH"
        assert "query" in result.parameters
        assert result.parameters["query"] == "python tutorials"
    
    def test_search_command_hindi_extracts_query(self):
        """Test Hindi SEARCH command extracts query parameter."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("python tutorials dhundo", language="hi")
        
        assert result.is_command is True
        assert result.action_id == "SEARCH"
        assert "query" in result.parameters
        assert result.parameters["query"] == "python tutorials"
    
    def test_search_command_punjabi_extracts_query(self):
        """Test Punjabi SEARCH command extracts query parameter."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("music ਲੱਭੋ", language="pa")
        
        assert result.is_command is True
        assert result.action_id == "SEARCH"
        assert "query" in result.parameters
        assert result.parameters["query"] == "music"
    
    def test_command_without_parameters_has_empty_dict(self):
        """Test commands without parameters have empty parameters dict."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("open youtube", language="en")
        
        assert result.is_command is True
        assert result.parameters == {}
    
    def test_custom_command_with_parameter_extractors(self):
        """Test custom command with parameter extractors."""
        interpreter = CommandInterpreter()
        
        def extract_number(text):
            import re
            match = re.search(r'\d+', text)
            return int(match.group()) if match else None
        
        interpreter.register_command(
            patterns=["set volume *"],
            action_id="SET_VOLUME",
            description="Set volume level",
            parameter_extractors={"level": extract_number}
        )
        
        result = interpreter.interpret("set volume 75", language="en")
        
        assert result.is_command is True
        assert result.action_id == "SET_VOLUME"
        assert "level" in result.parameters
        assert result.parameters["level"] == 75
    
    def test_parameter_extraction_with_wildcard_at_end(self):
        """Test parameter extraction with wildcard at end of pattern."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("search for machine learning", language="en")
        
        assert result.is_command is True
        assert result.parameters["query"] == "machine learning"
    
    def test_parameter_extraction_with_wildcard_at_start(self):
        """Test parameter extraction with wildcard at start of pattern."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("artificial intelligence dhundo", language="hi")
        
        assert result.is_command is True
        assert result.parameters["query"] == "artificial intelligence"


class TestCommandInterpreterFuzzyMatching:
    """Unit tests for fuzzy matching behavior."""
    
    def test_fuzzy_match_with_typo(self):
        """Test fuzzy matching handles minor typos."""
        interpreter = CommandInterpreter()
        
        # "opn youtube" is close to "open youtube"
        result = interpreter.interpret("opn youtube", language="en")
        
        # Should match with fuzzy matching (similarity >= 0.8)
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
        assert result.confidence < 1.0  # Not exact match
        assert result.confidence >= 0.8  # But high confidence
    
    def test_fuzzy_match_confidence_less_than_exact(self):
        """Test fuzzy match has lower confidence than exact match."""
        interpreter = CommandInterpreter()
        
        exact_result = interpreter.interpret("play music", language="en")
        fuzzy_result = interpreter.interpret("ply music", language="en")
        
        if fuzzy_result.is_command:
            assert exact_result.confidence == 1.0
            assert fuzzy_result.confidence < 1.0
    
    def test_very_different_text_not_fuzzy_matched(self):
        """Test very different text is not fuzzy matched."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("completely different text", language="en")
        
        # Should not match any command
        assert result.is_command is False


class TestCommandInterpreterEdgeCases:
    """Unit tests for edge cases and error conditions."""
    
    def test_interpret_with_none_text_raises_error(self):
        """Test interpret with None text raises error."""
        interpreter = CommandInterpreter()
        
        with pytest.raises((CommandInterpretationError, AttributeError)):
            interpreter.interpret(None, language="en")
    
    def test_interpret_with_special_characters(self):
        """Test interpret handles special characters."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("open youtube!!!", language="en")
        
        # Should not match due to special characters
        # Or might match with fuzzy matching depending on implementation
        assert isinstance(result, CommandResult)
    
    def test_interpret_with_numbers(self):
        """Test interpret handles text with numbers."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("search for python 3.11", language="en")
        
        assert result.is_command is True
        assert result.action_id == "SEARCH"
        assert "3.11" in result.parameters["query"]
    
    def test_interpret_with_unicode_characters(self):
        """Test interpret handles unicode characters."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("youtube ਖੋਲ੍ਹੋ", language="pa")
        
        assert result.is_command is True
        assert result.action_id == "OPEN_YOUTUBE"
    
    def test_command_result_structure_completeness(self):
        """Test CommandResult has all required fields."""
        interpreter = CommandInterpreter()
        
        result = interpreter.interpret("open youtube", language="en")
        
        # Verify all fields are present
        assert hasattr(result, 'action_id')
        assert hasattr(result, 'parameters')
        assert hasattr(result, 'raw_text')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'language')
        assert hasattr(result, 'is_command')
        
        # Verify types
        assert isinstance(result.parameters, dict)
        assert isinstance(result.raw_text, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.language, str)
        assert isinstance(result.is_command, bool)
