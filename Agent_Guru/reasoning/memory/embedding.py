"""Embedding generation for semantic search using sentence-transformers.

This module provides GPU-accelerated embedding generation for memory content
using the sentence-transformers library with the all-MiniLM-L6-v2 model.

Performance Characteristics:
    - Time Complexity: O(n) where n is text length
    - Space Complexity: O(1) - fixed 384-dim embeddings
    - Latency: <50ms per text (GPU), <200ms (CPU)
    - Batch processing: 10x faster for multiple texts

Design Principles:
    - GPU acceleration when available
    - Batch processing for efficiency
    - Model caching to avoid reloading
    - Normalized embeddings for cosine similarity

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from Agent_Guru.security.embedding_auth import RETRIEVAL_THRESHOLD, verify_embedding
from Agent_Guru.utils.path_utils import app_data_dir

logger = logging.getLogger(__name__)

# torch is no longer imported at module scope. It was imported here only to
# pick "cuda" or "cpu", and that one line made every import of the memory
# package load torch: 532 MB on disk and most of the 1,232 MB a typed turn
# with memory loaded (measured 2026-11-04 in the development venv). The ONNX
# route below needs no torch at all, and the sentence-transformers route
# imports it when it actually loads a model.


def _onnx_folder(model_name: str) -> Path:
    """Where the ONNX export of *model_name* is kept, if it is installed.

    The installer puts model.onnx and tokenizer.json from the model's pinned
    revision here, each checked against its SHA-256. The folder is Agent
    Guru's own and not the Hugging Face cache, so the installer never writes
    into a cache another program owns.
    """
    return app_data_dir("models", "embedding", model_name.rsplit("/", 1)[-1], create=False)


class _OnnxSentenceEncoder:
    """all-MiniLM-L6-v2 run by onnxruntime, with the same encode() as SentenceTransformer.

    This exists so an install does not need torch, transformers and
    sentence-transformers for memory search: on Windows with Python 3.13 that
    stack is 221 MB more to download than onnxruntime and tokenizers alone
    (272.6 MB against 51.7 MB for the whole core, resolved against the lock).

    The computation is the one sentence-transformers performs for this model:
    the tokenizer from the same revision, truncation at 256 tokens
    (sentence_bert_config.json; tokenizer.json alone says 128), mean pooling
    of the last hidden state over the attention mask, then L2 normalisation.
    Checked on 38 texts (English, Hinglish, Devanagari, an empty string, a
    single letter and two texts longer than 256 tokens): the cosine
    similarity between the two routes' vectors was 1.000000 at the lowest,
    to six decimals, and 8 of 8 retrieval queries picked the same memory.
    The int8 export from the same repository was rejected: its lowest cosine
    was 0.973.

    Only the arguments the callers in this repository pass are accepted; an
    unexpected one is a TypeError instead of being ignored, so a caller
    relying on a SentenceTransformer feature this class lacks fails loudly.
    """

    _MAX_TOKENS = 256

    def __init__(self, folder: Path) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=self._MAX_TOKENS)
        self._tokenizer.enable_padding()
        self._session = ort.InferenceSession(str(folder / "model.onnx"), providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._dimension = int(self._session.get_outputs()[0].shape[-1])

    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension

    def encode(
        self,
        sentences: str | list[str],
        batch_size: int = 32,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False,
        show_progress_bar: bool | None = None,
    ) -> np.ndarray:
        single = isinstance(sentences, str)
        texts = [sentences] if single else list(sentences)
        chunks = []
        for start in range(0, len(texts), max(1, batch_size)):
            batch = self._tokenizer.encode_batch(texts[start:start + batch_size])
            ids = np.array([e.ids for e in batch], dtype=np.int64)
            mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.array([e.type_ids for e in batch], dtype=np.int64)
            hidden = np.asarray(self._session.run(None, feed)[0], dtype=np.float32)
            weights = mask[..., None].astype(np.float32)
            pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
            if normalize_embeddings:
                pooled = pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
            chunks.append(pooled.astype(np.float32))
        vectors = np.concatenate(chunks) if chunks else np.zeros((0, self._dimension), dtype=np.float32)
        return vectors[0] if single else vectors


def _onnx_encoder(model_name: str) -> _OnnxSentenceEncoder | None:
    """The ONNX route when its files and libraries are installed, else None."""
    folder = _onnx_folder(model_name)
    if not ((folder / "model.onnx").is_file() and (folder / "tokenizer.json").is_file()):
        return None
    try:
        return _OnnxSentenceEncoder(folder)
    except ImportError as exc:
        logger.warning("ONNX embedding files are in %s but %s; using sentence-transformers", folder, exc)
        return None


def _default_device(model_name: str) -> str:
    if (_onnx_folder(model_name) / "model.onnx").is_file():
        return "cpu"
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"

# Process-wide model cache, keyed by (model_name, device).
#
# The module docstring above has always listed "Model caching to avoid
# reloading" and the class docstring below says "The model is loaded once and
# cached for reuse" -- but no cache existed. Every EmbeddingGenerator()
# constructed a fresh SentenceTransformer, re-reading the model from disk:
# measured at 11.2 s and ~90 MB of resident weights per instance on a CPU-only
# machine. Anything that builds more than one generator (the memory retriever,
# the pruner and the storage pipeline each build their own) paid that cost
# again and held another full copy of the weights.
#
# Unbounded by design: the key space is the set of distinct models this
# process loads, which is one in practice and a handful at most. An LRU here
# would add eviction complexity to protect against nothing.
_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _load_model(model_name: str, device: str) -> Any:
    """Return a SentenceTransformer for this (model, device), loading once.

    Double-checked locking: the fast path is a plain dict lookup with no lock,
    and the lock only serialises the first concurrent loads of the same key so
    two threads starting together cannot each spend 11 s loading the same
    weights.
    """
    key = (model_name, device)
    cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached

    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is None:
            # The ONNX export wins when it is installed: same vectors, 5.4x
            # faster on the 38-text check (0.24 s against 1.31 s on the CPU),
            # and no torch in the process. Where it is not installed, as in a
            # development checkout, nothing changes.
            cached = _onnx_encoder(model_name)
            if cached is not None:
                logger.info("Loading model %s with onnxruntime (first use)", model_name)
                _MODEL_CACHE[key] = cached
                return cached

            from sentence_transformers import SentenceTransformer

            logger.info("Loading model %s on %s (first use)", model_name, device)
            # The copy already on disk is tried first, without the network. A
            # plain SentenceTransformer(name) asked huggingface.co whether each
            # of the model's files had a newer revision, even with the model
            # cached: 33 requests on every start of the app, and the load took
            # 6.1 to 6.6 s against 0.27 to 0.29 s from the cache alone (5 runs
            # each, 2026-11-02). That delay is most of what kept the first turn
            # after a start waiting out its 5 s memory budget. The network is
            # still used when the model is not cached (OSError), so a first
            # start downloads it as before. The trade-off: a cached model is
            # no longer refreshed to a newer upstream revision by itself.
            try:
                cached = SentenceTransformer(model_name, device=device, local_files_only=True)
            except OSError:
                logger.info("Model %s is not cached; downloading it", model_name)
                cached = SentenceTransformer(model_name, device=device)
            _MODEL_CACHE[key] = cached
    return cached


class EmbeddingGenerator:
    """Generate embeddings for semantic search using sentence-transformers.

    This class provides GPU-accelerated embedding generation using the
    all-MiniLM-L6-v2 model, which produces 384-dimensional embeddings
    optimized for semantic similarity search.

    The model is loaded once and cached for reuse. Embeddings are automatically
    normalized for cosine similarity computation.

    Attributes:
        model_name: Name of the sentence-transformers model
        device: Device to run model on (cuda or cpu)
        model: Loaded sentence-transformers model

    Example:
        >>> generator = EmbeddingGenerator()
        >>> embedding = generator.generate("User set a timer for 5 minutes")
        >>> print(len(embedding))
        384
        >>> # Batch processing
        >>> embeddings = generator.generate_batch([
        ...     "First text",
        ...     "Second text"
        ... ])
        >>> print(len(embeddings))
        2

    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,
    ) -> None:
        """Initialize embedding generator.

        Args:
            model_name: Name of the sentence-transformers model to use
            device: Device to run model on (cuda, cpu, or None for auto-detect)

        Raises:
            ImportError: If sentence-transformers is not installed
            RuntimeError: If model loading fails

        """
        self.model_name = model_name

        self.device = _default_device(model_name) if device is None else device

        logger.info(
            f"Initializing EmbeddingGenerator with model={model_name}, device={self.device}",
        )

        # Availability probe, kept so a missing optional dependency produces
        # the actionable message below rather than a bare ImportError from
        # inside _load_model(). The name itself is unused here -- the real
        # import happens in _load_model(). It is skipped when the ONNX export
        # is installed, which is the route an install without torch takes.
        if not (_onnx_folder(model_name) / "model.onnx").is_file():
            try:
                import sentence_transformers  # noqa: F401
            except ImportError as e:
                msg = (
                    "sentence-transformers is required for embedding generation. "
                    "Install with: pip install sentence-transformers"
                )
                raise ImportError(
                    msg,
                ) from e

        # Load model
        try:
            # Shared across instances -- see _MODEL_CACHE above. Nothing in
            # this class mutates the model, only calls encode() on it, which
            # is a read-only forward pass.
            self.model = _load_model(model_name, self.device)
            logger.info("Successfully loaded model on %s", self.device)
        except Exception as e:
            logger.exception("Failed to load model")
            msg = f"Failed to load embedding model: {e}"
            raise RuntimeError(msg) from e

    def generate(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Time Complexity: O(n) where n is text length
        Space Complexity: O(1) - fixed 384-dim output

        Args:
            text: Text to generate embedding for

        Returns:
            384-dimensional normalized embedding vector

        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails

        Example:
            >>> generator = EmbeddingGenerator()
            >>> embedding = generator.generate("Hello world")
            >>> len(embedding)
            384

        """
        if not text or not text.strip():
            msg = "Text cannot be empty"
            raise ValueError(msg)

        try:
            # Generate embedding (automatically normalized by sentence-transformers)
            embedding = self.model.encode(
                text.strip(),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            # Convert to list for JSON serialization
            return embedding.tolist()

        except Exception as e:
            logger.exception("Failed to generate embedding")
            msg = f"Embedding generation failed: {e}"
            raise RuntimeError(msg) from e

    def generate_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts (10x faster than individual).

        Time Complexity: O(n*m) where n is number of texts, m is avg text length
        Space Complexity: O(n) for output embeddings

        Args:
            texts: List of texts to generate embeddings for
            batch_size: Batch size for processing (default 32)

        Returns:
            List of 384-dimensional normalized embedding vectors

        Raises:
            ValueError: If texts list is empty or contains empty strings
            RuntimeError: If embedding generation fails

        Example:
            >>> generator = EmbeddingGenerator()
            >>> embeddings = generator.generate_batch([
            ...     "First text",
            ...     "Second text",
            ...     "Third text"
            ... ])
            >>> len(embeddings)
            3

        """
        if not texts:
            msg = "Texts list cannot be empty"
            raise ValueError(msg)

        # Validate all texts are non-empty
        cleaned_texts = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                msg = f"Text at index {i} is empty"
                raise ValueError(msg)
            cleaned_texts.append(text.strip())

        try:
            # Generate embeddings in batch (much faster than individual)
            embeddings = self.model.encode(
                cleaned_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            # Convert to list of lists for JSON serialization
            return embeddings.tolist()

        except Exception as e:
            logger.exception("Failed to generate batch embeddings")
            msg = f"Batch embedding generation failed: {e}"
            raise RuntimeError(msg) from e

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model.

        Returns:
            Embedding dimension (384 for all-MiniLM-L6-v2)

        Example:
            >>> generator = EmbeddingGenerator()
            >>> generator.get_embedding_dimension()
            384

        """
        return self.model.get_sentence_embedding_dimension()

    def compute_similarity(
        self,
        embedding1: list[float] | np.ndarray,
        embedding2: list[float] | np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Time Complexity: O(d) where d is embedding dimension
        Space Complexity: O(1)

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between -1.0 and 1.0

        Raises:
            ValueError: If embeddings have different dimensions

        Example::

            >>> generator = EmbeddingGenerator()
            >>> emb1 = generator.generate("Hello world")
            >>> emb2 = generator.generate("Hi there")
            >>> similarity = generator.compute_similarity(emb1, emb2)
            >>> 0.0 <= similarity <= 1.0
            True

        """
        # Convert to numpy arrays
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)

        if arr1.shape != arr2.shape:
            msg = f"Embeddings must have same dimension: {arr1.shape} vs {arr2.shape}"
            raise ValueError(msg)

        # Compute cosine similarity (dot product of normalized vectors)
        similarity = np.dot(arr1, arr2)

        # Clamp to [-1, 1] to handle floating point errors
        return float(np.clip(similarity, -1.0, 1.0))

    def is_similar(
        self,
        embedding1: list[float] | np.ndarray,
        embedding2: list[float] | np.ndarray,
        threshold: float = RETRIEVAL_THRESHOLD,
    ) -> bool:
        """Return True iff cosine similarity between the two embeddings >= *threshold*.

        Enforces the retrieval threshold via
        :func:`~Agent_Guru.security.embedding_auth.verify_embedding`
        (CWE-200/284/20 fix).

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.
            threshold: Minimum cosine similarity for a positive match.
                Defaults to :data:`~Agent_Guru.security.embedding_auth.RETRIEVAL_THRESHOLD` (0.35).

        Returns:
            ``True`` if similarity >= *threshold*, ``False`` otherwise.

        """
        arr1 = np.array(embedding1, dtype=np.float32)
        arr2 = np.array(embedding2, dtype=np.float32)
        return verify_embedding(arr1, arr2, threshold)
