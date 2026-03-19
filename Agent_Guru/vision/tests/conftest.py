"""Shared fixtures for vision module tests.

Covers both the existing face-recognition tests and the new vision-system
tests (scene, depth, OCR, gesture, pose, screen, VQA, tracking, activity,
bus, dispatcher, model manager).
"""

from __future__ import annotations

import io
import struct
import threading
import zlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from Agent_Guru.vision.face_features import FaceFeatureExtractor
from Agent_Guru.vision.vision_models import (
    BoundingBox,
    VisionConfig,
    VisionEvent,
)


# ---------------------------------------------------------------------------
# Class-level cache isolation — prevents test order-dependent failures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_insightface_cache() -> Any:
    """Save and restore FaceFeatureExtractor class-level InsightFace cache.

    Some tests (e.g. TestInsightfaceDetect, TestInsightfaceExtract) inject
    mock apps directly into the class-level ``_shared_app`` / ``_shared_events``
    dicts.  Without teardown, those mocks leak into subsequent tests and cause
    order-dependent failures (e.g. Hypothesis replaying a saved example against
    a mock instead of the real extractor).

    This autouse fixture snapshots the cache before each test and restores it
    afterwards, giving every test a clean slate without slowing down tests that
    don't touch the cache.
    """
    # Snapshot
    saved_app = dict(FaceFeatureExtractor._shared_app)
    saved_events: dict[bool, threading.Event] = {}
    for k, ev in FaceFeatureExtractor._shared_events.items():
        saved_events[k] = ev

    yield

    # Restore — replace contents in-place so existing references stay valid
    FaceFeatureExtractor._shared_app.clear()
    FaceFeatureExtractor._shared_app.update(saved_app)
    FaceFeatureExtractor._shared_events.clear()
    FaceFeatureExtractor._shared_events.update(saved_events)


# ---------------------------------------------------------------------------
# Minimal valid image helpers (no external dependencies)
# ---------------------------------------------------------------------------


def _make_png(width: int = 64, height: int = 64, fill: int = 128) -> bytes:
    """Create a minimal valid PNG image in memory.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        fill: Grey fill value (0-255).

    Returns:
        PNG-encoded bytes.
    """
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(name: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        return length + name + data + crc

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    raw_rows = b""
    for _ in range(height):
        row = bytes([fill] * (width * 3))
        raw_rows += b"\x00" + row
    compressed = zlib.compress(raw_rows)
    idat = chunk(b"IDAT", compressed)
    iend = chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Face-recognition fixtures (kept for backward compatibility)
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_image_bytes() -> bytes:
    """A minimal valid 64×64 grey PNG image."""
    return _make_png(64, 64, fill=128)


@pytest.fixture
def small_image_bytes() -> bytes:
    """A very small 8×8 PNG image."""
    return _make_png(8, 8, fill=200)


@pytest.fixture
def extractor() -> FaceFeatureExtractor:
    """A default FaceFeatureExtractor instance."""
    return FaceFeatureExtractor()


# ---------------------------------------------------------------------------
# Synthetic frame generators (vision system)
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_frame_rgb() -> np.ndarray:
    """A 480×640×3 uint8 RGB frame filled with random noise."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def synthetic_frame_dark() -> np.ndarray:
    """A 480×640×3 uint8 RGB frame with mean brightness < 20 (very dark)."""
    return np.full((480, 640, 3), 5, dtype=np.uint8)


@pytest.fixture
def synthetic_frame_1080p() -> np.ndarray:
    """A 1080×1920×3 uint8 RGB frame for latency tests."""
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)


def make_frame(height: int = 480, width: int = 640, brightness: int = 128) -> np.ndarray:
    """Create a synthetic RGB frame with uniform brightness.

    Args:
        height: Frame height in pixels.
        width: Frame width in pixels.
        brightness: Pixel fill value in [0, 255].

    Returns:
        uint8 ndarray of shape (height, width, 3).
    """
    return np.full((height, width, 3), brightness, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Mock ONNX session
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_onnx_session() -> MagicMock:
    """A MagicMock that mimics an onnxruntime.InferenceSession.

    The mock's ``run`` method returns a list containing a single float32
    zeros array of shape (1, 10) by default.
    """
    session = MagicMock()
    session.get_inputs.return_value = [MagicMock(name="input", shape=[1, 3, 224, 224])]
    session.get_outputs.return_value = [MagicMock(name="output", shape=[1, 10])]
    session.run.return_value = [np.zeros((1, 10), dtype=np.float32)]
    return session


# ---------------------------------------------------------------------------
# VisionConfig fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def default_vision_config() -> VisionConfig:
    """A VisionConfig with default values."""
    return VisionConfig()


@pytest.fixture
def gpu_disabled_config() -> VisionConfig:
    """A VisionConfig with GPU disabled."""
    return VisionConfig(gpu_enabled=False)


# ---------------------------------------------------------------------------
# VisionEvent factory
# ---------------------------------------------------------------------------


def make_vision_event(
    event_type: str = "object_detected",
    source_module: str = "scene",
    confidence: float = 0.9,
    **metadata: Any,
) -> VisionEvent:
    """Create a VisionEvent with sensible defaults.

    Args:
        event_type: Event type string.
        source_module: Originating module name.
        confidence: Event confidence score.
        **metadata: Extra metadata key-value pairs.

    Returns:
        A populated VisionEvent.
    """
    return VisionEvent(
        event_type=event_type,
        timestamp=VisionEvent.now_timestamp(),
        source_module=source_module,
        confidence=confidence,
        metadata=dict(metadata),
    )


@pytest.fixture
def sample_vision_event() -> VisionEvent:
    """A sample VisionEvent for bus/dispatcher tests."""
    return make_vision_event()


# ---------------------------------------------------------------------------
# BoundingBox factory
# ---------------------------------------------------------------------------


def make_bbox(x: float = 10.0, y: float = 10.0, w: float = 50.0, h: float = 50.0) -> BoundingBox:
    """Create a BoundingBox with given coordinates."""
    return BoundingBox(x=x, y=y, width=w, height=h)
