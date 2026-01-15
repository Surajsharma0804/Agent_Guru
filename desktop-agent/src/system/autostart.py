"""
Windows Auto-Start Manager

Manages GURU auto-start on Windows boot using Task Scheduler.
Provides production-grade startup configuration with proper error handling.
"""

import subprocess
import sys
from pathlib import Path


class AutoStartManager:
    """
    Production-grade auto-start manager for Windows.
    
    Uses Windows Task Scheduler for reliable startup configuration.
    Handles:
    - Task creation and deletion
    - Startup delay configuration
    - Error recovery
    - Permission management
    """
    
    def __init__(self):
        """Initialize auto-start manager"""
        self.task_name = "GURU_Personal_Assistant"
        self.guru_path = Path(__file__).parent.parent.parent / "launch_guru.py"
        self.python_exe = sys.executable
    
    def is_enabled(self) -> bool:
        """Check if auto-start is enabled"""
        try:
            result = subprocess.run(
                ['schtasks', '/Query', '/TN', self.task_name],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error checking auto-start status: {e}")
            return False
    
    def enable(self, delay_seconds: int = 30) -> bool:
        """
        Enable auto-start on Windows boot.
        
        Args:
            delay_seconds: Delay before starting GURU (default: 30s)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete existing task if present
            self.disable()
            
            # Create XML task definition
            task_xml = self._generate_task_xml(delay_seconds)
            
            # Write to temp file
            temp_xml = Path.home() / ".guru" / "task.xml"
            temp_xml.parent.mkdir(parents=True, exist_ok=True)
            
            with open(temp_xml, 'w') as f:
                f.write(task_xml)
            
            # Create task using schtasks
            result = subprocess.run(
                [
                    'schtasks',
                    '/Create',
                    '/TN', self.task_name,
                    '/XML', str(temp_xml),
                    '/F'  # Force overwrite
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Clean up temp file
            temp_xml.unlink(missing_ok=True)
            
            if result.returncode == 0:
                print(f"✓ Auto-start enabled: GURU will start {delay_seconds}s after Windows boot")
                return True
            else:
                print(f"✗ Failed to enable auto-start: {result.stderr}")
                return False
        
        except Exception as e:
            print(f"Error enabling auto-start: {e}")
            return False
    
    def disable(self) -> bool:
        """Disable auto-start"""
        try:
            result = subprocess.run(
                ['schtasks', '/Delete', '/TN', self.task_name, '/F'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                print("✓ Auto-start disabled")
                return True
            else:
                # Task might not exist, which is fine
                return True
        
        except Exception as e:
            print(f"Error disabling auto-start: {e}")
            return False
    
    def _generate_task_xml(self, delay_seconds: int) -> str:
        """Generate Windows Task Scheduler XML"""
        # Get current user
        import getpass
        username = getpass.getuser()
        
        # Build command
        f'"{self.python_exe}" "{self.guru_path}"'
        working_dir = str(self.guru_path.parent)
        
        xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>GURU Personal AI Assistant - Auto-start on Windows boot</Description>
    <Author>{username}</Author>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT{delay_seconds}S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{self.python_exe}</Command>
      <Arguments>"{self.guru_path}"</Arguments>
      <WorkingDirectory>{working_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''
        
        return xml


def configure_autostart(enable: bool, delay_seconds: int = 30) -> bool:
    """
    Configure GURU auto-start.
    
    Args:
        enable: True to enable, False to disable
        delay_seconds: Delay before starting (only used if enabling)
    
    Returns:
        True if successful
    """
    manager = AutoStartManager()
    
    if enable:
        return manager.enable(delay_seconds)
    else:
        return manager.disable()


def is_autostart_enabled() -> bool:
    """Check if auto-start is currently enabled"""
    manager = AutoStartManager()
    return manager.is_enabled()


if __name__ == "__main__":
    # Test auto-start configuration
    manager = AutoStartManager()
    
    print("Current status:", "Enabled" if manager.is_enabled() else "Disabled")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "enable":
            manager.enable()
        elif sys.argv[1] == "disable":
            manager.disable()
        elif sys.argv[1] == "status":
            print("Auto-start:", "Enabled" if manager.is_enabled() else "Disabled")
