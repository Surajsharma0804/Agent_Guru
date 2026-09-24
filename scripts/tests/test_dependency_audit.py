"""Tests for scripts/dependency_audit.py.

The script's whole job is to never report "clean" when it did not check.
Most of these tests pin down one of the ways the old `pip-audit || true`
step silently passed: a skipped package, a dropped package, an unknown
severity, or a stale acceptance.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dependency_audit as da  # noqa: E402

TODAY = dt.date(2026, 9, 24)


def _osv(tmp_path: Path, records: dict[str, dict]) -> da.SeverityLookup:
    d = tmp_path / "osv"
    d.mkdir()
    for vid, rec in records.items():
        (d / f"{vid}.json").write_text(json.dumps({"id": vid, **rec}), encoding="utf-8")
    return da.SeverityLookup(osv_dir=d)


def _finding(pkg="gitpython", adv="GHSA-aaaa-bbbb-cccc", sev="HIGH", aliases=()):
    return da.Finding("requirements-lock.txt", pkg, "1.0", adv, tuple(aliases), sev, "s", ("2.0",))


def _acc(pkg="gitpython", adv="GHSA-aaaa-bbbb-cccc", review_by=dt.date(2027, 1, 1)):
    return da.Acceptance(adv, pkg, "not reachable because reasons", dt.date(2026, 9, 1), review_by)


# --- local versions --------------------------------------------------------


def test_local_build_is_audited_under_its_public_release():
    text, notes = da.strip_local_versions("torch==2.11.0+cu128\nnumpy==2.4.6\n")
    assert text == "torch==2.11.0\nnumpy==2.4.6\n"
    assert notes == ["torch==2.11.0+cu128 audited as torch==2.11.0"]


def test_markers_and_comments_survive_the_rewrite():
    text, _ = da.strip_local_versions("torch==2.11.0+cpu ; sys_platform == 'linux'  # note\n")
    assert text == "torch==2.11.0 ; sys_platform == 'linux'  # note\n"


# --- audit_file refuses to pass what it did not check ----------------------


def _reqs(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "requirements-lock.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_a_skipped_package_fails_the_audit(tmp_path):
    p = _reqs(tmp_path, "torch==2.11.0\n")
    report = {"dependencies": [{"name": "torch", "skip_reason": "Dependency not found on PyPI"}]}
    with pytest.raises(da.AuditError, match="could not audit 1"):
        da.audit_file(p, _osv(tmp_path, {}), runner=lambda _: report)


def test_fewer_packages_than_pins_fails_the_audit(tmp_path):
    p = _reqs(tmp_path, "# header\n--index-url https://x\na==1\nb==2\n")
    report = {"dependencies": [{"name": "a", "version": "1", "vulns": []}]}
    with pytest.raises(da.AuditError, match="reported 1 packages but the file pins 2"):
        da.audit_file(p, _osv(tmp_path, {}), runner=lambda _: report)


def test_the_runner_sees_the_rewritten_file(tmp_path):
    p = _reqs(tmp_path, "torch==2.11.0+cu128\n")
    seen = {}

    def runner(path):
        seen["text"] = path.read_text(encoding="utf-8")
        return {"dependencies": [{"name": "torch", "version": "2.11.0", "vulns": []}]}

    _, notes = da.audit_file(p, _osv(tmp_path, {}), runner=runner)
    assert seen["text"] == "torch==2.11.0\n"
    assert notes


def test_one_advisory_under_two_ids_is_one_finding(tmp_path):
    p = _reqs(tmp_path, "nltk==3.10.0\n")
    vulns = [
        {"id": "PYSEC-2026-1", "aliases": ["GHSA-aaaa-bbbb-cccc"], "fix_versions": ["3.10.3"]},
        {"id": "GHSA-aaaa-bbbb-cccc", "aliases": ["PYSEC-2026-1"], "fix_versions": ["3.10.3"]},
    ]
    report = {"dependencies": [{"name": "nltk", "version": "3.10.0", "vulns": vulns}]}
    lookup = _osv(tmp_path, {"GHSA-aaaa-bbbb-cccc": {"database_specific": {"severity": "CRITICAL"}, "summary": "x"}})
    findings, _ = da.audit_file(p, lookup, runner=lambda _: report)
    assert [(f.advisory, f.severity) for f in findings] == [("GHSA-aaaa-bbbb-cccc", "CRITICAL")]


# --- severity lookup -------------------------------------------------------


def test_pysec_only_id_is_resolved_through_its_osv_aliases(tmp_path):
    lookup = _osv(
        tmp_path,
        {
            "PYSEC-2026-9": {"aliases": ["GHSA-zzzz-yyyy-xxxx"]},
            "GHSA-zzzz-yyyy-xxxx": {"database_specific": {"severity": "HIGH"}},
        },
    )
    assert lookup.resolve(["PYSEC-2026-9"])[:2] == ("HIGH", "GHSA-zzzz-yyyy-xxxx")


def test_no_severity_anywhere_is_unknown_not_low(tmp_path):
    assert _osv(tmp_path, {}).resolve(["PYSEC-2026-3716"])[0] == "UNKNOWN"


# --- classification --------------------------------------------------------


def test_new_high_blocks():
    blocking, *_ = da.classify([_finding()], [], TODAY)
    assert [w for _, w in blocking] == ["new"]


def test_unknown_severity_blocks():
    blocking, *_ = da.classify([_finding(sev="UNKNOWN")], [], TODAY)
    assert [w for _, w in blocking] == ["severity unknown"]


def test_moderate_and_low_never_block():
    blocking, accepted, info, *_ = da.classify([_finding(sev="MODERATE"), _finding(sev="LOW")], [], TODAY)
    assert not blocking and not accepted and len(info) == 2


def test_accepted_high_does_not_block():
    blocking, accepted, *_ = da.classify([_finding()], [_acc()], TODAY)
    assert not blocking and len(accepted) == 1


def test_acceptance_matches_by_alias():
    f = _finding(adv="GHSA-new-id", aliases=("GHSA-aaaa-bbbb-cccc",))
    blocking, accepted, *_ = da.classify([f], [_acc()], TODAY)
    assert not blocking and len(accepted) == 1


def test_acceptance_for_another_package_does_not_match():
    blocking, *_ = da.classify([_finding(pkg="aiohttp")], [_acc(pkg="gitpython")], TODAY)
    assert len(blocking) == 1


def test_expired_acceptance_blocks_again():
    blocking, accepted, *_ = da.classify([_finding()], [_acc(review_by=dt.date(2026, 9, 23))], TODAY)
    assert not accepted
    assert blocking[0][1] == "acceptance expired 2026-09-23"


def test_unused_acceptance_is_reported_stale():
    *_, stale, _ = da.classify([], [_acc()], TODAY)
    assert len(stale) == 1


def test_acceptance_due_within_30_days_is_flagged():
    *_, expiring = da.classify([_finding()], [_acc(review_by=TODAY + dt.timedelta(days=10))], TODAY)
    assert len(expiring) == 1


# --- acceptance file -------------------------------------------------------


def _accepted_file(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "accepted.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_acceptance_file_requires_a_reason(tmp_path):
    p = _accepted_file(
        tmp_path,
        '[[accepted]]\nadvisory = "GHSA-a"\npackage = "x"\naccepted_on = 2026-09-24\nreview_by = 2026-12-31\n',
    )
    with pytest.raises(da.AuditError, match="missing reason"):
        da.load_acceptances(p)


def test_acceptance_file_rejects_a_token_reason(tmp_path):
    p = _accepted_file(
        tmp_path,
        '[[accepted]]\nadvisory = "GHSA-a"\npackage = "x"\nreason = "no fix"\n'
        "accepted_on = 2026-09-24\nreview_by = 2026-12-31\n",
    )
    with pytest.raises(da.AuditError, match="must say why"):
        da.load_acceptances(p)


def test_acceptance_file_rejects_accept_forever(tmp_path):
    p = _accepted_file(
        tmp_path,
        '[[accepted]]\nadvisory = "GHSA-a"\npackage = "x"\nreason = "not reachable, see triage doc"\n'
        "accepted_on = 2026-09-24\nreview_by = 2030-01-01\n",
    )
    with pytest.raises(da.AuditError, match="at most 365 days"):
        da.load_acceptances(p)


def test_the_repository_acceptance_file_is_valid():
    repo = Path(__file__).resolve().parents[2]
    entries = da.load_acceptances(repo / ".github" / "dependency-audit-accepted.toml")
    assert entries, "the committed acceptance file should parse and be non-empty"


# --- end to end ------------------------------------------------------------


def test_an_incomplete_audit_exits_2_and_says_so(tmp_path, monkeypatch):
    bad = _accepted_file(tmp_path, "[[accepted]]\nadvisory = 1\n")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    reqs = _reqs(tmp_path, "a==1\n")
    rc = da.main([str(reqs), "--accepted", str(bad), "--report-dir", str(tmp_path / "out")])
    assert rc == 2
    assert "DID NOT COMPLETE" in summary.read_text(encoding="utf-8")
