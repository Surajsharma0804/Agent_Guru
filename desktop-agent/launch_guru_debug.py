#!/usr/bin/env python3
"""
Debug wrapper for GURU launch - forces output flushing
"""

import sys
import os

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("DEBUG: Starting launch_guru.py", flush=True)

# Import and run the actual launcher
from pathlib import Path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("DEBUG: Path setup complete", flush=True)

# Now execute the main launch script content
exec(open("launch_guru.py").read())
