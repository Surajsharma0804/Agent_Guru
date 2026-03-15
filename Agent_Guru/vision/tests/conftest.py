"""Shared fixtures for vision module tests."""

from __future__ import annotations

import io
import struct
import zlib
from typing import Generator

import numpy as np
import pytest

from Agent_Guru.vision.face_features import FaceFeatureExtractor


# ---------------------------------------------------------------------------
# Minimal valid image helpers (no external dependencies)
# ---------------------------------------------------------------------------


def _make_png(width: int = 64, height: int = 64, fill: int = 128) -> bytes:
    """Create a minimal valid PNG image in memory.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        fill: Grey fill value (0-255)

    Returns:
        PNG-encoded bytes
    """
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(name: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        return length + name + data + crc

    # IHDR: width, height, bit depth=8, colour type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    # IDAT: raw RGB scanlines, each prefixed with filter byte 0
    raw_rows = b""
    for _ in range(height):
        row = bytes([fill] * (width * 3))
        raw_rows += b"\x00" + row
    compressed = zlib.compress(raw_rows)
    idat = chunk(b"IDAT", compressed)

    # IEND
    iend = chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


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
