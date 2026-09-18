"""Test scenarios for the benchmark suite.

Provides pre-built test scenarios for benchmarking the Agent Guru self-improvement
engine and comparing against other frameworks.

Author: Agent Guru Team
Date: 2026-07-26
"""

from __future__ import annotations

from Agent_Guru.self_improvement.benchmarks.base_benchmark import (
    ScenarioType,
    TestScenario,
)


# ---------------------------------------------------------------------------
# Simple scenarios — basic command execution
# ---------------------------------------------------------------------------

_SIMPLE_SCENARIOS = [
    TestScenario(
        scenario_id="simple_001",
        name="Open Application",
        description="Open a common application like Notepad.",
        scenario_type=ScenarioType.SIMPLE,
        input_data={"question": "open notepad"},
        difficulty=1,
    ),
    TestScenario(
        scenario_id="simple_002",
        name="Set Volume",
        description="Set system volume to a specific level.",
        scenario_type=ScenarioType.SIMPLE,
        input_data={"question": "set volume to 50"},
        difficulty=1,
    ),
    TestScenario(
        scenario_id="simple_003",
        name="Get Time",
        description="Ask for current time.",
        scenario_type=ScenarioType.SIMPLE,
        input_data={"question": "what time is it"},
        difficulty=1,
    ),
    TestScenario(
        scenario_id="simple_004",
        name="Play Music",
        description="Play a music track.",
        scenario_type=ScenarioType.SIMPLE,
        input_data={"question": "play some music"},
        difficulty=1,
    ),
    TestScenario(
        scenario_id="simple_005",
        name="Weather Query",
        description="Ask about the weather.",
        scenario_type=ScenarioType.SIMPLE,
        input_data={"question": "what is the weather like today"},
        difficulty=1,
    ),
]


# ---------------------------------------------------------------------------
# Complex scenarios — multi-step reasoning
# ---------------------------------------------------------------------------

_COMPLEX_SCENARIOS = [
    TestScenario(
        scenario_id="complex_001",
        name="Multi-step File Operation",
        description="Create a folder, move files into it, and rename.",
        scenario_type=ScenarioType.COMPLEX,
        input_data={"question": "create a folder called backup and move all txt files there"},
        difficulty=3,
    ),
    TestScenario(
        scenario_id="complex_002",
        name="Conditional Task",
        description="Perform action based on condition.",
        scenario_type=ScenarioType.COMPLEX,
        input_data={"question": "if battery is below 20 percent enable power saver mode"},
        difficulty=4,
    ),
    TestScenario(
        scenario_id="complex_003",
        name="Chained Operations",
        description="Multiple operations in sequence.",
        scenario_type=ScenarioType.COMPLEX,
        input_data={"question": "close all browsers, clear temp files, and restart explorer"},
        difficulty=4,
    ),
]


# ---------------------------------------------------------------------------
# Tool usage scenarios
# ---------------------------------------------------------------------------

_TOOL_USAGE_SCENARIOS = [
    TestScenario(
        scenario_id="tool_001",
        name="Screenshot Capture",
        description="Take a screenshot and save it.",
        scenario_type=ScenarioType.TOOL_USAGE,
        input_data={"question": "take a screenshot"},
        difficulty=2,
    ),
    TestScenario(
        scenario_id="tool_002",
        name="File Search",
        description="Search for files matching a pattern.",
        scenario_type=ScenarioType.TOOL_USAGE,
        input_data={"question": "find all pdf files in documents"},
        difficulty=2,
    ),
    TestScenario(
        scenario_id="tool_003",
        name="System Info",
        description="Get detailed system information.",
        scenario_type=ScenarioType.TOOL_USAGE,
        input_data={"question": "show me system info including CPU, RAM, and disk usage"},
        difficulty=2,
    ),
]


# ---------------------------------------------------------------------------
# Error recovery scenarios
# ---------------------------------------------------------------------------

_ERROR_RECOVERY_SCENARIOS = [
    TestScenario(
        scenario_id="error_001",
        name="Missing File Recovery",
        description="Handle attempt to open non-existent file.",
        scenario_type=ScenarioType.ERROR_RECOVERY,
        input_data={"question": "open file nonexistent_document.txt"},
        difficulty=2,
    ),
    TestScenario(
        scenario_id="error_002",
        name="Permission Denied Recovery",
        description="Handle permission-denied file operation.",
        scenario_type=ScenarioType.ERROR_RECOVERY,
        input_data={"question": "delete system32 folder"},
        difficulty=3,
    ),
    TestScenario(
        scenario_id="error_003",
        name="Invalid Command Recovery",
        description="Gracefully handle gibberish input.",
        scenario_type=ScenarioType.ERROR_RECOVERY,
        input_data={"question": "xyzzy flurble gnork"},
        difficulty=2,
    ),
]


# ---------------------------------------------------------------------------
# Learning scenarios — improvement over time
# ---------------------------------------------------------------------------

_LEARNING_SCENARIOS = [
    TestScenario(
        scenario_id="learn_001",
        name="User Preference Learning",
        description="Learn and apply user preferences over time.",
        scenario_type=ScenarioType.LEARNING,
        input_data={"question": "remember I prefer dark mode"},
        difficulty=3,
    ),
    TestScenario(
        scenario_id="learn_002",
        name="Pattern Recognition",
        description="Recognize repeated patterns and suggest automation.",
        scenario_type=ScenarioType.LEARNING,
        input_data={"question": "I always open Chrome, Slack, and VS Code in the morning"},
        difficulty=4,
    ),
    TestScenario(
        scenario_id="learn_003",
        name="Error Pattern Learning",
        description="Learn from past errors to avoid repeating them.",
        scenario_type=ScenarioType.LEARNING,
        input_data={"question": "retry the task that failed yesterday"},
        difficulty=5,
    ),
]


# ---------------------------------------------------------------------------
# Public API — scenario getters
# ---------------------------------------------------------------------------


def get_simple_scenarios() -> list[TestScenario]:
    """Return all simple benchmark scenarios."""
    return list(_SIMPLE_SCENARIOS)


def get_complex_scenarios() -> list[TestScenario]:
    """Return all complex benchmark scenarios."""
    return list(_COMPLEX_SCENARIOS)


def get_tool_usage_scenarios() -> list[TestScenario]:
    """Return all tool usage benchmark scenarios."""
    return list(_TOOL_USAGE_SCENARIOS)


def get_error_recovery_scenarios() -> list[TestScenario]:
    """Return all error recovery benchmark scenarios."""
    return list(_ERROR_RECOVERY_SCENARIOS)


def get_learning_scenarios() -> list[TestScenario]:
    """Return all learning benchmark scenarios."""
    return list(_LEARNING_SCENARIOS)


def get_all_scenarios() -> list[TestScenario]:
    """Return all benchmark scenarios across all categories."""
    return (
        get_simple_scenarios()
        + get_complex_scenarios()
        + get_tool_usage_scenarios()
        + get_error_recovery_scenarios()
        + get_learning_scenarios()
    )
