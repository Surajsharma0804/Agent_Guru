"""A reply that asks something is answered without the wake word.

A message draft asks "What would you like me to send John?" and then reads
the message back. The app used to go back to waiting for the wake word after
every reply, so one message took three wake words. main._answer_follow_ups
listens once more after a turn that is awaiting_reply. It runs in a fresh
interpreter, as importing main.py rewraps stdout (see
deployment/tests/test_entry_point.py), with the microphone and the pipeline
replaced by scripted ones.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_SCRIPT = """
import asyncio, json, sys
import main

class Result:
    def __init__(self, awaiting):
        self.awaiting_reply = awaiting

heard = json.loads(sys.argv[1])          # what the microphone returns, in order ("" = silence)
awaiting = json.loads(sys.argv[2])       # awaiting_reply of each follow-up turn, in order
calls = {"listen": 0, "turns": [], "tones": 0}

async def listen():
    calls["listen"] += 1
    return heard.pop(0).encode() if heard else b""

class Orch:
    async def run_pipeline(self, event):
        calls["turns"].append(event.decode())
        return Result(awaiting.pop(0))

def tone():
    calls["tones"] += 1

async def go():
    first = Result(json.loads(sys.argv[3]))
    last = await main._answer_follow_ups(Orch(), first, listen, lambda audio: audio, before_turn=tone)
    calls["last_awaiting"] = last.awaiting_reply
    print("RESULT " + json.dumps(calls))

asyncio.run(go())
"""


def _run(heard, awaiting, first_awaiting=True):
    out = subprocess.run(
        [sys.executable, "-c", _SCRIPT, json.dumps(heard), json.dumps(awaiting), json.dumps(first_awaiting)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    line = next((x for x in out.stdout.splitlines() if x.startswith("RESULT ")), None)
    assert line, out.stdout[-2000:] + out.stderr[-2000:]  # nosec B101
    return json.loads(line[len("RESULT "):])


def test_each_answer_is_taken_until_nothing_is_awaited():
    # "Send John a message." -> text -> "yes": two answers, no wake word.
    calls = _run(["I'll reach in 10 minutes", "yes"], [True, False])
    assert calls["turns"] == ["I'll reach in 10 minutes", "yes"]  # nosec B101
    assert calls["listen"] == 2 and calls["tones"] == 2  # nosec B101
    assert calls["last_awaiting"] is False  # nosec B101


def test_an_ordinary_reply_does_not_listen():
    calls = _run([], [], first_awaiting=False)
    assert calls["listen"] == 0 and calls["turns"] == []  # nosec B101


def test_silence_ends_the_listening():
    calls = _run([""], [])
    assert calls["listen"] == 1 and calls["turns"] == []  # nosec B101
    assert calls["last_awaiting"] is True  # nosec B101  the question stays open


def test_listening_is_bounded():
    # A question that is never settled is not listened for forever.
    calls = _run(["a", "b", "c", "d", "e", "f"], [True] * 6)
    assert len(calls["turns"]) == 4  # nosec B101
