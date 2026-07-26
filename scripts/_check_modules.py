"""Quick check for actual module names and ctranslate2 issue."""
import os

print("=== Actual module names ===")
for d in ["Agent_Guru/policy", "Agent_Guru/agents"]:
    if os.path.isdir(d):
        files = [f for f in os.listdir(d) if f.endswith(".py") and f != "__init__.py"]
        print(f"  {d}/: {files}")
    else:
        print(f"  {d}/: DOES NOT EXIST")

print()
print("=== ctranslate2 check ===")
try:
    import ctranslate2
    print(f"  Version: {ctranslate2.__version__}")
    has_sv = hasattr(ctranslate2, "StorageView")
    print(f"  Has StorageView: {has_sv}")
except Exception as e:
    print(f"  Error: {e}")
