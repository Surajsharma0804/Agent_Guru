"""Owner-tuned guidance in the system prompt: proposed from mistakes, kept only if it measurably helps.

self_improvement/prompt_evolution.py kept prompt versions but nothing
proposed one from what went wrong, nothing measured a version before it
was used, and there was no way back. Tuning here works in four steps:

1. Mistakes: the owner's turns marked wrong by voice ("that was wrong",
   "galat hai"), and the evaluation cases the current prompt fails.
2. Proposal: the local model writes at most three short rules that would
   have prevented those mistakes.
3. Gate: the evaluation set (integration/turn_eval_set.py, run by
   scripts/turn_eval.py) runs with the current guidance and with the
   candidate. The candidate is kept only if more cases pass, no case
   that passed now fails, and the median turn is not more than 20 %
   slower.
4. History: every candidate is kept with its scores; `rollback` returns
   to the previous adopted version.

The adopted guidance is appended to the system prompt unchanged from turn
to turn, so Ollama's prompt reuse keeps working.

    python -m Agent_Guru learn tune       propose, measure, adopt or reject
    python -m Agent_Guru learn show       the current guidance and history
    python -m Agent_Guru learn rollback   back to the previous version
    python -m Agent_Guru learn export     turns as a fine-tuning dataset (see turn_dataset.py)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

#: The candidate under evaluation; set only by tune() while it measures.
OVERRIDE_ENV = "AGENT_GURU_GUIDANCE_OVERRIDE"
_MAX_GUIDANCE = 600
_cache: tuple[float, str] = (-1.0, "")


def _path() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("prompt_tuning.json")


def _load() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return {"versions": [], "current": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"versions": [], "current": None}


def _save(state: dict[str, Any]) -> None:
    from Agent_Guru.utils.secure_file import secure_write_bytes

    secure_write_bytes(_path(), json.dumps(state, indent=2).encode("utf-8"))


def current_guidance() -> str:
    """The adopted guidance text, or "" (re-read only when the file changes)."""
    global _cache
    override = os.environ.get(OVERRIDE_ENV)
    if override is not None:
        return override
    path = _path()
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return ""
    if stamp == _cache[0]:
        return _cache[1]
    state = _load()
    text = next((v["text"] for v in state["versions"] if v["id"] == state.get("current")), "")
    _cache = (stamp, text)
    return text


def _mistakes(limit: int = 15) -> list[str]:
    from Agent_Guru.integration.turn_trace import TurnTraceStore
    from Agent_Guru.utils.path_utils import app_data_dir

    path = app_data_dir("turns.db", create=False)
    if not path.exists():
        return []
    wrong = [t for t in TurnTraceStore(path).recent(limit=2000) if t.rating is not None and t.rating < 0.5 and t.heard]
    return [f"Owner said: {t.heard!r}\nAssistant answered: {t.said[:300]!r} (marked wrong)" for t in wrong[:limit]]


async def _propose(examples: list[str], current: str) -> str:
    from Agent_Guru.llm.models import CompletionRequest, Message

    import main  # the same model loading the assistant uses

    runtime = main._load_llm()
    model = os.environ.get("OLLAMA_MODEL", "gemma4")
    prompt = (
        "You help tune a voice assistant. Below are answers it got wrong.\n\n" + "\n\n".join(examples) +
        (f"\n\nIts current extra guidance is:\n{current}" if current else "") +
        "\n\nWrite at most 3 short, general rules (one line each, imperative) that would have prevented these "
        "mistakes without hurting other answers. No examples, no names, no numbering words. Only the rules."
    )
    response = await runtime.complete(CompletionRequest(model=model, messages=[Message(role="user", content=prompt)],
                                                        temperature=0.3, max_tokens=200))
    lines = [ln.strip(" -*0123456789.)\t") for ln in (response.content or "").splitlines() if ln.strip()]
    return "\n".join(f"- {ln}" for ln in lines[:3])[:_MAX_GUIDANCE]


async def _evaluate(guidance: str) -> dict[str, Any]:
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("turn_eval", root / "scripts" / "turn_eval.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("turn_eval", module)
    spec.loader.exec_module(module)
    from Agent_Guru.integration.turn_eval_set import CASES

    os.environ[OVERRIDE_ENV] = guidance
    try:
        harness = module.Harness()
        await harness.start()
        rows = await module.run_cases(harness, CASES)
    finally:
        os.environ.pop(OVERRIDE_ENV, None)
    summary = module.summarize(rows)
    return {"passed": summary["passed"], "judged": summary["judged"], "median_turn_s": summary["median_s"]["turn"],
            "passing": sorted(" | ".join(r["said"]) for r in rows if r["passed"])}


def gate(baseline: dict[str, Any], candidate: dict[str, Any]) -> tuple[bool, str]:
    """Whether *candidate* may replace *baseline*, and why."""
    if candidate["passed"] <= baseline["passed"]:
        return False, f"passed {candidate['passed']} of {candidate['judged']}, not more than {baseline['passed']}"
    lost = sorted(set(baseline["passing"]) - set(candidate["passing"]))
    if lost:
        return False, f"{len(lost)} case(s) that passed now fail: {lost[0][:60]}"
    before, after = baseline.get("median_turn_s"), candidate.get("median_turn_s")
    if before and after and after > before * 1.2:
        return False, f"median turn {after:.1f}s against {before:.1f}s"
    return True, f"passed {candidate['passed']} of {candidate['judged']} against {baseline['passed']}"


async def tune() -> dict[str, Any]:
    """One round: propose from mistakes, measure against the current guidance, adopt or reject."""
    state = _load()
    current = current_guidance()
    baseline = await _evaluate(current)
    examples = _mistakes()
    if not examples:
        return {"adopted": False, "reason": "no turns are marked wrong yet; say 'that was wrong' after a bad answer"}
    candidate_text = await _propose(examples, current)
    if not candidate_text:
        return {"adopted": False, "reason": "the model proposed nothing"}
    combined = (current + "\n" + candidate_text).strip()[:_MAX_GUIDANCE]
    candidate = await _evaluate(combined)
    ok, why = gate(baseline, candidate)
    version = {"id": len(state["versions"]) + 1, "text": combined, "created_at": time.time(), "adopted": ok,
               "reason": why, "baseline": {k: baseline[k] for k in ("passed", "judged", "median_turn_s")},
               "score": {k: candidate[k] for k in ("passed", "judged", "median_turn_s")},
               "previous": state.get("current")}
    state["versions"].append(version)
    if ok:
        state["current"] = version["id"]
    _save(state)
    return {"adopted": ok, "reason": why, "guidance": combined}


def rollback() -> str:
    state = _load()
    current = next((v for v in state["versions"] if v["id"] == state.get("current")), None)
    if current is None:
        return "No tuned guidance is in use."
    state["current"] = current.get("previous")
    _save(state)
    return f"Back to version {state['current']}." if state["current"] else "Tuned guidance removed."


def run(argv: list[str]) -> int:
    import asyncio

    parser = argparse.ArgumentParser(prog="python -m Agent_Guru learn", description="Learn from the owner's turns.")
    parser.add_argument("action", choices=["tune", "show", "rollback", "export"])
    parser.add_argument("--out", default="", help="export: the JSONL file to write")
    args = parser.parse_args(argv)
    if args.action == "export":
        from Agent_Guru.self_improvement.turn_dataset import export

        report = export(Path(args.out) if args.out else None)
        print(json.dumps(report, indent=2))  # noqa: T201  the command's output
        return 0
    if args.action == "rollback":
        print(rollback())  # noqa: T201
        return 0
    if args.action == "show":
        state = _load()
        print(f"In use: version {state.get('current') or 'none'}\n{current_guidance() or '(no tuned guidance)'}\n")  # noqa: T201
        for v in state["versions"]:
            print(f"v{v['id']} {'adopted' if v['adopted'] else 'rejected'}: {v['reason']}")  # noqa: T201
        return 0
    result = asyncio.run(tune())
    print(("Adopted" if result["adopted"] else "Not adopted") + f": {result['reason']}")  # noqa: T201
    if result.get("guidance") and result["adopted"]:
        print(result["guidance"])  # noqa: T201
    return 0
