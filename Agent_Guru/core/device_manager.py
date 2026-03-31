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

    def print_device_info(self):
        """Print detailed device information."""
        print("\n" + "=" * 60)
        print("AGENT GURU - GPU DEVICE INFORMATION")
        print("=" * 60)
        print(f"Device: {self._device}")

        if self.is_cuda_available():
            print(f"GPU Name: {self._device_name}")
            print(f"CUDA Version: {torch.version.cuda}")
            print(f"Device Count: {self.get_device_count()}")

            mem_info = self.get_memory_info()
            print("\nMemory Info:")
            print(f"  Total: {mem_info['total'] / 1024**3:.2f} GB")
            print(f"  Allocated: {mem_info['allocated'] / 1024**3:.2f} GB")
            print(f"  Free: {mem_info['free'] / 1024**3:.2f} GB")
        else:
            print("Status: CPU mode (no GPU detected)")

        print("=" * 60 + "\n")


# Global singleton instance
device_manager = DeviceManager()
