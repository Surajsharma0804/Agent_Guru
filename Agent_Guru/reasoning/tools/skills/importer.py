"""Import a skill from a git repository, a zip archive URL or a folder, after looking at it.

SkillInstaller installed only from a local folder the owner had already
put somewhere, and nothing looked inside before it did: a skill is code
that will run with the assistant, so taking one from the internet needs
a look first. import_skill() works in a quarantine folder:

1. Fetch without running anything: `git clone --depth 1` with hooks off
   and no submodules, or a zip download (at most 20 MB, no path that
   escapes the folder), or a copy of a local folder.
2. Find manifest.json and validate it as the installer does.
3. Scan every file: code that runs commands, evaluates strings, loads
   native libraries, deserialises pickles, opens network connections or
   reads the environment is listed; secrets and sensitive file names are
   flagged; files over 2 MB and binaries are listed.
4. If the manifest is signed (signature.sig beside it), verify it with
   deployment/crypto_verifier.py; a bad signature stops the import.
5. Show the report. Nothing is installed unless the owner passes --yes,
   and then through SkillInstaller, which asks for each permission.

    python -m Agent_Guru skills import <git URL | https://.../x.zip | folder> [--yes]
    python -m Agent_Guru skills discover    repeated tool sequences in past turns (trace_mining.py)
"""

from __future__ import annotations

import argparse
import asyncio
import io
import re
import shutil
import subprocess  # nosec B404 - git with a fixed argument list, no shell
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_MAX_ZIP = 20 * 1024 * 1024
_MAX_FILE = 2 * 1024 * 1024
_RISKY = (
    (re.compile(r"\bsubprocess\b|\bos\.system\b|\bos\.popen\b|\bchild_process\b|\bexecSync\b"), "runs commands"),
    (re.compile(r"(?<![\w.])(eval|exec)\s*\(|\bnew Function\(|\b__import__\("), "evaluates strings as code"),
    (re.compile(r"\bctypes\b|\bcffi\b|\bffi\.|\bLoadLibrary\b"), "loads native code"),
    (re.compile(r"\bpickle\.loads?\b|\bmarshal\.loads?\b|\byaml\.load\((?![^)]*SafeLoader)"), "deserialises untrusted data"),
    (re.compile(r"\brequests\.|\bhttpx\.|\burllib\.request\b|\bsocket\.|\bfetch\(|\baxios\b"), "uses the network"),
    (re.compile(r"\bos\.environ\b|\bprocess\.env\b|\bgetenv\("), "reads environment variables"),
    (re.compile(r"\bshutil\.rmtree\b|\bos\.remove\b|\bunlink\(|\brm -rf\b"), "deletes files"),
)
_SECRET = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]")
_CODE = {".py", ".js", ".mjs", ".ts", ".sh", ".ps1", ".bat", ".cmd"}


@dataclass(slots=True)
class ImportReport:
    source: str
    folder: Path | None = None
    skill_id: str = ""
    name: str = ""
    version: str = ""
    errors: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    signature: str = "unsigned"

    @property
    def blocked(self) -> bool:
        return bool(self.errors)


