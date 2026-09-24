#!/usr/bin/env python3
"""Audit the pinned dependency files and report what a person has to act on.

Why this exists. CI used to run ``pip-audit ... || true`` and upload the
JSON as an artifact that nobody opened. The ``|| true`` also hid that the
audit had never worked properly: it resolved the whole lock file through
pip, and it skipped torch, torchvision and torchaudio as "not found on PyPI"
because the lock pins ``+cu128`` builds. Meanwhile 145 Dependabot alerts
built up unread (docs/security/dependency-triage-2026-09.md).

What it does instead:

* Audits every file passed in, pin by pin (``--no-deps``), so the result is
  about exactly the versions written down, with no resolver in between.
* Audits a ``+local`` build (``2.11.0+cu128``) under its public release,
  which has the same source and the same advisories, and says so in the
  report. The audit fails if pip-audit still skips a package, or if it
  returns fewer packages than the file pins. A package that was never
  audited is never counted as clean.
* Looks up each advisory's GitHub severity in OSV. If the lookup fails,
  the severity is UNKNOWN, and UNKNOWN blocks the same as HIGH. A network
  failure must not turn into a green check.
* Blocks only on CRITICAL, HIGH or UNKNOWN findings that nobody has
  accepted. Moderate and low are listed, but never fail the build. Failing
  on everything is how the old job ended up ignored.
* An acceptance lives in .github/dependency-audit-accepted.toml, with a
  written reason and a review-by date at most a year out. An expired
  acceptance blocks again, so decisions get re-made rather than forgotten.
  An acceptance that matches nothing is reported, so it can be deleted.

Exit status: 0 when nothing needs a decision, 1 when a critical or high
finding does, 2 when the audit itself could not be completed. CI fails on
both 1 and 2.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BLOCKING_SEVERITIES = ("CRITICAL", "HIGH", "UNKNOWN")
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "UNKNOWN": 2, "MODERATE": 3, "LOW": 4}
MAX_ACCEPTANCE_DAYS = 365
EXPIRY_WARNING_DAYS = 30
OSV_URL = "https://api.osv.dev/v1/vulns/{}"

# `name==1.2.3+local` -> group 1 is `name==1.2.3`, group 2 is `+local`.
_LOCAL_PIN = re.compile(
    r"^(\s*[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]*\])?\s*==\s*[^\s;#+]+)(\+[A-Za-z0-9.]+)"
)


class AuditError(Exception):
    """The audit could not produce a trustworthy result."""


@dataclass(frozen=True)
class Finding:
    file: str
    package: str
    version: str
    advisory: str  # GHSA id when one exists, so it matches Dependabot
    aliases: tuple[str, ...]
    severity: str
    summary: str
    fixed_in: tuple[str, ...]


@dataclass(frozen=True)
class Acceptance:
    advisory: str
    package: str
    reason: str
    accepted_on: dt.date
    review_by: dt.date


@dataclass
class Result:
    audited: list[str]
    rewritten: list[str]
    blocking: list[tuple[Finding, str]]
    accepted: list[tuple[Finding, Acceptance]]
    informational: list[Finding]
    stale: list[Acceptance]
    expiring: list[Acceptance]


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------------------
# Requirement files
# ---------------------------------------------------------------------------


def pinned_lines(text: str) -> list[str]:
    """Requirement lines that pip-audit will report on (not comments or options)."""
    out = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if line and not line.startswith(("#", "-")):
            out.append(line)
    return out


def strip_local_versions(text: str) -> tuple[str, list[str]]:
    """Rewrite `pkg==X+local` to `pkg==X` so the public release is audited.

    Returns the rewritten text and a note for each line changed. PyPI has no
    `+cu128` builds, so without this pip-audit skips the package entirely.
    """
    notes, lines = [], []
    for line in text.splitlines(keepends=True):
        m = _LOCAL_PIN.match(line)
        if m:
            notes.append(f"{m.group(1).strip()}{m.group(2)} audited as {m.group(1).strip()}")
            line = m.group(1) + line[m.end() :]
        lines.append(line)
    return "".join(lines), notes


def run_pip_audit(requirements: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "audit.json"
        cmd = [
            sys.executable, "-m", "pip_audit",
            "-r", str(requirements),
            "--no-deps", "--disable-pip",
            "--format", "json", "--output", str(out),
            "--progress-spinner", "off",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
        # pip-audit exits 1 both for "vulnerabilities found" and for errors,
        # so the exit code cannot tell them apart. Trust only a parseable
        # report.
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
            raise AuditError(
                f"pip-audit produced no report for {requirements} (exit {proc.returncode}):\n{tail}"
            ) from exc


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class SeverityLookup:
    """GitHub severity for an advisory, from OSV (online, or a local export)."""

    def __init__(self, osv_dir: Path | None = None, timeout: float = 20.0) -> None:
        self.osv_dir = osv_dir
        self.timeout = timeout
        self._cache: dict[str, dict | None] = {}
        self.failures: list[str] = []

    def _record(self, vuln_id: str) -> dict | None:
        if vuln_id in self._cache:
            return self._cache[vuln_id]
        rec: dict | None = None
        if self.osv_dir is not None:
            path = self.osv_dir / f"{vuln_id}.json"
            if path.exists():
                rec = json.loads(path.read_text(encoding="utf-8"))
        else:
            try:
                with urllib.request.urlopen(OSV_URL.format(vuln_id), timeout=self.timeout) as r:  # noqa: S310
                    rec = json.load(r)
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    self.failures.append(f"{vuln_id}: HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                self.failures.append(f"{vuln_id}: {exc}")
        self._cache[vuln_id] = rec
        return rec

    def resolve(self, ids: list[str]) -> tuple[str, str, str]:
        """Return (severity, GHSA id or best id, summary) for one advisory."""
        ghsa = [i for i in ids if i.startswith("GHSA-")]
        if not ghsa:
            # A PYSEC record often names its GHSA only in its own aliases.
            for i in ids:
                rec = self._record(i)
                if rec:
                    ghsa = [a for a in rec.get("aliases", []) if a.startswith("GHSA-")]
                    if ghsa:
                        break
        for g in ghsa:
            rec = self._record(g)
            sev = ((rec or {}).get("database_specific") or {}).get("severity")
            if sev:
                return sev.upper(), g, (rec or {}).get("summary", "")
        return "UNKNOWN", (ghsa or ids)[0], ""


# ---------------------------------------------------------------------------
# Acceptances
# ---------------------------------------------------------------------------


def load_acceptances(path: Path) -> list[Acceptance]:
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise AuditError(f"{path}: {exc}") from exc
    out, problems = [], []
    for n, entry in enumerate(data.get("accepted", []), 1):
        where = f"{path} entry {n}"
        missing = [k for k in ("advisory", "package", "reason", "accepted_on", "review_by") if k not in entry]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        acc, rev = entry["accepted_on"], entry["review_by"]
        if not isinstance(acc, dt.date) or not isinstance(rev, dt.date):
            problems.append(f"{where}: accepted_on and review_by must be TOML dates (2026-09-24)")
            continue
        if len(str(entry["reason"]).strip()) < 20:
            problems.append(f"{where}: the reason must say why the risk is acceptable")
        if not dt.timedelta(0) < rev - acc <= dt.timedelta(days=MAX_ACCEPTANCE_DAYS):
            problems.append(f"{where}: review_by must be after accepted_on and at most {MAX_ACCEPTANCE_DAYS} days later")
        out.append(Acceptance(entry["advisory"], canonical(entry["package"]), str(entry["reason"]).strip(), acc, rev))
    if problems:
        raise AuditError("Invalid acceptance file:\n" + "\n".join(problems))
    return out


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def audit_file(
    path: Path,
    lookup: SeverityLookup,
    runner: Callable[[Path], dict] = run_pip_audit,
) -> tuple[list[Finding], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    rewritten, notes = strip_local_versions(text)
    expected = len(pinned_lines(rewritten))
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / path.name
        target.write_text(rewritten, encoding="utf-8")
        report = runner(target)

    deps = report.get("dependencies", [])
    skipped = [f"{d['name']}: {d['skip_reason']}" for d in deps if d.get("skip_reason")]
    if skipped:
        raise AuditError(f"{path}: pip-audit could not audit {len(skipped)} package(s):\n" + "\n".join(skipped))
    if len(deps) < expected:
        raise AuditError(f"{path}: pip-audit reported {len(deps)} packages but the file pins {expected}")

    findings: dict[tuple[str, str], Finding] = {}
    for d in deps:
        for v in d.get("vulns", []):
            ids = [v["id"], *v.get("aliases", [])]
            sev, advisory, summary = lookup.resolve(ids)
            key = (canonical(d["name"]), advisory)
            if key in findings:
                continue  # the same advisory under a PYSEC and a GHSA id
            findings[key] = Finding(
                file=path.name,
                package=canonical(d["name"]),
                version=d.get("version", ""),
                advisory=advisory,
                aliases=tuple(sorted(set(ids) - {advisory})),
                severity=sev,
                summary=summary or v.get("description", "").split("\n", 1)[0][:160],
                fixed_in=tuple(v.get("fix_versions", [])),
            )
    return list(findings.values()), notes


def classify(findings: list[Finding], acceptances: list[Acceptance], today: dt.date) -> tuple[
    list[tuple[Finding, str]], list[tuple[Finding, Acceptance]], list[Finding], list[Acceptance], list[Acceptance]
]:
    blocking, accepted, informational = [], [], []
    used: set[int] = set()
    for f in findings:
        if f.severity not in BLOCKING_SEVERITIES:
            informational.append(f)
            continue
        match = next(
            (
                (i, a)
                for i, a in enumerate(acceptances)
                if a.package == f.package and (a.advisory == f.advisory or a.advisory in f.aliases)
            ),
            None,
        )
        if match is None:
            why = "severity unknown" if f.severity == "UNKNOWN" else "new"
            blocking.append((f, why))
            continue
        i, a = match
        used.add(i)
        if today > a.review_by:
            blocking.append((f, f"acceptance expired {a.review_by}"))
        else:
            accepted.append((f, a))
    stale = [a for i, a in enumerate(acceptances) if i not in used]
    expiring = [
        a for i, a in enumerate(acceptances)
        if i in used and today <= a.review_by <= today + dt.timedelta(days=EXPIRY_WARNING_DAYS)
    ]
    return blocking, accepted, informational, stale, expiring


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _link(advisory: str) -> str:
    if advisory.startswith("GHSA-"):
        return f"[{advisory}](https://github.com/advisories/{advisory})"
    return advisory


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ").strip()


def render(result: Result, accepted_file: str) -> str:
    n = len(result.blocking)
    if n:
        noun = "findings need" if n != 1 else "finding needs"
        head = f"## Dependency audit: {n} critical/high {noun} a decision"
    else:
        head = "## Dependency audit: no new critical or high findings"
    lines = [head, ""]
    lines.append("Audited " + ", ".join(result.audited) + ".")
    if result.rewritten:
        lines.append("Local builds audited under their public release: " + "; ".join(result.rewritten) + ".")
    lines.append("")
    if n:
        lines += [
            "### Needs a decision (this fails the build)",
            "",
            "For each one: upgrade to a fixed version if the project reaches the vulnerable code. If it"
            f" does not, add an entry to `{accepted_file}` saying why, with a review-by date.",
            "",
            "| Severity | Package | File | Advisory | Fixed in | Why blocking | Summary |",
            "|---|---|---|---|---|---|---|",
        ]
        for f, why in sorted(result.blocking, key=lambda x: (SEVERITY_RANK[x[0].severity], x[0].package)):
            lines.append(
                f"| {f.severity.title()} | {f.package} {f.version} | {f.file} | {_link(f.advisory)} | "
                f"{', '.join(f.fixed_in) or 'no fix'} | {why} | {_cell(f.summary)} |"
            )
        lines.append("")
    if result.expiring:
        lines.append("### Acceptances due for review within 30 days")
        lines.append("")
        for a in result.expiring:
            lines.append(f"- {a.package} {_link(a.advisory)}: review by {a.review_by}")
        lines.append("")
    if result.stale:
        lines.append(f"### Acceptances that no longer match anything (delete them from `{accepted_file}`)")
        lines.append("")
        for a in result.stale:
            lines.append(f"- {a.package} {_link(a.advisory)}")
        lines.append("")
    if result.accepted:
        lines += [
            f"<details><summary>{len(result.accepted)} accepted critical/high (not blocking)</summary>",
            "",
            "| Severity | Package | Advisory | Review by | Reason |",
            "|---|---|---|---|---|",
        ]
        for f, a in sorted(result.accepted, key=lambda x: (SEVERITY_RANK[x[0].severity], x[0].package)):
            lines.append(
                f"| {f.severity.title()} | {f.package} {f.version} | {_link(f.advisory)} | {a.review_by} | {_cell(a.reason)} |"
            )
        lines += ["", "</details>", ""]
    if result.informational:
        per_pkg = Counter((f.package, f.version, f.severity) for f in result.informational)
        lines += [
            f"<details><summary>{len(result.informational)} moderate/low (never blocking)</summary>",
            "",
            "| Package | Severity | Count |",
            "|---|---|---|",
        ]
        for (pkg, ver, sev), c in sorted(per_pkg.items(), key=lambda x: (x[0][0], SEVERITY_RANK[x[0][2]])):
            lines.append(f"| {pkg} {ver} | {sev.title()} | {c} |")
        lines += ["", "</details>", ""]
    return "\n".join(lines)


def annotations(result: Result, accepted_file: str) -> list[str]:
    out = []
    for f, why in result.blocking:
        out.append(
            f"::error file={f.file},title={f.severity.title()} {f.package} {f.advisory}::"
            f"{f.package} {f.version}: {_cell(f.summary)} ({why}; fixed in {', '.join(f.fixed_in) or 'no release'})"
        )
    for a in result.expiring:
        out.append(f"::warning file={accepted_file},title=Acceptance due::{a.package} {a.advisory} must be reviewed by {a.review_by}")
    for a in result.stale:
        out.append(f"::warning file={accepted_file},title=Stale acceptance::{a.package} {a.advisory} no longer matches any finding")
    return out


def _append(env_var: str, text: str) -> None:
    target = os.environ.get(env_var)
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("files", nargs="+", type=Path, help="pinned requirement files to audit")
    ap.add_argument("--accepted", type=Path, default=Path(".github/dependency-audit-accepted.toml"))
    ap.add_argument("--report-dir", type=Path, default=Path("dependency-audit"))
    ap.add_argument("--osv-dir", type=Path, help="read OSV records from a local export instead of api.osv.dev")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args(argv)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    accepted_file = args.accepted.as_posix()

    try:
        acceptances = load_acceptances(args.accepted)
        lookup = SeverityLookup(args.osv_dir)
        findings, audited, rewritten = [], [], []
        for path in args.files:
            fs, notes = audit_file(path, lookup)
            findings += fs
            rewritten += notes
            audited.append(f"`{path.as_posix()}` ({len(pinned_lines(path.read_text(encoding='utf-8-sig')))} pins)")
        if lookup.failures:
            # Those advisories are already UNKNOWN, and so blocking; name the cause.
            print("::warning title=OSV lookup failed::" + "; ".join(lookup.failures[:10]))
    except AuditError as exc:
        msg = f"## Dependency audit: DID NOT COMPLETE\n\nNothing below this line was checked.\n\n```\n{exc}\n```\n"
        (args.report_dir / "report.md").write_text(msg, encoding="utf-8")
        _append("GITHUB_STEP_SUMMARY", msg)
        _append("GITHUB_OUTPUT", "blocking=error\n")
        print(f"::error title=Dependency audit did not complete::{_cell(str(exc))}")
        print(msg)
        return 2

    blocking, accepted, informational, stale, expiring = classify(findings, acceptances, args.today)
    result = Result(audited, rewritten, blocking, accepted, informational, stale, expiring)
    md = render(result, accepted_file)
    (args.report_dir / "report.md").write_text(md, encoding="utf-8")
    (args.report_dir / "report.json").write_text(
        json.dumps(
            {
                "blocking": [dict(f.__dict__, why=w) for f, w in blocking],
                "accepted": [dict(f.__dict__, review_by=str(a.review_by)) for f, a in accepted],
                "informational": [f.__dict__ for f in informational],
                "stale_acceptances": [a.advisory for a in stale],
            },
            indent=1,
            default=list,
        ),
        encoding="utf-8",
    )
    _append("GITHUB_STEP_SUMMARY", md)
    _append("GITHUB_OUTPUT", f"blocking={len(blocking)}\n")
    for line in annotations(result, accepted_file):
        print(line)
    print(md)
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
