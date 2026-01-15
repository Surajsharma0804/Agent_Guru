"""
macOS Input Automation Implementation.

Implements InputAutomation interface using CGEvent for keyboard and mouse control.
Requires Accessibility permission for full functionality.

Uses:
    - subprocess with osascript for AppleScript-based automation
    - CGEvent simulation via Python bindings (pyobjc-framework-Quartz)
    - Accessibility API for UI element targeting

Capabilities:
    - Full keyboard control (with Accessibility permission)
    - Full mouse control (with Accessibility permission)
    - Application focusing
    - Requires Accessibility permission

Validates: Requirements 35.5, 35.8
"""

import subprocess
import time
from typing import Optional, Dict

from ...interfaces import InputAutomation, AutomationTarget, PlatformCapabilityError


class macOSInputAutomation(InputAutomation):
    """
    macOS implementation of InputAutomation.
    
    Uses:
        - osascript for keystroke simulation (AppleScript)
        - CGEvent for mouse control (requires pyobjc-framework-Quartz)
        - Accessibility API for UI targeting
    
    Capabilities:
        - Full keyboard and mouse control
        - Requires Accessibility permission
        - System-wide automation
    
    IMPORTANT: This implementation uses AppleScript as a fallback that works
    without additional dependencies. For production use with CGEvent, install:
        pip install pyobjc-framework-Quartz
    """
    
    def __init__(self):
        """Initialize macOS input automation."""
        self.platform = "macos"
        self._has_accessibility = self._check_accessibility_permission()
        
        # Try to import Quartz for CGEvent support
        try:
            from Quartz import (
                CGEventCreateKeyboardEvent,
                CGEventPost,
                CGEventSourceCreate,
                kCGEventSourceStateHIDSystemState,
                kCGHIDEventTap,
            )
            self._has_quartz = True
            self._event_source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
        except ImportError:
            self._has_quartz = False
            self._event_source = None
            print("Warning: pyobjc-framework-Quartz not installed. Using AppleScript fallback.")
    
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        """
        Type text using AppleScript keystroke simulation.
        
        Algorithm:
            1. If target specified, focus target application
            2. Use osascript to send keystrokes
            3. Handle special characters and escaping
        
        Args:
            text: Text to type
            target: Optional specific target (window, control)
        
        Returns:
            True if text typed successfully, False otherwise
        
        Raises:
            PlatformCapabilityError: If Accessibility permission not granted
        """
        try:
            if not self._has_accessibility:
                raise PlatformCapabilityError(
                    "Accessibility permission required for input automation on macOS. "
                    "Grant permission in System Preferences > Security & Privacy > Privacy > Accessibility"
                )
            
            # Focus target application if specified
            if target and target.target_type == "app":
                self.focus_app(target.identifier)
                time.sleep(0.2)  # Wait for focus
            
            # Escape special characters for AppleScript
            escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
            
            # Use AppleScript to type text
            # System Events can send keystrokes to the frontmost application
            applescript = f'''
            tell application "System Events"
                keystroke "{escaped_text}"
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"Timeout typing text")
            return False
        except Exception as e:
            print(f"Error typing text: {e}")
            return False
    
    def click(self, target: AutomationTarget) -> bool:
        """
        Click on UI element using AppleScript or CGEvent.
        
        Algorithm:
            1. Parse target (coordinate or UI element)
            2. If coordinate: Use CGEvent or AppleScript to click
            3. If UI element: Use Accessibility API via AppleScript
        
        Args:
            target: Target to click (control, coordinate)
        
        Returns:
            True if click successful, False otherwise
        
        Raises:
            PlatformCapabilityError: If Accessibility permission not granted
        """
        try:
            if not self._has_accessibility:
                raise PlatformCapabilityError(
                    "Accessibility permission required for input automation on macOS"
                )
            
            if target.target_type == "coordinate":
                # Parse coordinates from identifier (format: "x,y")
                try:
                    x, y = map(int, target.identifier.split(','))
                    return self._click_at_coordinate(x, y)
                except ValueError:
                    print(f"Invalid coordinate format: {target.identifier}")
                    return False
            
            elif target.target_type == "control":
                # Click UI element using Accessibility API
                return self._click_ui_element(target)
            
            else:
                print(f"Unsupported target type: {target.target_type}")
                return False
                
        except Exception as e:
            print(f"Error clicking: {e}")
            return False
    
    def focus_app(self, app_id: str) -> bool:
        """
        Bring application to foreground using AppleScript.
        
        Algorithm:
            1. Use AppleScript 'activate' command
            2. Wait for application to come to front
        
        Args:
            app_id: Application identifier
        
        Returns:
            True if app focused successfully, False otherwise
        """
        try:
            # Use AppleScript to activate application
            applescript = f'tell application "{app_id}" to activate'
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                time.sleep(0.3)  # Wait for activation
                return True
            else:
                print(f"Error focusing {app_id}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"Timeout focusing {app_id}")
            return False
        except Exception as e:
            print(f"Error focusing {app_id}: {e}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return macOS input automation capabilities."""
        return {
            'can_type_text': self._has_accessibility,
            'can_click': self._has_accessibility,
            'can_focus_apps': True,  # Doesn't require Accessibility
            'has_full_automation': self._has_accessibility,
            'requires_permission': True,
        }
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _check_accessibility_permission(self) -> bool:
        """
        Check if Accessibility permission is granted.
        
        Returns:
            True if permission granted, False otherwise
        """
        try:
            # Try to use System Events to check permission
            applescript = '''
            tell application "System Events"
                return true
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # If this succeeds, we have permission
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _click_at_coordinate(self, x: int, y: int) -> bool:
        """
        Click at specific screen coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
        
        Returns:
            True if click successful, False otherwise
        """
        try:
            if self._has_quartz:
                # Use CGEvent for precise clicking
                from Quartz import (
                    CGEventCreateMouseEvent,
                    CGEventPost,
                    kCGEventLeftMouseDown,
                    kCGEventLeftMouseUp,
                    kCGHIDEventTap,
                    kCGMouseButtonLeft,
                )
                
                # Create mouse down event
                mouse_down = CGEventCreateMouseEvent(
                    None,
                    kCGEventLeftMouseDown,
                    (x, y),
                    kCGMouseButtonLeft
                )
                
                # Create mouse up event
                mouse_up = CGEventCreateMouseEvent(
                    None,
                    kCGEventLeftMouseUp,
                    (x, y),
                    kCGMouseButtonLeft
                )
                
                # Post events
                CGEventPost(kCGHIDEventTap, mouse_down)
                time.sleep(0.05)  # Small delay between down and up
                CGEventPost(kCGHIDEventTap, mouse_up)
                
                return True
            else:
                # Fallback to AppleScript (less precise)
                applescript = f'''
                tell application "System Events"
                    click at {{{x}, {y}}}
                end tell
                '''
                
                result = subprocess.run(
                    ['osascript', '-e', applescript],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                return result.returncode == 0
                
        except Exception as e:
            print(f"Error clicking at ({x}, {y}): {e}")
            return False
    
    def _click_ui_element(self, target: AutomationTarget) -> bool:
        """
        Click UI element using Accessibility API.
        
        Args:
            target: Target UI element
        
        Returns:
            True if click successful, False otherwise
        """
        try:
            # Extract application and element info from target
            app_name = target.platform_data.get('app_name', '')
            element_description = target.identifier
            
            if not app_name:
                print("No app_name in platform_data for UI element click")
                return False
            
            # Use AppleScript to click UI element
            applescript = f'''
            tell application "System Events"
                tell process "{app_name}"
                    click {element_description}
                end tell
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error clicking UI element: {e}")
            return False
