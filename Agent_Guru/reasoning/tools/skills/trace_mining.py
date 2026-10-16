"""Tool sequences the owner's turns repeat: candidates for a skill.

Turn records keep every tool call (mcp_call stages, in order), but
nothing looked across turns for the same steps done again and again,
such as searching mail and then reading the first result, or looking up
the weather and then scheduling a check, which is what a skill would do
in one step and one confirmation.

repeated_sequences() takes each turn's successful tool calls in order,
counts every run of two or three consecutive calls across turns, and
returns those seen in at least min_turns different turns, with an
example of what the owner said. Read-only: it suggests, it installs
nothing. `python -m Agent_Guru skills discover` prints the report.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Pattern:
    steps: tuple[str, ...]
    turns: int
    example: str


def _calls(turn: Any) -> list[str]:
    stages = sorted((s for s in turn.stages if s.name == "mcp_call"), key=lambda s: s.started_at)
    return [f"{s.detail.get('server')}/{s.detail.get('tool')}" for s in stages
            if (s.detail or {}).get("status") == "success"]


def repeated_sequences(turns: list[Any], *, min_turns: int = 3, lengths: tuple[int, ...] = (2, 3)) -> list[Pattern]:
    """Runs of consecutive tool calls that appear in at least *min_turns* turns, most frequent first."""
    seen_in: Counter[tuple[str, ...]] = Counter()
    example: dict[tuple[str, ...], str] = {}
    for turn in turns:
        calls = _calls(turn)
        found: set[tuple[str, ...]] = set()
        for n in lengths:
            for i in range(len(calls) - n + 1):
                found.add(tuple(calls[i:i + n]))
        for steps in found:
            seen_in[steps] += 1
            example.setdefault(steps, turn.heard)
    patterns = [Pattern(steps, count, example[steps]) for steps, count in seen_in.items() if count >= min_turns]
    # A longer run that is as frequent as its parts says more than the parts.
    longest: dict[int, list[Pattern]] = defaultdict(list)
    for p in patterns:
        longest[p.turns].append(p)
    kept = [p for p in patterns if not any(
        q is not p and len(q.steps) > len(p.steps) and q.turns == p.turns and _contains(q.steps, p.steps)
        for q in longest[p.turns])]
    return sorted(kept, key=lambda p: (-p.turns, -len(p.steps)))


def _contains(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    n = len(shorter)
    return any(longer[i:i + n] == shorter for i in range(len(longer) - n + 1))


def report(limit: int = 2000) -> str:
    from Agent_Guru.integration.turn_trace import TurnTraceStore
    from Agent_Guru.utils.path_utils import app_data_dir

    path = app_data_dir("turns.db", create=False)
    if not path.exists():
        return "No turn records yet."
    turns = TurnTraceStore(path).recent(limit=limit)
    patterns = repeated_sequences(turns)
    if not patterns:
        return f"No tool sequence repeats in 3 or more of the last {len(turns)} turns yet."
    return "\n".join(f"{p.turns:3d} turns  {' -> '.join(p.steps)}   e.g. {p.example[:60]!r}" for p in patterns[:20])
