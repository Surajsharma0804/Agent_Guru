"""Emotion recognition module.

Classifies 7 emotions from an aligned 112x112 face image.
Uses an ONNX model when available; falls back to a brightness/contrast
heuristic that still produces a valid probability distribution.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import numpy as np

from Agent_Guru.vision.exceptions import InvalidImageError

logger = logging.getLogger("guruvision.emotion")

EMOTION_LABELS: list[str] = [
    "neutral",
    "happy",
    "sad",
    "angry",
    "surprised",
    "fearful",
    "disgusted",
]


@dataclass
class EmotionResult:
    """Result of emotion recognition.

    Attributes:
        emotion: Dominant emotion label (one of EMOTION_LABELS).
        confidence: Confidence of the dominant emotion in [0.0, 1.0].
        all_scores: Score for each emotion; values sum to ~1.0.

    """

    emotion: str
    confidence: float
    all_scores: dict[str, float] = field(default_factory=dict)


class EmotionRecognizer:
    """Recognises emotions from aligned face images.

    Args:
        model_path: Optional path to an ONNX emotion model.
        use_gpu: Use CUDAExecutionProvider when True.

    """

    _EXPECTED_SHAPE: tuple[int, int, int] = (112, 112, 3)

    def __init__(
        self,
        model_path: str | None = None,
        use_gpu: bool = False,
    ) -> None:
        self.model_path = model_path
        self.use_gpu = use_gpu
        self._session: object | None = None

    def recognize(self, aligned_face: np.ndarray) -> EmotionResult:
        """Classify the emotion in an aligned face image.

        Args:
            aligned_face: BGR image of shape (112, 112, 3), dtype uint8.

        Returns:
            EmotionResult with dominant emotion, confidence, and all_scores.

        Raises:
            InvalidImageError: If aligned_face has wrong shape or dtype.

        """
        self._validate_face(aligned_face)

        session = self._get_session()
        if session is not None:
            scores = self._run_onnx(session, aligned_face)
        else:
            scores = self._heuristic_scores(aligned_face)

        all_scores = {label: float(s) for label, s in zip(EMOTION_LABELS, scores, strict=False)}
        dominant_idx = int(np.argmax(scores))
        return EmotionResult(
            emotion=EMOTION_LABELS[dominant_idx],
            confidence=float(scores[dominant_idx]),
            all_scores=all_scores,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> object | None:
        if self._session is not None:
            return self._session
        if not self.model_path or not os.path.isfile(self.model_path):  # noqa: PTH113
            if self.model_path:
                logger.warning(
                    "Emotion ONNX model not found at '%s', using heuristic fallback",
                    self.model_path,
                )
            return None
        try:
            import onnxruntime as ort  # type: ignore[import]

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if self.use_gpu
                else ["CPUExecutionProvider"]
            )
            self._session = ort.InferenceSession(self.model_path, providers=providers)
            logger.info("Loaded emotion ONNX model from '%s'", self.model_path)
            return self._session
        except Exception as exc:
            logger.exception(
                "Failed to load emotion ONNX model from '%s': %s",
                self.model_path,
                exc,
            )
            return None

    @staticmethod
    def _validate_face(face: np.ndarray) -> None:
        """Validate that face has the expected shape and dtype.

        Raises:
            InvalidImageError: If shape or dtype is wrong.

        """
        if face.shape != EmotionRecognizer._EXPECTED_SHAPE:
            msg = f"Expected face shape {EmotionRecognizer._EXPECTED_SHAPE}, got {face.shape}"
            raise InvalidImageError(
                msg,
            )
        if face.dtype != np.uint8:
            msg = f"Expected face dtype uint8, got {face.dtype}"
            raise InvalidImageError(msg)

    @staticmethod
    def _run_onnx(session: object, face: np.ndarray) -> np.ndarray:
        """Run ONNX inference and return softmax probabilities."""
        rgb = face[:, :, ::-1].astype(np.float32) / 255.0
        chw = rgb.transpose(2, 0, 1)[np.newaxis, ...]
        input_name = session.get_inputs()[0].name  # type: ignore[union-attr]
        logits: np.ndarray = session.run(None, {input_name: chw})[0][0]  # type: ignore[union-attr]
        return EmotionRecognizer._softmax(logits.astype(np.float32))

    @staticmethod
    def _heuristic_scores(face: np.ndarray) -> np.ndarray:
        """Brightness/contrast heuristic - returns a valid probability distribution.

        Note: This is a dev/test fallback only. It has no real correlation with
        actual emotions and should never be used in production without a real model.
        """
        logger.warning(
            "No emotion model available - using brightness/contrast heuristic fallback. "
            "Results are not meaningful without a real ONNX model.",
        )
        gray = (
            0.114 * face[:, :, 0].astype(np.float32)
            + 0.587 * face[:, :, 1].astype(np.float32)
            + 0.299 * face[:, :, 2].astype(np.float32)
        )
        brightness = float(np.mean(gray)) / 255.0  # 0..1
        contrast = float(np.std(gray)) / 128.0  # 0..~1

        n = len(EMOTION_LABELS)
        base = np.ones(n, dtype=np.float32)

        base[0] += 1.0 - abs(brightness - 0.5) * 2  # neutral: mid-brightness
        base[1] += brightness * contrast  # happy: bright + contrasty
        base[2] += (1.0 - brightness) * 0.8  # sad: dark
        base[3] += contrast * (1.0 - brightness)  # angry: high contrast, dark
        base[4] += contrast * brightness  # surprised: high contrast, bright
        base[5] += (1.0 - contrast) * (1.0 - brightness)  # fearful: low contrast, dark
        base[6] += (1.0 - contrast) * brightness  # disgusted: low contrast, bright

        return EmotionRecognizer._softmax(base)

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()
