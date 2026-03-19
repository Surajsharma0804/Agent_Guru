"""
Permission manager for skill permissions with user consent.

Manages permission requests, grants, revocations, and trust levels for skills.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from Agent_Guru.reasoning.models.skill import (
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
    ):
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

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize permission manager.

        Args:
            storage_path: Path to persist permission data
        """
        self.storage_path = storage_path
        self._permissions: Dict[str, Set[Permission]] = {}  # skill_id -> permissions
        self._trust_levels: Dict[str, TrustLevel] = {}  # skill_id -> trust_level
        self._permission_history: List[Dict] = []  # Audit trail
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
                await self.grant_permission(skill_id, permission)
                self._log_permission_event(
                    skill_id, permission, "auto_granted", reason
                )
                return True

            # Block for blocked skills
            if trust_level == TrustLevel.BLOCKED:
                self._log_permission_event(skill_id, permission, "denied_blocked", reason)
                return False

            # Create permission request
            request = PermissionRequest(
                skill_id=skill_id,
                permission=permission,
                reason=reason,
                timestamp=datetime.now(),
            )

            # Note: In a real implementation, this would:
            # 1. Show UI prompt to user with permission description
            # 2. Wait for user response
            # 3. Grant or deny based on user choice
            # For now, we'll simulate user approval for restricted skills
            user_approved = trust_level == TrustLevel.RESTRICTED

            if user_approved:
                await self.grant_permission(skill_id, permission)
                self._log_permission_event(skill_id, permission, "granted", reason)
                return True
            else:
                self._log_permission_event(skill_id, permission, "denied", reason)
                return False

    async def grant_permission(
        self, skill_id: str, permission: Permission
    ) -> None:
        """Grant a permission to a skill.

        Args:
            skill_id: Skill ID
            permission: Permission to grant
        """
        async with self._lock:
            if skill_id not in self._permissions:
                self._permissions[skill_id] = set()

            self._permissions[skill_id].add(permission)
            self._log_permission_event(skill_id, permission, "granted", "Manual grant")

            # Persist changes
            await self._persist()

    async def revoke_permission(
        self, skill_id: str, permission: Permission
    ) -> None:
        """Revoke a permission from a skill.

        Args:
            skill_id: Skill ID
            permission: Permission to revoke
        """
        async with self._lock:
            if skill_id in self._permissions:
                self._permissions[skill_id].discard(permission)
                self._log_permission_event(
                    skill_id, permission, "revoked", "Manual revocation"
                )

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
        return (
            skill_id in self._permissions
            and permission in self._permissions[skill_id]
        )

    def get_granted_permissions(self, skill_id: str) -> List[Permission]:
        """Get all granted permissions for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            List of granted permissions
        """
        return list(self._permissions.get(skill_id, set()))

    async def set_trust_level(
        self, skill_id: str, trust_level: TrustLevel
    ) -> None:
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
            if trust_level == TrustLevel.BLOCKED:
                if skill_id in self._permissions:
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
        return self.PERMISSION_DESCRIPTIONS.get(
            permission, "Unknown permission"
        )

    def get_permission_history(
        self, skill_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
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
            "timestamp": datetime.now().isoformat(),
            "skill_id": skill_id,
            "permission": permission.value,
            "action": action,
            "reason": reason,
        }
        self._permission_history.append(event)

        # Keep only last 10000 events
        if len(self._permission_history) > 10000:
            self._permission_history = self._permission_history[-10000:]

    def _log_trust_event(
        self, skill_id: str, old_level: TrustLevel, new_level: TrustLevel
    ) -> None:
        """Log a trust level change event.

        Args:
            skill_id: Skill ID
            old_level: Old trust level
            new_level: New trust level
        """
        event = {
            "timestamp": datetime.now().isoformat(),
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
                skill_id: [p.value for p in perms]
                for skill_id, perms in self._permissions.items()
            },
            "trust_levels": {
                skill_id: level.value
                for skill_id, level in self._trust_levels.items()
            },
            "history": self._permission_history[-1000:],  # Keep last 1000 events
        }

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_from_storage(self) -> None:
        """Load permission data from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
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
            print(f"Failed to load permission data: {e}")
            # Start with empty state on error
            self._permissions = {}
            self._trust_levels = {}
            self._permission_history = []


# Global permission manager instance
_global_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance.

    Returns:
        Global PermissionManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = PermissionManager()
    return _global_manager
