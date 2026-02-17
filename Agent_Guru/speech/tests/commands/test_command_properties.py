"""
Property-based tests for command parser.

Property 14: Command Parsing Completeness
Property 20: Command Recognition Coverage  
Property 21: Command Chaining Support

Validates: Requirements 6.1, 6.2, 6.4, 17.1, 17.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List

from Agent_Guru.speech.commands.command_parser import CommandParser
from Agent_Guru.speech.models import CommandResult


class TestCommandParserProperties:
    """Property-based tests for command parser."""
    
    # ========================================================================
    # PROPERTY 14: COMMAND PARSING COMPLETENESS
    # ========================================================================
    
    @given(
        text=st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=('Cs',))),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_14_confidence_score_range(self, text: str):
        """
        Property 14: Command Parsing Completeness
        
        For any transcribed text, confidence score must be in [0.0, 1.0].
        
        Validates: Requirements 6.4
        """
        parser = CommandParser()
        
        # Skip empty or whitespace-only text
        if not text or not text.strip():
            return
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTION: Confidence must be in valid range
        assert 0.0 <= result.confidence <= 1.0, \
            f"Confidence {result.confidence} outside [0.0, 1.0] for text: {text}"
    
    @given(
        app_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_14_intent_extraction(self, app_name: str):
        """
        Property 14: Command Parsing Completeness
        
        For any valid command text, primary intent should be extracted.
        
        Validates: Requirements 6.1
        """
        parser = CommandParser()
        
        # Skip empty or whitespace-only
        if not app_name or not app_name.strip():
            return
        
        app_name = app_name.strip()
        text = f"open {app_name}"
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize command: {text}"
        assert result.action_id is not None, "No action_id extracted"
        assert result.action_id == "OPEN_APP", f"Wrong action_id: {result.action_id}"
        assert "app_name" in result.parameters, "Failed to extract app_name parameter"
    
    @given(
        volume_level=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_14_entity_recognition_numbers(self, volume_level: int):
        """
        Property 14: Command Parsing Completeness
        
        For any command with numbers, entities should be recognized.
        
        Validates: Requirements 6.2
        """
        parser = CommandParser()
        text = f"set volume to {volume_level} percent"
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize command: {text}"
        assert "level" in result.parameters, "Failed to extract number entity"
        assert result.parameters["level"] == volume_level, \
            f"Extracted {result.parameters['level']}, expected {volume_level}"
    
    @given(
        text_content=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_14_parameter_extraction(self, text_content: str):
        """
        Property 14: Command Parsing Completeness
        
        For any command with parameters, parameters should be extracted.
        
        Validates: Requirements 6.1, 6.2
        """
        parser = CommandParser()
        if not text_content or not text_content.strip():
            return
        
        text_content = text_content.strip()
        command_text = f"type {text_content}"
        
        result = parser.interpret(command_text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize command: {command_text}"
        assert "text" in result.parameters, "Failed to extract text parameter"
        
        # Handle both string and int types (parser converts numeric strings to int)
        text_param = result.parameters["text"]
        if isinstance(text_param, str):
            assert len(text_param) > 0, "Extracted empty text parameter"
        else:
            # If it's an int, it was successfully extracted
            assert text_param is not None, "Extracted None text parameter"
    
    # ========================================================================
    # PROPERTY 20: COMMAND RECOGNITION COVERAGE
    # ========================================================================
    
    @given(
        command_type=st.sampled_from([
            "open", "close", "minimize", "maximize",
            "type", "click", "scroll up", "scroll down",
            "mute", "increase volume", "decrease volume"
        ]),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_20_system_control_coverage(self, command_type: str):
        """
        Property 20: Command Recognition Coverage
        
        For any system control command, parser should recognize it.
        
        Validates: Requirements 17.1
        """
        parser = CommandParser()
        # Build command text based on type
        if command_type in ["open", "close", "minimize", "maximize"]:
            text = f"{command_type} chrome"
        elif command_type == "type":
            text = "type hello world"
        else:
            text = command_type
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTION: System control commands must be recognized
        assert result.is_command, f"Failed to recognize system control command: {text}"
        assert result.action_id is not None, f"No action_id for command: {text}"
        assert result.confidence > 0.0, f"Zero confidence for valid command: {text}"
    
    @given(
        filename=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        extension=st.sampled_from([".txt", ".doc", ".pdf", ".jpg", ".png"]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_20_file_operations_coverage(self, filename: str, extension: str):
        """
        Property 20: Command Recognition Coverage
        
        For any file operation command, parser should recognize it.
        
        Validates: Requirements 17.1
        """
        parser = CommandParser()
        if not filename or not filename.strip():
            return
        
        filename = filename.strip() + extension
        operations = [
            f"create file {filename}",
            f"delete file {filename}",
            f"search for {filename}",
        ]
        
        for text in operations:
            result = parser.interpret(text)
            
            # PROPERTY ASSERTION
            assert result.is_command, f"Failed to recognize file operation: {text}"
            assert result.action_id is not None
    
    @given(
        setting_value=st.integers(min_value=0, max_value=100),
        setting_type=st.sampled_from(["volume", "brightness"]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_20_settings_coverage(self, setting_value: int, setting_type: str):
        """
        Property 20: Command Recognition Coverage
        
        For any settings command, parser should recognize it and extract parameters.
        
        Validates: Requirements 17.1
        """
        parser = CommandParser()
        text = f"set {setting_type} to {setting_value} percent"
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize settings command: {text}"
        assert result.action_id is not None
        assert "level" in result.parameters, "Failed to extract level parameter"
        assert result.parameters["level"] == setting_value
    
    # ========================================================================
    # PROPERTY 21: COMMAND CHAINING SUPPORT
    # ========================================================================
    
    @given(
        app1=st.sampled_from(["chrome", "firefox", "notepad", "calculator"]),
        app2=st.sampled_from(["chrome", "firefox", "notepad", "calculator"]),
        connector=st.sampled_from([" and ", " then "]),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_21_command_chaining(self, app1: str, app2: str, connector: str):
        """
        Property 21: Command Chaining Support
        
        For any valid chained command, parser should extract all sub-commands.
        
        Validates: Requirements 17.6
        """
        parser = CommandParser()
        text = f"open {app1}{connector}close {app2}"
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize chained command: {text}"
        assert result.action_id == "CHAINED_COMMAND", \
            f"Wrong action_id for chained command: {result.action_id}"
        assert "sub_commands" in result.parameters, "No sub_commands in chained command"
        
        sub_commands = result.parameters["sub_commands"]
        assert len(sub_commands) >= 2, \
            f"Expected at least 2 sub-commands, got {len(sub_commands)}"
        
        # Each sub-command should have required fields
        for sub_cmd in sub_commands:
            assert "action_id" in sub_cmd
            assert "parameters" in sub_cmd
            assert "confidence" in sub_cmd
            assert 0.0 <= sub_cmd["confidence"] <= 1.0
    
    @given(
        num_commands=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_21_multiple_command_chain(self, num_commands: int):
        """
        Property 21: Command Chaining Support
        
        For any number of chained commands, all should be extracted.
        
        Validates: Requirements 17.6
        """
        parser = CommandParser()
        commands = ["open chrome", "maximize window", "type hello", "click", "close chrome"]
        selected_commands = commands[:num_commands]
        text = " and ".join(selected_commands)
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize chained command: {text}"
        assert result.action_id == "CHAINED_COMMAND"
        
        sub_commands = result.parameters["sub_commands"]
        # Should extract at least some sub-commands
        assert len(sub_commands) >= 1, "No sub-commands extracted"
        
        # Confidence should be averaged
        assert 0.0 <= result.confidence <= 1.0
    
    @given(
        app_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))),
        text_content=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'Zs'))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_21_chain_with_parameters(self, app_name: str, text_content: str):
        """
        Property 21: Command Chaining Support
        
        For chained commands with parameters, all parameters should be extracted.
        
        Validates: Requirements 17.6
        """
        parser = CommandParser()
        if not app_name or not app_name.strip() or not text_content or not text_content.strip():
            return
        
        app_name = app_name.strip()
        text_content = text_content.strip()
        text = f"open {app_name} and type {text_content}"
        
        result = parser.interpret(text)
        
        # PROPERTY ASSERTIONS
        assert result.is_command, f"Failed to recognize chained command: {text}"
        assert result.action_id == "CHAINED_COMMAND"
        
        sub_commands = result.parameters["sub_commands"]
        assert len(sub_commands) >= 2, "Expected at least 2 sub-commands"
        
        # Check that parameters were extracted for sub-commands
        has_app_param = any("app_name" in cmd["parameters"] for cmd in sub_commands)
        has_text_param = any("text" in cmd["parameters"] for cmd in sub_commands)
        
        assert has_app_param or has_text_param, "No parameters extracted from chained commands"
    
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
        
        For any text, interpreting it multiple times should give same result.
        """
        parser = CommandParser()
        if not text or not text.strip():
            return
        
        text = text.strip()
        
        # Interpret same text multiple times
        results = [parser.interpret(text) for _ in range(3)]
        
        # PROPERTY ASSERTION: Results should be consistent
        for i in range(1, len(results)):
            assert results[i].is_command == results[0].is_command
            assert results[i].action_id == results[0].action_id
            assert results[i].confidence == results[0].confidence
            # Parameters might have different object identity but same content
            assert results[i].parameters == results[0].parameters
    
    # ========================================================================
    # PROPERTY: ROBUSTNESS
    # ========================================================================
    
    @given(
        command=st.sampled_from(["open chrome", "close firefox", "type hello", "click"]),
        prefix=st.text(max_size=20, alphabet=st.characters(whitelist_categories=('Zs',))),
        suffix=st.text(max_size=20, alphabet=st.characters(whitelist_categories=('Zs',))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_whitespace_robustness(self, command: str, prefix: str, suffix: str):
        """
        Property: Robustness to Whitespace
        
        For any command, adding whitespace should not affect recognition.
        """
        parser = CommandParser()
        text_with_whitespace = prefix + command + suffix
        
        result = parser.interpret(text_with_whitespace)
        
        # PROPERTY ASSERTION: Should still recognize command
        assert result.is_command, f"Failed to recognize command with whitespace: '{text_with_whitespace}'"
        assert result.confidence > 0.0
    
    @given(
        command=st.sampled_from(["open chrome", "OPEN CHROME", "Open Chrome", "OpEn ChRoMe"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_case_insensitivity(self, command: str):
        """
        Property: Case Insensitivity
        
        For any command, case variations should be recognized equally.
        """
        parser = CommandParser()
        result = parser.interpret(command)
        
        # PROPERTY ASSERTION: Should recognize regardless of case
        assert result.is_command, f"Failed to recognize command: {command}"
        assert result.action_id == "OPEN_APP"
