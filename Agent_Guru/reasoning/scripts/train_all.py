"""Master Training Script - Train Intent Classifier + NER Model.

Runs both training scripts in sequence:
1. Intent Classifier (DeBERTa-v3-large) - 50 epochs with early stopping
2. NER Model - After intent classifier completes

Author: Agent Guru Team
Date: 2026
"""

import subprocess  # nosec B404
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
        msg = f"script_name must be non-empty string, got {script_name!r}"
        raise ValueError(msg)
    if not isinstance(description, str) or not description.strip():
        msg = f"description must be non-empty string, got {description!r}"
        raise ValueError(msg)

    script_path = Path(__file__).parent / script_name

    try:
        # Run the training script
        subprocess.run(  # nosec B603  # noqa: S603
            [sys.executable, str(script_path)],
            check=True,
            cwd=Path(__file__).parent.parent.parent,  # Run from project root
        )

        return True

    except subprocess.CalledProcessError:
        return False

def main() -> None:
    """Run all training scripts in sequence."""
    # Check GPU
    import torch

    if not torch.cuda.is_available():
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != "yes":
            return
    else:
        pass

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
            break

    # Final summary

    for _description, _success in results.items():
        pass

    # Check if all succeeded
    if all(results.values()):
        pass
    else:
        pass

if __name__ == "__main__":
    main()
