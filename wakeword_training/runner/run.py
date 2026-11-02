r"""Train Agent Guru's wake-word models from the portable data folder, offline, resumable, then benchmark them.

    python run.py --data <data folder> --work <work folder> [--models hey|bare] [--scale 0.01]

  Windows laptop:  venv-313\Scripts\python.exe E:\agent_guru_wakeword_data\code\run.py --data E:\agent_guru_wakeword_data --work E:\agent_guru_wakeword_work
  Linux / A100:    $VENV/bin/python $DATA/code/run.py --data $DATA --work $WORK
  Dry run (1%):    add --scale 0.01 (and use a separate --work folder)

Rerun the same command after a crash, a reboot, Ctrl+C or a scheduler timeout: finished
stages are skipped (markers in <work>/state), generation skips every clip already on disk,
each train.py step clears its own partial output before rerunning. The run is not finished
until the benchmark has scored the models and <work>/out/REPORT.md is written.

No network is used: Hugging Face's offline mode is forced on and its cache is pointed at an
empty folder, so a missing input fails loudly here instead of being fetched quietly.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import io
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

CODE = Path(__file__).resolve().parent
# The compatibility module sits next to run.py in a data folder, and in notebook/ in the repo.
COMPAT = CODE if (CODE / "colab313_compat.py").exists() else CODE.parent / "notebook"
sys.path[:0] = [str(CODE), str(COMPAT)]
import layout as L  # noqa: E402

# ---- what is trained ----------------------------------------------------------------------
N_SAMPLES, N_SAMPLES_VAL, STEPS = 10000, 2000, 50000
SHARE_PARLER_EN, SHARE_HINDI, SHARE_REAL = 0.40, 0.15, 0.05      # the rest: LibriTTS-R top-up by train.py
MAX_REPEATS = 40
SVARAH_BENCH_FRACTION, SVARAH_CLIP_S = 0.30, 2.0
PARLER_EN_SPEAKERS = ["Thoma", "Mary", "Swapna", "Dinesh", "Meera", "Jatin", "Aakash", "Sneha", "Kabir",
                      "Tisha", "Chingkhei", "Thoiba", "Priya", "Tarun", "Gauri", "Nisha", "Raghav",
                      "Kavya", "Ravi", "Vikas", "Riya"]
PARLER_HI_SPEAKERS = ["Rohit", "Divya"]
# Hindi texts are plain, without a comma: "हे, गुरु" cut empty generations in fp16 but put a
# pause of 150 ms or more between the words in 11-21% of its clips, and a model trained on a
# pause would miss the phrase said as one word. English keeps "Hey, Guru!" and "Hey, Maya!" as
# rhythm variation (about 21% of their clips pause); the report carries each text's pauses.
MODELS = {
    "hey": {
        # "ji" after the name is a wake (owner's decision, round 6): the round-5 models woke on 12 of
        # 12 plain synthetic clips but 10 of 18 with "ji", so "... ji" joins the Piper top-up phrases.
        # The other assistants' wake phrases are negatives: "Hey Google" and "Hey Mario" woke the
        # round-5 models on the owner's own recorded negatives.
        "hey_guru": {"english": ["Hey Guru.", "Hey, Guru!", "Hey Guru"], "hindi": ["हे गुरु", "हे गुरू"],
                     "topup": ["hey guru", "hey guru ji"],
                     "negative": ["hey maya", "hey google", "hey gary", "hey you", "thank you", "take your room",
                                  "hey girl", "hey group", "hey guys", "my guru told me", "the gurudwara", "hey jeru",
                                  "hey siri", "hey alexa", "hey mario", "hey gurukul", "ok google"]},
        "hey_maya": {"english": ["Hey Maya.", "Hey, Maya!", "Hey Maya"], "hindi": ["हे माया", "हेय माया"],
                     "topup": ["hey maya", "hey maya ji"],
                     "negative": ["hey guru", "hey mario", "oh my god", "hey my dear", "hey mayor", "hey mama",
                                  "may i", "maya is here", "hey mira", "my way", "hey myra", "hey maria",
                                  "hey google", "hey siri", "hey alexa", "hey mayank", "ok google"]}},
    "bare": {
        "guru": {"english": ["Guru.", "Guru!", "Guru"], "hindi": ["गुरु", "गुरू"],
                 "negative": ["maya", "google", "group", "gurgaon", "kuru", "garu", "grew", "jeru",
                              "the gurudwara", "who are you", "through", "gru"]},
        "maya": {"english": ["Maya.", "Maya!", "Maya"], "hindi": ["माया"],
                 "negative": ["guru", "mayank", "mayor", "my", "mama", "maria", "mira", "myra",
                              "may i", "my ya", "malaya", "amaya"]}},
}
LOG = None


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def run_checked(cmd, label, **kw):
    """Run cmd with stdout and stderr shown and logged as they arrive; on failure repeat the tail and raise."""
    tail = collections.deque(maxlen=200)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", bufsize=1, **kw)
    with open(LOG, "a", encoding="utf-8") as f:
        for line in p.stdout:
            print(line, end="", flush=True)
            f.write(line)
            # Flushed per line: buffered, train.py's progress reached run.log in 8 KB chunks, so
            # `tail -f run.log` lagged by minutes and the kill test fired on stale positions.
            f.flush()
            tail.append(line)
    if p.wait() != 0:
        log(f"----- {label} failed with exit status {p.returncode}. Its last {len(tail)} lines: -----")
        print("".join(tail), end="")
        raise RuntimeError(f"{label} failed with exit status {p.returncode}; output above and in {LOG}")


class State:
    def __init__(self, work):
        self.dir = work / "state"
        self.dir.mkdir(parents=True, exist_ok=True)

    def done(self, name):
        return (self.dir / f"{name}.done").exists()

    def mark(self, name, info=None):
        atomic(self.dir / f"{name}.done", json.dumps(info or {}, ensure_ascii=False, indent=1))

    def info(self, name):
        p = self.dir / f"{name}.done"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def load(self, name, default):
        p = self.dir / f"{name}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def save(self, name, obj):
        atomic(self.dir / f"{name}.json", json.dumps(obj, ensure_ascii=False, indent=1))

    def add_time(self, key, seconds):
        t = self.load("timings", {})
        t[key] = round(t.get(key, 0) + seconds)
        self.save("timings", t)


def atomic(path, text):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def patch(path, old, new, why):
    """Replace old with new exactly once; a rerun on an already-patched file is a no-op."""
    src = Path(path).read_text(encoding="utf-8")
    if src.count(old) == 1:
        Path(path).write_text(src.replace(old, new), encoding="utf-8")
        log(f"patched {Path(path).name}: {why}")
    elif src.count(old) == 0 and src.count(new) >= 1:
        log(f"already patched {Path(path).name}: {why}")
    else:
        raise RuntimeError(f"{path} changed upstream ({src.count(old)} matches): re-check the patch: {why}")


def heard_name(text, name):
    import re

    def lev(a, b):
        d = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            p, d[0] = d[0], i
            for j, cb in enumerate(b, 1):
                p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
        return d[-1]
    words = re.sub(r"[^a-z\u0900-\u097f]+", " ", text.lower()).split()
    dev = {"guru": ("गुरु", "गुरू"), "maya": ("माया",)}[name]
    return any(lev(w, name) <= 1 or w in dev for w in words)


# ---- stages ---------------------------------------------------------------------------------

def stage_setup(data, work, cfg, env):
    """Working copies of the pinned source trees, patched; the checks that fail fast."""
    src = work / "src"
    oww, psg = src / "openwakeword", src / "piper-sample-generator"
    for s, d in ((data / L.OWW_SRC, oww), (data / L.PSG_SRC, psg)):
        if not d.exists():
            shutil.copytree(s, d)
    (psg / "models").mkdir(exist_ok=True)
    if not (psg / "models" / "en_US-libritts_r-medium.pt").exists():
        shutil.copy2(data / L.LIBRITTS, psg / "models" / "en_US-libritts_r-medium.pt")
    res = oww / "openwakeword" / "resources" / "models"
    res.mkdir(parents=True, exist_ok=True)
    for f, rel in L.OWW_MODELS.items():
        shutil.copy2(data / rel, res / f)
    tp, dp, up = (oww / "openwakeword" / n for n in ("train.py", "data.py", "utils.py"))
    patch(tp, '"--convert_to_tflite",\n        help="Convert the trained ONNX model to TFLite format",\n'
              '        action="store_true",\n        default="False",',
          '"--convert_to_tflite",\n        help="Convert the trained ONNX model to TFLite format",\n'
          '        action="store_true",\n        default=False,',
          '--convert_to_tflite defaulted to the truthy string "False", so every run attempted the TensorFlow export')
    # train.py wraps one generator in an IterableDataset with num_workers = cpu_count // 2. Each
    # worker gets its own copy of that generator, so with 16 workers on a 32-core node every
    # batch arrived 16 times and 50,000 steps saw about 3,100 distinct batches. Windows cannot
    # start such workers at all (spawn cannot pickle the dataset): 0 there. Linux: exactly 1,
    # which overlaps loading with training and gives Colab's batch order (2 vCPUs -> 1 worker).
    old = "batch_size=None, num_workers=n_cpus, prefetch_factor=16)"
    if platform.system() == "Windows":
        patch(tp, old, "batch_size=None, num_workers=0)", "DataLoader in-process (Windows spawn cannot pickle the dataset)")
        # Only on Windows: Linux deletes a memory-mapped file without complaint; Windows refuses.
        patch(up, "    trim_mmap(output_file)\n", "    del fp  # Windows: release the map before trim_mmap deletes the file\n"
              "    trim_mmap(output_file)\n", "Windows: release the feature map before trim_mmap deletes the file")
        patch(dp, "    # Remove old mmaped file\n", "    del mmap_file1, mmap_file2  # Windows: release both maps\n"
              "    # Remove old mmaped file\n", "Windows: release trim_mmap's maps before it deletes and renames")
    else:
        patch(tp, old, "batch_size=None, num_workers=1, prefetch_factor=16)",
              "one DataLoader worker: more replay the same batches (one generator copied per worker)")
    py = sys.executable
    tf_check = "\n".join([
        "import importlib.util, sys", "import torchmetrics, transformers", "from transformers.utils import is_tf_available",
        "loaded = sorted(m for m in sys.modules if m == 'tensorflow' or m.startswith('tensorflow.'))", "failed = []",
        "if loaded: failed.append(f'1. tensorflow modules are loaded: {loaded[:5]}')",
        "if is_tf_available() is not False: failed.append('2. is_tf_available() is not False')",
        "if importlib.util.find_spec('tensorflow') is not None: failed.append('3. tensorflow is installed')",
        "assert not failed, 'tensorflow check failed: ' + '; '.join(failed)", "print('tensorflow: absent')"])
    run_checked([py, "-c", tf_check], "tensorflow check", env=env)
    run_checked([py, "-c", f"import sys; sys.path[:0] = [{str(CODE)!r}, {str(COMPAT)!r}, {str(oww)!r}]; import colab313_compat, numpy; "
                 "import openwakeword.data, torchinfo, torchmetrics, acoustics; from openwakeword.utils import AudioFeatures; "
                 "print('openwakeword features', AudioFeatures(device='cpu').embed_clips(numpy.zeros((1, 32000), numpy.int16)).shape)"],
                "openwakeword import check", env=env)
    run_checked([py, "-c", f"import sys; sys.path[:0] = [{str(CODE)!r}, {str(COMPAT)!r}]; import colab313_compat, torch, os, tempfile; "
                 "d = tempfile.mkdtemp(); p = os.path.join(d, 'x.onnx'); "
                 "torch.onnx.export(torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(1536, 1)), torch.rand(1, 16, 96), p); "
                 "assert not os.path.exists(p + '.data'), 'weights went to a side file'; print('onnx export ok')"],
                "onnx export check", env=env)
    run_checked([py, "-c", f"import sys; sys.path[:0] = [{str(CODE)!r}, {str(COMPAT)!r}]; import colab313_compat, tempfile; "
                 "from generate_samples import generate_samples; generate_samples(text=['hey guru'], max_samples=1, "
                 "output_dir=tempfile.mkdtemp(), model='models/en_US-libritts_r-medium.pt'); print('piper-sample-generator ok')"],
                "piper-sample-generator check", cwd=psg, env=env)


def train_pool(data):
    """Clip ids training may read, per source file, from the committed split (scripts/split_wake_pools.py).

    Training used to decode clips the false-wake scoring then counted on: all 325 of the scored
    sound clips and 120 of the 200 scored music tracks. Every clip training reads is checked here.
    """
    for where in (CODE.parents[1] / "scripts" / "wake_audio_pools.json", data / "wake_audio_pools.json"):
        if where.is_file():
            pools = json.loads(where.read_text(encoding="utf-8"))
            scored = {i for ids in pools["score"].values() for i in ids}
            train = {name: set(ids) - scored for name, ids in pools["train"].items()}
            return train
    raise FileNotFoundError("wake_audio_pools.json not found beside the repo's scripts or in the data folder")


def only_train(pool, path, stem):
    if stem not in pool.get(Path(path).name, ()):
        raise RuntimeError(f"{Path(path).name}: clip {stem} is not in the training pool; the scoring pool must stay unheard")


def stage_background(data, work):
    """AudioSet shard 09 and 120 FMA-small tracks, decoded to 16 kHz WAV."""
    import pyarrow.parquet as pq
    import soundfile as sf
    from generation import write16k
    pool = train_pool(data)
    for sub, path, limit in (("audioset_16k", data / L.AUDIOSET, None), ("fma", data / L.FMA, 120)):
        out = work / "data" / sub
        out.mkdir(parents=True, exist_ok=True)
        n = 0
        for b in pq.ParquetFile(path).iter_batches(batch_size=50, columns=["audio"]):
            for r in b.column(0).to_pylist():
                if limit is not None and n >= limit:
                    break
                n += 1
                only_train(pool, path, Path(r["path"]).stem)
                dest = out / (Path(r["path"]).stem + ".wav")
                if not dest.exists():
                    a, sr = sf.read(io.BytesIO(r["bytes"]), dtype="float32")
                    write16k(dest, a, sr)
    counts = {s: len(list((work / "data" / s).glob("*.wav"))) for s in ("audioset_16k", "fma")}
    counts["mit_rirs"] = len(list((data / L.RIRS).glob("*.wav")))
    assert counts == {"audioset_16k": 500, "fma": 120, "mit_rirs": 270}, f"unexpected background counts {counts}"
    return counts


def stage_recordings(data, work, st):
    z = data / L.RECORDINGS
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    info = st.info("recordings")
    if info:
        if info["sha256"] != digest:
            raise RuntimeError(f"{z} changed since this run started. Finish with the old zip, or use a new --work folder.")
        return info
    real = work / "real"
    shutil.rmtree(real, ignore_errors=True)
    zipfile.ZipFile(z).extractall(real)
    split = json.loads((real / "split.json").read_text(encoding="utf-8"))
    info = {"sha256": digest, "train": split["train"], "bench": split["bench"]}
    st.mark("recordings", info)
    return info


def stage_svarah(data, work, scale):
    """Svarah's training speakers as negative features; the speaker split as the notebook made it."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    import scipy.signal
    import soundfile as sf
    from openwakeword.utils import AudioFeatures
    shards = [data / p for p in L.SVARAH]
    profile = ["gender", "age-group", "primary_language", "native_place_state", "native_place_district",
               "highest_qualification", "job_category", "occupation_domain"]
    meta = pa.concat_tables([pq.read_table(f, columns=profile + ["text", "duration"]) for f in shards])
    keys = ["|".join(str(v) for v in vals) for vals in zip(*(meta.column(f).to_pylist() for f in profile))]
    speakers = sorted(set(keys))
    assert 90 <= len(speakers) <= 150, f"{len(speakers)} speaker keys: does not match Svarah's 117 speakers"
    ranked = sorted(speakers, key=lambda k: hashlib.sha256(k.encode()).hexdigest())
    bench = set(ranked[: round(len(ranked) * SVARAH_BENCH_FRACTION)])
    texts, dur = meta.column("text").to_pylist(), meta.column("duration").to_pylist()
    wake = {i for i, x in enumerate(texts) if heard_name(x, "guru") or heard_name(x, "maya")}
    train_rows = [i for i, k in enumerate(keys) if k not in bench and i not in wake]
    bench_rows = [i for i, k in enumerate(keys) if k in bench and i not in wake]
    train_rows = train_rows[: max(64, int(len(train_rows) * scale))]
    report = {"speakers": len(speakers), "train_speakers": len(speakers) - len(bench), "bench_speakers": len(bench),
              "rows_dropped_for_wake_words": len(wake), "train_rows_used": len(train_rows),
              "train_hours": round(sum(dur[i] for i in train_rows) / 3600, 2),
              "bench_hours": round(sum(dur[i] for i in bench_rows) / 3600, 2)}
    # The speaker list has its own key: under "bench_speakers" it was overwritten by **report's
    # count of the same name, and the benchmark's len() on it then failed.
    atomic(work / "svarah_split.json", json.dumps({"profile_fields": profile, "bench_speaker_keys": sorted(bench),
                                                  "bench_rows": bench_rows, "train_rows": train_rows, **report}, indent=1))
    clip = int(16000 * SVARAH_CLIP_S)
    wanted, row, clips = set(train_rows), 0, []
    for f in shards:
        for b in pq.ParquetFile(f).iter_batches(batch_size=64, columns=["audio_filepath"]):
            for cell in b.column(0).to_pylist():
                row += 1
                if row - 1 not in wanted:
                    continue
                a, sr = sf.read(io.BytesIO(cell["bytes"]), dtype="float32")
                a = a.mean(axis=1) if a.ndim > 1 else a
                x = scipy.signal.resample_poly(a, 16000, sr).astype(np.float32) if sr != 16000 else a
                clips += [(np.clip(x[s:s + clip], -1, 1) * 32767).astype(np.int16) for s in range(0, len(x) - clip + 1, clip)]
    # Features computed here directly, not with compute_features_from_generator: that one
    # finishes with trim_mmap, which deletes a memory-mapped file (fine on Linux, refused on Windows).
    F = AudioFeatures(device="cpu", ncpu=1)
    feats = np.concatenate([F.embed_clips(np.stack(clips[i:i + 64]), batch_size=64)
                            for i in range(0, len(clips), 64)]).astype(np.float32)
    tmp = work / "svarah_features_train.partial.npy"
    np.save(tmp, feats)
    os.replace(tmp, work / "svarah_features_train.npy")
    report["feature_rows"] = int(feats.shape[0])
    log(f"svarah: {report}")
    return report


