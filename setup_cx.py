"""cx_Freeze setup script for Agent Guru MSI installer.

Usage:
    python setup_cx.py build     # Creates dist/AgentGuru/ folder
    python setup_cx.py bdist_msi # Creates AgentGuru-x.x.x-win64.msi

This script generates a Windows MSI installer using cx_Freeze.
The MSI provides standard Windows installer features: Add/Remove Programs,
silent install via msiexec, and proper Windows integration.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from cx_Freeze import Executable, setup

# Project root
ROOT = Path(__file__).parent

# Collect data files
include_files: list[tuple[str, str]] = []

# Assets
assets_dir = ROOT / "assets"
if assets_dir.exists():
    for f in assets_dir.iterdir():
        if f.is_file():
            include_files.append((str(f), f"assets/{f.name}"))

# Models directory (if exists and has content)
models_dir = ROOT / "models"
if models_dir.exists():
    for f in models_dir.rglob("*"):
        if f.is_file():
            rel = f.relative_to(ROOT)
            include_files.append((str(f), str(rel)))

# .env file (template)
env_example = ROOT / ".env.example"
if env_example.exists():
    include_files.append((str(env_example), ".env.example"))

# README
readme = ROOT / "README.md"
if readme.exists():
    include_files.append((str(readme), "README.txt"))

# Build options
build_exe_options = {
    "packages": [
        "Agent_Guru",
        "Agent_Guru.speech",
        "Agent_Guru.speech.biometric",
        "Agent_Guru.vision",
        "Agent_Guru.llm",
        "Agent_Guru.platform",
        "Agent_Guru.platform.features",
        "Agent_Guru.agents",
        "Agent_Guru.memory",
        "Agent_Guru.security",
        "Agent_Guru.policy",
        "Agent_Guru.emotion",
        "Agent_Guru.integration",
        "asyncio",
        "json",
        "logging",
        "threading",
        "collections",
        "pathlib",
        "re",
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "test",
        "tests",
        "pytest",
        "hypothesis",
        "black",
        "isort",
        "flake8",
        "mypy",
        "pylint",
        "ruff",
        "bandit",
        "sphinx",
        "IPython",
        "jupyter",
        "notebook",
    ],
    "include_files": include_files,
    "optimize": 1,
}

# MSI options
bdist_msi_options = {
    "add_to_path": True,
    "install_icon": str(ROOT / "assets" / "icon.ico"),
    "upgrade_code": "{A1B2C3D4-E5F6-7890-ABCD-EF0123456789}",
}

# Determine base
base = "Win32GUI" if sys.platform == "win32" else None
# Use console base for now since Agent Guru is a CLI/voice app
base = "Console" if sys.platform == "win32" else None

# Icon path
icon_path = str(ROOT / "assets" / "icon.ico")
if not os.path.exists(icon_path):
    icon_path = None

executables = [
    Executable(
        script=str(ROOT / "main.py"),
        base=base,
        target_name="AgentGuru",
        icon=icon_path,
        shortcut_name="Agent Guru",
        shortcut_dir="DesktopFolder",
    ),
]

setup(
    name="AgentGuru",
    version="1.0.0",
    description="Agent Guru - AI Voice Assistant with Laptop Control",
    author="Suraj Sharma",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
