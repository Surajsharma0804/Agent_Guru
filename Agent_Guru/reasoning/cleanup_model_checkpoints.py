"""
Model Checkpoint Cleanup Script

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

import shutil
from pathlib import Path
from typing import List


def get_directory_size(path: Path) -> float:
    """Get total size of directory in GB.
    
    Args:
        path: Directory path
        
    Returns:
        Size in GB
    """
    total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    return total_size / (1024 ** 3)


def cleanup_model_checkpoints(model_dir: str, dry_run: bool = True) -> None:
    """Clean up unnecessary training checkpoints.
    
    Args:
        model_dir: Path to model directory
        dry_run: If True, only show what would be deleted without actually deleting
    """
    model_path = Path(model_dir)
    
    if not model_path.exists():
        print(f"❌ Model directory not found: {model_path}")
        return
    
    print(f"\n{'='*80}")
    print("Model Checkpoint Cleanup")
    print(f"{'='*80}\n")
    
    # Calculate initial size
    initial_size = get_directory_size(model_path)
    print(f"📊 Initial directory size: {initial_size:.2f} GB\n")
    
    # Files and directories to delete
    patterns_to_delete = [
        "*.ckpt",  # All checkpoint files
        "checkpoint-*",  # Checkpoint directories
        "logs/",  # Training logs
    ]
    
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
    
    print("📋 Files/directories that will be KEPT:")
    for item in files_to_keep:
        item_path = model_path / item
        if item_path.exists():
            if item_path.is_dir():
                size = get_directory_size(item_path)
                print(f"  ✓ {item} ({size*1024:.2f} MB)")
            else:
                size = item_path.stat().st_size / (1024 ** 2)
                print(f"  ✓ {item} ({size:.2f} MB)")
    
    print(f"\n{'='*80}\n")
    
    # Find files to delete
    files_to_delete: List[Path] = []
    
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
        print("✅ No checkpoint files found to delete. Directory is already clean!")
        return
    
    # Calculate space to be freed
    space_to_free = 0.0
    print("🗑️  Files/directories to DELETE:")
    for item in files_to_delete:
        if item.is_dir():
            size = get_directory_size(item)
            space_to_free += size
            print(f"  ❌ {item.name}/ ({size:.2f} GB)")
        else:
            size = item.stat().st_size / (1024 ** 3)
            space_to_free += size
            print(f"  ❌ {item.name} ({size:.2f} GB)")
    
    print(f"\n{'='*80}")
    print(f"💾 Space to be freed: {space_to_free:.2f} GB")
    print(f"📊 Final directory size: {initial_size - space_to_free:.2f} GB")
    print(f"{'='*80}\n")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No files were deleted")
        print("   Run with dry_run=False to actually delete files")
        return
    
    # Confirm deletion
    print("⚠️  WARNING: This will permanently delete the files listed above!")
    response = input("   Type 'DELETE' to confirm: ")
    
    if response != "DELETE":
        print("\n❌ Cleanup cancelled")
        return
    
    # Delete files
    print("\n🗑️  Deleting files...")
    deleted_count = 0
    
    for item in files_to_delete:
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"  ✓ Deleted directory: {item.name}/")
            else:
                item.unlink()
                print(f"  ✓ Deleted file: {item.name}")
            deleted_count += 1
        except Exception as e:
            print(f"  ❌ Failed to delete {item.name}: {e}")
    
    # Calculate final size
    final_size = get_directory_size(model_path)
    actual_freed = initial_size - final_size
    
    print(f"\n{'='*80}")
    print("✅ Cleanup Complete!")
    print(f"{'='*80}")
    print(f"📊 Initial size: {initial_size:.2f} GB")
    print(f"📊 Final size: {final_size:.2f} GB")
    print(f"💾 Space freed: {actual_freed:.2f} GB")
    print(f"🗑️  Files deleted: {deleted_count}")
    print(f"{'='*80}\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up unnecessary model checkpoints"
    )
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
