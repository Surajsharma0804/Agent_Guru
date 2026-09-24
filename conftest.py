"""Pytest configuration and shared fixtures for Agent Guru tests."""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile

import pytest
from hypothesis import HealthCheck, Verbosity, settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hypothesis configuration
#
# pytest.ini carries a `[hypothesis]` section (max_examples, derandomize,
# deadline, print_blob, database). Hypothesis DOES NOT READ pytest.ini - it is
# configured through profiles, the HYPOTHESIS_PROFILE environment variable or
# --hypothesis-profile - so that section was dead configuration and every
# property test in this repository ran with Hypothesis's built-in defaults
# instead: a 200 ms per-example deadline, non-derandomised input, and the
# on-disk example database.
#
# The visible symptom was recurring, non-reproducible failures of the form
#     hypothesis.errors.FlakyFailure: ... produces unreliable results:
#     Failed on the first call but did not on a subsequent one
#     Unreliable test timings! On an initial run this test took 414.08ms,
#     which exceeded the deadline of 200.00ms, but on a subsequent run it
#     took 0.33ms
# - i.e. the FIRST example of a property paid a one-off warm-up (building a
# tool registry, loading a model, importing a backend) and Hypothesis reported
# it as a defect in the code under test.
#
# A wall-clock deadline is not a correctness property; this project asserts
# performance explicitly in its `performance`-marked tests. Registering the
# profile the repository already describes makes that configuration real.
# ---------------------------------------------------------------------------
settings.register_profile(
    "agent_guru",
    max_examples=100,
    derandomize=True,
    deadline=None,
    print_blob=False,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "fast",
    parent=settings.get_profile("agent_guru"),
    max_examples=10,
)
settings.register_profile(
    "debug",
    parent=settings.get_profile("agent_guru"),
    verbosity=Verbosity.verbose,
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "agent_guru"))


# ---------------------------------------------------------------------------
# Hermetic test runs: no model downloads
#
# KokoroTTSEngine._ensure_loaded() auto-downloads ~83 MB of ONNX weights the
# first time anything synthesises speech. Under test that turned ordinary unit
# tests into network transfers: Agent_Guru/speech/tests/tts/test_tts_properties.py
# and .../engine/test_speech_engine.py both blew their 30-second budget pulling
# model weights, and a CI runner would have re-downloaded them on every cold
# cache - slow, flaky, and dependent on a third-party host being up.
#
# A test suite has to be hermetic, so downloads are off by default here. The
# TTS engine treats the resulting TTSError as "this backend is unavailable" and
# falls back exactly as it does on a machine without the model, which is a
# state the suite should be able to exercise anyway. Tests that genuinely need
# real audio check TTSEngine.active_backend and skip themselves.
#
# Set AGENT_GURU_ALLOW_MODEL_DOWNLOAD=1 to run the suite against real weights.
# ---------------------------------------------------------------------------
if os.environ.get("AGENT_GURU_ALLOW_MODEL_DOWNLOAD", "").strip().lower() not in {
    "1",
    "true",
    "yes",
    "on",
}:
    os.environ.setdefault("AGENT_GURU_NO_DOWNLOAD", "1")


# ---------------------------------------------------------------------------
# librosa warm-up
#
# The first use of librosa.feature imports librosa.util.utils, whose
# @numba.vectorize functions are JIT-compiled at import time, and piptrack and
# beat_track compile further numba code on their first call. That one-off cost
# (about 18 s on a cold Linux cache, 19-30 s on the Windows CI runners) was
# charged to whichever test touched librosa first, inside that test's timeout
# budget. avatar/tests/test_properties.py::
# test_property_5_audio_feature_extraction_completeness took 19-22 s on one CI
# run and was killed at 30 s on the next, with the same code.
#
# This is the problem Agent_Guru/reasoning/tests/conftest.py already solves
# for the embedding model, solved the same way. The compile happens in
# pytest_collection_finish, outside every test's timeout window, and only when
# a collected test opts in with
#
#     pytestmark = pytest.mark.usefixtures("warm_librosa")
#
# It lives here rather than beside the embedding warm-up because the modules
# that need it are under avatar/ and speech/, which that conftest cannot
# serve.
#
# A warm-up failure must degrade, never abort: an exception raised from a
# collection hook is an INTERNALERROR that stops the whole session and hides
# its collection-error summary. librosa is also optional for the code under
# test - every caller has a numpy fallback - so unlike the embedding fixture,
# the warm_librosa fixture never raises either.
# ---------------------------------------------------------------------------
_LIBROSA_WARMUP_ATTEMPTED = False


def _warm_librosa_once() -> None:
    """Run the librosa calls the suite relies on once, compiling their numba code."""
    global _LIBROSA_WARMUP_ATTEMPTED
    if _LIBROSA_WARMUP_ATTEMPTED:
        return
    # Set before the work so a failure is not retried by the fixture backstop.
    _LIBROSA_WARMUP_ATTEMPTED = True

    import librosa
    import numpy as np

    sample_rate = 16000
    t = np.arange(sample_rate, dtype=np.float32) / sample_rate
    y = (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)

    librosa.feature.mfcc(y=y, sr=sample_rate, n_mfcc=13)
    librosa.feature.melspectrogram(y=y, sr=sample_rate)
    librosa.feature.rms(y=y)
    librosa.feature.zero_crossing_rate(y)
    librosa.feature.spectral_centroid(y=y, sr=sample_rate)
    librosa.feature.spectral_bandwidth(y=y, sr=sample_rate)
    librosa.feature.spectral_rolloff(y=y, sr=sample_rate)
    librosa.piptrack(y=y, sr=sample_rate)
    librosa.beat.beat_track(y=y, sr=sample_rate)


def _report_warmup_failure(config: pytest.Config, what: str, exc: Exception) -> None:
    """Log a warm-up failure and show it in the terminal, naming the root cause."""
    root: BaseException = exc
    while root.__cause__ is not None:
        root = root.__cause__
    detail = f"{type(exc).__name__}: {exc}"
    if root is not exc:
        detail += f" (caused by {type(root).__name__}: {root})"
    message = (
        f"{what} warm-up failed - {detail}. Tests that use it pay the "
        "first-use cost themselves or take their fallback path; all other "
        "tests run normally."
    )
    logger.warning(message)
    # Captured log records are not shown for a collection hook, so also
    # write the warning to the terminal where it is visible in CI logs.
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"WARNING: {message}", yellow=True)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Warm librosa after collection, before any test starts, if a test opted in."""
    if not any("warm_librosa" in item.fixturenames for item in session.items):
        return
    try:
        _warm_librosa_once()
    except Exception as exc:
        _report_warmup_failure(session.config, "librosa", exc)


@pytest.fixture(scope="session")
def warm_librosa(pytestconfig: pytest.Config) -> None:
    """Ensure librosa's numba code is compiled before the tests that use it.

    pytest_collection_finish above normally does this before any test starts.
    This fixture is the backstop for a run where that hook did not fire, and
    is a no-op once the warm-up has been attempted. It never raises: librosa
    is optional for the code under test.
    """
    try:
        _warm_librosa_once()
    except Exception as exc:
        _report_warmup_failure(pytestconfig, "librosa", exc)


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
