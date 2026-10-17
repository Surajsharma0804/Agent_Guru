"""Morning briefing for Agent Guru.

'Hey Guru, good morning' → speaks a personalized daily briefing:
  - Current date and time
  - Weather (if location is known)
  - Top news headlines (via RSS)
  - Any pending reminders

This is what Alexa, Google Assistant, and ChatGPT Pulse all do.
It's the #2 most-used voice assistant feature after timers.

No API keys needed - uses free public RSS feeds for news and
wttr.in for weather (no key required).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


#: Each part from a service gets this long; a slow one is left out, not waited for.
_SOURCE_TIMEOUT_S = 6.0


async def get_morning_briefing(
    location: str | None = None,
    *,
    reminders: list[Any] | None = None,
    connectors: Any = None,
    now: datetime | None = None,
) -> str:
    """Generate a morning briefing string for TTS.

    Args:
        location: City name for weather (e.g. "Mumbai"). Uses stored
                  user memory if not provided.
        reminders: the reminder manager's pending reminders; today's are said.
        connectors: the owner's connector tools (connectors/tools.py); a
                  calendar or task list that is connected is read for today.
        now: the moment to brief for; the local clock by default.

    Returns:
        A natural language briefing ready to be spoken.

    """
    parts = []

    # Date and time, on the local clock. This used datetime.now(tz=UTC):
    # in India the briefing said 02:43 PM at 08:13 PM, and "good morning"
    # at any hour.
    now = now or datetime.now().astimezone()
    day_name = now.strftime("%A")
    date_str = now.strftime("%B %d")
    time_str = now.strftime("%I:%M %p").lstrip("0")
    greeting = "Good morning" if now.hour < 12 else ("Good afternoon" if now.hour < 17 else "Good evening")
    parts.append(f"{greeting}. Today is {day_name}, {date_str}. The time is {time_str}.")

    # Weather
    if not location:
        from Agent_Guru.platform.features.user_memory import get_user_memory

        location = get_user_memory().get("location")

    if location:
        weather = await _get_weather(location)
        if weather:
            parts.append(weather)

    said = _todays_reminders(reminders or [], now)
    if said:
        parts.append(said)
    if connectors is not None:
        parts.extend(await _from_accounts(connectors, now))

    # News headlines
    headlines = await _get_news_headlines(max_items=3)
    if headlines:
        parts.append("Here are today's top headlines.")
        parts.extend(headlines)

    parts.append("Have a great day.")
    return " ".join(parts)


def _clock(moment: datetime) -> str:
    return moment.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def _listed(items: list[str], limit: int = 4) -> str:
    shown = items[:limit] + ([f"{len(items) - limit} more"] if len(items) > limit else [])
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def _todays_reminders(reminders: list[Any], now: datetime) -> str:
    """Spoken reminders still due today (scheduled checks and actions are not reminders)."""
    end = now.replace(hour=23, minute=59, second=59)
    due = sorted(
        (r for r in reminders
         if getattr(r, "kind", "say") == "say" and not getattr(r, "fired", False)
         and now.timestamp() <= r.fire_at <= end.timestamp()),
        key=lambda r: r.fire_at,
    )
    if not due:
        return ""
    items = [f"{r.message} at {_clock(datetime.fromtimestamp(r.fire_at, tz=now.tzinfo))}" for r in due]
    return f"Reminders today: {_listed(items)}."


async def _from_accounts(connectors: Any, now: datetime) -> list[str]:
    """Today's calendar and open tasks, from the accounts the owner connected; nothing for one that fails."""
    import asyncio

    try:
        usable = {tool["name"] for tool in connectors.tool_list()}
    except Exception as exc:
        logger.debug("Connector tools unavailable for the briefing: %s", exc)
        return []

    async def ask(name: str, arguments: dict[str, Any]) -> str | None:
        if name not in usable:
            return None
        try:
            answer = await asyncio.wait_for(connectors.call(name, arguments), _SOURCE_TIMEOUT_S)
        except Exception as exc:
            logger.debug("Briefing: %s failed: %s", name, exc)
            return None
        return None if answer[1] else str(answer[0])

    calendar, tasks = await asyncio.gather(ask("calendar_events", {"days": 1}), ask("tasks_list", {}))
    parts = []
    if calendar is not None:
        events = []
        for line in calendar.splitlines():
            when, _, rest = line.partition(" | ")
            title = rest.split(" | ", 1)[0].strip()
            if not title:
                continue
            try:
                start = datetime.fromisoformat(when.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
            if "T" not in when:  # an all-day event
                if start.date() == now.date():
                    events.append(f"{title} all day")
                continue
            start = start.astimezone(now.tzinfo) if start.tzinfo else start.replace(tzinfo=now.tzinfo)
            if start.date() == now.date():
                events.append(f"{title} at {_clock(start)}")
        if events:
            count = "one event" if len(events) == 1 else f"{len(events)} events"
            parts.append(f"You have {count} today: {_listed(events)}.")
        else:
            parts.append("Nothing is on your calendar for the rest of today.")
    if tasks is not None:
        open_tasks = [line.strip() for line in tasks.splitlines() if line.strip() and line.strip() != "No open tasks."]
        if open_tasks:
            count = "one open task" if len(open_tasks) == 1 else f"{len(open_tasks)} open tasks"
            parts.append(f"You have {count}: {_listed(open_tasks, 2)}.")
    return parts


async def _get_weather(location: str) -> str | None:
    """Get current weather using wttr.in (no API key needed)."""
    try:
        import urllib.parse

        import aiohttp

        encoded = urllib.parse.quote(location)
        url = f"https://wttr.in/{encoded}?format=3"

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=4),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp,
        ):
            if resp.status == 200:
                text = (await resp.text()).strip()
                # wttr.in format 3: "City: ⛅ +22°C"
                # Clean up emoji and format for TTS
                import re

                text = re.sub(r"[^\x00-\x7F]+", "", text)  # remove emoji
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    return f"The weather in {location} is {text}."
    except Exception as exc:
        logger.debug("Weather fetch failed: %s", exc)
    return None


