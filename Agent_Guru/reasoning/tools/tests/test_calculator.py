"""The calculator answers what people say, refuses what is not arithmetic, and never raises.

Before the rewrite, "What is 15% of 200" (the tool's own example) was refused
for its letters, sqrt, sin and log were unknown, and "(1+2", "9**9**9" and a
5,000-term sum raised out of execute() instead of returning an error. A
side-by-side run against another assistant's calculator on 15 expressions
found it answered or refused correctly 6 times out of 15.
"""

from __future__ import annotations

import asyncio

import pytest

from Agent_Guru.reasoning.tools.knowledge.information import (
    MAX_RESULT_DIGITS,
    CalculateTool,
    CalculationError,
    evaluate_expression,
)


def run(expression):
    return asyncio.run(CalculateTool().execute(expression=expression))


@pytest.mark.parametrize(("spoken", "value"), [
    ("2 + 3 * (4 - 1) / 2", 6.5),
    ("What is 15% of 200?", 30),
    ("15 percent of 80", 12),
    ("square root of 144", 12),
    ("cube root of 27", 3),
    ("5 squared", 25),
    ("2 cubed", 8),
    ("3 x 4", 12),
    ("10 divided by 4", 2.5),
    ("7 times 6", 42),
    ("2 to the power of 10", 1024),
    ("2^10", 1024),
    ("1,000 + 1", 1001),
    ("10 % 3", 1),  # modulo when a number follows the sign
    ("sqrt(16) + 2**10", 1028),
    ("sin(pi/2)", 1),
    ("log(100, 10)", 2),
    ("ln(e)", 1),
    ("factorial(5)", 120),
    ("0.1 + 0.2", 0.3),
])
def test_spoken_and_written_calculations_are_answered(spoken, value):
    result = run(spoken)
    assert result["success"], result  # nosec B101
    assert result["result"]["result"] == pytest.approx(value)  # nosec B101


@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo pwned')",
    "().__class__.__bases__[0].__subclasses__()",
    "open('/etc/passwd').read()",
    "'a' * 10",
    "x + 1",
    "print(1)",
    "sqrt(x=4)",
])
def test_anything_but_arithmetic_is_refused(expression):
    result = run(expression)
    assert result["success"] is False and result["error"]  # nosec B101


@pytest.mark.parametrize("expression", ["9**9**9", "10**10**8", "factorial(100000)", "2**40000"])
def test_results_too_large_to_compute_are_refused_before_computing(expression):
    result = run(expression)
    assert result["success"] is False  # nosec B101
    assert "digits" in result["error"] or "too large" in result["error"]  # nosec B101


@pytest.mark.parametrize(("expression", "words"), [
    ("1/0", "divide by zero"),
    ("(1+2", "could not read"),
    ("(-8)**0.5", "not a real number"),
    ("sqrt(-1)", "outside what the function accepts"),
    ("", "cannot be empty"),
])
def test_errors_come_back_as_results_not_exceptions(expression, words):
    result = run(expression)
    assert result["success"] is False and words in result["error"]  # nosec B101


def test_a_sum_too_long_for_the_parser_is_still_added_up():
    # Python's parser gives up at about 2,000 terms on Windows with 3.13.
    assert run("+".join(["1"] * 5000))["result"]["result"] == 5000  # nosec B101
    assert run("+".join(["2*3"] * 4000) + "-1")["result"]["result"] == 23999  # nosec B101


def test_the_size_limit_is_the_one_documented():
    with pytest.raises(CalculationError):
        evaluate_expression(f"10**{MAX_RESULT_DIGITS + 1}")
    assert evaluate_expression(f"10**{MAX_RESULT_DIGITS - 1}") == 10 ** (MAX_RESULT_DIGITS - 1)  # nosec B101


def test_whole_results_are_said_without_a_decimal_point():
    assert run("sqrt(16)")["result"]["message"].endswith("= 4")  # nosec B101
    assert run("0.1+0.2")["result"]["message"].endswith("= 0.3")  # nosec B101
