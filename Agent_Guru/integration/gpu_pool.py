"""Agent_Guru/integration/gpu_pool.py.

GPUResourcePool — coordinates GPU VRAM allocation across PyTorch, ONNX Runtime,
and faster-whisper so all three coexist without contention.

Budget partitioning (when GPU is available):
  - whisper  : 30% of total VRAM  (faster-whisper / STT)
  - onnx     : 30% of total VRAM  (ONNX Runtime / InsightFace vision)
  - torch    : 40% of total VRAM  (PyTorch / LLM inference)

CPU fallback: when no CUDA device is available, all subsystems receive
DeviceConfig(device="cpu", memory_limit=0) without raising any exception.

Performance:
  - Time Complexity: O(1) for all operations
  - Space Complexity: O(1) — fixed number of subsystems
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Budget fractions — must sum to 1.0
# On a 4GB VRAM device (RTX 2050):
#   - Whisper small needs ~500MB → give it 40% (1.6GB headroom)
#   - ONNX (vision) runs headless, minimal usage → 20%
#   - Torch (avatar/emotion) → 40%
# Ollama (LLM) manages its own VRAM separately — not tracked here.
_BUDGETS: dict[str, float] = {
    "whisper": 0.40,
    "onnx": 0.20,
    "torch": 0.40,
}


@dataclass
class DeviceConfig:
    """Device configuration returned to each subsystem.

    Attributes:
        device: "cuda" or "cpu"
        memory_limit: Maximum bytes this subsystem may allocate on the device.
                      0 when device is "cpu" (no hard limit enforced by OS).

    """

    device: str
    memory_limit: int


class GPUResourcePool:
    """Coordinates GPU VRAM allocation across all GPU-using subsystems.

    Partitions available VRAM into named budgets so PyTorch, ONNX Runtime,
    and faster-whisper coexist without contention.  Falls back to CPU
    transparently when no CUDA device is present.

    Example::

        pool = GPUResourcePool()
        cfg = pool.allocate("whisper")   # DeviceConfig(device="cuda", memory_limit=...)
        util = pool.get_utilization()    # float in [0.0, 1.0]

    Time Complexity: O(1) for all public methods
    Space Complexity: O(1)
    """

    def __init__(self) -> None:
        """Detect GPU and compute per-subsystem VRAM budgets."""
        try:
            import torch

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                self.device: str = "cuda"
                self.total_vram: int = props.total_memory
                logger.info(
                    "GPUResourcePool: CUDA device '%s' detected — total VRAM %.1f GB",
                    props.name,
                    self.total_vram / (1024**3),
                )
            else:
                self.device = "cpu"
                self.total_vram = 0
                logger.info("GPUResourcePool: no CUDA device — CPU-only mode")
        except Exception:  # torch not installed or CUDA error
            logger.exception("GPUResourcePool: GPU detection failed — CPU-only mode")
            self.device = "cpu"
            self.total_vram = 0

        # Pre-compute budgets (bytes); 0 on CPU
        self.whisper_budget: int = int(self.total_vram * _BUDGETS["whisper"])
        self.onnx_budget: int = int(self.total_vram * _BUDGETS["onnx"])
        self.torch_budget: int = int(self.total_vram * _BUDGETS["torch"])

        logger.info(
            "GPUResourcePool budgets — whisper: %d MB, onnx: %d MB, torch: %d MB",
            self.whisper_budget // (1024**2),
            self.onnx_budget // (1024**2),
            self.torch_budget // (1024**2),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(self, subsystem: str) -> DeviceConfig:
        """Return the DeviceConfig for the given subsystem.

        Args:
            subsystem: One of "whisper", "onnx", "torch".

        Returns:
            DeviceConfig with device string and memory_limit in bytes.

        Raises:
            ValueError: If subsystem name is not recognised.

        Time Complexity: O(1)

        """
        if subsystem == "whisper":
            return DeviceConfig(device=self.device, memory_limit=self.whisper_budget)
        if subsystem == "onnx":
            return DeviceConfig(device=self.device, memory_limit=self.onnx_budget)
        if subsystem == "torch":
            return DeviceConfig(device=self.device, memory_limit=self.torch_budget)
        msg = f"Unknown subsystem '{subsystem}'. Valid names: whisper, onnx, torch."
        raise ValueError(msg)

    def get_utilization(self) -> float:
        """Return current GPU utilization as a fraction in [0.0, 1.0].

        Returns 0.0 when running in CPU-only mode.

        Time Complexity: O(1)
        """
        if self.device == "cpu" or self.total_vram == 0:
            return 0.0
        try:
            import torch

            allocated = torch.cuda.memory_allocated(0)
            return min(allocated / self.total_vram, 1.0)
        except Exception:
            return 0.0

    def check_budget_compliance(self) -> dict[str, dict[str, float]]:
        """Check actual VRAM usage vs budget for each subsystem.

        Returns a dict per subsystem with budget_mb, actual usage is
        estimated from total GPU allocation (not per-subsystem since
        CUDA doesn't track per-module allocations).

        Logs a warning if total GPU usage exceeds the sum of budgets.

        Time Complexity: O(1)
        """
        result: dict[str, dict[str, float]] = {}
        for name in ("whisper", "onnx", "torch"):
            cfg = self.allocate(name)
            result[name] = {
                "budget_mb": cfg.memory_limit / (1024**2),
                "device": cfg.device,
            }

        # Warn if total GPU usage exceeds budget
        if self.device == "cuda":
            utilization = self.get_utilization()
            total_budget = self.whisper_budget + self.onnx_budget + self.torch_budget
            if utilization > 0 and self.total_vram * utilization > total_budget * 1.1:
                logger.warning(
                    "GPU VRAM usage (%.1f MB) exceeds total budget (%.1f MB) by >10%%",
                    self.total_vram * utilization / (1024**2),
                    total_budget / (1024**2),
                )

        return result

    def rebalance(self, active_subsystems: set[str] | None = None) -> None:
        """Redistribute VRAM budgets based on which subsystems are active.

        Subsystems not in ``active_subsystems`` donate their budget
        proportionally to the active ones.

        Args:
            active_subsystems: Set of active subsystem names.
                               Defaults to all subsystems if None.

        Time Complexity: O(1)
        """
        if self.device == "cpu" or self.total_vram == 0:
            return

        all_names = {"whisper", "onnx", "torch"}
        active = active_subsystems or all_names
        active = active & all_names  # Validate against known subsystems

        if not active:
            return

        # Calculate total budget to redistribute from inactive subsystems
        inactive_budget = sum(
            int(self.total_vram * _BUDGETS[name])
            for name in all_names - active
        )

        if inactive_budget == 0:
            return

        # Distribute evenly among active subsystems
        bonus_per_active = inactive_budget // len(active)

        for name in all_names:
            base = int(self.total_vram * _BUDGETS[name])
            if name in active:
                setattr(self, f"{name}_budget", base + bonus_per_active)
            else:
                setattr(self, f"{name}_budget", 0)

        logger.info(
            "GPUResourcePool rebalanced — active: %s, budgets: whisper=%dMB onnx=%dMB torch=%dMB",
            active,
            self.whisper_budget // (1024**2),
            self.onnx_budget // (1024**2),
            self.torch_budget // (1024**2),
        )
