"""Score the assistant on Agent_Guru.integration.turn_eval_set and time every stage of its turns.

Usage:
    python scripts/turn_eval.py [--json results.json] [--rated]
    python scripts/turn_eval.py --latency [--runs 5] [--json bench.json]

Needs a running Ollama with the configured model. Every case goes through
IntegrationOrchestrator.run_pipeline with the real model, the production
policy, the real intent recognizer, real long-term memory and real turn
records. What is not real, and why:

- Scoring mode types the words in, so a wrong transcription cannot be
  mistaken for a wrong answer. --latency speaks them instead (Kokoro voice,
  Whisper transcription) to time speech recognition.
- Actions are recorded, not performed: an evaluation must not open apps or
  send messages. Real actions are verified by their own tests.
- Speech is synthesized but not played. Time to first audio is when the
  first sentence's audio is ready, not when the speaker makes a sound.

Memory, user facts, reaction rules and turn records live in a temporary
folder for the run, never in the owner's own files. --rated reads the
owner's turns.db (read only) and re-asks the turns marked by voice.

Numbers are reported as measured, or as unavailable when this run could not
measure them; nothing is estimated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_RUN_DIR = Path(tempfile.mkdtemp(prefix="guru_turn_eval_"))
# Nothing may play aloud; synthesis still runs for real.
sys.modules["sounddevice"] = types.SimpleNamespace(play=lambda *a, **k: None, wait=lambda: None)

import numpy as np  # noqa: E402

import main  # noqa: E402
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent  # noqa: E402
from Agent_Guru.integration.turn_eval_set import (  # noqa: E402
    ANSWER_FIRST_CHARS,
    CASES,
    NEEDY_PHRASES,
    SMALL_TALK_OPENING,
    TurnCase,
)
from Agent_Guru.integration.turn_trace import TurnTraceStore  # noqa: E402
from Agent_Guru.memory.memory_manager import MemoryManager  # noqa: E402
from Agent_Guru.platform.features import reaction_rules, user_memory  # noqa: E402

LATENCY_QUESTIONS = (
    "what is the capital of France",
    "how many days are in a week",
    "which planet is closest to the sun",
)
MARKDOWN = re.compile(r"(?m)^\s*(?:[-*•]|\d+\.)\s|\*\*|^#")


def _isolate_stores() -> None:
    user_memory._user_memory = user_memory.UserMemory(_RUN_DIR / "user_memory.json")
    reaction_rules._rule_store = reaction_rules.ReactionRuleStore(_RUN_DIR / "reaction_rules.json")
    MemoryManager._resolve_db_path = staticmethod(lambda: _RUN_DIR / "memory.db")


class _Actions:
    """Takes every action call, does nothing, and says it worked."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def call(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            return types.SimpleNamespace(success=True, message="ok", error=None)

        async def send_message(*args: Any, **kwargs: Any) -> str:
            # OSController.send_message is a coroutine that reports what
            # WhatsApp showed. Nothing is sent here, so nothing is confirmed.
            self.calls.append(name)
            return "unverified"

        return send_message if name == "send_message" else call


class _TypedSpeech:
    """For scoring: the words are typed in, and speech is synthesized as silence."""

    def __init__(self) -> None:
        self.next_text = ""

    async def transcribe(self, audio: Any) -> Any:
        return types.SimpleNamespace(text=self.next_text, language="en", language_probability=1.0)

    def synthesize_to_array(self, sentence: str, personality: Any) -> Any:
        return np.zeros(800, np.float32), 16000


class Harness:
    def __init__(self, speech_engine: Any = None) -> None:
        _isolate_stores()
        self.llm = main._load_llm()
        self.policy = main._load_policy()
        # The real SpeechEngine goes to the orchestrator as it is, so its
        # own audio checks and transcription path are what get timed.
        self.typed = _TypedSpeech()
        self.speech = speech_engine if speech_engine is not None else self.typed
        self.store = TurnTraceStore(_RUN_DIR / "turns.db")
        self.memory = MemoryManager()

    async def start(self) -> None:
        await self.memory.initialize()

    def session(self) -> IntegrationOrchestrator:
        orch = IntegrationOrchestrator(
            speech_engine=self.speech, vision_engine=None, llm_runtime=self.llm, platform_controller=_Actions(),
            agent_orchestrator=None, memory=self.memory, reasoning=None, security=None, policy=self.policy,
            avatar=None, deployment=None, gpu_pool=None, trace_store=self.store,
        )

        async def no_web(transcript: str, intent: Any) -> str:
            return ""

        async def no_filler(*a: Any, **k: Any) -> None:
            return None

        # Web results change by the hour; scoring must not depend on them.
        orch._fetch_web_context = no_web
        orch._play_filler = no_filler
        return orch

    async def say(self, orch: IntegrationOrchestrator, text: str, audio: bytes | None = None) -> Any:
        self.typed.next_text = text
        event = WakeWordEvent(wake_word="Hey Guru", audio=audio if audio is not None else np.zeros(1600, np.float32).tobytes())
        result = await orch.run_pipeline(event)
        return result, self.store.recent(limit=1)[0]


