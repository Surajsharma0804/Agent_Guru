"""
Full codebase static audit — zero project imports, pure AST + text.
ASCII-only output for Windows PowerShell compatibility.
"""
import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "Agent_Guru")
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}

P_UTCNOW      = re.compile(r"\bdatetime\.utcnow\(\)")
P_BARE_EXCEPT = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
P_PRINT       = re.compile(r"^\s*print\(")
P_FLOG        = re.compile(r'(logger|log)\.(debug|info|warning|error|critical)\(f["\']')
P_GET_LOOP    = re.compile(r"\bget_event_loop\(\)")
P_TODO        = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")

def is_test_or_cli(rel):
    skip = ["tests/", "test_", "/scripts/", "/examples/",
            "/benchmarks/", "/training/", "validation/", "docs/"]
    return any(s in rel for s in skip)

issues = defaultdict(list)
syntax_errors = []
total_files = 0
prod_files = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        fpath = os.path.join(dirpath, fn)
        rel = os.path.relpath(fpath, ROOT).replace("\\", "/")
        total_files += 1
        prod = not is_test_or_cli(rel)
        if prod:
            prod_files += 1

        try:
            src = open(fpath, encoding="utf-8", errors="replace").read()
        except Exception as e:
            issues["read_error"].append((rel, 0, str(e)))
            continue

        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            syntax_errors.append((rel, e.lineno, str(e.msg)))
            continue

        lines = src.splitlines()

        def find_line(pattern):
            return [(i+1, lines[i].strip()[:80]) for i, l in
                    enumerate(lines) if pattern.search(l)]

        if prod:
            for lineno, text in find_line(P_UTCNOW):
                issues["utcnow_remaining"].append((rel, lineno, text))
            for lineno, text in find_line(P_BARE_EXCEPT):
                issues["bare_except"].append((rel, lineno, text))
            for lineno, text in find_line(P_PRINT):
                if "#" not in lines[lineno-1].split("print")[0]:
                    issues["prod_print"].append((rel, lineno, text))
            for lineno, text in find_line(P_FLOG):
                issues["flog_fstring"].append((rel, lineno, text))
            for lineno, text in find_line(P_GET_LOOP):
                issues["get_event_loop"].append((rel, lineno, text))
            for lineno, text in find_line(P_TODO):
                issues["todo_fixme"].append((rel, lineno, text))

        # AST: mutable default args
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues["mutable_default"].append(
                            (rel, node.lineno, "def %s() mutable default" % node.name))

PRIORITY = [
    ("syntax_errors",    "[CRIT] SYNTAX ERRORS"),
    ("get_event_loop",   "[CRIT] asyncio.get_event_loop() deprecated"),
    ("bare_except",      "[HIGH] bare except: (swallows all errors)"),
    ("mutable_default",  "[HIGH] mutable default arguments"),
    ("prod_print",       "[MED]  print() in production code"),
    ("flog_fstring",     "[MED]  f-string in logger calls (perf)"),
    ("utcnow_remaining", "[MED]  datetime.utcnow() remaining"),
    ("todo_fixme",       "[LOW]  TODO/FIXME comments"),
]

out = []
out.append("Scanned %d files (%d production)" % (total_files, prod_files))
out.append("=" * 64)

for key, label in PRIORITY:
    items = list(dict.fromkeys(  # deduplicate by (file,line)
        (r, l, t) for (r, l, t) in (issues.get(key, []) + syntax_errors if key == "syntax_errors" else issues.get(key, []))
    ))
    if not items:
        out.append("%s: OK (none found)" % label)
        continue
    out.append("\n%s: %d instances" % (label, len(items)))
    for (rel, lineno, text) in items[:20]:
        out.append("  %s:%d  %s" % (rel, lineno, text[:65]))
    if len(items) > 20:
        out.append("  ... and %d more" % (len(items) - 20))

if syntax_errors:
    out.append("\n[CRIT] SYNTAX ERRORS FOUND:")
    for rel, lineno, msg in syntax_errors:
        out.append("  %s:%d: %s" % (rel, lineno, msg))

out.append("\n" + "=" * 64)
findings = sum(1 for k,_ in PRIORITY if issues.get(k) or (k=="syntax_errors" and syntax_errors))
out.append("Issue categories with findings: %d / %d" % (findings, len(PRIORITY)))

result = "\n".join(out)
sys.stdout.buffer.write(result.encode("utf-8") + b"\n")
