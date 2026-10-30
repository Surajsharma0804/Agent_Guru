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
    assert "2026-10-30: violent rain showers, high 23.8°C, low 18.8°C, chance of precipitation 100%" in text


async def test_only_rain_itself_makes_the_report_mention_rain():
    # A check that tells the owner when the report contains "rain" must not
    # fire on a dry day. The recorded forecast's last day is clear (code 0).
    dry = _json("forecast_delhi.json")
    dry["current"]["weather_code"] = 0
    dry["daily"]["weather_code"] = [0, 1, 2]
    report = await get_weather("Delhi", client=_client("geocoding_delhi.json", forecast=dry))
    assert "rain" not in report.summary().lower()
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


# ---- watching for a condition ----
# "Tell me if it rains" was left to the model, which never wrote what to watch
# for: 10 of 10 live rain watches and 10 of 10 temperature watches ended without
# the right task. The words are now mapped in code.

from Agent_Guru.platform.features.weather import (  # noqa: E402
    MET,
    WeatherWatch,
    check_condition,
    condition_problem,
    describe_condition,
    watch_from_words,
)


@pytest.mark.parametrize(("said", "watch"), [
    ("check the weather in Delhi every hour and tell me if it rains", WeatherWatch("Delhi", "rain", 60)),
    ("keep an eye on the weather in Delhi every hour", WeatherWatch("Delhi", "none", 60)),
    ("check the temperature in Delhi every hour and tell me if it goes above 40",
     WeatherWatch("Delhi", "temperature_above", 60, 40.0)),
    ("watch the temperature in Shimla every 2 hours and tell me when it drops below 5",
     WeatherWatch("Shimla", "temperature_below", 120, 5.0)),
    ("check the weather in Mumbai every 30 minutes and tell me if there is baarish", WeatherWatch("Mumbai", "rain", 30)),
    ("tell me when it rains in Pune", WeatherWatch("Pune", "rain", 60)),
    ("watch the weather in New Delhi hourly", WeatherWatch("New Delhi", "none", 60)),
])
def test_the_owners_words_become_a_watch(said, watch):
    assert watch_from_words(said) == watch


@pytest.mark.parametrize("said", [
    "what's the weather in Delhi",          # a question now, not a watch
    "keep an eye on the weather",           # no place
    "remind me every hour to drink water",  # not the weather
    "tell me if the temperature in Delhi goes above 400",  # not a temperature
])
def test_words_that_do_not_spell_out_a_watch_are_left_to_the_model(said):
    assert watch_from_words(said) is None


async def _delhi(**changes):
    forecast = _json("forecast_delhi.json")
    forecast["current"].update(changes)
    return await get_weather("Delhi", client=_client("geocoding_delhi.json", forecast=forecast))


async def test_rain_holds_when_water_is_falling_and_not_on_a_dry_day():
    raining, said = check_condition(await _delhi(), "rain")  # the recording: dense drizzle, 0.3 mm
    assert raining and said.startswith("It is raining in Delhi, National Capital Territory of Delhi, India now")
    # Rain reported by its code, with nothing measured in the last 15 minutes yet.
    assert check_condition(await _delhi(weather_code=61, precipitation=0.0), "rain")[0]
    dry, said = check_condition(await _delhi(weather_code=2, precipitation=0.0), "rain")
    assert not dry and said == "No rain in Delhi, National Capital Territory of Delhi, India now (partly cloudy, 19.3°C)."


async def test_temperature_limits_hold_only_past_the_limit():
    report = await _delhi()  # 19.3°C
    assert check_condition(report, "temperature_above", 19)[0] and not check_condition(report, "temperature_above", 40)[0]
    assert check_condition(report, "temperature_below", 20)[0] and not check_condition(report, "temperature_below", 19.3)[0]


def test_a_temperature_watch_needs_its_limit():
    assert condition_problem("temperature_above", None) and condition_problem("snow", None)
    assert condition_problem("rain", None) is None and condition_problem("temperature_below", 5) is None


def test_the_words_said_for_each_condition():
    assert describe_condition("rain") == "tell you only when it rains"
    assert describe_condition("temperature_above", 40) == "tell you only when it is above 40 degrees"
    assert describe_condition("none") == "tell you what it finds each time"
    assert MET == "Condition met:"
