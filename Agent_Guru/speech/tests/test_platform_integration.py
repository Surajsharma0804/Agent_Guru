"""
Integration tests for platform integration.

Tests audio device access and system control operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List

from Agent_Guru.speech.platform_integration import (
    PlatformIntegration,
    AudioDeviceInfo
)
from Agent_Guru.speech.exceptions import AudioInputError, GuruSpeechError
from Agent_Guru.platform.os_controller import OperationResult, OperationCategory


class TestPlatformIntegrationAudioDevices:
    """Tests for audio device management."""
    
    def test_list_audio_devices(self):
        """Test listing audio devices."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices') as mock_query:
            with patch('sounddevice.default') as mock_default:
                # Mock device list
                mock_query.return_value = [
                    {
                        'name': 'Microphone 1',
                        'max_input_channels': 2,
                        'default_samplerate': 44100.0
                    },
                    {
                        'name': 'Microphone 2',
                        'max_input_channels': 1,
                        'default_samplerate': 16000.0
                    },
                    {
                        'name': 'Speaker',
                        'max_input_channels': 0,  # Output only
                        'default_samplerate': 48000.0
                    }
                ]
                mock_default.device = [0, None]  # Default input device is 0
                
                devices = integration.list_audio_devices()
                
                # Should only return input devices (max_input_channels > 0)
                assert len(devices) == 2
                assert devices[0].name == 'Microphone 1'
                assert devices[0].channels == 2
                assert devices[0].is_default is True
                assert devices[1].name == 'Microphone 2'
                assert devices[1].is_default is False
    
    def test_list_audio_devices_error(self):
        """Test error handling when listing devices fails."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices', side_effect=Exception("Device error")):
            with pytest.raises(AudioInputError, match="Failed to list audio devices"):
                integration.list_audio_devices()
    
    def test_get_default_audio_device(self):
        """Test getting default audio device."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices') as mock_query:
            with patch('sounddevice.default') as mock_default:
                mock_query.return_value = [
                    {
                        'name': 'Default Mic',
                        'max_input_channels': 1,
                        'default_samplerate': 16000.0
                    }
                ]
                mock_default.device = [0, None]
                
                device = integration.get_default_audio_device()
                
                assert device is not None
                assert device.name == 'Default Mic'
                assert device.is_default is True
    
    def test_get_default_audio_device_none(self):
        """Test when no default device is available."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices', return_value=[]):
            with patch('sounddevice.default') as mock_default:
                mock_default.device = [None, None]
                
                device = integration.get_default_audio_device()
                assert device is None
    
    def test_validate_audio_device_valid(self):
        """Test validating a valid audio device."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices') as mock_query:
            with patch('sounddevice.default') as mock_default:
                mock_query.return_value = [
                    {
                        'name': 'Mic',
                        'max_input_channels': 1,
                        'default_samplerate': 16000.0
                    }
                ]
                mock_default.device = [0, None]
                
                assert integration.validate_audio_device(0) is True
    
    def test_validate_audio_device_invalid(self):
        """Test validating an invalid audio device."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices', return_value=[]):
            with patch('sounddevice.default') as mock_default:
                mock_default.device = [None, None]
                
                assert integration.validate_audio_device(999) is False


class TestPlatformIntegrationSystemControl:
    """Tests for system control operations."""
    
    def test_set_system_volume_success(self):
        """Test setting system volume successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'set_volume') as mock_set:
            mock_set.return_value = OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message="Volume set to 50%"
            )
            
            result = integration.set_system_volume(50)
            
            assert result.success is True
            mock_set.assert_called_once_with(50)
    
    def test_set_system_volume_failure(self):
        """Test error handling when setting volume fails."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'set_volume') as mock_set:
            mock_set.return_value = OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message="Volume control not supported"
            )
            
            with pytest.raises(GuruSpeechError, match="Failed to set volume"):
                integration.set_system_volume(50)
    
    def test_set_system_brightness_success(self):
        """Test setting system brightness successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'set_brightness') as mock_set:
            mock_set.return_value = OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_brightness",
                message="Brightness set to 75%"
            )
            
            result = integration.set_system_brightness(75)
            
            assert result.success is True
            mock_set.assert_called_once_with(75)
    
    def test_open_application_success(self):
        """Test opening an application successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'open_application') as mock_open:
            mock_open.return_value = OperationResult(
                success=True,
                category=OperationCategory.APPLICATION,
                operation="open_application",
                message="Application opened: notepad"
            )
            
            result = integration.open_application("notepad")
            
            assert result.success is True
            mock_open.assert_called_once_with("notepad")
    
    def test_type_text_success(self):
        """Test typing text successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'type_text') as mock_type:
            mock_type.return_value = OperationResult(
                success=True,
                category=OperationCategory.TEXT_INPUT,
                operation="type_text",
                message="Text typed: Hello World"
            )
            
            result = integration.type_text("Hello World", typing_speed=0.05)
            
            assert result.success is True
            mock_type.assert_called_once_with("Hello World", 0.05)
    
    def test_play_media_success(self):
        """Test playing media successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'play_media') as mock_play:
            mock_play.return_value = OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="play_media",
                message="Media play key pressed"
            )
            
            result = integration.play_media()
            
            assert result.success is True
            mock_play.assert_called_once()
    
    def test_pause_media_success(self):
        """Test pausing media successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'pause_media') as mock_pause:
            mock_pause.return_value = OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="pause_media",
                message="Media pause key pressed"
            )
            
            result = integration.pause_media()
            
            assert result.success is True
            mock_pause.assert_called_once()
    
    def test_take_screenshot_success(self):
        """Test taking a screenshot successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'take_screenshot') as mock_screenshot:
            mock_screenshot.return_value = OperationResult(
                success=True,
                category=OperationCategory.SCREEN_CAPTURE,
                operation="take_screenshot",
                message="Screenshot saved",
                metadata={'path': '/tmp/screenshot.png'}
            )
            
            result = integration.take_screenshot('/tmp/screenshot.png')
            
            assert result.success is True
            assert result.metadata['path'] == '/tmp/screenshot.png'
            mock_screenshot.assert_called_once_with('/tmp/screenshot.png')


class TestPlatformIntegrationHardwareMonitoring:
    """Tests for hardware monitoring."""
    
    def test_get_system_info(self):
        """Test getting comprehensive system information."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'get_system_info') as mock_sys:
            with patch.object(integration.hardware_monitor, 'get_cpu_usage') as mock_cpu:
                with patch.object(integration.hardware_monitor, 'get_memory_info') as mock_mem:
                    with patch.object(integration.hardware_monitor, 'get_battery_info') as mock_bat:
                        # Mock return values
                        mock_sys.return_value = {'platform': 'Linux', 'version': '5.15'}
                        
                        mock_cpu_obj = Mock()
                        mock_cpu_obj.to_dict.return_value = {'usage_percent': 25.5}
                        mock_cpu.return_value = mock_cpu_obj
                        
                        mock_mem_obj = Mock()
                        mock_mem_obj.to_dict.return_value = {'used_percent': 60.0}
                        mock_mem.return_value = mock_mem_obj
                        
                        mock_bat_obj = Mock()
                        mock_bat_obj.to_dict.return_value = {'percent': 85.0}
                        mock_bat.return_value = mock_bat_obj
                        
                        info = integration.get_system_info()
                        
                        assert 'platform' in info
                        assert 'cpu' in info
                        assert 'memory' in info
                        assert 'battery' in info
                        assert info['cpu']['usage_percent'] == 25.5
    
    def test_get_cpu_usage(self):
        """Test getting CPU usage."""
        integration = PlatformIntegration()
        
        with patch.object(integration.hardware_monitor, 'get_cpu_usage') as mock_cpu:
            mock_cpu_obj = Mock()
            mock_cpu_obj.usage_percent = 42.5
            mock_cpu.return_value = mock_cpu_obj
            
            usage = integration.get_cpu_usage()
            
            assert usage == 42.5
    
    def test_get_memory_usage(self):
        """Test getting memory usage."""
        integration = PlatformIntegration()
        
        with patch.object(integration.hardware_monitor, 'get_memory_info') as mock_mem:
            mock_mem_obj = Mock()
            mock_mem_obj.to_dict.return_value = {
                'total': 16000000000,
                'used': 8000000000,
                'used_percent': 50.0
            }
            mock_mem.return_value = mock_mem_obj
            
            usage = integration.get_memory_usage()
            
            assert usage['used_percent'] == 50.0
    
    def test_get_battery_status_available(self):
        """Test getting battery status when available."""
        integration = PlatformIntegration()
        
        with patch.object(integration.hardware_monitor, 'get_battery_info') as mock_bat:
            mock_bat_obj = Mock()
            mock_bat_obj.to_dict.return_value = {
                'percent': 75.0,
                'is_charging': True
            }
            mock_bat.return_value = mock_bat_obj
            
            status = integration.get_battery_status()
            
            assert status is not None
            assert status['percent'] == 75.0
            assert status['is_charging'] is True
    
    def test_get_battery_status_unavailable(self):
        """Test getting battery status when unavailable (desktop)."""
        integration = PlatformIntegration()
        
        with patch.object(integration.hardware_monitor, 'get_battery_info', return_value=None):
            status = integration.get_battery_status()
            
            assert status is None


