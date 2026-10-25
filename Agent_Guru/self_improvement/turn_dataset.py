"""The owner's good turns as a fine-tuning dataset, with personal details masked.

There was nothing to fine-tune on: turns were recorded, but no step
turned them into training data. export() writes the turns that went
right as chat-format JSONL, the shape LoRA trainers (transformers/peft,
unsloth, axolotl) read:

    {"messages": [{"role": "user", "content": ...}, {"role": "assistant", "content": ...}]}

Kept: turns the owner rated right by voice. A turn's outcome says only
that the pipeline finished, not that the answer was right: unrated
"success" turns used to be kept too, and on the owner's own records 3 of
the 5 pairs that made were wrong (two refusals of "keep an eye on the
weather in Delhi every hour" and a bare "Done."), which a fine-tune would
learn as the right reply. include_unrated adds unrated successes back,
still without replies that refuse, apologise or only acknowledge.

Always dropped: empty replies, exact repeats of a question already kept,
and any turn that names a sensitive path. Email addresses and phone
numbers are replaced by placeholders in both sides of every pair; the
file is written owner-only.

Training itself needs a CUDA GPU with more memory than this laptop's
4 GB (see the A100 plan); the file is the input to that run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d \-]{7,}\d(?!\w)")
#: A reply that says the assistant did not or could not answer, or that only acknowledges. Matched
#: against unrated replies only: the owner's yes outranks it.
_NOT_AN_ANSWER = re.compile(
    r"\b(?:i can'?t|i cannot|i couldn'?t|i'?m (?:not able|unable)|i am (?:not able|unable)|i don'?t (?:know|have)|"
    r"isn'?t allowed|not allowed|sorry)\b|^(?:done|okay|ok|sure|got it)[.!]?$",
    re.IGNORECASE,
)


def mask(text: str) -> str:
    return _PHONE.sub("<phone>", _EMAIL.sub("<email>", text))


def export(out: Path | None = None, *, limit: int = 100_000, include_unrated: bool = False,
           source: Path | None = None) -> dict[str, Any]:
    """Write the dataset; returns where, how many pairs and why the rest were left out."""
    from Agent_Guru.integration.turn_trace import TurnTraceStore
    from Agent_Guru.security.file_policy import sensitive_paths_in
    from Agent_Guru.utils.path_utils import app_data_dir
    from Agent_Guru.utils.secure_file import secure_write_bytes

    source = source or app_data_dir("turns.db", create=False)
    out = out or app_data_dir("training", "turns_sft.jsonl")
    report: dict[str, Any] = {"file": str(out), "pairs": 0, "left_out": {}}
    if not source.exists():
        report["left_out"]["no turn records"] = 1
        return report

    def skip(why: str) -> None:
        report["left_out"][why] = report["left_out"].get(why, 0) + 1

    seen: set[str] = set()
    lines: list[str] = []
    for turn in TurnTraceStore(source).recent(limit=limit):
        heard, said = (turn.heard or "").strip(), (turn.said or "").strip()
        if turn.rating is not None:
            if turn.rating < 0.5:
                skip("rated wrong")
                continue
        elif not include_unrated:
            skip("not rated right")
            continue
        elif turn.outcome != "success":
            skip("not rated and not a success")
            continue
        elif _NOT_AN_ANSWER.search(said):
            skip("not rated, and the reply refuses or only acknowledges")
            continue
        if not heard or not said:
            skip("empty question or reply")
            continue
        if sensitive_paths_in({"q": heard, "a": said}):
            skip("names a sensitive path")
            continue
        key = heard.lower()
        if key in seen:
            skip("repeat of a kept question")
            continue
        seen.add(key)
        lines.append(json.dumps({"messages": [{"role": "user", "content": mask(heard)},
                                              {"role": "assistant", "content": mask(said)}]}, ensure_ascii=False))
    out.parent.mkdir(parents=True, exist_ok=True)
    secure_write_bytes(out, ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
    report["pairs"] = len(lines)
    return report
