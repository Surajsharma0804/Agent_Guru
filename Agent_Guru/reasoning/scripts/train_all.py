"""
Master Training Script - Train Intent Classifier + NER Model

Runs both training scripts in sequence:
1. Intent Classifier (DeBERTa-v3-large) - 50 epochs with early stopping
2. NER Model - After intent classifier completes

Author: Agent Guru Team
Date: 2026
"""

import subprocess
import sys
from pathlib import Path


def run_training_script(script_name: str, description: str) -> bool:
    """Run a training script and return success status.

    Args:
        script_name: Name of the training script
        description: Description of what's being trained

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: If script_name or description is not a non-empty string.
    """
    if not isinstance(script_name, str) or not script_name.strip():
        raise ValueError(f"script_name must be non-empty string, got {script_name!r}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"description must be non-empty string, got {description!r}")

    print(f"\n{'='*80}")
    print(f"STARTING: {description}")
    print(f"Script: {script_name}")
    print(f"{'='*80}\n")

    script_path = Path(__file__).parent / script_name

    try:
        # Run the training script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            cwd=Path(__file__).parent.parent.parent,  # Run from project root
        )

        print(f"\n{'='*80}")
        print(f"✓ COMPLETED: {description}")
        print(f"{'='*80}\n")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n{'='*80}")
        print(f"✗ FAILED: {description}")
        print(f"Error: {e}")
        print(f"{'='*80}\n")
        return False
    except KeyboardInterrupt:
        print(f"\n{'='*80}")
        print(f"⚠ INTERRUPTED: {description}")
        print(f"{'='*80}\n")
        return False


def main():
    """Run all training scripts in sequence."""
    print(f"\n{'='*80}")
    print("AGENT GURU - MASTER TRAINING PIPELINE")
    print("Training Intent Classifier + NER Model")
    print(f"{'='*80}\n")

    # Check GPU
    import torch

    if not torch.cuda.is_available():
        print("⚠ WARNING: GPU not available!")
        print("⚠ Training will take MUCH longer on CPU")
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("Exiting...")
            return
    else:
        print(f"✓ GPU available: {torch.cuda.get_device_name(0)}")
        print(f"✓ CUDA version: {torch.version.cuda}")
        print(f"✓ GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB\n")

    # Training sequence
    training_steps = [
        ("train_intent_classifier.py", "Intent Classifier (DeBERTa-v3-large, 30 epochs)"),
        ("train_ner_model.py", "NER Model (Entity Recognition)"),
    ]

    results = {}

    for script_name, description in training_steps:
        success = run_training_script(script_name, description)
        results[description] = success

        if not success:
            print(f"\n⚠ Training failed at: {description}")
            print("Stopping pipeline...")
            break

    # Final summary
    print(f"\n{'='*80}")
    print("TRAINING PIPELINE SUMMARY")
    print(f"{'='*80}")

    for description, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status}: {description}")

    print(f"{'='*80}\n")

    # Check if all succeeded
    if all(results.values()):
        print("🎉 ALL TRAINING COMPLETED SUCCESSFULLY!")
        print("Models are ready for deployment.\n")
    else:
        print("⚠ Some training steps failed. Please review the logs.\n")


if __name__ == "__main__":
    main()
