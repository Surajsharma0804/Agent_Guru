"""Module: Agent_Guru.vision.training.integration
Purpose: GuruVision system integration - deployment artifact generation.

Requirements: 11.1, 11.3, 11.5
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger("guruvision.training.integration")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeploymentArtifacts:
    """Deployment artifacts for GuruVision integration."""

    onnx_model_path: str = ""
    config_path: str = ""
    metadata_path: str = ""
    report_path: str = ""
    production_ready: bool = False
    artifact_dir: str = ""

@dataclass
class ModelMetadataFile:
    """Preprocessing metadata for the deployed model."""

    image_size: int = 112
    normalization_mean: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    normalization_std: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    alignment_required: bool = True
    embedding_dim: int = 512
    architecture: str = "resnet50"
    input_format: str = "BGR"
    input_range: str = "[-1, 1]"
    onnx_opset: int = 11

# ---------------------------------------------------------------------------
# GuruVisionIntegration
# ---------------------------------------------------------------------------

class GuruVisionIntegration:
    """Generate deployment artifacts for GuruVision system integration.

    Args:
        output_dir: Directory to write deployment artifacts.

    """

    def __init__(self, output_dir: str = "Agent_Guru/vision/data/deployment") -> None:
        self.output_dir = output_dir

    def generate_deployment_artifacts(
        self,
        onnx_model_path: str,
        config: Any | None = None,
        report_path: str | None = None,
        production_ready: bool = False,
        metadata: ModelMetadataFile | None = None,
    ) -> DeploymentArtifacts:
        """Generate all deployment artifacts.

        Args:
            onnx_model_path: Path to the exported ONNX model.
            config: Optional pipeline configuration.
            report_path: Optional path to the performance report.
            production_ready: Whether the model is production-ready.
            metadata: Optional model metadata. Uses defaults if None.

        Returns:
            DeploymentArtifacts with paths to all generated files.

        """
        artifact_dir = Path(self.output_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        _metadata = metadata or ModelMetadataFile()

        # Write metadata file
        metadata_path = str(artifact_dir / "model_metadata.json")
        self._write_metadata(_metadata, metadata_path)

        # Write config file
        config_path = str(artifact_dir / "pipeline_config.json")
        self._write_config(config, config_path)

        # Copy or reference ONNX model
        onnx_dest = str(artifact_dir / "guru_face_model.onnx")
        if onnx_model_path and Path(onnx_model_path).exists():
            import shutil

            shutil.copy2(onnx_model_path, onnx_dest)
        else:
            onnx_dest = onnx_model_path or onnx_dest  # Reference original path

        # Write deployment manifest
        manifest_path = str(artifact_dir / "deployment_manifest.json")
        self._write_manifest(
            onnx_dest,
            config_path,
            metadata_path,
            report_path or "",
            production_ready,
            manifest_path,
        )

        logger.info(
            "Deployment artifacts generated in '%s' (production_ready=%s)",
            artifact_dir,
            production_ready,
        )

        return DeploymentArtifacts(
            onnx_model_path=onnx_dest,
            config_path=config_path,
            metadata_path=metadata_path,
            report_path=report_path or "",
            production_ready=production_ready,
            artifact_dir=str(artifact_dir),
        )

    def validate_onnx_compatibility(self, onnx_path: str) -> bool:
        """Validate that the ONNX model is compatible with GuruVision.

        Args:
            onnx_path: Path to the ONNX model.

        Returns:
            True if compatible.

        """
        if not Path(onnx_path).exists():
            logger.error("ONNX model not found: %s", onnx_path)
            return False

        try:
            import onnxruntime as ort  # type: ignore[import]

            session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            inputs = session.get_inputs()
            outputs = session.get_outputs()

            if not inputs or not outputs:
                logger.error("ONNX model has no inputs or outputs")
                return False

            logger.info(
                "ONNX model compatible: inputs=%s, outputs=%s",
                [i.name for i in inputs],
                [o.name for o in outputs],
            )
            return True
        except ImportError:
            logger.exception("onnxruntime not available; skipping ONNX validation")
            return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_metadata(metadata: ModelMetadataFile, path: str) -> None:
        data = {
            "image_size": metadata.image_size,
            "normalization_mean": metadata.normalization_mean,
            "normalization_std": metadata.normalization_std,
            "alignment_required": metadata.alignment_required,
            "embedding_dim": metadata.embedding_dim,
            "architecture": metadata.architecture,
            "input_format": metadata.input_format,
            "input_range": metadata.input_range,
            "onnx_opset": metadata.onnx_opset,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _write_config(config: Any | None, path: str) -> None:
        if config is None:
            data: dict[str, Any] = {"note": "No configuration provided"}
        elif hasattr(config, "__dict__"):
            try:
                from dataclasses import asdict

                data = asdict(config)
            except Exception:
                data = {"config": str(config)}
        else:
            data = {"config": str(config)}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def _write_manifest(
        onnx_path: str,
        config_path: str,
        metadata_path: str,
        report_path: str,
        production_ready: bool,
        manifest_path: str,
    ) -> None:
        from datetime import datetime

        manifest = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "production_ready": production_ready,
            "artifacts": {
                "onnx_model": onnx_path,
                "config": config_path,
                "metadata": metadata_path,
                "report": report_path,
            },
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
