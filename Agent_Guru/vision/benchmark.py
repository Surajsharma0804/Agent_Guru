"""
GuruVision performance benchmarking script.

Measures FPS, per-frame latency, and memory usage for the recognition pipeline.

Usage:
    python -m Agent_Guru.vision.benchmark [--frames 100] [--config config.yaml]

Requirements: 14.1, 14.2, 14.3, 14.4, 32.3
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from typing import List

import numpy as np


def _measure_memory_mb() -> float:
    try:
        import psutil
        import os
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / 1024 / 1024
    except ImportError:
        return -1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="GuruVision performance benchmark")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to benchmark")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    parser.add_argument("--config", default=None, help="Optional config file")
    args = parser.parse_args()

    from Agent_Guru.vision.engine import GuruVisionEngine

    print(f"\nGuruVision Benchmark — {args.frames} frames @ {args.width}x{args.height}")
    print("=" * 55)

    engine = GuruVisionEngine(config_path=args.config)

    # Measure init time
    t0 = time.perf_counter()
    engine.initialize()
    init_ms = (time.perf_counter() - t0) * 1000
    print(f"  Initialization time : {init_ms:.1f} ms")

    mem_after_init = _measure_memory_mb()
    if mem_after_init >= 0:
        print(f"  Memory after init   : {mem_after_init:.1f} MB")

    # Warm-up
    dummy = np.zeros((args.height, args.width, 3), dtype=np.uint8)
    for _ in range(5):
        engine.process_frame(dummy)

    # Benchmark
    latencies: List[float] = []
    for _ in range(args.frames):
        frame = np.random.randint(0, 256, (args.height, args.width, 3), dtype=np.uint8)
        t = time.perf_counter()
        engine.process_frame(frame)
        latencies.append((time.perf_counter() - t) * 1000)

    mem_peak = _measure_memory_mb()

    engine.shutdown()

    mean_ms = statistics.mean(latencies)
    p50_ms = statistics.median(latencies)
    p95_ms = sorted(latencies)[int(len(latencies) * 0.95)]
    p99_ms = sorted(latencies)[int(len(latencies) * 0.99)]
    fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0

    print(f"\n  Latency (mean)      : {mean_ms:.2f} ms")
    print(f"  Latency (p50)       : {p50_ms:.2f} ms")
    print(f"  Latency (p95)       : {p95_ms:.2f} ms")
    print(f"  Latency (p99)       : {p99_ms:.2f} ms")
    print(f"  Throughput          : {fps:.1f} FPS")
    if mem_peak >= 0:
        print(f"  Memory (peak)       : {mem_peak:.1f} MB")

    print("=" * 55)

    # Check against targets
    target_fps = 30.0
    target_p95_ms = 50.0
    fps_ok = fps >= target_fps
    p95_ok = p95_ms <= target_p95_ms

    print(f"\n  Target FPS >= {target_fps}    : {'PASS' if fps_ok else 'FAIL'} ({fps:.1f})")
    print(f"  Target p95 <= {target_p95_ms} ms : {'PASS' if p95_ok else 'FAIL'} ({p95_ms:.2f} ms)")
    print()

    return 0 if (fps_ok and p95_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
