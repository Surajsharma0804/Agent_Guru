"""Pytest configuration and fixtures for network manager tests."""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from Agent_Guru.platform.network.manager import NetworkConfig, NetworkManager


@pytest.fixture
def network_config() -> NetworkConfig:
    """Provide default network configuration for tests."""
    return NetworkConfig(
        default_timeout=10.0,
        max_connections=50,
        verify_ssl=True,
        max_retries=3,
    )


@pytest.fixture
async def network_manager(network_config: NetworkConfig) -> AsyncGenerator[NetworkManager, None]:
    """Provide initialized network manager for tests."""
    manager = NetworkManager(network_config)
    await manager.start()

    yield manager

    await manager.close()


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
