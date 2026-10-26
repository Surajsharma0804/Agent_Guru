"""Pytest configuration and shared fixtures for Agent Guru tests."""

from __future__ import annotations

import importlib.util
import logging
import os
import pathlib
import sys
import tempfile
from typing import Any

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
# Hermetic test runs: no live model calls
#
# The suite gave the same pass count with Ollama stopped and running, but not
# the same run. With it running, 19 tests (test_engine::test_detect_intent and
# 18 in reasoning/tests/test_integration_checkpoint.py) sent real prompts to
# the model and waited for its 135 s intent timeout: those tests took 4,699 s
# instead of 260 s, 1 h 50 min for the whole suite instead of 42 min, and what
# they asserted depended on what the model happened to answer. The guards that
# already existed did not cover them. reasoning/tests/conftest.py replaces
# OllamaProvider and ReasoningEngine skips its provider under pytest, but the
# intent fallback (reasoning/intent/llm_fallback.py) posts to Ollama with
# requests directly, and vision, llm_manager and ollama_server each have their
# own client too.
#
# So the refusal is made where every client meets: the socket. Unless
# AGENT_GURU_LIVE_LLM=1, a connection to the Ollama port is refused exactly
# as it is when Ollama is not running, so a run on a machine with Ollama up
# is the same run as one without it. Tests that only mean something against
# a real model carry @pytest.mark.live_llm and are skipped unless opted in.
#
# Set AGENT_GURU_LIVE_LLM=1 to let the suite reach a real model.
# ---------------------------------------------------------------------------
_TRUE = {"1", "true", "yes", "on"}
_LIVE_LLM = os.environ.get("AGENT_GURU_LIVE_LLM", "").strip().lower() in _TRUE


def _ollama_ports() -> set[int]:
    """The port of the default Ollama address, plus the one OLLAMA_HOST names."""
    from urllib.parse import urlsplit

    ports = {11434}
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if host:
        try:
            port = urlsplit(host if "://" in host else f"http://{host}").port
        except ValueError:
            port = None
        if port:
            ports.add(port)
    return ports


def _refuse_ollama_connections() -> None:
    """Make every connection to the Ollama port fail as if Ollama were stopped."""
    import errno
    import socket

    ports = _ollama_ports()

    def refused(address: Any) -> bool:
        return isinstance(address, tuple) and len(address) >= 2 and address[1] in ports

    def error(address: Any) -> ConnectionRefusedError:
        return ConnectionRefusedError(
            errno.ECONNREFUSED,
            f"{address!r}: live model calls are off under test (AGENT_GURU_LIVE_LLM=1 allows them)",
        )

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, address: Any) -> None:
        if refused(address):
            raise error(address)
        return real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if refused(address):
            return errno.ECONNREFUSED
        return real_connect_ex(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]

    # The Windows proactor event loop connects through IOCP ConnectEx, not
    # socket.connect, so an asyncio client (httpx, aiohttp) would pass the
    # patch above untouched.
    if sys.platform == "win32":
        from asyncio import windows_events

        real_iocp_connect = windows_events.IocpProactor.connect

        def iocp_connect(self: Any, conn: socket.socket, address: Any) -> object:
            if refused(address):
                raise error(address)
            return real_iocp_connect(self, conn, address)

        windows_events.IocpProactor.connect = iocp_connect  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Windows: raise the per-test timeout, because it is a hang guard
#
# pytest.ini passes --timeout=30. That timeout is a HANG guard, not a
# performance assertion. It exists to stop a deadlocked test from hanging CI,
# not to measure how fast a runner is. A test that cares about speed must
# assert it explicitly in its body, as the `performance`-marked tests do.
# One test currently relies on the timeout instead:
# speech/tests/stt/test_language_detector.py::
# test_performance_40_languages_rapid_detection is named and documented as a
# "rapid detection" test but makes no timing assertion, so its only speed
# check is this timeout. That assertion belongs in the test body.
#
# On Linux and macOS pytest-timeout uses SIGALRM, so a timeout fails the one
# test and the run continues. Windows has no SIGALRM, so pytest-timeout falls
# back to its thread method, which dumps every stack and calls os._exit(1):
# one slow test kills the whole process, and the run's failure summary is
# never printed. The Windows CI runners are also highly variable - the same
# test took 2 s on one run and 31 s on the next - so a 30 s budget made every
# Windows run end at a random point.
#
# So on Windows only, every per-test timeout (the default, and any
# @pytest.mark.timeout marker) is raised to at least
# _WINDOWS_HANG_GUARD_SECONDS. A real deadlock is still stopped, with a stack
# dump; runner variance no longer is. A timeout of 0 (disabled) is left
# alone. Linux and macOS are not touched.
# ---------------------------------------------------------------------------
_WINDOWS_HANG_GUARD_SECONDS = 300.0


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Refuse live model calls, and on Windows raise the default timeout.

    The refusal goes in before collection, because test modules and
    session fixtures can reach the model before any test starts.
    """
    if not _LIVE_LLM:
        _refuse_ollama_connections()
    if sys.platform != "win32":
        return
    timeout = config.getoption("timeout", default=None)
    if timeout:
        config.option.timeout = max(float(timeout), _WINDOWS_HANG_GUARD_SECONDS)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live_llm tests unless opted in; on Windows raise explicit timeouts."""
    if not _LIVE_LLM:
        skip = pytest.mark.skip(reason="needs a real model: set AGENT_GURU_LIVE_LLM=1")
        for item in items:
            if item.get_closest_marker("live_llm") is not None:
                item.add_marker(skip)
    if sys.platform != "win32":
        return
    for item in items:
        marker = item.get_closest_marker("timeout")
        if marker is None or not marker.args:
            continue
        value = marker.args[0]
        if isinstance(value, (int, float)) and 0 < value < _WINDOWS_HANG_GUARD_SECONDS:
            # Prepended, so pytest-timeout's get_closest_marker() finds it first.
            item.add_marker(
                pytest.mark.timeout(_WINDOWS_HANG_GUARD_SECONDS, *marker.args[1:], **marker.kwargs),
                append=False,
            )


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
# its collection-error summary. librosa is also an optional extra, so unlike
# the embedding fixture, the warm_librosa fixture never raises either.
#
# Not every librosa caller has a fallback: voice_features, voice_cloner and
# emotion_detector need it to produce any result at all. Tests that drive
# those paths request `requires_librosa` below, so a machine without librosa
# reports them as skipped with the reason, instead of as dozens of failures
# that look like broken code.
# ---------------------------------------------------------------------------
_LIBROSA_WARMUP_ATTEMPTED = False


def _warm_librosa_once() -> None:
    """Run the librosa calls the suite relies on once, compiling their numba code."""
    global _LIBROSA_WARMUP_ATTEMPTED
    if _LIBROSA_WARMUP_ATTEMPTED:
        return
    # Set before the work so a failure is not retried by the fixture backstop.
    _LIBROSA_WARMUP_ATTEMPTED = True

    # Absent is a supported configuration, not a warm-up failure. Reporting
    # it as one printed a "warm-up failed" warning on every run of every
    # machine without the extra, which is exactly the noise that teaches
    # people to stop reading the test output.
    if importlib.util.find_spec("librosa") is None:
        return

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
def requires_librosa() -> None:
    """Skip the requesting test when librosa is not installed.

    For tests whose code path cannot produce a result without librosa. Before
    librosa was imported lazily, its absence broke collection of whole files;
    now those files collect, and only the tests that really need it are
    skipped, while the rest of each file still runs.
    """
    pytest.importorskip("librosa")


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
