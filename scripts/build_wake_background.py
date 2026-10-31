"""Build wake-free background audio for counting false wakes: everyday sounds, and music.

    <python with pyarrow, soundfile, scipy> scripts/build_wake_background.py <out folder> [<data folder>]

Writes bg_noise.npy (AudioSet clips whose labels name no speech, singing, TV or radio) and bg_music.npy
(200 FMA tracks), float32 16 kHz mono, each clip levelled to an RMS between 0.01 and 0.04 as a room
microphone hears it. Same seed, same audio. These are what scripts/wake_word_eval.py --background uses.
They are real recordings mixed by script, not a real room: a real-room measurement needs the owner's
microphone.

Only clips in the "score" pool of scripts/wake_audio_pools.json are read (see split_wake_pools.py).
This used to build the sets from AudioSet shard 09 and the first 200 tracks of FMA file 00000, which
wake word training also mixed under its examples: all 325 sound clips and 120 of the 200 music tracks
had been heard in training. Earlier sets built here (53.4 min of sounds, 100 min of music) are not
comparable with the ones it builds now.
"""
import io, json, sys
from pathlib import Path
import numpy as np, pyarrow.parquet as pq, soundfile as sf
from scipy.signal import resample_poly

OUT = sys.argv[1]
SCORE = (sys.argv[2] if len(sys.argv) > 2 else "E:/agent_guru_wakeword_data") + "/inputs/score_pool/"
POOLS = json.loads((Path(__file__).with_name("wake_audio_pools.json")).read_text(encoding="utf-8"))
TRAINED = {i for ids in POOLS["train"].values() for i in ids}

def score_rows(name):
    """The rows of a scoring file whose clip is in the score pool, in file order."""
    wanted = set(POOLS["score"][name])
    rows = [r for r in pq.read_table(SCORE + name).to_pylist() if Path(r["audio"]["path"]).stem in wanted]
    ids = {Path(r["audio"]["path"]).stem for r in rows}
    assert not ids & TRAINED and ids == wanted, f"{name}: rows do not match the score pool"
    return rows

def to16k(b):
    a, sr = sf.read(io.BytesIO(b), dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != 16000:
        from math import gcd
        g = gcd(sr, 16000); a = resample_poly(a, 16000 // g, sr // g).astype(np.float32)
    return a

def level(a, rms):
    r = float(np.sqrt(np.mean(a**2)))
    return (a * (rms / r)).astype(np.float32) if r > 1e-5 else None

rng = np.random.default_rng(7)
parts, meta = {"noise": [], "music": []}, {"noise": 0, "music": 0}
for row in score_rows("audioset_bal_train_01.parquet"):
    a = level(to16k(row["audio"]["bytes"]), float(rng.uniform(0.01, 0.04)))
    if a is not None: parts["noise"].append(a); meta["noise"] += 1
for row in score_rows("fma_small_train_00001.parquet"):
    a = level(to16k(row["audio"]["bytes"]), float(rng.uniform(0.01, 0.04)))
    if a is not None: parts["music"].append(a); meta["music"] += 1
for k, v in parts.items():
    a = np.concatenate(v); np.save(f"{OUT}/bg_{k}.npy", a); meta[k + "_min"] = round(len(a) / 16000 / 60, 1)
print(json.dumps(meta))
