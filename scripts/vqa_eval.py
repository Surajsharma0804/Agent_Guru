"""Score the configured local vision model on Agent_Guru.vision.eval_set.

Usage:
    python scripts/vqa_eval.py [--json results.json]

Needs a running Ollama with the model AGENT_GURU_VQA_MODEL names (default
gemma3:4b). Each question goes through VQAEngine exactly as the assistant
sends it, so a score change means the model or the engine changed. A wrong
answer and an error are counted separately: an error is the pipeline
failing, a wrong answer is the model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Agent_Guru.vision.eval_set import IMAGES, QUESTIONS  # noqa: E402
from Agent_Guru.vision.vqa import VQAEngine, vqa_model  # noqa: E402


async def run() -> list[dict]:
    engine = VQAEngine(platform="desktop", timeout_s=180)
    images = {name: load() for name, load in IMAGES.items()}
    rows = []
    for q in QUESTIONS:
        started = time.perf_counter()
        result = await engine.answer(images[q.image], q.question)
        rows.append({
            "category": q.category, "image": q.image, "question": q.question, "expected": q.expected,
            "answer": result.answer, "error": result.error, "declined": result.not_visible,
            "correct": result.error is None and q.is_correct(result.answer),
            "seconds": round(time.perf_counter() - started, 2),
        })
        mark = "ERROR" if result.error else ("ok" if rows[-1]["correct"] else "wrong")
        print(f"{mark:5s} {q.category:8s} {q.question[:55]:55s} -> {(result.error or result.answer)[:70]!r}", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write per-question results here")
    args = parser.parse_args()
    rows = asyncio.run(run())
    correct = sum(r["correct"] for r in rows)
    errors = sum(r["error"] is not None for r in rows)
    declined = sum(r["declined"] and r["error"] is None for r in rows)
    print(f"\n{vqa_model()}: {correct}/{len(rows)} correct, {declined} declined, {errors} errors")
    if args.json:
        args.json.write_text(json.dumps({"model": vqa_model(), "results": rows}, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
