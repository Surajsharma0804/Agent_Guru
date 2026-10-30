"""Measure wake word models the way the assistant runs them: false accepts, false rejects, latency.

    python scripts/wake_word_eval.py --models <folder> [--background a.npy ...] [--positives p.npy ...]
                                     [--contains c.npy ...] [--out report.json] [--stand-in]

<folder> holds one openWakeWord model per wake word, named after it (hey_guru.onnx, hey_maya.onnx),
which is what WakeWordDetector looks for in %LOCALAPPDATA%\\agent_guru\\wake_models. The audio is fed
to the assistant's own WakeWordDetector in the listen loop's chunks (1.5 s, main.py) on a simulated
clock, with its 3 s cooldown, so what is measured is what the assistant would do.

Inputs are float32 16 kHz mono .npy arrays, or for --positives and --contains a folder of recorded
takes (record_wake.py writes <speaker>/<phrase>/*.wav), whose phrase is the folder each take is in:
  --background  audio with no wake phrase in it (room talk, TV, music): false accepts per hour
  --positives   with a <name>_spans.json beside it, a list of [clip name, start s, end s]; each clip's
                wake word is read from its name (hey_guru, hey_maya, or --phrase for a stand-in):
                false reject rate, wrong-name rate, and latency from the end of the phrase to the wake
  --contains    like --positives, for sentences that hold a wake phrase without being a wake ("hey
                guru ji", "I told her hey maya is late"): how often they wake it, reported apart,
                since a detector that hears the phrase cannot tell these from a wake

Run it with a Python that has openwakeword installed (Windows: pip install openwakeword==0.6.0; Linux:
pip install --no-deps openwakeword==0.6.0, because its tflite-runtime has no Python 3.13 wheel) and this
repository on PYTHONPATH. --stand-in labels the report a check of this script, for runs with a stock
model renamed to a wake word: such numbers say the harness works, nothing about Guru or Maya.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SR = 16000
CHUNK_S = 1.5  # main.py: audio_capture_duration
COOLDOWN_S = 3.0  # main.py: cooldown_seconds
HIT_AFTER_S = 1.0  # a wake this long after the phrase ends still counts as hearing it


def _detector(models: Path, phrases: list[str]):
    import Agent_Guru.speech.audio.wake_word as ww
    from Agent_Guru.speech.models import PersonalityType

    clock = [0.0]
    ww.time = types.SimpleNamespace(time=lambda: clock[0])
    wake_words = {p: (PersonalityType.MAYA if "maya" in p else PersonalityType.GURU) for p in phrases}
    det = ww.WakeWordDetector(ww.WakeWordConfig(wake_words=wake_words, oww_model_dir=str(models),
                                                cooldown_seconds=COOLDOWN_S))
    if det._backend != "openwakeword":
        sys.exit(f"The detector did not choose openWakeWord: {det._backend_reason}")
    return det, clock


async def _stream(det, clock, audio: np.ndarray) -> tuple[list[tuple[float, str]], list[float]]:
    """Wakes as (time at the end of the chunk that woke it, phrase), and seconds spent per chunk."""
    det._oww_model.reset()
    det._last_detection_time = -1e9
    n, wakes, spent = int(SR * CHUNK_S), [], []
    for start in range(0, len(audio) - n + 1, n):
        clock[0] = (start + n) / SR
        began = time.perf_counter()
        found = await det.detect(np.asarray(audio[start:start + n], dtype=np.float32))
        spent.append(time.perf_counter() - began)
        if found is not None:
            wakes.append((clock[0], found.wake_word))
    return wakes, spent


def _takes(folder: Path) -> tuple[np.ndarray, list]:
    """Recorded takes as one stream: each take after 3 s of near silence, named after its folder."""
    import soundfile as sf

    parts, spans, t = [], [], 0.0
    gap = np.random.default_rng(0).normal(0, 0.0005, SR * 3).astype(np.float32)
    for wav in sorted(folder.rglob("*.wav")):
        audio, rate = sf.read(wav, dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        if rate != SR:
            from scipy.signal import resample_poly

            audio = resample_poly(audio, SR, rate).astype(np.float32)
        parts += [gap, audio]
        t += len(gap) / SR
        spans.append([f"{wav.parent.name}/{wav.name}", round(t, 3), round(t + len(audio) / SR, 3)])
        t += len(audio) / SR
    if not spans:
        sys.exit(f"no .wav takes under {folder}")
    parts.append(gap)
    return np.concatenate(parts), spans


def _load(path: str) -> tuple[np.ndarray, list | None]:
    p = Path(path)
    if p.is_dir():
        return _takes(p)
    spans_file = p.with_name(p.stem + "_spans.json")
    spans = json.loads(spans_file.read_text(encoding="utf-8")) if spans_file.exists() else None
    return np.load(p, mmap_mode="r"), spans


def _phrase_of(clip: str, phrases: list[str], default: str | None) -> str | None:
    name = clip.lower().replace(" ", "_")
    for phrase in sorted(phrases, key=len, reverse=True):
        if phrase.replace(" ", "_") in name:
            return phrase
    return default


async def evaluate(args, phrases: list[str], inputs: dict[str, list]) -> dict:
    """Stream every loaded input through the detector; inputs maps kind to (name, audio, spans)."""
    det, clock = _detector(Path(args.models), phrases)
    report: dict = {"models": phrases, "folder": args.models, "chunk_s": CHUNK_S, "cooldown_s": COOLDOWN_S,
                    "stand_in": args.stand_in, "background": {}, "positives": {}, "contains": {}}
    spent_all: list[float] = []

    for name, audio, _ in inputs["background"]:
        wakes, spent = await _stream(det, clock, audio)
        spent_all += spent
        hours = len(audio) / SR / 3600
        report["background"][name] = {"minutes": round(hours * 60, 1), "false_accepts": len(wakes),
                                      "per_hour": round(len(wakes) / hours, 2) if hours else None}

    for kind in ("positives", "contains"):
        for name, audio, spans in inputs[kind]:
            wakes, spent = await _stream(det, clock, audio)
            spent_all += spent
            heard = wrong = missed = 0
            latencies = []
            for clip, start, end in spans:
                expected = _phrase_of(clip, phrases, args.phrase)
                hits = [(t, w) for t, w in wakes if start < t <= end + CHUNK_S + HIT_AFTER_S]
                if not hits:
                    missed += 1
                    continue
                t, word = hits[0]
                if expected is not None and word != expected:
                    wrong += 1
                else:
                    heard += 1
                latencies.append(max(0.0, t - end))
            total = len(spans)
            report[kind][name] = {
                "clips": total, "woke": heard + wrong, "right_name": heard, "wrong_name": wrong, "missed": missed,
                "false_reject_rate": round(missed / total, 3) if total else None,
                "latency_s_median": round(statistics.median(latencies), 2) if latencies else None,
                "latency_s_max": round(max(latencies), 2) if latencies else None,
            }

    if spent_all:
        report["compute_ms_per_chunk"] = {"median": round(statistics.median(spent_all) * 1000, 1),
                                          "p95": round(sorted(spent_all)[int(len(spent_all) * 0.95)] * 1000, 1)}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--models", required=True, help="folder with <wake_word>.onnx files")
    parser.add_argument("--background", nargs="*", default=[], help="wake-free audio (.npy)")
    parser.add_argument("--positives", nargs="*", default=[], help="wake clips (.npy with _spans.json)")
    parser.add_argument("--contains", nargs="*", default=[], help="sentences holding a wake phrase (.npy with _spans.json)")
    parser.add_argument("--phrase", default=None, help="wake word for clips whose names do not say it")
    parser.add_argument("--out", default=None, help="write the report here as JSON")
    parser.add_argument("--stand-in", action="store_true", help="the model is a stand-in: label it a harness check")
    args = parser.parse_args()
    phrases = sorted({f.stem.replace("_", " ") for f in Path(args.models).glob("*.onnx")})
    inputs: dict[str, list] = {"background": [], "positives": [], "contains": []}
    for kind, paths in (("background", args.background), ("positives", args.positives), ("contains", args.contains)):
        for path in paths:
            audio, spans = _load(path)
            if kind != "background" and spans is None:
                sys.exit(f"{path} has no {Path(path).stem}_spans.json beside it")
            inputs[kind].append((Path(path).stem if Path(path).is_file() else Path(path).name, audio, spans))
    report = asyncio.run(evaluate(args, phrases, inputs))
    if args.stand_in:
        report["label"] = "HARNESS CHECK with a stand-in model: not a result for Hey Guru or Hey Maya"
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
