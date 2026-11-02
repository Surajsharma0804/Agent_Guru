"""Prove the parallel features equal the serial ones, byte for byte, and time the speed-up.

    python runner/features_test.py <work dir with data/ and models/<name>/positive_train> [n clips]

Runs augment_and_featurize on the same clips with 1 worker and with several, compares the
.npy files exactly, and reports seconds per clip for each worker count.
"""
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import augment_and_featurize, default_workers, total_length_for  # noqa: E402


def main():
    w = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    oww = w / "openwakeword"
    src = sorted((w / "my_custom_model" / "hey_guru" / "positive_train").glob("*.wav"))
    clips = [src[i % len(src)] for i in range(n)]       # repeats are fine: each copy is augmented differently
    background = [str(p) for d in ("audioset_16k", "fma") for p in sorted((w / d).glob("*.wav"))]
    rirs = [str(p) for p in sorted((w / "mit_rirs").glob("*.wav"))]
    total = total_length_for(w / "my_custom_model" / "hey_guru" / "positive_test")
    print(f"{n} clips, total_length {total}, {len(background)} background, {len(rirs)} RIRs, {os.cpu_count()} CPUs")
    out = {}
    counts = sorted({1, 4, default_workers()})
    for workers in counts:
        p = w / f"feat_test_{workers}.npy"
        t = time.time()
        augment_and_featurize(clips, p, total, background, rirs, oww, run_seed=7, workers=workers, log=lambda m: None)
        dt = time.time() - t
        out[workers] = np.load(p)
        print(f"workers {workers:2d}: {dt:6.1f} s = {dt / n * 1000:6.1f} ms/clip, shape {out[workers].shape}", flush=True)
    for workers in counts[1:]:
        same = out[1].tobytes() == out[workers].tobytes()
        print(f"1 worker vs {workers}: byte-identical {same}, max diff {float(np.abs(out[1] - out[workers]).max())}")
    a = w / "feat_test_1.npy"
    augment_and_featurize(clips, a.with_name("feat_test_1b.npy"), total, background, rirs, oww, run_seed=7, workers=1,
                          log=lambda m: None)
    print("1 worker run twice: byte-identical", np.load(a).tobytes() == np.load(a.with_name("feat_test_1b.npy")).tobytes())
    augment_and_featurize(clips, a.with_name("feat_test_seed8.npy"), total, background, rirs, oww, run_seed=8, workers=4,
                          log=lambda m: None)
    print("different run seed changes the augmentation:", np.load(a).tobytes() != np.load(a.with_name("feat_test_seed8.npy")).tobytes())
    os.environ["FEATURES_TEST_DIE_AT"] = "0"
    t = time.time()
    try:
        augment_and_featurize(clips, a.with_name("feat_test_die.npy"), total, background, rirs, oww, run_seed=7, workers=4,
                              log=lambda m: None)
        print("worker death: NOT detected")
    except Exception as e:
        print(f"worker death: raised {type(e).__name__} after {time.time() - t:.0f} s, no output file:",
              not a.with_name("feat_test_die.npy").exists())


if __name__ == "__main__":
    main()