class TestPlatformIntegrationFileOperations:
    """Tests for file operations."""
    
    def test_create_file_success(self):
        """Test creating a file successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'create_file') as mock_create:
            mock_create.return_value = OperationResult(
                success=True,
                category=OperationCategory.FILE,
                operation="create_file",
                message="File created: test.txt"
            )
            
            result = integration.create_file("test.txt", "Hello World")
            
            assert result.success is True
            mock_create.assert_called_once_with("test.txt", "Hello World")
    
    def test_create_file_failure(self):
        """Test error handling when file creation fails."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'create_file') as mock_create:
            mock_create.return_value = OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="create_file",
                message="Permission denied"
            )
            
            with pytest.raises(GuruSpeechError, match="Failed to create file"):
                integration.create_file("test.txt", "Hello World")
    
    def test_read_file_success(self):
        """Test reading a file successfully."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'read_file') as mock_read:
            mock_read.return_value = OperationResult(
                success=True,
                category=OperationCategory.FILE,
                operation="read_file",
                message="File read: test.txt",
                metadata={'content': 'Hello World'}
            )
            
            content = integration.read_file("test.txt")
            
            assert content == 'Hello World'
            mock_read.assert_called_once_with("test.txt")
    
    def test_read_file_failure(self):
        """Test error handling when file read fails."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'read_file') as mock_read:
            mock_read.return_value = OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="read_file",
                message="File not found"
            )
            
            with pytest.raises(GuruSpeechError, match="Failed to read file"):
                integration.read_file("test.txt")


