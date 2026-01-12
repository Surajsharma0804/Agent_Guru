#!/usr/bin/env python3

import sys
sys.path.append('.')

# Test minimal class definition
try:
    print("Testing minimal class definition...")
    
    from enum import Enum
    from dataclasses import dataclass
    from datetime import datetime
    from typing import Dict, Any
    
    class FailureType(Enum):
        HEALTH_CHECK_TIMEOUT = "health_check_timeout"
        COMPONENT_UNRESPONSIVE = "component_unresponsive"
    
    class FailureSeverity(Enum):
        LOW = "low"
        HIGH = "high"
    
    @dataclass(frozen=True)
    class ComponentFailure:
        component_name: str
        failure_type: FailureType
        severity: FailureSeverity
        timestamp: datetime
        error_message: str
        context: Dict[str, Any] = None
    
    class FailureDetector:
        def __init__(self):
            self.name = "test"
    
    print("Minimal classes defined successfully")
    print(f"FailureType: {FailureType}")
    print(f"ComponentFailure: {ComponentFailure}")
    print(f"FailureDetector: {FailureDetector}")
    
    # Test instantiation
    detector = FailureDetector()
    print(f"Detector created: {detector}")
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()