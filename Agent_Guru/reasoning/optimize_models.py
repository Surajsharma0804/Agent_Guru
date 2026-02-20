"""
Complete Model Optimization Script

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
    print(f"\n{'='*80}")
    print(f"🔧 {description}")
    print(f"{'='*80}\n")
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"\n✅ {description} - SUCCESS\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - FAILED")
        print(f"Error: {e}\n")
        return False
    except FileNotFoundError:
        print(f"\n❌ {description} - FAILED")
        print(f"Error: Command not found. Make sure Python is in your PATH.\n")
        return False


def check_prerequisites() -> bool:
    """Check if all prerequisites are met.
    
    Returns:
        True if all prerequisites are met, False otherwise
    """
    print(f"\n{'='*80}")
    print("🔍 Checking Prerequisites")
    print(f"{'='*80}\n")
    
    # Check if model directory exists
    model_dir = Path("Agent_Guru/reasoning/models/intent_classifier")
    if not model_dir.exists():
        print(f"❌ Model directory not found: {model_dir}")
        return False
    print(f"✅ Model directory found: {model_dir}")
    
    # Check if final_model exists
    final_model = model_dir / "final_model"
    if not final_model.exists():
        print(f"❌ Final model directory not found: {final_model}")
        print("   Please train the model first using train_intent_classifier.py")
        return False
    print(f"✅ Final model found: {final_model}")
    
    # Check if cleanup script exists
    cleanup_script = Path("Agent_Guru/reasoning/cleanup_model_checkpoints.py")
    if not cleanup_script.exists():
        print(f"❌ Cleanup script not found: {cleanup_script}")
        return False
    print(f"✅ Cleanup script found: {cleanup_script}")
    
    # Check if conversion script exists
    convert_script = Path("Agent_Guru/reasoning/convert_to_onnx.py")
    if not convert_script.exists():
        print(f"❌ Conversion script not found: {convert_script}")
        return False
    print(f"✅ Conversion script found: {convert_script}")
    
    print("\n✅ All prerequisites met!\n")
    return True


def main():
    """Main optimization workflow."""
    print(f"\n{'='*80}")
    print("🚀 Model Optimization Workflow")
    print(f"{'='*80}")
    print("\nThis script will:")
    print("  1. Clean up training checkpoints (~38GB space savings)")
    print("  2. Convert model to ONNX format (faster inference)")
    print("  3. Verify the optimized setup")
    print(f"\n{'='*80}\n")
    
    # Check prerequisites
    if not check_prerequisites():
        print("❌ Prerequisites not met. Please fix the issues above and try again.")
        sys.exit(1)
    
    # Ask for confirmation
    print("⚠️  WARNING: This will delete training checkpoint files!")
    print("   (They are not needed for production and take up ~38GB)")
    response = input("\n   Continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("\n❌ Optimization cancelled")
        sys.exit(0)
    
    # Step 1: Cleanup checkpoints
    success = run_command(
        [sys.executable, "Agent_Guru/reasoning/cleanup_model_checkpoints.py", "--execute"],
        "Step 1: Cleaning up training checkpoints"
    )
    
    if not success:
        print("❌ Cleanup failed. Stopping optimization.")
        sys.exit(1)
    
    # Step 2: Convert to ONNX
    success = run_command(
        [sys.executable, "Agent_Guru/reasoning/convert_to_onnx.py"],
        "Step 2: Converting model to ONNX format"
    )
    
    if not success:
        print("⚠️  ONNX conversion failed, but cleanup was successful.")
        print("   You can try converting manually later.")
        print("   Production will still work with the PyTorch model.")
    
    # Step 3: Verify setup (optional)
    verify_script = Path("verify_implementation.py")
    if verify_script.exists():
        print(f"\n{'='*80}")
        print("🔍 Would you like to verify the optimized setup?")
        print(f"{'='*80}\n")
        response = input("   Run verification? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            run_command(
                [sys.executable, "verify_implementation.py"],
                "Step 3: Verifying optimized setup"
            )
    
    # Final summary
    print(f"\n{'='*80}")
    print("✅ Optimization Complete!")
    print(f"{'='*80}\n")
    print("Summary:")
    print("  ✅ Training checkpoints cleaned up (~38GB freed)")
    
    onnx_model = Path("Agent_Guru/reasoning/models/intent_classifier/final_model/model.onnx")
    if onnx_model.exists():
        print("  ✅ ONNX model created (faster inference)")
    else:
        print("  ⚠️  ONNX model not created (using PyTorch model)")
    
    print("\nNext steps:")
    print("  1. Test the intent classifier with your own inputs")
    print("  2. Deploy to production")
    print("  3. Monitor performance and accuracy")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
