"""
Property-based tests for Agent_Guru.platform.permissions.command_checker
Using Hypothesis for comprehensive validation
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from Agent_Guru.platform.permissions.command_checker import (
    CommandPermissionChecker,
    CommandCategory,
    DangerLevel,
    is_dangerous_command,
    sanitize_command_args
)


# Custom strategies for generating test data
@st.composite
def safe_command_string(draw):
    """Generate safe command strings."""
    commands = ["git", "npm", "python", "node", "ls", "cat", "echo"]
    command = draw(st.sampled_from(commands))
    
    # Add safe arguments
    args = draw(st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=20
        ),
        min_size=0,
        max_size=5
    ))
    
    if args:
        return f"{command} {' '.join(args)}"
    return command


@st.composite
def command_with_args(draw):
    """Generate commands with various arguments."""
    command = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_"
    )))
    
    num_args = draw(st.integers(min_value=0, max_value=10))
    args = [
        draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_."
        )))
        for _ in range(num_args)
    ]
    
    if args:
        return f"{command} {' '.join(args)}"
    return command


class TestCommandValidationProperties:
    """Property-based tests for command validation."""
    
    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_empty_or_whitespace_always_rejected(self, command: str):
        """
        Feature: guru-platform-integration, Property: Empty Commands Rejected
        
        For any empty or whitespace-only command, validation should return
        allowed=False with appropriate reason.
        """
        assume(not command or command.isspace())
        
        checker = CommandPermissionChecker()
        result = checker.validate_command(command)
        
        assert not result.allowed
        assert result.reason == "Empty command"
    
    def test_property_long_commands_rejected(self):
        """
        Feature: guru-platform-integration, Property: Long Commands Rejected
        
        For any command exceeding maximum length, validation should return
        allowed=False with "too long" reason.
        """
        checker = CommandPermissionChecker()
        
        # Test with command exactly at max length + 1
        long_command = "a" * (checker._max_command_length + 1)
        result = checker.validate_command(long_command)
        
        assert not result.allowed
        assert "too long" in result.reason.lower()
        
        # Test with much longer command
        very_long_command = "b" * (checker._max_command_length * 2)
        result = checker.validate_command(very_long_command)
        
        assert not result.allowed
        assert "too long" in result.reason.lower()
    
    @given(safe_command_string())
    @settings(max_examples=100)
    def test_property_allowed_pattern_always_matches(self, command: str):
        """
        Feature: guru-platform-integration, Property: Allowed Patterns Match
        
        For any command matching an allowed pattern, validation should return
        allowed=True with matched_pattern set.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")  # Allow everything
        
        result = checker.validate_command(command)
        
        # Should be allowed unless it's dangerous
        if not is_dangerous_command(command):
            assert result.allowed
            assert result.matched_pattern is not None
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_property_dangerous_commands_always_blocked(self, suffix: str):
        """
        Feature: guru-platform-integration, Property: Dangerous Commands Blocked
        
        For any command containing dangerous patterns, validation should return
        allowed=False regardless of allowed patterns.
        """
        dangerous_prefixes = ["rm -rf /", "sudo ", "format C:", "shutdown"]
        
        for prefix in dangerous_prefixes:
            command = f"{prefix}{suffix}"
            checker = CommandPermissionChecker()
            checker.add_allowed_pattern(r".*")  # Allow everything
            
            result = checker.validate_command(command)
            
            # Should be blocked (either by pattern or parsing failure)
            assert not result.allowed
            # Danger level should be high or critical if successfully parsed
            if result.parsed_args:
                assert result.danger_level in [DangerLevel.HIGH, DangerLevel.CRITICAL]
    
    @given(command_with_args())
    @settings(max_examples=100)
    def test_property_validation_result_structure(self, command: str):
        """
        Feature: guru-platform-integration, Property: Result Structure Complete
        
        For any command validation, the result should contain all required fields
        with appropriate types.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(command)
        
        # Check all required fields exist
        assert isinstance(result.allowed, bool)
        assert isinstance(result.command, str)
        assert isinstance(result.parsed_args, list)
        assert isinstance(result.reason, str)
        assert isinstance(result.category, CommandCategory)
        assert isinstance(result.danger_level, DangerLevel)
        assert isinstance(result.warnings, list)
    
    @given(st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_.")
        ),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_property_parsed_args_count_matches(self, args: list):
        """
        Feature: guru-platform-integration, Property: Argument Count Consistency
        
        For any valid command, the number of parsed arguments should match
        the number of space-separated tokens (when no quotes are involved).
        """
        command = " ".join(args)
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(command)
        
        if result.allowed and result.parsed_args:
            # Parsed args should have same count as input args (no quotes in input)
            assert len(result.parsed_args) == len(args)
    
    @given(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_"
    )))
    @settings(max_examples=100)
    def test_property_blocked_pattern_priority(self, command: str):
        """
        Feature: guru-platform-integration, Property: Blocked Pattern Priority
        
        For any command, if it matches both allowed and blocked patterns,
        the blocked pattern should take precedence.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")  # Allow everything
        checker.add_blocked_pattern(f".*{command}.*")  # Block this specific command
        
        result = checker.validate_command(command)
        
        assert not result.allowed
        assert result.blocked_pattern is not None
    
    @given(safe_command_string())
    @settings(max_examples=100)
    def test_property_sanitization_removes_trailing(self, command: str):
        """
        Feature: guru-platform-integration, Property: Sanitization Consistency
        
        For any command, sanitization should remove trailing dangerous characters
        while preserving the core command.
        """
        # Add trailing dangerous characters
        command_with_trailing = f"{command}  ;  "
        
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(command_with_trailing)
        
        if result.allowed and result.sanitized_command:
            # Sanitized should not have trailing semicolons or spaces
            assert not result.sanitized_command.endswith(";")
            assert not result.sanitized_command.endswith(" ")
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_property_is_command_allowed_consistency(self, command: str):
        """
        Feature: guru-platform-integration, Property: Quick Check Consistency
        
        For any command, is_command_allowed() should return the same result
        as validate_command().allowed.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        quick_result = checker.is_command_allowed(command)
        full_result = checker.validate_command(command)
        
        assert quick_result == full_result.allowed
    
    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_property_sanitize_args_removes_dangerous(self, args: list):
        """
        Feature: guru-platform-integration, Property: Argument Sanitization
        
        For any list of arguments, sanitization should remove all dangerous
        characters while preserving safe content.
        """
        # Add dangerous characters to args
        dangerous_args = [f"{arg};|&`$" for arg in args]
        
        sanitized = sanitize_command_args(dangerous_args)
        
        # Check dangerous characters removed
        for sanitized_arg in sanitized:
            assert ";" not in sanitized_arg
            assert "|" not in sanitized_arg
            assert "&" not in sanitized_arg
            assert "`" not in sanitized_arg
            assert "$" not in sanitized_arg


class TestCommandCategorizationProperties:
    """Property-based tests for command categorization."""
    
    @given(st.sampled_from(["ls", "cat", "cp", "mv", "rm", "mkdir"]))
    @settings(max_examples=100)
    def test_property_file_commands_categorized(self, base_command: str):
        """
        Feature: guru-platform-integration, Property: File Command Category
        
        For any file operation command, categorization should return
        FILE_OPERATION category.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(f"{base_command} test.txt")
        
        if result.allowed:
            assert result.category == CommandCategory.FILE_OPERATION
    
    @given(st.sampled_from(["git", "svn", "hg"]))
    @settings(max_examples=100)
    def test_property_vcs_commands_categorized(self, base_command: str):
        """
        Feature: guru-platform-integration, Property: VCS Command Category
        
        For any version control command, categorization should return
        VERSION_CONTROL category.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(f"{base_command} status")
        
        if result.allowed:
            assert result.category == CommandCategory.VERSION_CONTROL
    
    @given(st.sampled_from(["npm", "pip", "apt", "yum", "brew"]))
    @settings(max_examples=100)
    def test_property_package_commands_categorized(self, base_command: str):
        """
        Feature: guru-platform-integration, Property: Package Command Category
        
        For any package management command, categorization should return
        PACKAGE_MANAGEMENT category.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(f"{base_command} install test")
        
        if result.allowed:
            assert result.category == CommandCategory.PACKAGE_MANAGEMENT