def stage_extra_negatives(data, work):
    """Everyday sounds, TV and radio talk, and music as negative features, none of them scored on.

    The round-5 models woke 6.7 times an hour on everyday sounds and 2.4 on music through the
    assistant's detector. The false-wake scoring now uses AudioSet shard 01 and FMA file 00001
    (see train_pool), so all of AudioSet shards 00 and 09 and every track of FMA file 00000 are
    training clips and are used here. Round 6 left out shard 09's clips with no speech label and
    the first 200 FMA tracks, because they were the scoring sets then.
    """
    import numpy as np
    import pyarrow.parquet as pq
    import scipy.signal
    import soundfile as sf
    from openwakeword.utils import AudioFeatures
    clip = int(16000 * SVARAH_CLIP_S)
    clips, counts = [], {"audioset_00": 0, "audioset_09": 0, "fma_00000": 0}
    pool = train_pool(data)

    def add(cell, key, path):
        only_train(pool, path, Path(cell["path"]).stem)
        a, sr = sf.read(io.BytesIO(cell["bytes"]), dtype="float32")
        a = a.mean(axis=1) if a.ndim > 1 else a
        x = scipy.signal.resample_poly(a, 16000, sr).astype(np.float32) if sr != 16000 else a
        clips.extend((np.clip(x[s:s + clip], -1, 1) * 32767).astype(np.int16) for s in range(0, len(x) - clip + 1, clip))
        counts[key] += 1

    for key, path in (("audioset_00", data / L.AUDIOSET_EXTRA), ("audioset_09", data / L.AUDIOSET),
                      ("fma_00000", data / L.FMA)):
        for row in pq.read_table(path, columns=["audio"]).column(0).to_pylist():
            add(row, key, path)
    F = AudioFeatures(device="cpu", ncpu=1)
    feats = np.concatenate([F.embed_clips(np.stack(clips[i:i + 64]), batch_size=64)
                            for i in range(0, len(clips), 64)]).astype(np.float32)
    tmp = work / "extra_negative_features.partial.npy"
    np.save(tmp, feats)
    os.replace(tmp, work / "extra_negative_features.npy")
    report = {**counts, "windows": len(clips), "feature_rows": int(feats.shape[0])}
    log(f"extra negatives: {report}")
    return report


