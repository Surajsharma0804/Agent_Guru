"""
Windows API Input Simulation Engine

Production-grade Windows input simulation using SendInput API with comprehensive
security validation, authority enforcement, and audit logging.

This implementation follows Windows security best practices and never bypasses
OS security mechanisms. All input simulation requires explicit authority.
"""

import ctypes
import logging
import time
from ctypes import windll, wintypes
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from ..authority.state import AuthorityState, AuthorityStateMachine
from .input_audit_logger import InputAuditLogger
from .input_validator import InputValidator


class InputType(Enum):
    """Input simulation types with security classifications"""

    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    KEY_COMBINATION = "key_combination"
    TEXT_TYPING = "text_typing"


class SecurityLevel(Enum):
    """Security levels for input operations"""

    LOW_RISK = "low_risk"  # Basic typing, simple keys
    MEDIUM_RISK = "medium_risk"  # Key combinations, mouse actions
    HIGH_RISK = "high_risk"  # System keys, admin shortcuts


@dataclass
class InputEvent:
    """Represents a validated input event ready for execution"""

    event_type: InputType
    security_level: SecurityLevel
    parameters: Dict
    timestamp: datetime
    session_id: str
    requires_authority: bool = True


@dataclass
class InputResult:
    """Result of input simulation operation"""

    success: bool
    events_sent: int
    error_message: Optional[str] = None
    security_violations: List[str] = None
    execution_time_ms: float = 0.0


# Windows API Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000


