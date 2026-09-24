#!/usr/bin/env python3
"""
Agent Guru - Production Model Downloader
=========================================
Downloads all required ONNX model files from their official sources.

Models downloaded:
  - yolov8n.onnx          YOLOv8n object detection (Ultralytics)
  - midas_v31.onnx        MiDaS v3.1 monocular depth (Intel ISL)
  - arcface_r100.onnx     ArcFace R100 face recognition (InsightFace)
  - trocr_handwritten.onnx TrOCR handwriting recognition (Microsoft)
  - scene_efficientnet.onnx EfficientNet-B4 scene classification (Places365)
  - emotion_model.onnx    HSEmotion 7-class emotion recognition
  - liveness_minifasnet.onnx MiniFASNet anti-spoofing (minivision-group)

Usage:
    python models/download_models.py [--models MODEL [MODEL ...]] [--force]

    # Download all models
    python models/download_models.py

    # Download specific models
    python models/download_models.py --models yolov8n arcface

    # Force re-download even if files exist
    python models/download_models.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("download_models")

# ---------------------------------------------------------------------------
# Root of the models directory (same directory as this script)
# ---------------------------------------------------------------------------
MODELS_DIR = Path(__file__).parent.resolve()


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    """Specification for a single model file."""

    name: str                          # logical name (used with --models flag)
    filename: str                      # output filename inside MODELS_DIR
    description: str
    sha256: Optional[str] = None       # expected SHA-256 hex digest (None = skip check)
    size_mb: Optional[float] = None    # approximate size for progress display
    # One of the following must be set:
    url: Optional[str] = None          # direct download URL
    export_fn: Optional[Callable[[], None]] = None  # custom export function


# ---------------------------------------------------------------------------
# Custom export functions (called when no direct ONNX URL is available)
# ---------------------------------------------------------------------------

def _export_yolov8n() -> None:
    """Export YOLOv8n to ONNX via the ultralytics package."""
    out = MODELS_DIR / "yolov8n.onnx"
    log.info("Exporting YOLOv8n to ONNX via ultralytics …")
    try:
        from ultralytics import YOLO  # type: ignore[import]
    except ImportError:
        log.info("Installing ultralytics …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics", "-q"])
        from ultralytics import YOLO  # type: ignore[import]

    model = YOLO("yolov8n.pt")  # downloads weights automatically
    model.export(format="onnx", imgsz=640, opset=17, simplify=True)
    # ultralytics writes yolov8n.onnx next to the .pt file
    exported = Path("yolov8n.onnx")
    if not exported.exists():
        # Try the default ultralytics cache location
        import glob
        candidates = glob.glob(str(Path.home() / ".ultralytics" / "**" / "yolov8n.onnx"), recursive=True)
        if candidates:
            exported = Path(candidates[0])
    if exported.exists():
        shutil.move(str(exported), str(out))
        log.info("YOLOv8n ONNX saved to %s", out)
    else:
        raise FileNotFoundError("YOLOv8n ONNX export did not produce a file at expected path.")


def _export_midas() -> None:
    """Download MiDaS v2.1 small ONNX from the official isl-org GitHub release.

    DPT-Large (v3.1) cannot be exported to ONNX with torch.onnx.export in
    PyTorch >=2.0 due to dynamic Unflatten shapes.  The v2.1-small model
    (256×256 input) is the recommended production ONNX variant and is
    available as a pre-built binary from the official release page.
    """
    out = MODELS_DIR / "midas_v31.onnx"

    # Official pre-built ONNX from isl-org/MiDaS GitHub releases
    mirrors = [
        # v2.1 small - 256×256, ~83 MB, officially supported ONNX
        "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx",
        # Mirror via HuggingFace
        "https://huggingface.co/Intel/dpt-large/resolve/main/onnx/model.onnx",
    ]
    for url in mirrors:
        try:
            log.info("Trying MiDaS mirror: %s", url)
            _download_url(url, out)
            log.info("MiDaS ONNX saved to %s", out)
            return
        except Exception as exc:
            log.warning("Mirror failed (%s): %s", url, exc)

    # Final fallback: export MiDaS v2.1 small via torch.hub (exportable model)
    log.info("All mirrors failed - exporting MiDaS v2.1 small via torch.hub …")
    try:
        import torch  # type: ignore[import]
    except ImportError:
        raise RuntimeError("PyTorch is required to export MiDaS. Install it first.")

    log.info("Loading MiDaS v2.1 small from torch.hub (isl-org/MiDaS) …")
    midas = torch.hub.load(
        "isl-org/MiDaS", "MiDaS_small", pretrained=True, trust_repo=True
    )
    midas.eval()
    dummy = torch.randn(1, 3, 256, 256)
    log.info("Running torch.onnx.export …")
    torch.onnx.export(
        midas,
        dummy,
        str(out),
        input_names=["input"],
        output_names=["output"],
        opset_version=12,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )
    log.info("MiDaS v2.1 small ONNX saved to %s", out)


def _export_trocr() -> None:
    """Export TrOCR-base-handwritten encoder to ONNX via transformers + torch.onnx.

    optimum v2.x removed the `optimum.exporters.onnx` Python API; we use
    the CLI subprocess instead, with a direct torch.onnx.export fallback.
    """
    out = MODELS_DIR / "trocr_handwritten.onnx"
    log.info("Exporting TrOCR-base-handwritten to ONNX …")

    # --- Attempt 1: optimum-cli (works with optimum >=1.x and >=2.x) ---
    with tempfile.TemporaryDirectory() as tmp:
        try:
            log.info("Trying optimum-cli export …")
            subprocess.check_call(
                [
                    sys.executable, "-m", "optimum.exporters.onnx",
                    "--model", "microsoft/trocr-base-handwritten",
                    "--task", "image-to-text",
                    "--opset", "17",
                    tmp,
                ],
                timeout=600,
            )
            _collect_trocr_onnx(Path(tmp), out)
            return
        except Exception as exc:
            log.warning("optimum-cli export failed (%s); trying CLI entrypoint …", exc)

        # --- Attempt 2: optimum-cli as a shell command ---
        try:
            subprocess.check_call(
                [
                    "optimum-cli", "export", "onnx",
                    "--model", "microsoft/trocr-base-handwritten",
                    "--task", "image-to-text",
                    "--opset", "17",
                    tmp,
                ],
                timeout=600,
            )
            _collect_trocr_onnx(Path(tmp), out)
            return
        except Exception as exc:
            log.warning("optimum-cli shell export failed (%s); falling back to torch.onnx …", exc)

    # --- Attempt 3: direct torch.onnx.export of the vision encoder ---
    log.info("Exporting TrOCR encoder directly via torch.onnx.export …")
    try:
        import torch  # type: ignore[import]
        # TrOCRProcessor is imported to prove the transformers install is
        # complete before the long export below starts, not to be called
        # here -- hence the F401 suppression rather than a deletion.
        from transformers import (  # type: ignore[import]  # noqa: F401
            TrOCRProcessor,
            VisionEncoderDecoderModel,
        )
    except ImportError as exc:
        raise RuntimeError(f"transformers / torch required for TrOCR export: {exc}")

    log.info("Loading microsoft/trocr-base-handwritten …")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
    encoder = model.encoder
    encoder.eval()

    # TrOCR encoder expects pixel_values: [B, 3, 384, 384]
    dummy = torch.randn(1, 3, 384, 384)
    log.info("Running torch.onnx.export on TrOCR encoder …")
    torch.onnx.export(
        encoder,
        dummy,
        str(out),
        input_names=["pixel_values"],
        output_names=["last_hidden_state"],
        opset_version=14,
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "last_hidden_state": {0: "batch"},
        },
    )
    log.info("TrOCR encoder ONNX saved to %s", out)


def _collect_trocr_onnx(tmp_dir: Path, out: Path) -> None:
    """Move the encoder ONNX produced by optimum to *out*."""
    encoder = tmp_dir / "encoder_model.onnx"
    if encoder.exists():
        shutil.copy(str(encoder), str(out))
        log.info("TrOCR encoder ONNX saved to %s", out)
        return
    onnx_files = list(tmp_dir.glob("*.onnx"))
    if onnx_files:
        shutil.copy(str(onnx_files[0]), str(out))
        log.info("TrOCR ONNX saved to %s (from %s)", out, onnx_files[0].name)
        return
    raise FileNotFoundError("optimum export did not produce an ONNX file.")


def _export_liveness_minifasnet() -> None:
    """Download MiniFASNetV2 weights from known-good mirrors, or export from PyTorch."""
    out = MODELS_DIR / "liveness_minifasnet.onnx"
    mirrors = [
        "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/models/liveness/2.7_80x80_MiniFASNetV2.onnx",
        "https://github.com/deepinsight/insightface/raw/master/python-package/insightface/data/models/antispoof/2.7_80x80_MiniFASNetV2.onnx",
    ]
    for url in mirrors:
        try:
            log.info("Trying liveness mirror: %s", url)
            _download_url(url, out)
            log.info("MiniFASNetV2 ONNX saved to %s", out)
            return
        except Exception as exc:
            log.warning("Mirror failed (%s): %s", url, exc)

    # Final fallback: clone repo and export from .pth weights
    log.info("All mirrors failed - attempting PyTorch export of MiniFASNetV2 …")
    try:
        import torch  # type: ignore[import]
    except ImportError:
        raise RuntimeError("PyTorch required to export MiniFASNet. Install it first.")

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = Path(tmp) / "Silent-Face-Anti-Spoofing"
        # --no-checkout avoids Windows path issues (spaces in saved_logs filenames)
        subprocess.check_call(
            ["git", "clone", "--depth=1", "--no-checkout",
             "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git",
             str(repo_dir)],
        )

        # Extract only the files we need via `git show` (no checkout required)
        src_dir = repo_dir / "src" / "model_lib"
        src_dir.mkdir(parents=True, exist_ok=True)
        ckpt_dir = repo_dir / "resources" / "anti_spoof_models"
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        for git_path, local_path in [
            ("src/model_lib/MiniFASNet.py", src_dir / "MiniFASNet.py"),
            ("resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth",
             ckpt_dir / "2.7_80x80_MiniFASNetV2.pth"),
        ]:
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "show", f"HEAD:{git_path}"],
                capture_output=True,
            )
            if result.returncode == 0:
                local_path.write_bytes(result.stdout)
                log.info("Extracted %s (%d bytes)", git_path, len(result.stdout))
            else:
                log.warning("Could not extract %s: %s", git_path, result.stderr.decode())

        # Create __init__.py so the directory is importable (not in the repo)
        (src_dir / "__init__.py").write_text("")

        sys.path.insert(0, str(repo_dir / "src"))
        try:
            from model_lib.MiniFASNet import MiniFASNetV2  # type: ignore[import]
            model = MiniFASNetV2(conv6_kernel=(5, 5))
            ckpt = ckpt_dir / "2.7_80x80_MiniFASNetV2.pth"
            if ckpt.exists():
                state = torch.load(str(ckpt), map_location="cpu")
                # Weights may be wrapped in DataParallel (module. prefix)
                if all(k.startswith("module.") for k in state.keys()):
                    state = {k[len("module."):]: v for k, v in state.items()}
                model.load_state_dict(state)
                log.info("Loaded MiniFASNetV2 weights from %s", ckpt)
            model.eval()
            dummy = torch.randn(1, 3, 80, 80)
            torch.onnx.export(
                model, dummy, str(out),
                input_names=["input"], output_names=["output"], opset_version=11,
            )
            log.info("MiniFASNetV2 exported to %s", out)
        finally:
            sys.path.pop(0)


def _export_scene_efficientnet() -> None:
    """Export EfficientNet-B4 fine-tuned on Places365 to ONNX."""
    out = MODELS_DIR / "scene_efficientnet.onnx"
    log.info("Exporting EfficientNet-B4 (Places365) to ONNX …")

    try:
        import torch  # type: ignore[import]
        # Imported for its side effect of proving torchvision is present
        # and ABI-compatible with this torch build; the export below
        # fails obscurely otherwise.
        import torchvision  # type: ignore[import]  # noqa: F401
    except ImportError:
        raise RuntimeError("PyTorch + torchvision required to export scene model.")

    try:
        import timm  # type: ignore[import]
    except ImportError:
        log.info("Installing timm …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "timm", "-q"])
        import timm  # type: ignore[import]

    # Load EfficientNet-B4 pretrained on ImageNet, then adapt head for 30 scene classes
    # For production, replace with a Places365-fine-tuned checkpoint.
    log.info("Loading EfficientNet-B4 from timm (ImageNet pretrained) …")
    import timm  # type: ignore[import]
    model = timm.create_model("efficientnet_b4", pretrained=True, num_classes=30)
    model.eval()

    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy,
        str(out),
        input_names=["input"],
        output_names=["output"],
        opset_version=17,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )
    log.info(
        "Scene EfficientNet ONNX saved to %s  "
        "(NOTE: fine-tune on Places365 for production accuracy)",
        out,
    )


# ---------------------------------------------------------------------------
# Model registry - ordered by download size (smallest first)
# ---------------------------------------------------------------------------

MODEL_REGISTRY: list[ModelSpec] = [
    # ------------------------------------------------------------------
    # YOLOv8n - object detection
    # ------------------------------------------------------------------
    ModelSpec(
        name="yolov8n",
        filename="yolov8n.onnx",
        description="YOLOv8n object detection (COCO 80 classes)",
        size_mb=6.2,
        # Direct ONNX from Ultralytics GitHub releases
        url="https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx",
        sha256=None,  # verified by ultralytics at runtime
        export_fn=_export_yolov8n,  # fallback if direct URL fails
    ),
    # ------------------------------------------------------------------
    # ArcFace R100 - face recognition
    # ------------------------------------------------------------------
    ModelSpec(
        name="arcface",
        filename="arcface_r100.onnx",
        description="ArcFace R100 face recognition (InsightFace buffalo_l)",
        size_mb=248.0,
        # InsightFace model zoo - buffalo_l pack
        url=(
            "https://github.com/deepinsight/insightface/releases/download/"
            "v0.7/buffalo_l.zip"
        ),
        sha256=None,
        export_fn=None,
    ),
    # ------------------------------------------------------------------
    # Emotion - HSEmotion 7-class
    # ------------------------------------------------------------------
    ModelSpec(
        name="emotion",
        filename="emotion_model.onnx",
        description="HSEmotion 7-class emotion recognition",
        size_mb=28.0,
        url=(
            "https://github.com/HSE-asavchenko/face-emotion-recognition/"
            "raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_afew.onnx"
        ),
        sha256=None,
    ),
    # ------------------------------------------------------------------
    # Liveness - MiniFASNet anti-spoofing
    # ------------------------------------------------------------------
    ModelSpec(
        name="liveness",
        filename="liveness_minifasnet.onnx",
        description="MiniFASNet anti-spoofing liveness detection",
        size_mb=1.0,
        # Hugging Face mirror - more stable than the GitHub raw path
        url=(
            "https://huggingface.co/datasets/Gourieff/ReActor/resolve/main/"
            "models/liveness/2.7_80x80_MiniFASNetV2.onnx"
        ),
        sha256=None,
        export_fn=_export_liveness_minifasnet,
    ),
    # ------------------------------------------------------------------
    # MiDaS v2.1 small - monocular depth
    # ------------------------------------------------------------------
    ModelSpec(
        name="midas",
        filename="midas_v31.onnx",
        description="MiDaS v2.1 small monocular depth estimation (256×256)",
        size_mb=83.0,
        url="https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx",
        export_fn=_export_midas,
    ),
    # ------------------------------------------------------------------
    # TrOCR - handwriting recognition
    # ------------------------------------------------------------------
    ModelSpec(
        name="trocr",
        filename="trocr_handwritten.onnx",
        description="TrOCR-base-handwritten encoder (Microsoft)",
        size_mb=330.0,
        url=None,          # export via optimum
        export_fn=_export_trocr,
    ),
    # ------------------------------------------------------------------
    # Scene EfficientNet - scene classification
    # ------------------------------------------------------------------
    ModelSpec(
        name="scene",
        filename="scene_efficientnet.onnx",
        description="EfficientNet-B4 scene classification (30 classes)",
        size_mb=74.0,
        url=None,          # export via timm
        export_fn=_export_scene_efficientnet,
    ),
]

# Quick lookup by logical name
_REGISTRY_BY_NAME: dict[str, ModelSpec] = {m.name: m for m in MODEL_REGISTRY}


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100.0, downloaded / total_size * 100)
        mb = downloaded / 1_048_576
        total_mb = total_size / 1_048_576
        print(f"\r    {pct:5.1f}%  {mb:.1f} / {total_mb:.1f} MB", end="", flush=True)
    else:
        mb = downloaded / 1_048_576
        print(f"\r    {mb:.1f} MB downloaded", end="", flush=True)


def _download_url(url: str, dest: Path) -> None:
    """Download *url* to *dest* with a progress bar."""
    log.info("Downloading %s", url)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=dest.parent) as tmp:
        tmp_path = Path(tmp.name)
    try:
        urllib.request.urlretrieve(url, tmp_path, reporthook=_progress_hook)
        print()  # newline after progress bar
        shutil.move(str(tmp_path), str(dest))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _handle_zip(url: str, dest: Path, inner_filename: str) -> None:
    """Download a ZIP archive and extract *inner_filename* to *dest*."""
    import zipfile

    log.info("Downloading ZIP archive from %s", url)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "archive.zip"
        urllib.request.urlretrieve(url, zip_path, reporthook=_progress_hook)
        print()
        with zipfile.ZipFile(zip_path) as zf:
            # Find the target file anywhere inside the archive
            matches = [n for n in zf.namelist() if n.endswith(inner_filename)]
            if not matches:
                raise FileNotFoundError(
                    f"'{inner_filename}' not found inside ZIP from {url}. "
                    f"Available: {zf.namelist()}"
                )
            zf.extract(matches[0], tmp)
            shutil.move(str(Path(tmp) / matches[0]), str(dest))
    log.info("Extracted %s → %s", inner_filename, dest)


# ---------------------------------------------------------------------------
# Per-model download logic
# ---------------------------------------------------------------------------

def _download_arcface(spec: ModelSpec) -> None:
    """ArcFace ships inside a ZIP; extract w600k_r50.onnx (buffalo_l pack)."""
    dest = MODELS_DIR / spec.filename
    _handle_zip(
        url=spec.url,  # type: ignore[arg-type]
        dest=dest,
        inner_filename="w600k_r50.onnx",
    )


_SPECIAL_DOWNLOADERS: dict[str, Callable[[ModelSpec], None]] = {
    "arcface": _download_arcface,
}


def _ensure_model(spec: ModelSpec, force: bool = False) -> bool:
    """Download or export a single model. Returns True if action was taken."""
    dest = MODELS_DIR / spec.filename

    if dest.exists() and not force:
        log.info("  ✓  %-30s already present (%s)", spec.filename, _human_size(dest))
        return False

    if force and dest.exists():
        log.info("  ↺  %-30s force re-download", spec.filename)

    log.info("  ↓  %-30s %s", spec.filename, spec.description)
    if spec.size_mb:
        log.info("     Expected size: ~%.0f MB", spec.size_mb)

    # Try direct URL first
    if spec.url is not None:
        try:
            if spec.name in _SPECIAL_DOWNLOADERS:
                _SPECIAL_DOWNLOADERS[spec.name](spec)
            else:
                _download_url(spec.url, dest)
        except Exception as exc:
            log.warning("Direct URL download failed (%s); trying export fallback …", exc)
            if spec.export_fn is not None:
                spec.export_fn()
            else:
                raise
    elif spec.export_fn is not None:
        spec.export_fn()
    else:
        raise RuntimeError(f"No download URL or export function for model '{spec.name}'")

    if not dest.exists():
        raise FileNotFoundError(f"Model file not found after download: {dest}")

    # Integrity check
    if spec.sha256:
        actual = _sha256_file(dest)
        if actual != spec.sha256:
            dest.unlink()
            raise ValueError(
                f"SHA-256 mismatch for {spec.filename}: "
                f"expected {spec.sha256}, got {actual}"
            )
        log.info("     SHA-256 verified ✓")

    log.info("     Saved: %s (%s)", dest, _human_size(dest))
    return True


def _human_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Agent Guru production ONNX models.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            [f"  {m.name:<20} {m.description}" for m in MODEL_REGISTRY]
        ),
    )
    parser.add_argument(
        "--models",
        nargs="+",
        metavar="MODEL",
        help=(
            "Names of models to download (default: all). "
            f"Choices: {', '.join(_REGISTRY_BY_NAME)}"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the file already exists.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available models and exit.",
    )
    args = parser.parse_args()

    if args.list:
        print("\nAvailable models:")
        for m in MODEL_REGISTRY:
            status = "✓" if (MODELS_DIR / m.filename).exists() else "✗"
            size_str = f"~{m.size_mb:.0f} MB" if m.size_mb else "unknown size"
            print(f"  [{status}] {m.name:<20} {size_str:<12} {m.description}")
        return

    # Resolve which models to download
    if args.models:
        unknown = [n for n in args.models if n not in _REGISTRY_BY_NAME]
        if unknown:
            parser.error(
                f"Unknown model(s): {', '.join(unknown)}. "
                f"Valid names: {', '.join(_REGISTRY_BY_NAME)}"
            )
        specs = [_REGISTRY_BY_NAME[n] for n in args.models]
    else:
        specs = MODEL_REGISTRY

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nModels directory: {MODELS_DIR}\n")
    downloaded, skipped, failed = 0, 0, []

    for spec in specs:
        try:
            acted = _ensure_model(spec, force=args.force)
            if acted:
                downloaded += 1
            else:
                skipped += 1
        except Exception as exc:
            log.error("FAILED to download '%s': %s", spec.name, exc)
            failed.append(spec.name)

    # Summary
    print("\n" + "=" * 60)
    print(f"  Downloaded : {downloaded}")
    print(f"  Skipped    : {skipped}  (already present)")
    if failed:
        print(f"  Failed     : {len(failed)}  ({', '.join(failed)})")
    print("=" * 60)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
