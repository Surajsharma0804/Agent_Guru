"""Build wake-free background audio for counting false wakes: everyday sounds, and music.

    <python with pyarrow, soundfile, scipy> scripts/build_wake_background.py <out folder> [<data folder>]

Writes bg_noise.npy (AudioSet clips whose labels name no speech, singing, TV or radio: 53.4 min from
the data folder's balanced shard) and bg_music.npy (200 FMA tracks: 100 min), float32 16 kHz mono, each
clip levelled to an RMS between 0.01 and 0.04 as a room microphone hears it. Same seed, same audio.
These are what scripts/wake_word_eval.py --background and the MFCC stopgap measurement used. They are
real recordings mixed by script, not a real room: a real-room measurement needs the owner's microphone.
"""
import io, json, sys
import numpy as np, pyarrow.parquet as pq, soundfile as sf
from scipy.signal import resample_poly

OUT = sys.argv[1]
BG = (sys.argv[2] if len(sys.argv) > 2 else "E:/agent_guru_wakeword_data") + "/inputs/background/"
SPEECHY = ("speech", "conversation", "narration", "singing", "chant", "rapping", "babbling",
           "whispering", "shout", "yell", "male", "female", "child", "laughter", "television", "radio")

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
parts, meta = {"noise": [], "music": []}, {"noise": 0, "music": 0, "skipped_speech": 0}
t = pq.read_table(BG + "audioset_bal_train_09.parquet").to_pylist()
for row in t:
    labels = " ".join(row["human_labels"]).lower()
    if any(w in labels for w in SPEECHY):
        meta["skipped_speech"] += 1; continue
    a = level(to16k(row["audio"]["bytes"]), float(rng.uniform(0.01, 0.04)))
    if a is not None: parts["noise"].append(a); meta["noise"] += 1
for row in pq.read_table(BG + "fma_small_train_00000.parquet").to_pylist()[:200]:
    a = level(to16k(row["audio"]["bytes"]), float(rng.uniform(0.01, 0.04)))
    if a is not None: parts["music"].append(a); meta["music"] += 1
for k, v in parts.items():
    a = np.concatenate(v); np.save(f"{OUT}/bg_{k}.npy", a); meta[k + "_min"] = round(len(a) / 16000 / 60, 1)
print(json.dumps(meta))
