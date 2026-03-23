"""
Tests for agent_guru.platform.controllers.messaging
Coverage Target: >80% (enforced by CI/CD)

Test Categories:
- Unit tests for messaging app launching
- Unit tests for message sending
- Unit tests for contact search
- Integration tests with messaging apps
- Property-based tests for correctness
"""

import pytest
import sys
from unittest.mock import patch
from hypothesis import given, strategies as st

from Agent_Guru.platform.controllers.messaging import (
    MessagingController,
    MessagingApp,
    ContactInfo,
    MessageInfo,
)


class TestMessagingController:
    """Unit tests for MessagingController."""

    def test_initialization(self):
        """Test controller initialization."""
        controller = MessagingController()

        assert controller.platform == sys.platform
        assert isinstance(controller._app_paths, dict)
        assert controller._text_input_controller is None

    def test_supported_apps(self):
        """Test that all supported apps are defined."""
        expected_apps = ["whatsapp", "telegram", "slack", "discord", "teams"]

        for app_name in expected_apps:
            app = MessagingApp(app_name)
            assert app.value == app_name

    def test_invalid_app_name(self):
        """Test handling of invalid app name."""
        controller = MessagingController()

        with pytest.raises(ValueError, match="Unsupported messaging app"):
            controller.open_messaging_app("invalid_app")

    @patch("webbrowser.open")
    def test_open_web_version(self, mock_browser):
        """Test opening web version of messaging app."""
        controller = MessagingController()

        result = controller.open_messaging_app("whatsapp", use_web=True)

        assert result is True
        mock_browser.assert_called_once()
        call_args = mock_browser.call_args[0][0]
        assert "whatsapp" in call_args.lower()

    @patch("webbrowser.open")
    def test_open_telegram_web(self, mock_browser):
        """Test opening Telegram web version."""
        controller = MessagingController()

        result = controller.open_messaging_app("telegram", use_web=True)

        assert result is True
        mock_browser.assert_called_once()
        call_args = mock_browser.call_args[0][0]
        assert "telegram" in call_args.lower()

    @patch("webbrowser.open")
    def test_open_slack_web(self, mock_browser):
        """Test opening Slack web version."""
        controller = MessagingController()

        result = controller.open_messaging_app("slack", use_web=True)

        assert result is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_whatsapp_message(self, mock_browser):
        """Test sending WhatsApp message."""
        controller = MessagingController()

        info = controller.send_message(
            "whatsapp",
            "+1234567890",
            "Hello World",
            confirm=False
        )

        assert isinstance(info, MessageInfo)
        assert info.app == MessagingApp.WHATSAPP
        assert info.recipient == "+1234567890"
        assert info.message == "Hello World"
        assert info.success is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_telegram_message(self, mock_browser):
        """Test sending Telegram message."""
        controller = MessagingController()

        info = controller.send_message(
            "telegram",
            "@username",
            "Test message",
            confirm=False
        )

        assert isinstance(info, MessageInfo)
        assert info.app == MessagingApp.TELEGRAM
        assert info.success is True
        mock_browser.assert_called_once()

    def test_send_message_invalid_app(self):
        """Test sending message with invalid app."""
        controller = MessagingController()

        with pytest.raises(ValueError, match="Unsupported messaging app"):
            controller.send_message("invalid_app", "recipient", "message")

    @patch("webbrowser.open")
    def test_send_message_with_special_characters(self, mock_browser):
        """Test sending message with special characters."""
        controller = MessagingController()

        message = "Hello! How are you? 😊"
        info = controller.send_message(
            "whatsapp",
            "+1234567890",
            message,
            confirm=False
        )

        assert info.success is True
        assert info.message == message

    def test_search_contacts(self):
        """Test contact search functionality."""
        controller = MessagingController()

        # Note: Returns empty list as placeholder
        contacts = controller.search_contacts("whatsapp", "John")

        assert isinstance(contacts, list)
        # Placeholder implementation returns empty list
        assert len(contacts) == 0

    def test_search_contacts_invalid_app(self):
        """Test contact search with invalid app."""
        controller = MessagingController()

        with pytest.raises(ValueError, match="Unsupported messaging app"):
            controller.search_contacts("invalid_app", "query")

    def test_get_recent_contacts(self):
        """Test getting recent contacts."""
        controller = MessagingController()

        contacts = controller.get_recent_contacts("telegram", limit=5)

        assert isinstance(contacts, list)
        # Placeholder implementation returns empty list
        assert len(contacts) == 0

    def test_get_recent_contacts_invalid_app(self):
        """Test getting recent contacts with invalid app."""
        controller = MessagingController()

        with pytest.raises(ValueError, match="Unsupported messaging app"):
            controller.get_recent_contacts("invalid_app")

    def test_is_app_installed(self):
        """Test checking if app is installed."""
        controller = MessagingController()

        # Test with valid app name
        result = controller.is_app_installed("whatsapp")
        assert isinstance(result, bool)

        # Test with invalid app name
        result = controller.is_app_installed("invalid_app")
        assert result is False

    def test_list_installed_apps(self):
        """Test listing installed apps."""
        controller = MessagingController()

        apps = controller.list_installed_apps()

        assert isinstance(apps, list)
        # All items should be valid app names
        for app in apps:
            assert app in [a.value for a in MessagingApp]

    @patch("os.path.exists")
    def test_find_windows_app(self, mock_exists):
        """Test finding Windows app path."""
        if sys.platform != "win32":
            pytest.skip("Windows-specific test")

        mock_exists.return_value = True
        controller = MessagingController()

        path = controller._find_windows_app(MessagingApp.WHATSAPP)

        # Should return a path if exists
        if path:
            assert isinstance(path, str)

    @patch("os.path.exists")
    def test_find_macos_app(self, mock_exists):
        """Test finding macOS app path."""
        if sys.platform != "darwin":
            pytest.skip("macOS-specific test")

        mock_exists.return_value = True
        controller = MessagingController()

        path = controller._find_macos_app(MessagingApp.WHATSAPP)

        # Should return a path if exists
        if path:
            assert isinstance(path, str)
            assert path.endswith(".app")

    @patch("shutil.which")
    def test_find_linux_app(self, mock_which):
        """Test finding Linux app command."""
        if not sys.platform.startswith("linux"):
            pytest.skip("Linux-specific test")

        mock_which.return_value = "/usr/bin/whatsapp-desktop"
        controller = MessagingController()

        command = controller._find_linux_app(MessagingApp.WHATSAPP)

        assert command == "/usr/bin/whatsapp-desktop"

    @patch("os.startfile")
    def test_launch_app_windows(self, mock_startfile):
        """Test launching app on Windows."""
        if sys.platform != "win32":
            pytest.skip("Windows-specific test")

        controller = MessagingController()
        result = controller._launch_app("C:\\test\\app.exe")

        assert result is True
        mock_startfile.assert_called_once()

    @patch("subprocess.Popen")
    def test_launch_app_macos(self, mock_popen):
        """Test launching app on macOS."""
        if sys.platform != "darwin":
            pytest.skip("macOS-specific test")

        controller = MessagingController()
        result = controller._launch_app("/Applications/Test.app")

        assert result is True
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_launch_app_linux(self, mock_popen):
        """Test launching app on Linux."""
        if not sys.platform.startswith("linux"):
            pytest.skip("Linux-specific test")

        controller = MessagingController()
        result = controller._launch_app("test-app")

        assert result is True
        mock_popen.assert_called_once()

    def test_launch_app_failure(self):
        """Test handling of app launch failure."""
        controller = MessagingController()

        with pytest.raises(RuntimeError, match="Failed to launch app"):
            controller._launch_app("/nonexistent/app")

    @patch("webbrowser.open")
    def test_open_web_version_failure(self, mock_browser):
        """Test handling of web version open failure."""
        mock_browser.side_effect = Exception("Browser error")
        controller = MessagingController()

        with pytest.raises(RuntimeError, match="Failed to open web version"):
            controller._open_web_version(MessagingApp.WHATSAPP)

    @patch("webbrowser.open")
    def test_send_slack_message(self, mock_browser):
        """Test sending Slack message."""
        controller = MessagingController()

        info = controller.send_message(
            "slack",
            "#general",
            "Test message",
            confirm=False
        )

        assert info.success is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_discord_message(self, mock_browser):
        """Test sending Discord message."""
        controller = MessagingController()

        info = controller.send_message(
            "discord",
            "user123",
            "Test message",
            confirm=False
        )

        assert info.success is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_teams_message(self, mock_browser):
        """Test sending Teams message."""
        controller = MessagingController()

        info = controller.send_message(
            "teams",
            "user@example.com",
            "Test message",
            confirm=False
        )

        assert info.success is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_whatsapp_with_contact_name(self, mock_browser):
        """Test sending WhatsApp message with contact name."""
        controller = MessagingController()

        info = controller.send_message(
            "whatsapp",
            "John Doe",  # Not a phone number
            "Hello",
            confirm=False
        )

        assert info.success is True
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_send_telegram_with_username(self, mock_browser):
        """Test sending Telegram message with @username."""
        controller = MessagingController()

        info = controller.send_message(
            "telegram",
            "@testuser",
            "Hello",
            confirm=False
        )

        assert info.success is True
        call_args = mock_browser.call_args[0][0]
        assert "testuser" in call_args  # @ should be stripped

    def test_get_text_input_controller(self):
        """Test lazy loading of text input controller."""
        controller = MessagingController()

        # Initially None
        assert controller._text_input_controller is None

        # Lazy load
        text_controller = controller._get_text_input_controller()
        assert text_controller is not None

        # Cached
        text_controller2 = controller._get_text_input_controller()
        assert text_controller is text_controller2

    def test_message_info_dataclass(self):
        """Test MessageInfo dataclass."""
        info = MessageInfo(
            app=MessagingApp.WHATSAPP,
            recipient="test",
            message="Hello",
            timestamp=1234567890.0,
            success=True,
            error=None
        )

        assert info.app == MessagingApp.WHATSAPP
        assert info.recipient == "test"
        assert info.message == "Hello"
        assert info.timestamp == 1234567890.0
        assert info.success is True
        assert info.error is None

    def test_contact_info_dataclass(self):
        """Test ContactInfo dataclass."""
        contact = ContactInfo(
            name="John Doe",
            identifier="+1234567890",
            app=MessagingApp.WHATSAPP,
            last_message_time=1234567890.0,
            is_favorite=True
        )

        assert contact.name == "John Doe"
        assert contact.identifier == "+1234567890"
        assert contact.app == MessagingApp.WHATSAPP
        assert contact.last_message_time == 1234567890.0
        assert contact.is_favorite is True


