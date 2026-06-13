"""Module: Agent_Guru.vision.training.preprocess
Purpose: Dataset preprocessing for ArcFace training.

Validates dataset structure, checks minimum image counts per identity,
detects and aligns faces, and writes aligned images to an output directory.
Generates a preprocessing report with per-identity statistics.

Expected dataset layout:
    dataset/
        IdentityA/
            img001.jpg
            img002.jpg
            ...
        IdentityB/
            ...

Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 29.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger("guruvision.training.preprocess")

# Minimum images required per identity for training.
MIN_IMAGES_PER_IDENTITY: int = 50

# Supported image extensions.
_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"},
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class IdentityStats:
    """Per-identity preprocessing statistics.

    Attributes:
        name: Identity name (directory name).
        total_images: Total images found in the source directory.
        processed: Images successfully aligned and saved.
        skipped_no_face: Images skipped because no face was detected.
        skipped_error: Images skipped due to read/processing errors.

    """

    name: str
    total_images: int = 0
    processed: int = 0
    skipped_no_face: int = 0
    skipped_error: int = 0


@dataclass
class PreprocessingReport:
    """Summary report produced after dataset preprocessing.

    Attributes:
        total_identities: Number of identity directories found.
        valid_identities: Identities with >= MIN_IMAGES_PER_IDENTITY processed images.
        total_images_found: Total source images across all identities.
        total_images_processed: Total aligned images written.
        total_skipped_no_face: Images skipped due to missing face.
        total_skipped_error: Images skipped due to errors.
        per_identity: Per-identity breakdown.
        warnings: Non-fatal warnings accumulated during preprocessing.

    """

    total_identities: int = 0
    valid_identities: int = 0
    total_images_found: int = 0
    total_images_processed: int = 0
    total_skipped_no_face: int = 0
    total_skipped_error: int = 0
    per_identity: dict[str, IdentityStats] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_dataset_structure(dataset_dir: str) -> tuple[bool, list[str]]:
    """Check that dataset_dir follows the expected layout.

    Expected: dataset_dir/{IdentityName}/*.{jpg,png,...}

    Args:
        dataset_dir: Path to the root dataset directory.

    Returns:
        (is_valid, errors) — is_valid is True when at least one identity
        sub-directory containing at least one image file is found.
        errors is a list of human-readable problem descriptions.

    """
    errors: list[str] = []
    root = Path(dataset_dir)

    if not root.exists():
        errors.append(f"Dataset directory does not exist: {dataset_dir}")
        return False, errors

    if not root.is_dir():
        errors.append(f"Dataset path is not a directory: {dataset_dir}")
        return False, errors

    identity_dirs = [p for p in root.iterdir() if p.is_dir()]
    if not identity_dirs:
        errors.append(f"No identity sub-directories found in: {dataset_dir}")
        return False, errors

    valid_identities = 0
    for identity_dir in identity_dirs:
        images = _list_images(identity_dir)
        if not images:
            errors.append(f"Identity '{identity_dir.name}' has no supported image files")
        else:
            valid_identities += 1

    if valid_identities == 0:
        errors.append("No identity directories contain any image files")
        return False, errors

    return True, errors


def check_minimum_images(dataset_dir: str) -> dict[str, int]:
    """Return a mapping of identity → image count for all identities.

    Identities with fewer than MIN_IMAGES_PER_IDENTITY images are flagged
    via a WARNING log message.

    Args:
        dataset_dir: Path to the root dataset directory.

    Returns:
        Dict mapping identity name to the number of image files found.

    """
    root = Path(dataset_dir)
    counts: dict[str, int] = {}

    for identity_dir in sorted(root.iterdir()):
        if not identity_dir.is_dir():
            continue
        images = _list_images(identity_dir)
        counts[identity_dir.name] = len(images)
        if len(images) < MIN_IMAGES_PER_IDENTITY:
            logger.warning(
                "Identity '%s' has only %d images (minimum %d required)",
                identity_dir.name,
                len(images),
                MIN_IMAGES_PER_IDENTITY,
            )

    return counts


def preprocess_dataset(
    dataset_dir: str,
    output_dir: str,
    detector: object | None = None,
    aligner: object | None = None,
) -> PreprocessingReport:
    """Detect, align, and save faces from a raw dataset.

    For each image in dataset_dir/{Identity}/:
    - Detect all faces.
    - If no face found: log warning and skip.
    - If multiple faces found: select the largest by bounding-box area.
    - Align the selected face to 112x112.
    - Save to output_dir/{Identity}/{original_filename}.

    Args:
        dataset_dir: Root directory of the raw dataset.
        output_dir: Root directory where aligned images will be written.
        detector: Optional FaceDetector instance.  When None a stub that
            returns an empty list is used (useful for unit testing).
        aligner: Optional FaceAligner instance.  When None a stub that
            returns a blank 112x112 image is used.

    Returns:
        PreprocessingReport with full statistics.

    """
    report = PreprocessingReport()
    root = Path(dataset_dir)
    out_root = Path(output_dir)

    # Use stubs when real modules are not provided (test / no-model mode).
    _detector = detector or _StubDetector()
    _aligner = aligner or _StubAligner()

    identity_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    report.total_identities = len(identity_dirs)

    for identity_dir in identity_dirs:
        stats = IdentityStats(name=identity_dir.name)
        images = _list_images(identity_dir)
        stats.total_images = len(images)

        out_identity_dir = out_root / identity_dir.name
        out_identity_dir.mkdir(parents=True, exist_ok=True)

        for img_path in images:
            frame = _load_image(img_path)
            if frame is None:
                stats.skipped_error += 1
                logger.warning("Failed to load image: %s", img_path)
                continue

            try:
                detections = _detector.detect(frame)
            except Exception:
                stats.skipped_error += 1
                logger.exception("Detection failed for %s: %s")
                continue

            if not detections:
                stats.skipped_no_face += 1
                logger.debug("No face detected in: %s", img_path)
                continue

            # Select largest face by bounding-box area.
            detection = _select_largest(detections)

            try:
                aligned = _aligner.align(frame, detection)
            except Exception:
                stats.skipped_error += 1
                logger.exception("Alignment failed for %s: %s")
                continue

            out_path = out_identity_dir / img_path.name
            if not _save_image(aligned, out_path):
                stats.skipped_error += 1
                continue

            stats.processed += 1

        if stats.processed < MIN_IMAGES_PER_IDENTITY:
            msg = (
                f"Identity '{identity_dir.name}' has only {stats.processed} "
                f"aligned images (minimum {MIN_IMAGES_PER_IDENTITY})"
            )
            report.warnings.append(msg)
            logger.warning(msg)
        else:
            report.valid_identities += 1

        report.per_identity[identity_dir.name] = stats
        report.total_images_found += stats.total_images
        report.total_images_processed += stats.processed
        report.total_skipped_no_face += stats.skipped_no_face
        report.total_skipped_error += stats.skipped_error

    logger.info(
        "Preprocessing complete: %d/%d identities valid, %d/%d images processed",
        report.valid_identities,
        report.total_identities,
        report.total_images_processed,
        report.total_images_found,
    )
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _list_images(directory: Path) -> list[Path]:
    """Return sorted list of image files in directory (non-recursive)."""
    return sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )


def _load_image(path: Path) -> np.ndarray | None:
    """Load an image as a BGR uint8 numpy array."""
    try:
        import cv2  # type: ignore[import]

        img = cv2.imread(str(path))
        if img is None:
            return None
        return img
    except ImportError:
        pass

    # Fallback: try PIL
    try:
        import numpy as np
        from PIL import Image  # type: ignore[import]

        pil_img = Image.open(path).convert("RGB")
        rgb = np.array(pil_img, dtype=np.uint8)
        return rgb[:, :, ::-1]  # RGB → BGR
    except Exception:
        return None


def _save_image(image: np.ndarray, path: Path) -> bool:
    """Save a BGR uint8 numpy array to disk."""
    try:
        import cv2  # type: ignore[import]

        return cv2.imwrite(str(path), image)
    except ImportError:
        pass

    try:
        from PIL import Image  # type: ignore[import]

        rgb = image[:, :, ::-1]  # BGR → RGB
        Image.fromarray(rgb).save(str(path))
        return True
    except Exception:
        logger.exception("Failed to save image to %s: %s")
        return False


def _select_largest(detections: list[object]) -> object:
    """Return the detection with the largest bounding-box area."""

    def _area(det: object) -> int:
        bbox = det.bbox if hasattr(det, "bbox") else det  # type: ignore[union-attr]
        _, _, w, h = bbox
        return int(w) * int(h)

    return max(detections, key=_area)


# ---------------------------------------------------------------------------
# Stubs for test / no-model mode
# ---------------------------------------------------------------------------


class _StubDetector:
    """Returns an empty detection list — simulates no-face scenario."""

    def detect(self, frame: np.ndarray) -> list[object]:
        return []


class _StubAligner:
    """Returns a blank 112x112 uint8 image."""

    def align(self, frame: np.ndarray, detection: object) -> np.ndarray:
        return np.zeros((112, 112, 3), dtype=np.uint8)
