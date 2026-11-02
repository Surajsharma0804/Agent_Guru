#!/usr/bin/env bash
# Install the runner's Python environment on Linux: no root, no network, nothing from the cluster's Python.
#
#   bash $DATA/code/install_linux.sh <env dir>                 # torch 2.11.0, CUDA 12.6: driver >= 525.60
#   TORCH_SET=linux-cu118 bash $DATA/code/install_linux.sh <env dir>   # torch 2.7.1, CUDA 11.8: driver >= 450.80
#
# Unpacks the standalone CPython 3.13 shipped in the data folder, makes a venv from it, and
# installs only from the folder's wheels. torch's CUDA libraries are pip wheels, so the node
# needs only an NVIDIA driver, not a CUDA toolkit or a matching module. Needs glibc >= 2.28
# (RHEL/Rocky 8+, Ubuntu 20.04+): check with `ldd --version`.
set -euo pipefail
DATA="$(cd "$(dirname "$0")/.." && pwd)"
ENVDIR="${1:?usage: install_linux.sh <env dir>}"
SET="${TORCH_SET:-linux}"
mkdir -p "$ENVDIR"
TARBALL=$(ls "$DATA"/env/python/cpython-3.13*-x86_64-unknown-linux-gnu-install_only.tar.gz)
echo "python: $TARBALL"
tar -xzf "$TARBALL" -C "$ENVDIR"
"$ENVDIR/python/bin/python3" -m venv "$ENVDIR/venv"
PY="$ENVDIR/venv/bin/python"
if [ "$SET" = "linux-cu118" ]; then
  "$PY" -m pip install --no-index --find-links "$DATA/env/wheels/linux-cu118" "torch==2.7.1+cu118" "torchaudio==2.7.1+cu118"
  "$PY" -m pip install --no-index --find-links "$DATA/env/wheels/linux" --find-links "$DATA/env/wheels/linux-cu118" \
      -r "$DATA/env/requirements-linux.txt"
else
  "$PY" -m pip install --no-index --find-links "$DATA/env/wheels/linux" "torch==2.11.0+cu126" "torchaudio==2.11.0+cu126" \
      -r "$DATA/env/requirements-linux.txt"
fi
"$PY" - <<'EOF'
import sys, torch
print("python", sys.version.split()[0], "| torch", torch.__version__, "| CUDA available", torch.cuda.is_available())
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"GPU {p.name}, {p.total_memory / 2**30:.0f} GiB, compute capability {p.major}.{p.minor}, CUDA runtime {torch.version.cuda}")
    x = torch.randn(1024, 1024, device="cuda", dtype=torch.bfloat16 if p.major >= 8 else torch.float16)
    print("GPU matmul ok:", float((x @ x).float().abs().mean()) > 0)
else:
    print("NO GPU VISIBLE: check `nvidia-smi`; on a cluster, run this inside a GPU job (srun --gres=gpu:1 ...)")
    sys.exit(1)
EOF
echo "installed: $PY"
