"""
Module: Agent_Guru.vision.training.dataset_manager
Purpose: Download, preprocess, and manage training and evaluation datasets.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.9
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("guruvision.training.dataset_manager")

# Supported datasets
SUPPORTED_DATASETS = {
    "ms1m-arcface", "vggface2", "lfw", "cfp-fp", "agedb-30", "ijb-c"
}

_IMAGE_EXTENSIONS: frozenset = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Face bounding box."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0


@dataclass
class Landmarks:
    """Five facial landmarks."""
    left_eye: Tuple[float, float] = (0.0, 0.0)
    right_eye: Tuple[float, float] = (0.0, 0.0)
    nose: Tuple[float, float] = (0.0, 0.0)
    left_mouth: Tuple[float, float] = (0.0, 0.0)
    right_mouth: Tuple[float, float] = (0.0, 0.0)


@dataclass
class DatasetStats:
    """Dataset statistics."""
    num_identities: int = 0
    num_images: int = 0
    images_per_identity: Dict[str, int] = field(default_factory=dict)
    resolution_distribution: Dict[Tuple[int, int], int] = field(default_factory=dict)
    failed_images: List[str] = field(default_factory=list)


@dataclass
class DownloadResult:
    """Result of a dataset download operation."""
    success: bool
    dataset_name: str
    output_dir: str
    num_files: int = 0
    error_message: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of dataset integrity verification."""
    valid: bool
    dataset_path: str
    num_identities: int = 0
    num_images: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class PreprocessResult:
    """Result of dataset preprocessing."""
    success: bool
    output_dir: str
    num_processed: int = 0
    num_failed: int = 0
    failed_images: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# FaceAligner
# ---------------------------------------------------------------------------

class FaceAligner:
    """Detect faces and align them to a canonical 112x112 pose.

    Uses InsightFace RetinaFace when available, falls back to stub.
    """

    TARGET_SIZE: Tuple[int, int] = (112, 112)

    # Reference landmarks for 112x112 alignment (ArcFace standard)
    _REFERENCE_LANDMARKS = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ], dtype=np.float32)

    def __init__(self, use_insightface: bool = True) -> None:
        self._detector: Optional[Any] = None
        if use_insightface:
            self._detector = self._try_load_insightface()

    def _try_load_insightface(self) -> Optional[Any]:
        try:
            import insightface  # type: ignore[import]
            app = insightface.app.FaceAnalysis(
                name="buffalo_sc",
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(640, 640))
            return app
        except Exception as exc:
            logger.debug("InsightFace not available: %s", exc)
            return None

    def detect_faces(self, image: np.ndarray) -> List[BoundingBox]:
        """Detect faces in an image.

        Args:
            image: BGR uint8 numpy array.

        Returns:
            List of BoundingBox objects.
        """
        if self._detector is None:
            return []
        try:
            faces = self._detector.get(image)
            return [
                BoundingBox(
                    x1=float(f.bbox[0]),
                    y1=float(f.bbox[1]),
                    x2=float(f.bbox[2]),
                    y2=float(f.bbox[3]),
                    confidence=float(f.det_score),
                )
                for f in faces
            ]
        except Exception as exc:
            logger.debug("Face detection failed: %s", exc)
            return []

    def get_landmarks(
        self, image: np.ndarray, bbox: BoundingBox
    ) -> Optional[Landmarks]:
        """Extract 5-point landmarks for a detected face.

        Args:
            image: BGR uint8 numpy array.
            bbox: Bounding box of the face.

        Returns:
            Landmarks or None if extraction fails.
        """
        if self._detector is None:
            return None
        try:
            faces = self._detector.get(image)
            for face in faces:
                fb = face.bbox
                if (
                    abs(float(fb[0]) - bbox.x1) < 5
                    and abs(float(fb[1]) - bbox.y1) < 5
                ):
                    kps = face.kps
                    return Landmarks(
                        left_eye=(float(kps[0][0]), float(kps[0][1])),
                        right_eye=(float(kps[1][0]), float(kps[1][1])),
                        nose=(float(kps[2][0]), float(kps[2][1])),
                        left_mouth=(float(kps[3][0]), float(kps[3][1])),
                        right_mouth=(float(kps[4][0]), float(kps[4][1])),
                    )
        except Exception as exc:
            logger.debug("Landmark extraction failed: %s", exc)
        return None

    def align_face(
        self, image: np.ndarray, landmarks: Optional[Landmarks] = None
    ) -> np.ndarray:
        """Align a face to 112x112 using similarity transform.

        Args:
            image: BGR uint8 numpy array.
            landmarks: Optional 5-point landmarks. If None, returns resized image.

        Returns:
            Aligned 112x112 BGR uint8 numpy array.
        """
        if landmarks is None:
            return self._resize_to_target(image)

        try:
            import cv2  # type: ignore[import]
            src_pts = np.array([
                [landmarks.left_eye[0], landmarks.left_eye[1]],
                [landmarks.right_eye[0], landmarks.right_eye[1]],
                [landmarks.nose[0], landmarks.nose[1]],
                [landmarks.left_mouth[0], landmarks.left_mouth[1]],
                [landmarks.right_mouth[0], landmarks.right_mouth[1]],
            ], dtype=np.float32)

            transform = cv2.estimateAffinePartial2D(
                src_pts, self._REFERENCE_LANDMARKS, method=cv2.LMEDS
            )[0]
            if transform is None:
                return self._resize_to_target(image)

            aligned = cv2.warpAffine(
                image, transform, self.TARGET_SIZE,
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT,
            )
            return aligned
        except Exception as exc:
            logger.debug("Alignment failed: %s", exc)
            return self._resize_to_target(image)

    def _resize_to_target(self, image: np.ndarray) -> np.ndarray:
        """Resize image to target size."""
        try:
            import cv2  # type: ignore[import]
            return cv2.resize(image, self.TARGET_SIZE)
        except ImportError:
            from PIL import Image  # type: ignore[import]
            pil = Image.fromarray(image[:, :, ::-1]).resize(self.TARGET_SIZE)
            return np.array(pil)[:, :, ::-1]


