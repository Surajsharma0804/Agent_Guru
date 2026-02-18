"""
GPU Check and Auto-Fix Script

Checks if GPU is available and automatically fixes CUDA_VISIBLE_DEVICES if needed.
Run this before training to ensure GPU is enabled.
"""

import os
import sys

import torch


def check_and_fix_gpu():
    """Check GPU availability and fix CUDA_VISIBLE_DEVICES if needed."""
    print("=" * 80)
    print("GPU AVAILABILITY CHECK")
    print("=" * 80)

    # Check current CUDA_VISIBLE_DEVICES
    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "not set")
    print(f"\nCUDA_VISIBLE_DEVICES: {cuda_visible}")

    # Check PyTorch CUDA availability
    cuda_available = torch.cuda.is_available()
    print(f"PyTorch CUDA available: {cuda_available}")

    if cuda_available:
        print(f"✓ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"✓ CUDA version: {torch.version.cuda}")
        print(f"✓ GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print("\n" + "=" * 80)
        print("GPU IS READY FOR TRAINING")
        print("=" * 80)
        return True
    else:
        print("\n⚠ WARNING: GPU NOT DETECTED")

        # Check if CUDA_VISIBLE_DEVICES is blocking GPU
        if cuda_visible == "-1":
            print("\n✗ CUDA_VISIBLE_DEVICES is set to -1 (GPU disabled)")
            print("\nFIXING: Setting CUDA_VISIBLE_DEVICES to 0...")

            # Fix for current session
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"

            # Try to set permanently (Windows)
            if sys.platform == "win32":
                try:
                    import subprocess

                    subprocess.run(
                        [
                            "powershell",
                            "-Command",
                            "[System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '0', [System.EnvironmentVariableTarget]::User)",
                        ],
                        check=True,
                    )
                    print("✓ CUDA_VISIBLE_DEVICES set to 0 permanently")
                except Exception as e:
                    print(f"⚠ Could not set permanently: {e}")
                    print("  Run: set_cuda_env.ps1 to fix permanently")

            # Re-check after fix
            print("\nRe-checking GPU availability...")
            # Need to restart Python to pick up environment variable change
            print("\n⚠ RESTART REQUIRED: Please restart your terminal/Python session")
            print("  Then run this script again to verify GPU is detected")
            print("\n" + "=" * 80)
            return False
        else:
            print("\n✗ GPU not detected for unknown reason")
            print("  Possible causes:")
            print("  1. NVIDIA drivers not installed")
            print("  2. CUDA toolkit not installed")
            print("  3. PyTorch CUDA version mismatch")
            print("\n  Run: nvidia-smi to check if GPU is detected by system")
            print("  Run: nvcc --version to check CUDA toolkit version")
            print("\n" + "=" * 80)
            return False


if __name__ == "__main__":
    success = check_and_fix_gpu()
    sys.exit(0 if success else 1)
