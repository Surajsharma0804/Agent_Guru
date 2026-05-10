"""Agent Guru Core Module
Provides central utilities and device management for GPU acceleration.
"""

from .device_manager import DeviceManager, device_manager

__all__ = ["DeviceManager", "device_manager"]
