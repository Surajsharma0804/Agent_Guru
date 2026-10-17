"""Slack messages and Granola meeting notes as sources, read with the owner's own tokens.

httpx's MockTransport answers in place of slack.com and Granola's API.
"""

from __future__ import annotations

import httpx
import pytest

from Agent_Guru.connectors import tools as connector_tools
from Agent_Guru.connectors.tools import ConnectorTools


@pytest.fixture
def services(monkeypatch):
    seen = []
    answers = {}

    def handle(request):
        seen.append(request)
        return answers[request.url.path](request)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(connector_tools, "_provider", lambda: "")
    monkeypatch.setattr("Agent_Guru.connectors.oauth.connected", lambda: {})
    return seen, answers


def _names():
    return {t["name"] for t in ConnectorTools().tool_list()}


def test_offered_only_with_their_tokens(services, monkeypatch):
    monkeypatch.delenv("SLACK_USER_TOKEN", raising=False)
    monkeypatch.delenv("GRANOLA_API_KEY", raising=False)
    assert not {"slack_search", "meetings_search", "meeting_read"} & _names()  # nosec B101
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-1")
    monkeypatch.setenv("GRANOLA_API_KEY", "gr-1")
    assert {"slack_search", "meetings_search", "meeting_read"} <= _names()  # nosec B101


async def test_slack_search_reads_the_owners_messages(services, monkeypatch):
    seen, answers = services
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-1")
    answers["/api/search.messages"] = lambda r: httpx.Response(200, json={"ok": True, "messages": {"matches": [
        {"ts": "1792233000.000100", "username": "rahul", "channel": {"name": "launch"}, "text": "Demo moved to Friday"}]}})
    text, is_error = await ConnectorTools().call("slack_search", {"query": "demo"})
    assert not is_error and "rahul | #launch | Demo moved to Friday" in text  # nosec B101
    assert seen[0].headers["Authorization"] == "Bearer xoxp-1" and seen[0].url.params["query"] == "demo"  # nosec B101


async def test_a_slack_refusal_is_an_error_not_an_empty_result(services, monkeypatch):
    _, answers = services
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxb-bot")
    answers["/api/search.messages"] = lambda r: httpx.Response(200, json={"ok": False, "error": "not_allowed_token_type"})
    text, is_error = await ConnectorTools().call("slack_search", {"query": "demo"})
    assert is_error and "not_allowed_token_type" in text  # nosec B101


async def test_granola_notes_are_found_and_read(services, monkeypatch):
    seen, answers = services
    monkeypatch.setenv("GRANOLA_API_KEY", "gr-1")
    answers["/v1/notes"] = lambda r: httpx.Response(200, json={"hasMore": False, "notes": [
        {"id": "n1", "created_at": "2026-10-15T10:00:00Z", "title": "Budget review", "summary": {"markdown": "Cut travel by 10%"}},
        {"id": "n2", "created_at": "2026-10-16T10:00:00Z", "title": "Standup", "summary": {"markdown": "Nothing new"}}]})
    answers["/v1/notes/n1"] = lambda r: httpx.Response(200, json={
        "title": "Budget review", "created_at": "2026-10-15T10:00:00Z", "attendees": [{"name": "Asha"}],
        "summary": {"markdown": "Cut travel by 10%"},
        "transcript": [{"speaker": {"source": "microphone"}, "text": "Let's cut travel."}]})
    tools = ConnectorTools()
    found, is_error = await tools.call("meetings_search", {"query": "budget"})
    assert not is_error and found.startswith("[n1] 2026-10-15 | Budget review") and "Standup" not in found  # nosec B101
    note, is_error = await tools.call("meeting_read", {"id": "n1"})
    assert not is_error and "Attendees: Asha" in note and "microphone: Let's cut travel." in note  # nosec B101
    assert seen[-1].url.params["include"] == "transcript" and seen[-1].headers["Authorization"] == "Bearer gr-1"  # nosec B101
