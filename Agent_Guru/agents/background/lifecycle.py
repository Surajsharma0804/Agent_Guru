"""Platform Lifecycle Handler - Handles OS lifecycle events across all platforms.

Translates platform-specific lifecycle events (Android, iOS, Desktop) into
coordinated component responses (sleep/wake/stop).

Performance Characteristics:
    - Time Complexity: O(1) per event dispatch
    - Space Complexity: O(h) where h is number of registered handlers
    - Event latency: <10ms

Validates: Requirement 12.4
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Supported platform types."""

    ANDROID = "android"
    IOS = "ios"
    DESKTOP = "desktop"
    UNKNOWN = "unknown"


class LifecycleEvent(Enum):
    """Normalised lifecycle events across all platforms."""

    # Foreground → Background (enter sleep)
    BACKGROUND = "background"
    # Background → Foreground (enter wake)
    FOREGROUND = "foreground"
    # App is being terminated (stop all)
    TERMINATE = "terminate"
    # App paused (light sleep)
    PAUSE = "pause"
    # App resumed (wake)
    RESUME = "resume"
    # Window minimised (sleep)
    MINIMIZE = "minimize"
    # Window restored (wake)
    RESTORE = "restore"
    # Window closed (stop)
    CLOSE = "close"


# Maps raw platform event strings to normalised LifecycleEvent
_ANDROID_EVENT_MAP: dict[str, LifecycleEvent] = {
    "onPause": LifecycleEvent.PAUSE,
    "onResume": LifecycleEvent.RESUME,
    "onStop": LifecycleEvent.BACKGROUND,
    "onDestroy": LifecycleEvent.TERMINATE,
}

_IOS_EVENT_MAP: dict[str, LifecycleEvent] = {
    "applicationDidEnterBackground": LifecycleEvent.BACKGROUND,
    "didEnterBackground": LifecycleEvent.BACKGROUND,
    "applicationWillEnterForeground": LifecycleEvent.FOREGROUND,
    "willEnterForeground": LifecycleEvent.FOREGROUND,
    "applicationWillTerminate": LifecycleEvent.TERMINATE,
    "willTerminate": LifecycleEvent.TERMINATE,
}

_DESKTOP_EVENT_MAP: dict[str, LifecycleEvent] = {
    "minimize": LifecycleEvent.MINIMIZE,
    "restore": LifecycleEvent.RESTORE,
    "close": LifecycleEvent.CLOSE,
}

# Combined lookup across all platforms
_ALL_EVENT_MAPS: dict[Platform, dict[str, LifecycleEvent]] = {
    Platform.ANDROID: _ANDROID_EVENT_MAP,
    Platform.IOS: _IOS_EVENT_MAP,
    Platform.DESKTOP: _DESKTOP_EVENT_MAP,
}

# Async handler type: (event) -> None
LifecycleHandler = Callable[[LifecycleEvent], Coroutine[Any, Any, None]]


