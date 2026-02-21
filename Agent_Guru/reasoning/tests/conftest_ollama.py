"""
Conftest for Ollama tests to avoid torch import issues.
"""
import sys

# Prevent Agent_Guru.__init__ from loading all modules
if "Agent_Guru" in sys.modules:
    del sys.modules["Agent_Guru"]
