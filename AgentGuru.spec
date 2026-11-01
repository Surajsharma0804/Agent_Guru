# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Agent Guru.

Build with:
    .venv\\Scripts\\pyinstaller.exe AgentGuru.spec --noconfirm
"""
import os
import sys
from pathlib import Path

ROOT = Path(os.path.abspath('.'))

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'Agent_Guru'), 'Agent_Guru'),
        (str(ROOT / 'assets'), 'assets'),
    ],
    hiddenimports=[
        'Agent_Guru',
        'Agent_Guru.speech',
        'Agent_Guru.speech.filler_response',
        'Agent_Guru.speech.biometric',
        'Agent_Guru.speech.biometric.speaker_verifier',
        'Agent_Guru.vision',
        'Agent_Guru.llm',
        'Agent_Guru.llm.companion_prompts',
        'Agent_Guru.platform',
        'Agent_Guru.platform.features',
        'Agent_Guru.platform.features.reaction_rules',
        'Agent_Guru.platform.features.confirmation',
        'Agent_Guru.platform.features.user_memory',
        'Agent_Guru.agents',
        'Agent_Guru.memory',
        'Agent_Guru.security',
        'Agent_Guru.policy',
        'Agent_Guru.emotion',
        'Agent_Guru.integration',
        'Agent_Guru.integration.orchestrator',
        'pydantic',
        'dotenv',
        'sounddevice',
        'numpy',
        'json',
        'asyncio',
        'collections',
        'pathlib',
        'threading',
        'logging',
        're',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy visualization - not needed at runtime for voice assistant
        'matplotlib',
        'matplotlib.pyplot',
        'seaborn',
        'plotly',
        # NLP packages with broken hooks
        'nltk',
        'spacy',
        # Testing frameworks
        'pytest',
        'hypothesis',
        'unittest',
        'test',
        'tests',
        '_pytest',
        # Dev tools
        'black',
        'isort',
        'flake8',
        'mypy',
        'pylint',
        'ruff',
        'bandit',
        'pre_commit',
        'safety',
        # Interactive / notebook
        'IPython',
        'jupyter',
        'notebook',
        'ipykernel',
        'ipywidgets',
        # GUI toolkits we don't use
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        # Large optional deps
        'tensorflow',
        'jax',
        'jaxlib',
        'tensorboard',
        'wandb',
        'mlflow',
        # Sphinx / docs
        'sphinx',
        'docutils',
        # Other heavy packages with broken hooks
        'numba',
        'datasets',
        'vllm',
        'deepface',
        'insightface',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgentGuru',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AgentGuru',
)
