"""Transcribe an audio file and generate an image, as tools in the tool loop.

"What does the voice note in my Downloads say?" had no answer: the
assistant transcribed only its microphone. "Make me a picture of a
sunrise over the Ganga" had no tool at all.

    transcribe_audio   an audio file under the owner's folders, by the local
                       Whisper (or the cloud recogniser the owner chose)       read-only
    generate_image     an image from a description, by OpenAI's image model,
                       saved to Pictures/Agent Guru; the owner says yes first,
                       because the description leaves the machine and costs   cloud only

Served in process through the same toolbox as MCP servers. A file must lie
under FILES_ROOTS (default Documents, Desktop, Downloads) and pass the
sensitive-file policy; generate_image is offered only with
AGENT_GURU_ALLOW_CLOUD and OPENAI_API_KEY.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import time
from pathlib import Path
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

SERVER_NAME = "media"
AUDIO_SUFFIXES = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac", ".opus", ".webm", ".aac"})
MAX_AUDIO_BYTES = 200 * 1024 * 1024
_IMAGE_SIZES = ("1024x1024", "1536x1024", "1024x1536")


def media_server() -> ServerConfig:
    rules = {"transcribe_audio": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
             "generate_image": ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)}
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=300.0, tools=rules)


def _roots() -> list[Path]:
    from Agent_Guru.connectors.tools import _roots as roots

    return [r.resolve() for r in roots()]


def allowed_audio(path_text: str) -> tuple[Path | None, str]:
    """(the file, "") when the assistant may read *path_text*, else (None, why not)."""
    from Agent_Guru.security.file_policy import sensitive_reason

    path = Path(os.path.expandvars(os.path.expanduser(path_text.strip().strip('"')))).resolve()
    if reason := sensitive_reason(path):
        return None, f"that file is off limits ({reason})"
    if not any(path.is_relative_to(root) for root in _roots()):
        return None, "only files under the owner's folders (FILES_ROOTS) can be read"
    if path.suffix.lower() not in AUDIO_SUFFIXES:
        return None, f"not an audio file (one of {', '.join(sorted(AUDIO_SUFFIXES))})"
    if not path.is_file():
        return None, "no such file"
    if path.stat().st_size > MAX_AUDIO_BYTES:
        return None, "the file is larger than 200 MB"
    return path, ""


def _cloud_images() -> bool:
    return (os.environ.get("AGENT_GURU_ALLOW_CLOUD", "").strip().lower() in {"1", "true", "yes", "on"}
            and bool(os.environ.get("OPENAI_API_KEY", "").strip()))


def _pictures() -> Path:
    return Path(os.environ.get("AGENT_GURU_IMAGES_DIR", "") or Path.home() / "Pictures" / "Agent Guru")


class MediaTools:
    """The media tools (see the module docstring)."""

    def __init__(self, transcriber: Any = None, client: Any = None) -> None:
        self._transcriber = transcriber
        self._client = client

    def tool_list(self) -> list[dict[str, Any]]:
        tools = [{
            "name": "transcribe_audio",
            "description": "Transcribe an audio file (voice note, recording) in the owner's folders and return its text.",
            "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {
                "path": {"type": "string", "minLength": 3, "maxLength": 500},
                "language": {"type": "string", "pattern": "^[a-z]{2}$"}},
                "required": ["path"], "additionalProperties": False},
        }]
        if _cloud_images():
            tools.append({
                "name": "generate_image",
                "description": "Generate an image from a description with a cloud image model and save it in the "
                               "owner's Pictures. The owner confirms first.",
                "annotations": {"readOnlyHint": False, "openWorldHint": True},
                "inputSchema": {"type": "object", "properties": {
                    "prompt": {"type": "string", "minLength": 3, "maxLength": 2000},
                    "size": {"type": "string", "enum": list(_IMAGE_SIZES)}},
                    "required": ["prompt"], "additionalProperties": False},
            })
        return tools

    def describe(self, tool: str, arguments: dict[str, Any]) -> str | None:
        if tool == "generate_image":
            return f"send this description to OpenAI and save the image it makes: {str(arguments.get('prompt', ''))[:200]}"
        return None

    async def precheck(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        if tool == "transcribe_audio":
            _, why = allowed_audio(str(arguments.get("path", "")))
            return [why] if why else []
        if tool == "generate_image" and not _cloud_images():
            return ["cloud image generation is not switched on (AGENT_GURU_ALLOW_CLOUD and OPENAI_API_KEY)"]
        return []

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        if name == "transcribe_audio":
            return await self._transcribe(str(arguments.get("path", "")), arguments.get("language"))
        if name == "generate_image":
            return await self._image(str(arguments.get("prompt", "")), str(arguments.get("size") or _IMAGE_SIZES[0]))
        return f"unknown tool {name}", True, False

    async def _transcribe(self, path_text: str, language: str | None) -> tuple[str, bool, bool]:
        path, why = allowed_audio(path_text)
        if path is None:
            return f"Cannot transcribe it: {why}.", True, False
        if self._transcriber is None:
            from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber

            self._transcriber = WhisperTranscriber()
        result = await asyncio.to_thread(self._transcriber.transcribe_file, str(path), language)
        text = (result.text or "").strip()
        if not text:
            return f"{path.name}: no speech was found in it.", False, False
        return f"{path.name} ({result.duration:.0f} s, {result.language}):\n{text[:8000]}", False, False

    async def _image(self, prompt: str, size: str) -> tuple[str, bool, bool]:
        if not _cloud_images():
            return "Cloud image generation is not switched on.", True, False
        import httpx

        try:
            async with (self._client or httpx.AsyncClient(timeout=120.0)) as http:
                response = await http.post(
                    "https://api.openai.com/v1/images/generations",
                    json={"model": os.environ.get("AGENT_GURU_IMAGE_MODEL", "").strip() or "gpt-image-1",
                          "prompt": prompt, "size": size, "n": 1},
                    headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY'].strip()}"})
            if response.status_code != 200:
                return f"The image service answered {response.status_code}: {response.text[:200]}", True, False
            data = base64.b64decode(response.json()["data"][0]["b64_json"])
        except Exception as exc:
            return f"The image could not be made: {type(exc).__name__}: {exc}"[:300], True, False
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return "The image service sent something that is not a PNG; nothing was saved.", True, False
        folder = _pictures()
        folder.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9]+", "-", prompt.lower()).strip("-")[:40] or "image"
        target = folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}.png"
        target.write_bytes(data)
        # Read back: the file exists and is the image that came.
        saved = target.read_bytes() == data
        return f"Saved the image to {target}.", not saved, saved