@pytest.mark.integration
class TestPlatformIntegrationEndToEnd:
    """End-to-end integration tests."""
    
    def test_audio_device_workflow(self):
        """Test complete audio device workflow."""
        integration = PlatformIntegration()
        
        with patch('sounddevice.query_devices') as mock_query:
            with patch('sounddevice.default') as mock_default:
                mock_query.return_value = [
                    {
                        'name': 'Test Mic',
                        'max_input_channels': 1,
                        'default_samplerate': 16000.0
                    }
                ]
                mock_default.device = [0, None]
                
                # List devices
                devices = integration.list_audio_devices()
                assert len(devices) > 0
                
                # Get default device
                default = integration.get_default_audio_device()
                assert default is not None
                
                # Validate device
                assert integration.validate_audio_device(default.device_id)
    
    def test_system_control_workflow(self):
        """Test complete system control workflow."""
        integration = PlatformIntegration()
        
        with patch.object(integration.os_controller, 'set_volume') as mock_vol:
            with patch.object(integration.os_controller, 'open_application') as mock_app:
                with patch.object(integration.os_controller, 'type_text') as mock_type:
                    # Mock successful operations
                    mock_vol.return_value = OperationResult(
                        success=True,
                        category=OperationCategory.SYSTEM_SETTINGS,
                        operation="set_volume",
                        message="OK"
                    )
                    mock_app.return_value = OperationResult(
                        success=True,
                        category=OperationCategory.APPLICATION,
                        operation="open_application",
                        message="OK"
                    )
                    mock_type.return_value = OperationResult(
                        success=True,
                        category=OperationCategory.TEXT_INPUT,
                        operation="type_text",
                        message="OK"
                    )
                    
                    # Execute workflow
                    integration.set_system_volume(50)
                    integration.open_application("notepad")
                    integration.type_text("Hello from speech engine")
                    
                    # Verify all operations called
                    mock_vol.assert_called_once()
                    mock_app.assert_called_once()
                    mock_type.assert_called_once()


def test_platform_integration_repr():
    """Test string representation."""
    integration = PlatformIntegration()
    repr_str = repr(integration)
    
    assert "PlatformIntegration" in repr_str
    assert "os=" in repr_str
