"""Final full codebase scan — every module import check."""
import os
import importlib

failures = {}
checked = 0
for root, dirs, files in os.walk("Agent_Guru"):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
    for f in files:
        if not f.endswith(".py") or f == "__init__.py":
            continue
        path = os.path.join(root, f)
        module_path = path.replace(os.sep, ".").replace(".py", "")
        checked += 1
        try:
            importlib.import_module(module_path)
        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e).splitlines()[0][:120]
            failures[module_path] = f"{err_type}: {err_msg}"

print(f"Checked: {checked} | Failed: {len(failures)} | PASSED: {checked - len(failures)}")
if failures:
    print()
    for mod, err in sorted(failures.items()):
        short = mod.replace("Agent_Guru.", "")
        print(f"  {short}: {err}")
else:
    print()
    print("=" * 50)
    print("ZERO FAILURES — ALL MODULES IMPORT SUCCESSFULLY")
    print("=" * 50)