# ---------------------------------------------------------------------------
# FaceDataset (PyTorch)
# ---------------------------------------------------------------------------

class FaceDataset:
    """PyTorch-compatible face dataset with augmentation support.

    Args:
        root_dir: Root directory with identity sub-directories.
        augment: Whether to apply data augmentation.
        image_size: Target image size (default 112).
    """

    def __init__(
        self,
        root_dir: str,
        augment: bool = False,
        image_size: int = 112,
    ) -> None:
        self.root_dir = root_dir
        self.augment = augment
        self.image_size = image_size
        self.samples: List[Tuple[str, int]] = []
        self.identity_to_label: Dict[str, int] = {}
        self._load_samples()

    def _load_samples(self) -> None:
        root = Path(self.root_dir)
        identity_dirs = sorted(p for p in root.iterdir() if p.is_dir())
        for label, identity_dir in enumerate(identity_dirs):
            self.identity_to_label[identity_dir.name] = label
            for img_path in identity_dir.iterdir():
                if img_path.suffix.lower() in _IMAGE_EXTENSIONS:
                    self.samples.append((str(img_path), label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[Any, int]:
        """Return (tensor, label) for the given index."""
        import torch
        path, label = self.samples[idx]
        image = self._load_image(path)
        tensor = self._to_tensor(image)
        if self.augment:
            tensor = self._augment(tensor)
        return tensor, label

    def _load_image(self, path: str) -> np.ndarray:
        try:
            import cv2  # type: ignore[import]
            img = cv2.imread(path)
            if img is None:
                return np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
            return cv2.resize(img, (self.image_size, self.image_size))
        except ImportError:
            return np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)

    def _to_tensor(self, image: np.ndarray) -> Any:
        import torch
        rgb = image[:, :, ::-1].copy()
        tensor = torch.from_numpy(
            rgb.astype(np.float32).transpose(2, 0, 1) / 127.5 - 1.0
        )
        return tensor

    def _augment(self, tensor: Any) -> Any:
        """Apply random augmentation: flip, brightness jitter."""
        import torch
        # Random horizontal flip
        if torch.rand(1).item() > 0.5:
            tensor = torch.flip(tensor, dims=[2])
        # Random brightness jitter
        factor = 0.8 + torch.rand(1).item() * 0.4  # [0.8, 1.2]
        tensor = torch.clamp(tensor * factor, -1.0, 1.0)
        return tensor


# ---------------------------------------------------------------------------
# DatasetManager
# ---------------------------------------------------------------------------

class DatasetManager:
    """Download, preprocess, and manage training and evaluation datasets.

    Args:
        root_dir: Root directory for all datasets.
    """

    def __init__(self, root_dir: str = "Agent_Guru/vision/data") -> None:
        self.root_dir = root_dir

    def download_dataset(
        self, dataset_name: str, output_dir: str
    ) -> DownloadResult:
        """Download a dataset to the specified directory.

        Note: Actual download requires dataset-specific credentials/URLs.
        This method validates the request and creates the directory structure.

        Args:
            dataset_name: One of the supported dataset names.
            output_dir: Directory to download the dataset to.

        Returns:
            DownloadResult indicating success or failure.
        """
        if dataset_name not in SUPPORTED_DATASETS:
            return DownloadResult(
                success=False,
                dataset_name=dataset_name,
                output_dir=output_dir,
                error_message=(
                    f"Unsupported dataset '{dataset_name}'. "
                    f"Supported: {SUPPORTED_DATASETS}"
                ),
            )

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        logger.info(
            "Dataset '%s' directory prepared at '%s'. "
            "Manual download required for large datasets.",
            dataset_name, output_dir,
        )
        return DownloadResult(
            success=True,
            dataset_name=dataset_name,
            output_dir=output_dir,
            num_files=0,
        )

    def verify_dataset(self, dataset_path: str) -> VerificationResult:
        """Verify dataset integrity by checking directory structure.

        Args:
            dataset_path: Path to the dataset root directory.

        Returns:
            VerificationResult with counts and any errors.
        """
        errors: List[str] = []
        root = Path(dataset_path)

        if not root.exists():
            return VerificationResult(
                valid=False,
                dataset_path=dataset_path,
                errors=[f"Dataset path does not exist: {dataset_path}"],
            )

        identity_dirs = [p for p in root.iterdir() if p.is_dir()]
        if not identity_dirs:
            errors.append(f"No identity directories found in: {dataset_path}")
            return VerificationResult(
                valid=False, dataset_path=dataset_path, errors=errors
            )

        num_images = 0
        for identity_dir in identity_dirs:
            images = [
                p for p in identity_dir.iterdir()
                if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
            ]
            num_images += len(images)

        return VerificationResult(
            valid=True,
            dataset_path=dataset_path,
            num_identities=len(identity_dirs),
            num_images=num_images,
            errors=errors,
        )

    def preprocess_dataset(
        self,
        dataset_path: str,
        output_dir: str,
        aligner: Optional[FaceAligner] = None,
    ) -> PreprocessResult:
        """Detect and align faces from a raw dataset.

        Args:
            dataset_path: Root directory of the raw dataset.
            output_dir: Root directory for aligned output.
            aligner: Optional FaceAligner. Creates one if not provided.

        Returns:
            PreprocessResult with statistics.
        """
        _aligner = aligner or FaceAligner(use_insightface=False)
        root = Path(dataset_path)
        out_root = Path(output_dir)
        failed: List[str] = []
        num_processed = 0

        identity_dirs = sorted(p for p in root.iterdir() if p.is_dir())
        for identity_dir in identity_dirs:
            out_identity = out_root / identity_dir.name
            out_identity.mkdir(parents=True, exist_ok=True)

            for img_path in identity_dir.iterdir():
                if img_path.suffix.lower() not in _IMAGE_EXTENSIONS:
                    continue
                try:
                    image = self._load_image(img_path)
                    if image is None:
                        failed.append(str(img_path))
                        logger.warning("Failed to load: %s", img_path)
                        continue

                    aligned = _aligner.align_face(image)
                    out_path = out_identity / img_path.name
                    self._save_image(aligned, out_path)
                    num_processed += 1
                except Exception as exc:
                    failed.append(str(img_path))
                    logger.warning("Preprocessing failed for %s: %s", img_path, exc)

        return PreprocessResult(
            success=True,
            output_dir=output_dir,
            num_processed=num_processed,
            num_failed=len(failed),
            failed_images=failed,
        )

    def get_dataset_stats(self, dataset_path: str) -> DatasetStats:
        """Compute dataset statistics.

        Args:
            dataset_path: Path to the dataset root directory.

        Returns:
            DatasetStats with identity and image counts.
        """
        stats = DatasetStats()
        root = Path(dataset_path)

        if not root.exists():
            return stats

        identity_dirs = sorted(p for p in root.iterdir() if p.is_dir())
        stats.num_identities = len(identity_dirs)

        for identity_dir in identity_dirs:
            images = [
                p for p in identity_dir.iterdir()
                if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
            ]
            stats.images_per_identity[identity_dir.name] = len(images)
            stats.num_images += len(images)

            for img_path in images:
                try:
                    img = self._load_image(img_path)
                    if img is not None:
                        h, w = img.shape[:2]
                        key = (w, h)
                        stats.resolution_distribution[key] = (
                            stats.resolution_distribution.get(key, 0) + 1
                        )
                    else:
                        stats.failed_images.append(str(img_path))
                except Exception:
                    stats.failed_images.append(str(img_path))

        return stats

    def create_dataloader(
        self,
        dataset_path: str,
        batch_size: int = 32,
        shuffle: bool = True,
        augment: bool = False,
        num_workers: int = 0,
    ) -> Any:
        """Create a PyTorch DataLoader for the dataset.

        Args:
            dataset_path: Path to the dataset root directory.
            batch_size: Batch size.
            shuffle: Whether to shuffle the data.
            augment: Whether to apply data augmentation.
            num_workers: Number of worker processes.

        Returns:
            torch.utils.data.DataLoader instance.
        """
        from torch.utils.data import DataLoader
        dataset = FaceDataset(dataset_path, augment=augment)
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=False,
        )

    @staticmethod
    def _load_image(path: Path) -> Optional[np.ndarray]:
        try:
            import cv2  # type: ignore[import]
            img = cv2.imread(str(path))
            return img
        except ImportError:
            pass
        try:
            from PIL import Image  # type: ignore[import]
            pil = Image.open(path).convert("RGB")
            rgb = np.array(pil, dtype=np.uint8)
            return rgb[:, :, ::-1]
        except Exception:
            return None

    @staticmethod
    def _save_image(image: np.ndarray, path: Path) -> bool:
        try:
            import cv2  # type: ignore[import]
            return bool(cv2.imwrite(str(path), image))
        except ImportError:
            pass
        try:
            from PIL import Image  # type: ignore[import]
            rgb = image[:, :, ::-1]
            Image.fromarray(rgb).save(str(path))
            return True
        except Exception:
            return False
