"""Safety gate for action validation."""

import time
from dataclasses import dataclass
from typing import Any

import structlog

from Agent_Guru.reasoning.models.action import ActionSensitivity, Tool
from Agent_Guru.reasoning.safety.classifier import ActionSensitivityClassifier
from Agent_Guru.reasoning.safety.permissions import PermissionManager

logger = structlog.get_logger(__name__)


@dataclass
class SafetyDecision:
    """Result of safety validation.

    Attributes:
        allowed: Whether action is allowed to execute
        requires_confirmation: Whether user confirmation is required
        reason: Human-readable reason for decision
        sensitivity: Classified sensitivity level
        validation_time: Time taken for validation in seconds

    """

    allowed: bool
    requires_confirmation: bool
    reason: str
    sensitivity: ActionSensitivity
    validation_time: float


class SafetyGate:
    """Safety gate for validating actions before execution.

    The safety gate classifies actions by sensitivity and enforces
    confirmation requirements and permission checks.

    Time Complexity: O(1) for permission checks + O(n) for classification
    Space Complexity: O(m) where m is number of users with permissions
    """

    def __init__(
        self,
        classifier: ActionSensitivityClassifier | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        """Initialize safety gate.

        Args:
            classifier: Action sensitivity classifier (creates default if None)
            permission_manager: Permission manager (creates default if None)

        """
        self._classifier = classifier or ActionSensitivityClassifier()
        self._permission_manager = permission_manager or PermissionManager()

        # Blocked actions log: list of (timestamp, user_id, tool_id, reason)
        self._blocked_actions: list[tuple[float, str, str, str]] = []

        # Sensitive categories that always require confirmation
        self._sensitive_categories: set[str] = {
            "file_deletion",
            "financial",
            "system_config",
            "external_communication",
            "smart_home",
            "data_export",
        }

    def validate_action(
        self,
        tool: Tool,
        parameters: dict[str, Any],
        user_id: str,
    ) -> SafetyDecision:
        """Validate action before execution.

        Time Complexity: O(n) where n is number of classification rules
        Space Complexity: O(1)

        Args:
            tool: Tool to validate
            parameters: Tool parameters
            user_id: User requesting action

        Returns:
            SafetyDecision with validation result

        """
        start_time = time.perf_counter()

        # Classify action sensitivity
        sensitivity, reason = self._classifier.classify(tool, parameters)

        # Check permissions if tool requires them
        if tool.requires_permission and not self.check_permissions(user_id, tool):
            validation_time = time.perf_counter() - start_time

            # Log blocked action
            self._log_blocked_action(user_id, tool.tool_id, "Insufficient permissions")

            logger.warning(
                "action_blocked_insufficient_permissions",
                user_id=user_id,
                tool_id=tool.tool_id,
                permission_scope=tool.permission_scope,
                validation_time=validation_time,
            )

            return SafetyDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"Insufficient permissions: {tool.permission_scope} required",
                sensitivity=sensitivity,
                validation_time=validation_time,
            )

        # Dangerous actions are blocked by default unless user has explicit permission
        if sensitivity == ActionSensitivity.DANGEROUS:
            # For dangerous actions, we need explicit permission even if tool doesn't require it
            # Check if tool has permission requirement OR if it's dangerous
            has_explicit_permission = False
            if tool.requires_permission and tool.permission_scope:
                has_explicit_permission = self.check_permissions(user_id, tool)

            if not has_explicit_permission:
                validation_time = time.perf_counter() - start_time

                # Log blocked action
                self._log_blocked_action(
                    user_id,
                    tool.tool_id,
                    "Dangerous action without permission",
                )

                logger.warning(
                    "action_blocked_dangerous",
                    user_id=user_id,
                    tool_id=tool.tool_id,
                    reason=reason,
                    validation_time=validation_time,
                )

                return SafetyDecision(
                    allowed=False,
                    requires_confirmation=False,
                    reason=f"Dangerous action blocked: {reason}",
                    sensitivity=sensitivity,
                    validation_time=validation_time,
                )

        # Determine if confirmation is required
        requires_confirmation = self._requires_confirmation(sensitivity, tool)

        validation_time = time.perf_counter() - start_time

        # Log validation decision
        logger.info(
            "action_validated",
            user_id=user_id,
            tool_id=tool.tool_id,
            sensitivity=sensitivity.value,
            requires_confirmation=requires_confirmation,
            validation_time=validation_time,
        )

        return SafetyDecision(
            allowed=True,
            requires_confirmation=requires_confirmation,
            reason=reason,
            sensitivity=sensitivity,
            validation_time=validation_time,
        )

    def _requires_confirmation(
        self,
        sensitivity: ActionSensitivity,
        tool: Tool,
    ) -> bool:
        """Determine if action requires user confirmation.

        Args:
            sensitivity: Classified sensitivity level
            tool: Tool being validated

        Returns:
            True if confirmation required, False otherwise

        """
        # Sensitive and dangerous actions require confirmation
        if sensitivity in (ActionSensitivity.SENSITIVE, ActionSensitivity.DANGEROUS):
            return True

        # Check if tool's permission scope is in sensitive categories
        return bool(tool.permission_scope and tool.permission_scope in self._sensitive_categories)

    def check_permissions(self, user_id: str, tool: Tool) -> bool:
        """Check if user has required permissions for tool.

        Time Complexity: O(1) average case (cached lookup)
        Space Complexity: O(1)

        Args:
            user_id: User identifier
            tool: Tool to check permissions for

        Returns:
            True if user has required permissions, False otherwise

        """
        # If tool doesn't require permissions, allow
        if not tool.requires_permission or not tool.permission_scope:
            return True

        # Check if user has the required permission scope using PermissionManager
        return self._permission_manager.check_permission(user_id, tool.permission_scope)

    def grant_permission(
        self,
        user_id: str,
        permission_scope: str,
        granted_by: str = "system",
        expires_at: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Grant permission to user.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User identifier
            permission_scope: Permission scope to grant
            granted_by: Who granted the permission
            expires_at: Optional expiration timestamp (Unix timestamp)
            metadata: Optional metadata dictionary

        """
        self._permission_manager.grant_permission(
            user_id=user_id,
            permission_scope=permission_scope,
            granted_by=granted_by,
            expires_at=expires_at,
            metadata=metadata,
        )

        logger.info(
            "permission_granted",
            user_id=user_id,
            permission_scope=permission_scope,
            granted_by=granted_by,
        )

    def revoke_permission(self, user_id: str, permission_scope: str) -> bool:
        """Revoke permission from user.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User identifier
            permission_scope: Permission scope to revoke

        Returns:
            True if permission was revoked, False if user didn't have it

        """
        result = self._permission_manager.revoke_permission(user_id, permission_scope)

        if result:
            logger.info(
                "permission_revoked",
                user_id=user_id,
                permission_scope=permission_scope,
            )

        return result

    def get_user_permissions(self, user_id: str) -> set[str]:
        """Get all permissions for user.

        Args:
            user_id: User identifier

        Returns:
            Set of permission scopes

        """
        permissions = self._permission_manager.get_user_permissions(user_id)
        return {perm.permission_scope for perm in permissions}

    def add_sensitive_category(self, category: str) -> None:
        """Add a sensitive action category.

        Args:
            category: Category name to add

        """
        self._sensitive_categories.add(category)

        logger.info(
            "sensitive_category_added",
            category=category,
        )

    def remove_sensitive_category(self, category: str) -> bool:
        """Remove a sensitive action category.

        Args:
            category: Category name to remove

        Returns:
            True if category was removed, False if not found

        """
        if category in self._sensitive_categories:
            self._sensitive_categories.remove(category)

            logger.info(
                "sensitive_category_removed",
                category=category,
            )

            return True

        return False

    def get_sensitive_categories(self) -> set[str]:
        """Get all sensitive action categories.

        Returns:
            Set of category names

        """
        return self._sensitive_categories.copy()

    def _log_blocked_action(
        self,
        user_id: str,
        tool_id: str,
        reason: str,
    ) -> None:
        """Log a blocked action for audit.

        Args:
            user_id: User identifier
            tool_id: Tool identifier
            reason: Reason for blocking

        """
        timestamp = time.time()
        self._blocked_actions.append((timestamp, user_id, tool_id, reason))

        # Keep only last 1000 blocked actions
        if len(self._blocked_actions) > 1000:  # noqa: PLR2004 - Percentage/large threshold

            self._blocked_actions = self._blocked_actions[-1000:]

    def get_blocked_actions(
        self,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[tuple[float, str, str, str]]:
        """Get blocked actions log.

        Args:
            user_id: Filter by user ID (None for all users)
            limit: Maximum number of entries to return

        Returns:
            List of (timestamp, user_id, tool_id, reason) tuples

        """
        if user_id:
            filtered = [entry for entry in self._blocked_actions if entry[1] == user_id]
            return filtered[-limit:]

        return self._blocked_actions[-limit:]

    def clear_blocked_actions_log(self) -> None:
        """Clear the blocked actions log."""
        self._blocked_actions.clear()
        logger.info("blocked_actions_log_cleared")
