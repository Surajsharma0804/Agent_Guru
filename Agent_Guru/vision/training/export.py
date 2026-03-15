"""
Module: Agent_Guru.vision.training.export
Purpose: Export a trained PyTorch ArcFace backbone to ONNX format and
         validate numerical equivalence between the two runtimes.

Requirements: 1.3, 11.1, 11.6, 28.1, 28.7
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("guruvision.training.export")

# Tolerance for PyTorch ↔ ONNX embedding comparison.
_EQUIVALENCE_TOLERANCE: float = 1e-3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_to_onnx(
    checkpoint_path: str,
    output_path: Optional[str] = None,
    opset_version: int = 11,
    embedding_dim: int = 512,
) -> str:
    """Export a trained ResNet-50 ArcFace backbone to ONNX.

    Loads the checkpoint saved by ``train_arcface_model()``, sets the model
    to eval mode, and exports it using ``torch.onnx.export``.

    Args:
        checkpoint_path: Path to the .pth checkpoint produced by training.
        output_path: Destination .onnx file path.  Defaults to the same
            directory as the checkpoint with the name ``guru_face_model.onnx``.
        opset_version: ONNX opset version (default 11).
        embedding_dim: Embedding dimension expected by the backbone FC layer.

    Returns:
        Absolute path to the exported .onnx file.

    Raises:
        FileNotFoundError: If checkpoint_path does not exist.
        ImportError: If PyTorch or torchvision is not installed.
    """
    if not os.path.isfile(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    import torch
    import torchvision.models as models  # type: ignore[import]
    import torch.nn as nn

    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    saved_embedding_dim = checkpoint.get("embedding_dim", embedding_dim)

    backbone = models.resnet50(weights=None)
    backbone.fc = nn.Linear(backbone.fc.in_features, saved_embedding_dim)
    backbone.load_state_dict(checkpoint["backbone_state_dict"])
    backbone.eval()

    if output_path is None:
        ckpt_dir = Path(checkpoint_path).parent
        output_path = str(ckpt_dir / "guru_face_model.onnx")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    dummy_input = torch.zeros(1, 3, 112, 112, dtype=torch.float32)

    torch.onnx.export(
        backbone,
        dummy_input,
        output_path,
        opset_version=opset_version,
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch_size"}, "embedding": {0: "batch_size"}},
        do_constant_folding=True,
    )

    logger.info(
        "Exported ONNX model to '%s' (opset=%d, embedding_dim=%d)",
        output_path,
        opset_version,
        saved_embedding_dim,
    )
    return os.path.abspath(output_path)


def validate_onnx_equivalence(
    checkpoint_path: str,
    onnx_path: str,
    num_samples: int = 10,
    tolerance: float = _EQUIVALENCE_TOLERANCE,
    embedding_dim: int = 512,
) -> bool:
    """Verify that PyTorch and ONNX produce equivalent embeddings.

    Runs ``num_samples`` random inputs through both runtimes and asserts
    that the maximum absolute difference is within ``tolerance``.

    Args:
        checkpoint_path: Path to the .pth checkpoint.
        onnx_path: Path to the exported .onnx model.
        num_samples: Number of random test inputs.
        tolerance: Maximum allowed absolute difference per element.
        embedding_dim: Embedding dimension (used to load the backbone).

    Returns:
        True if all samples are within tolerance.

    Raises:
        FileNotFoundError: If either file does not exist.
        ImportError: If PyTorch, torchvision, or onnxruntime is not installed.
        AssertionError: If any sample exceeds the tolerance.
    """
    for path in (checkpoint_path, onnx_path):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")

    import torch
    import torch.nn as nn
    import torchvision.models as models  # type: ignore[import]
    import onnxruntime as ort  # type: ignore[import]

    # Load PyTorch model
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    saved_embedding_dim = checkpoint.get("embedding_dim", embedding_dim)
    backbone = models.resnet50(weights=None)
    backbone.fc = nn.Linear(backbone.fc.in_features, saved_embedding_dim)
    backbone.load_state_dict(checkpoint["backbone_state_dict"])
    backbone.eval()

    # Load ONNX session
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    rng = np.random.default_rng(42)
    max_diff = 0.0

    with torch.no_grad():
        for i in range(num_samples):
            # Random normalised input in [-1, 1]
            x_np = rng.uniform(-1.0, 1.0, (1, 3, 112, 112)).astype(np.float32)
            x_torch = torch.from_numpy(x_np)

            pt_out = backbone(x_torch).numpy()
            ort_out = session.run(None, {input_name: x_np})[0]

            diff = float(np.max(np.abs(pt_out - ort_out)))
            max_diff = max(max_diff, diff)

            if diff > tolerance:
                logger.error(
                    "Sample %d: max diff %.6f exceeds tolerance %.6f",
                    i, diff, tolerance,
                )
                raise AssertionError(
                    f"ONNX/PyTorch mismatch on sample {i}: "
                    f"max_diff={diff:.6f} > tolerance={tolerance}"
                )

    logger.info(
        "ONNX equivalence validated over %d samples (max_diff=%.6f, tolerance=%.6f)",
        num_samples,
        max_diff,
        tolerance,
    )
    return True