def _latency(record: Any) -> dict[str, Any]:
    stages = {s.name: round(s.seconds, 3) for s in record.stages}
    answer = next((s.detail for s in record.stages if s.name == "answer_spoken"), {})
    return {
        "turn_s": round(record.seconds, 3),
        "stages_s": stages,
        "first_text_s": answer.get("first_text_s"),
        "model_load_s": answer.get("load_s"),
        "prompt_s": answer.get("prompt_s"),
        "decode_s": answer.get("decode_s"),
        "tokens_per_s": answer.get("tokens_per_s"),
        "first_audio_s": record.details.get("first_audio_s"),
    }


def score(case: TurnCase, result: Any, record: Any) -> dict[str, Any]:
    reply = record.said or ""
    checks: dict[str, bool | None] = {"reply": case.reply_ok(reply)}
    checks["intent"] = bool(re.search(case.intent, result.intent or "")) if case.intent else None
    status = result.action_status.value if result.action_status else None
    checks["status"] = (status == case.status) if case.status else None
    answer_at = None
    if case.answer_first and case.correct:
        found = re.search(case.correct, reply, re.IGNORECASE)
        answer_at = found.start() if found else None
        checks["answer_first"] = answer_at is not None and answer_at <= ANSWER_FIRST_CHARS
    else:
        checks["answer_first"] = None
    question = case.category in {"first_question", "factual", "follow_up", "memory_session", "memory_long_term"}
    checks["no_small_talk"] = not SMALL_TALK_OPENING.match(reply) if question else None
    checks["persona"] = bool(reply) and not MARKDOWN.search(reply) and not NEEDY_PHRASES.search(reply) if reply else None
    judged = [v for v in checks.values() if v is not None]
    return {
        "category": case.category, "said": list(case.said), "earlier_session": list(case.earlier_session),
        "reply": reply, "intent": result.intent, "status": status, "answer_at": answer_at,
        "checks": checks, "passed": all(judged) if judged else None, "error": result.error,
        "latency": _latency(record),
    }


async def run_cases(h: Harness, cases: tuple[TurnCase, ...]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        if case.earlier_session:
            earlier = h.session()
            for text in case.earlier_session:
                await h.say(earlier, text)
        orch = h.session()
        for text in case.said:
            result, record = await h.say(orch, text)
        row = score(case, result, record)
        rows.append(row)
        mark = "pass" if row["passed"] else ("FAIL" if row["passed"] is False else "info")
        failed = [k for k, v in row["checks"].items() if v is False]
        print(f"{mark:4s} {case.category:16s} {case.said[-1][:42]:42s} {('failed: ' + ','.join(failed)) if failed else ''}"
              f" -> {row['reply'][:70]!r}", flush=True)
    return rows


def rated_cases() -> tuple[TurnCase, ...]:
    """The owner's turns marked right or wrong, re-asked as first questions (owner's turns.db, read only)."""
    from Agent_Guru.utils.path_utils import app_data_dir

    path = app_data_dir("turns.db", create=False)
    if not path.exists():
        return ()
    turns = [t for t in TurnTraceStore(path).recent(limit=10_000) if t.rating is not None and t.heard]
    return tuple(TurnCase(f"rated_{'right' if t.rating else 'wrong'}", (t.heard,)) for t in turns)


def _median(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 3) if values else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, list[int]] = {}
    for r in rows:
        entry = by_category.setdefault(r["category"], [0, 0])
        if r["passed"] is not None:
            entry[0] += bool(r["passed"])
            entry[1] += 1
    by_check: dict[str, list[int]] = {}
    for r in rows:
        for name, ok in r["checks"].items():
            if ok is not None:
                entry = by_check.setdefault(name, [0, 0])
                entry[0] += ok
                entry[1] += 1
    lat = [r["latency"] for r in rows]
    return {
        "passed": sum(1 for r in rows if r["passed"]), "judged": sum(1 for r in rows if r["passed"] is not None),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in by_category.items()},
        "by_check": {k: f"{v[0]}/{v[1]}" for k, v in by_check.items()},
        "median_s": {
            "turn": _median([x["turn_s"] for x in lat]),
            "first_text": _median([x["first_text_s"] for x in lat]),
            "intent": _median([x["stages_s"].get("intent") for x in lat]),
            "policy": _median([x["stages_s"].get("policy") for x in lat]),
            "memory": _median([x["stages_s"].get("memory") for x in lat]),
        },
    }


