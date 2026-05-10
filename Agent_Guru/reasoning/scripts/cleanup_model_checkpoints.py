"""Model Checkpoint Cleanup Script.

This script removes unnecessary training checkpoints from the intent classifier
model directory, keeping only files needed for production inference.

Space Savings: ~37GB (from 38.82GB to ~1GB)

What Gets Deleted:
- Training checkpoint files (*.ckpt)
- Intermediate checkpoint directories (checkpoint-*)
- Training logs
- Optimizer states

What Gets Kept:
- final_model/ directory (for ONNX conversion)
- label_mappings.yaml
- Tokenizer files (tokenizer.json, vocab.json, merges.txt, etc.)
- training_metrics.yaml (for reference)
- test_results.json (if exists)

Author: Kiro AI
Date: 2026-02-19
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_directory_size(path: Path) -> float:
    """Get total size of directory in GB.

    Args:
        path: Directory path

    Returns:
        Size in GB

    """
    total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total_size / (1024**3)


def cleanup_model_checkpoints(model_dir: str, dry_run: bool = True) -> None:
    """Clean up unnecessary training checkpoints.

    Args:
        model_dir: Path to model directory
        dry_run: If True, only show what would be deleted without actually deleting

    """
    model_path = Path(model_dir)

    if not model_path.exists():
        return

    # Calculate initial size
    initial_size = get_directory_size(model_path)

    # Files and directories to delete

    # Files to keep (for reference)
    files_to_keep = [
        "final_model/",
        "label_mappings.yaml",
        "tokenizer.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "training_metrics.yaml",
        "test_results.json",
    ]

    for item in files_to_keep:
        item_path = model_path / item
        if item_path.exists():
            if item_path.is_dir():
                size = get_directory_size(item_path)
            else:
                size = item_path.stat().st_size / (1024**2)

    # Find files to delete
    files_to_delete: list[Path] = []

    # Find .ckpt files
    for ckpt_file in model_path.glob("*.ckpt"):
        files_to_delete.append(ckpt_file)

    # Find checkpoint directories
    for checkpoint_dir in model_path.glob("checkpoint-*"):
        if checkpoint_dir.is_dir():
            files_to_delete.append(checkpoint_dir)

    # Find logs directory
    logs_dir = model_path / "logs"
    if logs_dir.exists() and logs_dir.is_dir():
        files_to_delete.append(logs_dir)

    if not files_to_delete:
        return

    # Calculate space to be freed
    space_to_free = 0.0
    for delete_item in files_to_delete:
        if delete_item.is_dir():
            size = get_directory_size(delete_item)
            space_to_free += size
        else:
            size = delete_item.stat().st_size / (1024**3)
            space_to_free += size

    if dry_run:
        return

    # Confirm deletion
    response = input("   Type 'DELETE' to confirm: ")

    if response != "DELETE":
        return

    # Delete files
    deleted_count = 0

    for delete_item in files_to_delete:
        try:
            if delete_item.is_dir():
                shutil.rmtree(delete_item)
            else:
                delete_item.unlink()
            deleted_count += 1
        except Exception:
            logger.exception("Operation failed")

    # Calculate final size
    final_size = get_directory_size(model_path)
    initial_size - final_size


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean up unnecessary model checkpoints")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="Agent_Guru/reasoning/models/intent_classifier",
        help="Path to model directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without actually deleting (default: True)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files (overrides --dry-run)",
    )

    args = parser.parse_args()

    # If --execute is specified, disable dry_run
    dry_run = not args.execute

    cleanup_model_checkpoints(args.model_dir, dry_run=dry_run)


if __name__ == "__main__":
    main()
