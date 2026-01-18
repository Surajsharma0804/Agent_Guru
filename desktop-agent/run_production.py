#!/usr/bin/env python3
"""
GURU Production System Launcher

Production entry point for the GURU Personal Assistant system.
Handles proper module loading and system initialization.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path for proper imports
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

# Now import and run the production system
from main_production import run_production_system

if __name__ == "__main__":
    run_production_system()