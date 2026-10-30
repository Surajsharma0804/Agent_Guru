"""Weather from Open-Meteo: the place it resolved, the numbers with units, and a plain reason when it fails.

The responses are Open-Meteo's own, recorded once on 2026-10-30 (fixtures/open_meteo), and served
through httpx.MockTransport, so nothing here reaches the internet; the suite's network gate refuses
Open-Meteo's hosts as well, which the offline test relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from Agent_Guru.platform.features import weather
from Agent_Guru.platform.features.weather import WeatherError, get_weather

RECORDED = Path(__file__).with_name("fixtures") / "open_meteo"


def _json(name: str) -> dict:
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


def _client(geocoding: str | dict, forecast: str | dict | None = "forecast_delhi.json", seen: list | None = None):
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.host == "geocoding-api.open-meteo.com":
            body = _json(geocoding) if isinstance(geocoding, str) else geocoding
        elif forecast is None:
            raise AssertionError("no forecast should be asked for")
        else:
            body = _json(forecast) if isinstance(forecast, str) else forecast
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


async def test_delhi_resolves_to_the_capital_not_one_of_nine_us_towns():
    seen: list[httpx.Request] = []
    report = await get_weather("Delhi", client=_client("geocoding_delhi.json", seen=seen))
    assert report.place == "Delhi, National Capital Territory of Delhi, India"
    assert report.matches == 10
    # The forecast is asked for the coordinates of the place that was resolved.
    assert seen[1].url.params["latitude"] == "28.65195" and seen[1].url.params["longitude"] == "77.23149"


async def test_the_report_carries_numbers_with_their_units():
    report = await get_weather("Delhi", client=_client("geocoding_delhi.json"))
    text = report.summary()
    assert "Place: Delhi, National Capital Territory of Delhi, India" in text
    assert "(the most populous of 10 places with that name)" in text
    assert "dense drizzle, 19.3°C, feels like 21.6°C, humidity 96%" in text
    assert "2026-10-30: violent rain showers, high 23.8°C, low 18.8°C, chance of rain 100%" in text
    assert report.units["wind_speed_10m"] == "km/h"


async def test_several_matches_take_the_most_populous_and_say_so():
    report = await get_weather("Springfield", client=_client("geocoding_springfield.json"))
    assert report.place == "Springfield, Missouri, United States" and report.matches == 10


async def test_the_most_populous_match_wins_wherever_it_is_listed():
    # Both recorded answers happen to list the most populous place first; here
    # the nine small Delhis of the United States come first.
    found = _json("geocoding_delhi.json")
    found["results"].reverse()
    report = await get_weather("Delhi", client=_client(found))
    assert report.place == "Delhi, National Capital Territory of Delhi, India"


async def test_an_unknown_place_is_said_plainly_and_no_forecast_is_asked():
    with pytest.raises(WeatherError, match="couldn't find a place called Qwxzvbnm"):
        await get_weather("Qwxzvbnm", client=_client("geocoding_unknown.json", forecast=None))


async def test_a_malformed_forecast_is_reported_not_guessed():
    broken = _json("forecast_delhi.json")
    del broken["current"]["temperature_2m"]
    with pytest.raises(WeatherError, match="couldn't read"):
        await get_weather("Delhi", client=_client("geocoding_delhi.json", forecast=broken))


async def test_a_geocoding_answer_that_is_not_an_object_is_reported():
    with pytest.raises(WeatherError, match="couldn't read"):
        await get_weather("Delhi", client=_client(["not", "an", "object"]))  # type: ignore[arg-type]


async def test_a_service_that_does_not_answer_in_time_is_reported():
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(WeatherError, match="didn't answer within 6 seconds"):
        await get_weather("Delhi", client=httpx.AsyncClient(transport=httpx.MockTransport(slow)))


async def test_an_error_status_is_reported_with_its_code():
    def refused(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": True, "reason": "too many requests"})

    with pytest.raises(WeatherError, match="HTTP 429"):
        await get_weather("Delhi", client=httpx.AsyncClient(transport=httpx.MockTransport(refused)))


async def test_offline_is_said_in_words_the_owner_can_act_on():
    # A real client and a real socket: the suite's network gate refuses Open-Meteo's
    # hosts, which is what a machine with no internet does too.
    with pytest.raises(WeatherError, match="can't reach the weather service"):
        await get_weather("Delhi", timeout_s=2.0)


async def test_no_place_asks_for_one():
    with pytest.raises(WeatherError, match="Which place"):
        await get_weather(" ", client=_client("geocoding_delhi.json", forecast=None))


def test_every_condition_named_in_the_fixture_is_known():
    days = _json("forecast_delhi.json")["daily"]["weather_code"]
    assert all(code in weather.CONDITIONS for code in days)
