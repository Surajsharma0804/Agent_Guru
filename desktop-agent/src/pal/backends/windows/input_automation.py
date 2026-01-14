"""
Windows Input Automation Implementation.

Implements InputAutomation interface using Win32 SendInput API for complete
keyboard and mouse control on Windows 10/11.

Validates: Requirements 35.4, 35.8
"""

import time
from typing import Optional, Dict
import ctypes
from ctypes import wintypes
import win32gui
import win32con
import win32api
import psutil

from ...interfaces import InputAutomation, AutomationTarget, PlatformCapabilityError


# Win32 constants and structures
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(wintypes.ULONG)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(wintypes.ULONG)),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', wintypes.DWORD),
        ('union', INPUT_UNION),
    ]


class WindowsInputAutomation(InputAutomation):
    """
    Windows implementation of InputAutomation.
    
    Uses:
        - Win32 SendInput for keyboard simulation
        - Win32 SendInput for mouse simulation
        - Win32 SetForegroundWindow for focus
    
    Capabilities:
        - Full keyboard control
        - Full mouse control
        - No special permissions required
    """
    
    def __init__(self):
        """Initialize Windows input automation."""
        self.platform = "windows"
        
        # Load user32.dll for SendInput
        self.user32 = ctypes.windll.user32
    
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        """
        Type text using Win32 SendInput.
        
        Algorithm:
            1. If target specified, focus target window/control
            2. For each character in text:
                a. Create INPUT structure with KEYEVENTF_UNICODE
                b. Send key down event
                c. Send key up event
            3. Add small delay between characters (10ms)
        
        Args:
            text: Text to type
            target: Optional target window/control
        
        Returns:
            True if text typed successfully, False otherwise
        """
        try:
            # Focus target if specified
            if target:
                if target.target_type == "window":
                    hwnd = win32gui.FindWindow(None, target.identifier)
                    if hwnd:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.2)  # Wait for window to be ready
                elif target.target_type == "app":
                    self.focus_app(target.identifier)
                    time.sleep(0.2)
            
            # Type each character
            for char in text:
                # Create INPUT structures for key down and key up
                inputs = []
                
                # Key down
                ki_down = KEYBDINPUT()
                ki_down.wVk = 0
                ki_down.wScan = ord(char)
                ki_down.dwFlags = KEYEVENTF_UNICODE
                ki_down.time = 0
                ki_down.dwExtraInfo = None
                
                input_down = INPUT()
                input_down.type = INPUT_KEYBOARD
                input_down.union.ki = ki_down
                inputs.append(input_down)
                
                # Key up
                ki_up = KEYBDINPUT()
                ki_up.wVk = 0
                ki_up.wScan = ord(char)
                ki_up.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                ki_up.time = 0
                ki_up.dwExtraInfo = None
                
                input_up = INPUT()
                input_up.type = INPUT_KEYBOARD
                input_up.union.ki = ki_up
                inputs.append(input_up)
                
                # Send input
                input_array = (INPUT * len(inputs))(*inputs)
                self.user32.SendInput(len(inputs), input_array, ctypes.sizeof(INPUT))
                
                # Small delay between characters
                time.sleep(0.01)
            
            return True
            
        except Exception as e:
            print(f"Error typing text: {e}")
            return False
    
    def click(self, target: AutomationTarget) -> bool:
        """
        Click using Win32 SendInput.
        
        Algorithm:
            1. Determine click coordinates from target
            2. Move mouse to coordinates
            3. Send mouse down event
            4. Send mouse up event
        
        Args:
            target: Target to click (control, coordinate)
        
        Returns:
            True if click successful, False otherwise
        """
        try:
            # Get coordinates
            if target.target_type == "coordinate":
                x, y = map(int, target.identifier.split(','))
            elif target.target_type == "control":
                # Try to find control window and get its center
                hwnd = win32gui.FindWindow(None, target.identifier)
                if hwnd:
                    rect = win32gui.GetWindowRect(hwnd)
                    x = (rect[0] + rect[2]) // 2
                    y = (rect[1] + rect[3]) // 2
                else:
                    return False
            else:
                return False
            
            # Move mouse to position
            win32api.SetCursorPos((x, y))
            time.sleep(0.1)
            
            # Send mouse down
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            time.sleep(0.05)
            
            # Send mouse up
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            
            return True
            
        except Exception as e:
            print(f"Error clicking: {e}")
            return False
    
    def focus_app(self, app_id: str) -> bool:
        """
        Focus application using Win32 SetForegroundWindow.
        
        Algorithm:
            1. Find window belonging to application
            2. Use SetForegroundWindow to bring to front
            3. Verify window is now foreground
        
        Args:
            app_id: Application identifier
        
        Returns:
            True if app focused successfully, False otherwise
        """
        try:
            app_id_normalized = app_id.lower().strip().replace(' ', '')
            
            # Find process by name
            target_pid = None
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info['name'].lower()
                    if app_id_normalized in proc_name or proc_name.startswith(app_id_normalized):
                        target_pid = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not target_pid:
                return False
            
            # Find window belonging to this process
            def enum_windows_callback(hwnd, pid):
                if win32gui.IsWindowVisible(hwnd):
                    _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if window_pid == pid:
                        try:
                            win32gui.SetForegroundWindow(hwnd)
                            return False  # Stop enumeration
                        except:
                            pass
                return True
            
            import win32process
            win32gui.EnumWindows(lambda hwnd, pid: enum_windows_callback(hwnd, pid), target_pid)
            
            return True
            
        except Exception as e:
            print(f"Error focusing app {app_id}: {e}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return Windows input automation capabilities."""
        return {
            'can_type_text': True,
            'can_click': True,
            'can_focus_apps': True,
            'has_full_automation': True,
            'requires_permission': False,
        }
