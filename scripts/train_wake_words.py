"""Train the Hey Guru and Hey Maya wake word models, measure them as the assistant runs them, and install them.

    python scripts/train_wake_words.py --data E:\\agent_guru_wakeword_data --work E:\\agent_guru_wakeword_work
        [--heldout <folder of takes>] [--contains <folder of takes>] [--background a.npy ...]
        [--scale 0.01] [--install]

Steps, each resumable by running the same command again:
  1. verify   the portable data folder is complete (its code/verify.py hashes every file)
  2. train    its code/run.py: synthetic positives (Parler TTS, 21 Indian English and 2 Hindi voices,
              plus Piper/LibriTTS-R), negatives (ACAV100M speech and sound features, Svarah's Indian English
              speakers, near-miss phrases), augmentation with room impulses and AudioSet/FMA background,
              openWakeWord training, ONNX export checks, and its own benchmark (<work>/out/REPORT.md)
  3. evaluate scripts/wake_word_eval.py runs the trained models through the assistant's WakeWordDetector
              in its 1.5 s chunks: false accepts per hour on --background, false rejects and latency on
              --heldout, and how often --contains sentences wake it (<work>/out/app_eval.json)
  4. install  only with --install and only after --heldout was measured: copies hey_guru.onnx and
              hey_maya.onnx to %LOCALAPPDATA%\\agent_guru\\wake_models, where the detector looks

--heldout must be recordings that training never saw: record them after the data folder was packed,
under a speaker name of their own (docs/developer/wake-word-training.md says how). Without them there is
no measurement of the models on a real voice in a real room, and nothing is installed.

--python is the training environment (default wakeword_training/venv-313, Python 3.13 with torch);
--eval-python one with openwakeword installed (default wakeword_training/venv-oww).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - runs this repository's own scripts with chosen interpreters
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENVS = ROOT / "wakeword_training"
BIN = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
MODELS = ("hey_guru", "hey_maya")


def _run(step: str, command: list[str]) -> None:
    print(f"== {step}: {' '.join(command)}", flush=True)
    done = subprocess.run(command, check=False)  # noqa: S603  # nosec B603 - fixed scripts, chosen interpreters
    if done.returncode != 0:
        sys.exit(f"{step} failed (exit {done.returncode}); fix that and run the same command again")


def _wake_models_dir() -> Path:
    sys.path.insert(0, str(ROOT))
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("wake_models")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--data", required=True, help="the portable data folder (agent_guru_wakeword_data)")
    parser.add_argument("--work", required=True, help="where clips, features, models and reports go")
    parser.add_argument("--scale", type=float, default=1.0, help="0.01 for a dry run of the pipeline")
    parser.add_argument("--heldout", nargs="*", default=[], help="folders of wake takes training never saw")
    parser.add_argument("--contains", nargs="*", default=[], help="folders of sentences holding a wake phrase")
    parser.add_argument("--background", nargs="*", default=[], help="wake-free audio (.npy) for false accepts")
    parser.add_argument("--python", default=str(VENVS / "venv-313" / BIN), help="training interpreter")
    parser.add_argument("--eval-python", default=str(VENVS / "venv-oww" / BIN), help="interpreter with openwakeword")
    parser.add_argument("--install", action="store_true", help="copy the models where the assistant looks")
    args = parser.parse_args()
    data, work = Path(args.data), Path(args.work)

    _run("verify", [args.python, str(data / "code" / "verify.py"), "--data", str(data)])
    _run("train", [args.python, str(data / "code" / "run.py"), "--data", str(data), "--work", str(work),
                   "--models", "hey", "--scale", str(args.scale)])
    models = work / "models"
    missing = [m for m in MODELS if not (models / f"{m}.onnx").is_file()]
    if missing:
        sys.exit(f"training finished without {', '.join(missing)}.onnx in {models}")

    out = work / "out" / "app_eval.json"
    command = [args.eval_python, str(ROOT / "scripts" / "wake_word_eval.py"), "--models", str(models), "--out", str(out)]
    for flag, values in (("--background", args.background), ("--positives", args.heldout), ("--contains", args.contains)):
        if values:
            command += [flag, *values]
    env_path = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(ROOT) + (os.pathsep + env_path if env_path else "")
    _run("evaluate", command)
    report = json.loads(out.read_text(encoding="utf-8"))
    print(json.dumps({k: report[k] for k in ("background", "positives", "contains") if report.get(k)}, indent=1))

    if not args.install:
        print(f"Not installed. Read {work / 'out' / 'REPORT.md'} and {out}; then rerun with --install.")
        return 0
    if not report.get("positives"):
        sys.exit("Not installed: no --heldout recordings were measured, so nothing says these models hear you.")
    target = _wake_models_dir()
    for m in MODELS:
        shutil.copy2(models / f"{m}.onnx", target / f"{m}.onnx")
    print(f"Installed in {target}. The assistant's startup log will say backend=openwakeword when it uses them;"
          " openwakeword must be installed in its environment (pip install openwakeword==0.6.0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
