"""
Property-based tests for Agent_Guru.vision.training.preprocess.

Property 1:  Dataset Preprocessing Completeness
Property 26: Minimum Dataset Size Validation
Property 28: Multiple Face Selection (largest by area)
Property 29: No-Face Image Handling
Property 30: Dataset Structure Acceptance

Validates: Requirements 1.2, 2.1, 2.4, 2.5, 29.1
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from Agent_Guru.vision.training.preprocess import (
    check_minimum_images,
    preprocess_dataset,
    validate_dataset_structure,
    _select_largest,
)


# ---------------------------------------------------------------------------
# Helpers — build temporary dataset directories on disk
# ---------------------------------------------------------------------------

def _make_dataset(
    tmp_dir: str,
    identities: List[Tuple[str, int]],
) -> str:
    """Create a minimal dataset directory structure with empty .jpg files.

    Args:
        tmp_dir: Root temp directory.
        identities: List of (name, image_count) tuples.

    Returns:
        Path to the dataset root.
    """
    dataset_root = os.path.join(tmp_dir, "dataset")
    os.makedirs(dataset_root, exist_ok=True)
    for name, count in identities:
        identity_dir = os.path.join(dataset_root, name)
        os.makedirs(identity_dir, exist_ok=True)
        for i in range(count):
            # Write a minimal valid 1x1 BGR image using numpy raw bytes.
            img_path = os.path.join(identity_dir, f"img_{i:04d}.jpg")
            # Create a tiny valid JPEG-like file (just needs to exist and be
            # loadable; we use a 1x1 numpy array saved via PIL if available,
            # otherwise write a placeholder that our stub loader handles).
            _write_tiny_image(img_path)
    return dataset_root


def _write_tiny_image(path: str) -> None:
    """Write a 4x4 white BGR image to path."""
    try:
        import cv2  # type: ignore[import]
        img = np.full((4, 4, 3), 200, dtype=np.uint8)
        cv2.imwrite(path, img)
        return
    except ImportError:
        pass
    try:
        from PIL import Image  # type: ignore[import]
        Image.fromarray(np.full((4, 4, 3), 200, dtype=np.uint8)).save(path)
        return
    except ImportError:
        pass
    # Last resort: write a non-empty placeholder (loader will return None,
    # which is handled as skipped_error — acceptable for structure tests).
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 16)  # minimal JPEG header


# ---------------------------------------------------------------------------
# Stub detector / aligner that always succeed
# ---------------------------------------------------------------------------

@dataclass
class _FakeBbox:
    bbox: Tuple[int, int, int, int]
    confidence: float = 1.0


class _AlwaysDetectDetector:
    """Returns a single detection for every frame."""

    def detect(self, frame: np.ndarray) -> List[_FakeBbox]:
        h, w = frame.shape[:2]
        return [_FakeBbox(bbox=(0, 0, w, h))]


class _MultiDetectDetector:
    """Returns N detections of increasing size."""

    def __init__(self, n: int = 3) -> None:
        self.n = n

    def detect(self, frame: np.ndarray) -> List[_FakeBbox]:
        return [_FakeBbox(bbox=(0, 0, 10 * (i + 1), 10 * (i + 1))) for i in range(self.n)]


class _NoFaceDetector:
    """Never detects any face."""

    def detect(self, frame: np.ndarray) -> List[_FakeBbox]:
        return []


class _IdentityAligner:
    """Returns a 112x112 blank aligned face."""

    def align(self, frame: np.ndarray, detection: object) -> np.ndarray:
        return np.zeros((112, 112, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Property 30: Dataset Structure Acceptance
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(
    n_identities=st.integers(min_value=1, max_value=5),
    images_per_identity=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=30)
def test_valid_dataset_structure_accepted(
    n_identities: int, images_per_identity: int
) -> None:
    """validate_dataset_structure() must return True for any valid layout."""
    with tempfile.TemporaryDirectory() as tmp:
        identities = [(f"person_{i}", images_per_identity) for i in range(n_identities)]
        dataset_root = _make_dataset(tmp, identities)
        is_valid, errors = validate_dataset_structure(dataset_root)
        assert is_valid, f"Expected valid dataset, got errors: {errors}"


@pytest.mark.property
def test_missing_dataset_dir_rejected() -> None:
    """validate_dataset_structure() must reject a non-existent path."""
    is_valid, errors = validate_dataset_structure("/nonexistent/path/xyz")
    assert not is_valid
    assert len(errors) > 0


@pytest.mark.property
def test_empty_dataset_dir_rejected() -> None:
    """validate_dataset_structure() must reject a directory with no sub-dirs."""
    with tempfile.TemporaryDirectory() as tmp:
        is_valid, errors = validate_dataset_structure(tmp)
        assert not is_valid


# ---------------------------------------------------------------------------
# Property 26: Minimum Dataset Size Validation
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(
    n_identities=st.integers(min_value=1, max_value=4),
    images_per_identity=st.integers(min_value=0, max_value=60),
)
@settings(max_examples=30)
def test_check_minimum_images_counts_correctly(
    n_identities: int, images_per_identity: int
) -> None:
    """check_minimum_images() must return exact image counts per identity."""
    with tempfile.TemporaryDirectory() as tmp:
        identities = [(f"id_{i}", images_per_identity) for i in range(n_identities)]
        dataset_root = _make_dataset(tmp, identities)
        counts = check_minimum_images(dataset_root)
        assert len(counts) == n_identities
        for name, count in counts.items():
            assert count == images_per_identity, (
                f"Expected {images_per_identity} for {name}, got {count}"
            )


# ---------------------------------------------------------------------------
# Property 29: No-Face Image Handling
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(n_images=st.integers(min_value=1, max_value=10))
@settings(max_examples=20)
def test_no_face_images_are_skipped(n_images: int) -> None:
    """Images with no detected face must be counted in skipped_no_face."""
    with tempfile.TemporaryDirectory() as tmp:
        dataset_root = _make_dataset(tmp, [("person_a", n_images)])
        out_dir = os.path.join(tmp, "aligned")
        report = preprocess_dataset(
            dataset_root,
            out_dir,
            detector=_NoFaceDetector(),
            aligner=_IdentityAligner(),
        )
        stats = report.per_identity.get("person_a")
        assert stats is not None
        # All images that were loadable should be in skipped_no_face or skipped_error
        assert stats.processed == 0
        assert stats.skipped_no_face + stats.skipped_error == stats.total_images


# ---------------------------------------------------------------------------
# Property 28: Multiple Face Selection (largest by area)
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(n_faces=st.integers(min_value=2, max_value=6))
@settings(max_examples=30)
def test_largest_face_selected(n_faces: int) -> None:
    """_select_largest() must return the detection with the biggest bbox area."""
    detections = [_FakeBbox(bbox=(0, 0, 10 * i, 10 * i)) for i in range(1, n_faces + 1)]
    selected = _select_largest(detections)
    expected_area = (10 * n_faces) ** 2
    _, _, w, h = selected.bbox
    assert w * h == expected_area


# ---------------------------------------------------------------------------
# Property 1: Dataset Preprocessing Completeness
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(
    n_identities=st.integers(min_value=1, max_value=3),
    n_images=st.integers(min_value=1, max_value=8),
)
@settings(max_examples=20)
def test_preprocessing_report_totals_consistent(
    n_identities: int, n_images: int
) -> None:
    """Report totals must equal sum of per-identity stats."""
    with tempfile.TemporaryDirectory() as tmp:
        identities = [(f"id_{i}", n_images) for i in range(n_identities)]
        dataset_root = _make_dataset(tmp, identities)
        out_dir = os.path.join(tmp, "aligned")
        report = preprocess_dataset(
            dataset_root,
            out_dir,
            detector=_AlwaysDetectDetector(),
            aligner=_IdentityAligner(),
        )
        # Totals must be consistent with per-identity breakdown
        assert report.total_identities == n_identities
        assert report.total_images_found == sum(
            s.total_images for s in report.per_identity.values()
        )
        assert report.total_images_processed == sum(
            s.processed for s in report.per_identity.values()
        )
        assert report.total_skipped_no_face == sum(
            s.skipped_no_face for s in report.per_identity.values()
        )
        assert report.total_skipped_error == sum(
            s.skipped_error for s in report.per_identity.values()
        )
        # processed + skipped_no_face + skipped_error == total_images (per identity)
        for stats in report.per_identity.values():
            assert (
                stats.processed + stats.skipped_no_face + stats.skipped_error
                == stats.total_images
            )