class TestMessagingControllerProperties:
    """Property-based tests for MessagingController."""

    @given(
        app_name=st.sampled_from(["whatsapp", "telegram", "slack", "discord", "teams"])
    )
    def test_valid_app_names_always_work(self, app_name):
        """Property: Valid app names always create MessagingApp enum."""
        app = MessagingApp(app_name)
        assert app.value == app_name

    @given(
        app_name=st.sampled_from(["whatsapp", "telegram", "slack", "discord", "teams"])
    )
    @patch("webbrowser.open")
    def test_web_version_always_opens(self, mock_browser, app_name):
        """Property: Web version always opens for valid apps."""
        controller = MessagingController()

        result = controller.open_messaging_app(app_name, use_web=True)

        assert result is True
        mock_browser.assert_called_once()

    @given(
        app_name=st.sampled_from(["whatsapp", "telegram", "slack", "discord", "teams"]),
        recipient=st.text(min_size=1, max_size=50),
        message=st.text(min_size=1, max_size=200)
    )
    @patch("webbrowser.open")
    def test_send_message_always_returns_info(self, mock_browser, app_name, recipient, message):
        """Property: send_message always returns MessageInfo."""
        controller = MessagingController()

        info = controller.send_message(app_name, recipient, message, confirm=False)

        assert isinstance(info, MessageInfo)
        assert info.app.value == app_name
        assert info.recipient == recipient
        assert info.message == message
        assert isinstance(info.success, bool)
        assert isinstance(info.timestamp, float)

    @given(
        app_name=st.sampled_from(["whatsapp", "telegram", "slack", "discord", "teams"]),
        query=st.text(min_size=1, max_size=50)
    )
    def test_search_contacts_always_returns_list(self, app_name, query):
        """Property: search_contacts always returns list."""
        controller = MessagingController()

        contacts = controller.search_contacts(app_name, query)

        assert isinstance(contacts, list)
        # All items should be ContactInfo
        for contact in contacts:
            assert isinstance(contact, ContactInfo)

    @given(
        app_name=st.sampled_from(["whatsapp", "telegram", "slack", "discord", "teams"])
    )
    def test_is_app_installed_always_returns_bool(self, app_name):
        """Property: is_app_installed always returns bool."""
        controller = MessagingController()

        result = controller.is_app_installed(app_name)

        assert isinstance(result, bool)