class TestDangerLevelProperties:
    """Property-based tests for danger level assessment."""
    
    @given(st.sampled_from(["ls", "cat", "echo", "pwd"]))
    @settings(max_examples=100)
    def test_property_safe_commands_low_danger(self, base_command: str):
        """
        Feature: guru-platform-integration, Property: Safe Command Danger Level
        
        For any safe read-only command, danger level should be SAFE or LOW.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(base_command)
        
        if result.allowed:
            assert result.danger_level in [DangerLevel.SAFE, DangerLevel.LOW]
    
    @given(st.sampled_from(["chmod", "chown", "kill"]))
    @settings(max_examples=100)
    def test_property_system_commands_high_danger(self, base_command: str):
        """
        Feature: guru-platform-integration, Property: System Command Danger Level
        
        For any system modification command, danger level should be HIGH or CRITICAL.
        """
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        result = checker.validate_command(f"{base_command} test")
        
        if result.allowed:
            assert result.danger_level in [DangerLevel.HIGH, DangerLevel.CRITICAL]


class TestPatternMatchingProperties:
    """Property-based tests for pattern matching."""
    
    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll"),
            whitelist_characters="-_"
        ))
    )
    @settings(max_examples=100)
    def test_property_exact_pattern_matches_exactly(self, command: str):
        """
        Feature: guru-platform-integration, Property: Exact Pattern Matching
        
        For any command, an exact pattern should match only that exact command.
        """
        import re
        
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(f"^{re.escape(command)}$")
        
        # Exact match should be allowed
        result = checker.validate_command(command)
        assert result.allowed
        
        # With suffix should not match
        result = checker.validate_command(f"{command} extra")
        assert not result.allowed
    
    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll")
        ))
    )
    @settings(max_examples=100)
    def test_property_wildcard_pattern_matches_prefix(self, prefix: str):
        """
        Feature: guru-platform-integration, Property: Wildcard Pattern Matching
        
        For any prefix, a wildcard pattern should match all commands
        starting with that prefix.
        """
        import re
        
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(f"^{re.escape(prefix)} .*")
        
        # Should match with any suffix
        result = checker.validate_command(f"{prefix} anything")
        assert result.allowed
        
        result = checker.validate_command(f"{prefix} something else")
        assert result.allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
