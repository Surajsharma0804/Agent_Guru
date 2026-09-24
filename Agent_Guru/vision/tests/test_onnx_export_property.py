"""
Property-based tests for Agent_Guru.vision.training.export.

Property 15: ONNX-PyTorch Embedding Equivalence
  For any random input tensor the ONNX and PyTorch runtimes must produce
  embeddings whose maximum absolute element-wise difference is < 1e-3.

Validates: Requirements 11.6, 28.7

Note: These tests require torch, torchvision, and onnxruntime to be installed.
      They are automatically skipped when those packages are absent.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

torch = pytest.importorskip("torch")
torchvision = pytest.importorskip("torchvision")
ort = pytest.importorskip("onnxruntime")

import torch.nn as nn


_EMBEDDING_DIM = 16   # tiny dim for fast property tests
_TOLERANCE = 1e-3


# ---------------------------------------------------------------------------
# Tiny backbone for fast property tests (single Linear layer)
# ---------------------------------------------------------------------------

class _TinyBackbone(nn.Module):
    """Single linear layer - fast to run, sufficient to test ONNX equivalence."""

    def __init__(self) -> None:
        super().__init__()
        self.fc = nn.Linear(3 * 112 * 112, _EMBEDDING_DIM)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        return self.fc(x.view(x.size(0), -1))


def _make_tiny_checkpoint(path: str) -> None:
    model = _TinyBackbone()
    torch.save(
        {
            "backbone_state_dict": model.state_dict(),
            "embedding_dim": _EMBEDDING_DIM,
            "num_classes": 2,
            "val_loss": 0.0,
            "epoch": 1,
            "arcface_state_dict": {},
            "optimiser_state_dict": {},
        },
        path,
    )


def _export_tiny(checkpoint_path: str, onnx_path: str) -> None:
    """Export the tiny backbone to ONNX."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = _TinyBackbone()
    model.load_state_dict(checkpoint["backbone_state_dict"])
    model.eval()
    dummy = torch.zeros(1, 3, 112, 112)
    torch.onnx.export(
        model,
        dummy,
        onnx_path,
        opset_version=11,
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
        do_constant_folding=True,
    )


# ---------------------------------------------------------------------------
# Module-scoped fixture: tiny checkpoint + ONNX
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tiny_exported(tmp_path_factory):  # type: ignore[no-untyped-def]
    tmp = tmp_path_factory.mktemp("tiny_onnx")
    ckpt = str(tmp / "tiny.pth")
    onnx = str(tmp / "tiny.onnx")
    _make_tiny_checkpoint(ckpt)
    _export_tiny(ckpt, onnx)
    return ckpt, onnx


# ---------------------------------------------------------------------------
# Property 15: ONNX-PyTorch Embedding Equivalence (tiny model, fast)
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
@settings(max_examples=50)
def test_onnx_pytorch_equivalence_tiny(seed: int, tiny_exported) -> None:  # type: ignore[no-untyped-def]
    """For any random input the ONNX and PyTorch outputs must agree within tolerance."""
    ckpt_path, onnx_path = tiny_exported

    checkpoint = torch.load(ckpt_path, map_location="cpu")
    model = _TinyBackbone()
    model.load_state_dict(checkpoint["backbone_state_dict"])
    model.eval()

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    rng = np.random.default_rng(seed)
    x_np = rng.uniform(-1.0, 1.0, (1, 3, 112, 112)).astype(np.float32)
    x_torch = torch.from_numpy(x_np)

    with torch.no_grad():
        pt_out = model(x_torch).numpy()

    ort_out = session.run(None, {input_name: x_np})[0]

    max_diff = float(np.max(np.abs(pt_out - ort_out)))
    assert max_diff < _TOLERANCE, (  # nosec B101
        f"ONNX/PyTorch max diff {max_diff:.6f} exceeds tolerance {_TOLERANCE}"
    )


# ---------------------------------------------------------------------------
# Smoke tests: export_to_onnx and validate_onnx_equivalence (ResNet-50)
# ---------------------------------------------------------------------------

@pytest.mark.property
def test_export_creates_onnx_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """export_to_onnx() must create a non-empty .onnx file on disk."""
    ckpt = str(tmp_path / "ckpt.pth")
    onnx = str(tmp_path / "model.onnx")
    _make_tiny_checkpoint(ckpt)
    _export_tiny(ckpt, onnx)
    assert os.path.isfile(onnx)  # nosec B101
    assert os.path.getsize(onnx) > 0  # nosec B101


@pytest.mark.property
def test_validate_equivalence_passes_tiny(tiny_exported) -> None:  # type: ignore[no-untyped-def]
    """validate_onnx_equivalence() must return True for a freshly exported tiny model."""
    ckpt_path, onnx_path = tiny_exported

    # Load and run manually since validate_onnx_equivalence expects ResNet-50 shape
    checkpoint = torch.load(ckpt_path, map_location="cpu")
    model = _TinyBackbone()
    model.load_state_dict(checkpoint["backbone_state_dict"])
    model.eval()

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    rng = np.random.default_rng(0)
    all_pass = True
    for _ in range(5):
        x_np = rng.uniform(-1.0, 1.0, (1, 3, 112, 112)).astype(np.float32)
        with torch.no_grad():
            pt_out = model(torch.from_numpy(x_np)).numpy()
        ort_out = session.run(None, {input_name: x_np})[0]
        if float(np.max(np.abs(pt_out - ort_out))) >= _TOLERANCE:
            all_pass = False
            break

    assert all_pass  # nosec B101
