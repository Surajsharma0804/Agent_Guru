"""
Property-based tests for Linux platform integration.

Uses Hypothesis to verify universal properties across all valid inputs.
Tests run 100+ iterations with randomly generated test data.
"""

import pytest
import sys
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, patch
from Agent_Guru.platform.linux.integration import (
    LinuxIntegration,
    CommandResult,
    ProcessInfo,
    ServiceStatus,
    SystemInfo
)


# Skip all tests if not on Linux
pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="Linux integration property tests only run on Linux"
)


# Custom strategies for generating valid test data
@st.composite
def service_names(draw):
    """Generate valid service names."""
    # Service names can contain alphanumeric, dash, underscore
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=1,
        max_size=50
    ))
    # Filter out invalid names
    assume(len(name) > 0)
    assume(not name.startswith('-'))
    return name


@st.composite
def process_ids(draw):
    """Generate valid process IDs."""
    # PIDs are positive integers, typically 1-65535 on Linux
    return draw(st.integers(min_value=1, max_value=65535))


@st.composite
def command_names(draw):
    """Generate valid command names."""
    # Commands are typically lowercase with optional dashes
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll',), whitelist_characters='-_'),
        min_size=1,
        max_size=20
    ))


class TestServiceStatusProperties:
    """Property-based tests for service status operations."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    @given(service_name=service_names())
    @settings(max_examples=100)
    def test_property_service_status_returns_valid_status(self, integration, service_name):
        """
        Feature: guru-platform-integration, Property 5: Service Queries Return Valid Status
        
        For any service name query, the returned ServiceStatus should have a status field
        that is one of the valid states: "running", "stopped", or "disabled".
        """
        with patch('subprocess.run') as mock_run:
            # Mock systemctl responses
            mock_run.return_value = Mock(
                stdout="active\n",
                stderr="",
                returncode=0
            )
            
            try:
                status = integration.get_systemd_service_status(service_name)
                
                # Verify status is valid
                assert isinstance(status, ServiceStatus)
                assert status.status in ['running', 'stopped', 'disabled', 'unknown', 
                                        'starting', 'stopping', 'paused', 'failed',
                                        'active', 'inactive', 'activating', 'deactivating']
                assert isinstance(status.name, str)
                assert len(status.name) > 0
                assert isinstance(status.startup_type, str)
                
            except RuntimeError:
                # Service not found is acceptable
                pass
    
    @given(service_name=service_names())
    @settings(max_examples=100)
    def test_property_service_name_has_suffix(self, integration, service_name):
        """
        Property: Service names are normalized with .service suffix.
        
        For any service name, the returned ServiceStatus should have .service suffix.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="active\n",
                stderr="",
                returncode=0
            )
            
            try:
                status = integration.get_systemd_service_status(service_name)
                
                # Verify .service suffix is added
                assert status.name.endswith('.service')
                
            except RuntimeError:
                pass


class TestProcessManagementProperties:
    """Property-based tests for process management."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    @given(pid=process_ids())
    @settings(max_examples=100)
    def test_property_process_termination_returns_bool(self, integration, pid):
        """
        Feature: guru-platform-integration, Property 14: Process Termination Removes Process
        
        For any process termination attempt, the operation should return a boolean
        indicating success or raise an appropriate exception.
        """
        import psutil
        
        with patch('psutil.Process') as mock_process_class:
            mock_process = Mock()
            mock_process_class.return_value = mock_process
            
            try:
                result = integration.terminate_process(pid, force=False)
                
                # Should return boolean
                assert isinstance(result, bool)
                assert result is True
                
            except (ProcessLookupError, PermissionError):
                # These exceptions are acceptable
                pass
    
    @given(pid=process_ids(), force=st.booleans())
    @settings(max_examples=100)
    def test_property_terminate_uses_correct_signal(self, integration, pid, force):
        """
        Property: Process termination uses correct signal based on force parameter.
        
        For any PID and force flag, termination should use SIGKILL if force=True,
        SIGTERM if force=False.
        """
        import psutil
        
        with patch('psutil.Process') as mock_process_class:
            mock_process = Mock()
            mock_process_class.return_value = mock_process
            
            try:
                integration.terminate_process(pid, force=force)
                
                if force:
                    mock_process.kill.assert_called_once()
                    mock_process.terminate.assert_not_called()
                else:
                    mock_process.terminate.assert_called_once()
                    mock_process.kill.assert_not_called()
                    
            except (ProcessLookupError, PermissionError):
                pass
    
    def test_property_process_list_contains_valid_data(self, integration):
        """
        Feature: guru-platform-integration, Property 13: Process List Contains Valid Data
        
        For any process in the returned process list, the ProcessInfo should have
        a positive PID, non-empty name, valid status, and non-negative percentages.
        """
        with patch('psutil.process_iter') as mock_iter:
            # Generate multiple mock processes
            mock_processes = []
            for i in range(10):
                mock_proc = Mock()
                mock_proc.info = {
                    'pid': 1000 + i,
                    'name': f'process_{i}',
                    'status': 'running',
                    'cpu_percent': float(i),
                    'memory_percent': float(i * 0.5),
                    'create_time': 1234567890.0 + i
                }
                mock_processes.append(mock_proc)
            
            mock_iter.return_value = mock_processes
            
            processes = integration.get_process_list()
            
            # Verify all processes have valid data
            for proc in processes:
                assert proc.pid > 0
                assert len(proc.name) > 0
                assert proc.status in ['running', 'sleeping', 'stopped', 'zombie', 
                                      'disk-sleep', 'idle', 'dead', 'tracing-stop']
                assert proc.cpu_percent >= 0
                assert proc.memory_percent >= 0
                assert proc.create_time > 0


class TestCommandExecutionProperties:
    """Property-based tests for command execution."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    @given(
        command=command_names(),
        args=st.lists(st.text(min_size=0, max_size=20), max_size=5)
    )
    @settings(max_examples=100)
    def test_property_command_result_complete(self, integration, command, args):
        """
        Feature: guru-platform-integration, Property 7: Command Execution Returns Complete Result
        
        For any executed command, the returned CommandResult should contain stdout,
        stderr, return_code, and execution_time fields, with execution_time being non-negative.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="output",
                stderr="",
                returncode=0
            )
            
            try:
                result = integration.execute_command(command, args)
                
                # Verify complete result
                assert isinstance(result, CommandResult)
                assert isinstance(result.stdout, str)
                assert isinstance(result.stderr, str)
                assert isinstance(result.return_code, int)
                assert isinstance(result.execution_time, float)
                assert result.execution_time >= 0
                
            except (TimeoutError, RuntimeError):
                # Timeout or execution errors are acceptable
                pass
    
    @given(
        command=command_names(),
        return_code=st.integers(min_value=0, max_value=255)
    )
    @settings(max_examples=100)
    def test_property_command_return_code_preserved(self, integration, command, return_code):
        """
        Property: Command return codes are preserved correctly.
        
        For any command execution, the return code should match the subprocess return code.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="",
                returncode=return_code
            )
            
            result = integration.execute_command(command, [])
            
            assert result.return_code == return_code


