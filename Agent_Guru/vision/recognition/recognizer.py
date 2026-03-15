"""
Face recognition module using ONNX Runtime for embedding extraction.

Extracts 512-dim L2-normalised embeddings from aligned 112x112 faces.
Falls back to random normalised vectors when onnxruntime or model is unavailable.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np


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

    def __init__(self, model_path: str, use_gpu: bool = False) -> None:
        self.model_path = model_path
        self.use_gpu = use_gpu
        self._session: Optional[object] = None  # lazy init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """Extract a 512-dim L2-normalised embedding from an aligned face.

        Args:
            aligned_face: BGR image of shape (112, 112, 3), dtype uint8.

        Returns:
            L2-normalised embedding of shape (512,), dtype float32.
        """
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> Optional[object]:
        """Lazy-init the ONNX Runtime session. Returns None on failure."""
        if self._session is not None:
            return self._session

        if not os.path.isfile(self.model_path):
            return None

        try:
            import onnxruntime as ort  # type: ignore[import]

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if self.use_gpu
                else ["CPUExecutionProvider"]
            )
            self._session = ort.InferenceSession(self.model_path, providers=providers)
            return self._session
        except Exception:
            return None

    @staticmethod
    def _preprocess(face: np.ndarray) -> np.ndarray:
        """BGR uint8 (112,112,3) → float32 NCHW (1,3,112,112) in [-1,1]."""
        rgb = face[:, :, ::-1].astype(np.float32)  # BGR → RGB
        normalized = rgb / 127.5 - 1.0             # [0,255] → [-1,1]
        chw = normalized.transpose(2, 0, 1)         # HWC → CHW
        return chw[np.newaxis, ...]                  # → NCHW

    @staticmethod
    def _l2_normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm < 1e-10:
            return vec
        return vec / norm

    def _random_embedding(self) -> np.ndarray:
        """Return a random L2-normalised 512-dim vector (dev/test fallback)."""
        vec = np.random.randn(self.EMBEDDING_DIM).astype(np.float32)
        return self._l2_normalize(vec)
