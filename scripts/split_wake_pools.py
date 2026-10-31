"""Split the wake word background audio into a training pool and a scoring pool, by clip id.

    <python with pyarrow> scripts/split_wake_pools.py [<data folder>]

Writes scripts/wake_audio_pools.json. Training (wakeword_training/runner) mixes only "train" clips under
its examples and uses only them as negatives; scripts/build_wake_background.py builds the false-wake
sets only from "score" clips. Before this split the training augmentation decoded all 500 clips of
AudioSet shard 09 and the first 120 FMA tracks, while the false-wake sets were shard 09's 325 clips
with no speech label and the first 200 FMA tracks: all 325 sound clips and 120 of the 200 music
tracks had been heard in training, so the false wakes counted on them were low by an unknown amount.

The scoring pool comes from two files neither the first nor the second models read: AudioSet balanced
shard 01 (its clips with no speech, singing, TV or radio label) and FMA file 00001 (its first 200
tracks). A clip id is the stem of the clip's audio path: the YouTube id for AudioSet (the same as its
video_id column), the zero-padded track number for FMA, which is also the name training writes it as.
"""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

DATA = Path(sys.argv[1] if len(sys.argv) > 1 else "E:/agent_guru_wakeword_data") / "inputs"
OUT = Path(__file__).with_name("wake_audio_pools.json")
# The same words build_wake_background.py has always used to keep speech out of the sounds set.
SPEECHY = ("speech", "conversation", "narration", "singing", "chant", "rapping", "babbling",
           "whispering", "shout", "yell", "male", "female", "child", "laughter", "television", "radio")
MUSIC_SCORE_TRACKS = 200


def ids(path: Path, labels: bool = False) -> list[tuple[str, str]]:
    cols = ["audio", "human_labels"] if labels else ["audio"]
    rows = pq.read_table(path, columns=cols).to_pylist()
    return [(Path(r["audio"]["path"]).stem, " ".join(r.get("human_labels") or []).lower()) for r in rows]


def main() -> int:
    train: dict[str, list[str]] = {}
    score: dict[str, list[str]] = {}
    for name in ("audioset_bal_train_00.parquet", "audioset_bal_train_09.parquet", "fma_small_train_00000.parquet"):
        train[name] = [i for i, _ in ids(DATA / "background" / name)]
    shard01 = ids(DATA / "score_pool" / "audioset_bal_train_01.parquet", labels=True)
    score["audioset_bal_train_01.parquet"] = [i for i, lab in shard01 if not any(w in lab for w in SPEECHY)]
    train["audioset_bal_train_01.parquet"] = [i for i, lab in shard01 if any(w in lab for w in SPEECHY)]
    fma1 = [i for i, _ in ids(DATA / "score_pool" / "fma_small_train_00001.parquet")]
    score["fma_small_train_00001.parquet"] = fma1[:MUSIC_SCORE_TRACKS]
    train["fma_small_train_00001.parquet"] = fma1[MUSIC_SCORE_TRACKS:]
    pools = {"train": train, "score": score}
    shared = set().union(*train.values()) & set().union(*score.values())
    if shared:
        sys.exit(f"{len(shared)} clip ids are in both pools, for example {sorted(shared)[:3]}")
    OUT.write_text(json.dumps(pools, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({pool: {k: len(v) for k, v in p.items()} for pool, p in pools.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
