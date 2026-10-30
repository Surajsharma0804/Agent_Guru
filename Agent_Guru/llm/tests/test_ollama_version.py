"""The startup check names the installed Ollama against the tested one and never stops the start.

Ollama's /api/version is played by httpx.MockTransport; nothing connects to a real server.
"""

from __future__ import annotations

import logging

import httpx

from Agent_Guru.llm import ollama_version
from Agent_Guru.llm.ollama_version import TESTED_OLLAMA_VERSION, check_ollama_version


def _client(answer):
    return httpx.Client(transport=httpx.MockTransport(answer))


def _warnings(caplog):
    return [r for r in caplog.records if r.levelno >= logging.WARNING and r.name == ollama_version.__name__]


def test_the_tested_version_is_noted_without_a_warning(caplog):
    with caplog.at_level(logging.INFO, logger=ollama_version.__name__):
        found = check_ollama_version(client=_client(lambda r: httpx.Response(200, json={"version": TESTED_OLLAMA_VERSION})))
    assert found == TESTED_OLLAMA_VERSION and _warnings(caplog) == []
    assert "the version the README's measurements were made on" in caplog.text


def test_another_version_warns_once_and_names_both(caplog):
    with caplog.at_level(logging.INFO, logger=ollama_version.__name__):
        found = check_ollama_version(client=_client(lambda r: httpx.Response(200, json={"version": "0.41.0"})))
    (warning,) = _warnings(caplog)
    assert found == "0.41.0" and "0.41.0" in warning.getMessage() and TESTED_OLLAMA_VERSION in warning.getMessage()


def test_an_ollama_that_does_not_answer_is_reported_and_the_start_goes_on(caplog):
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    with caplog.at_level(logging.INFO, logger=ollama_version.__name__):
        assert check_ollama_version(client=_client(down)) is None
    assert _warnings(caplog) == [] and "did not answer" in caplog.text


def test_localhost_is_asked_as_127_0_0_1():
    asked = []

    def answer(request):
        asked.append(request.url.host)
        return httpx.Response(200, json={"version": TESTED_OLLAMA_VERSION})

    check_ollama_version("http://localhost:11434/", client=_client(answer))
    assert asked == ["127.0.0.1"]


def test_the_readme_names_the_tested_version():
    from pathlib import Path

    readme = (Path(__file__).resolve().parents[3] / "README.md").read_text(encoding="utf-8")
    assert f"Tested Ollama version: {TESTED_OLLAMA_VERSION}." in readme
