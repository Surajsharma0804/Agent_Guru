"""How well memory search finds what the owner told it, on the real embedder.

Usage:
    python scripts/memory_recall_eval.py

Stores the memories below in an isolated MemoryManager (nothing touches the
owner's memory.db), asks each question through MemoryManager.search, and
reports for every question what came back against what should have:

    found    every expected memory came back
    missed   an expected memory did not come back
    leaked   a memory came back that has nothing to do with the question

The questions are the kinds the assistant is asked in practice: a pet or a
person by name, a booking number, a model name, and questions that should
find nothing. Some are written to catch keyword matching going wrong: a
name shared by two different people, a name typed in lower case, and a
common word that appears in an unrelated memory.

Exits 1 if any question misses or leaks, so a change to search can be
compared run against run.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MEMORIES: dict[str, tuple[str, str]] = {
    "bruno": ("I have a golden retriever called Bruno and he hates thunderstorms", "Poor Bruno! A quiet room helps."),
    "priya": ("my sister Priya is getting married in December", "Congratulations to Priya!"),
    "bp": ("my doctor says my blood pressure is too high", "Let's keep an eye on it."),
    "pnr": ("my train PNR is 4521876390 for the Pune trip", "Noted, safe travels."),
    "mehta": ("Dr Mehta is my dentist, appointment on the 14th", "I'll keep that in mind."),
    "router": ("my wifi router is a TP-Link Archer C6", "Good router."),
    "peanut": ("I'm allergic to peanuts", "I'll remember that."),
    "kavitha": ("my manager Kavitha wants the Q3 deck by Friday", "Good luck with the deck."),
    "guitar": ("I started learning the guitar", "Nice!"),
    "laptop": ("my laptop is a Lenovo Legion with an RTX 3050", "Solid machine."),
    "ramesh": ("the plumber Ramesh charged 800 rupees", "That sounds fair."),
    "funfact": ("Tell me a fun fact", "Octopuses have three hearts. Anything fun happening?"),
    "sunil": ("my neighbour Sunil lends me his ladder", "Good neighbour."),
    "locker": ("the gym locker code is 7314", "Got it."),
    "mom": ("my mom's birthday is on the 3rd of March", "I'll remind you closer to it."),
}

#: (question, the memories it should find). An empty set: it should find none.
CASES: list[tuple[str, set[str]]] = [
    ("How is Bruno", {"bruno"}),
    ("What did Bruno do during the storm", {"bruno"}),
    ("Is Bruno scared of fireworks too", {"bruno"}),
    ("What is my PNR", {"pnr"}),
    ("Is 4521876390 confirmed", {"pnr"}),
    ("When is my Mehta appointment", {"mehta"}),
    ("Which Archer model do I have", {"router"}),
    ("What did Kavitha ask for", {"kavitha"}),
    ("What did Ramesh charge", {"ramesh"}),
    ("What GPU does my Legion have", {"laptop"}),
    ("Can I borrow Sunil's drill", {"sunil"}),
    ("What was the code 7314 for", {"locker"}),
    ("What's my locker code", {"locker"}),
    ("What should I gift my sister", {"priya"}),
    ("Any snack ideas for my hike", {"peanut"}),
    ("Any snack ideas for my Himalaya hike", {"peanut"}),
    ("how is bruno", {"bruno"}),
    ("When is mom's birthday", {"mom"}),
    # should find nothing
    ("Who is the prime minister of India", set()),
    ("Tell me about space", set()),
    ("What's the weather today", set()),
    ("Is Priyanka Chopra in a new film", set()),
    ("Who is Sunil Chhetri", set()),
    ("What is 800 times 3", set()),
    ("Play some music", set()),
]


async def run() -> int:
    from Agent_Guru.memory import memory_manager as mm

    mm.MemoryManager._resolve_db_path = staticmethod(lambda: Path(os.devnull))
    memory = mm.MemoryManager(platform_override="eval")
    by_text: dict[str, str] = {}
    for key, (said, reply) in MEMORIES.items():
        await memory.store_interaction("GURU", said, reply)
        by_text[said] = key
    found = missed = leaked = 0
    for question, want in CASES:
        got = {by_text[r["user_message"]] for r in await memory.search(question)}
        miss, leak = want - got, got - want
        missed += bool(miss)
        leaked += bool(leak)
        found += not miss and not leak
        mark = "ok    " if not miss and not leak else "WRONG "
        print(f"{mark}{question!r:44} want={sorted(want)} got={sorted(got)}")
    print(f"\n{found}/{len(CASES)} right, {missed} missed, {leaked} leaked")
    return 0 if found == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
