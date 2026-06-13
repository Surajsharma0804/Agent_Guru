"""Main orchestrator for the Agent Guru audit system.

This module implements the AuditRunner that executes all 9 audit phases
in DAG order with proper error handling and phase dependency management.

Classes:
    AuditRunner: Main orchestrator for executing audit phases

Author: Agent Guru Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from audit.models import AuditReport
from audit.report import MasterReportWriter


class AuditRunner:
    """Main orchestrator for executing all 9 audit phases.

    Executes phases in DAG order with proper dependency management:
    - Phase 1 first (baseline)
    - Phases 2 and 3 after Phase 1
    - Phases 4 and 5 after Phase 3
    - Phase 6 after Phases 4 and 5
    - Phase 7 after Phase 6
    - Phase 8 after Phase 7
    - Phase 9 after Phases 2 and 8

    Attributes:
        report: The audit report being built
        writer: Report writer for atomic writes
        phase_status: Tracking dict for phase completion

    Example:
        >>> runner = AuditRunner()
        >>> await runner.run_all_phases()

    """

    def __init__(self) -> None:
        """Initialize the audit runner."""
        self.report = AuditReport()
        self.writer = MasterReportWriter()
        self.phase_status: dict[int, bool] = {}

    async def run_phase(
        self,
        phase_fn: Callable[[AuditReport], Awaitable[None]],
        phase_name: str,
        phase_number: int,
    ) -> bool:
        """Run a single audit phase with error handling.

        Args:
            phase_fn: Async function implementing the phase
            phase_name: Human-readable phase name
            phase_number: Phase number (1-9)

        Returns:
            True if phase succeeded, False if it failed

        """
        try:
            print(f"Starting {phase_name}...")
            await phase_fn(self.report)
            self.phase_status[phase_number] = True
            print(f"Completed {phase_name}")
            return True
        except Exception as exc:
            print(f"Failed {phase_name}: {exc}")
            self.writer.add_phase_error(phase_name, exc)
            self.phase_status[phase_number] = False
            return False

    async def run_all_phases(self) -> None:
        """Execute all 9 phases in DAG order.

        Phases are executed with dependency checks. If a phase fails,
        dependent phases are skipped.
        """
        # Import phase implementations
        from audit.phases import phase1_repo_scan

        # Phase 1: Must run first
        async def phase1(report: AuditReport) -> None:
            """Phase 1: Repository Intelligence Scan."""
            await phase1_repo_scan.run(report, self.writer)

        # Placeholder phase functions - will be implemented in subsequent tasks
        async def phase2(report: AuditReport) -> None:
            """Phase 2: Competitive Analysis."""

        async def phase3(report: AuditReport) -> None:
            """Phase 3: Bug and Failure Detection."""

        async def phase4(report: AuditReport) -> None:
            """Phase 4: Performance Optimization."""

        async def phase5(report: AuditReport) -> None:
            """Phase 5: Architectural Cleanup."""

        async def phase6(report: AuditReport) -> None:
            """Phase 6: Integration Validation."""

        async def phase7(report: AuditReport) -> None:
            """Phase 7: World-Class Code Quality."""

        async def phase8(report: AuditReport) -> None:
            """Phase 8: Deployment and Production Readiness."""

        async def phase9(report: AuditReport) -> None:
            """Phase 9: Final Master Audit Report."""

        # Phase 1: Must run first
        if not await self.run_phase(phase1, "Phase 1: Repository Intelligence Scan", 1):
            print("Phase 1 failed. Aborting audit.")
            return

        # Phases 2 and 3: Depend on Phase 1
        await self.run_phase(phase2, "Phase 2: Competitive Analysis", 2)
        phase3_success = await self.run_phase(
            phase3, "Phase 3: Bug and Failure Detection", 3,
        )

        # Phases 4 and 5: Depend on Phase 3
        if phase3_success:
            phase4_success = await self.run_phase(
                phase4, "Phase 4: Performance Optimization", 4,
            )
            phase5_success = await self.run_phase(
                phase5, "Phase 5: Architectural Cleanup", 5,
            )

            # Phase 6: Depends on Phases 4 and 5
            if phase4_success and phase5_success:
                phase6_success = await self.run_phase(
                    phase6, "Phase 6: Integration Validation", 6,
                )

                # Phase 7: Depends on Phase 6
                if phase6_success:
                    phase7_success = await self.run_phase(
                        phase7, "Phase 7: World-Class Code Quality", 7,
                    )

                    # Phase 8: Depends on Phase 7
                    if phase7_success:
                        await self.run_phase(
                            phase8, "Phase 8: Deployment and Production Readiness", 8,
                        )

        # Phase 9: Depends on Phases 2 and 8
        if self.phase_status.get(2, False) and self.phase_status.get(8, False):
            await self.run_phase(phase9, "Phase 9: Final Master Audit Report", 9)

        # Write final report
        self.writer.write(self.report)
        print("Audit complete. Report written to AUDIT_REPORT_MASTER.md")


async def main() -> None:
    """Entry point for running the audit."""
    runner = AuditRunner()
    await runner.run_all_phases()


if __name__ == "__main__":
    asyncio.run(main())
