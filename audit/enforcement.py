"""Enforcement gate for the Agent Guru audit system.

This module implements the enforcement gate that runs after each phase
to ensure no regressions are introduced. The gate runs pytest, ruff format,
ruff check, and mypy in sequence.

Functions:
    run_enforcement_gate: Run the full enforcement gate
    run_auto_fix_gate: Run auto-fixable tools then re-check

Author: Agent Guru Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path("Agent_Guru")


def run_enforcement_gate(phase_name: str) -> bool:
    """Run the full enforcement gate after a batch of changes.

    Runs in order: pytest → ruff format --check → ruff check → mypy.
    Stops and returns False on first failure.

    Args:
        phase_name: Name of the phase that just completed

    Returns:
        True if all checks pass, False if any check fails

    """
    checks = [
        ["pytest", str(PACKAGE_ROOT), "-x", "--tb=short", "-q"],
        ["ruff", "format", "--check", str(PACKAGE_ROOT)],
        ["ruff", "check", str(PACKAGE_ROOT), "--select", "ALL"],
        ["mypy", str(PACKAGE_ROOT), "--strict"],
    ]

    for cmd in checks:
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _log_gate_failure(phase_name, cmd, result)
            return False

    logger.info("✓ Enforcement gate passed for %s", phase_name)
    return True


def run_auto_fix_gate(phase_name: str) -> bool:
    """Run auto-fixable tools (ruff format + ruff check --fix), then re-check.

    Args:
        phase_name: Name of the phase that just completed

    Returns:
        True if all checks pass after auto-fix, False otherwise

    """
    logger.info("Running auto-fix for %s...", phase_name)

    # Run auto-fixable tools
    subprocess.run(  # noqa: S603
        ["ruff", "format", str(PACKAGE_ROOT)],  # noqa: S607
        check=True,
    )
    subprocess.run(  # noqa: S603
        ["ruff", "check", str(PACKAGE_ROOT), "--fix"],  # noqa: S607
        check=True,
    )

    # Re-run full gate
    return run_enforcement_gate(phase_name)


def _log_gate_failure(
    phase_name: str,
    cmd: list[str],
    result: subprocess.CompletedProcess[str],
) -> None:
    """Log enforcement gate failure.

    Args:
        phase_name: Name of the phase
        cmd: Command that failed
        result: Subprocess result

    """
    logger.error("✗ Enforcement gate failed for %s", phase_name)
    logger.error("Command: %s", " ".join(cmd))
    logger.error("Exit code: %d", result.returncode)
    logger.error("STDOUT:\n%s", result.stdout)
    logger.error("STDERR:\n%s", result.stderr)

    # Append to AUDIT_REPORT_MASTER.md
    report_path = Path("AUDIT_REPORT_MASTER.md")
    if report_path.exists():
        with report_path.open("a", encoding="utf-8") as f:
            f.write(f"\n\n### Enforcement Gate Failure: {phase_name}\n\n")
            f.write(f"**Command**: `{' '.join(cmd)}`\n\n")
            f.write(f"**Exit Code**: {result.returncode}\n\n")
            f.write(f"**Output**:\n```\n{result.stdout}\n{result.stderr}\n```\n")
