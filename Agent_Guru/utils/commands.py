"""Everyday commands: ask, chat, config, model, memory, tasks, eval, bench.

Most of what the owner did with the assistant had no command: a typed
question needed the voice loop or a script, a setting meant editing
settings.toml by hand and hoping the name was right, and the evaluation
and latency runs were scripts to find. Each command here uses what the
assistant already has:

    ask "question"        one turn through the running assistant (local API)
    chat                  a typed conversation with it
    config [show|set K V|unset K]   settings.toml, checked like the file itself
    model [NAME]          the model in use, or switch it (settings.toml)
    memory [show|forget KEY]        what the assistant remembers about the owner
    tasks                 reminders, checks and actions it has scheduled (read only)
    eval / bench          scripts/turn_eval.py: scoring, or stage latency

ask and chat talk to the assistant that is running, through its local
API (AGENT_GURU_API), so a typed turn has the same memory, policy and
confirmations as a spoken one.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 - runs this interpreter on a script in the repository
import sys
from pathlib import Path


def _api(text: str) -> dict:
    import httpx

    from Agent_Guru.integration import local_api

    url = f"http://{local_api.HOST}:{local_api.port()}/v1/turn"
    try:
        response = httpx.post(url, json={"text": text}, headers={"X-API-Key": local_api.owner_key()}, timeout=180)
    except httpx.HTTPError as exc:
        msg = (f"The assistant is not answering on {url} ({type(exc).__name__}). Start it with "
               "AGENT_GURU_API = true in settings.toml.")
        raise SystemExit(msg) from exc
    if response.status_code != 200:
        msg = f"The assistant refused: HTTP {response.status_code} {response.text[:200]}"
        raise SystemExit(msg)
    return response.json()


def _show(answer: dict) -> None:
    print(answer.get("reply") or answer.get("error") or "(no reply)")  # noqa: T201  the command's output
    for source in answer.get("sources") or []:
        print(f"  [{source.get('id', '')}] {source.get('title', '')} {source.get('url', '')}".rstrip())  # noqa: T201
    if answer.get("awaiting_reply"):
        print("(It is waiting for your answer.)")  # noqa: T201


def ask(argv: list[str]) -> int:
    text = " ".join(argv).strip()
    if not text:
        print('python -m Agent_Guru ask "what is on my calendar tomorrow"')  # noqa: T201
        return 2
    _show(_api(text))
    return 0


def chat(argv: list[str]) -> int:
    print("Typed chat with the assistant. An empty line or Ctrl+C ends it.")  # noqa: T201
    try:
        while True:
            text = input("you> ").strip()
            if not text:
                return 0
            _show(_api(text))
    except (EOFError, KeyboardInterrupt):
        return 0


def _settings_file() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("settings.toml")


def _write_setting(key: str, value: str | None) -> str:
    """Set *key* to *value* (TOML text) in settings.toml, or remove it when None; keeps every other line."""
    import shutil

    path = _settings_file()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    first_table = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    kept = [line for i, line in enumerate(lines) if not (i < first_table and pattern.match(line))]
    if value is not None:
        first_table = next((i for i, line in enumerate(kept) if line.lstrip().startswith("[")), len(kept))
        while first_table > 0 and not kept[first_table - 1].strip():
            first_table -= 1
        kept.insert(first_table, f"{key} = {value}")
    path.write_text("\n".join(kept).rstrip("\n") + "\n", encoding="utf-8")
    return str(path)


def config(argv: list[str]) -> int:
    import os
    import tomllib

    from Agent_Guru.utils.recipes import _toml_value
    from Agent_Guru.utils.settings import _SECRET, KNOWN_SETTINGS, _as_env_value

    action = argv[0] if argv else "show"
    if action == "show":
        path = _settings_file()
        data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        print(f"{path}")  # noqa: T201
        for key in sorted(KNOWN_SETTINGS):
            if key in data or key in os.environ:
                where = "environment" if key in os.environ else "settings.toml"
                print(f"  {key} = {os.environ.get(key, data.get(key))!s}  ({where})")  # noqa: T201
        return 0
    if action in {"set", "unset"} and len(argv) >= 2:
        key = argv[1]
        if _SECRET.search(key):
            print(f"{key} looks like a secret: set it in the environment or .env, not settings.toml.")  # noqa: T201
            return 1
        if key not in KNOWN_SETTINGS:
            import difflib

            close = difflib.get_close_matches(key.upper(), list(KNOWN_SETTINGS), n=3, cutoff=0.6)
            print(f"{key} is not a setting Agent Guru reads." + (f" Did you mean: {', '.join(close)}" if close else ""))  # noqa: T201
            return 1
        if action == "unset":
            print(f"Removed {key} from {_write_setting(key, None)}")  # noqa: T201
            return 0
        raw = " ".join(argv[2:])
        kind = KNOWN_SETTINGS[key]
        value: object = raw
        if kind == "flag":
            value = raw.lower() in {"1", "true", "yes", "on"}
        elif kind in {"seconds", "count"}:
            try:
                value = float(raw) if kind == "seconds" else int(raw)
            except ValueError:
                print(f"{key} must be a number")  # noqa: T201
                return 1
        try:
            _as_env_value(key, value)
        except ValueError as exc:
            print(f"{key} {exc}")  # noqa: T201
            return 1
        print(f"Set {key} in {_write_setting(key, _toml_value(value))}. Restart the assistant to use it.")  # noqa: T201
        return 0
    print("python -m Agent_Guru config [show | set KEY VALUE | unset KEY]")  # noqa: T201
    return 2


def model(argv: list[str]) -> int:
    import os

    if not argv:
        print(f"In use: {os.environ.get('OLLAMA_MODEL', 'gemma4')}")  # noqa: T201
        from Agent_Guru.llm.model_catalog import run as models

        return models([])
    from Agent_Guru.llm.model_catalog import find

    try:
        entry = find(argv[0])
    except OSError as exc:
        print(exc)  # noqa: T201
        return 1
    if entry is None and not argv[0].startswith("engine:"):
        print(f"{argv[0]} is not installed in Ollama. Pull it first: ollama pull {argv[0]}")  # noqa: T201
        return 1
    return config(["set", "OLLAMA_MODEL", argv[0]])


def memory(argv: list[str]) -> int:
    from Agent_Guru.platform.features.user_memory import get_user_memory

    store = get_user_memory()
    if argv[:1] == ["forget"] and len(argv) == 2:
        print("Forgotten." if store.delete(argv[1]) else f"Nothing is remembered as {argv[1]}.")  # noqa: T201
        return 0
    facts = store.get_all()
    if not facts:
        print("Nothing is remembered about you yet.")  # noqa: T201
    for key, value in facts.items():
        print(f"  {key}: {json.dumps(value, ensure_ascii=False)[:200]}")  # noqa: T201
    return 0


def tasks(argv: list[str]) -> int:
    import datetime as dt

    from Agent_Guru.utils.path_utils import app_data_dir

    path = app_data_dir("reminders.json", create=False)
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if isinstance(items, dict):
        items = items.get("reminders") or list(items.values())
    if not items:
        print("Nothing is scheduled.")  # noqa: T201
        return 0
    for t in items:
        when = dt.datetime.fromtimestamp(float(t.get("fire_at", 0))).strftime("%a %d %b %H:%M") if t.get("fire_at") else "?"
        every = f" every {int(t['every_s']) // 60} min" if t.get("every_s") else ""
        state = "" if t.get("enabled", True) else " (disabled)"
        print(f"  {t.get('id', '?')[:8]}  {t.get('kind', 'say'):6} {when}{every}{state}  {t.get('message') or t.get('tool', '')}")  # noqa: T201
    print("To cancel one, ask the assistant: \"cancel the task <id>\".")  # noqa: T201
    return 0


def _turn_eval(extra: list[str]) -> int:
    script = Path(__file__).resolve().parents[2] / "scripts" / "turn_eval.py"
    return subprocess.run([sys.executable, str(script), *extra], check=False).returncode  # noqa: S603  # nosec B603


def evaluate(argv: list[str]) -> int:
    return _turn_eval(argv)


def bench(argv: list[str]) -> int:
    return _turn_eval(["--latency", *argv])
