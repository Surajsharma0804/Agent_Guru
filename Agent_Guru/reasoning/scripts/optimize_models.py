"""Complete Model Optimization Script.

This script performs a complete optimization of the intent classifier models:
1. Cleans up unnecessary training checkpoints (saves ~38GB)
2. Converts PyTorch model to ONNX format (for faster inference)
3. Verifies the optimized setup works correctly

Author: Kiro AI
Date: 2026-02-19
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and handle errors.

    Args:
        cmd: Command to run as list of strings
        description: Description of what the command does

    Returns:
        True if successful, False otherwise

    """
    try:
        subprocess.run(cmd, check=True, capture_output=False, text=True)  # noqa: S603
        return True
    except subprocess.CalledProcessError:
        return False
        return False


def check_prerequisites() -> bool:
    """Check if all prerequisites are met.

    Returns:
        True if all prerequisites are met, False otherwise

    """
    # Check if model directory exists
    model_dir = Path("Agent_Guru/reasoning/models/intent_classifier")
    if not model_dir.exists():
        return False

    # Check if final_model exists
    final_model = model_dir / "final_model"
    if not final_model.exists():
        return False

    # Check if cleanup script exists
    cleanup_script = Path("Agent_Guru/reasoning/scripts/cleanup_model_checkpoints.py")
    if not cleanup_script.exists():
        return False

    # Check if conversion script exists
    convert_script = Path("Agent_Guru/reasoning/scripts/convert_to_onnx.py")
    return convert_script.exists()


def main() -> None:
    """Main optimization workflow."""
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Ask for confirmation
    response = input("\n   Continue? (yes/no): ")

    if response.lower() not in ["yes", "y"]:
        sys.exit(0)

    # Step 1: Cleanup checkpoints
    success = run_command(
        [sys.executable, "Agent_Guru/reasoning/scripts/cleanup_model_checkpoints.py", "--execute"],
        "Step 1: Cleaning up training checkpoints",
    )

    if not success:
        sys.exit(1)

    # Step 2: Convert to ONNX
    success = run_command(
        [sys.executable, "Agent_Guru/reasoning/scripts/convert_to_onnx.py"],
        "Step 2: Converting model to ONNX format",
    )

    if not success:
        pass

    # Step 3: Verify setup (optional)
    verify_script = Path("verify_implementation.py")
    if verify_script.exists():
        response = input("   Run verification? (yes/no): ")

        if response.lower() in ["yes", "y"]:
            run_command(
                [sys.executable, "verify_implementation.py"],
                "Step 3: Verifying optimized setup",
            )

    # Final summary

    onnx_model = Path("Agent_Guru/reasoning/models/intent_classifier/final_model/model.onnx")
    if onnx_model.exists():
        pass
    else:
        pass


if __name__ == "__main__":
    main()