async def run_latency(runs: int) -> dict[str, Any]:
    from Agent_Guru.speech.models import PersonalityType

    engine = main._load_speech()
    await asyncio.to_thread(engine.initialize)
    h = Harness(speech_engine=engine)
    await h.start()
    clips = {}
    for text in LATENCY_QUESTIONS:
        audio, rate = await asyncio.to_thread(engine.synthesize_to_array, text, PersonalityType.GURU)
        if rate != 16000:
            audio = np.interp(np.linspace(0, len(audio), int(len(audio) * 16000 / rate), endpoint=False),
                              np.arange(len(audio)), audio).astype(np.float32)
        clips[text] = audio.astype(np.float32).tobytes()
    rows = []
    for run in range(runs):
        for text in LATENCY_QUESTIONS:
            orch = h.session()
            started = time.perf_counter()
            result, record = await h.say(orch, text, audio=clips[text])
            row = _latency(record)
            row.update(question=text, run=run, heard=record.heard, wall_s=round(time.perf_counter() - started, 3))
            rows.append(row)
            print(f"run {run} {text[:36]:36s} heard={record.heard[:36]!r:40s} stt={row['stages_s'].get('stt')}"
                  f" first_text={row['first_text_s']} first_audio={row['first_audio_s']} turn={row['turn_s']}", flush=True)
    await h.memory.shutdown()
    summary = h.store.stage_summary()
    measured = {
        "stt_s": summary.get("stt"), "intent_s": summary.get("intent"), "policy_s": summary.get("policy"),
        "memory_s": summary.get("memory"), "answer_and_speech_s": summary.get("answer_spoken"),
        "first_text_s": _median([r["first_text_s"] for r in rows]),
        "model_load_s": _median([r["model_load_s"] for r in rows]),
        "first_audio_ready_s": _median([r["first_audio_s"] for r in rows]),
        "turn_s": _median([r["turn_s"] for r in rows]),
    }
    unavailable = {
        "wake_word_and_command_capture": "not run: audio is given to the pipeline, the microphone is not used",
        "speaker_output": "not measured: audio is synthesized but not played",
    }
    return {"runs": runs, "rows": rows, "measured": measured, "unavailable": unavailable}


def main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write the full results here")
    parser.add_argument("--rated", action="store_true", help="also re-ask the turns the owner rated by voice")
    parser.add_argument("--latency", action="store_true", help="time real speech in and out instead of scoring")
    parser.add_argument("--runs", type=int, default=5, help="latency runs per question")
    args = parser.parse_args()

    if args.latency:
        report = asyncio.run(run_latency(args.runs))
        print("\nmeasured:", json.dumps(report["measured"], indent=2))
        print("unavailable:", json.dumps(report["unavailable"], indent=2))
    else:
        async def go() -> list[dict[str, Any]]:
            h = Harness()
            await h.start()
            try:
                return await run_cases(h, CASES + (rated_cases() if args.rated else ()))
            finally:
                await h.memory.shutdown()

        rows = asyncio.run(go())
        summary = summarize(rows)
        report = {"model": _model_name(), "summary": summary, "rows": rows}
        print(f"\n{summary['passed']}/{summary['judged']} cases passed")
        print("by category:", summary["by_category"])
        print("by check:", summary["by_check"])
        print("median seconds:", summary["median_s"])
    report["run_dir"] = str(_RUN_DIR)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0


def _model_name() -> str:
    from Agent_Guru.reasoning.llm.generation import ollama_model

    return ollama_model()


if __name__ == "__main__":
    sys.exit(main_cli())
