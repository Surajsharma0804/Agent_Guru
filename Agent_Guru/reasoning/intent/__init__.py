"""Intent detection module for Agent Guru reasoning engine.

This module provides ultra-fast intent detection through multiple strategies:
- Fast Router: Pattern-based matching for 80% of commands (<50ms)
- Neural Classifier: Fine-tuned models for complex intents (<200ms)
- LLM Fallback: GPT-4/Claude for unknown patterns (<400ms)

Performance Targets:
- Fast Router: <50ms P95, >98% accuracy
- Neural: <200ms P95, >95% accuracy
- LLM: <400ms P95, >98% accuracy

Author: Agent Guru Team
Date: 2026-02-19
"""

from Agent_Guru.reasoning.intent.fast_router import (
    FastIntentRouter,
    MatchQuality,
    PatternMatch,
    TrieNode,
)

__all__ = [
    "FastIntentRouter",
    "MatchQuality",
    "PatternMatch",
    "TrieNode",
]
