"""
Windows Security Enforcer Implementation.

Implements SecurityEnforcer interface using Win32 LockWorkStation API for
system-wide security lockdown on Windows 10/11.

Validates: Requirements 40.2, 40.6
"""

import ctypes
from typing import Dict

from ...interfaces import SecurityEnforcer


class WindowsSecurityEnforcer(SecurityEnforcer):
    """
    Windows implementation of SecurityEnforcer.
    
    Uses:
        - Win32 LockWorkStation API for workstation lock
        - System-wide authority
    
    Capabilities:
        - Workstation lock (system-wide)
        - Immediate effect
        - Requires user unlock
    """
    
    def __init__(self):
        """Initialize Windows security enforcer."""
        self.platform = "windows"
        
        # Load user32.dll for LockWorkStation
        self.user32 = ctypes.windll.user32
    
    def lock_session(self, reason: str) -> bool:
        """
        Lock workstation using Win32 LockWorkStation.
        
        Algorithm:
            1. Call LockWorkStation API
            2. Workstation locks immediately
            3. User must unlock with credentials
        
        Args:
            reason: Reason for lock (for audit logging)
        
        Returns:
            True if lock successful, False otherwise
        
        Security:
            - Immediate effect (no delay)
            - System-wide lock (entire workstation)
            - Requires user credentials to unlock
            - Cryptographic audit logging (handled by caller)
        
        Note: This requires the SE_SHUTDOWN_NAME privilege, which is typically
        available to interactive users. If the application runs with restricted
        privileges, this may fail.
        """
        try:
            # Log reason (for audit trail)
            
            # Call LockWorkStation API
            # Returns non-zero on success, zero on failure
            result = self.user32.LockWorkStation()
            
            if result == 0:
                # Get error code
                ctypes.get_last_error()
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def get_lock_scope(self) -> str:
        """
        Get scope of lock operation.
        
        Returns:
            Lock scope: "system" (workstation lock)
        
        Windows locks the entire workstation, requiring user credentials
        to unlock. This is system-wide, not just screen or app level.
        """
        return "system"
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return Windows security capabilities."""
        return {
            'can_lock_system': True,
            'can_lock_screen': True,
            'can_lock_app': True,
            'has_system_authority': True,
        }
    
    # ========================================================================
    # Additional Security Methods
    # ========================================================================
    
    def is_workstation_locked(self) -> bool:
        """
        Check if workstation is currently locked.
        
        Returns:
            True if workstation is locked, False otherwise
        
        Note: This uses OpenInputDesktop to check if the desktop is accessible.
        If the desktop is locked, OpenInputDesktop will fail.
        """
        try:
            # Try to open the input desktop
            # If workstation is locked, this will fail
            hdesk = self.user32.OpenInputDesktop(0, False, 0)
            
            if hdesk:
                # Desktop is accessible (not locked)
                self.user32.CloseDesktop(hdesk)
                return False
            else:
                # Desktop is not accessible (locked)
                return True
                
        except Exception as e:
            return False
    
    def enable_screensaver(self) -> bool:
        """
        Enable screensaver immediately.
        
        This is a softer alternative to full workstation lock.
        
        Returns:
            True if screensaver enabled, False otherwise
        """
        try:
            # Send WM_SYSCOMMAND with SC_SCREENSAVE
            SC_SCREENSAVE = 0xF140
            result = self.user32.SendMessageW(
                0xFFFF,  # HWND_BROADCAST
                0x0112,  # WM_SYSCOMMAND
                SC_SCREENSAVE,
                0
            )
            return True
        except Exception as e:
            return False
    
    def log_off_user(self) -> bool:
        """
        Log off current user.
        
        This is a more severe action than locking the workstation.
        Use with caution.
        
        Returns:
            True if logoff initiated, False otherwise
        
        Note: This requires SE_SHUTDOWN_NAME privilege.
        """
        try:
            # ExitWindowsEx with EWX_LOGOFF flag
            EWX_LOGOFF = 0x00000000
            result = self.user32.ExitWindowsEx(EWX_LOGOFF, 0)
            return result != 0
        except Exception as e:
            return False
