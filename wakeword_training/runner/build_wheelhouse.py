"""Build the offline Linux wheelhouse: every package the runner needs, for CPython 3.13 on x86-64 Linux.

    venv-313\\Scripts\\python.exe runner\\build_wheelhouse.py <data root>

Writes <data root>/env/wheels/linux (torch 2.11.0+cu126 and everything else) and
<data root>/env/wheels/linux-cu118 (torch 2.7.1+cu118 and its CUDA libraries, for a driver
too old for CUDA 12), plus env/requirements-linux.txt and env/constraints.txt.

pip cannot be trusted to resolve for another platform: it evaluates environment markers
such as platform_system == "Linux" against the machine running pip. Run from Windows with
--platform manylinux, it fetched torch but skipped every nvidia-* CUDA library and triton
(the first attempt's torch folder was 804 MB; on the cluster torch would have imported and
then failed to find cuDNN). So every wheel is fetched with --no-deps and the dependency
closure is computed here: each wheel's own Requires-Dist, markers evaluated for Linux /
CPython 3.13, until nothing is missing. Packages published only as source (acoustics and
others found on the way) are pure Python and are built into wheels here.
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename

# Every manylinux tag up to glibc 2.28, the documented minimum for the cluster: wheels carry whichever
# tag they were built for (nvidia-nccl-cu12 is manylinux_2_18), and a short list of tags missed some.
PLAT = [a for t in [f"manylinux_2_{i}_x86_64" for i in range(5, 29)]
        + ["manylinux1_x86_64", "manylinux2010_x86_64", "manylinux2014_x86_64", "linux_x86_64", "any"]
        for a in ("--platform", t)] + ["--python-version", "3.13", "--implementation", "cp",
                                     "--abi", "cp313", "--abi", "abi3", "--abi", "none"]
LINUX = {"python_version": "3.13", "python_full_version": "3.13.16", "os_name": "posix", "sys_platform": "linux",
         "platform_system": "Linux", "platform_machine": "x86_64", "platform_python_implementation": "CPython",
         "implementation_name": "cpython", "platform_release": "", "platform_version": "", "implementation_version": "3.13.16"}
GIT = {"parler-tts": "git+https://github.com/huggingface/parler-tts.git@d108732cd57788ec86bc857d99a6cabd66663d68",
       "descript-audiotools": "git+https://github.com/descriptinc/audiotools@348ebf2034ce24e2a91a553e3171cb00c0c71678"}
TOP = """numpy scipy soundfile pyarrow huggingface_hub pyyaml psutil tqdm requests scikit-learn onnxruntime==1.30.0
onnx==1.22.0 piper-phonemize-fix==1.2.2 webrtcvad-wheels piper-tts==1.8.0 faster-whisper==1.2.1 mutagen==1.47.0
torchinfo==1.8.0 torchmetrics==1.2.0 speechbrain==0.5.14 audiomentations==0.33.0 torch-audiomentations==0.11.0
acoustics==0.2.6 pronouncing==0.2.0 transformers==4.46.1 protobuf==4.25.9 sentencepiece descript-audio-codec==1.0.0
parler-tts descript-audiotools packaging""".split()
TORCH = {"linux": ("cu126", "2.11.0"), "linux-cu118": ("cu118", "2.7.1")}


def pip(*args):
    # A time limit on every call: one step once hung for the whole hour (see fetch).
    try:
        return subprocess.run([sys.executable, "-m", "pip", *args], capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", f"pip {' '.join(args[:2])} timed out after 3600 s")


def requires(wheel, extras=()):
    """Requirements of a wheel that apply on Linux / CPython 3.13 with the given extras requested.

    Extras count: torch 2.11 asks for cuda-toolkit[cublas,cudart,cufft,...], and cuda-toolkit
    lists each CUDA library only under its extra. Evaluated with no extras, the first complete
    build left cufft, curand, cusolver, cusparse, the CUDA runtime and five more out of the
    wheelhouse, and an offline install on the cluster would have stopped on the first of them.
    """
    with zipfile.ZipFile(wheel) as z:
        meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        lines = z.read(meta).decode("utf-8", "replace").splitlines()
    out = []
    for ln in lines:
        if not ln.startswith("Requires-Dist:"):
            continue
        r = Requirement(ln.split(":", 1)[1].strip())
        if r.marker is None or any(r.marker.evaluate({**LINUX, "extra": e}) for e in ("", *extras)):
            out.append(r)
    return out


def have(folder):
    return {canonicalize_name(parse_wheel_filename(p.name)[0]): p for p in Path(folder).glob("*.whl")}


def fetch(spec, out, built, pins, index=None):
    """Download one requirement as a Linux wheel, building it here if it is source-only."""
    name = canonicalize_name(re.split(r"[<>=!~ \[@]", spec)[0])
    pinned = pins.get(name, spec) if not re.search(r"[<>=!~]", spec) else spec
    already = have(built)
    if name in already:          # built in an earlier round or set: just copy it here
        w = already[name]
        (Path(out) / w.name).write_bytes(w.read_bytes())
        return
    if name in GIT:
        r = pip("wheel", "--no-deps", "-q", "-w", str(built), f"{name} @ {GIT[name]}")
    else:
        extra = ["--index-url", index, "--extra-index-url", "https://pypi.org/simple"] if index else []
        r = pip("download", "--no-deps", "-q", "--only-binary=:all:", *PLAT, *extra, "-d", str(out), pinned)
        # NVIDIA's libraries always ship wheels; their only source package on PyPI is a 0.0.1
        # placeholder whose build reaches out to NVIDIA's servers and hung the first build for an
        # hour. A missing NVIDIA wheel is an error to see, never something to build.
        if r.returncode and not name.startswith("nvidia-") and name != "triton":
            print(f"  {pinned}: no Linux wheel, building one (pure Python)")
            r = pip("wheel", "--no-deps", "-q", "-w", str(built), pinned)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"could not get {pinned}")
    # Copy only the wheel this call built: copying every built wheel put parler-tts and its
    # whole dependency tree into the torch-only CUDA 11.8 folder.
    new = have(built).get(name)
    if new is not None and not (Path(out) / new.name).exists():
        (Path(out) / new.name).write_bytes(new.read_bytes())


def closure(out, built, pins, top, index=None):
    """Fetch top and everything it needs until every requirement is met by a wheel in out.

    Every present wheel is checked against all the version specifiers that apply to it, not
    only fetched when absent: the first build kept nvidia-cublas-cu12 12.9 and
    nvidia-cuda-nvrtc-cu12 12.9 (pulled in unversioned by another package) next to
    cuda-toolkit 12.6.3, which pins 12.6.4.1.* and 12.6.85.*, a set pip refuses to install.
    """
    extras, seen = {}, {}
    # Drop every wheel that differs from its pin before reading anyone's requirements: a stale
    # tensorboard 2.21 left from an unpinned build still demanded protobuf>=6.31.1 while
    # protobuf was being resolved, and the closure asked for an impossible protobuf.
    for n, w in have(out).items():
        if n in pins and str(parse_wheel_filename(w.name)[1]).split("+")[0] != pins[n].split("==", 1)[1].split("+")[0]:
            print(f"  {w.name} is not the pinned {pins[n]}; removing it")
            w.unlink()
    for spec in top:
        if "@" not in spec:
            r = Requirement(spec)
            extras.setdefault(canonicalize_name(r.name), set()).update(r.extras)
        if canonicalize_name(re.split(r"[<>=!~ \[@]", spec)[0]) not in have(out):
            fetch(spec, out, built, pins, index)
    for _ in range(50):
        present = have(out)
        wanted = {}
        for n_w, w in present.items():
            for r in requires(w, sorted(extras.get(n_w, ()))):
                n = canonicalize_name(r.name)
                wanted.setdefault(n, SpecifierSet())
                wanted[n] &= r.specifier
                extras.setdefault(n, set()).update(r.extras)
        changed = False
        for n, spec in sorted(wanted.items()):
            pin = pins.get(n)
            if n in present:
                version = parse_wheel_filename(present[n].name)[1]
                pinned_ok = not pin or str(version).split("+")[0] == pin.split("==", 1)[1].split("+")[0]
                if spec.contains(version, prereleases=True) and pinned_ok:
                    continue
                print(f"  {present[n].name} does not satisfy {n}{spec} {pin or ''}; replacing it")
                present[n].unlink()
            if pin and spec.contains(pin.split("==", 1)[1], prereleases=True):
                fetch(pin, out, built, pins, index)
            else:
                fetch(f"{n}{spec}" if str(spec) else n, out, built, pins, index)
            changed = True
        # A newly requested extra changes what an already present wheel requires: go round again.
        if not changed and extras == seen:
            return
        seen = {n: set(e) for n, e in extras.items()}
    raise SystemExit("dependency closure did not converge")


def _fits_linux_313(wheel):
    """Whether CPython 3.13 on x86_64 Linux can install this wheel.

    The first version matched "-cp312-" in the name and rejected seven good wheels (av, onnx,
    protobuf, safetensors and others): they are abi3 builds, where cp312 is the oldest Python
    they support, not the only one. The build had finished downloading and failed on this check.
    """
    from packaging.utils import parse_wheel_filename
    for t in parse_wheel_filename(wheel)[3]:
        if not (t.platform == "any" or (t.platform.startswith("manylinux") and t.platform.endswith("x86_64"))):
            continue
        if t.interpreter == "cp313" or t.interpreter in ("py3", "py2.py3") and t.abi == "none":
            return True
        m = re.fullmatch(r"cp3(\d+)", t.interpreter)
        if t.abi == "abi3" and m and int(m.group(1)) <= 13:
            return True
    return False


def main():
    root = Path(sys.argv[1])
    env = root / "env"
    built = env / "wheels" / "built"
    built.mkdir(parents=True, exist_ok=True)
    freeze = pip("freeze").stdout.splitlines()
    # The pins are the versions this interpreter has, so it must be the one the runner was tested
    # in. Run once from venv-oww (no torch, no parler-tts), nothing was pinned and pip took the
    # newest of everything: librosa 1.0.0 against audiomentations' <0.11, and tensorboard 2.21,
    # whose protobuf>=6.31.1 cannot coexist with descript-audiotools' protobuf<5.
    missing = [p for p in ("torch==", "parler_tts", "descript-audiotools", "librosa==", "protobuf==")
               if not any(ln.lower().startswith(p.lower()) for ln in freeze)]
    if missing:
        raise SystemExit(f"run this with the runner's own environment (venv-313); {sys.executable} lacks {missing}")
    cons = [ln.replace("+cu128", "") for ln in freeze if "==" in ln and "@" not in ln]
    pins = {canonicalize_name(c.split("==")[0]): c for c in cons if not c.startswith(("torch==", "torchaudio=="))}
    (env / "constraints.txt").write_text("\n".join(cons) + "\n", encoding="utf-8")
    (env / "requirements-linux.txt").write_text("\n".join(TOP) + "\n", encoding="utf-8")
    # The linux folder holds torch and everything else, so even its torch-only pass needs the
    # full pins: with none, that pass judged a stale tensorboard 2.21 acceptable and resolved
    # protobuf against it. The CUDA 11.8 folder holds torch alone and pins nothing.
    pins.update({"torch": "torch==2.11.0+cu126", "torchaudio": "torchaudio==2.11.0+cu126"})
    for tag, (cuda, ver) in TORCH.items():
        out = env / "wheels" / tag
        out.mkdir(parents=True, exist_ok=True)
        print(f"{tag}: torch {ver}+{cuda} with its Linux dependency closure")
        closure(out, built, pins if tag == "linux" else {}, [f"torch=={ver}+{cuda}", f"torchaudio=={ver}+{cuda}"],
                index=f"https://download.pytorch.org/whl/{cuda}")
    print("linux: everything else")
    closure(env / "wheels" / "linux", built, pins, TOP, index="https://download.pytorch.org/whl/cu126")
    for tag in TORCH:
        wheels = sorted(p.name for p in (env / "wheels" / tag).glob("*.whl"))
        bad = [w for w in wheels if not _fits_linux_313(w)]
        assert not bad, f"{tag}: non-Linux or non-3.13 wheels: {bad}"
        size = sum(p.stat().st_size for p in (env / "wheels" / tag).glob("*.whl"))
        nvidia = [w for w in wheels if w.startswith("nvidia_")]
        print(f"{tag}: {len(wheels)} wheels, {size / 2**30:.2f} GiB, {len(nvidia)} nvidia CUDA libraries")


if __name__ == "__main__":
    main()
