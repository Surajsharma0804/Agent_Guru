"""
Unit tests for Windows platform integration.
Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import sys
import winreg
from unittest.mock import patch
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
        assert integration is not None
    
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
            assert value is not None
            assert isinstance(value, str)
            assert len(value) > 0
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
            assert read_value == test_data
            
        finally:
            # Cleanup
            try:
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    test_value
                )
            except Exception as e:
                _logger.warning("Suppressed exception: %s", e)
    
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
                _logger.warning("Suppressed exception: %s", e)
    
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
            
            assert isinstance(status, ServiceStatus)
            assert status.name == "wuauserv"
            assert status.status in ["running", "stopped", "paused", "starting", "stopping"]
            assert status.startup_type in ["automatic", "manual", "disabled", "unknown"]
            
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
        
        assert isinstance(processes, list)
        assert len(processes) > 0
        
        # Check first process has valid data
        proc = processes[0]
        assert isinstance(proc, ProcessInfo)
        assert proc.pid >= 0  # PID 0 is valid on Windows (System Idle Process)
        assert len(proc.name) > 0
        assert proc.status in ["running", "sleeping", "stopped", "zombie", "disk-sleep"]
        assert proc.cpu_percent >= 0.0
        assert proc.memory_percent >= 0.0
        assert proc.create_time >= 0  # Can be 0 for system processes
    
    def test_start_process_success(self):
        """Test starting a process."""
        integration = WindowsIntegration()
        
        # Start a simple process (cmd /c echo test)
        pid = integration.start_process("cmd.exe", ["/c", "echo", "test"])
        
        assert isinstance(pid, int)
        assert pid > 0
    
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
            assert proc.is_running()
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Terminate it
        result = integration.terminate_process(pid, force=False)
        assert result is True
    
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
            assert proc.is_running()
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Force kill it
        result = integration.terminate_process(pid, force=True)
        assert result is True
    
    # Command Execution Tests
    
    def test_execute_command_success(self):
        """Test executing a command successfully."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "echo", "Hello"])
        
        assert isinstance(result, CommandResult)
        assert "Hello" in result.stdout
        assert result.return_code == 0
        assert result.execution_time >= 0
    
    def test_execute_command_with_error(self):
        """Test executing a command that fails."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "exit", "1"])
        
        assert isinstance(result, CommandResult)
        assert result.return_code == 1
    
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
        
        assert isinstance(info, SystemInfo)
        assert len(info.hostname) > 0
        assert info.platform == "Windows"
        assert len(info.platform_version) > 0
        assert len(info.architecture) > 0
        assert info.cpu_count_physical > 0
        assert info.cpu_count_logical > 0
        assert info.boot_time > 0
    
    # Permission Tests
    
    def test_is_admin(self):
        """Test checking administrator status."""
        integration = WindowsIntegration()
        
        is_admin = integration.is_admin()
        
        assert isinstance(is_admin, bool)
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
            assert value is not None
        except PermissionError as e:
            pytest.skip("Insufficient permissions")
    
    def test_process_list_handles_terminated_processes(self):
        """Test that process list handles processes that terminate during iteration."""
        integration = WindowsIntegration()
        
        # This should not raise even if processes terminate during iteration
        processes = integration.get_process_list()
        assert isinstance(processes, list)
    
    def test_command_execution_with_empty_args(self):
        """Test command execution with empty arguments."""
        integration = WindowsIntegration()
        
        result = integration.execute_command("cmd", ["/c", "echo"])
        assert isinstance(result, CommandResult)
        assert result.return_code == 0


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
            assert read_data == test_data
            
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
                _logger.warning("Suppressed exception: %s", e)
    
    def test_process_lifecycle(self):
        """Test complete process lifecycle: start, query, terminate."""
        integration = WindowsIntegration()
        
        # Start process using ping (more reliable)
        pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
        assert pid > 0
        
        # Give it time to start
        import time
        time.sleep(1.0)
        
        # Verify it exists
        try:
            import psutil
            proc = psutil.Process(pid)
            assert proc.is_running()
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Verify it's in process list
        processes = integration.get_process_list()
        process_pids = [p.pid for p in processes]
        assert pid in process_pids
        
        # Terminate
        result = integration.terminate_process(pid, force=True)
        assert result is True
        
        # Give it time to terminate
        time.sleep(1.0)
        
        # Verify it's gone (or zombie)
        processes = integration.get_process_list()
        process_pids = [p.pid for p in processes if p.status != "zombie"]
        assert pid not in process_pids
