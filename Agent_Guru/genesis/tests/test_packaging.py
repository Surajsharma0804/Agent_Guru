"""The spec and the installer script keep the install small, per user and honest."""

from __future__ import annotations

import ast
import re

from Agent_Guru.genesis.layout import source_root
from Agent_Guru.genesis.server import UI_DIR

ROOT = source_root()
SPEC = (ROOT / "AgentGuru.spec").read_text(encoding="utf-8")
ISS = (ROOT / "AgentGuru_setup.iss").read_text(encoding="utf-8")


def _calls(name):
    return [n for n in ast.walk(ast.parse(SPEC)) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == name]


def _kw(call, key):
    return next((k.value for k in call.keywords if k.arg == key), None)


def test_the_spec_freezes_the_launcher_and_ships_the_vendored_ui():
    assert "GENESIS / 'launcher.py'" in SPEC and "main.py" not in SPEC.split("Analysis(")[1]  # nosec B101
    assert "(str(GENESIS / 'ui'), 'Agent_Guru/genesis/ui')" in SPEC  # nosec B101
    assert "(str(GENESIS / 'components.json'), 'Agent_Guru/genesis')" in SPEC  # nosec B101
    for name in ("index.html", "tokens.css", "app.js", "core.js", "strings.en.json", "fonts/Rajdhani-Medium.ttf",
                 "fonts/Rajdhani-SemiBold.ttf", "fonts/OFL.txt"):
        assert (UI_DIR / name).is_file(), name  # nosec B101


def test_one_folder_without_upx():
    exes, collects = _calls("EXE"), _calls("COLLECT")
    assert len(exes) == 2 and len(collects) == 1  # nosec B101
    for call in exes:
        assert _kw(call, "exclude_binaries").value is True and _kw(call, "upx").value is False  # nosec B101
    assert _kw(collects[0], "upx").value is False  # nosec B101


def test_the_application_is_excluded_from_the_launcher():
    packages = {p.name for p in (ROOT / "Agent_Guru").iterdir() if p.is_dir() and (p / "__init__.py").is_file()}
    excluded = set(re.findall(r"'Agent_Guru\.([a-z_]+)'", SPEC.split("EXCLUDED_APP = [")[1].split("]")[0]))
    # Everything except the two the launcher itself imports. A new package must
    # be added here or it would be frozen through runtime_tasks's lazy imports.
    assert packages - excluded == {"genesis", "utils"}  # nosec B101


def _setup(key):
    return re.search(rf"^{key}=(.*)$", ISS, re.M).group(1).strip()


def test_the_installer_is_per_user_solid_lzma2_and_asks_for_no_admin():
    assert _setup("PrivilegesRequired") == "lowest"  # nosec B101
    assert _setup("Compression") == "lzma2/ultra64" and _setup("SolidCompression") == "yes"  # nosec B101
    assert _setup("DefaultDirName").startswith("{autopf}")  # nosec B101  the user's Programs folder at this level


def test_every_optional_task_starts_unticked():
    tasks = [line for line in ISS.splitlines() if line.startswith('Name: "') and "GroupDescription" in line]
    assert len(tasks) == 1 and all("Flags: unchecked" in t for t in tasks)  # nosec B101


def test_start_at_sign_in_is_the_plans_choice_and_uninstall_undoes_it():
    """The installer's own task duplicated the plan's box and opened setup at every sign-in."""
    assert 'Tasks: startup' not in ISS and 'Name: "startup"' not in ISS  # nosec B101
    assert 'Type: files; Name: "{userstartup}\\Agent Guru.lnk"' in ISS  # nosec B101
    # A running assistant holds the files uninstall has to delete.
    assert 'Parameters: "--stop"' in ISS and "[UninstallRun]" in ISS  # nosec B101


def test_nothing_touches_path_the_registry_or_the_firewall():
    for word in ("[Registry]", "ChangesEnvironment", "netsh", "advfirewall", "sc create"):
        assert word.lower() not in ISS.lower(), word  # nosec B101


def test_setup_is_offered_on_the_last_page_and_never_runs_silently():
    run = ISS.split("[Run]")[1].split("[UninstallDelete]")[0]
    assert 'Description: "Set up Agent Guru now"' in run  # nosec B101
    assert "postinstall" in run and "skipifsilent" in run  # nosec B101


def test_uninstall_removes_only_the_runtime_and_keeps_data_unless_asked():
    assert 'Type: filesandordirs; Name: "{app}\\runtime"' in ISS  # nosec B101
    assert ISS.count("DelTree(") == 1  # nosec B101
    code = ISS.split("[Code]")[1]
    assert "and RemoveData then" in code and "MB_DEFBUTTON2" in code  # nosec B101  No is the default answer


def test_the_installer_ships_no_tests_and_no_models():
    files = ISS.split("[Files]")[1].split("[Icons]")[0]
    assert 'Excludes: "tests,__pycache__,*.pyc,test_*.py,conftest.py"' in files  # nosec B101
    assert ".onnx" not in files and "torch" not in files  # nosec B101


def test_the_app_source_ships_where_the_frozen_layout_looks():
    assert 'DestDir: "{app}\\app\\Agent_Guru"' in ISS and 'DestDir: "{app}\\app"' in ISS  # nosec B101


def _pins():
    from Agent_Guru.genesis.manifest import lock_pins

    return lock_pins(ROOT / "requirements-lock.txt")


def test_the_build_tools_are_pinned_in_the_lock():
    pins = _pins()
    for name in ("pyinstaller", "pyinstaller-hooks-contrib", "pywebview", "pythonnet", "clr-loader"):
        assert name in pins, name  # nosec B101


def test_every_build_script_takes_its_tool_versions_from_the_lock():
    for script in ("installer/linux/build_appimage.sh", "installer/macos/build_dmg.sh"):
        text = (ROOT / script).read_text(encoding="utf-8")
        assert "requirements-lock.txt" in text, script  # nosec B101
        assert 'dist/AgentGuru-$VERSION' in text, script  # nosec B101  the project folder, never temp
    assert "requirements-lock.txt" in (ROOT / "installer/windows/build_installer.ps1").read_text(encoding="utf-8")  # nosec B101


def test_the_linux_stub_is_pinned_by_hash_and_checked():
    text = (ROOT / "installer/linux/build_appimage.sh").read_text(encoding="utf-8")
    assert re.search(r'RUNTIME_SHA256="[0-9a-f]{64}"', text) and "sha256sum -c" in text  # nosec B101


def test_frozen_linux_and_macos_builds_carry_the_app_source_without_tests():
    assert "datas.append((str(path), str(Path('app', *parts[:-1]))))" in SPEC  # nosec B101
    assert "'tests' in parts" in SPEC and "requirements-lock.txt" in SPEC  # nosec B101
    assert "BUNDLE(coll, name='Agent Guru.app'" in SPEC  # nosec B101


def test_the_macos_build_says_it_is_unsigned():
    text = (ROOT / "installer/macos/build_dmg.sh").read_text(encoding="utf-8")
    assert "right-click" in text and "codesign" not in text  # nosec B101
