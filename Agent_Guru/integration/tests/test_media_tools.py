"""Audio files are transcribed only from the owner's folders; images are made only with cloud switched on."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from Agent_Guru.integration.media_tools import MediaTools, allowed_audio

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


@pytest.fixture
def folders(monkeypatch, tmp_path):
    home = tmp_path / "Documents"
    home.mkdir()
    monkeypatch.setenv("FILES_ROOTS", str(home))
    monkeypatch.setenv("AGENT_GURU_IMAGES_DIR", str(tmp_path / "Pictures"))
    for name in ("AGENT_GURU_ALLOW_CLOUD", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return home


class Whisper:
    def __init__(self):
        self.files = []

    def transcribe_file(self, path, language=None):
        self.files.append(path)
        return SimpleNamespace(text=" call the electrician tomorrow ", duration=4.2, language="en")


async def test_a_voice_note_in_the_owners_folder_is_transcribed(folders):
    note = folders / "note.m4a"
    note.write_bytes(b"audio")
    whisper = Whisper()
    text, is_error, _ = await MediaTools(transcriber=whisper).call("transcribe_audio", {"path": str(note)})
    assert not is_error and "call the electrician tomorrow" in text and "note.m4a" in text  # nosec B101


@pytest.mark.parametrize(("make", "why"), [
    (lambda root, tmp: tmp / "elsewhere.wav", "owner's folders"),
    (lambda root, tmp: root / "report.pdf", "not an audio file"),
    (lambda root, tmp: root / "missing.wav", "no such file"),
])
async def test_files_outside_the_rules_are_refused(folders, tmp_path, make, why):
    path = make(folders, tmp_path)
    if "missing" not in path.name:
        path.write_bytes(b"x")
    whisper = Whisper()
    tools = MediaTools(transcriber=whisper)
    assert why in (await tools.precheck("transcribe_audio", {"path": str(path)}))[0]  # nosec B101
    _, is_error, _ = await tools.call("transcribe_audio", {"path": str(path)})
    assert is_error and whisper.files == []  # nosec B101


def test_a_sensitive_file_is_refused_even_in_the_folders(folders):
    key = folders / ".ssh" / "id_rsa.wav"
    key.parent.mkdir()
    key.write_bytes(b"x")
    path, why = allowed_audio(str(key))
    assert path is None and "off limits" in why  # nosec B101


def test_image_generation_is_not_offered_without_cloud(folders, monkeypatch):
    assert [t["name"] for t in MediaTools().tool_list()] == ["transcribe_audio"]  # nosec B101
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert "generate_image" in [t["name"] for t in MediaTools().tool_list()]  # nosec B101


async def test_an_image_is_made_saved_and_read_back(folders, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    sent = []

    def answer(request):
        sent.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})

    tools = MediaTools(client=httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    assert "send this description to OpenAI" in tools.describe("generate_image", {"prompt": "a sunrise"})  # nosec B101
    text, is_error, verified = await tools.call("generate_image", {"prompt": "A sunrise over the Ganga"})
    body = json.loads(sent[0].content)
    assert str(sent[0].url) == "https://api.openai.com/v1/images/generations"  # nosec B101
    assert body["prompt"] == "A sunrise over the Ganga" and body["size"] == "1024x1024"  # nosec B101
    saved = list((tmp_path / "Pictures").glob("*-a-sunrise-over-the-ganga.png"))
    assert not is_error and verified and len(saved) == 1 and saved[0].read_bytes() == PNG  # nosec B101


async def test_an_answer_that_is_not_a_png_saves_nothing(folders, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    bad = base64.b64encode(b"<html>").decode()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"b64_json": bad}]})))
    _, is_error, _ = await MediaTools(client=client).call("generate_image", {"prompt": "anything"})
    assert is_error and not (tmp_path / "Pictures").exists()  # nosec B101