@pytest.mark.integration
class TestMessagingControllerIntegration:
    """Integration tests for MessagingController."""

    @pytest.mark.skipif(
        sys.platform not in ["win32", "darwin", "linux"],
        reason="Requires desktop platform"
    )
    def test_list_installed_apps_integration(self):
        """Test listing installed apps on real system."""
        controller = MessagingController()

        apps = controller.list_installed_apps()

        # Should return a list (may be empty if no apps installed)
        assert isinstance(apps, list)

        # All returned apps should be valid
        for app in apps:
            assert app in [a.value for a in MessagingApp]

    @pytest.mark.skipif(
        sys.platform not in ["win32", "darwin", "linux"],
        reason="Requires desktop platform"
    )
    @patch("webbrowser.open")
    def test_open_and_send_message_workflow(self, mock_browser):
        """Test complete workflow: open app and send message."""
        controller = MessagingController()

        # Open app
        result = controller.open_messaging_app("whatsapp", use_web=True)
        assert result is True

        # Send message
        info = controller.send_message(
            "whatsapp",
            "+1234567890",
            "Integration test message",
            confirm=False
        )
        assert info.success is True

    @patch("webbrowser.open")
    def test_multiple_apps_workflow(self, mock_browser):
        """Test opening multiple messaging apps."""
        controller = MessagingController()

        apps = ["whatsapp", "telegram", "slack"]

        for app in apps:
            result = controller.open_messaging_app(app, use_web=True)
            assert result is True

        # Should have called browser for each app
        assert mock_browser.call_count == len(apps)

    @patch("webbrowser.open")
    def test_send_multiple_messages(self, mock_browser):
        """Test sending multiple messages."""
        controller = MessagingController()

        messages = [
            ("whatsapp", "+1111111111", "Message 1"),
            ("telegram", "@user1", "Message 2"),
            ("slack", "#channel", "Message 3"),
        ]

        for app, recipient, message in messages:
            info = controller.send_message(app, recipient, message, confirm=False)
            assert info.success is True
            assert info.app.value == app

    def test_error_handling_workflow(self):
        """Test error handling in complete workflow."""
        controller = MessagingController()

        # Test invalid app name
        with pytest.raises(ValueError):
            controller.open_messaging_app("invalid_app")

        # Test invalid app in send_message
        with pytest.raises(ValueError):
            controller.send_message("invalid_app", "recipient", "message")

        # Test invalid app in search_contacts
        with pytest.raises(ValueError):
            controller.search_contacts("invalid_app", "query")


