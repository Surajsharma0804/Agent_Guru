"""VQAEngine asks the local Ollama model with the image attached, and fails honestly.

The desktop path used to load a 7B LLaVA model through llama.cpp on every
question, without the projector llama.cpp needs to see an image, from a model
file and package that were not installed: every answer was "I cannot determine
that from the image", whether or not anything had looked. These run the real
request path against a local HTTP server standing in for Ollama's
/api/generate, so the payload and the error handling are checked without a
model. (Run against the real gemma4 separately; see the commit message.)
"""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from Agent_Guru.vision.vqa import _NOT_VISIBLE_PHRASE, VQAEngine


class FakeOllama:
    """A /api/generate endpoint that records requests and replies as told."""

    def __init__(self, reply="A red square.", status=200, delay=0.0):
        self.reply, self.status, self.delay = reply, status, delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, "body": body})
                time.sleep(outer.delay)
                data = json.dumps({"response": outer.reply}).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def image():
    img = np.zeros((48, 64, 3), dtype=np.uint8)
    img[8:40, 16:48] = (255, 0, 0)
    return img


@pytest.fixture
def ollama():
    server = FakeOllama()
    yield server
    server.close()


async def test_desktop_sends_the_image_to_the_verified_vision_model(ollama, image, monkeypatch):
    monkeypatch.delenv("AGENT_GURU_VQA_MODEL", raising=False)
    from Agent_Guru.reasoning.llm.generation import OLLAMA_THINK
    from Agent_Guru.vision.vqa import DEFAULT_VQA_MODEL

    result = await VQAEngine(ollama_url=ollama.url, timeout_s=10).answer(image, "What colour is the square?")

    assert result.answer == "A red square."  # nosec B101
    assert result.error is None and not result.not_visible  # nosec B101
    sent = ollama.requests[0]
    assert sent["path"] == "/api/generate"  # nosec B101
    body = sent["body"]
    # gemma3:4b, the model verified on real questions, not the conversation model.
    assert body["model"] == DEFAULT_VQA_MODEL == "gemma3:4b"  # nosec B101
    assert body["think"] is OLLAMA_THINK  # nosec B101
    assert body["stream"] is False  # nosec B101
    assert "What colour is the square?" in body["prompt"]  # nosec B101
    # The shared load options, so Ollama does not reload the model for this call.
    assert {"num_ctx", "num_gpu", "num_predict"} <= set(body["options"])  # nosec B101
    jpeg = base64.b64decode(body["images"][0])
    assert jpeg[:3] == b"\xff\xd8\xff"  # nosec B101  a real JPEG, not raw pixels


async def test_model_saying_it_cannot_tell_is_not_visible(image):
    server = FakeOllama(reply=f"{_NOT_VISIBLE_PHRASE}.")
    try:
        result = await VQAEngine(ollama_url=server.url, timeout_s=10).answer(image, "Whose house?")
    finally:
        server.close()
    assert result.not_visible and result.error is None and result.confidence == 0.0  # nosec B101


async def test_server_error_is_reported_as_an_error_not_as_unclear_image(image):
    server = FakeOllama(status=500, reply="model crashed")
    try:
        result = await VQAEngine(ollama_url=server.url, timeout_s=10).answer(image, "What is this?")
    finally:
        server.close()
    assert result.error and "500" in result.error  # nosec B101
    assert not result.not_visible and result.confidence == 0.0  # nosec B101


async def test_unreachable_server_is_an_error(image):
    result = await VQAEngine(ollama_url="http://127.0.0.1:9", timeout_s=5).answer(image, "What is this?")
    assert result.error and "ConnectionError" in result.error  # nosec B101


async def test_stalled_model_returns_at_the_timeout(image):
    server = FakeOllama(delay=8.0)
    started = time.perf_counter()
    try:
        result = await VQAEngine(ollama_url=server.url, timeout_s=1.0).answer(image, "What is this?")
    finally:
        server.close()
    assert result.error  # nosec B101
    assert time.perf_counter() - started < 4.0  # nosec B101


async def test_event_loop_keeps_running_during_inference(image):
    import asyncio

    server = FakeOllama(delay=1.0)
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        await VQAEngine(ollama_url=server.url, timeout_s=10).answer(image, "What is this?")
    finally:
        task.cancel()
        server.close()
    # A blocking call would have frozen the ticker for the whole second.
    assert ticks >= 10  # nosec B101


async def test_text_questions_are_grounded_in_awaited_ocr(image, monkeypatch, ollama):
    class FakeOCR:
        async def extract(self, img):
            return type("R", (), {"text": "EXIT 12"})()

    monkeypatch.setattr("Agent_Guru.vision.ocr.OCREngine", FakeOCR)
    result = await VQAEngine(ollama_url=ollama.url, timeout_s=10).answer(image, "What does the sign say?")
    assert result.grounded_in_ocr  # nosec B101
    assert "EXIT 12" in ollama.requests[0]["body"]["prompt"]  # nosec B101


def test_openai_client_is_built_once_with_the_deadline(monkeypatch, image):
    openai = pytest.importorskip("openai")
    built = []

    class FakeClient:
        def __init__(self, **kwargs):
            built.append(kwargs)
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(
                lambda **kw: type("R", (), {"choices": [type("Ch", (), {"message": type(
                    "M", (), {"content": "a square"})()})()]})())})()})()

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    engine = VQAEngine(platform="mobile", cloud_provider="openai", timeout_s=7.0)
    assert engine._call_cloud_vlm(image, "q") == "a square"  # nosec B101
    assert engine._call_cloud_vlm(image, "q") == "a square"  # nosec B101
    assert built == [{"timeout": 7.0, "max_retries": 0}]  # nosec B101


def test_gemini_default_is_not_the_retired_model():
    from Agent_Guru.vision.vqa import DEFAULT_GEMINI_MODEL

    assert DEFAULT_GEMINI_MODEL != "gemini-pro-vision"  # nosec B101


async def test_large_images_are_scaled_down_before_sending(ollama):
    # A full 3840x2160 image crashed Ollama's model runner on a 4 GB GPU, and
    # then the server; the vision tower works at 896 px anyway.
    import io

    from PIL import Image

    big = np.zeros((2160, 3840, 3), dtype=np.uint8)
    await VQAEngine(ollama_url=ollama.url, timeout_s=10).answer(big, "What is this?")
    sent = Image.open(io.BytesIO(base64.b64decode(ollama.requests[0]["body"]["images"][0])))
    assert max(sent.size) == 896  # nosec B101
    assert sent.size[0] / sent.size[1] == pytest.approx(3840 / 2160, rel=0.01)  # nosec B101


async def test_vision_model_can_differ_from_the_conversation_model(ollama, image, monkeypatch):
    # gemma4's vision answered wrongly under Ollama 0.34.4 while gemma3:4b
    # answered correctly, so the vision model is its own setting.
    monkeypatch.setenv("AGENT_GURU_VQA_MODEL", "gemma3:4b")
    await VQAEngine(ollama_url=ollama.url, timeout_s=10).answer(image, "What is this?")
    assert ollama.requests[0]["body"]["model"] == "gemma3:4b"  # nosec B101