class PlatformLifecycleHandler:
    """Handles platform-specific lifecycle events and coordinates responses.

    Translates raw platform event strings into normalised LifecycleEvent
    values and dispatches them to registered handlers.

    Supported platforms:
    - Android: onPause, onResume, onStop, onDestroy
    - iOS: applicationDidEnterBackground, applicationWillEnterForeground,
           applicationWillTerminate
    - Desktop: minimize, restore, close

    Time Complexity: O(h) per event where h is number of handlers
    Space Complexity: O(h) for handler registry

    Example:
        >>> handler = PlatformLifecycleHandler(platform=Platform.ANDROID)
        >>> handler.register_handler(my_async_handler)
        >>> await handler.handle_event("onPause")

    Validates: Requirement 12.4

    """

    def __init__(self, platform: Platform = Platform.UNKNOWN) -> None:
        """Initialise the lifecycle handler.

        Args:
            platform: The platform this handler is running on.

        """
        self.platform = platform
        self._handlers: list[LifecycleHandler] = []
        # BUG FIX: was an unbounded list -- this handler runs for the
        # entire lifetime of a long-running companion process, and
        # background/foreground/minimize/restore cycles recur
        # constantly, so an unbounded history leaks memory forever
        # (same class already fixed in convergence_analyzer.py,
        # Round 57, and elsewhere). event_history still returns a
        # plain list snapshot -- the public contract is unchanged.
        self._event_history: deque[LifecycleEvent] = deque(maxlen=1000)

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(self, handler: LifecycleHandler) -> None:
        """Register an async handler for lifecycle events.

        Args:
            handler: Async callable(LifecycleEvent) invoked on each event.

        """
        self._handlers.append(handler)

    def unregister_handler(self, handler: LifecycleHandler) -> None:
        """Remove a previously registered handler.

        Args:
            handler: Handler to remove.

        Raises:
            ValueError: If handler is not registered.

        """
        self._handlers.remove(handler)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def handle_event(self, raw_event: str) -> LifecycleEvent | None:
        """Handle a raw platform lifecycle event string.

        Normalises the event and dispatches to all registered handlers.

        Args:
            raw_event: Platform-specific event string (e.g. "onPause").

        Returns:
            The normalised LifecycleEvent, or None if unrecognised.

        Time Complexity: O(h) where h is number of handlers
        Validates: Requirement 12.4

        """
        event = self._normalise_event(raw_event)
        if event is None:
            logger.warning("Unrecognised lifecycle event: '%s'", raw_event)
            return None

        self._event_history.append(event)
        logger.info("Lifecycle event: %s → %s", raw_event, event.value)

        # BUG FIX: was `for handler in self._handlers:` -- iterating
        # the live list directly. If any handler mutates
        # self._handlers during its own await (e.g. a "run once"
        # handler unregistering itself after firing), CPython's list
        # iterator silently skips whichever handler got shifted into
        # the just-vacated index -- a real, silent, hard-to-diagnose
        # failure to deliver an event to a registered handler.
        # Dispatching over a snapshot copy makes registration changes
        # during dispatch never affect this event's delivery.
        for handler in list(self._handlers):
            try:
                await handler(event)
            except Exception as exc:
                logger.exception("Lifecycle handler failed for event '%s': %s", event.value, exc)

        return event

    def _normalise_event(self, raw_event: str) -> LifecycleEvent | None:
        """Map a raw event string to a normalised LifecycleEvent.

        Checks the platform-specific map first, then falls back to
        checking all maps for cross-platform compatibility.

        Args:
            raw_event: Raw platform event string.

        Returns:
            Normalised LifecycleEvent or None if not found.

        Time Complexity: O(1) — dict lookup

        """
        # Try platform-specific map first
        if self.platform in _ALL_EVENT_MAPS:
            event = _ALL_EVENT_MAPS[self.platform].get(raw_event)
            if event:
                return event

        # Fall back to searching all maps
        for event_map in _ALL_EVENT_MAPS.values():
            event = event_map.get(raw_event)
            if event:
                return event

        # Try direct enum value match
        for member in LifecycleEvent:
            if member.value == raw_event.lower():
                return member

        return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def event_history(self) -> list[LifecycleEvent]:
        """Ordered list of all lifecycle events received."""
        return list(self._event_history)

    def is_sleep_event(self, event: LifecycleEvent) -> bool:
        """Return True if the event should trigger sleep mode."""
        return event in (
            LifecycleEvent.BACKGROUND,
            LifecycleEvent.PAUSE,
            LifecycleEvent.MINIMIZE,
        )

    def is_wake_event(self, event: LifecycleEvent) -> bool:
        """Return True if the event should trigger wake mode."""
        return event in (
            LifecycleEvent.FOREGROUND,
            LifecycleEvent.RESUME,
            LifecycleEvent.RESTORE,
        )

    def is_terminate_event(self, event: LifecycleEvent) -> bool:
        """Return True if the event should trigger full shutdown."""
        return event in (
            LifecycleEvent.TERMINATE,
            LifecycleEvent.CLOSE,
        )
