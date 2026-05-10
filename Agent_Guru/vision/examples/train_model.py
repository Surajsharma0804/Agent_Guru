r"""Example: Train a custom GuruVision face recognition model.

Usage:
    python -m Agent_Guru.vision.examples.train_model \\
        --dataset_dir path/to/dataset \\
        --output_dir path/to/output \\
        [--config path/to/config.yaml]

Dataset layout expected:
    dataset/
        Alice/
            img001.jpg
            img002.jpg
            ...   (50+ images per identity)
        Bob/
            img001.jpg
            ...

Requirements: 1.1, 28.1
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a custom GuruVision ArcFace model")
    parser.add_argument("--dataset_dir", required=True, help="Path to raw dataset directory")
    parser.add_argument("--output_dir", required=True, help="Directory to save model artifacts")
    parser.add_argument("--config", default=None, help="Optional YAML/JSON config file")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir)

    if not dataset_dir.exists():
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Import here so the example can be imported without heavy deps at module level
    from Agent_Guru.vision.training.export import export_to_onnx
    from Agent_Guru.vision.training.preprocess import preprocess_dataset, validate_dataset_structure
    from Agent_Guru.vision.training.train import TrainingConfig, train_arcface_model

    issues = validate_dataset_structure(str(dataset_dir))
    if issues:
        for _issue in issues:
            pass

    aligned_dir = output_dir / "aligned_dataset"
    preprocess_dataset(str(dataset_dir), str(aligned_dir))

    cfg = TrainingConfig(
        dataset_dir=str(aligned_dir),
        output_dir=str(output_dir),
    )
    checkpoint_path = train_arcface_model(cfg)

    onnx_path = output_dir / "guru_face_model.onnx"
    export_to_onnx(str(checkpoint_path), str(onnx_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
