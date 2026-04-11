"""Mobile application controller for Agent Guru.

Provides async application lifecycle management (open, close) on Android
and iOS mobile platforms.

Platform support:
    - Android: adb shell am start/force-stop (graceful fallback if adb unavailable)
    - iOS:     xcrun simctl openurl for simulators (graceful fallback if xcrun unavailable)

Design Decisions:
    - All public methods are async (asyncio.create_subprocess_exec for I/O)
    - Returns True on success, False on failure — never raises for normal failures
    - Fuzzy app name matching: case-insensitive, partial match against known app map
    - Raises RuntimeError only on desktop platforms (windows/macos/linux) where
      mobile control is not applicable

Performance Characteristics:
    - Time Complexity: O(n) for fuzzy matching where n = number of known apps
    - Space Complexity: O(1) per operation
    - Latency: <2 seconds for app launch (target)

Author: Agent Guru Team
Date: 2026-03-20
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from Agent_Guru.platform.platform_detector import PlatformDetector
from Agent_Guru.platform.utils import fuzzy_match as _fuzzy_match

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform detection (mirrors desktop_app_controller.py)
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


def _is_desktop(plat: str) -> bool:
    """Return True if *plat* is a desktop platform."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile(plat: str) -> bool:
    """Return True if *plat* is a mobile platform."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# App name → package / URL scheme mappings
# ---------------------------------------------------------------------------

# Android: app name → package name
_ANDROID_PACKAGES: dict[str, str] = {
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "gmail": "com.google.android.gm",
    "chrome": "com.android.chrome",
    "google chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "youtube": "com.google.android.youtube",
    "camera": "com.android.camera2",
    "settings": "com.android.settings",
    "phone": "com.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "photos": "com.google.android.apps.photos",
    "drive": "com.google.android.apps.docs",
    "google drive": "com.google.android.apps.docs",
    "spotify": "com.spotify.music",
    "telegram": "org.telegram.messenger",
    "twitter": "com.twitter.android",
    "facebook": "com.facebook.katana",
    "netflix": "com.netflix.mediaclient",
    "slack": "com.Slack",
    "zoom": "us.zoom.videomeetings",
    "tiktok": "com.zhiliaoapp.musically",
    "snapchat": "com.snapchat.android",
    "linkedin": "com.linkedin.android",
}

# Android: package name → default activity (for am start -n)
_ANDROID_ACTIVITIES: dict[str, str] = {
    "com.whatsapp": "com.whatsapp.Main",
    "com.instagram.android": "com.instagram.android.activity.MainTabActivity",
    "com.google.android.gm": "com.google.android.gm.ConversationListActivityGmail",
    "com.android.chrome": "com.google.android.apps.chrome.Main",
    "com.google.android.apps.maps": "com.google.android.maps.MapsActivity",
    "com.google.android.youtube": "com.google.android.youtube.HomeActivity",
    "com.android.settings": "com.android.settings.Settings",
    "com.android.dialer": "com.android.dialer.main.impl.MainActivity",
    "com.google.android.apps.messaging": "com.google.android.apps.messaging.ui.ConversationListActivity",
    "com.google.android.apps.photos": "com.google.android.apps.photos.home.HomeActivity",
    "com.google.android.apps.docs": "com.google.android.apps.docs.app.NewMainProxyActivity",
    "com.spotify.music": "com.spotify.music.MainActivity",
    "org.telegram.messenger": "org.telegram.ui.LaunchActivity",
    "com.twitter.android": "com.twitter.android.StartActivity",
    "com.facebook.katana": "com.facebook.katana.LoginActivity",
    "com.netflix.mediaclient": "com.netflix.mediaclient.ui.launch.UIWebViewActivity",
    "com.Slack": "slack.app.ui.HomeActivity",
    "us.zoom.videomeetings": "us.zoom.videomeetings.MainActivity",
    "com.zhiliaoapp.musically": "com.zhiliaoapp.musically.MainTabActivity",
    "com.snapchat.android": "com.snap.mushroom.MainActivity",
    "com.linkedin.android": "com.linkedin.android.authenticator.LaunchActivity",
}

# iOS: app name → URL scheme
_IOS_URL_SCHEMES: dict[str, str] = {
    "whatsapp": "whatsapp://",
    "instagram": "instagram://",
    "gmail": "googlegmail://",
    "chrome": "googlechrome://",
    "google chrome": "googlechrome://",
    "maps": "maps://",
    "apple maps": "maps://",
    "youtube": "youtube://",
    "camera": "camera://",
    "settings": "app-settings://",
    "phone": "tel://",
    "messages": "sms://",
    "photos": "photos-redirect://",
    "spotify": "spotify://",
    "telegram": "tg://",
    "twitter": "twitter://",
    "facebook": "fb://",
    "netflix": "nflx://",
    "slack": "slack://",
    "zoom": "zoomus://",
    "tiktok": "snssdk1233://",
    "snapchat": "snapchat://",
    "linkedin": "linkedin://",
    "facetime": "facetime://",
    "safari": "x-web-search://",
}


def _resolve_android_package(app_name: str) -> Optional[str]:
    """Resolve an app name to an Android package name via fuzzy matching.

    Args:
        app_name: Human-readable app name.

    Returns:
        Package name string, or ``None`` if no match found.
    """
    for key, package in _ANDROID_PACKAGES.items():
        if _fuzzy_match(app_name, key):
            return package
    return None


def _resolve_ios_scheme(app_name: str) -> Optional[str]:
    """Resolve an app name to an iOS URL scheme via fuzzy matching.

    Args:
        app_name: Human-readable app name.

    Returns:
        URL scheme string (e.g. ``"whatsapp://"``), or ``None`` if no match.
    """
    for key, scheme in _IOS_URL_SCHEMES.items():
        if _fuzzy_match(app_name, key):
            return scheme
    return None


# ---------------------------------------------------------------------------
# MobileApplicationController
# ---------------------------------------------------------------------------

class MobileApplicationController:
    """Async controller for mobile application lifecycle management.

    Supports Android and iOS.  Raises :class:`RuntimeError` when instantiated
    on Windows, macOS, or Linux desktop platforms.

    Example::

        controller = MobileApplicationController()
        await controller.initialize()

        opened = await controller.open_app("WhatsApp")
        closed = await controller.close_app("WhatsApp")
        await controller.shutdown()

    All action methods return ``True`` on success and ``False`` on failure.
    They never raise exceptions for normal operational failures.

    Android implementation:
        Uses ``adb shell am start -n <package>/<activity>`` to open apps and
        ``adb shell am force-stop <package>`` to close them.  If ``adb`` is
        not available the method logs a warning and returns ``False``.

    iOS implementation:
        Uses ``xcrun simctl openurl booted <scheme>`` for simulator targets.
        If ``xcrun`` is not available the method logs a warning and returns
        ``False`` with guidance.
    """

    def __init__(self, platform_override: Optional[str] = None) -> None:
        """Create the controller.

        Args:
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.

        Raises:
            RuntimeError: If the detected platform is a desktop platform
                (``"windows"``, ``"macos"``, ``"linux"``, or ``"unknown"``).
        """
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        if _is_desktop(self._platform):
            raise RuntimeError(
                f"MobileApplicationController is not supported on desktop "
                f"platform '{self._platform}'. Use DesktopApplicationController instead."
            )

        logger.info(
            "MobileApplicationController created — platform=%s", self._platform
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("MobileApplicationController already initialized")
            return

        self._initialized = True
        logger.info(
            "MobileApplicationController initialized — platform=%s", self._platform
        )

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("MobileApplicationController shut down")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def open_app(self, app_name: str) -> bool:
        """Launch an application by name.

        Resolves the human-readable *app_name* to a platform-specific
        identifier (Android package or iOS URL scheme) via fuzzy matching.

        Args:
            app_name: Application name (fuzzy matched, case-insensitive).

        Returns:
            ``True`` if the launch command succeeded, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            logger.warning("open_app called with empty app_name")
            return False

        logger.info("open_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "android":
                return await self._open_android(app_name)
            else:  # ios
                return await self._open_ios(app_name)
        except Exception as exc:
            logger.error("open_app(%r) failed: %s", app_name, exc)
            return False

    async def close_app(self, app_name: str) -> bool:
        """Terminate an application by name.

        Args:
            app_name: Application name (fuzzy matched, case-insensitive).

        Returns:
            ``True`` if the stop command succeeded, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            logger.warning("close_app called with empty app_name")
            return False

        logger.info("close_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "android":
                return await self._close_android(app_name)
            else:  # ios
                return await self._close_ios(app_name)
        except Exception as exc:
            logger.error("close_app(%r) failed: %s", app_name, exc)
            return False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return self._platform

    @property
    def is_initialized(self) -> bool:
        """Whether the controller has been initialized."""
        return self._initialized

    # ------------------------------------------------------------------
    # Android implementations
    # ------------------------------------------------------------------

    async def _open_android(self, app_name: str) -> bool:
        """Launch an app on Android via adb.

        Uses ``adb shell am start -n <package>/<activity>`` when the activity
        is known, otherwise falls back to ``adb shell monkey -p <package> 1``.
        Logs a warning and returns ``False`` if adb is not available.
        """
        if not await self._adb_available():
            logger.warning(
                "adb not available — cannot open %r on Android. "
                "Ensure adb is installed and the device is connected.",
                app_name,
            )
            return False

        package = _resolve_android_package(app_name)
        if package is None:
            logger.warning(
                "open_app: no Android package mapping found for %r", app_name
            )
            return False

        activity = _ANDROID_ACTIVITIES.get(package)
        if activity:
            # Preferred: explicit component start
            try:
                proc = await asyncio.create_subprocess_exec(
                    "adb", "shell", "am", "start", "-n",
                    f"{package}/{activity}",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )  # nosec B603 B607
                await asyncio.wait_for(proc.wait(), timeout=10.0)
                if proc.returncode == 0:
                    logger.info("Opened %r via adb am start -n", app_name)
                    return True
            except Exception as exc:
                logger.debug("adb am start -n failed for %r: %s", app_name, exc)

        # Fallback: monkey launch (works without knowing the activity)
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "shell", "monkey", "-p", package, "1",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Opened %r via adb monkey", app_name)
            else:
                logger.warning("adb monkey failed for package %r", package)
            return success
        except Exception as exc:
            logger.debug("adb monkey failed for %r: %s", app_name, exc)
            return False

    async def _close_android(self, app_name: str) -> bool:
        """Force-stop an app on Android via adb.

        Uses ``adb shell am force-stop <package>``.
        Logs a warning and returns ``False`` if adb is not available.
        """
        if not await self._adb_available():
            logger.warning(
                "adb not available — cannot close %r on Android. "
                "Ensure adb is installed and the device is connected.",
                app_name,
            )
            return False

        package = _resolve_android_package(app_name)
        if package is None:
            logger.warning(
                "close_app: no Android package mapping found for %r", app_name
            )
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "shell", "am", "force-stop", package,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Force-stopped %r (package=%s)", app_name, package)
            else:
                logger.warning(
                    "adb force-stop returned non-zero for %r (package=%s)",
                    app_name, package,
                )
            return success
        except Exception as exc:
            logger.debug("adb force-stop failed for %r: %s", app_name, exc)
            return False

    # ------------------------------------------------------------------
    # iOS implementations
    # ------------------------------------------------------------------

    async def _open_ios(self, app_name: str) -> bool:
        """Open an app on iOS via xcrun simctl URL scheme.

        Uses ``xcrun simctl openurl booted <scheme>`` for simulator targets.
        Logs a warning and returns ``False`` if xcrun is not available.
        """
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available — cannot open %r on iOS. "
                "To open apps on a physical iOS device, use the Shortcuts app "
                "or an MDM solution. For simulators, install Xcode.",
                app_name,
            )
            return False

        scheme = _resolve_ios_scheme(app_name)
        if scheme is None:
            logger.warning(
                "open_app: no iOS URL scheme mapping found for %r", app_name
            )
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun", "simctl", "openurl", "booted", scheme,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Opened %r via xcrun simctl openurl %s", app_name, scheme)
            else:
                logger.warning(
                    "xcrun simctl openurl returned non-zero for %r (scheme=%s)",
                    app_name, scheme,
                )
            return success
        except Exception as exc:
            logger.debug("xcrun simctl openurl failed for %r: %s", app_name, exc)
            return False

    async def _close_ios(self, app_name: str) -> bool:
        """Terminate an app on iOS via xcrun simctl.

        Uses ``xcrun simctl terminate booted <bundle-id>`` for simulator targets.
        iOS URL schemes do not map 1:1 to bundle IDs, so this uses a best-effort
        approach.  Logs a warning and returns ``False`` if xcrun is not available.
        """
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available — cannot close %r on iOS. "
                "To close apps on a physical iOS device, use the Shortcuts app "
                "or an MDM solution. For simulators, install Xcode.",
                app_name,
            )
            return False

        # Map app name to bundle ID for terminate command
        bundle_id = _resolve_ios_bundle_id(app_name)
        if bundle_id is None:
            logger.warning(
                "close_app: no iOS bundle ID mapping found for %r", app_name
            )
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun", "simctl", "terminate", "booted", bundle_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info(
                    "Terminated %r via xcrun simctl terminate (bundle=%s)",
                    app_name, bundle_id,
                )
            else:
                logger.warning(
                    "xcrun simctl terminate returned non-zero for %r (bundle=%s)",
                    app_name, bundle_id,
                )
            return success
        except Exception as exc:
            logger.debug("xcrun simctl terminate failed for %r: %s", app_name, exc)
            return False

    # ------------------------------------------------------------------
    # Availability checks (cached)
    # ------------------------------------------------------------------

    _adb_cache: Optional[bool] = None
    _xcrun_cache: Optional[bool] = None

    async def _adb_available(self) -> bool:
        """Return True if adb is installed and reachable (cached)."""
        if MobileApplicationController._adb_cache is not None:
            return MobileApplicationController._adb_cache

        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception as e:
            result = False

        MobileApplicationController._adb_cache = result
        return result

    async def _xcrun_available(self) -> bool:
        """Return True if xcrun is installed and reachable (cached)."""
        if MobileApplicationController._xcrun_cache is not None:
            return MobileApplicationController._xcrun_cache

        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception as e:
            result = False

        MobileApplicationController._xcrun_cache = result
        return result


# ---------------------------------------------------------------------------
# iOS bundle ID mapping (for terminate command)
# ---------------------------------------------------------------------------

_IOS_BUNDLE_IDS: dict[str, str] = {
    "whatsapp": "net.whatsapp.WhatsApp",
    "instagram": "com.burbn.instagram",
    "gmail": "com.google.Gmail",
    "chrome": "com.google.chrome.ios",
    "google chrome": "com.google.chrome.ios",
    "maps": "com.apple.Maps",
    "apple maps": "com.apple.Maps",
    "youtube": "com.google.ios.youtube",
    "camera": "com.apple.camera",
    "settings": "com.apple.Preferences",
    "phone": "com.apple.mobilephone",
    "messages": "com.apple.MobileSMS",
    "photos": "com.apple.mobileslideshow",
    "spotify": "com.spotify.client",
    "telegram": "ph.telegra.Telegraph",
    "twitter": "com.atebits.Tweetie2",
    "facebook": "com.facebook.Facebook",
    "netflix": "com.netflix.Netflix",
    "slack": "com.tinyspeck.chatlyio",
    "zoom": "us.zoom.videomeetings",
    "tiktok": "com.zhiliaoapp.musically",
    "snapchat": "com.toyopagroup.picaboo",
    "linkedin": "com.linkedin.LinkedIn",
    "facetime": "com.apple.facetime",
    "safari": "com.apple.mobilesafari",
}


def _resolve_ios_bundle_id(app_name: str) -> Optional[str]:
    """Resolve an app name to an iOS bundle ID via fuzzy matching.

    Args:
        app_name: Human-readable app name.

    Returns:
        Bundle ID string, or ``None`` if no match found.
    """
    for key, bundle_id in _IOS_BUNDLE_IDS.items():
        if _fuzzy_match(app_name, key):
            return bundle_id
    return None
