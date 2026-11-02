"""Validation audio for choosing a wake threshold, from the TRAINING pool of wake_audio_pools.json only.

Uses the training-pool clips the third models never read: FMA file 00001 from track 201 on, and AudioSet
shard 01's clips with a speech label. They are not in the scoring pool, so the held-out sets stay unseen.
Same levelling as build_wake_background.py. Writes val_music.npy and val_speechy.npy.
"""
import io
import json
import sys
from math import gcd
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from scipy.signal import resample_poly

OUT = Path(sys.argv[1])
POOLS = json.loads(Path(r"F:\MY PROJECTS\Agent_Guru\scripts\wake_audio_pools.json").read_text(encoding="utf-8"))
SCORED = {i for ids in POOLS["score"].values() for i in ids}
SRC = Path("E:/agent_guru_wakeword_data/inputs/score_pool")
rng = np.random.default_rng(11)


def to16k(b):
    a, sr = sf.read(io.BytesIO(b), dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != 16000:
        g = gcd(sr, 16000)
        a = resample_poly(a, 16000 // g, sr // g).astype(np.float32)
    return a


for name, out in (("fma_small_train_00001.parquet", "val_music"), ("audioset_bal_train_01.parquet", "val_speechy")):
    want = set(POOLS["train"][name])
    parts = []
    for r in pq.read_table(SRC / name).to_pylist():
        cid = Path(r["audio"]["path"]).stem
        if cid not in want:
            continue
        assert cid not in SCORED
        a = to16k(r["audio"]["bytes"])
        rms = float(np.sqrt(np.mean(a ** 2)))
        if rms > 1e-5:
            parts.append((a * (rng.uniform(0.01, 0.04) / rms)).astype(np.float32))
    v = np.concatenate(parts)
    np.save(OUT / f"{out}.npy", v)
    print(out, len(parts), "clips", round(len(v) / 16000 / 60, 1), "min")
