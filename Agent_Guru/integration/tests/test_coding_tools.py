"""A project is read, a change tried on a sandbox copy, and applied to the real files only after a yes.

The project tools, the patching and, where WSL is set up, the real
sandbox run; the model and the owner's words are scripted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration import coding_tools
from Agent_Guru.integration.coding_tools import CodingTools, coding_server
from Agent_Guru.integration.mcp_tools import install_mcp_policies
from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.llm.models import ToolCall
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies
from Agent_Guru.reasoning.tools.skills import wsl_sandbox

BUGGY = "def add(a, b):\n    return a - b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
FIX = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"


@pytest.fixture
def project(monkeypatch, tmp_path):
    root = tmp_path / "Documents" / "budget"
    root.mkdir(parents=True)
    (root / "calc.py").write_text(BUGGY, encoding="utf-8")
    (root / "test_calc.py").write_text(TEST, encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]", encoding="utf-8")
    (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
    monkeypatch.setenv("FILES_ROOTS", str(tmp_path / "Documents"))
    monkeypatch.setenv(coding_tools.ENABLE_ENV, "1")
    return root


async def test_files_are_listed_and_read_without_git_or_secrets(project):
    tools = CodingTools()
    listing, is_error, _ = await tools.call("project_files", {"path": str(project)})
    assert not is_error and "calc.py" in listing and "test_calc.py" in listing  # nosec B101
    assert ".git" not in listing and ".env" not in listing  # nosec B101
    text, _, _ = await tools.call("project_files", {"path": str(project), "file": "calc.py"})
    assert text == BUGGY  # nosec B101


async def test_a_project_outside_the_owners_folders_is_refused(project, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert await CodingTools().precheck("project_files", {"path": str(other)})  # nosec B101


async def test_apply_changes_the_files_keeps_backups_and_reads_back(project, tmp_path):
    tools = CodingTools(backups=tmp_path / "backups")
    assert tools.describe("project_apply", {"path": str(project), "patch": FIX}) == "change 1 file(s) in budget: calc.py"  # nosec B101
    text, is_error, verified = await tools.call("project_apply", {"path": str(project), "patch": FIX})
    assert not is_error and verified and "return a + b" in (project / "calc.py").read_text()  # nosec B101
    (backup,) = (tmp_path / "backups").iterdir()
    assert (backup / "calc.py").read_text() == BUGGY  # nosec B101


async def test_a_diff_that_does_not_fit_changes_no_file(project, tmp_path):
    bad = FIX.replace("return a - b", "return a * b")
    tools = CodingTools(backups=tmp_path / "backups")
    assert "does not match" in (await tools.precheck("project_apply", {"path": str(project), "patch": bad}))[0]  # nosec B101
    _, is_error, _ = await tools.call("project_apply", {"path": str(project), "patch": bad})
    assert is_error and (project / "calc.py").read_text() == BUGGY  # nosec B101


async def test_try_runs_on_a_copy_and_never_touches_the_project(project, monkeypatch):
    shipped = {}

    async def fake_run(files, command, **kw):
        shipped.update(files)
        return wsl_sandbox.SandboxRun("success", 0, "1 passed", "", 0.5)

    monkeypatch.setattr(wsl_sandbox, "run_project", fake_run)
    text, is_error, _ = await CodingTools().call("project_try", {"path": str(project), "patch": FIX,
                                                                 "command": "python3 -m pytest -q"})
    assert not is_error and "passed (exit 0)" in text  # nosec B101
    assert b"return a + b" in shipped["calc.py"] and ".env" not in shipped  # nosec B101
    assert (project / "calc.py").read_text() == BUGGY  # nosec B101


async def test_the_owner_hears_the_files_before_any_change(project, tmp_path):
    server = coding_server()
    server.local = CodingTools(backups=tmp_path / "backups")
    engine = PolicyEngine()
    install_default_policies(engine)
    install_mcp_policies(engine, [server])

    class Model:
        def __init__(self):
            self.script = [("", [ToolCall(name="code_project__project_apply", arguments={"path": str(project), "patch": FIX})]),
                           ("Fixed.", [])]

        async def supports_tool_calling(self, model):
            return True

        async def complete(self, request):
            text, calls = self.script.pop(0) if self.script else ("Okay.", [])
            return SimpleNamespace(content=text, tool_calls=calls, finish_reason="stop")

    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None, mcp_servers=[server], reminder_store=tmp_path / "r.json",
    )

    async def no_web(*a, **k):
        return ""

    orch._fetch_web_context = no_web
    orch._start_tools()
    await orch._tools_starting
    try:
        asked = await orch.run_text_turn("fix the add bug in my budget project")
        assert asked.awaiting_reply and "change 1 file(s) in budget: calc.py" in asked.llm_response  # nosec B101
        assert (project / "calc.py").read_text() == BUGGY  # nosec B101
        done = await orch.run_text_turn("yes")
        assert done.action_status is ActionStatus.SUCCESS and "a + b" in (project / "calc.py").read_text()  # nosec B101
    finally:
        orch.close_scheduler()
        await orch.close_tools()


async def test_the_real_sandbox_runs_the_projects_tests(project):
    problems = wsl_sandbox.check()
    if problems:
        pytest.skip("UNVERIFIED on this host: " + "; ".join(problems))
    tools = CodingTools()
    before, failed, _ = await tools.call("project_try", {"path": str(project), "command": "python3 -m pytest -q"})
    after, failed_after, _ = await tools.call("project_try", {"path": str(project), "patch": FIX,
                                                              "command": "python3 -m pytest -q"})
    assert failed and "1 failed" in before  # nosec B101
    assert not failed_after and "1 passed" in after  # nosec B101


def _link_out(project, outside):
    """A folder link from the project to *outside*: a junction on Windows (no admin needed), a symlink elsewhere."""
    import os
    import subprocess  # nosec B404 - mklink with fixed arguments
    import sys

    link = project / "linkdir"
    if sys.platform == "win32":
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],  # nosec B603 B607
                              capture_output=True, check=False)
        if done.returncode != 0:
            pytest.skip("UNVERIFIED on this host: a junction could not be made")
    else:
        os.symlink(outside, link, target_is_directory=True)
    return link


async def test_a_link_out_of_the_project_is_neither_read_nor_written(project, tmp_path):
    """A junction in the project let project_files read, and project_apply overwrite, a file outside it."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("outside secret\n", encoding="utf-8")
    _link_out(project, outside)
    tools = CodingTools(backups=tmp_path / "backups")
    listing, _, _ = await tools.call("project_files", {"path": str(project)})
    assert "private.txt" not in listing  # nosec B101
    _, is_error, _ = await tools.call("project_files", {"path": str(project), "file": "linkdir/private.txt"})
    assert is_error  # nosec B101
    overwrite = "--- a/linkdir/private.txt\n+++ b/linkdir/private.txt\n@@ -1 +1 @@\n-outside secret\n+overwritten\n"
    plant = "--- /dev/null\n+++ b/linkdir/new.txt\n@@ -0,0 +1 @@\n+planted\n"
    for diff in (overwrite, plant):
        _, is_error, _ = await tools.call("project_apply", {"path": str(project), "patch": diff})
        assert is_error  # nosec B101
    assert (outside / "private.txt").read_text() == "outside secret\n" and not (outside / "new.txt").exists()  # nosec B101
