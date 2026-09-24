"""Deterministic seed utilities for reproducible training runs.

Setting all random-number-generator seeds before training ensures that
experiments are reproducible across runs and machines, which is required
for scientific validity and debugging (Requirement 2.24).

Performance Characteristics:
    - Time Complexity: O(1) - constant number of seed calls
    - Space Complexity: O(1) - no allocations

Requirements: 2.24
"""

from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


def set_deterministic_seeds(seed: int = 42) -> None:
    """Seed all random-number generators for reproducible training.

    Sets seeds for the Python ``random`` module, NumPy, and PyTorch
    (both CPU and CUDA).  Missing optional libraries (NumPy, PyTorch)
    are handled gracefully - a warning is logged but execution continues.

    Args:
        seed: Integer seed value.  Default is ``42``.

    Returns:
        ``None``

    Example::

        from Agent_Guru.training.seed_utils import set_deterministic_seeds

        set_deterministic_seeds(42)
        model = train_model(data)

    """
    logger.info("Setting deterministic seeds: seed=%d", seed)

    # Python built-in random
    random.seed(seed)

    # NumPy (optional dependency)
    try:
        import numpy as np  # type: ignore[import-untyped]

        np.random.seed(seed)
        logger.debug("NumPy seed set to %d", seed)
    except ImportError:
        logger.exception("NumPy not available - skipping np.random.seed")

    # PyTorch CPU + CUDA (optional dependency)
    try:
        import torch  # type: ignore[import-untyped]

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        logger.debug("PyTorch CPU and CUDA seeds set to %d", seed)
    except ImportError:
        logger.exception("PyTorch not available - skipping torch seed calls for seed=")
