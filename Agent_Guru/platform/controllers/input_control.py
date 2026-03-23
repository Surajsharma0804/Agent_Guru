"""
Module: agent_guru.platform.controllers.input_control
Purpose: Cross-platform mouse and keyboard control for complete input automation

This module provides comprehensive input control capabilities including mouse
operations (move, click, drag) and keyboard operations (shortcuts, typing).

Performance Characteristics:
    - Time Complexity: O(1) per operation
    - Space Complexity: O(1) (no state storage)
    - Latency: <10ms per operation
    - Accuracy: Pixel-perfect mouse positioning

Architecture:
    Uses pyautogui for cross-platform input simulation with safety features
    including fail-safe corners and configurable delays.

Usage Example:
    >>> from agent_guru.platform.controllers.input_control import (
    ...     MouseController, KeyboardController
    ... )
    >>>
    >>> # Mouse operations
    >>> mouse = MouseController()
    >>> mouse.move_to(100, 200)
    >>> mouse.click()
    >>> mouse.drag_to(300, 400)
    >>>
    >>> # Keyboard operations
    >>> keyboard = KeyboardController()
    >>> keyboard.type_text("Hello World")
    >>> keyboard.press_shortcut("ctrl", "c")

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from typing import Literal, Optional, Union

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger(__name__)


# Mouse button types
MouseButton = Literal["left", "right", "middle"]


@dataclass
class MouseConfig:
    """Configuration for mouse controller.

    Attributes:
        duration: Movement duration in seconds (0 for instant)
        pause: Pause after each operation in seconds
        fail_safe: Enable fail-safe (move to corner to abort)
        tween: Easing function for movement (linear, easeInQuad, etc.)
    """
    duration: float = 0.1
    pause: float = 0.01
    fail_safe: bool = True
    tween: str = "linear"


@dataclass
class KeyboardConfig:
    """Configuration for keyboard controller.

    Attributes:
        interval: Interval between key presses in seconds
        pause: Pause after each operation in seconds
    """
    interval: float = 0.01
    pause: float = 0.01


class MouseController:
    """Cross-platform mouse controller using pyautogui.

    Time Complexity: O(1) per operation
    Space Complexity: O(1)

    Provides comprehensive mouse control including:
    - Cursor movement (absolute and relative)
    - Click operations (left, right, middle, double)
    - Drag and drop operations
    - Scroll operations

    Example:
        >>> mouse = MouseController()
        >>> mouse.move_to(100, 200)
        >>> mouse.click()
        >>> mouse.drag_to(300, 400)
        >>> mouse.scroll(10)
    """

    def __init__(self, config: Optional[MouseConfig] = None) -> None:
        """Initialize mouse controller.

        Args:
            config: Mouse configuration (uses defaults if None)

        Raises:
            ImportError: If pyautogui is not available
        """
        if not PYAUTOGUI_AVAILABLE:
            raise ImportError(
                "pyautogui is required for mouse control. "
                "Install with: pip install pyautogui"
            )

        self.config = config or MouseConfig()

        # Configure pyautogui
        pyautogui.PAUSE = self.config.pause
        pyautogui.FAILSAFE = self.config.fail_safe

        logger.info("MouseController initialized")

    def get_position(self) -> tuple[int, int]:
        """Get current cursor position.

        Time Complexity: O(1)

        Returns:
            Tuple of (x, y) coordinates

        Example:
            >>> mouse = MouseController()
            >>> x, y = mouse.get_position()
            >>> print(f"Cursor at ({x}, {y})")
        """
        x, y = pyautogui.position()
        return int(x), int(y)

    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None
    ) -> None:
        """Move cursor to absolute position.

        Time Complexity: O(1)

        Args:
            x: Target x coordinate
            y: Target y coordinate
            duration: Movement duration (uses config default if None)

        Raises:
            ValueError: If coordinates are out of screen bounds

        Example:
            >>> mouse = MouseController()
            >>> mouse.move_to(100, 200)  # Move to (100, 200)
            >>> mouse.move_to(300, 400, duration=0.5)  # Slow movement
        """
        screen_width, screen_height = pyautogui.size()

        if not (0 <= x < screen_width and 0 <= y < screen_height):
            raise ValueError(
                f"Coordinates ({x}, {y}) out of screen bounds "
                f"({screen_width}x{screen_height})"
            )

        duration = duration if duration is not None else self.config.duration

        pyautogui.moveTo(
            x, y,
            duration=duration,
            tween=getattr(pyautogui, self.config.tween)
        )

        logger.debug(f"Moved cursor to ({x}, {y})")

    def move_relative(
        self,
        dx: int,
        dy: int,
        duration: Optional[float] = None
    ) -> None:
        """Move cursor relative to current position.

        Time Complexity: O(1)

        Args:
            dx: Horizontal offset
            dy: Vertical offset
            duration: Movement duration (uses config default if None)

        Example:
            >>> mouse = MouseController()
            >>> mouse.move_relative(50, 100)  # Move 50 right, 100 down
            >>> mouse.move_relative(-50, -100)  # Move back
        """
        duration = duration if duration is not None else self.config.duration

        pyautogui.move(
            dx, dy,
            duration=duration,
            tween=getattr(pyautogui, self.config.tween)
        )

        logger.debug(f"Moved cursor by ({dx}, {dy})")

    def click(
        self,
        button: MouseButton = "left",
        clicks: int = 1,
        interval: float = 0.0
    ) -> None:
        """Click mouse button at current position.

        Time Complexity: O(1)

        Args:
            button: Mouse button to click ("left", "right", "middle")
            clicks: Number of clicks
            interval: Interval between clicks in seconds

        Example:
            >>> mouse = MouseController()
            >>> mouse.click()  # Single left click
            >>> mouse.click("right")  # Right click
            >>> mouse.click("left", clicks=2)  # Double click
        """
        pyautogui.click(button=button, clicks=clicks, interval=interval)
        logger.debug(f"Clicked {button} button {clicks} time(s)")

    def click_at(
        self,
        x: int,
        y: int,
        button: MouseButton = "left",
        clicks: int = 1
    ) -> None:
        """Click mouse button at specific position.

        Time Complexity: O(1)

        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button to click
            clicks: Number of clicks

        Example:
            >>> mouse = MouseController()
            >>> mouse.click_at(100, 200)  # Click at (100, 200)
            >>> mouse.click_at(300, 400, "right")  # Right click
        """
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        logger.debug(f"Clicked {button} at ({x}, {y})")

    def double_click(self, button: MouseButton = "left") -> None:
        """Double-click mouse button at current position.

        Time Complexity: O(1)

        Args:
            button: Mouse button to double-click

        Example:
            >>> mouse = MouseController()
            >>> mouse.double_click()  # Double left click
        """
        self.click(button=button, clicks=2)

    def right_click(self) -> None:
        """Right-click at current position.

        Time Complexity: O(1)

        Example:
            >>> mouse = MouseController()
            >>> mouse.right_click()
        """
        self.click(button="right")

    def drag_to(
        self,
        x: int,
        y: int,
        button: MouseButton = "left",
        duration: Optional[float] = None
    ) -> None:
        """Drag from current position to target position.

        Time Complexity: O(1)

        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button to hold during drag
            duration: Drag duration (uses config default if None)

        Example:
            >>> mouse = MouseController()
            >>> mouse.move_to(100, 100)
            >>> mouse.drag_to(200, 200)  # Drag to (200, 200)
        """
        duration = duration if duration is not None else self.config.duration

        pyautogui.dragTo(
            x, y,
            duration=duration,
            button=button,
            tween=getattr(pyautogui, self.config.tween)
        )

        logger.debug(f"Dragged to ({x}, {y})")

    def drag_relative(
        self,
        dx: int,
        dy: int,
        button: MouseButton = "left",
        duration: Optional[float] = None
    ) -> None:
        """Drag relative to current position.

        Time Complexity: O(1)

        Args:
            dx: Horizontal offset
            dy: Vertical offset
            button: Mouse button to hold during drag
            duration: Drag duration (uses config default if None)

        Example:
            >>> mouse = MouseController()
            >>> mouse.drag_relative(100, 100)  # Drag 100 right, 100 down
        """
        duration = duration if duration is not None else self.config.duration

        pyautogui.drag(
            dx, dy,
            duration=duration,
            button=button,
            tween=getattr(pyautogui, self.config.tween)
        )

        logger.debug(f"Dragged by ({dx}, {dy})")

    def scroll(
        self,
        clicks: int,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> None:
        """Scroll mouse wheel.

        Time Complexity: O(1)

        Args:
            clicks: Number of scroll clicks (positive=up, negative=down)
            x: Optional x coordinate to scroll at
            y: Optional y coordinate to scroll at

        Example:
            >>> mouse = MouseController()
            >>> mouse.scroll(10)  # Scroll up 10 clicks
            >>> mouse.scroll(-5)  # Scroll down 5 clicks
            >>> mouse.scroll(3, x=100, y=200)  # Scroll at position
        """
        pyautogui.scroll(clicks, x=x, y=y)
        logger.debug(f"Scrolled {clicks} clicks")

    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions.

        Time Complexity: O(1)

        Returns:
            Tuple of (width, height) in pixels

        Example:
            >>> mouse = MouseController()
            >>> width, height = mouse.get_screen_size()
            >>> print(f"Screen: {width}x{height}")
        """
        width, height = pyautogui.size()
        return int(width), int(height)


