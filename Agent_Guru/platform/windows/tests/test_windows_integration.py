"""
Unit tests for Windows platform integration.
Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import sys

# winreg exists only on Windows. It has to come in through importorskip
# rather than a bare `import`: the pytestmark skipif below cannot take
# effect until this module has already been imported, so on a non-Windows
# host a plain `import winreg` turned the SKIP the author asked for into a
# collection ERROR -- which is why the suite could not even be collected on
# Linux or macOS. On Windows the import succeeds and every test in this
# file runs exactly as before.
winreg = pytest.importorskip("winreg")
from unittest.mock import patch
import logging

logger = logging.getLogger(__name__)

from Agent_Guru.platform.windows.integration import (
    WindowsIntegration,
    RegistryKeyNotFoundError,
    ServiceStatus,
    ProcessInfo,
    SystemInfo,
    CommandResult,
)


# Skip all tests if not on Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific tests"
)


class TestWindowsIntegration:
    """Unit tests for WindowsIntegration class."""
    
    def test_initialization(self):
        """Test Windows integration initialization."""
        integration = WindowsIntegration()
        assert integration is not None  # nosec B101
    
    def test_initialization_on_non_windows_raises_error(self):
        """Test that initialization fails on non-Windows platforms."""
        with patch('platform.system', return_value='Linux'):
            with pytest.raises(RuntimeError, match="requires Windows"):
                WindowsIntegration()
    
    # Registry Operations Tests
    
    def test_read_registry_key_success(self):
        """Test successful registry key read."""
        integration = WindowsIntegration()
        
        # Read a known registry key (Windows version)
        try:
            value = integration.read_registry_key(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                "ProductName"
            )
            assert value is not None  # nosec B101
            assert isinstance(value, str)  # nosec B101
            assert len(value) > 0  # nosec B101
        except PermissionError:
            pytest.skip("Insufficient permissions to read registry")
    
    def test_read_registry_key_not_found(self):
        """Test reading non-existent registry key."""
        integration = WindowsIntegration()
        
        with pytest.raises(RegistryKeyNotFoundError):
            integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\NonExistentKey",
                "NonExistentValue"
            )
    
    def test_write_registry_key_success(self):
        """Test successful registry key write."""
        integration = WindowsIntegration()
        
        # Write to HKEY_CURRENT_USER (doesn't require admin)
        test_key = r"SOFTWARE\AgentGuruTest"
        test_value = "TestValue"
        test_data = "TestData"
        
        try:
            # Write the key
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value,
                test_data
            )
            
            # Verify it was written
            read_value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value
            )
            assert read_value == test_data  # nosec B101
            
        finally:
            # Cleanup
            try:
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    test_value
                )
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_delete_registry_value_success(self):
        """Test successful registry value deletion."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruTest"
        test_value = "TestValue"
        test_data = "TestData"
        
        try:
            # Create a test value
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value,
                test_data
            )
            
            # Delete the value
            integration.delete_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value
            )
            
            # Verify it's deleted
            with pytest.raises(RegistryKeyNotFoundError):
                integration.read_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    test_value
                )
                
        finally:
            # Cleanup key if it exists
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_delete_registry_key_not_found(self):
        """Test deleting non-existent registry key."""
        integration = WindowsIntegration()
        
        with pytest.raises(RegistryKeyNotFoundError):
            integration.delete_registry_key(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\NonExistentKey",
                "NonExistentValue"
            )
    
    # Service Management Tests
    
    @pytest.mark.skipif(
        not hasattr(sys, 'getwindowsversion'),
        reason="Requires Windows with pywin32"
    )
    def test_get_service_status_success(self):
        """Test getting service status for a known service."""
        integration = WindowsIntegration()
        
        try:
            # Query a common Windows service (Windows Update)
            status = integration.get_service_status("wuauserv")
            
            assert isinstance(status, ServiceStatus)  # nosec B101
            assert status.name == "wuauserv"  # nosec B101
            assert status.status in ["running", "stopped", "paused", "starting", "stopping"]  # nosec B101
            assert status.startup_type in ["automatic", "manual", "disabled", "unknown"]  # nosec B101
            
        except RuntimeError as e:
            if "pywin32 required" in str(e):
                pytest.skip("pywin32 not available")
            raise
    
    @pytest.mark.skipif(
        not hasattr(sys, 'getwindowsversion'),
        reason="Requires Windows with pywin32"
    )
    def test_get_service_status_not_found(self):
        """Test getting status for non-existent service."""
        integration = WindowsIntegration()
        
        try:
            with pytest.raises(RuntimeError, match="Service not found"):
                integration.get_service_status("NonExistentService12345")
        except RuntimeError as e:
            if "pywin32 required" in str(e):
                pytest.skip("pywin32 not available")
            raise
    
    # Process Management Tests
    
    def test_get_process_list(self):
        """Test getting list of running processes."""
        integration = WindowsIntegration()
        
        processes = integration.get_process_list()
        
        assert isinstance(processes, list)  # nosec B101
        assert len(processes) > 0  # nosec B101
        
        # Check first process has valid data
        proc = processes[0]
        assert isinstance(proc, ProcessInfo)  # nosec B101
        assert proc.pid >= 0  # PID 0 is valid on Windows (System Idle Process)  # nosec B101
        assert len(proc.name) > 0  # nosec B101
        assert proc.status in ["running", "sleeping", "stopped", "zombie", "disk-sleep"]  # nosec B101
        assert proc.cpu_percent >= 0.0  # nosec B101
        assert proc.memory_percent >= 0.0  # nosec B101
        assert proc.create_time >= 0  # Can be 0 for system processes  # nosec B101
    
    def test_start_process_success(self):
        """Test starting a process."""
        integration = WindowsIntegration()
        
        # Start a simple process (cmd /c echo test)
        pid = integration.start_process("cmd.exe", ["/c", "echo", "test"])
        
        assert isinstance(pid, int)  # nosec B101
        assert pid > 0  # nosec B101
    
    def test_start_process_not_found(self):
        """Test starting non-existent executable."""
        integration = WindowsIntegration()
        
        with pytest.raises(FileNotFoundError):
            integration.start_process("nonexistent_executable_12345.exe", [])
    
    def test_terminate_process_success(self):
        """Test terminating a process."""
        integration = WindowsIntegration()
        
        # Start a process that will run for a while using ping (more reliable than timeout)
        pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
        
        # Give it a moment to start
        import time
        time.sleep(1.0)
        
        # Verify it exists
        try:
            import psutil
            proc = psutil.Process(pid)
            assert proc.is_running()  # nosec B101
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Terminate it
        result = integration.terminate_process(pid, force=False)
        assert result is True  # nosec B101
    
    def test_terminate_process_not_found(self):
        """Test terminating non-existent process."""
        integration = WindowsIntegration()
        
        # Use a PID that's unlikely to exist
        with pytest.raises(ProcessLookupError):
            integration.terminate_process(999999, force=False)
    
    def test_terminate_process_force_kill(self):
        """Test force killing a process."""
        integration = WindowsIntegration()
        
        # Start a process using ping (more reliable)
        pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
        
        # Give it a moment to start
        import time
        time.sleep(1.0)
        
        # Verify it exists
        try:
            import psutil
            proc = psutil.Process(pid)
            assert proc.is_running()  # nosec B101
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Force kill it
        result = integration.terminate_process(pid, force=True)
        assert result is True  # nosec B101
    
    # Command Execution Tests
    
    def test_execute_command_success(self):
        """Test executing a command successfully."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "echo", "Hello"])
        
        assert isinstance(result, CommandResult)  # nosec B101
        assert "Hello" in result.stdout  # nosec B101
        assert result.return_code == 0  # nosec B101
        assert result.execution_time >= 0  # nosec B101
    
    def test_execute_command_with_error(self):
        """Test executing a command that fails."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "exit", "1"])
        
        assert isinstance(result, CommandResult)  # nosec B101
        assert result.return_code == 1  # nosec B101
    
    def test_execute_command_not_found(self):
        """Test executing non-existent command."""
        integration = WindowsIntegration()
        
        with pytest.raises(RuntimeError):
            integration.execute_command("nonexistent_command_12345", [])
    
    # System Info Tests
    
    def test_get_system_info(self):
        """Test getting system information."""
        integration = WindowsIntegration()
        
        info = integration.get_system_info()
        
        assert isinstance(info, SystemInfo)  # nosec B101
        assert len(info.hostname) > 0  # nosec B101
        assert info.platform == "Windows"  # nosec B101
        assert len(info.platform_version) > 0  # nosec B101
        assert len(info.architecture) > 0  # nosec B101
        assert info.cpu_count_physical > 0  # nosec B101
        assert info.cpu_count_logical > 0  # nosec B101
        assert info.boot_time > 0  # nosec B101
    
    # Permission Tests
    
    def test_is_admin(self):
        """Test checking administrator status."""
        integration = WindowsIntegration()
        
        is_admin = integration.is_admin()
        
        assert isinstance(is_admin, bool)  # nosec B101
        # We can't assert the value since it depends on how tests are run


