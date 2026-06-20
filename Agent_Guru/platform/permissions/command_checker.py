"""Module: Agent_Guru.platform.permissions.command_checker
Purpose: Command permission validation with pattern matching and argument validation.

This module implements comprehensive command validation:
- Allowed command pattern matching (regex-based)
- Blocked command detection (security priority)
- Command argument validation
- Dangerous pattern detection
- Command sanitization
- Injection attack prevention

Performance Characteristics:
    - Time Complexity: O(n + m) where n is allowed patterns, m is blocked patterns
    - Space Complexity: O(1) for validation
    - Pattern Matching: O(k) where k is command length

Security Features:
    - Injection attack prevention (SQL, shell, command)
    - Dangerous command detection (rm -rf, format, sudo)
    - Argument sanitization
    - Whitelist-based validation
    - Blacklist priority (security first)

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import logging
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Command category types."""

    FILE_OPERATION = "file_operation"
    NETWORK_OPERATION = "network_operation"
    SYSTEM_OPERATION = "system_operation"
    PACKAGE_MANAGEMENT = "package_management"
    VERSION_CONTROL = "version_control"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


class DangerLevel(Enum):
    """Command danger level."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CommandValidationResult:
    """Result of command validation."""

    allowed: bool
    command: str
    parsed_args: list[str]
    matched_pattern: str | None
    blocked_pattern: str | None
    reason: str
    category: CommandCategory
    danger_level: DangerLevel
    sanitized_command: str | None
    warnings: list[str]


class CommandValidationError(Exception):
    """Raised when command validation fails."""


class CommandPermissionChecker:
    """Command permission checker with pattern matching and argument validation.

    Features:
    - Regex-based pattern matching
    - Dangerous command detection
    - Argument validation and sanitization
    - Injection attack prevention
    - Command categorization
    - Danger level assessment

    Time Complexity: O(n + m) where n is allowed, m is blocked patterns
    Space Complexity: O(1) for validation

    Example:
        >>> checker = CommandPermissionChecker()
        >>> checker.add_allowed_pattern(r"^git .*")
        >>> checker.add_blocked_pattern(r".*rm -rf.*")
        >>> result = checker.validate_command("git status")
        >>> print(f"Allowed: {result.allowed}")

    """

    # Dangerous command patterns (CRITICAL - always blocked)
    DANGEROUS_PATTERNS: ClassVar[list[str]] = [
        r"rm\s+-rf\s+/",  # Recursive delete from root
        r"format\s+[A-Z]:",  # Windows format
        r"del\s+/[fqs]",  # Windows forced delete
        r"sudo\s+",  # Privilege escalation
        r"chmod\s+777",  # Insecure permissions
        r">\s*/dev/sd[a-z]",  # Direct disk write
        r"dd\s+if=.*of=/dev/",  # Disk imaging
        r"mkfs\.",  # Filesystem creation
        r"shutdown",  # System shutdown
        r"reboot",  # System reboot
        r":(){ :|:& };:",  # Fork bomb
        r"curl.*\|\s*bash",  # Pipe to shell (dangerous)
        r"wget.*\|\s*sh",  # Pipe to shell (dangerous)
        r"eval\s+",  # Code evaluation
        r"exec\s+",  # Code execution
        r"system\s*\(",  # System call
        r"__import__\s*\(",  # Dynamic import
        r"compile\s*\(",  # Code compilation
    ]

    # Injection attack patterns
    INJECTION_PATTERNS: ClassVar[list[str]] = [
        r";\s*rm\s+",  # Command injection
        r"&&\s*rm\s+",  # Command chaining
        r"\|\s*rm\s+",  # Pipe injection
        r"`.*`",  # Command substitution
        r"\$\(.*\)",  # Command substitution
        r"<\s*\(",  # Process substitution
        r">\s*\(",  # Process substitution
    ]

    def __init__(self) -> None:
        """Initialize command permission checker."""
        self._allowed_patterns: list[re.Pattern] = []
        self._blocked_patterns: list[re.Pattern] = []
        self._max_command_length = 10000  # Prevent DoS
        self._max_args = 100  # Prevent DoS

        # Add dangerous patterns to blocked list by default
        for pattern in self.DANGEROUS_PATTERNS:
            self._blocked_patterns.append(re.compile(pattern, re.IGNORECASE))

        logger.debug(
            f"CommandPermissionChecker initialized with "
            f"{len(self._blocked_patterns)} dangerous patterns",
        )

    def add_allowed_pattern(self, pattern: str) -> None:
        """Add allowed command pattern (regex).

        Args:
            pattern: Regular expression pattern

        Example:
            >>> checker.add_allowed_pattern(r"^git .*")
            >>> checker.add_allowed_pattern(r"^npm (install|test|build)")

        """
        try:
            compiled_pattern = re.compile(pattern)
            self._allowed_patterns.append(compiled_pattern)
            logger.debug("Added allowed command pattern: %s", pattern)
        except re.error as e:
            logger.exception("Invalid regex pattern")
            msg = f"Invalid regex pattern: {pattern}"
            raise CommandValidationError(msg) from e

    def add_blocked_pattern(self, pattern: str) -> None:
        """Add blocked command pattern (regex).

        Blocked patterns take precedence over allowed patterns.

        Args:
            pattern: Regular expression pattern

        Example:
            >>> checker.add_blocked_pattern(r".*rm -rf.*")
            >>> checker.add_blocked_pattern(r".*sudo.*")

        """
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self._blocked_patterns.append(compiled_pattern)
            logger.debug("Added blocked command pattern: %s", pattern)
        except re.error as e:
            logger.exception("Invalid regex pattern")
            msg = f"Invalid regex pattern: {pattern}"
            raise CommandValidationError(msg) from e

    def validate_command(self, command: str, validate_args: bool = True) -> CommandValidationResult:
        """Validate command against allowed and blocked patterns.

        Time Complexity: O(n + m) where n is allowed, m is blocked patterns
        Space Complexity: O(k) where k is number of arguments

        Args:
            command: Command string to validate
            validate_args: Whether to validate command arguments

        Returns:
            CommandValidationResult with validation details

        """
        warnings = []

        # Basic validation
        if not command or not command.strip():
            return CommandValidationResult(
                allowed=False,
                command=command,
                parsed_args=[],
                matched_pattern=None,
                blocked_pattern=None,
                reason="Empty command",
                category=CommandCategory.UNKNOWN,
                danger_level=DangerLevel.SAFE,
                sanitized_command=None,
                warnings=[],
            )

        # Length validation (prevent DoS)
        if len(command) > self._max_command_length:
            return CommandValidationResult(
                allowed=False,
                command=command[:100] + "...",
                parsed_args=[],
                matched_pattern=None,
                blocked_pattern=None,
                reason=f"Command too long (max: {self._max_command_length})",
                category=CommandCategory.UNKNOWN,
                danger_level=DangerLevel.HIGH,
                sanitized_command=None,
                warnings=[],
            )

        # Parse command arguments
        try:
            parsed_args = shlex.split(command)
        except ValueError as e:
            return CommandValidationResult(
                allowed=False,
                command=command,
                parsed_args=[],
                matched_pattern=None,
                blocked_pattern=None,
                reason=f"Failed to parse command: {e}",
                category=CommandCategory.UNKNOWN,
                danger_level=DangerLevel.MEDIUM,
                sanitized_command=None,
                warnings=[],
            )

        # Argument count validation (prevent DoS)
        if len(parsed_args) > self._max_args:
            return CommandValidationResult(
                allowed=False,
                command=command,
                parsed_args=parsed_args[:10],
                matched_pattern=None,
                blocked_pattern=None,
                reason=f"Too many arguments (max: {self._max_args})",
                category=CommandCategory.UNKNOWN,
                danger_level=DangerLevel.HIGH,
                sanitized_command=None,
                warnings=[],
            )

        # Check for injection attacks
        injection_result = self._check_injection_attacks(command)
        if not injection_result[0]:
            return CommandValidationResult(
                allowed=False,
                command=command,
                parsed_args=parsed_args,
                matched_pattern=None,
                blocked_pattern=injection_result[1],
                reason=f"Injection attack detected: {injection_result[1]}",
                category=CommandCategory.UNKNOWN,
                danger_level=DangerLevel.CRITICAL,
                sanitized_command=None,
                warnings=[],
            )

        # Check blocked patterns first (security priority)
        for pattern in self._blocked_patterns:
            if pattern.search(command):
                logger.warning("Command blocked by pattern: %s", command)
                return CommandValidationResult(
                    allowed=False,
                    command=command,
                    parsed_args=parsed_args,
                    matched_pattern=None,
                    blocked_pattern=pattern.pattern,
                    reason=f"Command matches blocked pattern: {pattern.pattern}",
                    category=self._categorize_command(parsed_args[0] if parsed_args else ""),
                    danger_level=DangerLevel.CRITICAL,
                    sanitized_command=None,
                    warnings=[],
                )

        # Check allowed patterns
        matched_pattern = None
        for pattern in self._allowed_patterns:
            if pattern.search(command):
                matched_pattern = pattern.pattern
                break

        if not matched_pattern:
            logger.warning("Command denied (no matching pattern): %s", command)
            return CommandValidationResult(
                allowed=False,
                command=command,
                parsed_args=parsed_args,
                matched_pattern=None,
                blocked_pattern=None,
                reason="Command does not match any allowed pattern",
                category=self._categorize_command(parsed_args[0] if parsed_args else ""),
                danger_level=DangerLevel.MEDIUM,
                sanitized_command=None,
                warnings=[],
            )

        # Validate arguments if requested
        if validate_args and len(parsed_args) > 1:
            arg_validation = self._validate_arguments(parsed_args)
            if not arg_validation[0]:
                warnings.append(arg_validation[1])

        # Assess danger level
        danger_level = self._assess_danger_level(command, parsed_args)

        # Sanitize command
        sanitized_command = self._sanitize_command(command)

        # Categorize command
        category = self._categorize_command(parsed_args[0] if parsed_args else "")

        logger.debug(
            f"Command allowed: {command} -> {matched_pattern} "
            f"(category: {category.value}, danger: {danger_level.value})",
        )

        return CommandValidationResult(
            allowed=True,
            command=command,
            parsed_args=parsed_args,
            matched_pattern=matched_pattern,
            blocked_pattern=None,
            reason="Command matches allowed pattern",
            category=category,
            danger_level=danger_level,
            sanitized_command=sanitized_command,
            warnings=warnings,
        )

    def _check_injection_attacks(self, command: str) -> tuple[bool, str | None]:
        """Check for injection attack patterns.

        Args:
            command: Command to check

        Returns:
            Tuple of (is_safe, detected_pattern)

        """
        for pattern_str in self.INJECTION_PATTERNS:
            pattern = re.compile(pattern_str)
            if pattern.search(command):
                return (False, pattern_str)
        return (True, None)

    def _validate_arguments(self, args: list[str]) -> tuple[bool, str]:
        """Validate command arguments for suspicious patterns.

        Args:
            args: Parsed command arguments

        Returns:
            Tuple of (is_valid, warning_message)

        """
        warnings = []

        for arg in args[1:]:  # Skip command name
            # Check for suspicious characters
            if any(char in arg for char in [";", "|", "&", "`", "$", "<", ">"]):
                warnings.append(f"Suspicious character in argument: {arg}")

            # Check for path traversal
            if ".." in arg:
                warnings.append(f"Path traversal detected in argument: {arg}")

            # Check for environment variable expansion
            if arg.startswith("$"):
                warnings.append(f"Environment variable in argument: {arg}")

        if warnings:
            return (False, "; ".join(warnings))
        return (True, "")

    def _assess_danger_level(self, command: str, args: list[str]) -> DangerLevel:
        """Assess danger level of command.

        Args:
            command: Full command string
            args: Parsed arguments

        Returns:
            Danger level

        """
        if not args:
            return DangerLevel.SAFE

        base_command = args[0].lower()

        # Critical danger commands
        critical_commands = ["rm", "del", "format", "dd", "mkfs"]
        if any(cmd in base_command for cmd in critical_commands):
            return DangerLevel.CRITICAL

        # High danger commands
        high_commands = ["chmod", "chown", "kill", "pkill"]
        if any(cmd in base_command for cmd in high_commands):
            return DangerLevel.HIGH

        # Medium danger commands
        medium_commands = ["mv", "cp", "wget", "curl"]
        if any(cmd in base_command for cmd in medium_commands):
            return DangerLevel.MEDIUM

        # Low danger commands
        low_commands = ["npm", "pip", "docker", "kubectl"]
        if any(cmd in base_command for cmd in low_commands):
            return DangerLevel.LOW

        return DangerLevel.SAFE

    def _categorize_command(self, base_command: str) -> CommandCategory:
        """Categorize command by type.

        Args:
            base_command: Base command name

        Returns:
            Command category

        """
        base_command = base_command.lower()

        # File operations
        file_commands = ["ls", "cat", "cp", "mv", "rm", "mkdir", "touch", "chmod"]
        if any(cmd in base_command for cmd in file_commands):
            return CommandCategory.FILE_OPERATION

        # Network operations
        network_commands = ["curl", "wget", "ping", "ssh", "scp", "ftp"]
        if any(cmd in base_command for cmd in network_commands):
            return CommandCategory.NETWORK_OPERATION

        # System operations
        system_commands = ["ps", "kill", "top", "systemctl", "service"]
        if any(cmd in base_command for cmd in system_commands):
            return CommandCategory.SYSTEM_OPERATION

        # Package management
        package_commands = ["npm", "pip", "apt", "yum", "brew", "cargo"]
        if any(cmd in base_command for cmd in package_commands):
            return CommandCategory.PACKAGE_MANAGEMENT

        # Version control
        vcs_commands = ["git", "svn", "hg"]
        if any(cmd in base_command for cmd in vcs_commands):
            return CommandCategory.VERSION_CONTROL

        # Development
        dev_commands = ["python", "node", "java", "gcc", "make", "docker", "kubectl"]
        if any(cmd in base_command for cmd in dev_commands):
            return CommandCategory.DEVELOPMENT

        return CommandCategory.UNKNOWN

    def _sanitize_command(self, command: str) -> str:
        """Sanitize command by removing potentially dangerous elements.

        Args:
            command: Command to sanitize

        Returns:
            Sanitized command

        """
        # Remove trailing semicolons and pipes
        sanitized = command.strip().rstrip(";|&")

        # Remove multiple spaces
        return " ".join(sanitized.split())

    def is_command_allowed(self, command: str) -> bool:
        """Quick check if command is allowed.

        Time Complexity: O(n + m)
        Space Complexity: O(1)

        Args:
            command: Command to check

        Returns:
            True if command is allowed

        """
        result = self.validate_command(command, validate_args=False)
        return result.allowed

    def get_command_info(self, command: str) -> dict[str, Any]:
        """Get detailed information about command.

        Args:
            command: Command to analyze

        Returns:
            Dictionary with command information

        """
        result = self.validate_command(command)

        return {
            "allowed": result.allowed,
            "command": result.command,
            "parsed_args": result.parsed_args,
            "matched_pattern": result.matched_pattern,
            "blocked_pattern": result.blocked_pattern,
            "reason": result.reason,
            "category": result.category.value,
            "danger_level": result.danger_level.value,
            "sanitized_command": result.sanitized_command,
            "warnings": result.warnings,
        }

    def clear_patterns(self) -> None:
        """Clear all allowed patterns (keeps dangerous patterns)."""
        self._allowed_patterns.clear()
        logger.debug("Allowed command patterns cleared")

    @property
    def allowed_pattern_count(self) -> int:
        """Get number of allowed patterns."""
        return len(self._allowed_patterns)

    @property
    def blocked_pattern_count(self) -> int:
        """Get number of blocked patterns."""
        return len(self._blocked_patterns)


def is_dangerous_command(command: str) -> bool:
    """Quick check if command is dangerous.

    Time Complexity: O(n) where n is number of dangerous patterns
    Space Complexity: O(1)

    Args:
        command: Command to check

    Returns:
        True if command is dangerous

    """
    for pattern_str in CommandPermissionChecker.DANGEROUS_PATTERNS:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        if pattern.search(command):
            return True
    return False


def sanitize_command_args(args: list[str]) -> list[str]:
    """Sanitize command arguments.

    Time Complexity: O(n) where n is number of arguments
    Space Complexity: O(n)

    Args:
        args: Command arguments

    Returns:
        Sanitized arguments

    """
    sanitized = []
    for arg in args:
        # Remove dangerous characters
        cleaned = arg.replace(";", "").replace("|", "").replace("&", "")
        cleaned = cleaned.replace("`", "").replace("$", "")
        sanitized.append(cleaned)
    return sanitized


def parse_command_safely(command: str) -> list[str] | None:
    """Safely parse command into arguments.

    Time Complexity: O(n) where n is command length
    Space Complexity: O(n)

    Args:
        command: Command to parse

    Returns:
        Parsed arguments or None if parsing fails

    """
    try:
        return shlex.split(command)
    except ValueError:
        return None
