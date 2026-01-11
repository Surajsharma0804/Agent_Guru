#!/usr/bin/env python3

import sys
import os

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

try:
    from src.intrusion.patterns import PatternAnalysisConfig
    
    # Test creating config with keyword arguments
    config = PatternAnalysisConfig(rapid_succession_threshold_seconds=10)
    print(f"SUCCESS: Config created with rapid_succession_threshold_seconds = {config.rapid_succession_threshold_seconds}")
    
    # Test all parameters
    config2 = PatternAnalysisConfig(
        clustering_window_minutes=5,
        rapid_succession_threshold_seconds=10,
        confidence_degradation_threshold=0.3,
        minimum_samples_for_statistics=3
    )
    print(f"SUCCESS: Full config created with all parameters")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()