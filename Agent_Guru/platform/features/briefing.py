"""Morning briefing for Agent Guru.

'Hey Guru, good morning' → speaks a personalized daily briefing:
  - Current date and time
  - Weather (if location is known)
  - Top news headlines (via RSS)
  - Any pending reminders

This is what Alexa, Google Assistant, and ChatGPT Pulse all do.
It's the #2 most-used voice assistant feature after timers.

No API keys needed — uses free public RSS feeds for news and
wttr.in for weather (no key required).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def get_morning_briefing(location: Optional[str] = None) -> str:
    """Generate a morning briefing string for TTS.

    Args:
        location: City name for weather (e.g. "Mumbai"). Uses stored
                  user memory if not provided.

    Returns:
        A natural language briefing ready to be spoken.
    """
    parts = []

    # Date and time
    now = datetime.now()
    day_name = now.strftime("%A")
    date_str = now.strftime("%B %d")
    time_str = now.strftime("%I:%M %p").lstrip("0")
    parts.append(f"Good morning. Today is {day_name}, {date_str}. The time is {time_str}.")

    # Weather
    if not location:
        from Agent_Guru.platform.features.user_memory import get_user_memory
        location = get_user_memory().get("location")

    if location:
        weather = await _get_weather(location)
        if weather:
            parts.append(weather)

    # News headlines
    headlines = await _get_news_headlines(max_items=3)
    if headlines:
        parts.append("Here are today's top headlines.")
        parts.extend(headlines)

    parts.append("Have a great day.")
    return " ".join(parts)


async def _get_weather(location: str) -> Optional[str]:
    """Get current weather using wttr.in (no API key needed)."""
    try:
        import aiohttp
        import urllib.parse

        encoded = urllib.parse.quote(location)
        url = f"https://wttr.in/{encoded}?format=3"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=4),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp:
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


async def _get_news_headlines(max_items: int = 3) -> list[str]:
    """Get top news headlines from BBC RSS (no API key needed)."""
    try:
        import aiohttp
        import xml.etree.ElementTree as ET

        url = "https://feeds.bbci.co.uk/news/rss.xml"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=5),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp:
                if resp.status != 200:
                    return []
                content = await resp.text()

        root = ET.fromstring(content)
        headlines = []
        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", "").strip()
            if title and len(title) > 10:
                headlines.append(title + ".")

        return headlines
    except Exception as exc:
        logger.debug("News fetch failed: %s", exc)
    return []


def is_briefing_command(transcript: str) -> bool:
    """Return True if the user is asking for a morning briefing."""
    import re
    return bool(re.search(
        r"\b(good morning|morning briefing|daily briefing|"
        r"what.s my day|brief me|start my day|"
        r"what.s happening today|today.s summary)\b",
        transcript, re.I,
    ))
