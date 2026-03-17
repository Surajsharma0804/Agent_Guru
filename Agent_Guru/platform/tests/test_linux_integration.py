"""
Unit tests for Linux platform integration.

Tests cover:
- D-Bus operations (Linux only)
- systemd service control
- Process management
- Permission validation
- Error handling
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from Agent_Guru.platform.linux.integration import (
    LinuxIntegration,
    DBusError,
    CommandResult,
    ProcessInfo,
    ServiceStatus,
    SystemInfo
)


# Helper: create a LinuxIntegration instance with platform mocked to Linux
def _make_integration():
    with patch('platform.system', return_value='Linux'):
        return LinuxIntegration()


class TestLinuxIntegrationInitialization:
    """Test Linux integration initialization."""

    def test_initialization_success(self):
        """Test successful initialization on Linux."""
        with patch('platform.system', return_value='Linux'):
            integration = LinuxIntegration()
            assert integration is not None

    def test_initialization_wrong_platform(self):
        """Test initialization fails on non-Linux platform."""
        with patch('platform.system', return_value='Windows'):
            with pytest.raises(RuntimeError, match="requires Linux"):
                LinuxIntegration()


class TestSystemdServiceManagement:
    """Test systemd service management operations."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_get_service_status_running(self, integration):
        """Test getting status of running service."""
        with patch('subprocess.run') as mock_run:
            # Mock systemctl is-active
            mock_run.return_value = Mock(
                stdout="active\n",
                stderr="",
                returncode=0
            )
            
            status = integration.get_systemd_service_status("ssh")
            
            assert status.name == "ssh.service"
            assert status.status == "running"
            assert mock_run.called
    
    def test_get_service_status_stopped(self, integration):
        """Test getting status of stopped service."""
        with patch('subprocess.run') as mock_run:
            # Mock systemctl is-active
            mock_run.return_value = Mock(
                stdout="inactive\n",
                stderr="",
                returncode=3
            )
            
            status = integration.get_systemd_service_status("nginx")
            
            assert status.name == "nginx.service"
            assert status.status == "stopped"
    
    def test_get_service_status_adds_suffix(self, integration):
        """Test that .service suffix is added if missing."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="active\n",
                stderr="",
                returncode=0
            )
            
            status = integration.get_systemd_service_status("ssh")
            
            # Check that systemctl was called with .service suffix
            call_args = mock_run.call_args_list[0][0][0]
            assert "ssh.service" in call_args
    
    def test_get_service_status_timeout(self, integration):
        """Test service status query timeout."""
        with patch('subprocess.run', side_effect=TimeoutError("Timeout")):
            with pytest.raises(RuntimeError, match="Timeout"):
                integration.get_systemd_service_status("slow-service")
    
    def test_start_service_success(self, integration):
        """Test starting a service successfully."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="",
                returncode=0
            )
            
            result = integration.start_systemd_service("nginx")
            
            assert result is True
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert "systemctl" in call_args
            assert "start" in call_args
            assert "nginx.service" in call_args
    
    def test_start_service_permission_denied(self, integration):
        """Test starting service without permissions."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="Permission denied",
                returncode=1
            )
            
            with pytest.raises(PermissionError, match="Permission denied"):
                integration.start_systemd_service("nginx")
    
    def test_stop_service_success(self, integration):
        """Test stopping a service successfully."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="",
                returncode=0
            )
            
            result = integration.stop_systemd_service("nginx")
            
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "stop" in call_args
    
    def test_restart_service_success(self, integration):
        """Test restarting a service successfully."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="",
                returncode=0
            )
            
            result = integration.restart_systemd_service("nginx")
            
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "restart" in call_args


class TestDBusOperations:
    """Test D-Bus operations (requires dbus-python)."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    @pytest.mark.skipif(
        not hasattr(sys.modules.get('Agent_Guru.platform.linux.integration', object()), 'DBUS_AVAILABLE'),
        reason="dbus-python not available"
    )
    def test_query_dbus_service_no_dbus(self, integration):
        """Test D-Bus query when dbus-python not available."""
        with patch('Agent_Guru.platform.linux.integration.DBUS_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="dbus-python required"):
                integration.query_dbus_service(
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1",
                    "org.freedesktop.systemd1.Manager",
                    "ListUnits"
                )
    
    def test_query_dbus_service_not_connected(self, integration):
        """Test D-Bus query when bus not connected but dbus is available."""
        import Agent_Guru.platform.linux.integration as _linux_mod

        integration._system_bus = None

        with patch.object(_linux_mod, 'DBUS_AVAILABLE', True):
            with pytest.raises(DBusError, match="not connected"):
                integration.query_dbus_service(
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1",
                    "org.freedesktop.systemd1.Manager",
                    "ListUnits"
                )


class TestProcessManagement:
    """Test process management operations."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_get_process_list(self, integration):
        """Test getting list of running processes."""
        with patch('psutil.process_iter') as mock_iter:
            # Mock process data
            mock_proc = Mock()
            mock_proc.info = {
                'pid': 1234,
                'name': 'test_process',
                'status': 'running',
                'cpu_percent': 5.0,
                'memory_percent': 2.5,
                'create_time': 1234567890.0
            }
            mock_iter.return_value = [mock_proc]
            
            processes = integration.get_process_list()
            
            assert len(processes) == 1
            assert processes[0].pid == 1234
            assert processes[0].name == 'test_process'
            assert processes[0].status == 'running'
    
    def test_get_process_list_handles_no_such_process(self, integration):
        """Test that process list handles terminated processes."""
        import psutil

        with patch('psutil.process_iter') as mock_iter:
            # Mock process whose .info dict raises NoSuchProcess when accessed
            mock_proc = Mock()
            mock_proc.info = Mock(side_effect=psutil.NoSuchProcess(1234))
            # Make .info raise when iterated as a dict (subscript access)
            mock_proc.info.__getitem__ = Mock(side_effect=psutil.NoSuchProcess(1234))
            mock_iter.return_value = [mock_proc]

            # Patch process_iter to raise NoSuchProcess on the proc
            # The real fix: make proc.info a dict that raises on access
            # Actually the simplest approach: make process_iter yield a proc
            # whose .info property raises NoSuchProcess
            mock_proc2 = Mock()
            type(mock_proc2).info = property(lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(1234)))
            mock_iter.return_value = [mock_proc2]

            processes = integration.get_process_list()

            # Should skip the terminated process
            assert len(processes) == 0
    
    def test_start_process_success(self, integration):
        """Test starting a process successfully."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.pid = 5678
            mock_popen.return_value = mock_process
            
            pid = integration.start_process("/bin/echo", ["hello"])
            
            assert pid == 5678
            assert mock_popen.called
    
    def test_start_process_not_found(self, integration):
        """Test starting non-existent process."""
        with patch('subprocess.Popen', side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError, match="not found"):
                integration.start_process("/nonexistent", [])
    
    def test_start_process_permission_denied(self, integration):
        """Test starting process without permissions."""
        with patch('subprocess.Popen', side_effect=PermissionError()):
            with pytest.raises(PermissionError, match="Permission denied"):
                integration.start_process("/bin/restricted", [])
    
    def test_terminate_process_graceful(self, integration):
        """Test graceful process termination (SIGTERM)."""
        with patch('psutil.Process') as mock_process_class:
            mock_process = Mock()
            mock_process_class.return_value = mock_process
            
            result = integration.terminate_process(1234, force=False)
            
            assert result is True
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_not_called()
    
    def test_terminate_process_force(self, integration):
        """Test force process termination (SIGKILL)."""
        with patch('psutil.Process') as mock_process_class:
            mock_process = Mock()
            mock_process_class.return_value = mock_process
            
            result = integration.terminate_process(1234, force=True)
            
            assert result is True
            mock_process.kill.assert_called_once()
            mock_process.terminate.assert_not_called()
    
    def test_terminate_process_not_found(self, integration):
        """Test terminating non-existent process."""
        import psutil
        
        with patch('psutil.Process', side_effect=psutil.NoSuchProcess(1234)):
            with pytest.raises(ProcessLookupError, match="not found"):
                integration.terminate_process(1234)
    
    def test_terminate_process_access_denied(self, integration):
        """Test terminating process without permissions."""
        import psutil
        
        with patch('psutil.Process') as mock_process_class:
            mock_process = Mock()
            mock_process.terminate.side_effect = psutil.AccessDenied(1234)
            mock_process_class.return_value = mock_process
            
            with pytest.raises(PermissionError, match="Permission denied"):
                integration.terminate_process(1234)


class TestCommandExecution:
    """Test command execution operations."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_execute_command_success(self, integration):
        """Test successful command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="Hello\n",
                stderr="",
                returncode=0
            )
            
            result = integration.execute_command("echo", ["Hello"])
            
            assert isinstance(result, CommandResult)
            assert result.stdout == "Hello\n"
            assert result.stderr == ""
            assert result.return_code == 0
            assert result.execution_time >= 0
    
    def test_execute_command_with_error(self, integration):
        """Test command execution with non-zero return code."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="Error message\n",
                returncode=1
            )
            
            result = integration.execute_command("false", [])
            
            assert result.return_code == 1
            assert "Error message" in result.stderr
    
    def test_execute_command_timeout(self, integration):
        """Test command execution timeout."""
        import subprocess
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("cmd", 30)):
            with pytest.raises(TimeoutError, match="timed out"):
                integration.execute_command("sleep", ["100"])


class TestSystemInfo:
    """Test system information retrieval."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_get_system_info(self, integration):
        """Test getting system information."""
        with patch('socket.gethostname', return_value='test-host'):
            with patch('platform.release', return_value='5.15.0'):
                with patch('platform.machine', return_value='x86_64'):
                    with patch('platform.processor', return_value='Intel'):
                        with patch('psutil.cpu_count', side_effect=[4, 8]):
                            with patch('psutil.boot_time', return_value=1234567890.0):
                                info = integration.get_system_info()
        
        assert isinstance(info, SystemInfo)
        assert info.hostname == 'test-host'
        assert info.platform == 'Linux'
        assert info.platform_version == '5.15.0'
        assert info.architecture == 'x86_64'
        assert info.cpu_count_physical == 4
        assert info.cpu_count_logical == 8
        assert info.boot_time == 1234567890.0