def stage_parler_check(data, work, st, tts, models, n_check):
    """Clips built like the notebook's 50-clip check, batched by text, judged by Whisper medium."""
    import numpy as np
    import scipy.signal
    from faster_whisper import WhisperModel
    from generation import describe, write16k
    rng = random.Random(0)
    items = []
    for i in range(n_check):
        name = "guru" if i % 2 == 0 else "maya"
        hindi = i % 5 == 4
        spec = next(v for k, v in models.items() if k.endswith(name))
        items.append((name, "hi" if hindi else "en", rng.choice(spec["hindi"] if hindi else spec["english"]),
                      rng.choice(PARLER_HI_SPEAKERS if hindi else PARLER_EN_SPEAKERS)))
    t0, clips, reasons = time.time(), [None] * n_check, collections.Counter()
    groups = collections.defaultdict(list)
    for i, it in enumerate(items):
        groups[(it[2], it[1])].append(i)
    for (text, lang), idx in groups.items():
        for i, (a, reason) in zip(idx, tts.generate(text, [describe(items[i][3], f"check{i}") for i in idx], lang)):
            clips[i] = a
            reasons[reason] += 1
    rate = (time.time() - t0) / n_check
    out = work / "parler_samples"
    out.mkdir(exist_ok=True)
    judge = WhisperModel(str(data / L.WHISPER), device="cpu", compute_type="int8")
    ok = scored = 0
    for i, ((name, lang, text, spk), a) in enumerate(zip(items, clips)):
        if a is None:
            continue
        write16k(out / f"{i:02d}_{name}_{spk}.wav", a, tts.sr)
        a16 = scipy.signal.resample_poly(a, 16000, tts.sr).astype(np.float32)
        pad = np.zeros(16000, np.float32)
        heard = " ".join(s.text for s in judge.transcribe(np.concatenate([pad, a16, pad]), language=lang)[0])
        ok += heard_name(heard, name)
        scored += 1
        log(f"check {i:02d} [{lang}] {text!r} -> {heard.strip()!r}")
    return {"seconds_per_clip": round(rate, 2), "clips": n_check, "whisper_medium_heard_name": f"{ok}/{scored}",
            "rejected": dict(reasons)}


