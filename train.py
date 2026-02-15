#!/usr/bin/env python3
"""
GuruVision Main Training Script

This script orchestrates the complete training pipeline for the GuruVision facial
recognition system. It executes preprocessing, training, and ONNX export in sequence,
generating a comprehensive training report.

Requirements: 1.1, 1.2, 1.3, 1.4, 28.1, 28.2

Usage:
    python train.py --dataset dataset/ --output guru_face/
    python train.py --dataset dataset/ --output guru_face/ --config config.yaml
    python train.py --dataset dataset/ --output guru_face/ --epochs 30 --batch-size 64
"""

import os
import sys
import argparse
import logging
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guru_vision.training.preprocess import (
    preprocess_dataset,
    validate_dataset_structure,
    check_minimum_images,
    PreprocessResult
)
from guru_vision.training.train import (
    train_arcface_model,
    TrainingConfig
)
from guru_vision.training.export import (
    export_to_onnx,
    validate_onnx_pytorch_equivalence
)


# Configure logging
def setup_logging(output_dir: str, log_level: str = "INFO") -> None:
    """
    Setup logging configuration for the training pipeline.
    
    Args:
        output_dir: Directory where log file will be saved
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_dir = os.path.join(output_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"training_{timestamp}.log")
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Setup file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info(f"Logging initialized. Log file: {log_file}")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="GuruVision Face Recognition Model Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic training with default settings
  python train.py --dataset dataset/ --output guru_face/
  
  # Training with custom hyperparameters
  python train.py --dataset dataset/ --output guru_face/ --epochs 30 --batch-size 64 --lr 0.05
  
  # Training with configuration file
  python train.py --dataset dataset/ --output guru_face/ --config training_config.yaml
  
  # CPU-only training
  python train.py --dataset dataset/ --output guru_face/ --no-gpu
  
  # Skip ONNX export
  python train.py --dataset dataset/ --output guru_face/ --skip-export
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to dataset directory (structure: dataset/{IdentityName}/*.jpg)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for models, logs, and reports"
    )
    
    # Optional configuration
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to training configuration file (YAML or JSON)"
    )
    
    # Training hyperparameters
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for training (default: 32)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        help="Number of training epochs (default: 20)"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.1,
        help="Learning rate (default: 0.1)"
    )
    parser.add_argument(
        "--backbone",
        type=str,
        default="r50",
        choices=["r50"],
        help="Backbone architecture (default: r50 for ResNet-50)"
    )
    
    # Hardware options
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU acceleration (use CPU only)"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of data loading workers (default: 4)"
    )
    
    # Pipeline control
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Skip preprocessing step (use existing aligned dataset)"
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip ONNX export step"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX-PyTorch equivalence validation"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)"
    )
    
    return parser.parse_args()


def load_config_file(config_path: str) -> Dict[str, Any]:
    """
    Load training configuration from YAML or JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    import yaml
    
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            config = yaml.safe_load(f)
        elif config_path.endswith('.json'):
            config = json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {config_path}")
    
    return config


def generate_training_report(
    output_dir: str,
    preprocess_result: Optional[PreprocessResult],
    training_time: float,
    model_path: str,
    onnx_path: Optional[str],
    validation_passed: Optional[bool],
    config: TrainingConfig
) -> str:
    """
    Generate comprehensive training report.
    
    Args:
        output_dir: Output directory for the report
        preprocess_result: Preprocessing statistics
        training_time: Total training time in seconds
        model_path: Path to saved PyTorch model
        onnx_path: Path to saved ONNX model (if exported)
        validation_passed: Whether ONNX validation passed (if performed)
        config: Training configuration used
        
    Returns:
        Path to generated report file
    """
    report_dir = os.path.join(output_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"training_report_{timestamp}.json")
    
    # Build report data
    report = {
        "timestamp": datetime.now().isoformat(),
        "training_configuration": {
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "num_epochs": config.num_epochs,
            "backbone": config.backbone,
            "embedding_size": config.embedding_size,
            "use_gpu": config.use_gpu,
            "arcface_scale": config.arcface_scale,
            "arcface_margin": config.arcface_margin
        },
        "preprocessing": None,
        "training": {
            "duration_seconds": training_time,
            "duration_formatted": f"{training_time // 3600:.0f}h {(training_time % 3600) // 60:.0f}m {training_time % 60:.0f}s",
            "model_path": model_path,
            "model_exists": os.path.exists(model_path)
        },
        "onnx_export": {
            "performed": onnx_path is not None,
            "onnx_path": onnx_path,
            "onnx_exists": os.path.exists(onnx_path) if onnx_path else False,
            "validation_performed": validation_passed is not None,
            "validation_passed": validation_passed
        }
    }
    
    # Add preprocessing statistics if available
    if preprocess_result:
        report["preprocessing"] = {
            "total_images": preprocess_result.total_images,
            "successful": preprocess_result.successful,
            "no_face": preprocess_result.no_face,
            "multiple_faces": preprocess_result.multiple_faces,
            "failed": preprocess_result.failed,
            "identities_processed": preprocess_result.identities_processed,
            "success_rate": f"{(preprocess_result.successful / preprocess_result.total_images * 100):.2f}%",
            "per_identity_statistics": preprocess_result.statistics
        }
    
    # Save report
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logging.info(f"Training report saved to: {report_path}")
    
    return report_path


