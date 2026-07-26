"""Pytest configuration and shared fixtures for Agent Guru tests."""

from __future__ import annotations

import pathlib
import tempfile

import pytest


@pytest.fixture
def tmp_path_factory_clean(tmp_path: pathlib.Path) -> pathlib.Path:
    """Provide a clean temporary directory for each test."""
    return tmp_path


@pytest.fixture
def mock_audio_samples() -> list[bytes]:
    """Generate mock audio samples (silence) for testing audio pipelines."""
    import numpy as np

    sample_rate = 16000
    duration_s = 1.0
    samples = int(sample_rate * duration_s)
    audio = np.zeros(samples, dtype=np.float32)
    return [audio.tobytes()]


@pytest.fixture
def temp_json_path() -> pathlib.Path:
    """Provide a temporary JSON file path for testing storage."""
    path = pathlib.Path(tempfile.mktemp(suffix=".json"))
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def temp_npz_path() -> pathlib.Path:
    """Provide a temporary .npz file path for testing speaker profiles."""
    path = pathlib.Path(tempfile.mktemp(suffix=".npz"))
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from writing to real user directories."""
    temp_dir = tempfile.mkdtemp(prefix="agent_guru_test_")
    monkeypatch.setenv("AGENT_GURU_DATA_DIR", temp_dir)
