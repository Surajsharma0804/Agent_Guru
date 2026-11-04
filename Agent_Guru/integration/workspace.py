"""The everyday window: the orb, the conversation, questions, settings, Control Center, System Doctor.

It runs inside the assistant's process on the same secure server as the
installer (genesis/server.py) and the same tokens. Nothing on these screens is
timed or guessed: the orb's state is worked out from the events the pipeline
publishes (Orb below), and the conversation from its turns.

A question stays with the source that asked it. The orchestrator keeps pending
confirmations by source, so a spoken "yes" cannot answer a typed question or
the other way round, and pending_questions() shows the page which question
is waiting. /api/answer takes the question's source and turn, and refuses one
that is not this window's: the page cannot answer for the microphone.

Only the settings in STUDIO can be changed here, each mapped to a real value in
KNOWN_SETTINGS and written through utils/commands.set_setting. Credentials go
through the vault and are write-only: the page sees "set" or "not set".
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from Agent_Guru.genesis.app import _expect

SOURCE = "workspace"
MAX_TEXT = 4000
MAX_TURNS = 200
#: Turns are answered by a person reading: long enough for a slow model.
TURN_RESULT_TIMEOUT_S = 600

#: What the Configuration Studio offers: setting, label, control. Every entry is
#: a real key of utils/settings.KNOWN_SETTINGS (a test holds it to that).
STUDIO: tuple[dict[str, Any], ...] = (
    {"key": "OLLAMA_MODEL", "label": "Language model", "control": "text", "group": "Model"},
    {"key": "AGENT_GURU_NUM_CTX", "label": "Context size (tokens)", "control": "number", "group": "Model"},
    {"key": "AGENT_GURU_SPOKEN_REPLY_TOKENS", "label": "Longest spoken reply (tokens)", "control": "number", "group": "Voice"},
    {"key": "AGENT_GURU_STT_DEVICE", "label": "Speech recognition device", "control": "choice",
     "choices": ["auto", "cuda", "cpu"], "group": "Voice"},
    {"key": "AGENT_GURU_LEARN_FACTS", "label": "Learn facts from conversations", "control": "flag", "group": "Memory and privacy"},
    {"key": "AGENT_GURU_TRACES", "label": "Keep a record of each turn", "control": "flag", "group": "Memory and privacy"},
    {"key": "AGENT_GURU_RESEARCH", "label": "Web research", "control": "flag", "group": "Memory and privacy"},
    {"key": "AGENT_GURU_ALLOW_CLOUD", "label": "Allow cloud models", "control": "flag", "group": "Cloud"},
    {"key": "AGENT_GURU_CLOUD_MODEL", "label": "Cloud model", "control": "text", "group": "Cloud"},
    {"key": "AGENT_GURU_API", "label": "Local HTTP API", "control": "flag", "group": "Startup"},
)
#: Provider credentials the page may set. Never read back.
CLOUD_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY")


def enabled() -> bool:
    return os.environ.get("AGENT_GURU_WORKSPACE", "").strip().lower() in {"1", "true", "yes", "on"}


class Orb:
    """The orb's state, from pipeline events only: it has no timer and no clock.

    speaking beats thinking: a reply is spoken inside a turn. muted beats idle
    and listening, not a turn already running, which still answers.
    """

    def __init__(self, muted: bool = False) -> None:
        self.muted = muted
        self.listening = False
        self.speaking = False
        self.active = 0

    def apply(self, topic: str, data: dict[str, Any]) -> None:
        if topic == "mic":
            self.muted = bool(data.get("muted"))
        elif topic == "listen.started":
            self.listening = True
        elif topic == "listen.finished":
            self.listening = False
        elif topic == "turn.started":
            self.active += 1
            self.listening = False
        elif topic == "turn.ended":
            self.active = max(0, self.active - 1)
        elif topic == "speech.started":
            self.speaking = True
        elif topic == "speech.finished":
            self.speaking = False

    @property
    def state(self) -> str:
        if self.speaking:
            return "speaking"
        if self.active:
            return "thinking"
        if self.muted:
            return "muted"
        return "listening" if self.listening else "idle"


class Workspace:
    """The routes for one running assistant. Handlers run on server threads; the pipeline on its loop."""

    def __init__(self, orchestrator: Any, loop: asyncio.AbstractEventLoop, genesis: Any = None) -> None:
        self.orch = orchestrator
        self.loop = loop
        self.genesis = genesis
        mic = getattr(orchestrator, "microphone", None)
        self.orb = Orb(bool(mic and mic.muted))
        self.lock = threading.Lock()
        self.turns: deque[dict[str, Any]] = deque(maxlen=MAX_TURNS)
        self.waiting = 0
        self.seq = 0
        self.unsubscribe = orchestrator.events.subscribe("*", self.on_event)

    def on_event(self, event: Any) -> None:
        topic, data = event.topic, dict(event.data)
        with self.lock:
            self.seq += 1
            self.orb.apply(topic, data)
            if topic == "turn.queued":
                self.waiting = int(data.get("waiting", 0))
            elif topic == "turn.started":
                self.waiting = max(0, self.waiting - 1)
                self.turns.append({"turn": data.get("turn_id"), "source": data.get("source"), "heard": data.get("heard") or "",
                                   "said": "", "sources": [], "status": "working"})
            elif topic == "turn.finished":
                row = next((t for t in reversed(self.turns) if t["turn"] == data.get("source_turn", data.get("turn_id"))), None)
                if row is None:
                    row = {"turn": data.get("turn_id"), "source": data.get("source"), "status": "working"}
                    self.turns.append(row)
                row.update(heard=data.get("heard") or row.get("heard", ""), said=data.get("said") or "",
                           sources=list(data.get("sources") or []), status=data.get("status") or "answered")
            elif topic == "turn.ended":
                # turn.finished is not published when a turn fails before its
                # record is written, and the row would say "Working on it" for
                # the rest of the session.
                for t in self.turns:
                    if t["turn"] == data.get("turn_id") and t["status"] == "working":
                        t["status"] = "no reply"

    def _microphone(self) -> Any:
        """The microphone, or None when this install has nothing to listen with."""
        mic = getattr(self.orch, "microphone", None)
        return None if getattr(mic, "no_audio_library", False) is True else mic

    # --- reading ------------------------------------------------------------

    def state(self, body: dict[str, Any]) -> tuple[int, Any]:
        mic = self._microphone()
        with self.lock:
            return 200, {"orb": self.orb.state, "seq": self.seq, "turns": [dict(t) for t in self.turns], "waiting": self.waiting,
                         "microphone": "none" if mic is None else ("muted" if self.orb.muted else "on"),
                         "questions": self.orch.pending_questions(), "source": SOURCE}

    def tasks(self, body: dict[str, Any]) -> tuple[int, Any]:
        rows = self.orch._reminders().list_reminders()
        return 200, {"tasks": [{"id": r.reminder_id, "kind": r.kind, "message": r.message, "fire_at": r.fire_at,
                                "every_s": r.every_s, "enabled": r.enabled} for r in rows]}

    def settings(self, body: dict[str, Any]) -> tuple[int, Any]:
        import tomllib

        from Agent_Guru.security import vault
        from Agent_Guru.utils.commands import _settings_file

        path = _settings_file()
        saved = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        names = set(vault.names())
        controls = []
        for item in STUDIO:
            key = item["key"]
            controls.append({**item, "value": saved.get(key), "from_environment": key in os.environ and key not in saved})
        return 200, {"controls": controls, "credentials": {k: "set" if k in names or k in os.environ else "not set" for k in CLOUD_KEYS}}

    # --- acting ---------------------------------------------------------------

    def _run(self, coro: Any, *, wait: bool = False) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(TURN_RESULT_TIMEOUT_S) if wait else future

    def turn(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {"text": str})
        text = (body.get("text") or "").strip()
        if not text or len(text) > MAX_TEXT:
            return 400, {"error": f"a message is 1 to {MAX_TEXT} characters"}
        self._run(self.orch.run_text_turn(text, source=SOURCE)).add_done_callback(lambda f: self._turned_away(text, f))
        return 202, {"accepted": True}

    def _turned_away(self, text: str, future: Any) -> None:
        """Show a message the queue refused: it starts no turn, so no event ever names it."""
        result = None if future.cancelled() or future.exception() else future.result()
        if getattr(result, "error", None) == "busy":
            with self.lock:
                self.seq += 1
                self.turns.append({"turn": None, "source": SOURCE, "heard": text, "said": result.llm_response or "",
                                   "sources": [], "status": "busy"})

    def answer(self, body: dict[str, Any]) -> tuple[int, Any]:
        """Answer one waiting question, named by its source and turn."""
        _expect(body, {"source": str, "turn": int, "yes": bool})
        if "yes" not in body:
            return 400, {"error": "say yes or no"}
        if body.get("source") != SOURCE:
            return 409, {"error": "that question was asked by voice; answer it by voice"}
        waiting = [q for q in self.orch.pending_questions() if q["source"] == SOURCE and q["turn"] == body.get("turn")]
        if not waiting:
            return 409, {"error": "that question is no longer waiting"}
        self._run(self.orch.run_text_turn("yes" if body["yes"] else "no", source=SOURCE))
        return 202, {"accepted": True}

    def set_mic(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {"muted": bool})
        mic = self._microphone()
        if mic is None or "muted" not in body:
            return 409, {"error": "nothing is listening"}
        mic.set_muted(body["muted"])
        self.loop.call_soon_threadsafe(lambda: self.orch.events.publish("mic", muted=body["muted"]))
        return 200, {"muted": body["muted"]}

    def set_setting(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {"key": str, "value": (str, bool, int, float)})
        from Agent_Guru.utils.commands import set_setting

        key = body.get("key", "")
        if key not in {i["key"] for i in STUDIO}:
            return 400, {"error": "not a setting of this screen"}
        return 200, {"saved": set_setting(key, str(body.get("value", "")))}

    def set_credential(self, body: dict[str, Any]) -> tuple[int, Any]:
        """Keep a provider key in the vault. The value is never read back, logged or echoed."""
        _expect(body, {"name": str, "value": str})
        from Agent_Guru.security import vault

        name = body.get("name", "")
        if name not in CLOUD_KEYS:
            return 400, {"error": "not a provider key"}
        vault.put(name, body.get("value", ""))
        return 200, {"name": name, "state": "set"}

    def routes(self) -> dict[tuple[str, str], Callable[[dict[str, Any]], tuple[int, Any]]]:
        def guarded(fn: Callable[[dict[str, Any]], tuple[int, Any]]) -> Callable[[dict[str, Any]], tuple[int, Any]]:
            def call(body: dict[str, Any]) -> tuple[int, Any]:
                try:
                    return fn(body)
                except ValueError as exc:
                    return 400, {"error": str(exc)}
            return call

        table = {("GET", "/api/workspace"): self.state, ("GET", "/api/tasks"): self.tasks,
                 ("GET", "/api/settings"): self.settings, ("POST", "/api/turn"): self.turn,
                 ("POST", "/api/answer"): self.answer, ("POST", "/api/mic"): self.set_mic,
                 ("POST", "/api/setting"): self.set_setting, ("POST", "/api/credential"): self.set_credential}
        routes = dict(self.genesis.routes()) if self.genesis is not None else {}
        routes.update({k: guarded(v) for k, v in table.items()})
        return routes


def start(orchestrator: Any, loop: asyncio.AbstractEventLoop) -> Any:
    """Start the window's server and leave its URL for the launcher, readable by this account only."""
    from Agent_Guru.genesis.app import GenesisApp
    from Agent_Guru.genesis.layout import default_layout
    from Agent_Guru.genesis.server import GenesisServer

    root = os.environ.get("AGENT_GURU_INSTALL_ROOT")
    genesis = GenesisApp(default_layout(Path(root))) if root else None
    workspace = Workspace(orchestrator, loop, genesis)
    server = GenesisServer(workspace.routes())
    if genesis is not None:
        genesis.close = server.stop
    url = server.start() .replace("/#t=", "/workspace.html#t=")
    target = os.environ.get("AGENT_GURU_WORKSPACE_FILE")
    if target:
        path = Path(target)
        path.write_text(json.dumps({"url": url}), encoding="utf-8")
        path.chmod(0o600)
    return server
