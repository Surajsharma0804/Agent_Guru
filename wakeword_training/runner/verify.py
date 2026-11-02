r"""Check the portable data folder against its manifest before any compute starts.

    python verify.py [--data <folder>] [--quick]

Every file in manifest.json must exist with the recorded size and SHA-256 (--quick checks
sizes only). Files in the folder but not in the manifest are listed as a warning. Exit
status 0 means complete and uncorrupted; anything else prints exactly what is wrong.
Needs only the Python standard library, so it runs before the environment is installed.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import sys
import time
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--quick", action="store_true", help="sizes only, no hashing")
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    data = Path(a.data)
    mf = data / "manifest.json"
    if not mf.exists():
        print(f"FAIL: no manifest.json in {data}")
        return 2
    m = json.loads(mf.read_text(encoding="utf-8"))
    t0 = time.time()
    missing, wrong_size, present = [], [], []
    for rel, e in m["files"].items():
        p = data / rel
        if not p.exists():
            missing.append(rel)
        elif p.stat().st_size != e["bytes"]:
            wrong_size.append(f"{rel}: {p.stat().st_size} bytes, manifest says {e['bytes']}")
        else:
            present.append(rel)
    corrupt = []
    if not a.quick:
        with cf.ThreadPoolExecutor(a.threads) as ex:
            for rel, d in zip(present, ex.map(lambda r: sha256(data / r), present)):
                if d != m["files"][rel]["sha256"]:
                    corrupt.append(rel)
    listed = set(m["files"])
    extra = [p.relative_to(data).as_posix() for p in data.rglob("*")
             if p.is_file() and p.name != "manifest.json" and p.relative_to(data).as_posix() not in listed
             and "__pycache__" not in p.parts]
    gib = m["total_bytes"] / 2**30
    print(f"manifest from {m['created']}: {len(m['files'])} files, {gib:.2f} GiB; checked in {time.time() - t0:.0f} s"
          f"{' (sizes only)' if a.quick else ''}")
    for label, items in (("MISSING", missing), ("WRONG SIZE", wrong_size), ("CORRUPT (sha256 differs)", corrupt)):
        for x in items:
            print(f"  {label}: {x}")
    for x in extra[:20]:
        print(f"  warning, not in manifest: {x}")
    if missing or wrong_size or corrupt:
        print(f"FAIL: {len(missing)} missing, {len(wrong_size)} wrong size, {len(corrupt)} corrupt. "
              f"Re-copy those files from the source folder, then run verify again.")
        return 1
    print("OK: the data folder is complete" + ("" if a.quick else " and every file matches its checksum"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
