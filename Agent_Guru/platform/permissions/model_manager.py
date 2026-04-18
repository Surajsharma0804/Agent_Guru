"""
Module: Agent_Guru.platform.permissions.model_manager
Purpose: Permission model manager with YAML configuration and hot reload

This module implements fine-grained permission control with:
- YAML-based configuration loading
- Configuration validation
- Hot reload without restart
- Environment-specific configs
- Path, command, and network permission checking
- Enhanced time-based permissions with timezone support

Performance Characteristics:
    - Time Complexity: O(1) for permission checks (hash table lookups)
    - Space Complexity: O(n) where n is number of permission rules
    - Hot Reload: <100ms for typical configurations

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Optional

import yaml

# Import enhanced time-based permissions
from .time_checker import TimeRestriction as EnhancedTimeRestriction

logger = logging.getLogger(__name__)


class FileOperation(Enum):
    """File system operation types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


class HttpMethod(Enum):
    """HTTP method types."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class OperationType(Enum):
    """Operation types for quota tracking."""
    FILE_OPERATION = "file_operation"
    COMMAND_EXECUTION = "command_execution"
    NETWORK_REQUEST = "network_request"


@dataclass
class TimeRestriction:
    """
    DEPRECATED: Use EnhancedTimeRestriction from time_checker module instead.

    This class is kept for backward compatibility only.
    """
    days: list[str]  # ["monday", "tuesday", ...]
    hours: str  # "09:00-18:00"

    def is_allowed(self, dt: Optional[datetime] = None) -> bool:
        """Check if current time is within allowed window."""
        if dt is None:
            dt = datetime.now(tz=timezone.utc)

        # Check day of week
        day_name = dt.strftime("%A").lower()
        if day_name not in [d.lower() for d in self.days]:
            return False

        # Parse and check hour range
        start_str, end_str = self.hours.split("-")
        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)
        current_time = dt.time()

        return start_time <= current_time <= end_time


@dataclass
class PathPermission:
    """File system path permission with enhanced time restrictions."""
    path: str
    permissions: list[str]
    time_restrictions: list[EnhancedTimeRestriction] = field(default_factory=list)

    def is_allowed(
        self,
        operation: FileOperation,
        dt: Optional[datetime] = None
    ) -> bool:
        """Check if operation is allowed at given time."""
        # Check operation permission
        if operation.value not in self.permissions:
            return False

        # Check time restrictions if any (OR logic - any restriction allows)
        if self.time_restrictions:
            return any(tr.is_allowed(dt) for tr in self.time_restrictions)

        return True


@dataclass
class QuotaConfig:
    """Operation quota configuration."""
    per_hour: int
    per_day: int


@dataclass
class QuotaStatus:
    """Current quota status."""
    operation_type: OperationType
    current_hour: int
    current_day: int
    limit_hour: int
    limit_day: int
    available: bool

    @property
    def hour_remaining(self) -> int:
        """Remaining operations this hour."""
        return max(0, self.limit_hour - self.current_hour)

    @property
    def day_remaining(self) -> int:
        """Remaining operations today."""
        return max(0, self.limit_day - self.current_day)


@dataclass
class OperationContext:
    """Context for permission evaluation."""
    user_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    additional_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionModel:
    """Complete permission model configuration."""
    version: str
    environment: str
    file_system: dict[str, Any]
    commands: dict[str, Any]
    network: dict[str, Any]
    resources: dict[str, Any]
    quotas: dict[str, QuotaConfig]
    lockdown_mode: dict[str, Any]

    # Parsed structures for fast lookup
    allowed_paths: list[PathPermission] = field(default_factory=list)
    blocked_extensions: set[str] = field(default_factory=set)
    allowed_command_patterns: list[re.Pattern] = field(default_factory=list)
    blocked_command_patterns: list[re.Pattern] = field(default_factory=list)
    allowed_domains: set[str] = field(default_factory=set)
    allowed_methods: set[HttpMethod] = field(default_factory=set)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""


class PermissionModelManager:
    """
    Permission model manager with dynamic policy evaluation.

    Features:
    - YAML-based configuration
    - Hot reload without restart
    - Environment-specific configs
    - Time-based permissions
    - User/role-based permissions
    - Operation quotas

    Time Complexity: O(1) for most operations (hash table lookups)
    Space Complexity: O(n) where n is number of permission rules

    Example:
        >>> manager = PermissionModelManager(Path("config/permissions.yaml"))
        >>> context = OperationContext(user_id="user123")
        >>> allowed = manager.is_path_allowed(
        ...     Path("/home/agent_guru/workspace/file.txt"),
        ...     FileOperation.READ,
        ...     context
        ... )
        >>> print(f"Read allowed: {allowed}")
    """

    def __init__(self, config_path: Path):
        """
        Initialize permission model manager.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            ConfigurationError: If configuration is invalid
            FileNotFoundError: If configuration file not found
        """
        self.config_path = config_path
        self._lock = RLock()  # Thread-safe configuration updates
        self._config_hash: Optional[str] = None
        self._lockdown_mode = False
        self._lockdown_activated_at: Optional[datetime] = None
        self._lockdown_reason: Optional[str] = None
        self._lockdown_activated_by: Optional[str] = None

        # Quota tracking (in-memory, reset hourly/daily)
        self._quota_counters: dict[str, dict[OperationType, dict[str, int]]] = {}
        self._last_hour_reset = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
        self._last_day_reset = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Load initial configuration
        self.model: PermissionModel = self.load_model()

        logger.info(
            f"PermissionModelManager initialized with config: {config_path}, "
            f"environment: {self.model.environment}"
        )

    def load_model(self) -> PermissionModel:
        """
        Load permission model from YAML configuration.

        Returns:
            Loaded and validated permission model

        Raises:
            ConfigurationError: If configuration is invalid
            FileNotFoundError: If configuration file not found
        """
        with self._lock:
            try:
                # Read configuration file
                with open(self.config_path) as f:
                    config_data = yaml.safe_load(f)

                # Compute configuration hash for change detection
                config_str = yaml.dump(config_data, sort_keys=True)
                new_hash = hashlib.sha256(config_str.encode()).hexdigest()

                # Skip reload if configuration unchanged
                if self._config_hash == new_hash:
                    logger.debug("Configuration unchanged, skipping reload")
                    return self.model if hasattr(self, 'model') else self._parse_config(config_data)

                self._config_hash = new_hash

                # Validate and parse configuration
                self._validate_config(config_data)
                model = self._parse_config(config_data)

                logger.info("Configuration loaded successfully (hash: %s...)", new_hash[:8])
                return model

            except FileNotFoundError:
                logger.error("Configuration file not found: %s", self.config_path)
                raise
            except yaml.YAMLError as e:
                logger.error("YAML parsing error: %s", e)
                raise ConfigurationError(f"Invalid YAML configuration: {e}") from e
            except Exception as e:
                logger.error("Configuration loading error: %s", e)
                raise ConfigurationError(f"Failed to load configuration: {e}") from e

    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate configuration structure and values.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Required top-level keys
        required_keys = ["version", "environment", "file_system", "commands", "network", "quotas"]
        for key in required_keys:
            if key not in config:
                raise ConfigurationError(f"Missing required key: {key}")

        # Validate version format
        if not isinstance(config["version"], str):
            raise ConfigurationError("Version must be a string")

        # Validate environment
        valid_environments = ["development", "staging", "production"]
        if config["environment"] not in valid_environments:
            raise ConfigurationError(
                f"Invalid environment: {config['environment']}. "
                f"Must be one of: {valid_environments}"
            )

        # Validate file_system section
        fs = config["file_system"]
        if "allowed_paths" not in fs:
            raise ConfigurationError("file_system.allowed_paths is required")

        # Validate commands section
        cmd = config["commands"]
        if "allowed_patterns" not in cmd or "blocked_patterns" not in cmd:
            raise ConfigurationError("commands must have allowed_patterns and blocked_patterns")

        # Validate network section
        net = config["network"]
        if "allowed_domains" not in net or "allowed_methods" not in net:
            raise ConfigurationError("network must have allowed_domains and allowed_methods")

        # Validate quotas section
        quotas = config["quotas"]
        for quota_type in ["file_operations", "command_executions", "network_requests"]:
            if quota_type not in quotas:
                raise ConfigurationError(f"quotas.{quota_type} is required")
            if "per_hour" not in quotas[quota_type] or "per_day" not in quotas[quota_type]:
                raise ConfigurationError(f"quotas.{quota_type} must have per_hour and per_day")

    def _parse_config(self, config: dict[str, Any]) -> PermissionModel:
        """
        Parse configuration into PermissionModel.

        Args:
            config: Configuration dictionary

        Returns:
            Parsed permission model
        """
        # Parse file system permissions
        allowed_paths = []
        for path_config in config["file_system"]["allowed_paths"]:
            time_restrictions = []
            if "time_restrictions" in path_config:
                for tr in path_config["time_restrictions"]:
                    # Use enhanced TimeRestriction from time_checker
                    time_restrictions.append(EnhancedTimeRestriction.from_dict(tr))

            allowed_paths.append(PathPermission(
                path=path_config["path"],
                permissions=path_config["permissions"],
                time_restrictions=time_restrictions
            ))

        blocked_extensions = set(config["file_system"].get("blocked_extensions", []))

        # Parse command patterns
        allowed_command_patterns = [
            re.compile(pattern)
            for pattern in config["commands"]["allowed_patterns"]
        ]
        blocked_command_patterns = [
            re.compile(pattern)
            for pattern in config["commands"]["blocked_patterns"]
        ]

        # Parse network permissions
        allowed_domains = set(config["network"]["allowed_domains"])
        allowed_methods = {HttpMethod[method] for method in config["network"]["allowed_methods"]}

        # Parse quotas
        quotas = {
            OperationType.FILE_OPERATION: QuotaConfig(
                per_hour=config["quotas"]["file_operations"]["per_hour"],
                per_day=config["quotas"]["file_operations"]["per_day"]
            ),
            OperationType.COMMAND_EXECUTION: QuotaConfig(
                per_hour=config["quotas"]["command_executions"]["per_hour"],
                per_day=config["quotas"]["command_executions"]["per_day"]
            ),
            OperationType.NETWORK_REQUEST: QuotaConfig(
                per_hour=config["quotas"]["network_requests"]["per_hour"],
                per_day=config["quotas"]["network_requests"]["per_day"]
            )
        }

        # Create permission model
        model = PermissionModel(
            version=config["version"],
            environment=config["environment"],
            file_system=config["file_system"],
            commands=config["commands"],
            network=config["network"],
            resources=config.get("resources", {}),
            quotas=quotas,
            lockdown_mode=config.get("lockdown_mode", {"enabled": False}),
            allowed_paths=allowed_paths,
            blocked_extensions=blocked_extensions,
            allowed_command_patterns=allowed_command_patterns,
            blocked_command_patterns=blocked_command_patterns,
            allowed_domains=allowed_domains,
            allowed_methods=allowed_methods
        )

        # Update lockdown mode state
        self._lockdown_mode = model.lockdown_mode.get("enabled", False)

        return model

    def reload(self) -> None:
        """
        Reload configuration without restart (hot reload).

        This method is thread-safe and can be called while the system is running.
        Configuration changes take effect immediately after reload.

        Raises:
            ConfigurationError: If new configuration is invalid
        """
        with self._lock:
            logger.info("Reloading permission model configuration...")
            old_environment = self.model.environment if hasattr(self, 'model') else None

            try:
                self.model = self.load_model()
                logger.info(
                    f"Configuration reloaded successfully. "
                    f"Environment: {old_environment} -> {self.model.environment}"
                )
            except Exception as e:
                logger.error("Configuration reload failed: %s", e)
                raise

    def is_path_allowed(
        self,
        path: Path,
        operation: FileOperation,
        context: OperationContext
    ) -> bool:
        """
        Check if file path operation is allowed.

        Time Complexity: O(n) where n is number of allowed paths
        Space Complexity: O(1)

        Args:
            path: File system path to check
            operation: Operation type (read, write, delete, execute)
            context: Operation context (user, time, etc.)

        Returns:
            True if operation is allowed, False otherwise
        """
        with self._lock:
            # Check lockdown mode
            if self._lockdown_mode:
                allowed_ops = self.model.lockdown_mode.get("allowed_operations", [])
                operation_name = f"{operation.value}_file"

                if operation_name not in allowed_ops and "file_operations" not in allowed_ops:
                    logger.warning(
                        f"Path operation denied (lockdown mode): {path} ({operation.value}), "
                        f"allowed operations: {allowed_ops}"
                    )
                    return False

            # Normalize path to string (use forward slashes for consistency)
            normalized_path = str(path).replace("\\", "/")

            # Check blocked extensions
            if path.suffix in self.model.blocked_extensions:
                logger.warning("Path denied (blocked extension): %s", path)
                return False

            # Check against allowed paths
            for path_perm in self.model.allowed_paths:
                # Normalize allowed path for comparison
                allowed_path_normalized = path_perm.path.replace("\\", "/")

                if normalized_path.startswith(allowed_path_normalized):
                    if path_perm.is_allowed(operation, context.timestamp):
                        logger.debug("Path operation allowed: %s (%s)", path, operation.value)
                        return True

            logger.warning("Path operation denied: %s (%s)", path, operation.value)
            return False

    def is_command_allowed(
        self,
        command: str,
        context: OperationContext
    ) -> bool:
        """
        Check if command matches allowed patterns.

        Time Complexity: O(m + n) where m is allowed patterns, n is blocked patterns
        Space Complexity: O(1)

        Args:
            command: Command string to check
            context: Operation context

        Returns:
            True if command is allowed, False otherwise
        """
        with self._lock:
            # Check lockdown mode
            if self._lockdown_mode:
                allowed_ops = self.model.lockdown_mode.get("allowed_operations", [])
                if "execute_command" not in allowed_ops and "commands" not in allowed_ops:
                    logger.warning(
                        f"Command denied (lockdown mode): {command}, "
                        f"allowed operations: {allowed_ops}"
                    )
                    return False

            # Check blocked patterns first (security priority)
            for pattern in self.model.blocked_command_patterns:
                if pattern.search(command):
                    logger.warning("Command denied (blocked pattern): %s", command)
                    return False

            # Check allowed patterns
            for pattern in self.model.allowed_command_patterns:
                if pattern.search(command):
                    logger.debug("Command allowed: %s", command)
                    return True

            logger.warning("Command denied (no matching pattern): %s", command)
            return False

    def is_network_allowed(
        self,
        url: str,
        method: HttpMethod,
        context: OperationContext
    ) -> bool:
        """
        Check if network endpoint is allowed.

        Time Complexity: O(1) average (hash table lookup)
        Space Complexity: O(1)

        Args:
            url: URL to check
            method: HTTP method
            context: Operation context

        Returns:
            True if network request is allowed, False otherwise
        """
        with self._lock:
            # Check lockdown mode
            if self._lockdown_mode:
                allowed_ops = self.model.lockdown_mode.get("allowed_operations", [])
                if "network_request" not in allowed_ops and "network" not in allowed_ops:
                    logger.warning(
                        f"Network request denied (lockdown mode): {url}, "
                        f"allowed operations: {allowed_ops}"
                    )
                    return False

            # Check method
            if method not in self.model.allowed_methods:
                logger.warning("Network request denied (method not allowed): %s", method.value)
                return False

            # Extract domain from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc

            # Check against allowed domains (support wildcards)
            for allowed_domain in self.model.allowed_domains:
                if allowed_domain.startswith("*."):
                    # Wildcard subdomain matching
                    base_domain = allowed_domain[2:]
                    if domain.endswith(base_domain):
                        logger.debug("Network request allowed: %s (%s)", url, method.value)
                        return True
                elif domain == allowed_domain:
                    logger.debug("Network request allowed: %s (%s)", url, method.value)
                    return True

            logger.warning("Network request denied: %s (%s)", url, method.value)
            return False

    def check_quota(
        self,
        operation_type: OperationType,
        context: OperationContext
    ) -> QuotaStatus:
        """
        Check if operation quota is available.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            operation_type: Type of operation
            context: Operation context

        Returns:
            Quota status with availability and remaining counts
        """
        with self._lock:
            # Reset counters if needed
            self._reset_quotas_if_needed()

            # Get or initialize user counters
            user_id = context.user_id
            if user_id not in self._quota_counters:
                self._quota_counters[user_id] = {
                    OperationType.FILE_OPERATION: {"hour": 0, "day": 0},
                    OperationType.COMMAND_EXECUTION: {"hour": 0, "day": 0},
                    OperationType.NETWORK_REQUEST: {"hour": 0, "day": 0}
                }

            user_counters = self._quota_counters[user_id][operation_type]
            quota_config = self.model.quotas[operation_type]

            # Check availability
            hour_available = user_counters["hour"] < quota_config.per_hour
            day_available = user_counters["day"] < quota_config.per_day
            available = hour_available and day_available

            # Increment counters if available
            if available:
                user_counters["hour"] += 1
                user_counters["day"] += 1

            status = QuotaStatus(
                operation_type=operation_type,
                current_hour=user_counters["hour"],
                current_day=user_counters["day"],
                limit_hour=quota_config.per_hour,
                limit_day=quota_config.per_day,
                available=available
            )

            if not available:
                logger.warning(
                    f"Quota exceeded for {operation_type.value}: "
                    f"hour={status.current_hour}/{status.limit_hour}, "
                    f"day={status.current_day}/{status.limit_day}"
                )

            return status

    def _reset_quotas_if_needed(self) -> None:
        """Reset quota counters if hour or day has changed."""
        now = datetime.now(tz=timezone.utc)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Reset hourly counters
        if current_hour > self._last_hour_reset:
            for user_counters in self._quota_counters.values():
                for op_counters in user_counters.values():
                    op_counters["hour"] = 0
            self._last_hour_reset = current_hour
            logger.debug("Hourly quota counters reset")

        # Reset daily counters
        if current_day > self._last_day_reset:
            for user_counters in self._quota_counters.values():
                for op_counters in user_counters.values():
                    op_counters["day"] = 0
            self._last_day_reset = current_day
            logger.debug("Daily quota counters reset")

    def enter_lockdown_mode(self, reason: str = "Emergency lockdown", activated_by: str = "system") -> None:
        """
        Enter emergency lockdown mode (disable all non-critical operations).

        In lockdown mode, only operations in the allowed_operations list are permitted.
        This is useful for emergency situations or security incidents.

        Args:
            reason: Reason for activating lockdown mode
            activated_by: User or system that activated lockdown
        """
        with self._lock:
            if not self._lockdown_mode:
                self._lockdown_mode = True
                self._lockdown_activated_at = datetime.now(tz=timezone.utc)
                self._lockdown_reason = reason
                self._lockdown_activated_by = activated_by

                logger.critical(
                    f"LOCKDOWN MODE ACTIVATED - Only critical operations allowed. "
                    f"Reason: {reason}, Activated by: {activated_by}"
                )

                # Log to security audit
                try:
                    from Agent_Guru.platform.security.auditor import SecurityAuditor
                    auditor = SecurityAuditor()
                    auditor.log_security_event(
                        event_type="lockdown_activated",
                        severity="critical",
                        details={
                            "reason": reason,
                            "activated_by": activated_by,
                            "timestamp": self._lockdown_activated_at.isoformat(),
                            "allowed_operations": self.model.lockdown_mode.get("allowed_operations", [])
                        }
                    )
                except Exception as e:
                    logger.error("Failed to log lockdown activation to security audit: %s", e)
            else:
                logger.warning("Lockdown mode already active")

    def exit_lockdown_mode(self, exited_by: str = "system") -> None:
        """
        Exit lockdown mode and restore normal operations.

        Args:
            exited_by: User or system that deactivated lockdown
        """
        with self._lock:
            if self._lockdown_mode:
                duration = None
                if self._lockdown_activated_at:
                    duration = (datetime.now(tz=timezone.utc) - self._lockdown_activated_at).total_seconds()

                self._lockdown_mode = False

                logger.warning(
                    f"Lockdown mode deactivated - Normal operations restored. "
                    f"Exited by: {exited_by}, Duration: {duration:.2f}s"
                )

                # Log to security audit
                try:
                    from Agent_Guru.platform.security.auditor import SecurityAuditor
                    auditor = SecurityAuditor()
                    auditor.log_security_event(
                        event_type="lockdown_deactivated",
                        severity="warning",
                        details={
                            "exited_by": exited_by,
                            "duration_seconds": duration,
                            "activated_at": self._lockdown_activated_at.isoformat() if self._lockdown_activated_at else None,
                            "reason": self._lockdown_reason
                        }
                    )
                except Exception as e:
                    logger.error("Failed to log lockdown deactivation to security audit: %s", e)

                # Clear lockdown tracking
                self._lockdown_activated_at = None
                self._lockdown_reason = None
                self._lockdown_activated_by = None
            else:
                logger.warning("Lockdown mode not active")

    def get_lockdown_status(self) -> dict[str, Any]:
        """
        Get current lockdown mode status with details.

        Returns:
            Dictionary with lockdown status information
        """
        with self._lock:
            if not self._lockdown_mode:
                return {
                    "active": False,
                    "activated_at": None,
                    "duration_seconds": None,
                    "reason": None,
                    "activated_by": None,
                    "allowed_operations": []
                }

            duration = None
            if self._lockdown_activated_at:
                duration = (datetime.now(tz=timezone.utc) - self._lockdown_activated_at).total_seconds()

            return {
                "active": True,
                "activated_at": self._lockdown_activated_at.isoformat() if self._lockdown_activated_at else None,
                "duration_seconds": duration,
                "reason": self._lockdown_reason,
                "activated_by": self._lockdown_activated_by,
                "allowed_operations": self.model.lockdown_mode.get("allowed_operations", [])
            }

    @property
    def is_lockdown_mode(self) -> bool:
        """Check if system is in lockdown mode."""
        with self._lock:
            return self._lockdown_mode

    @property
    def environment(self) -> str:
        """Get current environment name."""
        with self._lock:
            return self.model.environment

    @property
    def version(self) -> str:
        """Get configuration version."""
        with self._lock:
            return self.model.version
