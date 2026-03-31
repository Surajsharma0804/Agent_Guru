"""
Depth Estimator for the Agent Guru Vision System.

Provides monocular depth estimation via MiDaS/Depth Anything ONNX models.

Design:
- Output normalised to [0.0, 1.0]: 0.0 = nearest, 1.0 = farthest.
- Returns null DepthMap (is_null=True) when mean brightness < 20 or
  pixel variance < 5 — frame is too dark/featureless for reliable estimation.
- Latency target: ≤100 ms per frame on GPU.
- No stereo camera or depth sensor required.

Requirements: 2.1–2.7
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import numpy as np
import structlog

from Agent_Guru.vision.model_manager import ModelManager
from Agent_Guru.vision.vision_models import DepthMap, VisionConfig

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_DARK_BRIGHTNESS_THRESHOLD: float = 20.0
_LOW_VARIANCE_THRESHOLD: float = 5.0


class DepthEstimator:
    """Monocular depth estimator using MiDaS / Depth Anything ONNX.

    Args:
        model_manager: Shared ModelManager for ONNX session lifecycle.
        config: VisionConfig (gpu_enabled used for provider selection).
        model_path: Path to the MiDaS / Depth Anything ONNX model file.
        _infer_fn: Optional callable for testing; replaces ONNX inference.
            Signature: ``(frame: np.ndarray) -> np.ndarray``
            Output: float32 array of shape (H, W) with raw depth values.
    """

    def __init__(
        self,
        model_manager: ModelManager,
        config: VisionConfig,
        model_path: str = "models/midas_v31.onnx",
        _infer_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._model_manager = model_manager
        self._config = config
        self._model_path = model_path
        self._infer_fn = _infer_fn
        self._session: Any = None
        logger.info("DepthEstimator initialised", model_path=model_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> Any:
        if self._infer_fn is not None:
            return None
        if self._session is None:
            try:
                self._session = self._model_manager.load_model(
                    "depth_estimator", self._model_path
                )
            except Exception as exc:
                logger.error(
                    "DepthEstimator: failed to load model",
                    path=self._model_path,
                    error=str(exc),
                )
                raise
        return self._session

    def _run_inference(self, frame: np.ndarray) -> np.ndarray:
        """Run depth inference and return a raw (H, W) float32 depth array."""
        if self._infer_fn is not None:
            return self._infer_fn(frame)

        session = self._get_session()
        h, w = frame.shape[:2]
        # Resize to model input size (384×384 for MiDaS v3.1)
        try:
            import cv2  # type: ignore[import]
            resized = cv2.resize(frame, (384, 384)).astype(np.float32) / 255.0
        except ImportError:
            resized = (
                frame[
                    :: frame.shape[0] // 384 or 1,
                    :: frame.shape[1] // 384 or 1,
                ][:384, :384].astype(np.float32)
                / 255.0
            )
        blob = np.transpose(resized, (2, 0, 1))[np.newaxis]
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: blob})
        raw: np.ndarray = outputs[0][0]  # (H_out, W_out)

        # Resize back to original frame dimensions
        try:
            import cv2  # type: ignore[import]
            raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)
        except ImportError:
            pass  # keep model output size; normalisation still applies

        return raw.astype(np.float32)

    @staticmethod
    def _normalise(raw: np.ndarray) -> np.ndarray:
        """Normalise raw depth values to [0.0, 1.0]."""
        mn, mx = float(raw.min()), float(raw.max())
        if mx - mn < 1e-6:
            return np.zeros_like(raw, dtype=np.float32)
        return ((raw - mn) / (mx - mn)).astype(np.float32)

    @staticmethod
    def _is_dark_or_featureless(frame: np.ndarray) -> bool:
        """Return True when the frame is too dark or featureless for depth."""
        grey = frame.mean(axis=2) if frame.ndim == 3 else frame.astype(np.float32)
        mean_brightness = float(grey.mean())
        variance = float(grey.var())
        return mean_brightness < _DARK_BRIGHTNESS_THRESHOLD or variance < _LOW_VARIANCE_THRESHOLD

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def estimate(self, frame: np.ndarray) -> DepthMap:
        """Estimate per-pixel relative depth for a single frame.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            DepthMap with data in [0.0, 1.0] and same (H, W) as input.
            Returns ``is_null=True`` when frame is too dark or featureless.
        """
        h, w = frame.shape[:2]

        if self._is_dark_or_featureless(frame):
            logger.warning(
                "DepthEstimator: frame too dark/featureless, returning null map",
                mean=float(frame.mean()),
            )
            return DepthMap(
                data=np.zeros((h, w), dtype=np.float32),
                confidence=0.0,
                is_null=True,
            )

        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._run_inference, frame)
        normalised = self._normalise(raw)

        # Ensure output shape matches input frame
        if normalised.shape != (h, w):
            try:
                import cv2  # type: ignore[import]
                normalised = cv2.resize(normalised, (w, h), interpolation=cv2.INTER_LINEAR)
            except ImportError:
                normalised = np.zeros((h, w), dtype=np.float32)

        confidence = float(1.0 - normalised.std())
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            "DepthEstimator: depth map produced",
            shape=normalised.shape,
            confidence=confidence,
        )
        return DepthMap(data=normalised, confidence=confidence, is_null=False)
