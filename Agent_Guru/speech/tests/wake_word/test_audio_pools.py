"""No background clip may be in both the wake word training pool and the false-wake scoring pool.

Training used to mix all of AudioSet shard 09 and the first 120 FMA tracks under its examples, and the
false wakes were counted on shard 09's clips and the first 200 FMA tracks: all 325 sound clips and 120
of the 200 music tracks had been heard in training. scripts/wake_audio_pools.json now names every clip's
pool, and this fails if one id is listed in both.
"""

from __future__ import annotations

import json
from pathlib import Path

POOLS = Path(__file__).resolve().parents[4] / "scripts" / "wake_audio_pools.json"


def _pools() -> dict[str, dict[str, list[str]]]:
    return json.loads(POOLS.read_text(encoding="utf-8"))


def test_no_clip_is_in_both_pools():
    pools = _pools()
    train = {i for ids in pools["train"].values() for i in ids}
    score = {i for ids in pools["score"].values() for i in ids}
    assert not train & score, sorted(train & score)[:5]


def test_the_scoring_pool_holds_sounds_and_music():
    score = _pools()["score"]
    assert len(score["audioset_bal_train_01.parquet"]) >= 300
    assert len(score["fma_small_train_00001.parquet"]) == 200


def test_the_files_the_old_scoring_sets_came_from_are_training_only():
    # Both earlier model pairs heard these files in training, so they can never score them again.
    score = _pools()["score"]
    for name in ("audioset_bal_train_09.parquet", "audioset_bal_train_00.parquet", "fma_small_train_00000.parquet"):
        assert not score.get(name)
