"""Score wake word models on the owner's in-room held-out takes, through the assistant's own detector.

    wakeword_training\\venv-oww\\Scripts\\python scripts\\room_wake_eval.py --models <folder of .onnx>

Reads wakeword_training/recordings/room_<distance>_<sound>/ (recorded with record_wake.py --speaker
room_near_quiet and so on) and, if present, wakeword_training/recordings/room_sound/score_*.wav as
wake-free audio from the same room. Every take is streamed through WakeWordDetector exactly as
scripts/wake_word_eval.py does. A condition with no folder is reported as not recorded, never as a
result. These folders are listed in recordings/bench_only.txt, so training never hears them.

The takes held back so far were recorded in one sitting, close to the microphone, in the same session
as the training takes; they say little about the far end of a room or a TV in the background.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wake_word_eval as ev  # noqa: E402

REC = Path(__file__).resolve().parents[1] / "wakeword_training" / "recordings"
DISTANCES = ("near", "2m", "far")
SOUNDS = ("quiet", "tv")
MIN_TAKES = 20


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--recordings", default=str(REC), help="the recordings folder (default: the training one)")
    args = ap.parse_args()
    phrases = sorted({f.stem.replace("_", " ") for f in Path(args.models).glob("*.onnx")})
    inputs: dict[str, list] = {"background": [], "positives": [], "contains": []}
    rows = {}
    for sound in SOUNDS:
        for distance in DISTANCES:
            name = f"room_{distance}_{sound}"
            folder = Path(args.recordings) / name
            takes = sorted(folder.rglob("*.wav")) if folder.is_dir() else []
            if not takes:
                rows[name] = "not recorded"
                continue
            audio, spans = ev._takes(folder)
            inputs["positives"].append((name, audio, spans))
            if len(takes) < MIN_TAKES * 2:
                rows[name] = f"only {len(takes)} takes; {MIN_TAKES} per phrase were asked for"
    sound_files = sorted((Path(args.recordings) / "room_sound").glob("score_*.wav"))
    if sound_files:
        import numpy as np
        import soundfile as sf

        parts = []
        for f in sound_files:
            audio, rate = sf.read(f, dtype="float32", always_2d=True)
            if rate != ev.SR:
                sys.exit(f"{f} is {rate} Hz; record room sound at {ev.SR} Hz")
            parts.append(audio.mean(axis=1))
        inputs["background"].append(("room_sound", np.concatenate(parts), None))
    if not inputs["positives"] and not inputs["background"]:
        print(json.dumps({"result": "nothing recorded yet", "conditions": rows}, indent=1))
        return 2
    report = asyncio.run(ev.evaluate(types.SimpleNamespace(models=args.models, stand_in=False, phrase=None),
                                     phrases, inputs))
    report["conditions"] = rows
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
