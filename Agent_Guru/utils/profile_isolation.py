"""Point every user-profile location at a throwaway folder, for tests, evals and harnesses.

Anything that starts the assistant reads and writes the owner's profile: memory,
learned facts, reminders, turns.db, the onboarding KeyStore, logs, the speaker
profile. Isolation used to be done piece by piece. The test suite's autouse
fixture set AGENT_GURU_DATA_DIR, a variable no code reads, so it isolated
nothing. scripts/turn_eval.py swapped three stores by hand. The round 12 soak
isolated LOCALAPPDATA only, and user_memory.json lives under the home folder,
so the soak's turns were written into the owner's real learned facts.

isolate_profile() points HOME, USERPROFILE, LOCALAPPDATA, APPDATA and the XDG
data, cache, config and state folders at one temporary root. It must run before
the assistant's modules are imported: several of them fix their path when
imported (user_memory._MEMORY_PATH = Path.home() / ...), and a later change of
environment would not move them. It refuses to run after one of those modules
is loaded rather than isolate half the profile.

Model downloads are not the owner's data and are large: the Hugging Face and
torch caches are pinned to their real locations through HF_HOME and
TORCH_HOME, and the Kokoro and prompt-injection model folders are linked into
the temporary home. Without that, an isolated run would find no models and
try to download them.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import MutableMapping

#: The variables that name the owner's profile on Windows, macOS and Linux.
PROFILE_VARS = (
    "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME",
)

#: Modules that compute a profile path when imported. If one is already loaded
#: when isolate_profile() runs, its path still points at the real profile.
CACHES_PATH_AT_IMPORT = (
    "Agent_Guru.platform.features.user_memory",
    "Agent_Guru.platform.features.reaction_rules",
    "Agent_Guru.platform.browser_manager",
    "Agent_Guru.speech.biometric.speaker_verifier",
    "Agent_Guru.speech.filler_response",
    "Agent_Guru.speech.tts.tts_engine",
    "Agent_Guru.core.error_handler",
    "Agent_Guru.reasoning.tools.system.file_operations",
)

#: Model folders under the home cache, linked into the temporary home so they are
#: found without a download. Model files only; nothing the owner wrote.
_LINKED_MODEL_DIRS = (
    Path(".cache") / "agent_guru" / "kokoro",
    Path(".cache") / "agent_guru" / "prompt-injection",
    Path(".cache") / "agent_guru" / "prompt-injection-small",
)

#: Set by isolate_profile(): the profile variables as they were before it ran.
REAL_PROFILE: dict[str, str] = {}


def _link(target: Path, link: Path) -> None:
    """A directory link at *link* to *target*: a junction on Windows, which needs no privilege."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def isolate_profile(
    root: str | os.PathLike[str] | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
    link_model_caches: bool = True,
) -> Path:
    """Point the profile variables at folders under *root* (a new temp folder by default).

    Returns the root. Raises RuntimeError if a module in CACHES_PATH_AT_IMPORT is
    already imported. The variables' previous values are kept in REAL_PROFILE.
    """
    env = os.environ if environ is None else environ
    loaded = [name for name in CACHES_PATH_AT_IMPORT if name in sys.modules]
    if loaded:
        msg = (f"isolate_profile() must run before these are imported, or they keep the real profile: "
               f"{', '.join(loaded)}")
        raise RuntimeError(msg)

    real_home = Path(env.get("USERPROFILE") or env.get("HOME") or Path.home())
    real_cache = Path(env.get("XDG_CACHE_HOME") or real_home / ".cache")
    base = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="agent_guru_profile_"))
    home = base / "home"
    folders = {
        "HOME": home,
        "USERPROFILE": home,
        "LOCALAPPDATA": home / "AppData" / "Local",
        "APPDATA": home / "AppData" / "Roaming",
        "XDG_DATA_HOME": home / ".local" / "share",
        "XDG_CACHE_HOME": home / ".cache",
        "XDG_CONFIG_HOME": home / ".config",
        "XDG_STATE_HOME": home / ".local" / "state",
    }
    for name in PROFILE_VARS:
        if name in env:
            REAL_PROFILE.setdefault(name, env[name])
    # Model caches stay where they are, read through the real paths.
    env.setdefault("HF_HOME", str(real_cache / "huggingface"))
    env.setdefault("TORCH_HOME", str(real_cache / "torch"))
    # NLTK looks under the home folder and, on Windows, under APPDATA. Moving
    # those hid the wordnet and tagger data, so every test run since this
    # helper went back to the download server, and on a bad network nltk's
    # error path crashed test_train_intent_classifier (2026-11-04).
    for folder in (Path(env.get("APPDATA") or real_home) / "nltk_data", real_home / "nltk_data"):
        if folder.is_dir():
            env.setdefault("NLTK_DATA", str(folder))
            break
    for name, folder in folders.items():
        folder.mkdir(parents=True, exist_ok=True)
        env[name] = str(folder)
    if link_model_caches:
        for relative in _LINKED_MODEL_DIRS:
            target = real_home / relative
            if target.is_dir() and not (home / relative).exists():
                _link(target, home / relative)
    return base
