"""The schedule_check example names a tool the running assistant really offers.

It named eval__get_weather, which exists only in the evaluation server. In the live app gemma4
copied the pattern and invented "weather__get_weather" (3 of 3 runs), the call was refused, and
"keep an eye on the weather in Delhi every hour" was never scheduled.
"""

from __future__ import annotations

import json
import re

from Agent_Guru.integration import research
from Agent_Guru.integration.task_tools import TaskTools


def test_the_example_tool_is_the_assistants_own_weather_tool():
    # It was web_research with a query; weather now has its own tool, which
    # an hourly weather watch should repeat (Open-Meteo, not a web search).
    (check,) = [t for t in TaskTools().tool_list() if t["name"] == "schedule_check"]
    example = json.loads(re.search(r"\{.*?\}", check["description"]).group(0))
    offered = {t["name"] for t in research.ResearchTools().tool_list()}
    server, _, tool = example["tool"].partition("__")
    assert server == research.SERVER_NAME and tool in offered  # nosec B101
    assert tool == "weather" and "place" in example and example["every_minutes"] == 60  # nosec B101


def test_the_example_in_the_error_names_a_real_tool_too():
    # The error for a check with nothing to repeat still named eval__get_weather,
    # which only the evaluation server has; gemma4 copied the examples it was shown.
    import inspect

    from Agent_Guru.integration import task_tools

    named = set(re.findall(r'"tool": "([a-z_]+)"', inspect.getsource(task_tools)))
    offered = {f"{research.SERVER_NAME}__{t['name']}" for t in research.ResearchTools().tool_list()}
    assert named and named <= offered  # nosec B101
