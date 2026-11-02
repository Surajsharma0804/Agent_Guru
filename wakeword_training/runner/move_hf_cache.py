r"""Move the wake-word repos from the C: Hugging Face cache to E:\hf_home, once.

    python runner/move_hf_cache.py

Agent Guru itself loads faster-whisper and sentence-transformers from the C: cache, so those
stay where they are (faster-whisper-medium is copied, the runner's quality check uses it).
Each repo is copied, its file count and total size compared, and only then removed from C:.
The login token is copied so gated repos (Svarah, Indic Parler-TTS) still resolve under E:.
"""
import shutil
from pathlib import Path

SRC = Path.home() / ".cache" / "huggingface"
DST = Path(r"E:\hf_home")
MOVE = ["models--ai4bharat--indic-parler-tts", "datasets--ai4bharat--Svarah", "datasets--agkphysics--AudioSet",
        "datasets--rpmon--fma-genre-classification", "models--rhasspy--piper-voices",
        "datasets--davidscripka--MIT_environmental_impulse_responses", "models--google--flan-t5-large"]
COPY = ["models--Systran--faster-whisper-medium"]


def tally(d):
    files = [p for p in Path(d).rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


(DST / "hub").mkdir(parents=True, exist_ok=True)
for name in ("token", "stored_tokens"):
    if (SRC / name).exists():
        shutil.copy2(SRC / name, DST / name)
for repo in MOVE + COPY:
    s, d = SRC / "hub" / repo, DST / "hub" / repo
    if not s.exists():
        print(f"{repo}: not on C:, {'already on E:' if d.exists() else 'MISSING'}")
        continue
    shutil.copytree(s, d, dirs_exist_ok=True)
    if tally(s) != tally(d):
        raise SystemExit(f"{repo}: copy differs {tally(s)} vs {tally(d)}; C: copy left in place")
    n, size = tally(d)
    if repo in MOVE:
        shutil.rmtree(s)
    print(f"{repo}: {n} files, {size / 2**30:.2f} GiB {'moved' if repo in MOVE else 'copied'} to E:")
