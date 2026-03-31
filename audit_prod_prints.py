"""Audit script: find print() statements in production service modules only."""
import os
import re

ROOT = r"f:\MY PROJECTS\Agent_Guru\Agent_Guru"
SKIP_DIRS = {"tests", "__pycache__"}
# These sub-paths are intentionally CLI-facing (print() is fine there)
SKIP_SEGMENTS = {"scripts", "examples", "data", "training", "benchmark", "benchmarks"}

print_pat = re.compile(r"^\s*print\s*\(")
issues = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    rel_dir = dirpath.replace(ROOT, "").lower()
    parts = [p for p in rel_dir.replace("\\", "/").split("/") if p]
    if any(seg in parts for seg in SKIP_SEGMENTS):
        continue
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        fpath = os.path.join(dirpath, fn)
        try:
            lines = open(fpath, encoding="utf-8", errors="ignore").readlines()
            for i, line in enumerate(lines, 1):
                if print_pat.match(line):
                    rel = fpath.replace(ROOT, "")
                    issues.append((rel, i, line.strip()))
        except Exception:
            pass

print(f"Production print() hits: {len(issues)}")
for rel, lineno, content in issues:
    safe = content.encode('ascii', errors='replace').decode('ascii')
    print(f"  {rel}:{lineno}  {safe[:100]}")
