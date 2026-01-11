#!/usr/bin/env python3
"""Detailed debug script to test patterns.py step by step."""

import sys
import os

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

try:
    print("Testing individual imports from patterns.py...")
    
    # Test basic imports first
    print("1. Testing basic imports...")
    import threading
    import uuid
    from datetime import datetime, timedelta
    from enum import Enum
    from typing import Dict, List, Optional, Set
    from collections import defaultdict, deque
    print("   Basic imports successful")
    
    # Test BiometricFactor import
    print("2. Testing BiometricFactor import...")
    try:
        from src.authority.state import BiometricFactor
        print("   BiometricFactor import successful")
    except Exception as e:
        print(f"   BiometricFactor import failed: {e}")
        # Let's create a mock for testing
        from enum import Enum
        class BiometricFactor(Enum):
            FACE = "face"
            FINGERPRINT = "fingerprint"
            VOICE = "voice"
        print("   Using mock BiometricFactor")
    
    # Test structlog import
    print("3. Testing structlog import...")
    try:
        import structlog
        print("   structlog import successful")
    except Exception as e:
        print(f"   structlog import failed: {e}")
        # Create mock logger
        class MockLogger:
            def get_logger(self, name):
                class Logger:
                    def info(self, *args, **kwargs): pass
                    def warning(self, *args, **kwargs): pass
                    def error(self, *args, **kwargs): pass
                    def critical(self, *args, **kwargs): pass
                return Logger()
        structlog = MockLogger()
        print("   Using mock structlog")
    
    logger = structlog.get_logger(__name__)
    
    # Now test the classes from patterns.py
    print("4. Testing class definitions...")
    
    # Test FailurePatternType
    class FailurePatternType(Enum):
        TEMPORAL_CLUSTERING = "temporal_clustering"
        RAPID_SUCCESSION = "rapid_succession"
        UNUSUAL_TIMING = "unusual_timing"
        FACTOR_SWITCHING = "factor_switching"
        CONFIDENCE_DEGRADATION = "confidence_degradation"
        BEHAVIORAL_ANOMALY = "behavioral_anomaly"
        STATISTICAL_OUTLIER = "statistical_outlier"
        PERSISTENCE_PATTERN = "persistence_pattern"
    print("   FailurePatternType defined")
    
    # Test PatternSeverity
    class PatternSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    print("   PatternSeverity defined")
    
    # Test PatternAnalysisConfig
    class PatternAnalysisConfig:
        def __init__(self,
                     clustering_window_minutes: int = 5,
                     rapid_succession_threshold_seconds: int = 10,
                     unusual_timing_threshold_seconds: float = 2.0,
                     confidence_degradation_threshold: float = 0.3,
                     statistical_outlier_threshold: float = 2.0,
                     minimum_samples_for_statistics: int = 5,
                     factor_switching_threshold: int = 3,
                     persistence_pattern_threshold: int = 5,
                     behavioral_window_minutes: int = 15,
                     enable_temporal_analysis: bool = True,
                     enable_statistical_analysis: bool = True,
                     enable_behavioral_analysis: bool = True,
                     pattern_retention_hours: int = 24,
                     max_patterns_stored: int = 1000):
            self.clustering_window_minutes = clustering_window_minutes
            self.rapid_succession_threshold_seconds = rapid_succession_threshold_seconds
            self.unusual_timing_threshold_seconds = unusual_timing_threshold_seconds
            self.confidence_degradation_threshold = confidence_degradation_threshold
            self.statistical_outlier_threshold = statistical_outlier_threshold
            self.minimum_samples_for_statistics = minimum_samples_for_statistics
            self.factor_switching_threshold = factor_switching_threshold
            self.persistence_pattern_threshold = persistence_pattern_threshold
            self.behavioral_window_minutes = behavioral_window_minutes
            self.enable_temporal_analysis = enable_temporal_analysis
            self.enable_statistical_analysis = enable_statistical_analysis
            self.enable_behavioral_analysis = enable_behavioral_analysis
            self.pattern_retention_hours = pattern_retention_hours
            self.max_patterns_stored = max_patterns_stored
    
    print("   PatternAnalysisConfig defined")
    
    # Test instantiation
    config = PatternAnalysisConfig()
    print(f"   Config created with attributes: {list(config.__dict__.keys())}")
    print(f"   clustering_window_minutes: {config.clustering_window_minutes}")
    print(f"   rapid_succession_threshold_seconds: {config.rapid_succession_threshold_seconds}")
    
    print("All tests passed! The issue is likely in the actual patterns.py file execution.")

except Exception as e:
    print(f"Error during testing: {e}")
    import traceback
    traceback.print_exc()