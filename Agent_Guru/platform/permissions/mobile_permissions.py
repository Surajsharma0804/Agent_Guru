"""Mobile Permission Manager - Android and iOS permission handling.

This module provides mobile-specific permission request flows and runtime
permission handling for Android 6.0+ and iOS.

Performance Characteristics:
    - Time Complexity: O(1) for permission checks
    - Space Complexity: O(n) where n is number of permissions
    - Latency: <10ms for checks, variable for user prompts

Architecture:
    The MobilePermissionManager handles runtime permission requests on mobile
    platforms, providing user-friendly explanations and graceful denial handling.

Author: Agent Guru Team
"""

import platform
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class MobilePermission(Enum):
    """Mobile permission types."""

    # Android permissions
    RECORD_AUDIO = "android.permission.RECORD_AUDIO"
    CAMERA = "android.permission.CAMERA"
    READ_EXTERNAL_STORAGE = "android.permission.READ_EXTERNAL_STORAGE"
    WRITE_EXTERNAL_STORAGE = "android.permission.WRITE_EXTERNAL_STORAGE"
    ACCESS_FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
    ACCESS_COARSE_LOCATION = "android.permission.ACCESS_COARSE_LOCATION"
    READ_CONTACTS = "android.permission.READ_CONTACTS"
    WRITE_SETTINGS = "android.permission.WRITE_SETTINGS"
    SYSTEM_ALERT_WINDOW = "android.permission.SYSTEM_ALERT_WINDOW"
    REQUEST_IGNORE_BATTERY_OPTIMIZATIONS = "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"

    # iOS permissions (mapped to Android-style names)
    IOS_MICROPHONE = "ios.permission.MICROPHONE"
    IOS_CAMERA = "ios.permission.CAMERA"
    IOS_PHOTOS = "ios.permission.PHOTOS"
    IOS_LOCATION = "ios.permission.LOCATION"
    IOS_CONTACTS = "ios.permission.CONTACTS"
    IOS_SPEECH_RECOGNITION = "ios.permission.SPEECH_RECOGNITION"


class PermissionStatus(Enum):
    """Permission status states."""

    GRANTED = "granted"
    DENIED = "denied"
    DENIED_PERMANENTLY = "denied_permanently"
    NOT_DETERMINED = "not_determined"


@dataclass
class PermissionRequest:
    """Permission request with explanation.

    Attributes:
        permission: Permission being requested
        rationale: User-friendly explanation of why permission is needed
        required: Whether permission is required for core functionality

    """

    permission: MobilePermission
    rationale: str
    required: bool = True


@dataclass
class PermissionResult:
    """Result of permission request.

    Attributes:
        permission: Permission that was requested
        status: Current status of the permission
        can_request_again: Whether permission can be requested again

    """

    permission: MobilePermission
    status: PermissionStatus
    can_request_again: bool


