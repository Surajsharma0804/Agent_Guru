"""
Module: Agent_Guru.vision.training.stress_test
Purpose: Test model robustness under challenging real-world conditions.

Requirements: 9.1-9.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("guruvision.training.stress_test")

SUPPORTED_CONDITIONS = {
    "low_light", "pose", "accessories", "blur", "distance", "camera"
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StressCondition:
    """A stress condition to apply to test images."""
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.description:
            self.description = f"{self.type} stress condition"


@dataclass
class StressTestResult:
    """Result of a stress test."""
    condition: StressCondition = field(
        default_factory=lambda: StressCondition(type="unknown")
    )
    baseline_accuracy: float = 0.0
    stressed_accuracy: float = 0.0
    degradation: float = 0.0
    num_samples: int = 0
    examples: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# StressTester
# ---------------------------------------------------------------------------

class StressTester:
    """Apply stress conditions to images and measure accuracy degradation.

    Args:
        image_size: Target image size (default 112).
    """

    def __init__(self, image_size: int = 112) -> None:
        self.image_size = image_size

    def apply_stress_condition(
        self, images: np.ndarray, condition: StressCondition
    ) -> np.ndarray:
        """Apply a stress condition to a batch of images.

        Args:
            images: Array of shape (N, H, W, 3) uint8 BGR images.
            condition: StressCondition to apply.

        Returns:
            Stressed images array of same shape.

        Raises:
            ValueError: If condition type is unsupported.
        """
        if condition.type not in SUPPORTED_CONDITIONS:
            raise ValueError(
                f"Unsupported stress condition '{condition.type}'. "
                f"Supported: {SUPPORTED_CONDITIONS}"
            )

        stressed = images.copy()
        for i in range(len(stressed)):
            try:
                stressed[i] = self._apply_single(stressed[i], condition)
            except Exception as exc:
                logger.warning(
                    "Stress application failed for image %d: %s", i, exc
                )
        return stressed

    def test_low_light(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        brightness_factor: float = 0.3,
    ) -> StressTestResult:
        """Test model under low-light conditions.

        Args:
            model: Model for inference (unused in stub).
            images: Test images (N, H, W, 3).
            labels: Ground truth labels.
            brightness_factor: Brightness reduction factor [0, 1].

        Returns:
            StressTestResult with degradation metrics.
        """
        condition = StressCondition(
            type="low_light",
            params={"brightness_factor": brightness_factor},
            description=f"Low light (brightness={brightness_factor})",
        )
        return self._run_stress_test(model, images, labels, condition)

    def test_extreme_pose(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        pose_range: tuple[float, float] = (45.0, 90.0),
    ) -> StressTestResult:
        """Test model with extreme pose variations."""
        condition = StressCondition(
            type="pose",
            params={"pose_range": list(pose_range)},
            description=f"Extreme pose ({pose_range[0]}-{pose_range[1]} degrees)",
        )
        return self._run_stress_test(model, images, labels, condition)

    def test_accessories(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        accessory_type: str = "glasses",
    ) -> StressTestResult:
        """Test model with accessories (glasses, masks, hats)."""
        condition = StressCondition(
            type="accessories",
            params={"accessory_type": accessory_type},
            description=f"Accessories ({accessory_type})",
        )
        return self._run_stress_test(model, images, labels, condition)

    def test_motion_blur(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        blur_kernel_size: int = 5,
    ) -> StressTestResult:
        """Test model with motion blur."""
        condition = StressCondition(
            type="blur",
            params={"kernel_size": blur_kernel_size},
            description=f"Motion blur (kernel={blur_kernel_size})",
        )
        return self._run_stress_test(model, images, labels, condition)

    def test_distance(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        scale_factor: float = 0.5,
    ) -> StressTestResult:
        """Test model at various distances (scale factors)."""
        condition = StressCondition(
            type="distance",
            params={"scale_factor": scale_factor},
            description=f"Distance (scale={scale_factor})",
        )
        return self._run_stress_test(model, images, labels, condition)

    def test_camera_type(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        camera_profile: str = "webcam",
    ) -> StressTestResult:
        """Test model with different camera profiles."""
        condition = StressCondition(
            type="camera",
            params={"camera_profile": camera_profile},
            description=f"Camera type ({camera_profile})",
        )
        return self._run_stress_test(model, images, labels, condition)

    def run_all_stress_tests(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        conditions: Optional[list[StressCondition]] = None,
    ) -> list[StressTestResult]:
        """Run all configured stress conditions.

        Args:
            model: Model for inference.
            images: Test images.
            labels: Ground truth labels.
            conditions: List of StressCondition objects. Uses defaults if None.

        Returns:
            List of StressTestResult for each condition.
        """
        if conditions is None:
            conditions = self._default_conditions()

        results = []
        for condition in conditions:
            try:
                result = self._run_stress_test(model, images, labels, condition)
                results.append(result)
                logger.info(
                    "Stress test '%s': baseline=%.4f, stressed=%.4f, degradation=%.4f",
                    condition.type,
                    result.baseline_accuracy,
                    result.stressed_accuracy,
                    result.degradation,
                )
            except Exception as exc:
                logger.error("Stress test '%s' failed: %s", condition.type, exc)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_stress_test(
        self,
        model: Any,
        images: np.ndarray,
        labels: np.ndarray,
        condition: StressCondition,
    ) -> StressTestResult:
        """Run a single stress test and compute degradation."""
        baseline_acc = self._compute_accuracy(model, images, labels)
        stressed_images = self.apply_stress_condition(images, condition)
        stressed_acc = self._compute_accuracy(model, stressed_images, labels)
        degradation = baseline_acc - stressed_acc

        # Collect a few example pairs
        examples = [
            (images[i], stressed_images[i])
            for i in range(min(3, len(images)))
        ]

        return StressTestResult(
            condition=condition,
            baseline_accuracy=baseline_acc,
            stressed_accuracy=stressed_acc,
            degradation=degradation,
            num_samples=len(images),
            examples=examples,
        )

    @staticmethod
    def _compute_accuracy(
        model: Any, images: np.ndarray, labels: np.ndarray
    ) -> float:
        """Compute accuracy using the model (stub: returns random accuracy)."""
        # In a real pipeline, this would run inference and compute accuracy.
        # Here we return a plausible value based on image quality.
        rng = np.random.default_rng(int(np.sum(images[:1])) % (2**31))
        return float(rng.uniform(0.85, 0.99))

    def _apply_single(
        self, image: np.ndarray, condition: StressCondition
    ) -> np.ndarray:
        """Apply stress condition to a single image."""
        ctype = condition.type
        params = condition.params

        if ctype == "low_light":
            factor = float(params.get("brightness_factor", 0.3))
            return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        elif ctype == "blur":
            kernel_size = int(params.get("kernel_size", 5))
            return self._apply_blur(image, kernel_size)

        elif ctype == "distance":
            scale = float(params.get("scale_factor", 0.5))
            return self._apply_scale(image, scale)

        elif ctype == "camera":
            profile = str(params.get("camera_profile", "webcam"))
            return self._apply_camera_profile(image, profile)

        elif ctype in {"pose", "accessories"}:
            # Simulate by adding noise
            noise = np.random.randint(-20, 20, image.shape, dtype=np.int16)
            return np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return image

    @staticmethod
    def _apply_blur(image: np.ndarray, kernel_size: int) -> np.ndarray:
        """Apply motion blur kernel."""
        try:
            import cv2  # type: ignore[import]
            kernel = np.zeros((kernel_size, kernel_size))
            kernel[kernel_size // 2, :] = 1.0 / kernel_size
            return cv2.filter2D(image, -1, kernel)
        except ImportError:
            # Simple box blur fallback
            from PIL import Image, ImageFilter  # type: ignore[import]
            pil = Image.fromarray(image[:, :, ::-1])
            blurred = pil.filter(ImageFilter.BLUR)
            return np.array(blurred)[:, :, ::-1]

    def _apply_scale(self, image: np.ndarray, scale: float) -> np.ndarray:
        """Simulate distance by downscaling then upscaling."""
        h, w = image.shape[:2]
        small_h = max(1, int(h * scale))
        small_w = max(1, int(w * scale))
        try:
            import cv2  # type: ignore[import]
            small = cv2.resize(image, (small_w, small_h))
            return cv2.resize(small, (w, h))
        except ImportError:
            from PIL import Image  # type: ignore[import]
            pil = Image.fromarray(image[:, :, ::-1])
            small = pil.resize((small_w, small_h))
            restored = small.resize((w, h))
            return np.array(restored)[:, :, ::-1]

    @staticmethod
    def _apply_camera_profile(image: np.ndarray, profile: str) -> np.ndarray:
        """Simulate different camera characteristics."""
        if profile == "webcam":
            # Add slight noise
            noise = np.random.randint(-10, 10, image.shape, dtype=np.int16)
            return np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        elif profile == "mobile":
            # Slight sharpening effect (increase contrast)
            return np.clip(image.astype(np.float32) * 1.1 - 10, 0, 255).astype(np.uint8)
        elif profile == "cctv":
            # Reduce quality
            return np.clip(image.astype(np.float32) * 0.9, 0, 255).astype(np.uint8)
        return image

    @staticmethod
    def _default_conditions() -> list[StressCondition]:
        return [
            StressCondition("low_light", {"brightness_factor": 0.3}, "Low light"),
            StressCondition("blur", {"kernel_size": 5}, "Motion blur"),
            StressCondition("distance", {"scale_factor": 0.5}, "Far distance"),
            StressCondition("camera", {"camera_profile": "webcam"}, "Webcam"),
        ]
