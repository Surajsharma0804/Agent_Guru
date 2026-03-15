"""
Example: Add a new identity to the GuruVision database without retraining.

Usage:
    python -m Agent_Guru.vision.examples.add_identity \\
        --name "Alice" \\
        --images path/to/alice/*.jpg \\
        [--permission user] \\
        [--config path/to/config.yaml]

Permission levels: admin | user | guest | denied

Requirements: 16.1, 16.2
"""

import argparse
import glob
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Add an identity to the GuruVision database")
    parser.add_argument("--name", required=True, help="Identity name (unique)")
    parser.add_argument(
        "--images",
        required=True,
        nargs="+",
        help="Image file paths or glob patterns (e.g. photos/*.jpg)",
    )
    parser.add_argument(
        "--permission",
        default="user",
        choices=["admin", "user", "guest", "denied"],
        help="Permission level (default: user)",
    )
    parser.add_argument("--config", default=None, help="Optional YAML/JSON config file")
    args = parser.parse_args()

    # Expand globs
    image_paths: list[str] = []
    for pattern in args.images:
        expanded = glob.glob(pattern)
        if expanded:
            image_paths.extend(expanded)
        elif Path(pattern).exists():
            image_paths.append(pattern)
        else:
            print(f"WARNING: no files matched '{pattern}'", file=sys.stderr)

    if not image_paths:
        print("ERROR: no image files found.", file=sys.stderr)
        return 1

    try:
        import cv2  # type: ignore[import]
        import numpy as np
    except ImportError:
        print("ERROR: opencv-python is required. Install with: pip install opencv-python", file=sys.stderr)
        return 1

    from Agent_Guru.vision.engine import GuruVisionEngine

    engine = GuruVisionEngine(config_path=args.config)
    engine.initialize()

    images = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is None:
            print(f"WARNING: could not read '{path}' — skipping", file=sys.stderr)
            continue
        images.append(img)

    if not images:
        print("ERROR: no valid images could be loaded.", file=sys.stderr)
        engine.shutdown()
        return 1

    print(f"Adding identity '{args.name}' from {len(images)} image(s) …")
    success = engine.add_identity(args.name, images, permission_level=args.permission)

    if success:
        identities = engine.get_identities()
        info = next((i for i in identities if i.name == args.name), None)
        if info:
            print(
                f"  Stored {info.num_embeddings} embedding(s) "
                f"with permission '{info.permission_level}'."
            )
        print(f"Identity '{args.name}' added successfully.")
    else:
        print(f"ERROR: failed to add identity '{args.name}'.", file=sys.stderr)

    engine.shutdown()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
