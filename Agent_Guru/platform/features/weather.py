"""Current weather and a short forecast for a named place, from Open-Meteo.

Weather questions were answered from a web search: the search returned
pages about Delhi's climate and a year-old news item, and "what's the
weather in Delhi" came back with "the search results I pulled up are kinda
old ... check a dedicated weather app" and no forecast at all. Weather is a
structured fact with a free source that needs no key, so it is looked up
there: Open-Meteo's geocoding API turns the place into coordinates, and its
forecast API gives the current conditions, today's rain chance and three
days ahead.

The place that was resolved is part of the answer ("Delhi, National Capital
Territory of Delhi, India"), because the name alone is often ambiguous: of
the ten places Open-Meteo calls Delhi, nine are small towns in the United
States. The most populous match is taken and the answer says how many there
were, so a wrong pick is visible instead of silently wrong.

This goes to the internet. It is offered as a research tool (see
integration/research.py), so it passes the same policy check, injection
guard and source labelling as a web search, with a short timeout and a
plain sentence when the network or the service fails.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
#: Seconds for each of the two requests. A voice turn waits on this, and a
#: weather service that does not answer in that time is reported as down.
TIMEOUT_S = 6.0

#: WMO weather interpretation codes, as Open-Meteo documents them.
CONDITIONS = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle", 56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light rain showers",
    81: "rain showers", 82: "violent rain showers", 85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with heavy hail",
}


class WeatherError(Exception):
    """Why no weather could be given, in words the owner can be told."""


@dataclass(slots=True)
class DayForecast:
    date: str
    conditions: str
    high: float
    low: float
    rain_chance: int | None


@dataclass(slots=True)
class WeatherReport:
    """What Open-Meteo said for the place it resolved."""

    place: str
    matches: int
    latitude: float
    longitude: float
    timezone: str
    observed_at: str
    temperature: float
    feels_like: float | None
    conditions: str
    humidity: int | None
    precipitation: float | None
    wind: float | None
    units: dict[str, str]
    days: list[DayForecast] = field(default_factory=list)
    url: str = ""
    #: The WMO code behind `conditions`, for checks that need the kind of weather, not its name.
    weather_code: int = -1

    def summary(self) -> str:
        """The report as plain lines, with every number's unit, for the model to answer from."""
        u = self.units
        lines = [f"Place: {self.place}"]
        if self.matches > 1:
            lines.append(f"(the most populous of {self.matches} places with that name)")
        now = f"Now ({self.observed_at} local time): {self.conditions}, {self.temperature:g}{u.get('temperature_2m', '')}"
        if self.feels_like is not None:
            now += f", feels like {self.feels_like:g}{u.get('apparent_temperature', '')}"
        if self.humidity is not None:
            now += f", humidity {self.humidity}{u.get('relative_humidity_2m', '')}"
        if self.wind is not None:
            now += f", wind {self.wind:g} {u.get('wind_speed_10m', '')}"
        if self.precipitation:
            now += f", precipitation {self.precipitation:g} {u.get('precipitation', '')} in the last 15 minutes"
        lines.append(now)
        for day in self.days:
            # Not "chance of rain": a scheduled check told to say when the
            # report contains "rain" matched those words on every run, rain
            # or not, so a rain watch would have spoken every hour.
            rain = f", chance of precipitation {day.rain_chance}%" if day.rain_chance is not None else ""
            lines.append(f"{day.date}: {day.conditions}, high {day.high:g}{u.get('temperature_2m', '')}, "
                         f"low {day.low:g}{u.get('temperature_2m', '')}{rain}")
        return "\n".join(lines)


def _resolve(results: list[dict[str, Any]], name: str) -> tuple[dict[str, Any], int]:
    if not results:
        msg = f"I couldn't find a place called {name}."
        raise WeatherError(msg)
    best = max(results, key=lambda r: (r.get("population") or 0, -results.index(r)))
    return best, len(results)