def _fetch(source: str, into: Path) -> Path:
    """Fetch *source* into *into* without running any of it; the folder holding the skill."""
    target = into / "skill"
    if re.match(r"^(https?|git)://|^git@", source) and (source.endswith(".git") or "github.com" in source or "gitlab" in source) \
            and not source.endswith(".zip"):
        git = shutil.which("git")
        if git is None:
            msg = "git is not installed"
            raise ValueError(msg)
        subprocess.run(  # noqa: S603  # nosec B603 - fixed arguments, the URL is one argument
            [git, "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never", "clone", "--depth", "1",
             "--no-recurse-submodules", "--", source, str(target)],
            check=True, capture_output=True, timeout=120,
        )
        shutil.rmtree(target / ".git", ignore_errors=True)
        return target
    if source.startswith("https://") and source.endswith(".zip"):
        import httpx

        with httpx.stream("GET", source, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > _MAX_ZIP:
                    msg = f"the archive is over {_MAX_ZIP // 2**20} MB"
                    raise ValueError(msg)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                path = (target / member.filename).resolve()
                if not path.is_relative_to(target.resolve()):
                    msg = f"the archive tries to write outside its folder: {member.filename}"
                    raise ValueError(msg)
            archive.extractall(target)  # nosec B202 - every member checked above
        return target
    folder = Path(source).expanduser()
    if folder.is_dir():
        shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        return target
    msg = f"{source} is not a git URL, an https .zip URL or a folder"
    raise ValueError(msg)


def _skill_root(folder: Path) -> Path | None:
    found = sorted(folder.rglob("manifest.json"), key=lambda p: len(p.parts))
    return found[0].parent if found else None


def scan(root: Path) -> list[str]:
    """What the files under *root* do that the owner should know before running them."""
    from Agent_Guru.security.file_policy import sensitive_reason

    findings: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if sensitive_reason(path):
            findings.append(f"{rel}: a file named like {sensitive_reason(path)}")
        size = path.stat().st_size
        if size > _MAX_FILE:
            findings.append(f"{rel}: {size // 1024} KB, too large to read")
            continue
        data = path.read_bytes()
        if b"\x00" in data[:4096]:
            findings.append(f"{rel}: a binary file")
            continue
        text = data.decode("utf-8", errors="replace")
        if path.suffix.lower() in _CODE:
            for pattern, what in _RISKY:
                if pattern.search(text):
                    findings.append(f"{rel}: {what}")
        if _SECRET.search(text):
            findings.append(f"{rel}: holds what looks like a secret")
    return findings


def inspect(source: str, quarantine: Path) -> ImportReport:
    """Fetch and look at *source*; installs nothing."""
    from Agent_Guru.reasoning.tools.skills.manifest import SkillManifestParser, SkillManifestValidator

    report = ImportReport(source=source)
    try:
        fetched = _fetch(source, quarantine)
    except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        report.errors.append(f"could not fetch it: {exc}")
        return report
    except Exception as exc:  # httpx errors
        report.errors.append(f"could not fetch it: {type(exc).__name__}: {exc}")
        return report
    root = _skill_root(fetched)
    if root is None:
        report.errors.append("no manifest.json in it")
        return report
    report.folder = root
    try:
        import json

        manifest = SkillManifestParser.parse_dict(json.loads((root / "manifest.json").read_text(encoding="utf-8")))
    except Exception as exc:
        report.errors.append(f"manifest.json is not valid: {exc}")
        return report
    problems = SkillManifestValidator.validate(manifest)
    if problems:
        report.errors.extend(f"manifest: {p}" for p in problems)
    report.skill_id, report.name, report.version = manifest.skill_id, manifest.name, manifest.version
    report.findings = scan(root)
    report.signature = _check_signature(root)
    if report.signature == "INVALID":
        report.errors.append("signature.sig does not match manifest.json for any trusted key")
    return report


def _trusted_keys() -> list[bytes]:
    """Ed25519 public keys (32 raw bytes, base64 in .pub files) in the data folder's skill_keys/."""
    import base64

    from Agent_Guru.utils.path_utils import app_data_dir

    folder = app_data_dir("skill_keys")
    keys = []
    for path in folder.glob("*.pub"):
        try:
            raw = base64.b64decode(path.read_text(encoding="ascii").strip())
        except (ValueError, OSError):
            continue
        if len(raw) == 32:
            keys.append(raw)
    return keys


def _check_signature(root: Path) -> str:
    """'unsigned', 'valid' (a trusted key signed manifest.json), 'unknown key', or 'INVALID'."""
    import base64

    signature_file = root / "signature.sig"
    if not signature_file.exists():
        return "unsigned"
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    raw = signature_file.read_bytes().strip()
    try:
        signature = raw if len(raw) == 64 else base64.b64decode(raw)
    except ValueError:
        return "INVALID"
    manifest = (root / "manifest.json").read_bytes()
    keys = _trusted_keys()
    if not keys:
        return "unknown key"
    for key in keys:
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, manifest)
            return "valid"
        except InvalidSignature:
            continue
    return "INVALID"


async def import_skill(source: str, *, install: bool) -> ImportReport:
    """Inspect *source*, and install it through SkillInstaller when *install* and nothing blocks it."""
    quarantine = Path(tempfile.mkdtemp(prefix="agent_guru_skill_"))
    try:
        report = await asyncio.to_thread(inspect, source, quarantine)
        if install and not report.blocked and report.folder is not None:
            from Agent_Guru.reasoning.tools.skills.installer import get_skill_installer

            result = await get_skill_installer().install_skill(report.folder, user_id="owner")
            if not result.success:
                report.errors.append(f"install failed: {result.error}")
        return report
    finally:
        shutil.rmtree(quarantine, ignore_errors=True)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru skills", description="Skills.")
    sub = parser.add_subparsers(dest="action")
    imp = sub.add_parser("import", help="fetch, check and (with --yes) install a skill")
    imp.add_argument("source")
    imp.add_argument("--yes", action="store_true", help="install it if nothing blocks it")
    sub.add_parser("discover", help="repeated tool sequences in past turns")
    args = parser.parse_args(argv)
    if args.action == "discover":
        from Agent_Guru.reasoning.tools.skills.trace_mining import report

        print(report())  # noqa: T201  the command's output
        return 0
    if args.action != "import":
        parser.print_help()
        return 0
    result = asyncio.run(import_skill(args.source, install=args.yes))
    print(f"{result.name or '?'} {result.version} ({result.skill_id or 'no id'}), signature: {result.signature}")  # noqa: T201
    for f in result.findings:
        print(f"  note: {f}")  # noqa: T201
    for e in result.errors:
        print(f"  BLOCKED: {e}")  # noqa: T201
    if result.blocked:
        return 1
    print("Installed." if args.yes else "Not installed. Read the notes, then run again with --yes to install.")  # noqa: T201
    return 0