def model_jobs(name, spec, split, total):
    rng = random.Random(f"{name}/{split}")
    parler, piper = [], []
    for i in range(round(total * SHARE_PARLER_EN)):
        spk = rng.choice(PARLER_EN_SPEAKERS)
        parler.append((f"pe_{spk}_{i:05d}.wav", spk, rng.choice(spec["english"]), "en"))
    for i in range(round(total * SHARE_HINDI)):
        text = rng.choice(spec["hindi"])
        if i % 2 == 0:
            spk = PARLER_HI_SPEAKERS[(i // 2) % 2]
            parler.append((f"ph_{spk}_{i:05d}.wav", spk, text, "hi"))
        else:
            voice = ("pratham", "priyamvada")[(i // 2) % 2]
            piper.append((f"pi_{voice}_{i:05d}.wav", voice, text))
    return parler, piper


def stage_generate(data, work, st, tts, models, batch):
    from generation import Ledger, run_parler, run_piper
    ledger = Ledger(st)
    for name, spec in models.items():
        if st.done(f"generated_{name}"):
            continue
        for split, total in (("positive_train", N_SAMPLES), ("positive_test", N_SAMPLES_VAL)):
            out = work / "models" / name / split
            out.mkdir(parents=True, exist_ok=True)
            for tmp in out.glob("*.tmp"):
                tmp.unlink()
            parler, piper = model_jobs(name, spec, split, total)
            made, secs = run_parler(tts, ledger, parler, out, batch, log, f"{name}/{split}")
            st.add_time(f"{name}_{split}_parler_s", secs)
            run_piper({k: data / v for k, v in L.PIPER.items()}, piper, out)
            if split == "positive_train":
                # "hey" models take the "hey" takes; bare models take bare takes when recorded,
                # else the "hey" takes, which contain the name.
                if name.startswith("hey_"):
                    folder = name
                else:
                    folder = name if any((work / "real" / "train" / name).glob("*.wav")) else f"hey_{name}"
                takes = sorted((work / "real" / "train" / folder).glob("*.wav"))
                assert takes, f"no recorded training takes for {name} in real/train/{folder}"
                want = round(total * SHARE_REAL)
                reps = min(MAX_REPEATS, math.ceil(want / len(takes)))
                n = 0
                for r in range(reps):
                    for f in takes:
                        if n >= want:
                            break
                        if not (out / f"real_{r}_{f.name}").exists():
                            shutil.copy(f, out / f"real_{r}_{f.name}")
                        n += 1
        st.mark(f"generated_{name}")


def clean_wavs(folder):
    import soundfile as sf
    removed = 0
    for tmp in folder.glob("*.tmp"):
        tmp.unlink()
        removed += 1
    for f in folder.glob("*.wav"):
        try:
            if sf.info(f).frames == 0:
                raise ValueError("empty")
        except Exception:
            f.unlink()
            removed += 1
    return removed


def check_export(work, path, name):
    import numpy as np
    import onnx
    import onnxruntime as ort
    m = onnx.load(str(path), load_external_data=False)
    opset = [o.version for o in m.opset_import if o.domain in ("", "ai.onnx")]
    assert opset == [13] and m.ir_version == 7, f"{path}: opset {opset}, ir_version {m.ir_version}; expected [13] and 7"
    assert not os.path.exists(str(path) + ".data"), f"{path}.data exists: the weights are in a side file"
    ref = np.load(work / "export_refs" / f"{name}.npz")
    s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    feed = s.get_inputs()[0].name
    diff = max(float(np.abs(s.run(None, {feed: x})[0] - y).max()) for x, y in zip(ref["x"], ref["y"]))
    assert diff <= 1e-5, f"{path}: onnxruntime differs from the torch model by {diff:.2e} (limit 1e-5)"
    log(f"export check {path.name}: opset 13, ir 7, no side file, matches torch on {len(ref['x'])} inputs within {diff:.1e}")


def stage_train(data, work, st, models, env, cfg, validation_path):
    import yaml
    from features import augment_and_featurize, total_length_for
    oww = work / "src" / "openwakeword"
    base = yaml.safe_load((oww / "examples" / "custom_model.yml").read_text(encoding="utf-8"))
    bg = [str(p) for d in ("audioset_16k", "fma") for p in sorted((work / "data" / d).glob("*.wav"))]
    rirs = [str(p) for p in sorted((data / L.RIRS).glob("*.wav"))]
    for name, spec in models.items():
        c = dict(base)
        c.update({"target_phrase": spec.get("topup") or [spec["english"][2].lower().strip(".!")],
                  "model_name": name, "n_samples": N_SAMPLES,
                  "n_samples_val": N_SAMPLES_VAL, "steps": STEPS, "custom_negative_phrases": spec["negative"],
                  "piper_sample_generator_path": str(work / "src" / "piper-sample-generator"),
                  "output_dir": str(work / "models"), "rir_paths": [str(data / L.RIRS)],
                  "background_paths": [str(work / "data" / "audioset_16k"), str(work / "data" / "fma")],
                  "background_paths_duplication_rate": [1, 1], "false_positive_validation_data_path": str(validation_path),
                  "feature_data_files": {"ACAV100M_sample": str(data / L.ACAV),
                                         "svarah": str(work / "svarah_features_train.npy"),
                                         "everyday": str(work / "extra_negative_features.npy")},
                  "batch_n_per_class": {"ACAV100M_sample": 1024, "svarah": 256, "everyday": 256,
                                        "adversarial_negative": 50, "positive": 50}})
        cfg_path = work / "models" / f"{name}.yaml"
        atomic(cfg_path, yaml.safe_dump(c, allow_unicode=True))
        mdir = work / "models" / name
        launch = [sys.executable, str(CODE / "trainpy_launch.py"), str(oww), "--training_config", str(cfg_path)]
        if not st.done(f"{name}_generate_clips"):
            for split in ("positive_train", "positive_test", "negative_train", "negative_test"):
                (mdir / split).mkdir(parents=True, exist_ok=True)
                n = clean_wavs(mdir / split)
                if n:
                    log(f"{name}/{split}: removed {n} partial clips left by an interrupted run")
            t0 = time.time()
            run_checked(launch + ["--generate_clips"], f"train.py {name} --generate_clips", env=env, cwd=work)
            st.add_time(f"{name}_generate_clips_s", time.time() - t0)
            st.mark(f"{name}_generate_clips")
        if not st.done(f"{name}_features"):
            t0 = time.time()
            total = total_length_for(mdir / "positive_test")
            for split in ("positive_train", "negative_train", "positive_test", "negative_test"):
                out = mdir / f"{split.replace('_', '_features_')}.npy"
                if out.exists():
                    continue
                clips = sorted((mdir / split).glob("*.wav"))
                log(f"{name}/{split}: augmenting and featurizing {len(clips)} clips with {cfg['feature_workers']} workers")
                augment_and_featurize(clips, out, total, bg, rirs, oww, run_seed=int(hashlib.sha256(f"{name}/{split}".encode()).hexdigest()[:8], 16),
                                      workers=cfg["feature_workers"], log=log)
            st.add_time(f"{name}_features_s", time.time() - t0)
            st.mark(f"{name}_features", {"total_length": total})
        if not st.done(f"{name}_train_model"):
            for f in (work / "models" / f"{name}.onnx", work / "export_refs" / f"{name}.npz"):
                if f.exists():
                    f.unlink()
            t0 = time.time()
            run_checked(launch + ["--train_model"], f"train.py {name} --train_model", env=env, cwd=work)
            st.add_time(f"{name}_train_model_s", time.time() - t0)
            check_export(work, work / "models" / f"{name}.onnx", name)
            st.mark(f"{name}_train_model")


def voice_mix(work, models):
    mix = {}
    for name in models:
        for split in ("positive_train", "positive_test"):
            c = collections.Counter()
            for f in (work / "models" / name / split).glob("*.wav"):
                n = f.name
                key = ("parler_en_" + n.split("_")[1] if n.startswith("pe_") else "parler_hi_" + n.split("_")[1]
                       if n.startswith("ph_") else "piper_hi_" + n.split("_")[1] if n.startswith("pi_")
                       else "real_takes" if n.startswith("real_") else "libritts_r_topup")
                c[key] += 1
            mix.setdefault(name, {})[split] = dict(sorted(c.items()))
    return mix


def main():
    global LOG, N_SAMPLES, N_SAMPLES_VAL, STEPS
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", required=True, help="the portable data folder")
    ap.add_argument("--work", required=True, help="where clips, features, models and the report go")
    ap.add_argument("--models", choices=sorted(MODELS), default="hey")
    ap.add_argument("--scale", type=float, default=1.0, help="0.01 for the dry run")
    ap.add_argument("--parler-dtype", choices=["bfloat16", "float16", "float32"])
    ap.add_argument("--parler-batch", type=int, help="largest Parler batch to try (default: from VRAM)")
    ap.add_argument("--workers", type=int, help="feature workers (default: CPUs and RAM)")
    ap.add_argument("--stop-after", default="", help="stop after this stage (testing resume)")
    a = ap.parse_args()
    # Hindi texts are logged; with output redirected on Windows (cp1252) or under a non-UTF-8
    # cluster locale, printing Devanagari raised UnicodeEncodeError and stopped the run.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    data, work = Path(a.data).resolve(), Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    LOG = work / "run.log"
    if a.scale < 1:
        N_SAMPLES, N_SAMPLES_VAL, STEPS = max(40, round(N_SAMPLES * a.scale)), max(12, round(N_SAMPLES_VAL * a.scale)), \
            max(200, round(STEPS * a.scale))
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                       "HF_HOME": str(work / "hf_home_unused"), "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
                       "USE_TF": "0", "USE_TORCH": "1"})
    oww_src = str(work / "src" / "openwakeword")
    sys.path.insert(0, oww_src)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(CODE), str(COMPAT), oww_src]), PYTHONIOENCODING="utf-8",
               TQDM_MININTERVAL="30", TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD="1", OWW_EXPORT_REF_DIR=str(work / "export_refs"))
    import colab313_compat  # noqa: F401
    import env as E
    st = State(work)
    info = E.detect()
    cfg = E.choose(info, a)
    log(f"run start: data {data}, work {work}, models {a.models}, scale {a.scale}; machine {info}; chosen {cfg}; "
        f"done so far {sorted(p.stem for p in st.dir.glob('*.done'))}")
    st.save("environment", {"machine": info, "chosen": cfg, "args": vars(a),
                            "training": {"n_samples": N_SAMPLES, "n_samples_val": N_SAMPLES_VAL, "steps": STEPS}})
    models = MODELS[a.models]

    def stage(name, fn):
        if st.done(name):
            return st.info(name)
        t0 = time.time()
        log(f"== {name}")
        result = fn()
        st.add_time(f"{name}_s", time.time() - t0)
        st.mark(name, result if isinstance(result, dict) else {})
        if a.stop_after == name:
            log(f"stopping after {name} as asked")
            sys.exit(0)
        return result

    stage("setup", lambda: stage_setup(data, work, cfg, env))
    # oww_src went onto sys.path before setup created it, and Python caches that a path entry
    # did not exist: without this, `import openwakeword` failed here on a first run.
    import importlib
    sys.path_importer_cache.pop(oww_src, None)
    importlib.invalidate_caches()
    stage("background", lambda: stage_background(data, work))
    rec = stage_recordings(data, work, st)
    stage("svarah", lambda: stage_svarah(data, work, a.scale))
    stage("extra_negatives", lambda: stage_extra_negatives(data, work))
    validation = data / L.VALIDATION
    if a.scale < 1:      # a slice of the 481,345 validation windows: building all of them costs ~7 min per model
        import numpy as np
        validation = work / "validation_slice.npy"
        if not validation.exists():
            v = np.load(data / L.VALIDATION, mmap_mode="r")
            np.save(validation, np.asarray(v[: max(5000, int(len(v) * a.scale))]))
    tts = None
    needs_tts = not st.done("parler_check") or not all(st.done(f"generated_{n}") for n in models)
    if needs_tts:
        from generation import Parler, pick_batch
        tts = Parler(data / L.PARLER, data / L.FLAN_T5, cfg["parler_dtype"],
                     device="cuda" if info["cuda"] else "cpu")
        if "parler_batch" not in st.load("parler_settings", {}):
            log("== parler batch size")
            batch, rows = pick_batch(tts, "Hey Guru.", "en", PARLER_EN_SPEAKERS, cfg["parler_batch_max"], log)
            st.save("parler_settings", {"parler_batch": batch, "probe": rows, "dtype": cfg["parler_dtype"]})
    batch = st.load("parler_settings", {}).get("parler_batch")
    stage("parler_check", lambda: stage_parler_check(data, work, st, tts, models, 50 if a.scale >= 1 else 6))
    stage("generate", lambda: stage_generate(data, work, st, tts, models, batch))
    if tts is not None:
        del tts
        import torch
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
    stage("train", lambda: stage_train(data, work, st, models, env, cfg, validation))
    import bench
    import report
    stage("benchmark", lambda: bench.run([work / "models" / f"{n}.onnx" for n in models], a.models, data / L.BENCH,
                                         data / L.RECORDINGS, [data / p for p in L.SVARAH], work / "svarah_split.json",
                                         1.0 if a.scale >= 1 else a.scale, log,
                                         validation_dir=data / "inputs" / "validation"))
    report.write(work, st, models, a, voice_mix(work, models), rec, validation)
    log(f"finished: {work / 'out' / 'REPORT.md'}")


if __name__ == "__main__":
    main()
