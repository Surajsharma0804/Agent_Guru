#!/usr/bin/env python3
"""Minimal test to isolate the issue."""

from enum import Enum
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

# Test basic enum
class FailurePatternType(Enum):
    TEMPORAL_CLUSTERING = "temporal_clustering"
    RAPID_SUCCESSION = "rapid_succession"

print("FailurePatternType defined:", FailurePatternType)

# Test dataclass with frozenset
@dataclass(frozen=True)
class TestPattern:
    pattern_id: str
    affected_factors: frozenset

print("TestPattern defined:", TestPattern)

# Test class with frozenset type hint
class TestAnalyzer:
    def __init__(self):
        self.test_set: frozenset[str] = frozenset()
        print("TestAnalyzer initialized")

print("TestAnalyzer defined:", TestAnalyzer)

# Test instantiation
analyzer = TestAnalyzer()
print("All tests passed!")