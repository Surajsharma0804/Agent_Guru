r"""Fill the portable data folder with every input the run needs, then write its manifest.

    venv-313\Scripts\python.exe runner\prepare.py --data E:\agent_guru_wakeword_data [--hf-home E:\hf_home]

Run it on this PC, with internet. Afterwards the folder holds everything (models, datasets,
features, source code at pinned commits, the user's recordings, the benchmark, the Linux
wheels and a standalone Python), with paths only relative to its root, so it can be copied
to the cluster as one unit and run there with no network at all. Rerunning is cheap: files
already present at the right size are kept, so after recording new takes a rerun refreshes
the recordings and the manifest.

Hugging Face files are fetched through the E: cache and hard-linked into the folder (same
drive, no second copy on disk); copying the folder anywhere copies real files.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402

PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20261001/"
              "cpython-3.13.16+20261001-x86_64-unknown-linux-gnu-install_only.tar.gz")
PSG_MODEL_URL = "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
PSG_MODEL_BYTES = 204089915
OWW_MODELS_URL = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"
BENCH_FILES = ["wake_pos.npy", "wake_pos_spans.json", "wake_heldout.npy", "wake_heldout_spans.json", "wake_neg.npy",
               "hindi_pos.npy", "hindi_pos_spans.json", "bare_pos.npy", "bare_pos_spans.json", "bench_extra_tx.json"]


def say(msg):
    print(f"{datetime.datetime.now():%H:%M:%S}  {msg}", flush=True)


def place(src, dest):
    """Hard-link src at dest (same drive), else copy; keep an existing dest of the same size."""
    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        return
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def download(url, dest, size=None):
    dest = Path(dest)
    if dest.exists() and (size is None or dest.stat().st_size == size):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    say(f"downloading {url.rsplit('/', 1)[1]}")
    urllib.request.urlretrieve(url, tmp)
    if size is not None and tmp.stat().st_size != size:
        raise SystemExit(f"{url}: {tmp.stat().st_size} bytes, expected {size}")
    os.replace(tmp, dest)


def hf_file(repo, filename, dest, repo_type="model"):
    from huggingface_hub import hf_hub_download
    place(hf_hub_download(repo, filename, repo_type=repo_type), dest)


def hf_tree(repo, dest, allow=None, repo_type="model"):
    from huggingface_hub import snapshot_download
    root = Path(snapshot_download(repo, repo_type=repo_type, allow_patterns=allow))
    for f in root.rglob("*"):
        if f.is_file():
            place(f, Path(dest) / f.relative_to(root))


def git_tree(url, ref, dest, work):
    """The files of url at ref, no .git: what the runner copies and patches at run time."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        return
    clone = Path(work) / Path(url).name
    if not (clone / ".git").exists():
        subprocess.run(["git", "clone", "-q", url, str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "fetch", "-q", "--tags"], check=True)
    tar = Path(work) / f"{Path(url).name}.tar"
    subprocess.run(["git", "-C", str(clone), "archive", "--format=tar", "-o", str(tar), ref], check=True)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar) as t:
        t.extractall(dest, filter="data")
    tar.unlink()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(data):
    files = sorted(p for p in data.rglob("*") if p.is_file() and p.name != L.MANIFEST.name
                   and not p.name.endswith((".part", ".tmp")))
    say(f"hashing {len(files)} files ({sum(p.stat().st_size for p in files) / 2**30:.1f} GiB)")
    with cf.ThreadPoolExecutor(8) as ex:
        digests = list(ex.map(sha256, files))
    entries = {p.relative_to(data).as_posix(): {"bytes": p.stat().st_size, "sha256": d} for p, d in zip(files, digests)}
    manifest = {"created": datetime.datetime.now().isoformat(timespec="seconds"), "files": entries,
                "total_bytes": sum(e["bytes"] for e in entries.values()),
                "openwakeword_commit": L.OWW_COMMIT, "piper_sample_generator_tag": L.PSG_TAG}
    tmp = data / (L.MANIFEST.name + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    os.replace(tmp, data / L.MANIFEST)
    say(f"manifest: {len(entries)} files, {manifest['total_bytes'] / 2**30:.2f} GiB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=r"E:\agent_guru_wakeword_data")
    ap.add_argument("--hf-home", default=r"E:\hf_home")
    ap.add_argument("--skip-wheels", action="store_true", help="the wheelhouse is built separately (build_wheelhouse.py)")
    a = ap.parse_args()
    os.environ["HF_HOME"] = a.hf_home
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    data = Path(a.data)
    work = data.parent / (data.name + "_prepare_tmp")
    work.mkdir(parents=True, exist_ok=True)

    say("features (the 17.3 GB file resumes if interrupted)")
    hf_file("davidscripka/openwakeword_features", "openwakeword_features_ACAV100M_2000_hrs_16bit.npy", data / L.ACAV, "dataset")
    hf_file("davidscripka/openwakeword_features", "validation_set_features.npy", data / L.VALIDATION, "dataset")
    say("background audio, room impulse responses, Svarah")
    hf_file("agkphysics/AudioSet", "data/bal_train/09.parquet", data / L.AUDIOSET, "dataset")
    hf_file("agkphysics/AudioSet", "data/bal_train/00.parquet", data / L.AUDIOSET_EXTRA, "dataset")
    hf_file("rpmon/fma-genre-classification", "data/train-00000-of-00013.parquet", data / L.FMA, "dataset")
    from huggingface_hub import snapshot_download
    rir_root = Path(snapshot_download("davidscripka/MIT_environmental_impulse_responses", repo_type="dataset",
                                      allow_patterns="16khz/*.wav"))
    for f in sorted((rir_root / "16khz").glob("*.wav")):
        place(f, data / L.RIRS / f.name)
    for i, dest in enumerate(L.SVARAH):
        hf_file("ai4bharat/Svarah", f"data/test-0000{i}-of-00003.parquet", data / dest, "dataset")
    say("models")
    hf_tree("ai4bharat/indic-parler-tts", data / L.PARLER)
    hf_tree("google/flan-t5-large", data / L.FLAN_T5,
            allow=["config.json", "spiece.model", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"])
    hf_tree("Systran/faster-whisper-medium", data / L.WHISPER)
    piper_paths = {"pratham": "hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
                   "priyamvada": "hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx"}
    for name, path in piper_paths.items():
        hf_file("rhasspy/piper-voices", path, data / L.PIPER[name])
        hf_file("rhasspy/piper-voices", path + ".json", Path(str(data / L.PIPER[name]) + ".json"))
    download(PSG_MODEL_URL, data / L.LIBRITTS, PSG_MODEL_BYTES)
    for f, dest in L.OWW_MODELS.items():
        download(OWW_MODELS_URL + f, data / dest)
    say("source at pinned commits")
    git_tree(L.OWW_URL, L.OWW_COMMIT, data / L.OWW_SRC, work)
    git_tree(L.PSG_COMMIT_URL, L.PSG_TAG, data / L.PSG_SRC, work)
    say("recordings and benchmark")
    rec = REPO / "recordings_upload.zip"
    (data / L.RECORDINGS).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rec, data / L.RECORDINGS)          # copied, not linked: it changes when the user re-packs
    for f in BENCH_FILES:
        place(REPO / "bench" / f, data / L.BENCH / f)
    say("standalone Python for Linux")
    download(PYTHON_URL, data / L.PYTHON_LINUX / PYTHON_URL.rsplit("/", 1)[1])
    if not a.skip_wheels:
        subprocess.run([sys.executable, str(HERE / "build_wheelhouse.py"), str(data)], check=True)
    # Checked even with --skip-wheels: the first wheelhouse to finish was missing ten CUDA
    # libraries and still reported success, and only pip's resolver showed it.
    for tag in ("linux", "linux-cu118"):
        if (data / "env" / "wheels" / tag).is_dir():
            say(f"pip resolution check, {tag}")
            subprocess.run([sys.executable, str(HERE / "check_wheelhouse.py"), str(data), tag], check=True,
                           stdout=subprocess.DEVNULL)
    say("runner code snapshot")
    code = data / L.CODE
    shutil.rmtree(code, ignore_errors=True)
    code.mkdir(parents=True)
    for f in [*HERE.glob("*.py"), *HERE.glob("*.sh"), *HERE.glob("*.md")]:
        shutil.copy2(f, code / f.name)
    shutil.copy2(REPO / "notebook" / "colab313_compat.py", code / "colab313_compat.py")
    shutil.rmtree(work, ignore_errors=True)
    write_manifest(data)


if __name__ == "__main__":
    main()
