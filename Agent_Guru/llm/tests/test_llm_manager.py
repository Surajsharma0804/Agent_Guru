"""LLMManager drives local Ollama only and says so.

It used to import cloud adapters that were removed from llm/providers, so a
cloud setting sent Ollama a Claude model name, the request failed and the
user got the canned rule-based reply.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from Agent_Guru.llm.llm_manager import LLMConfig, LLMManager, LLMProvider


@pytest.fixture
def ollama(monkeypatch):
    """Stands in for Ollama's /api/chat and records the model each request names."""
    models: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            models.append(body.get("model"))
            data = json.dumps({
                "model": body.get("model"), "message": {"role": "assistant", "content": "Paris."},
                "done": True, "done_reason": "stop", "prompt_eval_count": 12, "eval_count": 2,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma3:4b")
    yield models
    server.shutdown()
    server.server_close()


async def test_cloud_setting_still_sends_the_ollama_model(ollama, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 30)
    manager = LLMManager(LLMConfig(mode="cloud", provider=LLMProvider.ANTHROPIC), platform_override="windows")
    await manager.initialize()

    reply = await manager.generate_response("capital of France?", personality="guru")

    assert ollama == ["gemma3:4b"]  # nosec B101  was "claude-3-haiku-20240307"
    assert reply.content == "Paris." and not reply.used_fallback  # nosec B101


async def test_cloud_model_name_is_not_sent_to_ollama(ollama):
    manager = LLMManager(LLMConfig(cloud_model="gpt-4o-mini"), platform_override="windows")
    await manager.initialize()
    await manager.generate_response("hello", personality="maya")
    assert ollama == ["gemma3:4b"]  # nosec B101


def test_only_providers_that_can_be_reached_are_listed():
    assert LLMManager(platform_override="windows").get_supported_providers() == ["ollama"]  # nosec B101
    assert LLMManager(platform_override="android").get_supported_providers() == []  # nosec B101


async def test_cloud_key_test_is_refused_not_reported_invalid():
    manager = LLMManager(platform_override="windows")
    with pytest.raises(ValueError, match="local Ollama only"):
        await manager.test_api_key(LLMProvider.ANTHROPIC, "sk-ant-" + "y" * 30)


async def test_ollama_provider_test_reaches_ollama(ollama):
    manager = LLMManager(platform_override="windows")
    assert await manager.test_api_key(LLMProvider.OLLAMA, "") is True  # nosec B101
    assert ollama == ["gemma3:4b"]  # nosec B101
