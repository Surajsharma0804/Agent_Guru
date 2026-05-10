#!/usr/bin/env python3
r"""train.py — GuruVision ArcFace training entry-point.

Usage:
    python -m Agent_Guru.vision.train \\
        --dataset_dir  path/to/aligned_dataset \\
        --output_dir   path/to/output \\
        [--config_path path/to/config.yaml] \\
        [--epochs 20] \\
        [--batch_size 32] \\
        [--no_gpu]

The script executes three phases in sequence:
  1. Dataset validation & preprocessing report
  2. ArcFace model training (ResNet-50 backbone)
  3. ONNX export + equivalence validation

A JSON training report is written to output_dir/training_report.json.

Requirements: 1.1, 1.2, 1.3, 1.4, 28.1, 28.2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from Agent_Guru.training.seed_utils import set_deterministic_seeds
from Agent_Guru.utils.path_utils import safe_path
from Agent_Guru.vision.training.export import export_to_onnx, validate_onnx_equivalence
from Agent_Guru.vision.training.preprocess import (
    MIN_IMAGES_PER_IDENTITY,
    check_minimum_images,
    validate_dataset_structure,
)
from Agent_Guru.vision.training.train import TrainingConfig, train_arcface_model
from Agent_Guru.vision.utils.logging import setup_logging

BASE_DIR = Path(__file__).parent.resolve()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train GuruVision ArcFace face recognition model",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset_dir",
        required=True,
        help="Path to the aligned dataset root (dataset/{Identity}/*.jpg)",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory where checkpoints, ONNX model, and report are saved",
    )
    parser.add_argument(
        "--config_path",
        default=None,
        help="Optional path to a YAML/JSON config file (overrides CLI defaults)",
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=0.1)
    parser.add_argument("--embedding_dim", type=int, default=512)
    parser.add_argument(
        "--no_gpu",
        action="store_true",
        help="Disable GPU even if CUDA is available",
    )
    parser.add_argument(
        "--log_level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def _load_config_overrides(config_path: str, config: TrainingConfig) -> TrainingConfig:
    """Apply overrides from a YAML or JSON config file."""
    path = safe_path(BASE_DIR, config_path)
    if not path.exists():
        logging.getLogger("guruvision.train").warning(
            "Config file not found: %s — using defaults",
            config_path,
        )
        return config

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import]

            data = yaml.safe_load(text) or {}
        except ImportError:
            logging.getLogger("guruvision.train").warning(
                "PyYAML not installed — cannot load YAML config",
            )
            return config
    else:
        data = json.loads(text)

    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Set deterministic seeds for reproducibility (Req 2.24)
    set_deterministic_seeds(42)

    log_file = str(safe_path(BASE_DIR, os.path.join(args.output_dir, "training.log")))  # noqa: PTH118
    os.makedirs(args.output_dir, exist_ok=True)  # noqa: PTH103
    logger = setup_logging(log_level=args.log_level, log_file=log_file)
    logger.info("GuruVision training started")

    report: dict = {
        "dataset_dir": args.dataset_dir,
        "output_dir": args.output_dir,
        "phases": {},
        "success": False,
    }

    # ------------------------------------------------------------------
    # Phase 1: Dataset validation
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("Phase 1: Validating dataset structure …")

    is_valid, errors = validate_dataset_structure(args.dataset_dir)
    if not is_valid:
        for err in errors:
            logger.error("Dataset error: %s", err)
        report["phases"]["validation"] = {"success": False, "errors": errors}
        _write_report(report, args.output_dir)
        return 1

    counts = check_minimum_images(args.dataset_dir)
    under_minimum = {k: v for k, v in counts.items() if v < MIN_IMAGES_PER_IDENTITY}
    if under_minimum:
        for name, count in under_minimum.items():
            logger.warning(
                "Identity '%s' has %d images (< %d minimum)",
                name,
                count,
                MIN_IMAGES_PER_IDENTITY,
            )

    report["phases"]["validation"] = {
        "success": True,
        "num_identities": len(counts),
        "under_minimum": under_minimum,
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }
    logger.info("Dataset valid: %d identities found", len(counts))

    # ------------------------------------------------------------------
    # Phase 2: Training
    # ------------------------------------------------------------------
    t1 = time.perf_counter()
    logger.info("Phase 2: Training ArcFace model …")

    config = TrainingConfig(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        embedding_dim=args.embedding_dim,
        use_gpu=not args.no_gpu,
    )

    if args.config_path:
        config = _load_config_overrides(args.config_path, config)

    try:
        checkpoint_path = train_arcface_model(config)
    except ImportError as exc:
        logger.exception("PyTorch not available")
        report["phases"]["training"] = {"success": False, "error": str(exc)}
        _write_report(report, args.output_dir)
        return 1
        logger.exception("Training failed: %s", exc)
        report["phases"]["training"] = {"success": False, "error": str(exc)}
        _write_report(report, args.output_dir)
        return 1
    report["phases"]["training"] = {
        "success": True,
        "checkpoint_path": checkpoint_path,
        "elapsed_s": round(time.perf_counter() - t1, 2),
    }
    logger.info("Training complete. Checkpoint: %s", checkpoint_path)

    # ------------------------------------------------------------------
    # Phase 3: ONNX export + validation
    # ------------------------------------------------------------------
    t2 = time.perf_counter()
    logger.info("Phase 3: Exporting to ONNX …")

    onnx_path = str(safe_path(BASE_DIR, os.path.join(args.output_dir, "guru_face_model.onnx")))  # noqa: PTH118
    try:
        onnx_path = export_to_onnx(checkpoint_path, output_path=onnx_path)
        equivalence_ok = validate_onnx_equivalence(checkpoint_path, onnx_path)
    except ImportError as exc:
        logger.exception("ONNX export skipped (missing dependency)")
        report["phases"]["onnx_export"] = {"success": False, "error": str(exc)}
        logger.exception("ONNX export/validation failed: %s", exc)
        report["phases"]["onnx_export"] = {"success": False, "error": str(exc)}
        _write_report(report, args.output_dir)
        return 1
    else:
        report["phases"]["onnx_export"] = {
            "success": True,
            "onnx_path": onnx_path,
            "equivalence_validated": equivalence_ok,
            "elapsed_s": round(time.perf_counter() - t2, 2),
        }
        logger.info("ONNX model exported and validated: %s", onnx_path)

    report["success"] = True
    report["total_elapsed_s"] = round(time.perf_counter() - t0, 2)
    _write_report(report, args.output_dir)
    logger.info("Training pipeline complete in %.1fs", report["total_elapsed_s"])
    return 0


def _write_report(report: dict, output_dir: str) -> None:
    report_path = str(safe_path(BASE_DIR, os.path.join(output_dir, "training_report.json")))  # noqa: PTH118
    try:
        with open(report_path, "w", encoding="utf-8") as f:  # noqa: PTH123
            json.dump(report, f, indent=2)
        logging.getLogger("guruvision.train").info("Report written to %s", report_path)
    except Exception as exc:
        logging.getLogger("guruvision.train").exception("Failed to write report: %s", exc)
if __name__ == "__main__":
    sys.exit(main())