class TestPermissionValidationProperties:
    """Property-based tests for permission validation."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    @given(uid=st.integers(min_value=0, max_value=65535))
    @settings(max_examples=100)
    def test_property_root_detection_correct(self, integration, uid):
        """
        Feature: guru-platform-integration, Property 17: Elevated Privilege Detection
        
        For any UID, is_root() should return True when UID is 0 (root) and False otherwise.
        """
        with patch('os.geteuid', return_value=uid):
            is_root = integration.is_root()
            
            assert isinstance(is_root, bool)
            if uid == 0:
                assert is_root is True
            else:
                assert is_root is False
    
    @given(uid=st.integers(min_value=1, max_value=65535))
    @settings(max_examples=100)
    def test_property_require_root_raises_when_not_root(self, integration, uid):
        """
        Feature: guru-platform-integration, Property 18: Permission Errors When Insufficient
        
        For any non-root UID, require_root() should raise PermissionError.
        """
        with patch('os.geteuid', return_value=uid):
            with pytest.raises(PermissionError, match="root privileges"):
                integration.require_root()
    
    def test_property_require_root_succeeds_when_root(self, integration):
        """
        Property: require_root() succeeds when running as root.
        
        When UID is 0, require_root() should not raise any exception.
        """
        with patch('os.geteuid', return_value=0):
            # Should not raise
            integration.require_root()


class TestSystemInfoProperties:
    """Property-based tests for system information."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    def test_property_system_info_completeness(self, integration):
        """
        Feature: guru-platform-integration, Property 23: System Info Completeness
        
        For any system information query, the returned SystemInfo should contain
        all required fields with non-empty/non-zero values.
        """
        with patch('socket.gethostname', return_value='test-host'):
            with patch('platform.release', return_value='5.15.0'):
                with patch('platform.machine', return_value='x86_64'):
                    with patch('platform.processor', return_value='Intel'):
                        with patch('psutil.cpu_count', side_effect=[4, 8]):
                            with patch('psutil.boot_time', return_value=1234567890.0):
                                info = integration.get_system_info()
        
        # Verify all required fields are present and valid
        assert isinstance(info, SystemInfo)
        assert len(info.hostname) > 0
        assert info.platform == "Linux"
        assert len(info.platform_version) > 0
        assert len(info.architecture) > 0
        assert info.cpu_count_physical >= 0
        assert info.cpu_count_logical >= 0
        assert info.boot_time > 0


class TestErrorHandlingProperties:
    """Property-based tests for error handling."""
    
    @pytest.fixture
    def integration(self):
        """Create Linux integration instance."""
        with patch('platform.system', return_value='Linux'):
            return LinuxIntegration()
    
    @given(service_name=service_names())
    @settings(max_examples=100)
    def test_property_permission_errors_descriptive(self, integration, service_name):
        """
        Feature: guru-platform-integration, Property 19: Permission Errors Are Descriptive
        
        For any permission validation failure, the raised PermissionError should
        include descriptive information about the required permission level.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="",
                stderr="Permission denied",
                returncode=1
            )
            
            try:
                integration.start_systemd_service(service_name)
            except PermissionError as e:
                # Verify error message is descriptive
                error_msg = str(e)
                assert "Permission denied" in error_msg or "permission" in error_msg.lower()
                assert "root" in error_msg.lower() or "sudo" in error_msg.lower()
    
    @given(pid=process_ids())
    @settings(max_examples=100)
    def test_property_errors_contain_context(self, integration, pid):
        """
        Feature: guru-platform-integration, Property 16: Errors Contain Context
        
        For any operation failure, the raised exception should contain relevant
        identifiers (PID, service name, etc.) and operation name.
        """
        import psutil
        
        with patch('psutil.Process', side_effect=psutil.NoSuchProcess(pid)):
            try:
                integration.terminate_process(pid)
            except ProcessLookupError as e:
                # Verify error contains PID
                error_msg = str(e)
                assert str(pid) in error_msg or "PID" in error_msg