class KeyboardController:
    """Cross-platform keyboard controller using pyautogui.

    Time Complexity: O(n) for typing n characters
    Space Complexity: O(1)

    Provides comprehensive keyboard control including:
    - Text typing
    - Key press/release/hold operations
    - Keyboard shortcuts (Ctrl+C, Alt+Tab, etc.)
    - Special key handling

    Example:
        >>> keyboard = KeyboardController()
        >>> keyboard.type_text("Hello World")
        >>> keyboard.press_shortcut("ctrl", "c")
        >>> keyboard.press_key("enter")
    """

    def __init__(self, config: Optional[KeyboardConfig] = None) -> None:
        """Initialize keyboard controller.

        Args:
            config: Keyboard configuration (uses defaults if None)

        Raises:
            ImportError: If pyautogui is not available
        """
        if not PYAUTOGUI_AVAILABLE:
            raise ImportError(
                "pyautogui is required for keyboard control. "
                "Install with: pip install pyautogui"
            )

        self.config = config or KeyboardConfig()

        # Configure pyautogui
        pyautogui.PAUSE = self.config.pause

        logger.info("KeyboardController initialized")

    def type_text(self, text: str, interval: Optional[float] = None) -> None:
        """Type text string.

        Time Complexity: O(n) where n is text length
        Space Complexity: O(1)

        Args:
            text: Text to type
            interval: Interval between key presses (uses config default if None)

        Example:
            >>> keyboard = KeyboardController()
            >>> keyboard.type_text("Hello World")
            >>> keyboard.type_text("Fast typing", interval=0.0)
        """
        interval = interval if interval is not None else self.config.interval

        pyautogui.write(text, interval=interval)
        logger.debug(f"Typed text: {text[:50]}...")

    def press_key(self, key: str, presses: int = 1) -> None:
        """Press and release key.

        Time Complexity: O(1)

        Args:
            key: Key name (e.g., "enter", "space", "a", "f1")
            presses: Number of times to press

        Example:
            >>> keyboard = KeyboardController()
            >>> keyboard.press_key("enter")
            >>> keyboard.press_key("space", presses=3)
        """
        pyautogui.press(key, presses=presses)
        logger.debug(f"Pressed key: {key} ({presses} times)")

    def key_down(self, key: str) -> None:
        """Press key down (without releasing).

        Time Complexity: O(1)

        Args:
            key: Key name to press down

        Example:
            >>> keyboard = KeyboardController()
            >>> keyboard.key_down("shift")
            >>> keyboard.press_key("a")  # Types "A"
            >>> keyboard.key_up("shift")
        """
        pyautogui.keyDown(key)
        logger.debug(f"Key down: {key}")

    def key_up(self, key: str) -> None:
        """Release key.

        Time Complexity: O(1)

        Args:
            key: Key name to release

        Example:
            >>> keyboard = KeyboardController()
            >>> keyboard.key_down("ctrl")
            >>> keyboard.press_key("c")
            >>> keyboard.key_up("ctrl")
        """
        pyautogui.keyUp(key)
        logger.debug(f"Key up: {key}")

    def press_shortcut(self, *keys: str) -> None:
        """Press keyboard shortcut (multiple keys simultaneously).

        Time Complexity: O(1)

        Args:
            *keys: Keys to press together (e.g., "ctrl", "c")

        Example:
            >>> keyboard = KeyboardController()
            >>> keyboard.press_shortcut("ctrl", "c")  # Copy
            >>> keyboard.press_shortcut("ctrl", "v")  # Paste
            >>> keyboard.press_shortcut("alt", "tab")  # Switch window
            >>> keyboard.press_shortcut("ctrl", "shift", "esc")  # Task manager
        """
        pyautogui.hotkey(*keys)
        logger.debug(f"Pressed shortcut: {'+'.join(keys)}")

    def hold_keys(self, keys: list[str]) -> "KeyHoldContext":
        """Context manager to hold keys down.

        Time Complexity: O(1)

        Args:
            keys: List of keys to hold

        Returns:
            Context manager that releases keys on exit

        Example:
            >>> keyboard = KeyboardController()
            >>> with keyboard.hold_keys(["ctrl", "shift"]):
            ...     keyboard.press_key("a")  # Ctrl+Shift+A
        """
        return KeyHoldContext(self, keys)

    # Convenience methods for common shortcuts
    def copy(self) -> None:
        """Copy shortcut (Ctrl+C)."""
        self.press_shortcut("ctrl", "c")

    def paste(self) -> None:
        """Paste shortcut (Ctrl+V)."""
        self.press_shortcut("ctrl", "v")

    def cut(self) -> None:
        """Cut shortcut (Ctrl+X)."""
        self.press_shortcut("ctrl", "x")

    def select_all(self) -> None:
        """Select all shortcut (Ctrl+A)."""
        self.press_shortcut("ctrl", "a")

    def undo(self) -> None:
        """Undo shortcut (Ctrl+Z)."""
        self.press_shortcut("ctrl", "z")

    def redo(self) -> None:
        """Redo shortcut (Ctrl+Y)."""
        self.press_shortcut("ctrl", "y")

    def save(self) -> None:
        """Save shortcut (Ctrl+S)."""
        self.press_shortcut("ctrl", "s")

    def find(self) -> None:
        """Find shortcut (Ctrl+F)."""
        self.press_shortcut("ctrl", "f")

    def press(self, keys: Union[str, list[str]]) -> None:
        """Press key(s).

        Args:
            keys: Single key or list of keys to press
        """
        if isinstance(keys, str):
            self.press_key(keys)
        else:
            pyautogui.press(keys)

    def hotkey(self, *keys: str) -> None:
        """Alias for press_shortcut."""
        self.press_shortcut(*keys)

    def hold_key(self, key: str) -> "KeyHoldContext":
        """Context manager to hold a single key.

        Args:
            key: Key to hold

        Returns:
            Context manager that releases key on exit
        """
        return KeyHoldContext(self, [key])


    # Convenience methods for common shortcuts
    def copy(self) -> None:
        """Copy shortcut (Ctrl+C)."""
        self.press_shortcut("ctrl", "c")

    def paste(self) -> None:
        """Paste shortcut (Ctrl+V)."""
        self.press_shortcut("ctrl", "v")

    def cut(self) -> None:
        """Cut shortcut (Ctrl+X)."""
        self.press_shortcut("ctrl", "x")

    def select_all(self) -> None:
        """Select all shortcut (Ctrl+A)."""
        self.press_shortcut("ctrl", "a")

    def undo(self) -> None:
        """Undo shortcut (Ctrl+Z)."""
        self.press_shortcut("ctrl", "z")

    def redo(self) -> None:
        """Redo shortcut (Ctrl+Y)."""
        self.press_shortcut("ctrl", "y")

    def save(self) -> None:
        """Save shortcut (Ctrl+S)."""
        self.press_shortcut("ctrl", "s")

    def find(self) -> None:
        """Find shortcut (Ctrl+F)."""
        self.press_shortcut("ctrl", "f")

    def press(self, keys: Union[str, list[str]]) -> None:
        """Press key(s).

        Args:
            keys: Single key or list of keys to press
        """
        if isinstance(keys, str):
            self.press_key(keys)
        else:
            pyautogui.press(keys)

    def hotkey(self, *keys: str) -> None:
        """Alias for press_shortcut."""
        self.press_shortcut(*keys)

    def hold_key(self, key: str) -> "KeyHoldContext":
        """Context manager to hold a single key.

        Args:
            key: Key to hold

        Returns:
            Context manager that releases key on exit
        """
        return KeyHoldContext(self, [key])



