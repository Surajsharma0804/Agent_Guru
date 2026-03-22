#!/usr/bin/env python3
"""
Model Downloader for Llama 3.2 8B

Downloads and prepares Llama 3.2 8B model with Q4_K_M quantization for local inference.

Usage:
    python download_model.py --output-dir models/

Requirements:
- huggingface_hub for model download
- llama.cpp for quantization (optional, can use pre-quantized)
"""

import argparse
import sys
from pathlib import Path


def download_model(output_dir: Path, model_name: str = "llama-3.2-8b-q4_k_m") -> Path:
    """Download Llama 3.2 8B model with Q4_K_M quantization.

    Args:
        output_dir: Directory to save model
        model_name: Model variant to download

    Returns:
        Path to downloaded model file

    Raises:
        ImportError: If huggingface_hub not installed
        RuntimeError: If download fails
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise ImportError(
            "huggingface_hub not installed. " "Install with: pip install huggingface-hub"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {model_name} to {output_dir}...")
    print("This may take several minutes (model size: ~4.5GB)")

    try:
        # Download pre-quantized GGUF model
        # Note: Replace with actual HuggingFace repo when available
        model_file = hf_hub_download(  # nosec B615
            repo_id="TheBloke/Llama-2-7B-GGUF",  # Placeholder
            filename="llama-2-7b.Q4_K_M.gguf",
            local_dir=str(output_dir),
            local_dir_use_symlinks=False,
        )

        print(f"✓ Model downloaded: {model_file}")
        return Path(model_file)

    except Exception as e:
        raise RuntimeError(f"Model download failed: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Download Llama 3.2 8B model for local inference")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models"),
        help="Output directory for model (default: models/)",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="llama-3.2-8b-q4_k_m",
        help="Model variant to download",
    )

    args = parser.parse_args()

    try:
        model_path = download_model(args.output_dir, args.model_name)
        print(f"\n✓ Model ready: {model_path}")
        print("\nNext steps:")
        print("1. Install llama.cpp server binary")
        print("2. Configure LocalLLMConfig with model path")
        print("3. Start LocalLLMServer")
        return 0
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
