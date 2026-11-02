"""Prove the benchmark scorer can see a detection before trusting what it says about real models.

The first dry run reported 0% detection on every set at every threshold and 0 false wakes.
That is what a 600-step model should score, and also exactly what a scorer with misaligned
spans, a wrong frame size, or a broken name mapping would report for any model. The two
cannot be told apart from the result, so the benchmark now runs a model whose behaviour is
known first.

The known model is a speech detector, written directly as ONNX: the mean of the 16
openWakeWord embedding frames it is given, projected on the direction from the noise floor
to real speech, through a sigmoid. It goes through the same openwakeword.Model path as the
trained models. Named "hey_guru", it must

- wake on nearly every Guru clip of the TTS dev set (the clip spans line up with the scores),
- wake on nearly every Maya clip as the wrong name (the name mapping is applied),
- wake many times in 16 minutes of speech (false wakes are counted).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

import bench

MIN_RATE = 0.9


def _embeddings(audio):
    from openwakeword.utils import AudioFeatures
    f = AudioFeatures(inference_framework="onnx", device="cpu")
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    return f.embed_clips(pcm[None, :], batch_size=1)[0]            # (frames, 96)


def _windows(emb):
    return np.stack([emb[i:i + 16].mean(axis=0) for i in range(len(emb) - 15)])


def _write_model(path, w, b):
    import onnx
    from onnx import TensorProto, helper
    g = helper.make_graph(
        [helper.make_node("ReduceMean", ["input"], ["m"], axes=[1], keepdims=0),
         helper.make_node("MatMul", ["m", "W"], ["p"]),
         helper.make_node("Add", ["p", "B"], ["z"]),
         helper.make_node("Sigmoid", ["z"], ["output"])],
        "speech_detector",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 16, 96])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 1])],
        [helper.make_tensor("W", TensorProto.FLOAT, [96, 1], w.astype(np.float32).ravel().tolist()),
         helper.make_tensor("B", TensorProto.FLOAT, [1], [float(b)])])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 7
    onnx.checker.check_model(m)
    onnx.save(m, str(path))


def run(bench_dir, log=print):
    bench_dir = Path(bench_dir)
    rng = np.random.default_rng(7)
    neg = np.load(bench_dir / "wake_neg.npy")
    speech = _windows(_embeddings(neg[: bench.SR * 120]))
    floor = _windows(_embeddings(rng.normal(0, bench.FLOOR_RMS, bench.SR * 30).astype(np.float32)))
    w = speech.mean(axis=0) - floor.mean(axis=0)
    ps, pf = speech @ w, floor @ w
    # Midway between the loudest floor window and the typical speech window, steep enough
    # that a window clearly on either side scores near 0 or 1.
    mid = (pf.max() + np.median(ps)) / 2
    k = 12 / max(np.median(ps) - pf.max(), 1e-6)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "hey_guru.onnx"
        _write_model(path, w * k, -mid * k)
        scorer = bench.Scorer([path])
        a, spans = bench.tts_set(bench_dir, "wake_pos.npy", "wake_pos_spans.json", "en", bench.dev_set_name)
        r = bench._positives(scorer, scorer.scores(a), spans, 0.5)
        fw = len(scorer.wakes(scorer.scores(neg), 0.5))
    guru = [x for x in r if x["wake"] == "guru"]
    maya = [x for x in r if x["wake"] == "maya"]
    res = {"guru_clips_detected": f"{sum(x['hit'] for x in guru)}/{len(guru)}",
           "maya_clips_woken_as_guru": f"{sum(x['wrong_name'] for x in maya)}/{len(maya)}",
           "false_wakes_in_speech": fw, "speech_hours": round(len(neg) / bench.SR / 3600, 3)}
    log(f"benchmark self-test: {json.dumps(res)}")
    ok = (guru and sum(x["hit"] for x in guru) >= MIN_RATE * len(guru)
          and maya and sum(x["wrong_name"] for x in maya) >= MIN_RATE * len(maya) and fw > 0)
    if not ok:
        raise RuntimeError(f"benchmark self-test failed, the scorer cannot be trusted: {res}")
    return res


if __name__ == "__main__":
    import sys
    print(run(sys.argv[1]))
