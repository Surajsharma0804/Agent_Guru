"""isolate_profile() keeps a run of the assistant out of the owner's profile.

The round 12 soak isolated LOCALAPPDATA only; user_memory.json lives under the
home folder, so the soak's typed turns were written into the owner's real
learned facts. The suite's own autouse fixture set a variable nothing reads.

The check runs the orchestrator in a fresh interpreter, because several modules
fix their profile path when imported. The child starts with every profile
variable pointing at a stand-in "real" profile made here, already holding a
user_memory.json, never at the owner's: a broken isolation then damages only
the stand-in. After the turns the stand-in must be unchanged, file for file,
and the turns' writes must have landed in the isolated root instead.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

import pytest

from Agent_Guru.utils.profile_isolation import CACHES_PATH_AT_IMPORT, PROFILE_VARS

REPO = Path(__file__).resolve().parents[3]

_CHILD = r"""
import asyncio, json, sys
from types import SimpleNamespace
from Agent_Guru.utils.profile_isolation import isolate_profile
isolate_profile(sys.argv[1])
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies

class Model:
    async def complete(self, request):
        return SimpleNamespace(content="Noted.", finish_reason="stop", tool_calls=[])

async def main():
    engine = PolicyEngine(); install_default_policies(engine)
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None,
    )
    async def no_web(*a, **k):
        return ""
    orch._fetch_web_context = no_web
    for said in ("remember that my favourite colour is blue", "remind me to stretch in 10 minutes",
                 "what is two plus two"):
        await orch.run_text_turn(said)
    orch.close_scheduler()

asyncio.run(main())
"""


def _snapshot(root: Path) -> dict[str, list[int]]:
    return {str(p.relative_to(root)): [p.stat().st_size, p.stat().st_mtime_ns]
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.timeout(180)
def test_typed_turns_write_to_the_isolated_profile_not_the_real_one(tmp_path):
    real = tmp_path / "real_profile"
    profile = {
        "HOME": real, "USERPROFILE": real, "LOCALAPPDATA": real / "AppData" / "Local",
        "APPDATA": real / "AppData" / "Roaming", "XDG_DATA_HOME": real / ".local" / "share",
        "XDG_CACHE_HOME": real / ".cache", "XDG_CONFIG_HOME": real / ".config",
        "XDG_STATE_HOME": real / ".local" / "state",
    }
    assert set(profile) == set(PROFILE_VARS)  # nosec B101  a new variable must be covered here too
    for folder in profile.values():
        folder.mkdir(parents=True, exist_ok=True)
    memory = real / ".cache" / "agent_guru" / "user_memory.json"
    memory.parent.mkdir(parents=True)
    memory.write_text(json.dumps({"learned_facts": []}), encoding="utf-8")
    before = _snapshot(real)

    env = {k: v for k, v in os.environ.items() if k not in PROFILE_VARS and not k.startswith("AGENT_GURU_")}
    env.update({k: str(v) for k, v in profile.items()})
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONIOENCODING"] = "utf-8"
    isolated = tmp_path / "isolated"
    run = subprocess.run([sys.executable, "-c", _CHILD, str(isolated)], cwd=str(tmp_path), env=env,  # nosec B603
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=170, check=False)
    assert run.returncode == 0, run.stderr[-2000:]  # nosec B101

    changed = {p: (before.get(p), now) for p, now in _snapshot(real).items() if before.get(p) != now}
    assert not changed, f"written to the real profile: {sorted(changed)}"  # nosec B101
    written = _snapshot(isolated)
    assert any(p.endswith("user_memory.json") for p in written), sorted(written)  # nosec B101


def test_it_refuses_once_a_path_caching_module_is_imported(monkeypatch, tmp_path):
    from Agent_Guru.utils import profile_isolation

    monkeypatch.setitem(sys.modules, CACHES_PATH_AT_IMPORT[0], object())
    with pytest.raises(RuntimeError, match="must run before"):
        profile_isolation.isolate_profile(tmp_path, environ={})


def test_the_test_suite_itself_runs_in_an_isolated_profile():
    # The root conftest isolates the profile before any test module is
    # imported. Its old autouse fixture set a variable nothing read, so this
    # suite's stores fell back to the owner's real folders wherever a test
    # did not swap them itself.
    from Agent_Guru.platform.features import user_memory
    from Agent_Guru.utils.path_utils import app_data_dir

    root = getattr(sys.modules.get("conftest"), "TEST_PROFILE", None)
    assert root is not None, "the root conftest did not isolate the profile"  # nosec B101
    for path in (Path.home(), user_memory._MEMORY_PATH, app_data_dir("x", create=False)):
        assert Path(root) in path.parents, f"{path} is outside the test profile {root}"  # nosec B101
