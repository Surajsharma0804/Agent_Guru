"""
Central GPU Device Manager for Agent Guru
Automatically detects and manages CUDA GPU availability across all AI models.
"""


import logging

import torch

_logger = logging.getLogger(__name__)


class DeviceManager:
    """
    Centralized device management for GPU acceleration.

    Automatically detects CUDA availability and provides a consistent
    interface for all AI models in the Agent Guru system.

    Usage:
        from Agent_Guru.core.device_manager import device_manager

        device = device_manager.get_device()
        model.to(device)
        tensor = tensor.to(device)
    """

    def __init__(self):
        """Initialize device manager and detect CUDA availability."""
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device_name = None

        if self.is_cuda_available():
            try:
                self._device_name = torch.cuda.get_device_name(0)
                _logger.info("GPU detected: %s", self._device_name)
                _logger.info("CUDA version: %s", torch.version.cuda)
            except Exception as e:
                _logger.warning("GPU detected but couldn't get device name: %s", e)
        else:
            _logger.info("No GPU detected - using CPU")

    def get_device(self) -> str:
        """
        Get the current device (cuda or cpu).

        Returns:
            str: 'cuda' if GPU is available, 'cpu' otherwise
        """
        return self._device

    def is_cuda_available(self) -> bool:
        """
        Check if CUDA GPU is available.

        Returns:
            bool: True if CUDA is available, False otherwise
        """
        return self._device == "cuda"

    def get_device_name(self) -> str | None:
        """
        Get the name of the GPU device.

        Returns:
            Optional[str]: GPU name if available, None otherwise
        """
        return self._device_name

    def get_device_count(self) -> int:
        """
        Get the number of available CUDA devices.

        Returns:
            int: Number of CUDA devices
        """
        if self.is_cuda_available():
            return torch.cuda.device_count()
        return 0

    def get_memory_info(self) -> dict:
        """
        Get GPU memory information.

        Returns:
            dict: Memory info with 'allocated', 'reserved', 'free' in bytes
        """
        if not self.is_cuda_available():
            return {"allocated": 0, "reserved": 0, "free": 0}

        allocated = torch.cuda.memory_allocated(0)
        reserved = torch.cuda.memory_reserved(0)
        total = torch.cuda.get_device_properties(0).total_memory
        free = total - allocated

        return {"allocated": allocated, "reserved": reserved, "free": free, "total": total}

    def log_device_info(self) -> None:
        """Log detailed device information at INFO level (replaces print_device_info)."""
        sep = "=" * 60
        _logger.info(sep)
        _logger.info("AGENT GURU - GPU DEVICE INFORMATION")
        _logger.info(sep)
        _logger.info("Device: %s", self._device)

        if self.is_cuda_available():
            _logger.info("GPU Name: %s", self._device_name)
            _logger.info("CUDA Version: %s", torch.version.cuda)
            _logger.info("Device Count: %d", self.get_device_count())

            mem_info = self.get_memory_info()
            _logger.info("Memory Info:")
            _logger.info("  Total:     %.2f GB", mem_info["total"] / 1024**3)
            _logger.info("  Allocated: %.2f GB", mem_info["allocated"] / 1024**3)
            _logger.info("  Free:      %.2f GB", mem_info["free"] / 1024**3)
        else:
            _logger.info("Status: CPU mode (no GPU detected)")

        _logger.info(sep)

    # Keep old name as alias for backward compatibility
    def print_device_info(self) -> None:  # noqa: D102
        """Deprecated alias for log_device_info(). Use log_device_info() instead."""
        self.log_device_info()


# Global singleton instance
device_manager = DeviceManager()
