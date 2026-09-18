"""Permission manager for skill permissions with user consent.

Manages permission requests, grants, revocations, and trust levels for skills.
"""

import logging

_logger = logging.getLogger(__name__)

import asyncio  # noqa: E402
import json  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from Agent_Guru.reasoning.models.skill import (  # noqa: E402
    Permission,
    TrustLevel,
)


class PermissionRequest:
    """Permission request data."""

    def __init__(
        self,
        skill_id: str,
        permission: Permission,
        reason: str,
        timestamp: datetime,
    ) -> None:
        """Initialize permission request.

        Args:
            skill_id: Skill requesting permission
            permission: Permission being requested
            reason: Reason for permission request
            timestamp: Request timestamp

        """
        self.skill_id = skill_id
        self.permission = permission
        self.reason = reason
        self.timestamp = timestamp


class PermissionManager:
    """Manager for skill permissions with user consent."""

    # Permission descriptions for user display
    PERMISSION_DESCRIPTIONS = {
        Permission.NETWORK_ACCESS: "Access the internet and make network requests",
        Permission.FILE_READ: "Read files from your device",
        Permission.FILE_WRITE: "Write and modify files on your device",
        Permission.LOCATION_ACCESS: "Access your location information",
        Permission.CALENDAR_ACCESS: "Read and modify your calendar events",
        Permission.CONTACTS_ACCESS: "Access your contacts",
        Permission.SYSTEM_CONTROL: "Control system settings (volume, brightness, etc.)",
    }

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize permission manager.

        Args:
            storage_path: Path to persist permission data

        """
        self.storage_path = storage_path
        self._permissions: dict[str, set[Permission]] = {}  # skill_id -> permissions
        self._trust_levels: dict[str, TrustLevel] = {}  # skill_id -> trust_level
        self._permission_history: list[dict] = []  # Audit trail
        self._lock = asyncio.Lock()

        # Load persisted data if available
        if storage_path and storage_path.exists():
            self._load_from_storage()

    async def request_permission(
        self,
        skill_id: str,
        permission: Permission,
        reason: str,
        auto_grant: bool = False,
    ) -> bool:
        """Request a permission for a skill.

        This is the first-use permission request flow. The user will be
        prompted to grant or deny the permission.

        Args:
            skill_id: Skill ID requesting permission
            permission: Permission being requested
            reason: Reason for permission request
            auto_grant: Auto-grant for trusted skills

        Returns:
            True if permission granted, False otherwise

        """
        async with self._lock:
            # Check if already granted
            if self.check_permission(skill_id, permission):
                return True

            # Check trust level
            trust_level = self.get_trust_level(skill_id)

            # Auto-grant for trusted skills
            if trust_level == TrustLevel.TRUSTED and auto_grant:
                # CONCURRENCY FIX (Round 14): this used to call
                # `await self.grant_permission(...)` right here -- but this
                # whole method body runs inside `async with self._lock:`
                # above, and grant_permission() itself does `async with
                # self._lock:` too. asyncio.Lock is NOT reentrant, so the
                # second acquire attempt would block forever waiting for a
                # lock this same coroutine already holds -- a real deadlock,
                # confirmed by executing this exact path in a regression
                # test (it hung indefinitely until killed). Every TRUSTED
                # skill's very first auto-granted permission request hung
                # the caller permanently. Fixed by inlining the grant logic
                # via the lock-free helper (also used by grant_permission()
                # itself under its own lock) instead of recursively
                # re-entering the lock.
                await self._grant_permission_unlocked(skill_id, permission)
                await self._persist()
                self._log_permission_event(skill_id, permission, "auto_granted", reason)
                return True

            # Block for blocked skills
            if trust_level == TrustLevel.BLOCKED:
                self._log_permission_event(skill_id, permission, "denied_blocked", reason)
                return False

            # Create permission request
            PermissionRequest(
                skill_id=skill_id,
                permission=permission,
                reason=reason,
                timestamp=datetime.now(tz=UTC),
            )

            # SECURITY FIX (Round 14): this used to read
            # `user_approved = trust_level == TrustLevel.RESTRICTED`, with a
            # comment admitting it was "simulating user approval" because no
            # real UI consent prompt exists yet. RESTRICTED is this
            # subsystem's *default* trust level (see get_trust_level()) --
            # every never-vetted, newly-installed skill starts there. So in
            # practice this line auto-granted every permission any
            # unconfigured skill asked for, to every skill, unconditionally,
            # with no human ever consulted. That is not a missing feature
            # with a conservative fallback -- it is a fabricated approval
            # that silently defeats the entire point of having a permission
            # system. A skill request that genuinely requires interactive
            # user consent must fail closed (denied) until a real consent
            # channel exists, never fail open. Auto-approval remains
            # available through the legitimate path above (TRUSTED trust
            # level with the caller passing auto_grant=True), and an
            # operator can still grant_permission()/set_trust_level()
            # explicitly through the manual API -- neither of those is
            # affected by this fix.
            self._log_permission_event(skill_id, permission, "denied_no_consent_channel", reason)
            return False

    async def grant_permission(self, skill_id: str, permission: Permission) -> None:
        """Grant a permission to a skill.

        Args:
            skill_id: Skill ID
            permission: Permission to grant

        """
        async with self._lock:
            await self._grant_permission_unlocked(skill_id, permission)
            self._log_permission_event(skill_id, permission, "granted", "Manual grant")

            # Persist changes
            await self._persist()

    async def _grant_permission_unlocked(self, skill_id: str, permission: Permission) -> None:
        """Core grant-permission bookkeeping, assuming `self._lock` is
        already held by the caller.

        Extracted so `request_permission()`'s TRUSTED+auto_grant path can
        perform the same bookkeeping without recursively re-entering
        `self._lock` (see the deadlock fix note in `request_permission()`).
        """
        if skill_id not in self._permissions:
            self._permissions[skill_id] = set()

        self._permissions[skill_id].add(permission)

    async def revoke_permission(self, skill_id: str, permission: Permission) -> None:
        """Revoke a permission from a skill.

        Args:
            skill_id: Skill ID
            permission: Permission to revoke

        """
        async with self._lock:
            if skill_id in self._permissions:
                self._permissions[skill_id].discard(permission)
                self._log_permission_event(skill_id, permission, "revoked", "Manual revocation")

                # Persist changes
                await self._persist()

    def check_permission(self, skill_id: str, permission: Permission) -> bool:
        """Check if a skill has a permission.

        Args:
            skill_id: Skill ID
            permission: Permission to check

        Returns:
            True if permission is granted

        """
        return skill_id in self._permissions and permission in self._permissions[skill_id]

    def get_granted_permissions(self, skill_id: str) -> list[Permission]:
        """Get all granted permissions for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            List of granted permissions

        """
        return list(self._permissions.get(skill_id, set()))

    async def set_trust_level(self, skill_id: str, trust_level: TrustLevel) -> None:
        """Set trust level for a skill.

        Args:
            skill_id: Skill ID
            trust_level: Trust level to set

        """
        async with self._lock:
            old_level = self._trust_levels.get(skill_id, TrustLevel.RESTRICTED)
            self._trust_levels[skill_id] = trust_level

            self._log_trust_event(skill_id, old_level, trust_level)

            # If setting to BLOCKED, revoke all permissions
            if trust_level == TrustLevel.BLOCKED and skill_id in self._permissions:
                self._permissions[skill_id].clear()

            # Persist changes
            await self._persist()

    def get_trust_level(self, skill_id: str) -> TrustLevel:
        """Get trust level for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            Trust level (default: RESTRICTED)

        """
        return self._trust_levels.get(skill_id, TrustLevel.RESTRICTED)

    def get_permission_description(self, permission: Permission) -> str:
        """Get user-friendly description of a permission.

        Args:
            permission: Permission

        Returns:
            Description string

        """
        return self.PERMISSION_DESCRIPTIONS.get(permission, "Unknown permission")

    def get_permission_history(self, skill_id: str | None = None, limit: int = 100) -> list[dict]:
        """Get permission history (audit trail).

        Args:
            skill_id: Filter by skill ID (optional)
            limit: Maximum number of entries to return

        Returns:
            List of permission events

        """
        history = self._permission_history

        if skill_id:
            history = [e for e in history if e.get("skill_id") == skill_id]

        return history[-limit:]

    def _log_permission_event(
        self,
        skill_id: str,
        permission: Permission,
        action: str,
        reason: str,
    ) -> None:
        """Log a permission event to audit trail.

        Args:
            skill_id: Skill ID
            permission: Permission
            action: Action taken (granted, denied, revoked, etc.)
            reason: Reason for action

        """
        event = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "skill_id": skill_id,
            "permission": permission.value,
            "action": action,
            "reason": reason,
        }
        self._permission_history.append(event)

        # Keep only last 10000 events
        if len(self._permission_history) > 10000:
            self._permission_history = self._permission_history[-10000:]

    def _log_trust_event(self, skill_id: str, old_level: TrustLevel, new_level: TrustLevel) -> None:
        """Log a trust level change event.

        Args:
            skill_id: Skill ID
            old_level: Old trust level
            new_level: New trust level

        """
        event = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "skill_id": skill_id,
            "event_type": "trust_level_change",
            "old_level": old_level.value,
            "new_level": new_level.value,
        }
        self._permission_history.append(event)

    async def _persist(self) -> None:
        """Persist permission data to storage."""
        if not self.storage_path:
            return

        data = {
            "permissions": {
                skill_id: [p.value for p in perms] for skill_id, perms in self._permissions.items()
            },
            "trust_levels": {
                skill_id: level.value for skill_id, level in self._trust_levels.items()
            },
            "history": self._permission_history[-1000:],  # Keep last 1000 events
        }

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            json.dump(data, f, indent=2)

    def _load_from_storage(self) -> None:
        """Load permission data from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)

            # Load permissions
            self._permissions = {
                skill_id: {Permission(p) for p in perms}
                for skill_id, perms in data.get("permissions", {}).items()
            }

            # Load trust levels
            self._trust_levels = {
                skill_id: TrustLevel(level)
                for skill_id, level in data.get("trust_levels", {}).items()
            }

            # Load history
            self._permission_history = data.get("history", [])

        except Exception as e:
            _logger.warning("Failed to load permission data: %s", e)
            # Start with empty state on error
            self._permissions = {}
            self._trust_levels = {}
            self._permission_history = []


# Global permission manager instance
_global_manager: PermissionManager | None = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance.

    Returns:
        Global PermissionManager instance

    """
    global _global_manager
    if _global_manager is None:
        _global_manager = PermissionManager()
    return _global_manager