class MobilePermissionManager:
    """Mobile permission manager for Android and iOS.

    Handles runtime permission requests, status checking, and denial handling
    for mobile platforms.

    Time Complexity: O(1) for permission checks
    Space Complexity: O(n) where n is number of permissions

    Example:
        >>> manager = MobilePermissionManager()
        >>> request = PermissionRequest(
        ...     permission=MobilePermission.RECORD_AUDIO,
        ...     rationale="Agent Guru needs microphone access for voice commands",
        ...     required=True
        ... )
        >>> result = manager.request_permission(request)
        >>> if result.status == PermissionStatus.GRANTED:
        ...     print("Permission granted!")

    """

    def __init__(self) -> None:
        """Initialize mobile permission manager."""
        self._platform = platform.system()
        self._permission_status: dict[MobilePermission, PermissionStatus] = {}
        self._request_callbacks: dict[MobilePermission, Callable] = {}

    def request_permission(self, request: PermissionRequest) -> PermissionResult:
        """Request a mobile permission with user-friendly explanation.

        Time Complexity: O(1)

        Args:
            request: Permission request with rationale

        Returns:
            PermissionResult with current status

        Example:
            >>> manager = MobilePermissionManager()
            >>> request = PermissionRequest(
            ...     permission=MobilePermission.CAMERA,
            ...     rationale="For face recognition authentication"
            ... )
            >>> result = manager.request_permission(request)

        """
        # Check current status
        current_status = self.check_permission_status(request.permission)

        if current_status == PermissionStatus.GRANTED:
            return PermissionResult(
                permission=request.permission,
                status=PermissionStatus.GRANTED,
                can_request_again=False,
            )

        if current_status == PermissionStatus.DENIED_PERMANENTLY:
            return PermissionResult(
                permission=request.permission,
                status=PermissionStatus.DENIED_PERMANENTLY,
                can_request_again=False,
            )

        # Request permission from platform
        if self._platform == "Android":
            return self._request_android_permission(request)
        if self._platform == "iOS":
            return self._request_ios_permission(request)
        # Not on mobile platform
        return PermissionResult(
            permission=request.permission,
            status=PermissionStatus.NOT_DETERMINED,
            can_request_again=False,
        )

    def check_permission_status(self, permission: MobilePermission) -> PermissionStatus:
        """Check current status of a permission.

        Time Complexity: O(1)

        Args:
            permission: Permission to check

        Returns:
            Current permission status

        Example:
            >>> manager = MobilePermissionManager()
            >>> status = manager.check_permission_status(
            ...     MobilePermission.RECORD_AUDIO
            ... )
            >>> if status == PermissionStatus.GRANTED:
            ...     print("Microphone access granted")

        """
        # Check cached status
        if permission in self._permission_status:
            return self._permission_status[permission]

        # Query platform for status
        if self._platform == "Android":
            status = self._check_android_permission(permission)
        elif self._platform == "iOS":
            status = self._check_ios_permission(permission)
        else:
            status = PermissionStatus.NOT_DETERMINED

        # Cache status
        self._permission_status[permission] = status
        return status

    def handle_permission_denial(
        self,
        permission: MobilePermission,
        fallback_action: Callable | None = None,
    ) -> None:
        """Handle permission denial with fallback action.

        Time Complexity: O(1)

        Args:
            permission: Permission that was denied
            fallback_action: Optional fallback action to execute

        Example:
            >>> manager = MobilePermissionManager()
            >>> def fallback():
            ...     print("Using cloud speech recognition instead")
            >>> manager.handle_permission_denial(
            ...     MobilePermission.RECORD_AUDIO,
            ...     fallback_action=fallback
            ... )

        """
        status = self.check_permission_status(permission)

        if status == PermissionStatus.DENIED_PERMANENTLY:
            # Guide user to settings
            self._show_settings_guidance(permission)
        elif status == PermissionStatus.DENIED:
            # Show rationale and allow retry
            self._show_permission_rationale(permission)

        # Execute fallback if provided
        if fallback_action is not None:
            fallback_action()

    def request_multiple_permissions(
        self,
        requests: list[PermissionRequest],
    ) -> dict[MobilePermission, PermissionResult]:
        """Request multiple permissions at once.

        Time Complexity: O(n) where n is number of permissions

        Args:
            requests: List of permission requests

        Returns:
            Dictionary mapping permissions to results

        Example:
            >>> manager = MobilePermissionManager()
            >>> requests = [
            ...     PermissionRequest(
            ...         MobilePermission.RECORD_AUDIO,
            ...         "For voice commands"
            ...     ),
            ...     PermissionRequest(
            ...         MobilePermission.CAMERA,
            ...         "For face recognition"
            ...     )
            ... ]
            >>> results = manager.request_multiple_permissions(requests)

        """
        results = {}

        for request in requests:
            result = self.request_permission(request)
            results[request.permission] = result

        return results

    def get_denied_permissions(self) -> set[MobilePermission]:
        """Get set of currently denied permissions.

        Time Complexity: O(n) where n is number of cached permissions

        Returns:
            Set of denied permissions

        Example:
            >>> manager = MobilePermissionManager()
            >>> denied = manager.get_denied_permissions()
            >>> if MobilePermission.CAMERA in denied:
            ...     print("Camera access denied")

        """
        denied = set()

        for permission, status in self._permission_status.items():
            if status in (PermissionStatus.DENIED, PermissionStatus.DENIED_PERMANENTLY):
                denied.add(permission)

        return denied

    def _request_android_permission(self, request: PermissionRequest) -> PermissionResult:
        """Request Android permission (Android 6.0+).

        Time Complexity: O(1)

        Args:
            request: Permission request

        Returns:
            Permission result

        """
        # This would use Android APIs via pyjnius
        # For now, return mock result
        # TODO: Implement actual Android permission request

        return PermissionResult(
            permission=request.permission,
            status=PermissionStatus.NOT_DETERMINED,
            can_request_again=True,
        )

    def _request_ios_permission(self, request: PermissionRequest) -> PermissionResult:
        """Request iOS permission.

        Time Complexity: O(1)

        Args:
            request: Permission request

        Returns:
            Permission result

        """
        # This would use iOS APIs via pyobjus
        # For now, return mock result
        # TODO: Implement actual iOS permission request

        return PermissionResult(
            permission=request.permission,
            status=PermissionStatus.NOT_DETERMINED,
            can_request_again=True,
        )

    def _check_android_permission(self, permission: MobilePermission) -> PermissionStatus:
        """Check Android permission status.

        Time Complexity: O(1)

        Args:
            permission: Permission to check

        Returns:
            Permission status

        """
        # This would use Android APIs via pyjnius
        # For now, return mock status
        # TODO: Implement actual Android permission check

        return PermissionStatus.NOT_DETERMINED

    def _check_ios_permission(self, permission: MobilePermission) -> PermissionStatus:
        """Check iOS permission status.

        Time Complexity: O(1)

        Args:
            permission: Permission to check

        Returns:
            Permission status

        """
        # This would use iOS APIs via pyobjus
        # For now, return mock status
        # TODO: Implement actual iOS permission check

        return PermissionStatus.NOT_DETERMINED

    def _show_settings_guidance(self, permission: MobilePermission) -> None:
        """Show guidance to enable permission in settings.

        Args:
            permission: Permission that needs to be enabled

        """
        # This would show platform-specific UI
        # TODO: Implement actual settings guidance

    def _show_permission_rationale(self, permission: MobilePermission) -> None:
        """Show rationale for why permission is needed.

        Args:
            permission: Permission to explain

        """
        # This would show platform-specific UI
        # TODO: Implement actual rationale display
