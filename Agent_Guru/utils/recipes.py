"""Recipes: named sets of settings, applied to settings.toml in one step.

Switching the assistant between ways of running (the small model for a
4 GB GPU, no network at all, research on) meant knowing which of about
fifty variables to set and to what. A recipe is a short TOML file of
settings.toml lines with a description:

    description = "Smaller model for a 4 GB GPU; faster replies, less depth"
    OLLAMA_MODEL = "gemma4:e2b"
    AGENT_GURU_NUM_CTX = 4096

Built-in recipes ship in Agent_Guru/recipes/; the owner's own go in the
data folder's recipes/ and win over a built-in of the same name. Applying
checks every value exactly as settings.toml is checked (known settings
only, no secrets), rewrites only those lines of settings.toml, keeps every
other line and comment, and saves the previous file as settings.toml.bak.

    python -m Agent_Guru recipes                 list them
    python -m Agent_Guru recipes show NAME       what one sets
    python -m Agent_Guru recipes apply NAME      write it into settings.toml
"""

from __future__ import annotations

import argparse
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from Agent_Guru.utils.settings import _SECRET, KNOWN_SETTINGS, _as_env_value

BUILT_IN = Path(__file__).resolve().parent.parent / "recipes"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


@dataclass(slots=True)
class Recipe:
    name: str
    description: str
    settings: dict[str, str] = field(default_factory=dict)
    path: Path | None = None


def _owner_dir() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("recipes")


def _settings_path() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("settings.toml")


def load(path: Path) -> Recipe:
    """The recipe in *path*; ValueError naming the problem if any line does not fit settings.toml."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        msg = f"{path.name}: {type(exc).__name__}: {exc}"
        raise ValueError(msg) from exc
    description = str(data.pop("description", "")).strip()
    settings: dict[str, str] = {}
    for key, value in data.items():
        if _SECRET.search(key):
            msg = f"{path.name}: {key} looks like a secret; recipes never hold secrets"
            raise ValueError(msg)
        if key not in KNOWN_SETTINGS:
            msg = f"{path.name}: {key} is not a setting Agent Guru reads"
            raise ValueError(msg)
        try:
            _as_env_value(key, value)
        except ValueError as exc:
            msg = f"{path.name}: {key} {exc}"
            raise ValueError(msg) from exc
        settings[key] = _toml_value(value)
    return Recipe(name=path.stem, description=description, settings=settings, path=path)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def available() -> dict[str, Recipe]:
    """Every recipe by name; the owner's override a built-in with the same name. Broken ones are skipped."""
    found: dict[str, Recipe] = {}
    for folder in (BUILT_IN, _owner_dir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.toml")):
            if not _NAME.match(path.stem):
                continue
            try:
                found[path.stem] = load(path)
            except ValueError:
                continue
    return found


def apply(name: str, settings_path: Path | None = None) -> list[str]:
    """Write recipe *name* into settings.toml; returns the lines written. KeyError if there is no such recipe."""
    recipe = available()[name]
    path = settings_path or _settings_path()
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    lines = text.splitlines()
    written = []
    # Top-level keys must come before the first [table]; new ones go there.
    first_table = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    while first_table > 0 and not lines[first_table - 1].strip():
        first_table -= 1
    for key, value in recipe.settings.items():
        line = f"{key} = {value}"
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        for i, existing in enumerate(lines[:first_table]):
            if pattern.match(existing):
                lines[i] = line
                break
        else:
            lines.insert(first_table, line)
            first_table += 1
        written.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return written


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru recipes", description="Named sets of settings.")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("name")
    use = sub.add_parser("apply")
    use.add_argument("name")
    args = parser.parse_args(argv)
    recipes = available()
    if args.action in (None, "list"):
        for recipe in recipes.values():
            print(f"{recipe.name:16} {recipe.description}")  # noqa: T201  the command's output
        return 0
    if args.name not in recipes:
        print(f"No recipe called {args.name}. Try: {', '.join(recipes)}")  # noqa: T201
        return 1
    if args.action == "show":
        recipe = recipes[args.name]
        print(recipe.description)  # noqa: T201
        for key, value in recipe.settings.items():
            print(f"  {key} = {value}")  # noqa: T201
        return 0
    for line in apply(args.name):
        print(f"set {line}")  # noqa: T201
    print("Restart the assistant to use it. The previous file is settings.toml.bak.")  # noqa: T201
    return 0