class TestPermissionValidation:
    """Test permission validation operations."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_is_root_true(self, integration):
        """Test root detection when running as root."""
        with patch('os.geteuid', return_value=0, create=True):
            assert integration.is_root() is True
    
    def test_is_root_false(self, integration):
        """Test root detection when not running as root."""
        with patch('os.geteuid', return_value=1000, create=True):
            assert integration.is_root() is False
    
    def test_require_root_success(self, integration):
        """Test require_root when running as root."""
        with patch('os.geteuid', return_value=0, create=True):
            # Should not raise
            integration.require_root()
    
    def test_require_root_failure(self, integration):
        """Test require_root when not running as root."""
        with patch('os.geteuid', return_value=1000, create=True):
            with pytest.raises(PermissionError, match="root privileges"):
                integration.require_root()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()
    
    def test_service_status_systemctl_not_found(self, integration):
        """Test service status when systemctl not found."""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="systemctl not found"):
                integration.get_systemd_service_status("test")
    
    def test_command_execution_generic_error(self, integration):
        """Test command execution with generic error."""
        with patch('subprocess.run', side_effect=Exception("Generic error")):
            with pytest.raises(RuntimeError, match="Error executing"):
                integration.execute_command("test", [])


@pytest.mark.integration
class TestLinuxIntegrationReal:
    """Integration tests that verify real behaviour via mocks (cross-platform safe)."""

    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        return _make_integration()

    def test_real_system_info(self, integration):
        """Test getting system information returns correct structure."""
        with patch('socket.gethostname', return_value='test-host'):
            with patch('platform.release', return_value='5.15.0'):
                with patch('platform.machine', return_value='x86_64'):
                    with patch('platform.processor', return_value='Intel'):
                        with patch('psutil.cpu_count', side_effect=[4, 8]):
                            with patch('psutil.boot_time', return_value=1234567890.0):
                                info = integration.get_system_info()

        assert info.platform == "Linux"
        assert len(info.hostname) > 0
        assert info.cpu_count_logical > 0
        assert info.boot_time > 0

    def test_real_process_list(self, integration):
        """Test getting process list returns valid data."""
        with patch('psutil.process_iter') as mock_iter:
            mock_proc = Mock()
            mock_proc.info = {
                'pid': 1,
                'name': 'systemd',
                'status': 'running',
                'cpu_percent': 0.0,
                'memory_percent': 0.1,
                'create_time': 1234567890.0,
            }
            mock_iter.return_value = [mock_proc]

            processes = integration.get_process_list()

        assert len(processes) > 0
        for proc in processes:
            assert proc.pid > 0
            assert len(proc.name) > 0
            assert proc.status in [
                'running', 'sleeping', 'stopped', 'zombie',
                'disk-sleep', 'idle',
            ]

    def test_real_command_execution(self, integration):
        """Test command execution returns complete result."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout="test\n", stderr="", returncode=0)
            result = integration.execute_command("echo", ["test"])

        assert result.return_code == 0
        assert "test" in result.stdout
        assert result.execution_time >= 0

    def test_real_permission_check(self, integration):
        """Test permission check returns boolean."""
        with patch('os.geteuid', return_value=1000, create=True):
            is_root = integration.is_root()

        assert isinstance(is_root, bool)
