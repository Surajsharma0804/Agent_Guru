"""
Example script demonstrating ArcFace model training.

This script shows how to:
1. Configure training parameters
2. Train a custom ArcFace model
3. Load and use the trained model

Requirements: 1.1, 1.5, 1.6, 28.1, 28.5
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guru_vision.training.train import (
    train_arcface_model,
    load_trained_model,
    TrainingConfig
)


def example_basic_training():
    """
    Example 1: Basic training with default configuration.
    """
    print("=" * 80)
    print("Example 1: Basic Training with Default Configuration")
    print("=" * 80)
    
    # Train with default configuration
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset"
    )
    
    print(f"\nModel saved to: {model_path}")


def example_custom_training():
    """
    Example 2: Training with custom configuration.
    """
    print("=" * 80)
    print("Example 2: Training with Custom Configuration")
    print("=" * 80)
    
    # Create custom configuration
    config = TrainingConfig(
        batch_size=64,           # Larger batch size
        learning_rate=0.05,      # Lower learning rate
        num_epochs=30,           # More epochs
        use_gpu=True,            # Enable GPU
        num_workers=4,           # Parallel data loading
        validation_split=0.15,   # 15% validation
        save_interval=10,        # Save every 10 epochs
        lr_schedule="cosine"     # Cosine annealing
    )
    
    # Train model
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset",
        config=config
    )
    
    print(f"\nModel saved to: {model_path}")


def example_cpu_training():
    """
    Example 3: CPU-only training for systems without GPU.
    """
    print("=" * 80)
    print("Example 3: CPU-Only Training")
    print("=" * 80)
    
    # Configure for CPU training
    config = TrainingConfig(
        batch_size=16,      # Smaller batch for CPU
        num_epochs=10,      # Fewer epochs for testing
        use_gpu=False,      # Disable GPU
        num_workers=2       # Fewer workers for CPU
    )
    
    # Train model
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset",
        config=config
    )
    
    print(f"\nModel saved to: {model_path}")


def example_load_model():
    """
    Example 4: Loading a trained model for inference.
    """
    print("=" * 80)
    print("Example 4: Loading Trained Model")
    print("=" * 80)
    
    # Load trained model
    model = load_trained_model(
        model_path="guru_face/model/guru_face_model.pth",
        device="cpu"  # or "cuda"
    )
    
    print(f"Model loaded successfully!")
    print(f"Model type: {type(model)}")
    print(f"Model device: {next(model.parameters()).device}")
    
    # Model is ready for inference
    model.eval()
    print("Model is in evaluation mode and ready for inference")


def example_training_with_monitoring():
    """
    Example 5: Training with detailed monitoring and logging.
    """
    print("=" * 80)
    print("Example 5: Training with Detailed Monitoring")
    print("=" * 80)
    
    # Setup detailed logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('training.log'),
            logging.StreamHandler()
        ]
    )
    
    # Create configuration
    config = TrainingConfig(
        batch_size=32,
        num_epochs=20,
        learning_rate=0.1,
        use_gpu=True,
        save_interval=5,
        output_dir="guru_face/model",
        checkpoint_dir="guru_face/checkpoints"
    )
    
    # Train model with logging
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset",
        config=config
    )
    
    print(f"\nTraining complete!")
    print(f"Model saved to: {model_path}")
    print(f"Training log saved to: training.log")
    print(f"Checkpoints saved to: {config.checkpoint_dir}")


def example_fine_tuning():
    """
    Example 6: Fine-tuning with custom ArcFace parameters.
    """
    print("=" * 80)
    print("Example 6: Fine-Tuning with Custom ArcFace Parameters")
    print("=" * 80)
    
    # Configure ArcFace loss parameters
    config = TrainingConfig(
        batch_size=32,
        num_epochs=20,
        learning_rate=0.1,
        
        # Custom ArcFace parameters
        arcface_scale=32.0,    # Lower scale for easier optimization
        arcface_margin=0.3,    # Smaller margin for less strict separation
        
        # Optimization
        momentum=0.95,         # Higher momentum
        weight_decay=1e-4,     # Lower weight decay
        lr_schedule="step"     # Step decay instead of cosine
    )
    
    # Train model
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset",
        config=config
    )
    
    print(f"\nModel saved to: {model_path}")


def example_small_dataset_training():
    """
    Example 7: Training on a small dataset with adjusted parameters.
    """
    print("=" * 80)
    print("Example 7: Training on Small Dataset")
    print("=" * 80)
    
    # Adjust parameters for small dataset
    config = TrainingConfig(
        batch_size=8,           # Smaller batch size
        num_epochs=50,          # More epochs to compensate
        learning_rate=0.01,     # Lower learning rate
        validation_split=0.2,   # Larger validation split
        weight_decay=1e-3,      # Higher regularization
        save_interval=10
    )
    
    # Train model
    model_path = train_arcface_model(
        aligned_dataset_dir="aligned_dataset",
        config=config
    )
    
    print(f"\nModel saved to: {model_path}")
    print("\nNote: Small datasets may result in lower accuracy.")
    print("Recommended: 100-300 images per identity for best results.")


def main():
    """
    Main function to run examples.
    """
    print("\n" + "=" * 80)
    print("ArcFace Model Training Examples")
    print("=" * 80 + "\n")
    
    print("Available examples:")
    print("1. Basic training with default configuration")
    print("2. Training with custom configuration")
    print("3. CPU-only training")
    print("4. Loading a trained model")
    print("5. Training with detailed monitoring")
    print("6. Fine-tuning with custom ArcFace parameters")
    print("7. Training on small dataset")
    print()
    
    # Note: Uncomment the example you want to run
    
    # Example 1: Basic training
    # example_basic_training()
    
    # Example 2: Custom configuration
    # example_custom_training()
    
    # Example 3: CPU training
    # example_cpu_training()
    
    # Example 4: Load model
    # example_load_model()
    
    # Example 5: Detailed monitoring
    # example_training_with_monitoring()
    
    # Example 6: Fine-tuning
    # example_fine_tuning()
    
    # Example 7: Small dataset
    # example_small_dataset_training()
    
    print("\nTo run an example, uncomment the corresponding function call in main().")
    print("\nPrerequisites:")
    print("1. Prepare aligned dataset in 'aligned_dataset/' directory")
    print("2. Dataset structure: aligned_dataset/{IdentityName}/*.jpg")
    print("3. Minimum 50 images per identity (recommended: 100-300)")
    print("4. Images should be aligned and cropped to 112x112 pixels")
    print("\nUse the preprocessing module to prepare your dataset:")
    print("  python -m guru_vision.training.preprocess --dataset dataset --output aligned_dataset")


if __name__ == "__main__":
    main()
