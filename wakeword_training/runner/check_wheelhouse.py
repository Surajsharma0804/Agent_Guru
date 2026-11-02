r"""Ask pip's own resolver, offline, whether a wheelhouse set installs on Linux / CPython 3.13.

    venv-313\Scripts\python.exe runner\check_wheelhouse.py <data root> [linux|linux-cu118]

build_wheelhouse.py computes the closure itself; this is the independent check, and it is
what install_linux.sh will do on the cluster with no network. pip running here evaluates
environment markers for Windows, so its dry run first asked for colorama (tqdm needs it on
Windows only) and reported a conflict that cannot happen on Linux. pip's vendored packaging
is pointed at a Linux marker environment before pip starts, so the resolution is the one
the cluster will compute.
"""
import sys
from pathlib import Path

from pip._vendor.packaging import markers

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_wheelhouse import LINUX, PLAT  # noqa: E402

markers.default_environment = lambda: dict(LINUX)

root, tag = Path(sys.argv[1]), (sys.argv[2] if len(sys.argv) > 2 else "linux")
env = root / "env"
if tag == "linux":
    # Exactly install_linux.sh's request, with no constraints file: it installs without one, so a
    # check that pinned versions through constraints.txt could pass while the install did not.
    reqs = ["torch==2.11.0+cu126", "torchaudio==2.11.0+cu126", "-r", str(env / "requirements-linux.txt")]
    links = ["--find-links", str(env / "wheels" / "linux")]
else:
    # install_linux.sh's fallback: torch from the CUDA 11.8 folder, everything else from linux.
    reqs = ["torch==2.7.1+cu118", "torchaudio==2.7.1+cu118", "-r", str(env / "requirements-linux.txt")]
    links = ["--find-links", str(env / "wheels" / "linux-cu118"), "--find-links", str(env / "wheels" / "linux")]
target = root.parent / f"{root.name}_pipcheck_unused"
sys.argv = ["pip", "install", "--dry-run", "--no-index", *links, "--only-binary=:all:", *PLAT,
            "--target", str(target), "--report", "-", "--quiet", *reqs]
from pip._internal.cli.main import main  # noqa: E402

code = main()
print(f"\n{tag}: pip resolution {'OK' if code == 0 else 'FAILED'}", file=sys.stderr)
sys.exit(code)
