"""
Module: Agent_Guru.vision.training.config_manager
Purpose: Load, validate, and manage pipeline configuration from YAML/JSON files.

Requirements: 1.1, 1.2, 12.1, 12.2, 12.4
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("guruvision.training.config_manager")

# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DatasetConfig:
    """Dataset configuration."""
    root_dir: str = "Agent_Guru/vision/data"
    training_name: str = "ms1m-arcface"
    training_path: str = "Agent_Guru/vision/data/training"
    benchmark_paths: dict[str, str] = field(default_factory=dict)


@dataclass
class TrainingConfig:
    """Training configuration."""
    backbone: str = "resnet50"
    embedding_size: int = 512
    batch_size: int = 32
    num_epochs: int = 20
    learning_rate: float = 0.1
    weight_decay: float = 5e-4
    momentum: float = 0.9
    arcface_margin: float = 0.5
    arcface_scale: float = 64.0
    distributed: bool = False
    num_gpus: int = 1
    checkpoint_interval: int = 5
    log_interval: int = 100
    output_dir: str = "Agent_Guru/vision/data/model"
    checkpoint_name: str = "guru_face_model.pth"
    seed: int = 42
    use_gpu: bool = True
    val_split: float = 0.1


@dataclass
class EvaluationConfig:
    """Evaluation configuration."""
    batch_size: int = 64
    use_onnx: bool = False
    targets: dict[str, float] = field(default_factory=lambda: {
        "lfw": 0.997,
        "cfp_fp": 0.98,
        "agedb_30": 0.97,
    })


@dataclass
class ExportConfig:
    """ONNX export configuration."""
    dynamic_batch: bool = True
    opset_version: int = 11
    optimize: bool = True
    output_path: str = "Agent_Guru/vision/data/model/guru_face_model.onnx"


@dataclass
class StressTestConfig:
    """Stress testing configuration."""
    enabled: bool = True
    conditions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportingConfig:
    """Reporting configuration."""
    output_dir: str = "Agent_Guru/vision/data/reports"
    formats: list[str] = field(default_factory=lambda: ["json", "html"])


@dataclass
class Config:
    """Complete pipeline configuration."""
    name: str = "guruvision-pipeline"
    version: str = "1.0.0"
    random_seed: int = 42
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    stress_testing: StressTestConfig = field(default_factory=StressTestConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """Load, validate, and provide access to pipeline configuration.

    Supports YAML and JSON configuration files with schema validation.

    Example:
        >>> manager = ConfigManager()
        >>> config = manager.load_config("config.yaml")
        >>> result = manager.validate_config(config)
        >>> print(result.valid)
    """

    SUPPORTED_BACKBONES = {"resnet50", "resnet100", "vit"}
    SUPPORTED_BENCHMARKS = {"lfw", "cfp_fp", "agedb_30", "ijb_c"}
    SUPPORTED_FORMATS = {"pdf", "html", "json"}

    def __init__(self) -> None:
        self._config: Optional[Config] = None

    def load_config(self, config_path: str) -> Config:
        """Load configuration from YAML or JSON file.

        Args:
            config_path: Path to the configuration file (.yaml, .yml, or .json).

        Returns:
            Loaded Config object.

        Raises:
            FileNotFoundError: If config file does not exist.
            ValueError: If file format is unsupported or content is invalid.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            data = self._load_yaml(path)
        elif suffix == ".json":
            data = self._load_json(path)
        else:
            raise ValueError(f"Unsupported config format: {suffix}. Use .yaml or .json")

        config = self._dict_to_config(data)
        self._config = config
        logger.info("Loaded configuration from '%s'", config_path)
        return config

    def validate_config(self, config: Config) -> ValidationResult:
        """Validate configuration against schema.

        Args:
            config: Configuration to validate.

        Returns:
            ValidationResult with valid flag and any errors/warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Validate training config
        tc = config.training
        if tc.backbone not in self.SUPPORTED_BACKBONES:
            errors.append(
                f"Unsupported backbone '{tc.backbone}'. "
                f"Supported: {self.SUPPORTED_BACKBONES}"
            )
        if tc.embedding_size <= 0:
            errors.append(f"embedding_size must be > 0, got {tc.embedding_size}")
        if tc.batch_size <= 0:
            errors.append(f"batch_size must be > 0, got {tc.batch_size}")
        if tc.num_epochs <= 0:
            errors.append(f"num_epochs must be > 0, got {tc.num_epochs}")
        if tc.learning_rate <= 0:
            errors.append(f"learning_rate must be > 0, got {tc.learning_rate}")
        if not (0.0 < tc.arcface_margin < 1.0):
            errors.append(
                f"arcface_margin must be in (0, 1), got {tc.arcface_margin}"
            )
        if tc.arcface_scale <= 0:
            errors.append(f"arcface_scale must be > 0, got {tc.arcface_scale}")
        if not (0.0 < tc.val_split < 1.0):
            errors.append(f"val_split must be in (0, 1), got {tc.val_split}")

        # Validate evaluation config
        ec = config.evaluation
        if ec.batch_size <= 0:
            errors.append(f"evaluation.batch_size must be > 0, got {ec.batch_size}")
        for benchmark, target in ec.targets.items():
            if not (0.0 <= target <= 1.0):
                errors.append(
                    f"Target for '{benchmark}' must be in [0, 1], got {target}"
                )

        # Validate export config
        xc = config.export
        if xc.opset_version < 9:
            errors.append(f"opset_version must be >= 9, got {xc.opset_version}")

        # Validate reporting config
        rc = config.reporting
        for fmt in rc.formats:
            if fmt not in self.SUPPORTED_FORMATS:
                warnings.append(
                    f"Unsupported report format '{fmt}'. "
                    f"Supported: {self.SUPPORTED_FORMATS}"
                )

        valid = len(errors) == 0
        if not valid:
            logger.warning("Configuration validation failed: %s", errors)
        else:
            logger.info("Configuration validation passed")

        return ValidationResult(valid=valid, errors=errors, warnings=warnings)

    def get_training_config(self) -> TrainingConfig:
        """Return training configuration from loaded config."""
        if self._config is None:
            raise RuntimeError("No configuration loaded. Call load_config() first.")
        return self._config.training

    def get_evaluation_config(self) -> EvaluationConfig:
        """Return evaluation configuration from loaded config."""
        if self._config is None:
            raise RuntimeError("No configuration loaded. Call load_config() first.")
        return self._config.evaluation

    def get_dataset_config(self) -> DatasetConfig:
        """Return dataset configuration from loaded config."""
        if self._config is None:
            raise RuntimeError("No configuration loaded. Call load_config() first.")
        return self._config.dataset

    def save_config(self, config: Config, output_path: str) -> None:
        """Save configuration to JSON file.

        Args:
            config: Configuration to save.
            output_path: Destination file path.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._config_to_dict(config)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved configuration to '%s'", output_path)

    def create_default_config(self, scenario: str = "quick_eval") -> Config:
        """Create a default configuration for common scenarios.

        Args:
            scenario: One of 'quick_eval', 'full_training', 'stress_test'.

        Returns:
            Config with scenario-appropriate defaults.
        """
        config = Config()
        if scenario == "quick_eval":
            config.name = "quick-evaluation"
            config.training.num_epochs = 5
            config.training.batch_size = 16
            config.evaluation.use_onnx = False
        elif scenario == "full_training":
            config.name = "full-training"
            config.training.num_epochs = 50
            config.training.batch_size = 64
            config.training.backbone = "resnet100"
        elif scenario == "stress_test":
            config.name = "stress-testing"
            config.stress_testing.enabled = True
            config.stress_testing.conditions = [
                {"type": "low_light", "params": {"brightness_factor": 0.3}},
                {"type": "blur", "params": {"kernel_size": 5}},
                {"type": "distance", "params": {"scale_factor": 0.5}},
            ]
        return config

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Load YAML file, falling back to JSON-compatible loader."""
        try:
            import yaml  # type: ignore[import]
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Fallback: try to parse as JSON (subset of YAML)
            with open(path, encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _dict_to_config(data: dict[str, Any]) -> Config:
        """Convert a raw dict to a Config object."""
        config = Config()
        config.name = data.get("name", config.name)
        config.version = data.get("version", config.version)
        config.random_seed = data.get("random_seed", config.random_seed)

        if "dataset" in data:
            d = data["dataset"]
            config.dataset = DatasetConfig(
                root_dir=d.get("root_dir", config.dataset.root_dir),
                training_name=d.get("training_name", config.dataset.training_name),
                training_path=d.get("training_path", config.dataset.training_path),
                benchmark_paths=d.get("benchmark_paths", {}),
            )

        if "training" in data:
            t = data["training"]
            config.training = TrainingConfig(
                backbone=t.get("backbone", config.training.backbone),
                embedding_size=t.get("embedding_size", config.training.embedding_size),
                batch_size=t.get("batch_size", config.training.batch_size),
                num_epochs=t.get("num_epochs", config.training.num_epochs),
                learning_rate=t.get("learning_rate", config.training.learning_rate),
                weight_decay=t.get("weight_decay", config.training.weight_decay),
                momentum=t.get("momentum", config.training.momentum),
                arcface_margin=t.get("arcface_margin", config.training.arcface_margin),
                arcface_scale=t.get("arcface_scale", config.training.arcface_scale),
                distributed=t.get("distributed", config.training.distributed),
                num_gpus=t.get("num_gpus", config.training.num_gpus),
                checkpoint_interval=t.get("checkpoint_interval", config.training.checkpoint_interval),
                log_interval=t.get("log_interval", config.training.log_interval),
                output_dir=t.get("output_dir", config.training.output_dir),
                checkpoint_name=t.get("checkpoint_name", config.training.checkpoint_name),
                seed=t.get("seed", config.training.seed),
                use_gpu=t.get("use_gpu", config.training.use_gpu),
                val_split=t.get("val_split", config.training.val_split),
            )

        if "evaluation" in data:
            e = data["evaluation"]
            config.evaluation = EvaluationConfig(
                batch_size=e.get("batch_size", config.evaluation.batch_size),
                use_onnx=e.get("use_onnx", config.evaluation.use_onnx),
                targets=e.get("targets", config.evaluation.targets),
            )

        if "export" in data:
            x = data["export"]
            config.export = ExportConfig(
                dynamic_batch=x.get("dynamic_batch", config.export.dynamic_batch),
                opset_version=x.get("opset_version", config.export.opset_version),
                optimize=x.get("optimize", config.export.optimize),
                output_path=x.get("output_path", config.export.output_path),
            )

        if "stress_testing" in data:
            s = data["stress_testing"]
            config.stress_testing = StressTestConfig(
                enabled=s.get("enabled", config.stress_testing.enabled),
                conditions=s.get("conditions", []),
            )

        if "reporting" in data:
            r = data["reporting"]
            config.reporting = ReportingConfig(
                output_dir=r.get("output_dir", config.reporting.output_dir),
                formats=r.get("formats", config.reporting.formats),
            )

        return config

    @staticmethod
    def _config_to_dict(config: Config) -> dict[str, Any]:
        """Convert Config to a JSON-serializable dict."""
        return {
            "name": config.name,
            "version": config.version,
            "random_seed": config.random_seed,
            "dataset": asdict(config.dataset),
            "training": asdict(config.training),
            "evaluation": {
                "batch_size": config.evaluation.batch_size,
                "use_onnx": config.evaluation.use_onnx,
                "targets": config.evaluation.targets,
            },
            "export": asdict(config.export),
            "stress_testing": {
                "enabled": config.stress_testing.enabled,
                "conditions": config.stress_testing.conditions,
            },
            "reporting": asdict(config.reporting),
        }


def verify_gpu() -> dict[str, Any]:
    """Verify GPU availability and CUDA compatibility.

    Returns:
        Dict with keys: available (bool), device_count (int),
        device_names (list[str]), cuda_version (str | None).
    """
    result: dict[str, Any] = {
        "available": False,
        "device_count": 0,
        "device_names": [],
        "cuda_version": None,
    }
    try:
        import torch
        result["available"] = torch.cuda.is_available()
        result["device_count"] = torch.cuda.device_count()
        result["cuda_version"] = torch.version.cuda
        result["device_names"] = [
            torch.cuda.get_device_name(i)
            for i in range(result["device_count"])
        ]
        if result["available"]:
            logger.info(
                "GPU available: %d device(s) — %s (CUDA %s)",
                result["device_count"],
                result["device_names"],
                result["cuda_version"],
            )
        else:
            logger.warning("No GPU available. Training will use CPU.")
    except ImportError:
        logger.warning("PyTorch not installed; cannot verify GPU.")
    return result
