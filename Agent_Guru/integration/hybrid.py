"""Answer a question about a long document: the local model reads it, a stronger model plans and answers.

"What does this 60-page contract say about notice periods?" did not fit:
the local model's window is 6k tokens, and sending the contract to a cloud
model sends the owner's document off the machine. This follows the shape
of local and cloud collaboration studied in the reference project
(Minions), written for Agent Guru:

1. plan: the planner turns the question into at most four short questions
   a small model can answer from one passage;
2. read: the local model answers each question against each passage,
   saying NONE when the passage does not say; only passages are read here;
3. answer: the planner answers the question from those findings alone,
   naming the passage numbers it used.

The planner is the cloud model (AGENT_GURU_CLOUD_MODEL, with
AGENT_GURU_ALLOW_CLOUD and its key) when the owner allows the cloud, and
the local model otherwise. Either way the document's text never leaves
the machine: the cloud sees the question and the short findings.

Served as the tool `read_long_document` (read-only) for files under the
owner's folders that pass the sensitive-file policy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

logger = logging.getLogger(__name__)

SERVER_NAME = "longdoc"
PASSAGE_CHARS = 3000
MAX_PASSAGES = 40
MAX_QUESTIONS = 4
Model = Callable[[str], Awaitable[str]]

_PLAN = (
    "A small model will read a long document one passage at a time. Break the owner's question into at most "
    "{n} short, self-contained questions it can answer from a single passage. Reply with a JSON list of "
    "strings only.\n\nQuestion: {question}"
)
_READ = (
    "Passage {i} of a document:\n<<<\n{passage}\n>>>\n\nAnswer each question from this passage only, quoting "
    "its words where you can. If the passage does not say, write NONE for that question. Reply as lines "
    "\"1: ...\", \"2: ...\".\n\n{questions}"
)
_ANSWER = (
    "Findings a reader took from passages of the owner's document (passage number, then what it found):\n"
    "{findings}\n\nAnswer the owner's question from these findings only, citing passage numbers like [P3]. If "
    "they do not answer it, say the document does not say.\n\nQuestion: {question}"
)


@dataclass(slots=True)
class LongAnswer:
    answer: str
    questions: list[str]
    findings: list[tuple[int, str]] = field(default_factory=list)
    passages: int = 0
    planner: str = "local"


def passages(text: str, size: int = PASSAGE_CHARS) -> list[str]:
    """Paragraph-aligned pieces of about *size* characters (a paragraph longer than that is cut)."""
    out: list[str] = []
    current = ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        while len(para) > size:
            out.append(para[:size])
            para = para[size:]
        if current and len(current) + len(para) + 2 > size:
            out.append(current)
            current = ""
        current = f"{current}\n\n{para}".strip() if para else current
    if current:
        out.append(current)
    return out


def _questions(reply: str, question: str) -> list[str]:
    match = re.search(r"\[.*\]", reply, re.DOTALL)
    try:
        items = json.loads(match.group(0)) if match else []
    except ValueError:
        items = []
    items = [str(q).strip() for q in items if isinstance(q, str) and str(q).strip()][:MAX_QUESTIONS]
    return items or [question]


async def answer(question: str, text: str, *, local: Model, planner: Model | None = None,
                 planner_name: str = "local", concurrency: int = 1) -> LongAnswer:
    """Plan with *planner* (the local model when None), read every passage with *local*, then answer."""
    plan = planner or local
    pieces = passages(text)[:MAX_PASSAGES]
    questions = _questions(await plan(_PLAN.format(n=MAX_QUESTIONS, question=question)), question)
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    gate = asyncio.Semaphore(max(1, concurrency))

    async def read(i: int, passage: str) -> tuple[int, str]:
        async with gate:
            reply = await local(_READ.format(i=i, passage=passage, questions=numbered))
        kept = [line.strip() for line in reply.splitlines()
                if line.strip() and not re.search(r":\s*NONE\b", line, re.IGNORECASE) and line.strip().upper() != "NONE"]
        return i, " ".join(kept)

    found = [f for f in await asyncio.gather(*(read(i, p) for i, p in enumerate(pieces, 1))) if f[1]]
    if not found:
        return LongAnswer("The document does not say.", questions, [], len(pieces), planner_name)
    findings = "\n".join(f"[P{i}] {text_[:600]}" for i, text_ in found)
    reply = await plan(_ANSWER.format(findings=findings, question=question))
    return LongAnswer(reply.strip(), questions, found, len(pieces), planner_name)


# --- the models, for the tool ----------------------------------------------

async def ollama_model(prompt: str) -> str:
    import httpx

    # The model and the load options come from reasoning/llm/generation.py, like every other client.
    # This call sent only a temperature, so Ollama loaded the model at the server's own context
    # (4096 here, 131072 where the desktop app's setting is high) instead of the 6144 the voice
    # answer uses, and reloaded it on every switch between the two: 7.4 s each way on gemma3:1b,
    # twice for each long-document question. Its default model was "gemma4", not the configured one.
    from Agent_Guru.reasoning.llm.generation import OLLAMA_THINK, ollama_options
    from Agent_Guru.reasoning.llm.generation import ollama_model as configured_model

    host = (os.environ.get("OLLAMA_HOST", "").strip() or "http://localhost:11434").rstrip("/")
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{host}/api/chat", json={
            "model": configured_model(), "stream": False, "think": OLLAMA_THINK,
            "messages": [{"role": "user", "content": prompt}],
            "options": ollama_options(num_predict=None, temperature=0.1)})
    response.raise_for_status()
    return str((response.json().get("message") or {}).get("content", ""))


def cloud_planner() -> tuple[Model | None, str]:
    """The cloud model as planner when the owner allows it and set its key; (None, "local") otherwise."""
    from Agent_Guru.llm.providers.openai_compatible import endpoint_for

    name = os.environ.get("AGENT_GURU_CLOUD_MODEL", "").strip()
    if not name or endpoint_for(name) is None:
        return None, "local"

    async def call(prompt: str) -> str:
        from Agent_Guru.llm.models import CompletionRequest, Message
        from Agent_Guru.llm.providers.openai_compatible import OpenAICompatibleAdapter

        response = await OpenAICompatibleAdapter().complete(CompletionRequest(
            model=name, messages=[Message(role="user", content=prompt)], temperature=0.1, max_tokens=800))
        return response.content or ""

    return call, name


def longdoc_server() -> ServerConfig:
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=900.0,
                        tools={"read_long_document": ToolRule(allow=True, risk=ToolRisk.READ_ONLY)})


class LongDocumentTools:
    def __init__(self, local: Model | None = None, planner: tuple[Model | None, str] | None = None) -> None:
        self._local = local or ollama_model
        self._planner = planner

    def tool_list(self) -> list[dict[str, Any]]:
        return [{
            "name": "read_long_document",
            "description": "Answer a question about one long document in the owner's folders (a contract, a report, "
                           "a manual) by reading all of it, passage by passage. Slow: use it for one long file, "
                           "not for short notes or the web.",
            "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {
                "path": {"type": "string", "minLength": 3, "maxLength": 500},
                "question": {"type": "string", "minLength": 3, "maxLength": 500}},
                "required": ["path", "question"], "additionalProperties": False},
        }]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        if name != "read_long_document":
            return f"unknown tool {name}", True, False
        from Agent_Guru.connectors.tools import _roots
        from Agent_Guru.platform.features.presentation import read_source_text
        from Agent_Guru.security.file_policy import sensitive_reason

        path = Path(os.path.expandvars(os.path.expanduser(str(arguments.get("path", "")).strip().strip('"')))).resolve()
        if reason := sensitive_reason(path):
            return f"That file is off limits ({reason}).", True, False
        if not any(path.is_relative_to(r.resolve()) for r in _roots()) or not path.is_file():
            return "Only an existing file under the owner's folders (FILES_ROOTS) can be read.", True, False
        text = await read_source_text(path)
        if not text.strip():
            return f"No text could be read from {path.name}.", True, False
        planner, planner_name = self._planner or cloud_planner()
        result = await answer(str(arguments.get("question", "")), text, local=self._local, planner=planner,
                              planner_name=planner_name)
        note = f" (read {result.passages} passages; planned and answered by {result.planner}; the text stayed on this machine)"
        return result.answer + note, False, False