async def _get_news_headlines(
    max_items: int = 3, url: str = "https://feeds.bbci.co.uk/news/rss.xml", *, with_links: bool = False,
) -> list[str]:
    """Top headlines from an RSS or Atom feed (BBC by default; no API key needed).

    It read BBC's RSS only; the news tool (connectors/tools.py) passes the
    owner's own feeds, which are often Atom (<entry> with <link href>).
    """
    try:
        from Agent_Guru.security.xml_utils import safe_xml_parse

        import aiohttp

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=5),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp,
        ):
            if resp.status != 200:
                return []
            content = await resp.text()

        root = safe_xml_parse(content)
        atom = "{http://www.w3.org/2005/Atom}"
        items = root.findall(".//item") or root.findall(f".//{atom}entry")
        headlines = []
        for item in items[:max_items]:
            title = (item.findtext("title") or item.findtext(f"{atom}title") or "").strip()
            if not title or len(title) <= 10:
                continue
            if with_links:
                link = (item.findtext("link") or "").strip()
                if not link:
                    node = item.find(f"{atom}link")
                    link = node.get("href", "") if node is not None else ""
                headlines.append(f"{title} - {link}" if link else title)
            else:
                headlines.append(title + ".")

        return headlines
    except Exception as exc:
        logger.debug("News fetch failed: %s", exc)
    return []


def is_briefing_command(transcript: str) -> bool:
    """Return True if the user is asking for a morning briefing."""
    import re

    return bool(
        re.search(
            r"\b(good morning|morning briefing|daily briefing|"
            r"what.s my day|brief me|start my day|"
            r"what.s happening today|today.s summary)\b",
            transcript,
            re.IGNORECASE,
        ),
    )
