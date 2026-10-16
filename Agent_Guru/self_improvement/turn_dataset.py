"""The owner's good turns as a fine-tuning dataset, with personal details masked.

There was nothing to fine-tune on: turns were recorded, but no step
turned them into training data. export() writes the turns that went
right as chat-format JSONL, the shape LoRA trainers (transformers/peft,
unsloth, axolotl) read:

    {"messages": [{"role": "user", "content": ...}, {"role": "assistant", "content": ...}]}

Kept: turns rated right by voice, and turns whose outcome was success
that were not rated wrong. Dropped: empty or failed replies, exact
repeats of a question already kept, and any turn that names a sensitive
path. Email addresses and phone numbers are replaced by placeholders in
both sides of every pair; the file is written owner-only.

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


def mask(text: str) -> str:
    return _PHONE.sub("<phone>", _EMAIL.sub("<email>", text))


def export(out: Path | None = None, *, limit: int = 100_000) -> dict[str, Any]:
    """Write the dataset; returns where, how many pairs and why the rest were left out."""
    from Agent_Guru.integration.turn_trace import TurnTraceStore
    from Agent_Guru.security.file_policy import sensitive_paths_in
    from Agent_Guru.utils.path_utils import app_data_dir
    from Agent_Guru.utils.secure_file import secure_write_bytes

    source = app_data_dir("turns.db", create=False)
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
        good = (turn.rating is not None and turn.rating >= 0.5) or (turn.outcome == "success" and turn.rating is None)
        if not good:
            skip("not marked right and not a success")
            continue
        heard, said = (turn.heard or "").strip(), (turn.said or "").strip()
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
