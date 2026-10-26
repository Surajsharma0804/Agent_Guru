"""Under pytest, nothing reaches a real model unless AGENT_GURU_LIVE_LLM=1.

With Ollama running, 19 tests used to send real prompts through the intent
fallback's own requests client, which no mock covered, and wait out its 135 s
timeout. The root conftest now refuses the Ollama port at the socket. The
refusal names the opt-in, which is how these tests tell it apart from Ollama
simply being stopped: both refuse, only the gate says why.
"""

from __future__ import annotations

import asyncio
import os
import socket

import httpx
import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_GURU_LIVE_LLM", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="AGENT_GURU_LIVE_LLM=1 lets the suite reach the model",
)

_GATE = "AGENT_GURU_LIVE_LLM=1"


def test_a_plain_socket_is_refused_by_the_gate():
    with socket.socket() as sock, pytest.raises(ConnectionRefusedError, match=_GATE):
        sock.settimeout(2)
        sock.connect(("127.0.0.1", 11434))


def test_the_requests_client_the_intent_fallback_uses_is_refused():
    with pytest.raises(requests.ConnectionError, match=_GATE):
        requests.get("http://127.0.0.1:11434/api/tags", timeout=2)


def test_an_asyncio_client_is_refused():
    async def ask():
        async with httpx.AsyncClient(timeout=2) as client:
            await client.get("http://localhost:11434/api/tags")

    with pytest.raises(httpx.ConnectError) as caught:
        asyncio.run(ask())
    # anyio replaces the message with "All connection attempts failed"; the
    # refusal it is reporting is further down the chain.
    assert any(_GATE in str(e) for e in _chain(caught.value))  # nosec B101


def _chain(exc: BaseException):
    seen: list[BaseException] = []
    todo = [exc]
    while todo:
        e = todo.pop()
        if e is None or any(e is s for s in seen):
            continue
        seen.append(e)
        todo += [e.__cause__, e.__context__, *getattr(e, "exceptions", ())]
    return seen
