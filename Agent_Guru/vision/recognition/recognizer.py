"""Face recognition module using ONNX Runtime for embedding extraction.

Extracts 512-dim L2-normalised embeddings from aligned 112x112 faces.
Falls back to random normalised vectors when onnxruntime or model is unavailable.
"""

from __future__ import annotations

import logging
import os

import numpy as np

from Agent_Guru.security.embedding_auth import BIOMETRIC_THRESHOLD, verify_embedding
from Agent_Guru.vision.exceptions import InvalidImageError

logger = logging.getLogger("guruvision.recognition")


class FaceRecognizer:
    """Extracts face embeddings and computes similarity scores.

    Uses an ArcFace ONNX model for inference. When the model file is missing
    or onnxruntime is not installed, returns a random L2-normalised 512-dim
    vector so the rest of the pipeline keeps working in dev/test.

    Args:
        model_path: Path to the ArcFace ONNX model file.
        use_gpu: Use CUDAExecutionProvider when True, else CPUExecutionProvider.

    """

    EMBEDDING_DIM: int = 512
    _EXPECTED_SHAPE: tuple[int, int, int] = (112, 112, 3)

    def __init__(self, model_path: str, use_gpu: bool = False) -> None:
        self.model_path = model_path
        self.use_gpu = use_gpu
        self._session: object | None = None  # lazy init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """Extract a 512-dim L2-normalised embedding from an aligned face.

        Args:
            aligned_face: BGR image of shape (112, 112, 3), dtype uint8.

        Returns:
            L2-normalised embedding of shape (512,), dtype float32.

        Raises:
            InvalidImageError: If aligned_face has wrong shape or dtype.

        """
        self._validate_face(aligned_face)

        session = self._get_session()
        if session is None:
            return self._random_embedding()

        blob = self._preprocess(aligned_face)
        input_name = session.get_inputs()[0].name  # type: ignore[union-attr]
        raw: np.ndarray = session.run(None, {input_name: blob})[0][0]  # type: ignore[union-attr]
        return self._l2_normalize(raw.astype(np.float32))

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two L2-normalised embeddings.

        Args:
            emb1: First embedding, shape (512,).
            emb2: Second embedding, shape (512,).

        Returns:
            Similarity score in [-1.0, 1.0].

        """
        score = float(np.dot(emb1, emb2))
        return float(np.clip(score, -1.0, 1.0))

    def compute_similarity_batch(self, query: np.ndarray, gallery: np.ndarray) -> np.ndarray:
        """Vectorized cosine similarity between one query and N gallery embeddings.

        Uses matrix multiplication instead of a Python loop - O(n) with a
        single BLAS call, ~100x faster than iterating compute_similarity().

        Args:
            query: L2-normalised embedding, shape (512,).
            gallery: L2-normalised embeddings, shape (N, 512).

        Returns:
            Similarity scores, shape (N,), values in [-1.0, 1.0].

        """
        scores = gallery @ query  # (N, 512) @ (512,) → (N,)
        return np.clip(scores, -1.0, 1.0)

    def verify(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray,
        threshold: float = BIOMETRIC_THRESHOLD,
    ) -> bool:
        """Return True iff cosine similarity between *emb1* and *emb2* >= *threshold*.

        Uses :func:`~Agent_Guru.security.embedding_auth.verify_embedding` to
        enforce the biometric threshold (FAR < 0.1%).

        Args:
            emb1: First L2-normalised embedding, shape (512,).
            emb2: Second L2-normalised embedding, shape (512,).
            threshold: Minimum cosine similarity for a positive match.

        Returns:
            ``True`` if the embeddings are similar enough, ``False`` otherwise.

        """
        return verify_embedding(emb1, emb2, threshold)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> object | None:
        """Lazy-init the ONNX Runtime session.

        Returns None only in explicit test/dev mode (when model_path is empty
        or starts with "test_").  In all other cases a missing or unloadable
        model raises ``RuntimeError`` so the failure is never silently swallowed.
        """
        if self._session is not None:
            return self._session

        # Allow explicit test/dev bypass via a sentinel path prefix
        _is_test_mode = not self.model_path or self.model_path.startswith("test_")

        if not os.path.isfile(self.model_path):  # noqa: PTH113
            if _is_test_mode:
                logger.warning(
                    "FaceRecognizer: test mode - no model at '%s', random fallback active",
                    self.model_path,
                )
                return None
            msg = (
                f"ArcFace ONNX model not found at '{self.model_path}'. "
                "Download the model and place it at the configured path. "
                "See docs/models.md for instructions."
            )
            raise RuntimeError(
                msg,
            )

        try:
            import onnxruntime as ort  # type: ignore[import]

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if self.use_gpu
                else ["CPUExecutionProvider"]
            )
            self._session = ort.InferenceSession(self.model_path, providers=providers)
            logger.info("Loaded ArcFace ONNX model from '%s'", self.model_path)
            return self._session
        except Exception as exc:
            msg = f"Failed to load ArcFace ONNX model from '{self.model_path}': {exc}"
            raise RuntimeError(
                msg,
            ) from exc

    @staticmethod
    def _validate_face(face: np.ndarray) -> None:
        """Validate that face has the expected shape and dtype.

        Args:
            face: Image array to validate.

        Raises:
            InvalidImageError: If shape or dtype is wrong.

        """
        if face.shape != FaceRecognizer._EXPECTED_SHAPE:
            msg = f"Expected face shape {FaceRecognizer._EXPECTED_SHAPE}, got {face.shape}"
            raise InvalidImageError(
                msg,
            )
        if face.dtype != np.uint8:
            msg = f"Expected face dtype uint8, got {face.dtype}"
            raise InvalidImageError(msg)

    @staticmethod
    def _preprocess(face: np.ndarray) -> np.ndarray:
        """BGR uint8 (112,112,3) → float32 NCHW (1,3,112,112) in [-1,1]."""
        rgb = face[:, :, ::-1].astype(np.float32)  # BGR → RGB
        normalized = rgb / 127.5 - 1.0  # [0,255] → [-1,1]
        chw = normalized.transpose(2, 0, 1)  # HWC → CHW
        return chw[np.newaxis, ...]  # → NCHW

    @staticmethod
    def _l2_normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm < 1e-10:
            return vec
        return vec / norm

    def _random_embedding(self) -> np.ndarray:
        """Return a random L2-normalised 512-dim vector.

        ONLY used in test/dev mode (model_path is empty or starts with "test_").
        Never called in production - _get_session() raises RuntimeError instead.
        """
        vec = np.random.randn(self.EMBEDDING_DIM).astype(np.float32)
        return self._l2_normalize(vec)
