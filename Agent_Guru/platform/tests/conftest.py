"""Pytest configuration and fixtures for platform integration tests."""

import platform

import pytest


@pytest.fixture
def current_platform():
    """Fixture that returns the current platform name."""
    return platform.system()


@pytest.fixture
def is_windows():
    """Fixture that returns True if running on Windows."""
    return platform.system() == "Windows"


@pytest.fixture
def is_macos():
    """Fixture that returns True if running on macOS."""
    return platform.system() == "Darwin"


@pytest.fixture
def is_linux():
    """Fixture that returns True if running on Linux."""
    return platform.system() == "Linux"
