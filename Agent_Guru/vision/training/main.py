"""Module: Agent_Guru.vision.training.main
Purpose: CLI entry point for the GuruVision training evaluation pipeline.

Requirements: 12.1
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config_manager import Config

logger = logging.getLogger("guruvision.training.main")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_config(config_path: str, output_dir: str) -> Config:
    from .config_manager import ConfigManager

    manager = ConfigManager()
    config = manager.load_config(config_path)
    result = manager.validate_config(config)
    if not result.valid:
        logger.error("Invalid configuration: %s", result.errors)
        sys.exit(1)

    if output_dir:
        config.reporting.output_dir = output_dir
        config.training.output_dir = output_dir

    return config


def cmd_train(args: argparse.Namespace) -> None:
    """Run training stage only."""
    config = _load_config(args.config, args.output_dir)
    from .pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    result = orchestrator.run_training_stage()
    if result:
        pass
    else:
        pass


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Run evaluation stage only."""
    config = _load_config(args.config, args.output_dir)
    from .pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    model_path = (
        args.model_path or config.training.output_dir + "/" + config.training.checkpoint_name
    )
    results = orchestrator.run_evaluation_stage(model_path)
    for _r in results:
        pass


def cmd_improve(args: argparse.Namespace) -> None:
    """Run improvement loop."""
    config = _load_config(args.config, args.output_dir)
    from .pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    orchestrator.run_improvement_loop(max_iterations=args.max_iterations)


def cmd_stress_test(args: argparse.Namespace) -> None:
    """Run stress testing stage."""
    config = _load_config(args.config, args.output_dir)
    from .pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    model_path = args.model_path or ""
    results = orchestrator.run_stress_testing_stage(model_path)
    for _r in results:
        pass


def cmd_full_pipeline(args: argparse.Namespace) -> None:
    """Run the full pipeline."""
    config = _load_config(args.config, args.output_dir)
    from .pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    result = orchestrator.run_full_pipeline()
    if result.report_path:
        pass


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="guruvision-pipeline",
        description="GuruVision Training Evaluation Pipeline",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common arguments
    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--config",
            required=True,
            help="Path to pipeline configuration file (YAML or JSON)",
        )
        p.add_argument(
            "--output-dir",
            default="",
            help="Override output directory",
        )

    # train
    p_train = subparsers.add_parser("train", help="Run training stage")
    _add_common(p_train)
    p_train.set_defaults(func=cmd_train)

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Run evaluation stage")
    _add_common(p_eval)
    p_eval.add_argument("--model-path", default="", help="Path to model checkpoint")
    p_eval.set_defaults(func=cmd_evaluate)

    # improve
    p_improve = subparsers.add_parser("improve", help="Run improvement loop")
    _add_common(p_improve)
    p_improve.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max improvement iterations",
    )
    p_improve.set_defaults(func=cmd_improve)

    # stress-test
    p_stress = subparsers.add_parser("stress-test", help="Run stress testing")
    _add_common(p_stress)
    p_stress.add_argument("--model-path", default="", help="Path to model checkpoint")
    p_stress.set_defaults(func=cmd_stress_test)

    # full-pipeline
    p_full = subparsers.add_parser("full-pipeline", help="Run full pipeline")
    _add_common(p_full)
    p_full.set_defaults(func=cmd_full_pipeline)

    return parser


def main(argv: list | None = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.log_level)
    args.func(args)


if __name__ == "__main__":
    main()
