"""A spoken question about the screen goes through the live pipeline to the vision model.

Before, "describe my screen" was classified as screen_read, which skips the
LLM, and nothing answered it: the assistant said "Done.". Other screen
questions went to the LLM with only the screen's text. These run the real
IntegrationOrchestrator.run_pipeline from transcript to spoken reply, with the
microphone, LLM, speaker and screen replaced by fakes and Ollama by a local
HTTP server, so intent detection, LLM gating, policy, action dispatch and VQA
all run as they do in the application.
"""

from __future__ import annotations

import asyncio
import base64
import glob
import io
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
from PIL import Image

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.platform.features import screen_reader
from Agent_Guru.vision.vqa import VQAEngine


class VisionServer:
    """Stands in for Ollama's /api/generate; answers with the question it was asked."""

    def __init__(self, status=200, delay=0.0):
        self.status, self.delay = status, delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                time.sleep(outer.delay)
                question = body["prompt"].rsplit("Question: ", 1)[-1]
                data = json.dumps({"response": f"Seen: {question}"}).encode()
                try:
                    self.send_response(outer.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class FakeScreen:
    """Platform controller whose take_screenshot writes a known image."""

    def __init__(self, size=(640, 360)):
        self.size = size
        self.saved: list[str] = []

    def take_screenshot(self, save_path=None, region=None):
        img = Image.new("RGB", self.size, (200, 30, 30))
        img.save(save_path)
        self.saved.append(save_path)
        return type("Result", (), {"success": True, "message": ""})()


class FakeSpeech:
    def __init__(self, transcript):
        self.transcript = transcript

    async def transcribe(self, audio):
        # Async: the pipeline hands it the audio directly. A sync fake goes
        # through audio validation first, which rejects test silence.
        return type("R", (), {"text": self.transcript, "language": "en", "language_probability": 0.99})()


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def infer(self, *args, **kwargs):
        self.calls += 1
        return "The capital of France is Paris."

    generate = infer


class AllowPolicy:
    def evaluate(self, intent):
        return True


@pytest.fixture
def vision(monkeypatch):
    servers = []

    def make(timeout_s=5.0, **kwargs):
        server = VisionServer(**kwargs)
        servers.append(server)
        monkeypatch.setattr(screen_reader, "_engine", VQAEngine(ollama_url=server.url, timeout_s=timeout_s))
        return server

    # UI Automation runs PowerShell; the flow is tested without it.
    monkeypatch.setattr(screen_reader, "_read_via_uia", lambda max_chars: None)
    yield make
    for s in servers:
        s.close()


async def _speak(transcript, screen=None):
    """Run the real pipeline for one spoken transcript; return (spoken text, llm, screen)."""
    llm, screen = FakeLLM(), screen or FakeScreen()
    orch = IntegrationOrchestrator(
        speech_engine=FakeSpeech(transcript), vision_engine=None, llm_runtime=llm,
        platform_controller=screen, agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=AllowPolicy(), avatar=None, deployment=None, gpu_pool=None,
    )
    spoken: list[str] = []

    async def capture_tts(text, personality):
        spoken.append(text)

    async def no_filler(*args, **kwargs):
        return None

    async def no_browser():
        raise RuntimeError("tests never start a browser")

    # Nothing may play through the speakers: the filler clip and the reply
    # are both replaced. A misrouted question must not open a browser
    # either: the old recogniser sent "which application is open on my
    # screen" to open_url, which starts the real BrowserManager when
    # Playwright is installed. FakeScreen has no open_url, so the fallback
    # cannot reach the OS browser.
    orch._stage_tts = capture_tts
    orch._play_filler = no_filler
    orch._get_browser_mgr = no_browser
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return (spoken[0] if spoken else None), llm, screen


async def test_screen_question_reaches_the_vision_model_and_is_spoken(vision):
    server = vision()
    spoken, llm, screen = await _speak("what is on my screen")

    assert len(server.requests) == 1  # nosec B101
    assert spoken == "Seen: what is on my screen"  # nosec B101
    assert llm.calls == 0  # nosec B101  the LLM is not consulted for a screen question
    sent = Image.open(io.BytesIO(base64.b64decode(server.requests[0]["images"][0])))
    assert sent.getpixel((10, 10))[0] > 150  # nosec B101  the captured (red) screen reached the model


async def test_text_question_does_not_invoke_vision(vision):
    server = vision()
    spoken, llm, screen = await _speak("what is the capital of France")

    assert server.requests == [] and screen.saved == []  # nosec B101
    assert llm.calls == 1  # nosec B101


@pytest.mark.parametrize("transcript", [
    "describe my screen", "what am I looking at", "read the text on my screen",
    "what color is the window on my screen",
    # These contain "open", and the web rule used to take them as open_url.
    "which application is open on my screen", "how many tabs are open on my screen",
])
async def test_every_screen_phrase_is_answered_by_vision(vision, transcript):
    server = vision()
    spoken, llm, _ = await _speak(transcript)
    # "describe my screen" used to be answered "Done.".
    assert spoken == f"Seen: {transcript}"  # nosec B101
    assert len(server.requests) == 1 and llm.calls == 0  # nosec B101


async def test_large_screen_is_scaled_before_sending(vision):
    server = vision()
    await _speak("what is on my screen", FakeScreen(size=(3840, 2160)))
    sent = Image.open(io.BytesIO(base64.b64decode(server.requests[0]["images"][0])))
    assert max(sent.size) == 896  # nosec B101


async def test_model_timeout_is_said_as_a_timeout(vision):
    vision(delay=6.0, timeout_s=1.0)
    started = time.perf_counter()
    spoken, _, _ = await _speak("what is on my screen")
    assert spoken == "I couldn't look at your screen: the vision model took too long."  # nosec B101
    assert time.perf_counter() - started < 6.0  # nosec B101


async def test_model_failure_is_not_passed_off_as_uncertainty(vision):
    vision(status=500)
    spoken, _, _ = await _speak("what is on my screen")
    assert spoken == "I couldn't look at your screen just now."  # nosec B101
    assert "cannot determine" not in spoken  # nosec B101


async def test_no_vision_server_is_said_plainly(monkeypatch):
    monkeypatch.setattr(screen_reader, "_engine", VQAEngine(ollama_url="http://127.0.0.1:9", timeout_s=3.0))
    monkeypatch.setattr(screen_reader, "_read_via_uia", lambda max_chars: None)
    spoken, _, _ = await _speak("what is on my screen")
    assert spoken == "I couldn't look at your screen: the local vision model isn't running."  # nosec B101


async def test_text_question_works_without_any_ocr_backend(vision, monkeypatch):
    # No OCR backend is installed here; the screen's UI text, when there is
    # some, is the grounding, and without it the model reads the image.
    server = vision()

    class NoOCR:
        async def extract(self, image):
            raise ImportError("no OCR backend installed")

    monkeypatch.setattr("Agent_Guru.vision.ocr.OCREngine", NoOCR)
    spoken, _, _ = await _speak("read the text on my screen")
    assert spoken == "Seen: read the text on my screen"  # nosec B101
    assert "extracted by OCR" not in server.requests[0]["prompt"]  # nosec B101


async def test_screen_text_grounds_the_answer(vision, monkeypatch):
    server = vision()
    monkeypatch.setattr(screen_reader, "_read_via_uia", lambda max_chars: "Invoice 4471 total 92.50")
    await _speak("read the text on my screen")
    assert "Invoice 4471 total 92.50" in server.requests[0]["prompt"]  # nosec B101


async def test_configured_vision_model_is_used(vision, monkeypatch):
    server = vision()
    monkeypatch.setenv("AGENT_GURU_VQA_MODEL", "llava:7b")
    await _speak("what is on my screen")
    assert server.requests[0]["model"] == "llava:7b"  # nosec B101


async def test_one_engine_serves_every_question(vision, monkeypatch):
    server = vision()
    engine = screen_reader._engine
    built = []
    monkeypatch.setattr("Agent_Guru.vision.vqa.VQAEngine.__init__",
                        lambda self, *a, **k: built.append(1))
    for transcript in ("what is on my screen", "describe my screen", "what am I looking at"):
        await _speak(transcript)
    assert screen_reader._engine is engine and built == []  # nosec B101
    assert len(server.requests) == 3  # nosec B101


async def test_concurrent_questions_get_their_own_answers(vision):
    vision(delay=0.3)
    questions = [f"what is on my screen number {i}" for i in range(6)]
    screen = FakeScreen()
    answers = await asyncio.gather(*(screen_reader.answer_screen_question(q, screen) for q in questions))
    assert answers == [f"Seen: {q}" for q in questions]  # nosec B101
    assert len(set(screen.saved)) == 6  # nosec B101  one private file per question
    assert not [p for p in screen.saved if os.path.exists(p)]  # nosec B101  all deleted


async def test_cancelled_question_stops_and_leaves_no_screenshot(vision):
    vision(delay=5.0)
    screen = FakeScreen()
    task = asyncio.create_task(screen_reader.answer_screen_question("what is on my screen", screen))
    await asyncio.sleep(0.5)
    started = time.perf_counter()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert time.perf_counter() - started < 1.0  # nosec B101
    assert screen.saved and not os.path.exists(screen.saved[0])  # nosec B101


def test_no_screenshot_files_left_behind():
    leftovers = glob.glob(os.path.join(tempfile.gettempdir(), "guru_screen_*.png"))
    assert leftovers == []  # nosec B101
