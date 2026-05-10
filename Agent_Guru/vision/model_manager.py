"""GPU/Model Manager for the Agent Guru Vision System.

Responsibilities:
- Detect CUDA availability and select the appropriate ONNX Runtime provider.
- Load ONNX models on demand, caching them in an LRU cache.
- Evict the least-recently-used model when the VRAM budget is exceeded.
- Expose a synchronous ``get_cached_model`` for fast cache lookups.

All public methods are intentionally synchronous so they can be called from
both sync and async contexts without requiring an event loop.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import structlog

logger: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional ONNX Runtime import — graceful fallback when not installed
# ---------------------------------------------------------------------------

try:
    import onnxruntime as ort  # type: ignore[import]

    _ORT_AVAILABLE = True
except ImportError:  # pragma: no cover
    ort = None  # type: ignore[assignment]
    _ORT_AVAILABLE = False


# ---------------------------------------------------------------------------
# ModelManager
# ---------------------------------------------------------------------------


class ModelManager:
    """Manages ONNX model loading, caching, and LRU eviction.

    The cache is an ``OrderedDict`` used as an LRU cache: the most-recently
    accessed entry is moved to the end; the front entry is the LRU candidate.

    Args:
        max_models: Maximum number of models to keep in the cache.
        vram_budget_gb: Maximum GPU VRAM budget in gigabytes.

    """

    def __init__(
        self,
        max_models: int = 10,
        vram_budget_gb: float = 4.0,
    ) -> None:
        if max_models < 1:
            msg = f"max_models must be ≥ 1, got {max_models}"
            raise ValueError(msg)
        if vram_budget_gb <= 0.0:
            msg = f"vram_budget_gb must be positive, got {vram_budget_gb}"
            raise ValueError(msg)

        self._max_models = max_models
        self._vram_budget_gb = vram_budget_gb
        # OrderedDict: key = model name, value = InferenceSession (or mock)
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._provider: str = self._detect_provider()

        logger.info(
            "ModelManager initialised",
            provider=self._provider,
            max_models=max_models,
            vram_budget_gb=vram_budget_gb,
        )

    # ------------------------------------------------------------------
    # Provider detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_provider() -> str:
        """Detect whether CUDA is available via ONNX Runtime.

        Returns:
            "CUDAExecutionProvider" if CUDA is available,
            "CPUExecutionProvider" otherwise.

        """
        if not _ORT_AVAILABLE:
            return "CPUExecutionProvider"
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            return "CUDAExecutionProvider"
        return "CPUExecutionProvider"

    def get_provider(self) -> str:
        """Return the active ONNX Runtime execution provider string.

        Returns:
            "CUDAExecutionProvider" or "CPUExecutionProvider".

        """
        return self._provider

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self, name: str, path: str) -> Any:
        """Load an ONNX model, cache it, and return the session.

        If the model is already cached it is returned immediately (cache hit).
        If the cache is at capacity, the LRU entry is evicted before loading.

        Args:
            name: Logical model name used as the cache key.
            path: Filesystem path to the ``.onnx`` model file.

        Returns:
            An ``onnxruntime.InferenceSession`` (or a mock in tests).

        Raises:
            RuntimeError: If ONNX Runtime is not installed.
            FileNotFoundError: If the model file does not exist.

        """
        # Cache hit — move to end (most recently used)
        if name in self._cache:
            self._cache.move_to_end(name)
            logger.debug("Model cache hit", model=name)
            return self._cache[name]

        # Evict LRU if at capacity
        if len(self._cache) >= self._max_models:
            self.evict_lru()

        if not _ORT_AVAILABLE:
            msg = "onnxruntime is not installed. Install it with: pip install onnxruntime-gpu"
            raise RuntimeError(
                msg,
            )

        logger.info("Loading ONNX model", model=name, path=path, provider=self._provider)
        try:
            session = ort.InferenceSession(path, providers=[self._provider])
        except Exception as exc:
            logger.exception("Failed to load model", model=name, path=path, error=str(exc))
            raise

        self._cache[name] = session
        self._cache.move_to_end(name)
        logger.info("Model loaded and cached", model=name, cache_size=len(self._cache))
        return session

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def evict_lru(self) -> None:
        """Evict the least-recently-used model from the cache.

        If the cache is empty this is a no-op.
        """
        if not self._cache:
            return
        lru_name, _ = next(iter(self._cache.items()))
        del self._cache[lru_name]
        logger.info("Evicted LRU model", model=lru_name, cache_size=len(self._cache))

    def get_cached_model(self, name: str) -> Any | None:
        """Return a cached model session without loading from disk.

        Accessing a model via this method counts as a use and moves it to
        the MRU position.

        Args:
            name: Logical model name.

        Returns:
            The cached ``InferenceSession``, or ``None`` if not cached.

        """
        if name not in self._cache:
            return None
        self._cache.move_to_end(name)
        return self._cache[name]

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def cached_model_names(self) -> list[str]:
        """Return the names of all currently cached models (LRU → MRU order)."""
        return list(self._cache.keys())

    @property
    def cache_size(self) -> int:
        """Return the number of models currently in the cache."""
        return len(self._cache)

    def clear(self) -> None:
        """Remove all models from the cache."""
        self._cache.clear()
        logger.info("Model cache cleared")
