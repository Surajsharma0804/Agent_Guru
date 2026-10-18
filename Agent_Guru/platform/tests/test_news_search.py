"""Questions about now are searched in the news, newest first, with each publisher's own address."""

from __future__ import annotations

import pytest

from Agent_Guru.platform.features import web_search
from Agent_Guru.platform.features.web_search import is_current, search_sources

_FEED = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>
<item><title>Older result: India beat Ireland</title>
 <link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fwww.example.com%2fold&amp;c=1</link>
 <description>June &lt;b&gt;report&lt;/b&gt;</description><pubDate>Mon, 29 Jun 2026 00:11:00 GMT</pubDate></item>
<item><title>India win the fifth T20I</title>
 <link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fnews.example.org%2fwin</link>
 <description>Won by six wickets</description><pubDate>Fri, 16 Oct 2026 22:00:00 GMT</pubDate></item>
<item><title>Bad link</title><link>javascript:alert(1)</link><pubDate>Sat, 17 Oct 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.mark.parametrize(("query", "current"), [
    ("who won yesterday's match", True), ("latest news on the election", True), ("petrol price today", True),
    ("what happened in 2026", True), ("who was Akbar", False), ("how far is the moon", False),
])
def test_questions_about_now_are_told_apart(query, current):
    assert is_current(query) is current  # nosec B101


async def test_news_keeps_publisher_addresses_newest_first(monkeypatch):
    async def feed(url, params):
        assert "bing.com/news" in url and params["format"] == "rss"  # nosec B101
        return _FEED

    async def none(*a):
        return []

    monkeypatch.setattr(web_search, "_get_text", feed)
    monkeypatch.setattr(web_search, "_wikipedia_results", none)
    monkeypatch.setattr(web_search, "_ddg_instant_results", none)
    outcome = await search_sources("who won yesterday's match")
    assert [r.url for r in outcome.results] == ["https://news.example.org/win", "https://www.example.com/old"]  # nosec B101
    assert outcome.results[0].provider == "bing_news" and outcome.results[0].updated.startswith("2026-10-16")  # nosec B101
    assert outcome.results[1].snippet == "June report"  # nosec B101


async def test_news_comes_before_the_encyclopedia_for_a_question_about_now(monkeypatch):
    async def news(query, limit):
        return [web_search.SearchResult("News", "https://news.example.org/a", "", "bing_news", 0.0)]

    async def wiki(query, limit):
        return [web_search.SearchResult("Wiki", "https://en.wikipedia.org/wiki/A", "", "wikipedia", 0.0)]

    async def none(*a):
        return []

    monkeypatch.setattr(web_search, "_news_results", news)
    monkeypatch.setattr(web_search, "_wikipedia_results", wiki)
    monkeypatch.setattr(web_search, "_ddg_instant_results", none)
    outcome = await search_sources("latest score")
    assert [r.title for r in outcome.results] == ["News", "Wiki"]  # nosec B101


async def test_a_question_about_the_past_does_not_wait_for_news(monkeypatch):
    async def news(query, limit):
        raise AssertionError("news was searched")

    async def none(*a):
        return []

    monkeypatch.setattr(web_search, "_news_results", news)
    monkeypatch.setattr(web_search, "_wikipedia_results", none)
    monkeypatch.setattr(web_search, "_ddg_instant_results", none)
    assert (await search_sources("who was Akbar")).status == "empty"  # nosec B101


@pytest.mark.parametrize("query", [
    "Who won yesterday's India cricket match?", "What were the election results?", "Who plays tonight?",
])
def test_a_question_about_what_just_happened_is_researched_first(query):
    """These matched no live-data word, so the model answered from memory ("I don't know") without searching."""
    assert web_search.needs_web_search(query)  # nosec B101


@pytest.mark.parametrize("query", ["What is 17 times 23?", "Tell me a joke", "How do I boil an egg?"])
def test_a_question_that_needs_no_web_is_not_sent_there(query):
    assert not web_search.needs_web_search(query)  # nosec B101