def _place_name(place: dict[str, Any]) -> str:
    parts = [place.get("name"), place.get("admin1"), place.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    return ", ".join(seen)


def _report(place: dict[str, Any], matches: int, data: dict[str, Any], url: str) -> WeatherReport:
    """Raises KeyError, TypeError, ValueError or IndexError on an answer of the wrong shape."""
    current, units, daily = data["current"], data["current_units"], data.get("daily") or {}
    days = [
        DayForecast(
            date=date,
            conditions=CONDITIONS.get(int(daily["weather_code"][n]), f"weather code {daily['weather_code'][n]}"),
            high=float(daily["temperature_2m_max"][n]), low=float(daily["temperature_2m_min"][n]),
            rain_chance=(None if daily.get("precipitation_probability_max", [None] * (n + 1))[n] is None
                         else int(daily["precipitation_probability_max"][n])),
        )
        for n, date in enumerate(daily.get("time") or [])
    ]
    code = int(current["weather_code"])
    return WeatherReport(
        place=_place_name(place), matches=matches,
        latitude=float(place["latitude"]), longitude=float(place["longitude"]),
        timezone=str(data.get("timezone") or ""), observed_at=str(current["time"]).replace("T", " "),
        temperature=float(current["temperature_2m"]),
        feels_like=None if current.get("apparent_temperature") is None else float(current["apparent_temperature"]),
        conditions=CONDITIONS.get(code, f"weather code {code}"),
        humidity=None if current.get("relative_humidity_2m") is None else int(current["relative_humidity_2m"]),
        precipitation=None if current.get("precipitation") is None else float(current["precipitation"]),
        wind=None if current.get("wind_speed_10m") is None else float(current["wind_speed_10m"]),
        units={k: str(v) for k, v in units.items()}, days=days, url=url, weather_code=code,
    )


async def get_weather(place: str, *, client: Any = None, timeout_s: float = TIMEOUT_S) -> WeatherReport:
    """The weather now and the next three days for *place*; WeatherError says why not."""
    import httpx

    name = " ".join(place.split())[:100]
    if len(name) < 2:
        msg = "Which place should I get the weather for?"
        raise WeatherError(msg)
    own = client is None
    client = client or httpx.AsyncClient(timeout=timeout_s)
    try:
        geo = await client.get(GEOCODING_URL, params={"name": name, "count": 10, "language": "en", "format": "json"},
                               timeout=timeout_s)
        geo.raise_for_status()
        found = geo.json()
        if not isinstance(found, dict):
            raise ValueError("geocoding answer is not an object")
        best, matches = _resolve(found.get("results") or [], name)
        params = {
            "latitude": best["latitude"], "longitude": best["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,"
                       "wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 3,
        }
        forecast = await client.get(FORECAST_URL, params=params, timeout=timeout_s)
        forecast.raise_for_status()
        return _report(best, matches, forecast.json(), str(forecast.url))
    except WeatherError:
        raise
    except httpx.TimeoutException as exc:
        msg = f"The weather service didn't answer within {timeout_s:g} seconds."
        raise WeatherError(msg) from exc
    except httpx.HTTPStatusError as exc:
        msg = f"The weather service refused the request (HTTP {exc.response.status_code})."
        raise WeatherError(msg) from exc
    except httpx.TransportError as exc:
        msg = "I can't reach the weather service; this computer may be offline."
        raise WeatherError(msg) from exc
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.warning("Open-Meteo answer not understood: %s: %s", type(exc).__name__, exc)
        msg = "The weather service sent an answer I couldn't read."
        raise WeatherError(msg) from exc
    finally:
        if own:
            await client.aclose()


# ---- watching for a condition -------------------------------------------------------------
# "Tell me if it rains" was left to the model: gemma4 had to write notify_when "contains" and
# contains_text "rain" into a scheduling call, and in 30 live runs it never wrote the words, so
# 6 to 8 of 10 rain watches failed. The condition is now a fixed vocabulary the weather tool
# checks itself, and the owner's words are mapped to it in code (watch_from_words).

#: The conditions the weather tool can watch for; the temperature ones take degrees Celsius
#: as a separate number. An enum and a number, not one string with the limit inside: the tool
#: schema checker refuses regular expressions (a server's pattern could take unbounded time).
WATCHED = ("none", "rain", "temperature_above", "temperature_below")
DEGREES_RANGE = (-50, 60)
#: WMO codes that mean water is falling now: drizzle, rain, showers, thunderstorms.
RAIN_CODES = frozenset({51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99})
#: The first line of a report checked against a condition starts with one of these; the
#: scheduler speaks a watched check only when it starts with MET.
MET, NOT_MET = "Condition met:", "Condition not met:"


def condition_problem(condition: str, degrees: float | None) -> str | None:
    """What is wrong with a condition and its degrees together, or None."""
    if condition not in WATCHED:
        return f"condition is one of {', '.join(WATCHED)}"
    if condition.startswith("temperature_") and degrees is None:
        return f"condition {condition} needs degrees, the limit in degrees Celsius"
    return None


def check_condition(report: WeatherReport, condition: str, degrees: float | None = None) -> tuple[bool, str]:
    """Whether *condition* holds now in *report*, and one sentence saying so for the owner."""
    unit = report.units.get("temperature_2m", "")
    now = f"{report.conditions}, {report.temperature:g}{unit}"
    if condition == "rain":
        raining = report.weather_code in RAIN_CODES or bool(report.precipitation)
        said = f"It is raining in {report.place} now ({now})." if raining else f"No rain in {report.place} now ({now})."
        return raining, said
    problem = condition_problem(condition, degrees)
    if problem:
        raise ValueError(problem)
    kind, limit = condition, float(degrees)  # type: ignore[arg-type]
    if kind == "temperature_above":
        met = report.temperature > limit
        return met, f"It is {report.temperature:g}{unit} in {report.place}, {'above' if met else 'not above'} {limit:g}{unit}."
    if kind == "temperature_below":
        met = report.temperature < limit
        return met, f"It is {report.temperature:g}{unit} in {report.place}, {'below' if met else 'not below'} {limit:g}{unit}."
    msg = f"unknown condition {condition}"
    raise ValueError(msg)


def describe_condition(condition: str, degrees: float | None = None) -> str:
    """What the owner is told a watch will do: the same words the confirmation and the reply use."""
    if condition == "rain":
        return "tell you only when it rains"
    if condition == "temperature_above" and degrees is not None:
        return f"tell you only when it is above {float(degrees):g} degrees"
    if condition == "temperature_below" and degrees is not None:
        return f"tell you only when it is below {float(degrees):g} degrees"
    return "tell you what it finds each time"


@dataclass(slots=True)
class WeatherWatch:
    """A recurring weather check the owner's words asked for."""

    place: str
    condition: str
    every_minutes: int
    degrees: float | None = None


_WEATHER_WORDS = re.compile(r"\b(weather|rain\w*|temperature|degrees|baarish|barish|mausam)\b|बारिश|मौसम", re.IGNORECASE)
_RAIN_WORDS = re.compile(r"\b(rains?|raining|rainy|rainfall|baarish|barish)\b|बारिश", re.IGNORECASE)
_ABOVE = re.compile(r"\b(?:above|over|more than|higher than|exceeds?|crosses|goes (?:above|over|past)|hotter than)"
                    r"\s+(-?\d{1,2}(?:\.\d)?)", re.IGNORECASE)
_BELOW = re.compile(r"\b(?:below|under|less than|lower than|drops? (?:below|under)|falls? (?:below|under)|"
                    r"colder than)\s+(-?\d{1,2}(?:\.\d)?)", re.IGNORECASE)
_EVERY = re.compile(r"\bevery\s+(?:(\d{1,4})\s+)?(minutes?|mins?|hours?|hrs?)\b|\b(hourly|har ghante)\b", re.IGNORECASE)
_WATCH = re.compile(r"\bkeep (?:an eye|checking|watching|track)\b|\b(?:watch|monitor)\b|"
                    r"\b(?:tell|let|alert|notify|inform|ping)\s+me\b", re.IGNORECASE)
_PLACE = re.compile(r"\b(?:in|at|for)\s+([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3}?)"
                    r"(?=\s+(?:every|each|hourly|and|if|when|whenever|tell|let|please|till|until|today|now|"
                    r"har|mein|ke)\b|\s*[?.,!]|\s*$)", re.IGNORECASE)
_NOT_PLACES = frozenset({"the", "a", "an", "it", "me", "case", "degrees", "celsius", "minutes", "hours", "hour"})


def watch_from_words(text: str) -> WeatherWatch | None:
    """The recurring weather watch *text* asks for, or None when it does not clearly ask for one.

    Clear means: it is about the weather, it asks to repeat or to be told (every hour, hourly,
    keep an eye, tell me if), and it names a place after "in", "at" or "for". The condition is
    rain for rain words (English and Hindi), temperature_above or _below for a number after
    "above"/"below" and their synonyms, and none otherwise. Interval: what "every ..." says,
    or an hour.
    """
    if not _WEATHER_WORDS.search(text):
        return None
    every = _EVERY.search(text)
    if every is None and _WATCH.search(text) is None:
        return None
    place = None
    for match in _PLACE.finditer(text):
        words = match.group(1).strip(" .'-")
        if words and words.lower() not in _NOT_PLACES and not words.lower().startswith(("the weather", "case ")):
            place = words
            break
    if place is None:
        return None
    degrees = None
    if _RAIN_WORDS.search(text):
        condition = "rain"
    elif (above := _ABOVE.search(text)) is not None:
        condition, degrees = "temperature_above", float(above.group(1))
    elif (below := _BELOW.search(text)) is not None:
        condition, degrees = "temperature_below", float(below.group(1))
    else:
        condition = "none"
    if degrees is not None and not DEGREES_RANGE[0] <= degrees <= DEGREES_RANGE[1]:
        return None
    minutes = 60
    if every is not None and every.group(2):
        count = int(every.group(1) or 1)
        minutes = count if every.group(2).lower().startswith("min") else count * 60
    return WeatherWatch(place=place, condition=condition, every_minutes=max(5, min(minutes, 10080)), degrees=degrees)
