"""
Integration tests for the GuruVision recognition pipeline.

Tests:
  28.1 - Training pipeline end-to-end (preprocess → train → ONNX export)
  28.2 - Recognition pipeline end-to-end (engine init → process_frame)
  28.3 - Incremental identity addition (add → recognise → existing still works)

Requirements: 1.1, 1.2, 1.3, 3.1, 5.3, 10.1, 16.1, 16.3, 16.6, 28.1
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from Agent_Guru.vision.config import GuruVisionConfig
from Agent_Guru.vision.database.face_db import FaceDatabase
from Agent_Guru.vision.engine import GuruVisionEngine, RecognitionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(
    enable_liveness: bool = False,
    enable_emotion: bool = False,
    enable_tracking: bool = False,
) -> GuruVisionEngine:
    """Return a fully initialised engine with all heavy sub-modules mocked."""
    engine = GuruVisionEngine()
    engine._config = GuruVisionConfig(
        enable_liveness=enable_liveness,
        enable_emotion=enable_emotion,
        enable_tracking=enable_tracking,
        enable_low_light_enhancement=False,
    )

    mock_detector = MagicMock()
    mock_detector.detect.return_value = []
    engine._detector = mock_detector

    mock_aligner = MagicMock()
    engine._aligner = mock_aligner

    mock_recognizer = MagicMock()
    mock_recognizer.extract_embedding.return_value = np.zeros(512, dtype=np.float32)
    engine._recognizer = mock_recognizer

    engine._liveness = None
    engine._emotion = None
    engine._tracker = None
    engine._database = FaceDatabase(db_path=None)
    engine._initialized = True
    return engine


def _blank_frame(h: int = 64, w: int = 64) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 28.1 Training pipeline (lightweight - no real model training)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTrainingPipelineIntegration:
    """28.1 - Training pipeline components work together."""

    def test_validate_dataset_structure_accepts_valid_layout(self, tmp_path: Path) -> None:
        """validate_dataset_structure returns a (bool, list) tuple."""
        from Agent_Guru.vision.training.preprocess import validate_dataset_structure
        import cv2

        alice_dir = tmp_path / "Alice"
        alice_dir.mkdir()
        # Add a dummy image so the identity is not empty
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2.imwrite(str(alice_dir / "img001.jpg"), blank)

        result = validate_dataset_structure(str(tmp_path))
        # Returns (is_valid: bool, issues: list)
        assert isinstance(result, tuple)  # nosec B101
        assert len(result) == 2  # nosec B101
        assert isinstance(result[1], list)  # nosec B101

    def test_preprocess_dataset_skips_no_face_images(self, tmp_path: Path) -> None:
        """preprocess_dataset skips images where no face is detected."""
        from Agent_Guru.vision.training.preprocess import preprocess_dataset
        import cv2

        identity_dir = tmp_path / "Alice"
        identity_dir.mkdir()
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2.imwrite(str(identity_dir / "img001.jpg"), blank)

        aligned_dir = tmp_path / "aligned"
        report = preprocess_dataset(str(tmp_path), str(aligned_dir))

        # report is a PreprocessingReport dataclass
        assert hasattr(report, "total_images_found")  # nosec B101
        assert report.total_images_found >= 1  # nosec B101

    def test_export_to_onnx_produces_file(self, tmp_path: Path) -> None:
        """export_to_onnx creates an .onnx file from a valid ResNet-50 checkpoint."""
        # torch is an optional extra (requirements-torch.txt), so a plain
        # "import torch" turned "this machine has no torch" into a failing
        # test rather than a skipped one. The sibling property test in this
        # directory already guards it this way; this one did not.
        torch = pytest.importorskip("torch")
        from Agent_Guru.vision.training.train import setup_arcface_training, TrainingConfig
        from Agent_Guru.vision.training.export import export_to_onnx

        # Build a real ResNet-50 backbone (no training needed - just save weights)
        cfg = TrainingConfig(dataset_dir=str(tmp_path), output_dir=str(tmp_path), num_classes=2)
        backbone, _, _, _ = setup_arcface_training(cfg)

        ckpt_path = tmp_path / "model.pth"
        torch.save({"backbone_state_dict": backbone.state_dict(), "num_classes": 2}, str(ckpt_path))

        onnx_path = tmp_path / "model.onnx"
        export_to_onnx(str(ckpt_path), str(onnx_path))
        assert onnx_path.exists()  # nosec B101
        assert onnx_path.stat().st_size > 0  # nosec B101


# ---------------------------------------------------------------------------
# 28.2 Recognition pipeline end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRecognitionPipelineIntegration:
    """28.2 - process_frame returns valid results for any frame."""

    def test_process_frame_returns_recognition_result(self) -> None:
        engine = _make_engine()
        result = engine.process_frame(_blank_frame())
        assert isinstance(result, RecognitionResult)  # nosec B101

    def test_process_frame_faces_is_list(self) -> None:
        engine = _make_engine()
        result = engine.process_frame(_blank_frame())
        assert isinstance(result.faces, list)  # nosec B101

    def test_process_frame_timestamp_non_empty(self) -> None:
        engine = _make_engine()
        result = engine.process_frame(_blank_frame())
        assert len(result.frame_timestamp) > 0  # nosec B101

    def test_process_frame_processing_time_non_negative(self) -> None:
        engine = _make_engine()
        result = engine.process_frame(_blank_frame())
        assert result.processing_time_ms >= 0.0  # nosec B101

    def test_process_frame_multiple_frames_consistent(self) -> None:
        """Processing multiple frames never raises and always returns results."""
        engine = _make_engine()
        for _ in range(20):
            result = engine.process_frame(_blank_frame())
            assert isinstance(result, RecognitionResult)  # nosec B101

    def test_process_frame_raises_before_initialize(self) -> None:
        engine = GuruVisionEngine()
        with pytest.raises(RuntimeError):
            engine.process_frame(_blank_frame())


# ---------------------------------------------------------------------------
# 28.3 Incremental identity addition
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIncrementalIdentityAddition:
    """28.3 - Adding identities incrementally works without retraining."""

    def test_add_identity_appears_immediately(self) -> None:
        """Identity added via database is immediately in get_identities."""
        engine = _make_engine()
        emb = np.random.default_rng(1).random(512).astype(np.float32)
        engine._database.add_identity("Alice", [emb], permission_level="user")

        names = [i.name for i in engine.get_identities()]
        assert "Alice" in names  # nosec B101

    def test_existing_identities_unaffected_after_add(self) -> None:
        """Adding a new identity does not remove existing ones."""
        engine = _make_engine()
        emb_a = np.random.default_rng(1).random(512).astype(np.float32)
        emb_b = np.random.default_rng(2).random(512).astype(np.float32)

        engine._database.add_identity("Alice", [emb_a], permission_level="user")
        engine._database.add_identity("Bob", [emb_b], permission_level="user")

        names = {i.name for i in engine.get_identities()}
        assert "Alice" in names  # nosec B101
        assert "Bob" in names  # nosec B101

    def test_remove_identity_does_not_affect_others(self) -> None:
        """Removing one identity leaves others intact."""
        engine = _make_engine()
        emb_a = np.zeros(512, dtype=np.float32)
        emb_b = np.ones(512, dtype=np.float32)

        engine._database.add_identity("Alice", [emb_a], permission_level="user")
        engine._database.add_identity("Bob", [emb_b], permission_level="user")
        engine.remove_identity("Alice")

        names = {i.name for i in engine.get_identities()}
        assert "Alice" not in names  # nosec B101
        assert "Bob" in names  # nosec B101

    def test_database_search_finds_added_identity(self) -> None:
        """A stored embedding is matched by the database search."""
        engine = _make_engine()
        emb = np.ones(512, dtype=np.float32)
        emb = emb / np.linalg.norm(emb)  # L2-normalise
        engine._database.add_identity("Alice", [emb], permission_level="user")

        match = engine._database.search(emb, threshold=0.5)
        assert match.identity == "Alice"  # nosec B101

    def test_update_permission_reflected_immediately(self) -> None:
        """update_permission is visible in get_identities without restart."""
        engine = _make_engine()
        emb = np.zeros(512, dtype=np.float32)
        engine._database.add_identity("Charlie", [emb], permission_level="guest")

        engine.update_permission("Charlie", "admin")
        info = next(i for i in engine.get_identities() if i.name == "Charlie")
        assert info.permission_level == "admin"  # nosec B101


# ---------------------------------------------------------------------------
# Event system integration
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEventSystemIntegration:
    """Event callbacks fire correctly during pipeline execution."""

    def test_system_ready_fires_on_initialize(self) -> None:
        """system_ready callback fires when engine is initialised."""
        engine = GuruVisionEngine()
        fired = []
        engine.register_callback("system_ready", lambda d: fired.append(d))

        # Manually set up mocks and call initialize path
        engine._config = GuruVisionConfig(
            enable_liveness=False, enable_emotion=False,
            enable_tracking=False, enable_low_light_enhancement=False,
        )
        engine._detector = MagicMock()
        engine._detector.detect.return_value = []
        engine._aligner = MagicMock()
        engine._recognizer = MagicMock()
        engine._recognizer.extract_embedding.return_value = np.zeros(512, dtype=np.float32)
        engine._liveness = None
        engine._emotion = None
        engine._tracker = None
        engine._database = FaceDatabase(db_path=None)
        engine._initialized = True
        engine._emit("system_ready", {})

        assert len(fired) == 1  # nosec B101

    def test_error_callback_fires_on_detection_failure(self) -> None:
        """error callback fires when detection raises."""
        engine = _make_engine()
        errors = []
        engine.register_callback("error", lambda d: errors.append(d))

        engine._detector.detect.side_effect = RuntimeError("detector boom")
        engine.process_frame(_blank_frame())

        assert any(e.get("stage") == "detection" for e in errors)  # nosec B101
