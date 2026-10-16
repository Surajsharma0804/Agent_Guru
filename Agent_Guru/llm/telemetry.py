"""Inter-token latency of a streamed answer: how evenly the words arrive.

The answer stage recorded time to first text and an average decode speed,
and neither shows a stall: 40 tokens/s on average can hide a 900 ms gap
in the middle of a sentence, which is what the owner hears as the voice
stopping. The gaps between streamed chunks (Ollama sends about one token
per chunk) are kept as percentiles in the turn record, so a turn with a
stall can be found and compared.
"""

from __future__ import annotations

import math


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(0, min(len(sorted_values) - 1, math.ceil(fraction * len(sorted_values)) - 1))
    return sorted_values[rank]


def inter_token_stats(arrivals: list[float]) -> dict[str, float]:
    """Gaps between consecutive chunk *arrivals* (perf_counter seconds) as itl_* milliseconds; {} for fewer than 3."""
    if len(arrivals) < 3:
        return {}
    gaps = sorted((b - a) * 1000.0 for a, b in zip(arrivals, arrivals[1:]))
    return {
        "itl_p50_ms": round(_percentile(gaps, 0.50), 1),
        "itl_p95_ms": round(_percentile(gaps, 0.95), 1),
        "itl_max_ms": round(gaps[-1], 1),
        "itl_chunks": float(len(arrivals)),
    }
