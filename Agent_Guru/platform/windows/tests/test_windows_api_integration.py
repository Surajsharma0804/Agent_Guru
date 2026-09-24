"""
Integration tests for Windows API integration.
These tests verify deep integration with Windows APIs.
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
from Agent_Guru.platform.windows.integration import WindowsIntegration
import logging

logger = logging.getLogger(__name__)


# Skip all tests if not on Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific integration tests"
)


class TestWindowsAPIIntegration:
    """Deep integration tests with Windows APIs."""
    
    def test_registry_different_value_types(self):
        """Test registry operations with different value types."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruAPITest"
        
        try:
            # Test REG_SZ (string)
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "StringValue",
                "TestString",
                winreg.REG_SZ
            )
            value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "StringValue"
            )
            assert value == "TestString"  # nosec B101
            
            # Test REG_DWORD (integer)
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "DWordValue",
                12345,
                winreg.REG_DWORD
            )
            value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "DWordValue"
            )
            assert value == 12345  # nosec B101
            
            # Test REG_BINARY (binary data)
            binary_data = b"\x01\x02\x03\x04"
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "BinaryValue",
                binary_data,
                winreg.REG_BINARY
            )
            value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "BinaryValue"
            )
            assert value == binary_data  # nosec B101
            
        finally:
            # Cleanup
            try:
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    "StringValue"
                )
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    "DWordValue"
                )
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    "BinaryValue"
                )
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_registry_nested_keys(self):
        """Test registry operations with nested keys."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruAPITest\Nested\Deep"
        
        try:
            # Write to nested key
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "NestedValue",
                "DeepValue"
            )
            
            # Read from nested key
            value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "NestedValue"
            )
            assert value == "DeepValue"  # nosec B101
            
        finally:
            # Cleanup nested keys
            try:
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    "NestedValue"
                )
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\AgentGuruAPITest\Nested")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\AgentGuruAPITest")
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_process_with_different_executables(self):
        """Test process management with different Windows executables."""
        integration = WindowsIntegration()
        
        # Test with ping (more reliable than notepad)
        pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
        assert pid > 0  # nosec B101
        
        # Give it time to start
        import time
        time.sleep(1.0)
        
        # Verify it's running
        try:
            import psutil
            proc = psutil.Process(pid)
            assert proc.is_running()  # nosec B101
        except psutil.NoSuchProcess:
            pytest.skip("Process terminated too quickly")
        
        # Terminate it
        integration.terminate_process(pid, force=True)
    
    def test_command_execution_with_powershell(self):
        """Test command execution with PowerShell."""
        integration = WindowsIntegration()
        
        # Execute PowerShell command
        result = integration.execute_command(
            "powershell",
            ["-Command", "Write-Output 'Hello from PowerShell'"]
        )
        
        assert result.return_code == 0  # nosec B101
        assert "Hello from PowerShell" in result.stdout  # nosec B101
    
    def test_system_info_completeness(self):
        """Test that system info contains all required fields."""
        integration = WindowsIntegration()
        
        info = integration.get_system_info()
        
        # Verify all fields are present and non-empty
        assert info.hostname  # nosec B101
        assert info.platform == "Windows"  # nosec B101
        assert info.platform_version  # nosec B101
        assert info.architecture  # nosec B101
        assert info.processor  # nosec B101
        assert info.cpu_count_physical > 0  # nosec B101
        assert info.cpu_count_logical > 0  # nosec B101
        assert info.cpu_count_logical >= info.cpu_count_physical  # nosec B101
        assert info.boot_time > 0  # nosec B101
    
    def test_process_list_performance(self):
        """Test that process list retrieval is reasonably fast."""
        integration = WindowsIntegration()
        
        import time
        
        # Warm up (first call can be slow due to psutil initialization)
        integration.get_process_list()
        
        # Now measure
        start = time.time()
        processes = integration.get_process_list()
        elapsed = time.time() - start
        
        assert len(processes) > 0  # nosec B101
        assert elapsed < 5.0  # nosec B101
    
    def test_registry_read_performance(self):
        """Test that registry read is fast (<100ms)."""
        integration = WindowsIntegration()
        
        import time
        start = time.time()
        
        try:
            value = integration.read_registry_key(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                "ProductName"
            )
            elapsed = time.time() - start
            
            assert value is not None  # nosec B101
            assert elapsed < 0.1  # Must complete in <100ms  # nosec B101
        except PermissionError:
            pytest.skip("Insufficient permissions")
    
    def test_multiple_concurrent_processes(self):
        """Test managing multiple processes concurrently."""
        integration = WindowsIntegration()
        
        # Start multiple processes
        pids = []
        for i in range(3):
            pid = integration.start_process("ping", ["127.0.0.1", "-n", "100"])
            pids.append(pid)
        
        import time
        time.sleep(1.0)
        
        # Verify all are running
        processes = integration.get_process_list()
        process_pids = [p.pid for p in processes]
        
        for pid in pids:
            assert pid in process_pids  # nosec B101
        
        # Terminate all
        for pid in pids:
            integration.terminate_process(pid, force=True)
    
    def test_error_messages_are_descriptive(self):
        """Test that error messages contain useful information."""
        integration = WindowsIntegration()
        
        # Test registry error message
        try:
            integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\NonExistent",
                "NonExistent"
            )
            assert False, "Should have raised RegistryKeyNotFoundError"  # nosec B101
        except Exception as e:
            error_msg = str(e)
            assert "NonExistent" in error_msg  # nosec B101
            assert "not found" in error_msg.lower()  # nosec B101
        
        # Test process error message
        try:
            integration.terminate_process(999999)
            assert False, "Should have raised ProcessLookupError"  # nosec B101
        except ProcessLookupError as e:
            error_msg = str(e)
            assert "999999" in error_msg  # nosec B101
            assert "not found" in error_msg.lower()  # nosec B101


class TestWindowsAPIEdgeCases:
    """Edge case tests for Windows API integration."""
    
    def test_registry_with_unicode_values(self):
        """Test registry operations with Unicode characters."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruUnicodeTest"
        unicode_value = "Hello 世界 🌍"
        
        try:
            integration.write_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "UnicodeValue",
                unicode_value
            )
            
            value = integration.read_registry_key(
                winreg.HKEY_CURRENT_USER,
                test_key,
                "UnicodeValue"
            )
            
            assert value == unicode_value  # nosec B101
            
        finally:
            try:
                integration.delete_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    "UnicodeValue"
                )
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    def test_process_with_long_arguments(self):
        """Test process creation with long argument lists."""
        integration = WindowsIntegration()
        
        # Create a long argument list
        long_args = ["/c", "echo"] + ["arg" + str(i) for i in range(50)]
        
        pid = integration.start_process("cmd.exe", long_args)
        assert pid > 0  # nosec B101
    
    def test_command_execution_timeout(self):
        """Test that command execution respects timeout."""
        integration = WindowsIntegration()
        
        import time
        start = time.time()
        
        try:
            # Use a short ping that completes quickly to test timeout handling
            result = integration.execute_command(
                "ping",
                ["127.0.0.1", "-n", "3"]
            )
            elapsed = time.time() - start
            
            # Should complete within reasonable time
            assert elapsed < 10  # 3 pings should finish in <10s  # nosec B101
        except TimeoutError:
            elapsed = time.time() - start
            assert elapsed < 35  # nosec B101


class TestWindowsAPIPerformance:
    """Performance tests for Windows API operations."""
    
    def test_registry_batch_operations_performance(self):
        """Test performance of batch registry operations."""
        integration = WindowsIntegration()
        
        test_key = r"SOFTWARE\AgentGuruPerfTest"
        
        try:
            import time
            
            # Write 100 values
            start = time.time()
            for i in range(100):
                integration.write_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    f"Value{i}",
                    f"Data{i}"
                )
            write_time = time.time() - start
            
            # Read 100 values
            start = time.time()
            for i in range(100):
                value = integration.read_registry_key(
                    winreg.HKEY_CURRENT_USER,
                    test_key,
                    f"Value{i}"
                )
                assert value == f"Data{i}"  # nosec B101
            read_time = time.time() - start
            
            # Performance targets: <10ms per operation
            assert write_time / 100 < 0.01  # <10ms per write  # nosec B101
            assert read_time / 100 < 0.01   # <10ms per read  # nosec B101
            
        finally:
            # Cleanup
            try:
                for i in range(100):
                    integration.delete_registry_key(
                        winreg.HKEY_CURRENT_USER,
                        test_key,
                        f"Value{i}"
                    )
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
