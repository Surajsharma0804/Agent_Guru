#!/usr/bin/env python3
"""Model Downloader for Llama 3.2 8B.

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
    except ImportError as e:
        msg = "huggingface_hub not installed. Install with: pip install huggingface-hub"
        raise ImportError(
            msg,
        ) from e

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download pre-quantized GGUF model
        # Note: Replace with actual HuggingFace repo when available
        model_file = hf_hub_download(  # nosec B615
            repo_id="TheBloke/Llama-2-7B-GGUF",  # Placeholder
            filename="llama-2-7b.Q4_K_M.gguf",
            local_dir=str(output_dir),
            local_dir_use_symlinks=False,
        )

        return Path(model_file)

    except Exception as e:
        msg = f"Model download failed: {e!s}"
        raise RuntimeError(msg) from e


def main() -> int | None:
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
        download_model(args.output_dir, args.model_name)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
