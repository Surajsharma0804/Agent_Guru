"""The training-set expander is reproducible and writes only valid examples.

It drew from the secrets module, so two runs over the same data wrote
different training sets, and it filled templates from an entity "value" key
the data does not have (it uses "text") while copying the base example's
character offsets onto the new sentence: one run over the 2,448 training
examples added 20 sentences with a literal placeholder ("create alarm {time}")
and 848 entity spans pointing at the wrong characters.
"""

from __future__ import annotations

import random
from pathlib import Path

import yaml

from Agent_Guru.reasoning.data.expand_dataset import expand_dataset, expand_examples

TRAIN = Path(__file__).resolve().parents[1] / "data" / "train_annotated.yaml"


def _alarm(utterance: str, time: str) -> dict:
    start = utterance.index(time)
    return {
        "utterance": utterance,
        "intent": "set_alarm",
        "entities": [{"type": "time", "text": time, "start": start, "end": start + len(time)}],
    }


SMALL = [_alarm("wake me at 7am", "7am"), _alarm("alarm at 6:30 please", "6:30")]


def test_same_seed_same_output():
    assert expand_examples(SMALL, random.Random(3)) == expand_examples(SMALL, random.Random(3))  # nosec B101


def test_new_examples_are_valid_and_new():
    out = expand_examples(SMALL, random.Random(3))
    new = out[len(SMALL):]
    assert new  # nosec B101
    for item in new:
        assert "{" not in item["utterance"]  # nosec B101
        for e in item["entities"]:
            assert item["utterance"][e["start"]:e["end"]] == e["text"]  # nosec B101
    assert len({x["utterance"].lower() for x in out}) == len(out)  # nosec B101


def test_real_training_set_expands_cleanly_and_reproducibly():
    data = yaml.safe_load(TRAIN.read_text(encoding="utf-8"))
    a = expand_examples(data, random.Random(7))
    assert a == expand_examples(data, random.Random(7))  # nosec B101
    assert a != expand_examples(data, random.Random(8))  # nosec B101
    new = a[len(data):]
    assert new  # nosec B101
    assert not [x for x in new if "{" in x["utterance"]]  # nosec B101
    assert not [  # nosec B101
        x for x in new for e in x["entities"] if x["utterance"][e["start"]:e["end"]] != e["text"]
    ]


def test_cli_function_writes_where_asked(tmp_path):
    src, dst = tmp_path / "in.yaml", tmp_path / "out.yaml"
    src.write_text(yaml.dump(SMALL), encoding="utf-8")
    n = expand_dataset(src, dst, seed=5)
    assert yaml.safe_load(src.read_text(encoding="utf-8")) == SMALL  # nosec B101  input untouched
    assert len(yaml.safe_load(dst.read_text(encoding="utf-8"))) == n  # nosec B101
