"""Fail a CI test job that collected nothing or did not run what it collected.

From 2026-10-05 to 2026-10-12 no CI run reached a single test: on Python
3.11 and 3.12 `pip install -e ".[test]"` could not resolve, and on 3.13 two
collection errors stopped the job. Every run was red, but red for a reason
nobody read, and a run that installs and then reaches no tests is exactly
what a later change (a narrowed testpaths, a conftest that skips
everything, a crash half way through) could turn green. This check makes
"tests ran" something the job proves, not something it assumes.

It compares the run with its own collection, not with a fixed number:

* the collection step (``pytest --collect-only -qq``) must list at least
  one test, and its node IDs must agree with its own summary line;
* the JUnit report of the run must account for every collected test
  (passed, failed, errored or skipped). Fewer means the run stopped early.

Usage: python scripts/test_run_guard.py <collect-only output> <junit xml>
Exits 1 with the reason when either check fails. With GITHUB_STEP_SUMMARY
set, it also writes the counts per top-level package there, so a package
whose tests vanished is visible on the run page.
"""

from __future__ import annotations

import collections
import os
import re
import sys
import xml.etree.ElementTree as ET  # nosec B405 - parses the job's own pytest report
from pathlib import Path

_SUMMARY = re.compile(r"(?:(\d+)/)?(\d+) tests? collected")


def collected_ids(collect_output: str) -> list[str]:
    """The test node IDs a ``pytest --collect-only -qq`` run printed."""
    return [line.strip() for line in collect_output.splitlines() if "::" in line and not line.startswith(" ")]


def summary_count(collect_output: str) -> int | None:
    """The selected-test count from the summary line ("26 tests collected", "6293/6308 tests collected")."""
    found = _SUMMARY.findall(collect_output)
    if not found:
        return None
    selected, total = found[-1]
    return int(selected or total)


def junit_count(junit_xml: str) -> int:
    """The test cases a pytest JUnit report contains, each counted once."""
    root = ET.fromstring(junit_xml)  # nosec B314 - the job's own pytest report
    return len({(case.get("classname"), case.get("name")) for case in root.iter("testcase")})


def per_package(ids: list[str]) -> dict[str, int]:
    """Collected tests per top-level package, from node IDs like Agent_Guru/speech/tests/..."""
    counts: collections.Counter[str] = collections.Counter()
    for node in ids:
        parts = node.split("::", 1)[0].replace("\\", "/").split("/")
        counts["/".join(parts[:2]) if len(parts) > 2 else parts[0]] += 1
    return dict(sorted(counts.items()))


def check(collect_output: str, junit_xml: str | None) -> list[str]:
    """Every reason the run cannot be trusted to have run its tests; [] when it did."""
    problems = []
    ids = collected_ids(collect_output)
    stated = summary_count(collect_output)
    if not ids:
        problems.append("collection listed no tests")
    if stated is None:
        problems.append("collection printed no 'tests collected' summary; it may not have finished")
    elif stated != len(ids):
        problems.append(f"collection summary says {stated} tests but listed {len(ids)}")
    if junit_xml is None:
        problems.append("the test run wrote no JUnit report; it did not run or did not finish")
    else:
        ran = junit_count(junit_xml)
        if ran < len(ids):
            problems.append(f"the run reported {ran} tests but {len(ids)} were collected; it stopped early")
    return problems


def main(argv: list[str]) -> int:
    collect_path, junit_path = Path(argv[1]), Path(argv[2])
    collect_output = collect_path.read_text(encoding="utf-8", errors="replace") if collect_path.exists() else ""
    junit_xml = junit_path.read_text(encoding="utf-8") if junit_path.exists() else None
    ids = collected_ids(collect_output)
    problems = check(collect_output, junit_xml)
    lines = [f"Collected {len(ids)} tests; the run reported {junit_count(junit_xml) if junit_xml else 0}.", ""]
    lines += ["| Package | Collected |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in per_package(ids).items()]
    lines += ["", *(f"FAILED: {p}" for p in problems)]
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(["### Tests collected and run", "", *lines]) + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
