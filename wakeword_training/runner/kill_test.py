"""Kill the run at its riskiest moments, resume it each time, and check the result against a clean run.

    python kill_test.py --data <data folder> --work <new work folder> --reference <clean run's work folder>
                        [--models hey] [--scale 0.01]

A scheduler that ends a job at its time limit does this to the real run, so resume has to be
proven, not assumed. Each kill point waits for a line in <work>/run.log that marks the start
of a step, lets the step get partway, and kills the whole process tree: on Windows with
taskkill /F (there is no gentler signal); on Linux the way SLURM does at a time limit,
SIGTERM to the process group and SIGKILL 30 s later. The run is then started again with the
same command, until the next kill point or the end.

The resumed run must then match the clean reference run: the same clip files in every
generated folder (train.py's own clips, named at random, are compared by count), feature
arrays of the same shape, no partial files left anywhere, every clip readable and non-empty,
the Parler ledger agreeing with the clips on disk, and a report at the end.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# (name, a run.log line that marks the step's start, seconds to let the step run before the kill)
KILL_POINTS = [
    ("Parler generation", r"positive_train: \d+ of \d+ clips already done", 25),
    # The negative clips: at dry-run size the positives need no top-up, so the first version,
    # 10 s after "Generating positive clips", killed the features step instead.
    # Piper writes the dry run's 100 negatives in about 3 s, so the kill goes at the first batch,
    # which follows the header after a separator and the model-loading lines.
    ("train.py --generate_clips",
     r"Generating negative clips for training(?:\n(?!Generating).*){0,20}\nDEBUG:generate_samples:Batch 1/", 0),
    ("parallel features", r"augmenting and featurizing \d+ clips", 4),
    ("train.py --train_model", r"Starting training sequence 1", 3),
    ("benchmark", r"benchmark self-test:", 20),
]


def kill_tree(p):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    else:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
    p.wait()


def run_until(cmd, log, pattern, delay, out):
    """Start the run; kill it `delay` s after `pattern` first appears in the log.

    Returns (killed, exit code, last log lines)."""
    start = log.stat().st_size if log.exists() else 0
    kw = {"start_new_session": True} if os.name != "nt" else {}
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, **kw)
    seen = None
    while p.poll() is None:
        time.sleep(0.2)
        if pattern and seen is None and log.exists():
            with open(log, encoding="utf-8", errors="replace") as f:
                f.seek(start)
                if re.search(pattern, f.read()):
                    seen = time.time()
        if seen is not None and time.time() - seen >= delay:
            kill_tree(p)
            return True, p.returncode, _last_lines(log)
    return False, p.returncode, _last_lines(log)


def _last_lines(log, n=2):
    """Where the run was when it stopped, so a kill point that missed its step shows it."""
    if not log.exists():
        return []
    lines = [ln.strip() for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    return lines[-n:]


def files(folder, pattern="*"):
    return sorted(p.name for p in Path(folder).glob(pattern)) if Path(folder).is_dir() else []


def check(work, ref, models):
    import numpy as np
    import soundfile as sf
    problems, facts = [], {}
    leftovers = [str(p) for pat in ("*.tmp", "*.partial*", "*.zip.tmp") for p in work.rglob(pat)]
    if leftovers:
        problems.append(f"partial files left behind: {leftovers[:10]}")
    for name in models:
        for split in ("positive_train", "positive_test", "negative_train", "negative_test"):
            a, b = files(work / "models" / name / split, "*.wav"), files(ref / "models" / name / split, "*.wav")
            ours = [f for f in a if f.startswith(("pe_", "ph_", "pi_", "real_"))]
            theirs = [f for f in b if f.startswith(("pe_", "ph_", "pi_", "real_"))]
            if ours != theirs:
                problems.append(f"{name}/{split}: runner clips differ from the clean run "
                                f"(missing {sorted(set(theirs) - set(ours))[:5]}, extra {sorted(set(ours) - set(theirs))[:5]})")
            if len(a) != len(b):
                problems.append(f"{name}/{split}: {len(a)} clips, the clean run has {len(b)}")
            bad = []
            for f in a:
                try:
                    if sf.info(work / "models" / name / split / f).frames == 0:
                        bad.append(f)
                except Exception:
                    bad.append(f)
            if bad:
                problems.append(f"{name}/{split}: unreadable or empty clips {bad[:5]}")
            facts[f"{name}/{split}"] = len(a)
            fa = work / "models" / name / f"{split.replace('_', '_features_')}.npy"
            fb = ref / "models" / name / fa.name
            if fa.exists() and fb.exists():
                sa, sb = np.load(fa, mmap_mode="r").shape, np.load(fb, mmap_mode="r").shape
                if sa != sb:
                    problems.append(f"{fa.name} of {name}: shape {sa}, the clean run has {sb}")
            else:
                problems.append(f"{fa} or its reference is missing")
    ledger = json.loads((work / "state" / "parler_ledger.json").read_text(encoding="utf-8"))
    kept = sum(ledger["kept"].values())
    on_disk = sum(1 for n in models for s in ("positive_train", "positive_test")
                  for f in files(work / "models" / n / s, "*.wav") if f.startswith(("pe_", "ph_")))
    facts["parler ledger kept"], facts["parler clips on disk"] = kept, on_disk
    if kept != on_disk:
        problems.append(f"Parler ledger counts {kept} kept clips, {on_disk} are on disk")
    if not (work / "out" / "REPORT.md").exists():
        problems.append("no REPORT.md")
    return problems, facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--reference", required=True, help="work folder of a clean, uninterrupted run with the same options")
    ap.add_argument("--models", default="hey")
    ap.add_argument("--scale", default="0.01")
    a = ap.parse_args()
    work, data = Path(a.work), Path(a.data)
    assert not work.exists(), f"{work} exists; the kill test needs a fresh work folder"
    cmd = [sys.executable, str(data / "code" / "run.py"), "--data", str(data), "--work", str(work),
           "--models", a.models, "--scale", a.scale]
    sys.path.insert(0, str(data / "code"))
    from run import MODELS
    models = list(MODELS[a.models])
    work.mkdir(parents=True)
    log = work / "run.log"
    results = []
    with open(work / "kill_test_console.log", "ab") as out:
        for name, pattern, delay in KILL_POINTS:
            t0 = time.time()
            killed, code, last = run_until(cmd, log, pattern, delay, out)
            results.append({"point": name, "killed": killed, "exit": code, "seconds": round(time.time() - t0),
                            "last log lines": last})
            print(json.dumps(results[-1]), flush=True)
            if not killed:
                break           # the run ended before reaching this point: nothing more to kill
        t0 = time.time()
        _, code, _ = run_until(cmd, log, None, 0, out)
        results.append({"point": "final resume", "exit": code, "seconds": round(time.time() - t0)})
        print(json.dumps(results[-1]), flush=True)
    problems, facts = check(work, Path(a.reference), models)
    missed = [r["point"] for r in results if r.get("killed") is False]
    if missed:
        problems.append(f"kill points never reached (the step finished before the kill): {missed}")
    if results[-1]["exit"] != 0:
        problems.append(f"the final resume exited {results[-1]['exit']}")
    summary = {"kills": results, "facts": facts, "problems": problems}
    (work / "kill_test.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
