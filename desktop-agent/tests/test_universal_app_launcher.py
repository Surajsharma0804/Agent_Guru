"""
Universal Application Launcher Tests

Tests for comprehensive application database, dynamic discovery,
and 1-second launch performance.

Validates: Requirements 2.1, 2.2, 2.3, 2.7
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from src.execution.command_executor import (
    IntentRecognizer,
    ApplicationLauncher,
    CommandExecutor,
    ExecutionStatus
)
from src.pal.interfaces import ApplicationController, InputAutomation, AppDescriptor


class TestUniversalApplicationDatabase:
    """Test comprehensive application database (100+ apps)"""
    
    def test_application_database_has_100_plus_apps(self):
        """
        Verify application database contains 100+ applications.
        
        Validates: Requirement 2.2
        """
        recognizer = IntentRecognizer()
        
        # Count applications in database
        app_count = len(recognizer.app_mapping)
        
        assert app_count >= 100, (
            f"Application database must contain at least 100 apps, "
            f"but only has {app_count}"
        )
        
        print(f"✓ Application database contains {app_count} applications")
    
    def test_application_database_categories(self):
        """
        Verify application database covers major categories.
        
        Validates: Requirement 2.2
        """
        recognizer = IntentRecognizer()
        apps = recognizer.app_mapping
        
        # Define required categories with minimum counts
        required_categories = {
            "system_tools": ["notepad", "calculator", "paint", "cmd", "powershell"],
            "office": ["word", "excel", "powerpoint", "outlook"],
            "browsers": ["chrome", "firefox", "edge"],
            "communication": ["whatsapp", "telegram", "discord", "slack", "zoom"],
            "development": ["visual studio code", "pycharm", "git"],
            "media": ["vlc", "spotify", "photoshop"]
        }
        
        for category, required_apps in required_categories.items():
            found_apps = [app for app in required_apps if app in apps]
            assert len(found_apps) >= len(required_apps) * 0.8, (
                f"Category '{category}' missing too many apps. "
                f"Found: {found_apps}, Required: {required_apps}"
            )
        
        print("✓ Application database covers all major categories")
    
    def test_application_name_variations(self):
        """
        Verify application database handles name variations.
        
        Validates: Requirement 2.2
        """
        recognizer = IntentRecognizer()
        apps = recognizer.app_mapping
        
        # Test common variations
        variations = [
            ("chrome", "google chrome"),
            ("vscode", "visual studio code", "vs code"),
            ("word", "microsoft word"),
            ("excel", "microsoft excel")
        ]
        
        for variation_group in variations:
            # At least one variation should exist
            found = any(var in apps for var in variation_group)
            assert found, f"No variation found for: {variation_group}"
        
        print("✓ Application database handles name variations")


class TestDynamicApplicationDiscovery:
    """Test dynamic discovery for unlisted applications"""
    
    def test_dynamic_discovery_for_unlisted_app(self):
        """
        Verify dynamic discovery finds unlisted applications.
        
        Validates: Requirement 2.3
        """
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        mock_input_automation = Mock(spec=InputAutomation)
        
        # Mock capabilities
        mock_app_controller.get_capabilities.return_value = {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True
        }
        mock_input_automation.get_capabilities.return_value = {
            "can_type_text": True,
            "can_click": True,
            "can_focus_apps": True
        }
        
        # Mock app discovery
        custom_app = AppDescriptor(
            app_id="custom_app",
            display_name="Custom Application",
            executable_path="C:\\CustomApp\\custom.exe",
            is_running=False,
            platform="windows",
            metadata={}
        )
        mock_app_controller.discover_apps.return_value = [custom_app]
        
        # Create launcher
        launcher = ApplicationLauncher(mock_app_controller)
        
        # Try to find the custom app
        app_id = launcher.find_executable("custom")
        
        assert app_id is not None, "Dynamic discovery should find unlisted app"
        assert "custom" in app_id.lower(), "Found app should match search term"
        
        print("✓ Dynamic discovery finds unlisted applications")
    
    def test_dynamic_discovery_searches_common_paths(self):
        """
        Verify dynamic discovery searches common installation paths.
        
        Validates: Requirement 2.3
        """
        recognizer = IntentRecognizer()
        
        # Verify search paths are configured
        assert len(recognizer.search_paths) > 0, "Search paths must be configured"
        
        # Verify common paths are included
        path_strings = [str(p) for p in recognizer.search_paths]
        
        # Should include Program Files
        assert any("Program Files" in p for p in path_strings), (
            "Search paths should include Program Files"
        )
        
        # Should include user-specific paths
        assert any("AppData" in p or "Local" in p for p in path_strings), (
            "Search paths should include user-specific directories"
        )
        
        print("✓ Dynamic discovery searches common installation paths")


class TestApplicationLaunchPerformance:
    """Test 1-second launch performance requirement"""
    
    def test_launch_performance_under_1_second(self):
        """
        Verify application launch completes within 1 second.
        
        Validates: Requirement 2.7
        """
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        mock_input_automation = Mock(spec=InputAutomation)
        
        # Mock capabilities
        mock_app_controller.get_capabilities.return_value = {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True
        }
        mock_input_automation.get_capabilities.return_value = {
            "can_type_text": True,
            "can_click": True,
            "can_focus_apps": True
        }
        
        # Mock app discovery
        notepad_app = AppDescriptor(
            app_id="notepad",
            display_name="Notepad",
            executable_path="C:\\Windows\\System32\\notepad.exe",
            is_running=False,
            platform="windows",
            metadata={}
        )
        mock_app_controller.discover_apps.return_value = [notepad_app]
        
        # Mock successful launch
        mock_app_controller.open_app.return_value = True
        
        # Create launcher
        launcher = ApplicationLauncher(mock_app_controller)
        
        # Measure launch time
        start_time = time.time()
        result = launcher.launch("notepad.exe")
        execution_time = time.time() - start_time
        
        assert result.status == ExecutionStatus.SUCCESS, "Launch should succeed"
        assert execution_time < 1.0, (
            f"Launch must complete within 1 second, took {execution_time:.3f}s"
        )
        
        print(f"✓ Application launch completed in {execution_time:.3f}s (< 1.0s)")
    
    def test_command_executor_performance_under_1_second(self):
        """
        Verify end-to-end command execution completes within 1 second.
        
        Validates: Requirement 2.7
        """
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        mock_input_automation = Mock(spec=InputAutomation)
        
        # Mock capabilities
        mock_app_controller.get_capabilities.return_value = {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True
        }
        mock_input_automation.get_capabilities.return_value = {
            "can_type_text": True,
            "can_click": True,
            "can_focus_apps": True
        }
        
        # Mock app discovery
        chrome_app = AppDescriptor(
            app_id="chrome",
            display_name="Google Chrome",
            executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            is_running=False,
            platform="windows",
            metadata={}
        )
        mock_app_controller.discover_apps.return_value = [chrome_app]
        
        # Mock successful launch
        mock_app_controller.open_app.return_value = True
        
        # Create executor
        executor = CommandExecutor(mock_app_controller, mock_input_automation)
        
        # Measure execution time
        start_time = time.time()
        result = executor.execute("open chrome")
        execution_time = time.time() - start_time
        
        assert result.status == ExecutionStatus.SUCCESS, "Execution should succeed"
        assert execution_time < 1.0, (
            f"Command execution must complete within 1 second, took {execution_time:.3f}s"
        )
        
        print(f"✓ Command execution completed in {execution_time:.3f}s (< 1.0s)")


class TestIntentRecognition:
    """Test intent recognition for application launching"""
    
    def test_recognize_open_application_intent(self):
        """
        Verify intent recognizer detects application opening commands.
        
        Validates: Requirement 2.1
        """
        recognizer = IntentRecognizer()
        
        test_cases = [
            "open notepad",
            "launch chrome",
            "start word",
            "run calculator",
            "open google chrome",
            "launch microsoft word"
        ]
        
        for test_input in test_cases:
            command_type, params = recognizer.recognize(test_input)
            
            from src.execution.command_executor import CommandType
            assert command_type == CommandType.OPEN_APPLICATION, (
                f"Should recognize '{test_input}' as OPEN_APPLICATION"
            )
            assert "application" in params or "executable" in params, (
                f"Should extract application from '{test_input}'"
            )
        
        print("✓ Intent recognizer detects application opening commands")
    
    def test_extract_application_name_from_command(self):
        """
        Verify application name extraction from natural language.
        
        Validates: Requirement 2.1
        """
        recognizer = IntentRecognizer()
        
        test_cases = [
            ("open notepad", "notepad"),
            ("launch chrome", "chrome"),
            ("start microsoft word", "word"),
            ("run calculator", "calculator"),
            ("open whatsapp", "whatsapp")
        ]
        
        for test_input, expected_app in test_cases:
            command_type, params = recognizer.recognize(test_input)
            
            app_name = params.get("application", "").lower()
            assert expected_app in app_name or expected_app in params.get("executable", "").lower(), (
                f"Should extract '{expected_app}' from '{test_input}', got: {params}"
            )
        
        print("✓ Application name extraction works correctly")


class TestApplicationLauncherErrorHandling:
    """Test error handling in application launcher"""
    
    def test_handle_application_not_found(self):
        """
        Verify graceful handling when application is not found.
        
        Validates: Requirement 2.2
        """
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        
        # Mock capabilities
        mock_app_controller.get_capabilities.return_value = {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True
        }
        
        # Mock empty discovery (app not found)
        mock_app_controller.discover_apps.return_value = []
        
        # Create launcher
        launcher = ApplicationLauncher(mock_app_controller)
        
        # Try to launch non-existent app
        result = launcher.launch("nonexistent_app.exe")
        
        assert result.status == ExecutionStatus.NOT_FOUND, (
            "Should return NOT_FOUND status for missing app"
        )
        assert "not found" in result.message.lower() or "could not find" in result.message.lower(), (
            "Error message should indicate app was not found"
        )
        
        print("✓ Gracefully handles application not found")
    
    def test_handle_platform_capability_error(self):
        """
        Verify graceful handling when platform doesn't support app launching.
        
        Validates: Requirement 34.8 (iOS limitations)
        """
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        
        # Mock limited capabilities (like iOS)
        mock_app_controller.get_capabilities.return_value = {
            "can_open_apps": False,  # iOS limitation
            "can_close_apps": False,
            "can_discover_apps": False
        }
        
        # Create launcher
        launcher = ApplicationLauncher(mock_app_controller)
        
        # Try to launch app
        result = launcher.launch("notepad.exe")
        
        assert result.status == ExecutionStatus.FAILED, (
            "Should return FAILED status when platform doesn't support operation"
        )
        assert "platform" in result.message.lower() or "not support" in result.message.lower(), (
            "Error message should indicate platform limitation"
        )
        
        print("✓ Gracefully handles platform capability limitations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
