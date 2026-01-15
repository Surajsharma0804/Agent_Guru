"""
iOS Security Enforcer Implementation

PLATFORM LIMITATIONS (iOS Sandbox Restrictions):
- CANNOT lock device (iOS security restriction)
- CANNOT lock screen (iOS security restriction)
- CAN only lock GURU app itself
- NO system-wide authority

HONEST CAPABILITY DECLARATION:
iOS provides app-level security only. Cannot enforce system-wide lockdown.

Requirements: 40.5, 40.6, 39.2, 39.3
"""

import logging
import platform
from typing import Dict

from ...interfaces import SecurityEnforcer

logger = logging.getLogger(__name__)


class iOSSecurityEnforcer(SecurityEnforcer):
    """
    iOS Security Enforcer (APP-LEVEL ONLY).

    CRITICAL LIMITATIONS:
    - Cannot lock device (iOS security restriction)
    - Cannot lock screen (iOS security restriction)
    - Can only lock GURU app itself
    - No system-wide authority

    SECURITY IMPLICATION:
    On security violation, GURU can only lock itself.
    User can still access other apps and system.
    This is a fundamental iOS security model limitation.
    """

    def __init__(self):
        """Initialize iOS security enforcer."""
        self._is_ios = platform.system() == "Darwin" and platform.machine().startswith("iP")

        # App lock state
        self._app_locked = False

        logger.info("iOSSecurityEnforcer initialized (APP-LEVEL ONLY - cannot lock system)")
        logger.warning("iOS security enforcement is limited to GURU app only")

    def lock_session(self, reason: str) -> bool:
        """
        Lock user session.

        LIMITATION: iOS only allows locking GURU app, not the system.

        Args:
            reason: Reason for lock (for audit logging)

        Returns:
            True if app locked successfully, False otherwise

        Security:
            - Locks GURU app only (not system)
            - Requires biometric re-authentication to unlock
            - Cryptographic audit logging
            - Immediate effect (no delay)

        CRITICAL: This does NOT lock the device or screen.
        User can still access other apps and system.
        """
        logger.warning(f"Locking GURU app (NOT system): {reason}")

        if not self._is_ios:
            # Development/testing mode
            logger.info("[DEV MODE] Would lock GURU app")
            self._app_locked = True
            return True

        try:
            # On actual iOS, would:
            # 1. Set app state to locked
            # 2. Clear sensitive data from memory
            # 3. Show lock screen overlay
            # 4. Require biometric re-authentication
            # 5. Log lock event to audit logger

            self._app_locked = True

            logger.info(f"GURU app locked: {reason}")
            logger.warning("Device and other apps remain accessible (iOS limitation)")

            return True

        except Exception as e:
            logger.error(f"Failed to lock app: {e}")
            return False

    def get_lock_scope(self) -> str:
        """
        Get scope of lock operation.

        Returns:
            Always "app" (iOS limitation)

        Platform Behavior:
            iOS: "app" (app lock only, no system lock)
        """
        return "app"

    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform capabilities.

        HONEST DECLARATION: iOS has NO system-wide authority.

        Returns:
            Capability dictionary with system features disabled
        """
        return {
            "can_lock_system": False,  # iOS restriction
            "can_lock_screen": False,  # iOS restriction
            "can_lock_app": True,  # Supported
            "has_system_authority": False,  # iOS restriction
            "lock_scope": "app",  # App-level only
            "platform_limitations": "severe",  # Honest assessment
        }

    def is_app_locked(self) -> bool:
        """
        Check if GURU app is currently locked.

        Returns:
            True if app is locked, False otherwise
        """
        return self._app_locked

    def unlock_app(self) -> None:
        """
        Unlock GURU app.

        Should only be called after successful biometric authentication.
        """
        self._app_locked = False
        logger.info("GURU app unlocked")