def main():
    """
    Main training pipeline execution.
    
    This function orchestrates the complete training workflow:
    1. Parse command-line arguments
    2. Setup logging
    3. Validate dataset structure
    4. Preprocess dataset (detect, align, save faces)
    5. Train ArcFace model
    6. Export to ONNX format
    7. Validate ONNX model
    8. Generate training report
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 28.1, 28.2
    """
    # Parse arguments
    args = parse_arguments()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Setup logging
    setup_logging(args.output, args.log_level)
    
    logging.info("=" * 80)
    logging.info("GuruVision Face Recognition Training Pipeline")
    logging.info("=" * 80)
    logging.info(f"Dataset: {args.dataset}")
    logging.info(f"Output: {args.output}")
    logging.info(f"GPU Enabled: {not args.no_gpu}")
    logging.info("=" * 80)
    
    # Track overall timing
    pipeline_start_time = time.time()
    
    # Initialize variables for report
    preprocess_result = None
    model_path = None
    onnx_path = None
    validation_passed = None
    
    try:
        # ===================================================================
        # STEP 1: Validate Dataset Structure
        # ===================================================================
        logging.info("\n" + "=" * 80)
        logging.info("STEP 1: Validating Dataset Structure")
        logging.info("=" * 80)
        
        is_valid, errors = validate_dataset_structure(args.dataset)
        if not is_valid:
            logging.error("Dataset validation failed:")
            for error in errors:
                logging.error(f"  - {error}")
            sys.exit(1)
        
        logging.info("✓ Dataset structure is valid")
        
        # Check minimum images
        all_valid, identity_counts = check_minimum_images(args.dataset, minimum=50)
        logging.info(f"Found {len(identity_counts)} identities:")
        for identity, count in identity_counts.items():
            status = "✓" if count >= 50 else "⚠"
            logging.info(f"  {status} {identity}: {count} images")
        
        if not all_valid:
            logging.warning(
                "Some identities have fewer than 50 images. "
                "This may result in reduced recognition accuracy."
            )
        
        # ===================================================================
        # STEP 2: Preprocess Dataset
        # ===================================================================
        aligned_dataset_dir = os.path.join(args.output, "aligned_dataset")
        
        if args.skip_preprocess:
            logging.info("\n" + "=" * 80)
            logging.info("STEP 2: Preprocessing (SKIPPED)")
            logging.info("=" * 80)
            logging.info(f"Using existing aligned dataset: {aligned_dataset_dir}")
            
            if not os.path.exists(aligned_dataset_dir):
                logging.error(f"Aligned dataset not found: {aligned_dataset_dir}")
                logging.error("Cannot skip preprocessing without existing aligned dataset")
                sys.exit(1)
        else:
            logging.info("\n" + "=" * 80)
            logging.info("STEP 2: Preprocessing Dataset")
            logging.info("=" * 80)
            
            preprocess_start = time.time()
            preprocess_result = preprocess_dataset(
                dataset_dir=args.dataset,
                output_dir=aligned_dataset_dir,
                use_gpu=not args.no_gpu
            )
            preprocess_time = time.time() - preprocess_start
            
            logging.info(f"Preprocessing completed in {preprocess_time:.2f} seconds")
            
            if preprocess_result.successful == 0:
                logging.error("No faces were successfully preprocessed!")
                sys.exit(1)
        
        # ===================================================================
        # STEP 3: Train ArcFace Model
        # ===================================================================
        logging.info("\n" + "=" * 80)
        logging.info("STEP 3: Training ArcFace Model")
        logging.info("=" * 80)
        
        # Create training configuration
        model_output_dir = os.path.join(args.output, "model")
        checkpoint_dir = os.path.join(args.output, "checkpoints")
        
        config = TrainingConfig(
            batch_size=args.batch_size,
            learning_rate=args.lr,
            num_epochs=args.epochs,
            backbone=args.backbone,
            num_workers=args.num_workers,
            use_gpu=not args.no_gpu,
            output_dir=model_output_dir,
            checkpoint_dir=checkpoint_dir
        )
        
        # Load config file if provided
        if args.config:
            logging.info(f"Loading configuration from: {args.config}")
            config_dict = load_config_file(args.config)
            # Update config with file values
            for key, value in config_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # Train model
        training_start = time.time()
        model_path = train_arcface_model(aligned_dataset_dir, config)
        training_time = time.time() - training_start
        
        logging.info(f"Training completed in {training_time:.2f} seconds")
        logging.info(f"Model saved to: {model_path}")
        
        # ===================================================================
        # STEP 4: Export to ONNX
        # ===================================================================
        if args.skip_export:
            logging.info("\n" + "=" * 80)
            logging.info("STEP 4: ONNX Export (SKIPPED)")
            logging.info("=" * 80)
        else:
            logging.info("\n" + "=" * 80)
            logging.info("STEP 4: Exporting to ONNX Format")
            logging.info("=" * 80)
            
            onnx_path = os.path.join(model_output_dir, "guru_face_model.onnx")
            
            export_success = export_to_onnx(
                pytorch_model_path=model_path,
                output_path=onnx_path,
                verify=True
            )
            
            if not export_success:
                logging.error("ONNX export failed!")
                sys.exit(1)
            
            logging.info(f"ONNX model saved to: {onnx_path}")
            
            # ===================================================================
            # STEP 5: Validate ONNX-PyTorch Equivalence
            # ===================================================================
            if args.skip_validation:
                logging.info("\n" + "=" * 80)
                logging.info("STEP 5: ONNX Validation (SKIPPED)")
                logging.info("=" * 80)
            else:
                logging.info("\n" + "=" * 80)
                logging.info("STEP 5: Validating ONNX-PyTorch Equivalence")
                logging.info("=" * 80)
                
                validation_passed = validate_onnx_pytorch_equivalence(
                    pytorch_model_path=model_path,
                    onnx_model_path=onnx_path,
                    tolerance=0.001,
                    num_samples=10
                )
                
                if not validation_passed:
                    logging.error("ONNX validation failed!")
                    logging.error("Models do not produce equivalent embeddings")
                    sys.exit(1)
                
                logging.info("✓ ONNX validation passed!")
        
        # ===================================================================
        # STEP 6: Generate Training Report
        # ===================================================================
        logging.info("\n" + "=" * 80)
        logging.info("STEP 6: Generating Training Report")
        logging.info("=" * 80)
        
        pipeline_time = time.time() - pipeline_start_time
        
        report_path = generate_training_report(
            output_dir=args.output,
            preprocess_result=preprocess_result,
            training_time=training_time,
            model_path=model_path,
            onnx_path=onnx_path,
            validation_passed=validation_passed,
            config=config
        )
        
        # ===================================================================
        # Pipeline Complete
        # ===================================================================
        logging.info("\n" + "=" * 80)
        logging.info("TRAINING PIPELINE COMPLETE!")
        logging.info("=" * 80)
        logging.info(f"Total pipeline time: {pipeline_time:.2f} seconds")
        logging.info(f"PyTorch model: {model_path}")
        if onnx_path:
            logging.info(f"ONNX model: {onnx_path}")
        logging.info(f"Training report: {report_path}")
        logging.info("=" * 80)
        
        logging.info("\nNext steps:")
        logging.info("1. Review the training report for detailed statistics")
        logging.info("2. Test the model using the recognition engine")
        logging.info("3. Add identities incrementally without retraining")
        logging.info("\nFor usage examples, see: guru_vision/training/README.md")
        
        return 0
        
    except KeyboardInterrupt:
        logging.warning("\n\nTraining interrupted by user")
        return 130
        
    except Exception as e:
        logging.error(f"\n\nTraining pipeline failed with error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
