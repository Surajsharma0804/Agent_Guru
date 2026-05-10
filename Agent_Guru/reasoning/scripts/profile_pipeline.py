"""Profile the reasoning pipeline with py-spy to identify performance bottlenecks.

This script runs a representative workload through the pipeline and generates
profiling data including flame graphs for visualization.

Usage:
    # Install py-spy first:
    pip install py-spy

    # Run profiling:
    py-spy record -o profile.svg --native -- python Agent_Guru/reasoning/profile_pipeline.py

    # Or use this script directly:
    python Agent_Guru/reasoning/profile_pipeline.py
"""

import asyncio
import os
import sys
import time
from typing import Any

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from Agent_Guru.reasoning.models.intent import InputSource
from Agent_Guru.reasoning.pipeline import ReasoningPipeline

# Representative workload - common commands across different categories
WORKLOAD_COMMANDS = [
    # Simple commands (fast path)
    "set a timer for 5 minutes",
    "what's the weather like",
    "play some music",
    "turn on the lights",
    "what time is it",
    # Medium complexity commands
    "send a message to John saying I'll be late",
    "remind me to call mom tomorrow at 3pm",
    "show me my calendar for next week",
    "find restaurants near me",
    "what's my next meeting",
    # Complex multi-step commands
    "schedule a meeting with the team for tomorrow at 2pm and send them an email",
    "find a good Italian restaurant nearby, make a reservation for 7pm, and add it to my calendar",
    "check if I have any conflicts tomorrow afternoon and if not, schedule a dentist appointment",
    # Conversational commands (with context)
    "what about the day after",
    "cancel that",
    "make it 30 minutes instead",
    # Knowledge queries
    "when did I last talk to Sarah",
    "what apps do I use most in the morning",
    "show me my routine for weekdays",
]


async def run_workload(pipeline: ReasoningPipeline, iterations: int = 3) -> dict[str, Any]:
    """Run the workload through the pipeline multiple times.

    Args:
        pipeline: The reasoning pipeline to profile
        iterations: Number of times to run the full workload

    Returns:
        Dictionary with profiling statistics

    """
    stats = {
        "total_requests": 0,
        "total_time": 0.0,
        "command_times": {},
        "stage_times": {
            "input_normalization": [],
            "intent_detection": [],
            "reasoning": [],
            "tool_selection": [],
            "safety_validation": [],
            "execution": [],
            "response_generation": [],
        },
    }

    for iteration in range(iterations):
        for _i, command in enumerate(WORKLOAD_COMMANDS):
            start_time = time.perf_counter()

            try:
                # Process the command through the pipeline
                result = await pipeline.process(
                    text=command,
                    source=InputSource.TEXT,
                    user_id=f"profile_user_{iteration}",
                    conversation_id=f"profile_conv_{iteration}",
                )

                end_time = time.perf_counter()
                elapsed = end_time - start_time

                stats["total_requests"] += 1
                stats["total_time"] += elapsed

                # Track per-command timing
                if command not in stats["command_times"]:
                    stats["command_times"][command] = []
                stats["command_times"][command].append(elapsed)

                # Extract stage timings if available
                if hasattr(result, "metrics") and result.metrics:
                    for stage, duration in result.metrics.items():
                        if stage in stats["stage_times"]:
                            stats["stage_times"][stage].append(duration)

            except Exception:
                continue

    return stats


def print_statistics(stats: dict[str, Any]) -> None:
    """Print profiling statistics."""
    # Overall stats
    avg_time = stats["total_time"] / stats["total_requests"] if stats["total_requests"] > 0 else 0

    # Per-command stats
    command_avgs = []
    for command, times in stats["command_times"].items():
        if times:
            avg = sum(times) / len(times)
            p95 = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]
            command_avgs.append((command, avg, p95, len(times)))

    command_avgs.sort(key=lambda x: x[1], reverse=True)

    for _command, _avg, _p95, _count in command_avgs[:10]:  # Top 10 slowest
        pass

    # Stage-level stats
    for times in stats["stage_times"].values():
        if times:
            avg = sum(times) / len(times)
            p95 = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]

    # Performance targets
    target_avg = 1000  # 1.0s average
    target_p95 = 1500  # 1.5s P95

    if avg_time * 1000 < target_avg:
        pass
    else:
        pass

    # Calculate P95 from all command times
    all_times = []
    for times in stats["command_times"].values():
        all_times.extend(times)

    if all_times:
        all_times.sort()
        p95_overall = all_times[int(len(all_times) * 0.95)]

        if p95_overall * 1000 < target_p95:
            pass
        else:
            pass


async def main() -> None:
    """Main profiling function."""
    # Initialize pipeline
    try:
        pipeline = ReasoningPipeline()
    except Exception:
        return

    # Run workload
    try:
        stats = await run_workload(pipeline, iterations=3)
        print_statistics(stats)
    except Exception:
        import traceback

        traceback.print_exc()
        return


if __name__ == "__main__":
    asyncio.run(main())
