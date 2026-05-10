"""Handwriting Recognizer for the Agent Guru Vision System.

Provides:
- HandwritingRecognizer: Transcribes handwritten text from images.
  Primary: TrOCR ONNX fine-tuned on IAM Handwriting Database.
  Perspective correction via homography before recognition.
  Returns "[unreadable]" when internal confidence < 0.3.
  Latency ≤500ms per image.
  classify_region() distinguishes printed vs handwritten vs mixed.

Requirements: 4.1–4.6
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import BoundingBox, OCRResult, VisionConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from Agent_Guru.vision.model_manager import ModelManager

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_UNREADABLE_CONFIDENCE_THRESHOLD: float = 0.3
_UNREADABLE_TEXT: str = "[unreadable]"

# Heuristic: ratio of stroke-like pixels to total — above this → handwritten
_HANDWRITTEN_STROKE_RATIO: float = 0.08


class HandwritingRecognizer:
    """Handwriting transcription with perspective correction.

    Args:
        model_manager: Shared ModelManager for ONNX session lifecycle.
        config: VisionConfig (gpu_enabled used for provider selection).
        model_path: Path to TrOCR ONNX model file.
        _recognize_fn: Optional callable for testing; replaces ONNX inference.
            Signature: ``(image: np.ndarray) -> tuple[str, float]``
            Returns: ``(text, confidence)``

    """

    def __init__(
        self,
        model_manager: ModelManager,
        config: VisionConfig,
        model_path: str = "models/trocr_handwritten.onnx",
        _recognize_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._model_manager = model_manager
        self._config = config
        self._model_path = model_path
        self._recognize_fn = _recognize_fn
        self._session: Any = None
        logger.info("HandwritingRecognizer initialised", model_path=model_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> Any:  # noqa: ANN401
        if self._recognize_fn is not None:
            return None
        if self._session is None:
            try:
                self._session = self._model_manager.load_model(
                    "handwriting_recognizer",
                    self._model_path,
                )
            except Exception as exc:
                logger.exception(
                    "HandwritingRecognizer: failed to load model",
                    path=self._model_path,
                    error=str(exc),
                )
                raise
        return self._session

    @staticmethod
    def _correct_perspective(image: np.ndarray) -> np.ndarray:
        """Apply perspective correction via homography estimation.

        Detects the four corners of the text region and warps the image
        to a frontal view. Falls back to the original image when corner
        detection fails.
        """
        try:
            import cv2  # type: ignore[import]

            grey = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(grey, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return image

            # Largest contour as candidate document boundary
            largest = max(contours, key=cv2.contourArea)
            peri = cv2.arcLength(largest, True)
            approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

            if len(approx) != 4:  # noqa: PLR2004 - Small integer threshold

                return image

            src_pts = approx.reshape(4, 2).astype(np.float32)
            h, w = image.shape[:2]
            dst_pts = np.array(
                [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
                dtype=np.float32,
            )
            M = cv2.getPerspectiveTransform(src_pts, dst_pts)  # noqa: N806
            return cv2.warpPerspective(image, M, (w, h))
        except Exception:
            return image

    def _get_tokenizer(self) -> Any:  # noqa: ANN401
        """Load HuggingFace tokenizer for TrOCR token-ID decoding.

        Tries ``transformers.AutoTokenizer`` first (full HuggingFace stack),
        then falls back to the lighter ``tokenizers`` library.  Returns None
        when neither is available so the caller can handle the degraded path.
        """
        if hasattr(self, "_tokenizer_cache"):
            return self._tokenizer_cache  # type: ignore[attr-defined]

        tokenizer: Any = None
        model_name = "microsoft/trocr-base-handwritten"

        # Attempt 1: transformers (preferred — handles BPE correctly)
        try:
            from transformers import AutoTokenizer  # type: ignore[import]

            tokenizer = AutoTokenizer.from_pretrained(model_name)  # nosec B615
            logger.info("HandwritingRecognizer: loaded transformers tokenizer")
        except Exception as exc:  # noqa: BLE001
            logger.debug("HandwritingRecognizer: transformers tokenizer unavailable: %s", exc)

        # Attempt 2: tokenizers library (lighter, no PyTorch dependency)
        if tokenizer is None:
            try:
                from tokenizers import Tokenizer  # type: ignore[import]

                tokenizer = Tokenizer.from_pretrained(model_name)
                logger.info("HandwritingRecognizer: loaded tokenizers library tokenizer")
            except Exception as exc:
                logger.exception(
                    "HandwritingRecognizer: no tokenizer available (%s) — "
                    "text output will be empty on ONNX path",
                    exc,
                )

        self._tokenizer_cache = tokenizer  # type: ignore[attr-defined]
        return tokenizer

    def _decode_token_ids(self, token_ids: np.ndarray) -> str:
        """Decode a sequence of token IDs to a text string.

        Filters padding (0), BOS (1), and EOS (2) tokens before decoding.
        Falls back to an empty string when no tokenizer is available so the
        confidence check downstream can mark the result as unreadable.
        """
        ids = [int(t) for t in token_ids if int(t) > 2]  # noqa: PLR2004 - Small integer threshold

        if not ids:
            return ""

        tokenizer = self._get_tokenizer()
        if tokenizer is None:
            return ""

        try:
            # transformers AutoTokenizer
            if hasattr(tokenizer, "decode"):
                return tokenizer.decode(ids, skip_special_tokens=True).strip()
            # tokenizers library Tokenizer
            if hasattr(tokenizer, "decode"):
                return tokenizer.decode(ids).strip()
        except Exception:
            logger.exception("HandwritingRecognizer: token decode failed")

        return ""

    def _run_recognition(self, image: np.ndarray) -> tuple[str, float]:
        """Run TrOCR ONNX inference and return (text, confidence).

        Preprocessing follows the official TrOCR pipeline:
          - Resize to 384×384
          - Normalise to [-1, 1] with mean=0.5, std=0.5
          - NCHW layout

        Confidence is the mean of per-token max softmax probabilities.
        """
        if self._recognize_fn is not None:
            return self._recognize_fn(image)

        session = self._get_session()

        try:
            import cv2  # type: ignore[import]

            resized = cv2.resize(image, (384, 384)).astype(np.float32) / 255.0
        except ImportError:
            # Nearest-neighbour fallback without cv2
            h_src, w_src = image.shape[:2]
            row_idx = (np.arange(384) * h_src / 384).astype(int)
            col_idx = (np.arange(384) * w_src / 384).astype(int)
            resized = image[np.ix_(row_idx, col_idx)].astype(np.float32) / 255.0

        # TrOCR normalisation: (pixel - 0.5) / 0.5  →  [-1, 1]
        resized = (resized - 0.5) / 0.5

        blob = np.transpose(resized, (2, 0, 1))[np.newaxis].astype(np.float32)
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: blob})

        # TrOCR encoder output: (1, seq_len, vocab_size) logits
        logits: np.ndarray = outputs[0]  # shape (1, seq_len, vocab_size)
        token_ids = np.argmax(logits, axis=-1)[0]  # (seq_len,)

        # Confidence: mean of per-token max softmax probability
        # Use numerically stable log-sum-exp
        shifted = logits - logits.max(axis=-1, keepdims=True)
        log_softmax = shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))
        confidence = float(np.exp(log_softmax.max(axis=-1)).mean())

        text = self._decode_token_ids(token_ids)
        return text, confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def recognize(self, image: np.ndarray) -> OCRResult:
        """Transcribe handwritten text from an image.

        Applies perspective correction before recognition.
        Returns an OCRResult with text="[unreadable]" when confidence < 0.3.

        Args:
            image: uint8 RGB array of shape (H, W, 3).

        Returns:
            OCRResult with transcribed text and per-word details.

        """
        corrected = self._correct_perspective(image)
        loop = asyncio.get_running_loop()
        text, confidence = await loop.run_in_executor(None, self._run_recognition, corrected)

        if confidence < _UNREADABLE_CONFIDENCE_THRESHOLD:
            logger.warning(
                "HandwritingRecognizer: low confidence, marking unreadable",
                confidence=confidence,
            )
            return OCRResult(
                text=_UNREADABLE_TEXT,
                words=[],
                language="en",
                reading_order_preserved=True,
            )

        logger.debug(
            "HandwritingRecognizer: recognition complete",
            confidence=confidence,
            text_length=len(text),
        )
        # Build minimal word records from space-split tokens
        words: list[dict[str, Any]] = []
        x_offset = 0.0
        for token in text.split():
            words.append(
                {
                    "text": token,
                    "bounding_box": BoundingBox(x=x_offset, y=0.0, width=40.0, height=15.0),
                    "confidence": confidence,
                },
            )
            x_offset += 50.0

        return OCRResult(
            text=text,
            words=words,
            language="en",
            reading_order_preserved=True,
        )

    def classify_region(self, image: np.ndarray) -> Literal["printed", "handwritten", "mixed"]:
        """Classify whether a region contains printed, handwritten, or mixed text.

        Uses a heuristic based on stroke irregularity (variance of edge
        direction) to distinguish printed (regular) from handwritten (irregular).

        Args:
            image: uint8 RGB array of shape (H, W, 3).

        Returns:
            "printed", "handwritten", or "mixed".

        """
        try:
            import cv2  # type: ignore[import]

            grey = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            # Sobel gradients capture stroke direction variance
            gx = cv2.Sobel(grey, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(grey, cv2.CV_64F, 0, 1, ksize=3)
            magnitude = np.sqrt(gx**2 + gy**2)
            angle = np.arctan2(gy, gx)

            # Mask to significant edges only
            mask = magnitude > magnitude.mean() + magnitude.std()
            if mask.sum() == 0:
                return "printed"

            angle_var = float(np.var(angle[mask]))
            # High angle variance → irregular strokes → handwritten
            if angle_var > 1.2:  # noqa: PLR2004 - Threshold

                return "handwritten"
            if angle_var > 0.6:  # noqa: PLR2004 - Threshold value

                return "mixed"
            return "printed"
        except ImportError:
            # Fallback: pixel variance heuristic
            grey = image.mean(axis=2)
            ratio = float((grey < grey.mean()).mean())
            if ratio > _HANDWRITTEN_STROKE_RATIO * 1.5:
                return "handwritten"
            if ratio > _HANDWRITTEN_STROKE_RATIO:
                return "mixed"
            return "printed"
