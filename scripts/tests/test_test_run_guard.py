"""The CI guard that a test job collected tests and ran all of them."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "test_run_guard", Path(__file__).resolve().parents[1] / "test_run_guard.py",
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

COLLECTED = """\
Agent_Guru/speech/tests/test_a.py::test_one
Agent_Guru/speech/tests/test_a.py::TestB::test_two[1]
Agent_Guru/platform/tests/test_c.py::test_three
============================ Hypothesis Statistics ============================
3/5 tests collected (2 deselected) in 0.20s
"""


def _junit(*names: str) -> str:
    cases = "".join(f'<testcase classname="c" name="{n}"/>' for n in names)
    return f'<testsuites><testsuite name="pytest" tests="{len(names)}">{cases}</testsuite></testsuites>'


def test_a_run_that_ran_everything_it_collected_passes():
    assert guard.check(COLLECTED, _junit("a", "b", "c")) == []  # nosec B101


def test_a_run_that_stopped_early_fails():
    problems = guard.check(COLLECTED, _junit("a", "b"))
    assert problems == ["the run reported 2 tests but 3 were collected; it stopped early"]  # nosec B101


def test_a_run_that_never_wrote_a_report_fails():
    # The 2026-10 failure: install or collection broke, so no report existed.
    assert guard.check(COLLECTED, None) == [  # nosec B101
        "the test run wrote no JUnit report; it did not run or did not finish",
    ]


def test_collecting_nothing_fails_even_with_a_report():
    problems = guard.check("no tests ran in 0.01s\n", _junit())
    assert "collection listed no tests" in problems  # nosec B101


def test_an_unfinished_collection_fails():
    unfinished = COLLECTED.rsplit("\n", 2)[0] + "\n"
    assert "collection printed no 'tests collected' summary; it may not have finished" in guard.check(  # nosec B101
        unfinished, _junit("a", "b", "c"),
    )


def test_a_teardown_error_reported_twice_is_one_test():
    # pytest writes a second testcase entry for an error in teardown of a
    # passing test; the guard counts tests, not entries.
    assert guard.check(COLLECTED, _junit("a", "a", "b", "c")) == []  # nosec B101


def test_counts_are_shown_per_package():
    assert guard.per_package(guard.collected_ids(COLLECTED)) == {  # nosec B101
        "Agent_Guru/platform": 1, "Agent_Guru/speech": 2,
    }