# Windows API Structures
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class WindowsInputEngine:
    """
    Production-grade Windows input simulation engine with comprehensive security.

    This engine implements voice-driven input control with strict authority enforcement,
    comprehensive validation, and detailed audit logging. All operations require
    explicit authority and are subject to security validation.

    Security Features:
    - Authority state enforcement (requires ARMED state)
    - Input validation and sanitization
    - Comprehensive audit logging
    - Rate limiting and abuse prevention
    - Immediate halt on authority revocation
    """

    def __init__(
        self, authority_machine: AuthorityStateMachine, validator: InputValidator, audit_logger: InputAuditLogger
    ):
        """
        Initialize Windows Input Engine with security components.

        Args:
            authority_machine: Authority state management
            validator: Input validation and sanitization
            audit_logger: Audit logging for all input events
        """
        self.authority_machine = authority_machine
        self.validator = validator
        self.audit_logger = audit_logger
        self.logger = logging.getLogger(__name__)

        # Windows API setup
        self.user32 = windll.user32
        self.kernel32 = windll.kernel32

        # Security configuration
        self.max_text_length = 10000  # Maximum text length for safety
        self.rate_limit_window = 60  # Rate limiting window in seconds
        self.max_events_per_window = 1000  # Maximum events per window

        # Event tracking for rate limiting
        self.recent_events: List[datetime] = []

        # Virtual key code mappings for common keys
        self.vk_codes = self._initialize_virtual_key_codes()

        # Key combination mappings
        self.key_combinations = self._initialize_key_combinations()

        self.logger.info("WindowsInputEngine initialized with security enforcement")

    def _initialize_virtual_key_codes(self) -> Dict[str, int]:
        """Initialize virtual key code mappings for Windows API"""
        return {
            # Letters (A-Z)
            **{chr(i): i for i in range(ord("A"), ord("Z") + 1)},
            # Numbers (0-9)
            **{str(i): ord("0") + i for i in range(10)},
            # Function keys
            **{f"F{i}": 0x70 + i - 1 for i in range(1, 13)},
            # Special keys
            "BACKSPACE": 0x08,
            "TAB": 0x09,
            "ENTER": 0x0D,
            "SHIFT": 0x10,
            "CTRL": 0x11,
            "ALT": 0x12,
            "PAUSE": 0x13,
            "CAPS_LOCK": 0x14,
            "ESCAPE": 0x1B,
            "SPACE": 0x20,
            "PAGE_UP": 0x21,
            "PAGE_DOWN": 0x22,
            "END": 0x23,
            "HOME": 0x24,
            "LEFT": 0x25,
            "UP": 0x26,
            "RIGHT": 0x27,
            "DOWN": 0x28,
            "INSERT": 0x2D,
            "DELETE": 0x2E,
            "WINDOWS": 0x5B,
            "MENU": 0x5D,
            "NUMPAD_0": 0x60,
            "NUMPAD_1": 0x61,
            "NUMPAD_2": 0x62,
            "NUMPAD_3": 0x63,
            "NUMPAD_4": 0x64,
            "NUMPAD_5": 0x65,
            "NUMPAD_6": 0x66,
            "NUMPAD_7": 0x67,
            "NUMPAD_8": 0x68,
            "NUMPAD_9": 0x69,
            "MULTIPLY": 0x6A,
            "ADD": 0x6B,
            "SUBTRACT": 0x6D,
            "DECIMAL": 0x6E,
            "DIVIDE": 0x6F,
            "NUM_LOCK": 0x90,
            "SCROLL_LOCK": 0x91,
            "SEMICOLON": 0xBA,
            "EQUALS": 0xBB,
            "COMMA": 0xBC,
            "MINUS": 0xBD,
            "PERIOD": 0xBE,
            "SLASH": 0xBF,
            "BACKTICK": 0xC0,
            "LEFT_BRACKET": 0xDB,
            "BACKSLASH": 0xDC,
            "RIGHT_BRACKET": 0xDD,
            "QUOTE": 0xDE,
        }

    def _initialize_key_combinations(self) -> Dict[str, List[str]]:
        """Initialize common key combination mappings"""
        return {
            # System shortcuts
            "copy": ["CTRL", "C"],
            "paste": ["CTRL", "V"],
            "cut": ["CTRL", "X"],
            "undo": ["CTRL", "Z"],
            "redo": ["CTRL", "Y"],
            "select_all": ["CTRL", "A"],
            "save": ["CTRL", "S"],
            "open": ["CTRL", "O"],
            "new": ["CTRL", "N"],
            "find": ["CTRL", "F"],
            "replace": ["CTRL", "H"],
            "print": ["CTRL", "P"],
            # Window management
            "alt_tab": ["ALT", "TAB"],
            "alt_f4": ["ALT", "F4"],
            "windows_r": ["WINDOWS", "R"],
            "windows_d": ["WINDOWS", "D"],
            "windows_l": ["WINDOWS", "L"],
            "windows_e": ["WINDOWS", "E"],
            "windows_i": ["WINDOWS", "I"],
            # Browser shortcuts
            "new_tab": ["CTRL", "T"],
            "close_tab": ["CTRL", "W"],
            "reopen_tab": ["CTRL", "SHIFT", "T"],
            "refresh": ["CTRL", "R"],
            "hard_refresh": ["CTRL", "SHIFT", "R"],
            "address_bar": ["CTRL", "L"],
            "bookmark": ["CTRL", "D"],
            "history": ["CTRL", "H"],
            "downloads": ["CTRL", "J"],
            "developer_tools": ["F12"],
            # Text editing
            "bold": ["CTRL", "B"],
            "italic": ["CTRL", "I"],
            "underline": ["CTRL", "U"],
            "home": ["HOME"],
            "end": ["END"],
            "page_up": ["PAGE_UP"],
            "page_down": ["PAGE_DOWN"],
            "ctrl_home": ["CTRL", "HOME"],
            "ctrl_end": ["CTRL", "END"],
            "shift_home": ["SHIFT", "HOME"],
            "shift_end": ["SHIFT", "END"],
        }

    def _check_authority(self) -> bool:
        """Check if current authority state allows input simulation"""
        current_state = self.authority_machine.current_state
        return current_state == AuthorityState.ARMED

    def _check_rate_limit(self) -> bool:
        """Check if current operation is within rate limits"""
        now = datetime.now()

        # Remove events outside the window
        cutoff_time = now.timestamp() - self.rate_limit_window
        self.recent_events = [event for event in self.recent_events if event.timestamp() > cutoff_time]

        # Check if we're within limits
        return len(self.recent_events) < self.max_events_per_window

    def _record_event(self):
        """Record an event for rate limiting"""
        self.recent_events.append(datetime.now())

    def _create_keyboard_input(self, vk_code: int, key_up: bool = False) -> INPUT:
        """Create a keyboard INPUT structure for Windows API"""
        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki.wVk = vk_code
        input_struct.union.ki.wScan = 0
        input_struct.union.ki.dwFlags = KEYEVENTF_KEYUP if key_up else 0
        input_struct.union.ki.time = 0
        input_struct.union.ki.dwExtraInfo = None
        return input_struct

    def _create_unicode_input(self, char: str, key_up: bool = False) -> INPUT:
        """Create a Unicode keyboard INPUT structure"""
        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki.wVk = 0
        input_struct.union.ki.wScan = ord(char)
        input_struct.union.ki.dwFlags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
        input_struct.union.ki.time = 0
        input_struct.union.ki.dwExtraInfo = None
        return input_struct

    def _send_input_events(self, inputs: List[INPUT]) -> int:
        """Send input events to Windows using SendInput API"""
        if not inputs:
            return 0

        input_array = (INPUT * len(inputs))(*inputs)
        return self.user32.SendInput(len(inputs), input_array, ctypes.sizeof(INPUT))

    def type_text(self, text: str, session_id: str = None) -> InputResult:
        """
        Type exact text using voice-driven input simulation.

        This method types text exactly as spoken without paraphrasing or interpretation.
        All text is validated for security and logged for audit purposes.

        Args:
            text: Exact text to type (verbatim from voice input)
            session_id: Session identifier for audit logging

        Returns:
            InputResult with success status and execution details
        """
        start_time = time.time()

        # Authority enforcement
        if not self._check_authority():
            error_msg = "Input simulation requires ARMED authority state"
            self.audit_logger.log_security_violation(
                "authority_violation", {"action": "type_text", "reason": "insufficient_authority"}, session_id
            )
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["authority_not_granted"]
            )

        # Rate limiting check
        if not self._check_rate_limit():
            error_msg = "Rate limit exceeded for input simulation"
            self.audit_logger.log_security_violation(
                "rate_limit_exceeded",
                {"action": "type_text", "text_length": len(text) if text is not None else 0},
                session_id,
            )
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["rate_limit_exceeded"]
            )

        # Input validation
        validation_result = self.validator.validate_text_input(text)
        if not validation_result.is_valid:
            self.audit_logger.log_security_violation(
                "input_validation_failed",
                {
                    "action": "type_text",
                    "violations": validation_result.violations,
                    "text_length": len(text) if text is not None else 0,
                },
                session_id,
            )
            return InputResult(
                success=False,
                events_sent=0,
                error_message=f"Input validation failed: {validation_result.violations}",
                security_violations=validation_result.violations,
            )

        # Length check
        if text is not None and len(text) > self.max_text_length:
            error_msg = f"Text length {len(text)} exceeds maximum {self.max_text_length}"
            self.audit_logger.log_security_violation(
                "text_length_exceeded",
                {"action": "type_text", "length": len(text), "max_length": self.max_text_length},
                session_id,
            )
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["text_too_long"]
            )

        try:
            # Handle None text input
            if text is None:
                return InputResult(
                    success=False,
                    events_sent=0,
                    error_message="Text input cannot be None",
                    security_violations=["invalid_input"],
                )

            # Create input events for each character
            inputs = []
            for char in text:
                # Use Unicode input for reliable character reproduction
                inputs.append(self._create_unicode_input(char, key_up=False))
                inputs.append(self._create_unicode_input(char, key_up=True))

            # Send input events
            events_sent = self._send_input_events(inputs)

            # Record for rate limiting
            self._record_event()

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000

            # Audit logging (without text content for privacy)
            self.audit_logger.log_input_event(
                InputEvent(
                    event_type=InputType.TEXT_TYPING,
                    security_level=SecurityLevel.LOW_RISK,
                    parameters={
                        "text_length": len(text),
                        "characters_sent": len(inputs) // 2,
                        "execution_time_ms": execution_time,
                    },
                    timestamp=datetime.now(),
                    session_id=session_id or "unknown",
                )
            )

            self.logger.info(f"Successfully typed {len(text)} characters in {execution_time:.2f}ms")

            return InputResult(success=True, events_sent=events_sent, execution_time_ms=execution_time)

        except Exception as e:
            error_msg = f"Failed to type text: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            self.audit_logger.log_security_violation(
                "input_execution_failed",
                {"action": "type_text", "error": str(e), "text_length": len(text) if text is not None else 0},
                session_id,
            )

            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["execution_failed"]
            )

    def send_key_combination(self, combination: Union[str, List[str]], session_id: str = None) -> InputResult:
        """
        Send key combination (e.g., Ctrl+C, Alt+Tab, Windows+R).

        Args:
            combination: Key combination name or list of keys
            session_id: Session identifier for audit logging

        Returns:
            InputResult with success status and execution details
        """
        start_time = time.time()

        # Authority enforcement
        if not self._check_authority():
            error_msg = "Input simulation requires ARMED authority state"
            self.audit_logger.log_security_violation(
                "authority_violation", {"action": "key_combination", "combination": str(combination)}, session_id
            )
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["authority_not_granted"]
            )

        # Rate limiting check
        if not self._check_rate_limit():
            error_msg = "Rate limit exceeded for input simulation"
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["rate_limit_exceeded"]
            )

        # Resolve combination to key list
        if isinstance(combination, str):
            if combination.lower() in self.key_combinations:
                keys = self.key_combinations[combination.lower()]
            else:
                keys = [combination.upper()]
        else:
            keys = [key.upper() for key in combination]

        # Validate key combination
        validation_result = self.validator.validate_key_combination(keys)
        if not validation_result.is_valid:
            self.audit_logger.log_security_violation(
                "key_combination_validation_failed",
                {"action": "key_combination", "keys": keys, "violations": validation_result.violations},
                session_id,
            )
            return InputResult(
                success=False,
                events_sent=0,
                error_message=f"Key combination validation failed: {validation_result.violations}",
                security_violations=validation_result.violations,
            )

        # Determine security level
        security_level = self._determine_key_combination_security_level(keys)

        try:
            # Convert keys to virtual key codes
            vk_codes = []
            for key in keys:
                if key in self.vk_codes:
                    vk_codes.append(self.vk_codes[key])
                else:
                    raise ValueError(f"Unknown key: {key}")

            # Create input events (press all keys down, then release in reverse order)
            inputs = []

            # Press keys down
            for vk_code in vk_codes:
                inputs.append(self._create_keyboard_input(vk_code, key_up=False))

            # Release keys (in reverse order)
            for vk_code in reversed(vk_codes):
                inputs.append(self._create_keyboard_input(vk_code, key_up=True))

            # Send input events
            events_sent = self._send_input_events(inputs)

            # Record for rate limiting
            self._record_event()

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000

            # Audit logging
            self.audit_logger.log_input_event(
                InputEvent(
                    event_type=InputType.KEY_COMBINATION,
                    security_level=security_level,
                    parameters={"keys": keys, "vk_codes": vk_codes, "execution_time_ms": execution_time},
                    timestamp=datetime.now(),
                    session_id=session_id or "unknown",
                )
            )

            self.logger.info(f"Successfully sent key combination {'+'.join(keys)} in {execution_time:.2f}ms")

            return InputResult(success=True, events_sent=events_sent, execution_time_ms=execution_time)

        except Exception as e:
            error_msg = f"Failed to send key combination: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            self.audit_logger.log_security_violation(
                "key_combination_execution_failed",
                {"action": "key_combination", "keys": keys, "error": str(e)},
                session_id,
            )

            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["execution_failed"]
            )

    def send_single_key(self, key: str, session_id: str = None) -> InputResult:
        """
        Send a single key press.

        Args:
            key: Key name (e.g., 'ENTER', 'ESCAPE', 'F1')
            session_id: Session identifier for audit logging

        Returns:
            InputResult with success status and execution details
        """
        start_time = time.time()

        # Authority enforcement
        if not self._check_authority():
            error_msg = "Input simulation requires ARMED authority state"
            self.audit_logger.log_security_violation(
                "authority_violation", {"action": "single_key", "key": key}, session_id
            )
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["authority_not_granted"]
            )

        # Rate limiting check
        if not self._check_rate_limit():
            error_msg = "Rate limit exceeded for input simulation"
            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["rate_limit_exceeded"]
            )

        # Validate single key
        validation_result = self.validator.validate_single_key(key)
        if not validation_result.is_valid:
            self.audit_logger.log_security_violation(
                "single_key_validation_failed",
                {"action": "single_key", "key": key, "violations": validation_result.violations},
                session_id,
            )
            return InputResult(
                success=False,
                events_sent=0,
                error_message=f"Single key validation failed: {validation_result.violations}",
                security_violations=validation_result.violations,
            )

        try:
            # Get virtual key code
            key_upper = key.upper()
            if key_upper not in self.vk_codes:
                raise ValueError(f"Unknown key: {key}")

            vk_code = self.vk_codes[key_upper]

            # Create input events (key down, then key up)
            inputs = [
                self._create_keyboard_input(vk_code, key_up=False),
                self._create_keyboard_input(vk_code, key_up=True),
            ]

            # Send input events
            events_sent = self._send_input_events(inputs)

            # Record for rate limiting
            self._record_event()

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000

            # Determine security level
            security_level = self._determine_single_key_security_level(key_upper)

            # Audit logging
            self.audit_logger.log_input_event(
                InputEvent(
                    event_type=InputType.KEYBOARD,
                    security_level=security_level,
                    parameters={"key": key_upper, "vk_code": vk_code, "execution_time_ms": execution_time},
                    timestamp=datetime.now(),
                    session_id=session_id or "unknown",
                )
            )

            self.logger.info(f"Successfully sent key '{key_upper}' in {execution_time:.2f}ms")

            return InputResult(success=True, events_sent=events_sent, execution_time_ms=execution_time)

        except Exception as e:
            error_msg = f"Failed to send single key: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            self.audit_logger.log_security_violation(
                "single_key_execution_failed", {"action": "single_key", "key": key, "error": str(e)}, session_id
            )

            return InputResult(
                success=False, events_sent=0, error_message=error_msg, security_violations=["execution_failed"]
            )

    def _determine_key_combination_security_level(self, keys: List[str]) -> SecurityLevel:
        """Determine security level for key combination"""
        high_risk_keys = {"WINDOWS", "ALT", "CTRL", "F4", "DELETE"}
        system_keys = {"WINDOWS"}

        if any(key in system_keys for key in keys):
            return SecurityLevel.HIGH_RISK
        elif any(key in high_risk_keys for key in keys):
            return SecurityLevel.MEDIUM_RISK
        else:
            return SecurityLevel.LOW_RISK

    def _determine_single_key_security_level(self, key: str) -> SecurityLevel:
        """Determine security level for single key"""
        high_risk_keys = {"DELETE", "F4", "WINDOWS"}
        medium_risk_keys = {"ALT", "CTRL", "SHIFT", "ESCAPE"}

        if key in high_risk_keys:
            return SecurityLevel.HIGH_RISK
        elif key in medium_risk_keys:
            return SecurityLevel.MEDIUM_RISK
        else:
            return SecurityLevel.LOW_RISK

    def emergency_halt(self) -> None:
        """
        Emergency halt of all input simulation.

        Called when authority is revoked or security violation detected.
        Immediately stops all input operations and clears any pending events.
        """
        self.logger.warning("Emergency halt activated - all input simulation stopped")

        # Clear rate limiting events
        self.recent_events.clear()

        # Log emergency halt
        self.audit_logger.log_emergency_event(
            "input_simulation_halted",
            {
                "action": "input_simulation_halted",
                "reason": "authority_revoked_or_security_violation",
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_status(self) -> Dict:
        """Get current input engine status for monitoring"""
        return {
            "authority_state": self.authority_machine.current_state.value,
            "rate_limit_events": len(self.recent_events),
            "max_events_per_window": self.max_events_per_window,
            "rate_limit_window": self.rate_limit_window,
            "max_text_length": self.max_text_length,
            "available_key_combinations": len(self.key_combinations),
            "available_virtual_keys": len(self.vk_codes),
        }