class KeyHoldContext:
    """Context manager for holding keys down.

    Example:
        >>> keyboard = KeyboardController()
        >>> with KeyHoldContext(keyboard, ["ctrl"]):
        ...     keyboard.press_key("c")  # Ctrl+C
    """

    def __init__(self, controller: KeyboardController, keys: list[str]) -> None:
        """Initialize key hold context.

        Args:
            controller: Keyboard controller instance
            keys: Keys to hold down
        """
        self.controller = controller
        self.keys = keys

    def __enter__(self) -> "KeyHoldContext":
        """Press all keys down."""
        for key in self.keys:
            self.controller.key_down(key)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release all keys."""
        for key in reversed(self.keys):
            self.controller.key_up(key)


# Common keyboard shortcuts
class Shortcuts:
    """Common keyboard shortcuts for convenience.

    Example:
        >>> keyboard = KeyboardController()
        >>> keyboard.press_shortcut(*Shortcuts.COPY)
        >>> keyboard.press_shortcut(*Shortcuts.PASTE)
    """

    # Clipboard operations
    COPY = ("ctrl", "c")
    CUT = ("ctrl", "x")
    PASTE = ("ctrl", "v")
    SELECT_ALL = ("ctrl", "a")
    UNDO = ("ctrl", "z")
    REDO = ("ctrl", "y")

    # Window management
    SWITCH_WINDOW = ("alt", "tab")
    CLOSE_WINDOW = ("alt", "f4")
    MINIMIZE_WINDOW = ("win", "down")
    MAXIMIZE_WINDOW = ("win", "up")
    SHOW_DESKTOP = ("win", "d")

    # Application shortcuts
    NEW_TAB = ("ctrl", "t")
    CLOSE_TAB = ("ctrl", "w")
    REOPEN_TAB = ("ctrl", "shift", "t")
    REFRESH = ("f5")
    SAVE = ("ctrl", "s")
    PRINT = ("ctrl", "p")

    # System shortcuts
    TASK_MANAGER = ("ctrl", "shift", "esc")
    LOCK_SCREEN = ("win", "l")
    SCREENSHOT = ("win", "shift", "s")