@pytest.mark.performance
class TestMessagingControllerPerformance:
    """Performance tests for MessagingController."""

    def test_initialization_performance(self):
        """Test controller initialization performance."""
        import time
        start = time.perf_counter()
        controller = MessagingController()
        elapsed = time.perf_counter() - start
        
        assert controller is not None
        assert elapsed < 0.1  # Should initialize in <100ms

    @patch("webbrowser.open")
    def test_open_app_performance(self, mock_browser):
        """Test app opening performance."""
        import time
        controller = MessagingController()

        start = time.perf_counter()
        result = controller.open_messaging_app("whatsapp", use_web=True)
        elapsed = time.perf_counter() - start

        assert result is True
        assert elapsed < 0.2  # Should open in <200ms

    @patch("webbrowser.open")
    def test_send_message_performance(self, mock_browser):
        """Test message sending performance."""
        import time
        controller = MessagingController()

        start = time.perf_counter()
        result = controller.send_message(
            "whatsapp",
            "+1234567890",
            "Performance test message",
            confirm=False
        )
        elapsed = time.perf_counter() - start

        assert result.success is True
        assert elapsed < 0.2  # Should send in <200ms

    def test_list_installed_apps_performance(self):
        """Test listing installed apps performance."""
        import time
        controller = MessagingController()

        start = time.perf_counter()
        result = controller.list_installed_apps()
        elapsed = time.perf_counter() - start

        assert isinstance(result, list)
        assert elapsed < 1.0  # Should complete in <1s

    def test_is_app_installed_performance(self):
        """Test app installation check performance."""
        import time
        controller = MessagingController()

        start = time.perf_counter()
        result = controller.is_app_installed("whatsapp")
        elapsed = time.perf_counter() - start

        assert isinstance(result, bool)
        assert elapsed < 0.5  # Should check in <500ms


# Fixtures

@pytest.fixture
def controller():
    """Create MessagingController instance for testing."""
    return MessagingController()


@pytest.fixture
def mock_browser():
    """Mock webbrowser.open for testing."""
    with patch("webbrowser.open") as mock:
        yield mock


@pytest.fixture
def sample_contact():
    """Create sample ContactInfo for testing."""
    return ContactInfo(
        name="Test User",
        identifier="+1234567890",
        app=MessagingApp.WHATSAPP,
        last_message_time=1234567890.0,
        is_favorite=False
    )


@pytest.fixture
def sample_message_info():
    """Create sample MessageInfo for testing."""
    return MessageInfo(
        app=MessagingApp.WHATSAPP,
        recipient="+1234567890",
        message="Test message",
        timestamp=1234567890.0,
        success=True,
        error=None
    )
