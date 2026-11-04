# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Agent Guru launcher.

Only the launcher is frozen: the GENESIS engine, its window and the standard
library. The application and its dependencies are not. This spec used to
freeze main.py with everything its imports reach (torch, Whisper, OpenCV) into
one folder. Now the installer stays small and the launcher builds the private
runtime on the person's machine, from the pinned lock, with what that machine
needs.

One folder, not one file: a one-file build unpacks itself to a temporary
folder on every start, which costs seconds and trips antivirus scanners. No
UPX, for the same reason: packed executables start slower and draw false
positives.

Build in a venv holding only pyinstaller and pywebview, from the repository
root, so nothing else can be picked up:

    pyinstaller AgentGuru.spec --noconfirm
"""
from pathlib import Path

ROOT = Path(SPECPATH)
GENESIS = ROOT / 'Agent_Guru' / 'genesis'

# What the launcher reads at run time. The UI is listed folder by folder so
# test_packaging.py can check it against the files on disk.
datas = [
    (str(GENESIS / 'components.json'), 'Agent_Guru/genesis'),
    (str(GENESIS / 'ui'), 'Agent_Guru/genesis/ui'),
]

# genesis/runtime_tasks.py imports the application lazily, because it runs in
# the managed runtime. PyInstaller follows imports inside functions too, so
# without these it would freeze the whole assistant into the launcher.
EXCLUDED_APP = [
    'Agent_Guru.agent_orchestration', 'Agent_Guru.agents', 'Agent_Guru.avatar', 'Agent_Guru.connectors',
    'Agent_Guru.context', 'Agent_Guru.core', 'Agent_Guru.deployment', 'Agent_Guru.emotion',
    'Agent_Guru.explainability', 'Agent_Guru.fusion', 'Agent_Guru.goal_manager', 'Agent_Guru.health',
    'Agent_Guru.integration', 'Agent_Guru.iot', 'Agent_Guru.learning', 'Agent_Guru.llm', 'Agent_Guru.memory',
    'Agent_Guru.platform', 'Agent_Guru.policy', 'Agent_Guru.proactive', 'Agent_Guru.reasoning',
    'Agent_Guru.recipes', 'Agent_Guru.resilience', 'Agent_Guru.sdk', 'Agent_Guru.security',
    'Agent_Guru.self_improvement', 'Agent_Guru.skills', 'Agent_Guru.speech', 'Agent_Guru.sync',
    'Agent_Guru.training', 'Agent_Guru.translation', 'Agent_Guru.verifier', 'Agent_Guru.vision',
]
# Standard-library parts nothing here uses, and the test packages.
EXCLUDED_OTHER = ['tkinter', 'unittest', 'pydoc', 'pydoc_data', 'lib2to3', 'test', 'pytest', 'numpy', 'torch']

a = Analysis(
    [str(GENESIS / 'launcher.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=['Agent_Guru.utils.path_utils', 'Agent_Guru.utils.verified_files', 'Agent_Guru.utils.model_fit',
                   'Agent_Guru.utils.profile_isolation'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_APP + EXCLUDED_OTHER,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

window = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgentGuru',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / 'assets' / 'icon.ico'),
)

# The same program with a console, for `AgentGuruCli genesis --plan` and a
# terminal with no display: a windowed exe has no stdout to print to.
terminal = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgentGuruCli',
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(ROOT / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    window,
    terminal,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='AgentGuru',
)