class TestWindowsIntegrationEdgeCases:
    """Edge case tests for Windows integration."""
    
    def test_read_registry_with_special_characters(self):
        """Test reading registry keys with special characters."""
        integration = WindowsIntegration()
        
        # Test with a key that has spaces and special chars
        try:
            value = integration.read_registry_key(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                "ProductName"
            )
            assert value is not None  # nosec B101
        except PermissionError as e:
            pytest.skip("Insufficient permissions")
    
    def test_process_list_handles_terminated_processes(self):
        """Test that process list handles processes that terminate during iteration."""
        integration = WindowsIntegration()
        
        # This should not raise even if processes terminate during iteration
        processes = integration.get_process_list()
        assert isinstance(processes, list)  # nosec B101
    
    def test_command_execution_with_empty_args(self):
        """Test command execution with empty arguments."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "echo"])
        assert isinstance(result, CommandResult)  # nosec B101
        assert result.return_code == 0  # nosec B101


class TestWindowsIntegrationIntegration:
    """Integration tests for Windows integration."""
    
    def test_full_registry_workflow(self):
        """Test complete registry workflow: write, read, delete."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruIntegrationTest"
        test_value = "TestValue"
        test_data = "TestData123"
        
        try:
            # Write
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value,
                test_data
            )
            
            # Read
            read_data = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value
            )
            assert read_data == test_data  # nosec B101
            
            # Delete
            integration.delete_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                test_value
            )
            
            # Verify deleted
            with pytest.raises(RegistryKeyNotFoundError):
                integration.read_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    test_value
                )
                
        finally:
            # Cleanup
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_process_lifecycle(self):
        """Test complete process lifecycle: start, query, terminate."""
        integration = WindowsIntegration()
        
        # Start process using ping (more reliable)
        pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
        assert pid > 0  # nosec B101
        
        # Give it time to start
        import time
        time.sleep(1.0)
        
        # Verify it exists
        try:
            import psutil
            proc = psutil.Process(pid)
            assert proc.is_running()  # nosec B101
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Verify it's in process list
        processes = integration.get_process_list()
        process_pids = [p.pid for p in processes]
        assert pid in process_pids  # nosec B101
        
        # Terminate
        result = integration.terminate_process(pid, force=True)
        assert result is True  # nosec B101
        
        # Give it time to terminate
        time.sleep(1.0)
        
        # Verify it's gone (or zombie)
        processes = integration.get_process_list()
        process_pids = [p.pid for p in processes if p.status != "zombie"]
        assert pid not in process_pids  # nosec B101
