"""`agent-guru genesis`: plan, install, verify and report from a terminal, with no display needed.

The same engine and journal as the GENESIS window: the window is one way to
approve a plan, --yes is another.

    agent-guru genesis --root D:\\AG --plan          what would happen, nothing changed
    agent-guru genesis --root D:\\AG --plan --json   the same as JSON
    agent-guru genesis --root D:\\AG --yes           install what the plan says
    agent-guru genesis --root D:\\AG --resume --yes  continue after a stop or a crash
    agent-guru genesis --root D:\\AG --verify        check every installed component
    agent-guru genesis --root D:\\AG --report out.json   the redacted system report
    agent-guru genesis --root D:\\AG --offline E:\\ag-offline --yes   install from a folder
    agent-guru genesis --uninstall --yes            remove the app, keep your data (Linux, macOS)
    agent-guru genesis --uninstall --remove-data --yes   remove your data too

From an installed copy --root is not needed: the install folder is the
launcher's own. Exit codes:

    0  done (or, with --plan, the plan can be installed)
    1  at least one component failed; the journal and the summary say which
    2  the command line was wrong
    3  the plan cannot be installed here (disk, path length); nothing was changed
    4  the plan was not approved (no --yes and no terminal to ask in)
    5  another installer is running for this install folder
    6  cancelled
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import signal
import sys
from pathlib import Path
from typing import Any

from Agent_Guru.genesis import assistant, autostart
from Agent_Guru.genesis import executor as ex
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis import planner, probes, verify
from Agent_Guru.genesis.actions import ActionContext, current_platform
from Agent_Guru.genesis.layout import Layout, default_layout

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_CANNOT, EXIT_NOT_APPROVED, EXIT_BUSY, EXIT_CANCELLED = range(7)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-guru genesis", description="Install, check or report Agent Guru.")
    p.add_argument("--root", type=Path, help="the install folder (required from a source checkout)")
    p.add_argument("--plan", action="store_true", help="show the plan and change nothing")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    p.add_argument("--yes", action="store_true", help="approve the plan without asking")
    p.add_argument("--resume", action="store_true", help="continue an install that stopped")
    p.add_argument("--verify", action="store_true", help="run every installed component's check")
    p.add_argument("--report", nargs="?", const="-", metavar="FILE", help="write the redacted system report")
    p.add_argument("--offline", type=Path, metavar="FOLDER", help="install from pre-downloaded files in FOLDER")
    p.add_argument("--tiers", help="comma-separated optional tiers to turn on (voice,vision,research,browser,coding)")
    p.add_argument("--no-tiers", help="comma-separated optional tiers to turn off")
    p.add_argument("--model", help="the Ollama model to use instead of the plan's choice")
    p.add_argument("--uninstall", action="store_true", help="remove this install; your data stays unless --remove-data")
    p.add_argument("--remove-data", action="store_true", help="with --uninstall, also delete memory, settings and models")
    return p


def _choices(args: argparse.Namespace) -> planner.Choices:
    tiers = dict(planner.DEFAULT_TIERS)
    for name in filter(None, (args.tiers or "").split(",")):
        tiers[name.strip()] = True
    for name in filter(None, (args.no_tiers or "").split(",")):
        tiers[name.strip()] = False
    return planner.Choices(tiers=tiers, model=args.model or "", offline=args.offline is not None)


def _hosts(manifest: mf.Manifest) -> list[str]:
    return sorted({h for c in manifest.components for h in c.get("hosts", [])})


def redact(text: str) -> str:
    """Remove the user name and the home folder from a report; paths keep only what follows them."""
    home = str(Path.home())
    user = getpass.getuser()
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        text = text.replace(variant, "<home>")
    if user:
        text = re.sub(re.escape(user), "<user>", text, flags=re.IGNORECASE)
    return text


def _fmt_bytes(n: int | None) -> str:
    # Decimal megabytes, as the size audit and download pages count them;
    # dividing by 2**20 printed 84.6 "MB" for the core's 88.7 MB.
    return "unknown" if n is None else f"{n / 1e6:,.1f} MB"


def print_plan(plan: dict[str, Any], out: Any = None) -> None:
    # sys.stdout is looked up at call time: a default bound at import time
    # kept writing to the original stream after a caller redirected it.
    w = (out or sys.stdout).write
    t = plan["totals"]
    w(f"Plan for {plan['platform']}{' (offline)' if plan['offline'] else ''}\n")
    m = plan["model"]
    if m.get("name"):
        w(f"  Model: {m['name']} ({'already installed' if m['reused'] else 'to download'}), {m['note']}. Why: {m['why']}.\n")
    else:
        w(f"  Model: none. {m.get('error', '')}\n")
    w("  Tiers: " + ", ".join(f"{k} {'on' if v else 'off'}" for k, v in plan["tiers"].items()) + "\n")
    for r in plan["components"]:
        size = f" {_fmt_bytes(r['download_bytes'])} download" if r["action"] == "install" and r["download_bytes"] else ""
        w(f"  [{r['action']:7}] {r['title']}{size} - {r['reason']}\n")
    w(f"  Download {_fmt_bytes(t['download_bytes'])}; keep on disk {_fmt_bytes(t['disk_bytes'])}; "
      f"needed with a {int(t['margin'] * 100)} % margin {_fmt_bytes(t['needed_with_margin_bytes'])}; "
      f"free {_fmt_bytes(t['free_bytes'])}\n")
    if plan["unverified_sizes"]:
        w("  Sizes not measured yet (UNVERIFIED): " + ", ".join(plan["unverified_sizes"]) + "\n")
    for o in plan["outside_install"]:
        w(f"  Outside the install folder: {o['change']}\n")
    for u in plan["unavailable"]:
        w(f"  Unavailable: {u['feature']} - {u['why']}\n")
    if plan["irreversible"]:
        w("  Not reversible: " + ", ".join(plan["irreversible"]) + "\n")
    if plan["path_problem"]:
        w(f"  Cannot install here: {plan['path_problem']}\n")
    if t["fits"] is False:
        w("  Cannot install here: not enough free disk space\n")
    w("  Nothing is added to startup, PATH or the firewall.\n")


def pinned_files(layout: Layout, manifest: mf.Manifest) -> list[tuple[str, Path, list[tuple[str, int]]]]:
    """(component, folder, [(name, size)]) for every component that downloads pinned files."""
    from Agent_Guru.genesis.actions import resolve_dest

    return [(c["id"], resolve_dest(c["dest"], layout), [(f["name"], f["size"]) for f in c["files"]])
            for c in manifest.components if c.get("dest") and c.get("files")]


def make_plan(layout: Layout, args: argparse.Namespace, manifest: mf.Manifest) -> tuple[dict[str, Any], probes.Machine]:
    machine = probes.scan(layout, _hosts(manifest), network=args.offline is None,
                          pinned=pinned_files(layout, manifest))
    return planner.plan(machine, manifest, _choices(args)), machine


def installed_python(layout: Layout) -> str:
    """The Python the install was built from, as its python-runtime event recorded it.

    Without it, --verify checked the private runtime's path on a machine
    whose install reused its own Python, and reported a working install as
    FAILED (found on the first real install, 2026-11-04).
    """
    for e in reversed(jr.read(layout.journal_path)[0]):
        if e.component_id == "python-runtime" and e.kind in ("verified", "reused") and e.data.get("python"):
            return str(e.data["python"])
    return ""


def _verify_all(layout: Layout, manifest: mf.Manifest, model: str) -> dict[str, verify.Result]:
    events, _ = jr.read(layout.journal_path)
    installed = jr.installed_components(events)
    python = installed_python(layout)
    results: dict[str, verify.Result] = {}
    for c in manifest.components:
        if c["id"] not in installed:
            continue
        ctx = ActionContext(layout=layout, emit=lambda k, d: None, model=model, python=python)
        results[c["id"]] = verify.run(c["probe"], ctx, c)
    return results


def _installed_model(layout: Layout) -> str:
    for e in reversed(jr.read(layout.journal_path)[0]):
        if e.component_id == "llm-model" and e.kind in ("verified", "reused") and e.data.get("model"):
            return str(e.data["model"])
    return ""


def report(layout: Layout, manifest: mf.Manifest, machine: probes.Machine | None = None) -> dict[str, Any]:
    events, bad = jr.read(layout.journal_path)
    views = jr.project(events)
    data = {
        "machine": machine.to_dict() if machine else None,
        "components": {cid: {"state": v.state, "error": v.error, "detail": v.detail} for cid, v in views.items()},
        "installed": sorted(jr.installed_components(events)),
        "journal": {"events": len(events), "unreadable_lines": bad, "runs": len({e.run_id for e in events})},
    }
    return json.loads(redact(json.dumps(data, default=str)))


def uninstall(layout: Layout, *, remove_data: bool) -> str:
    """Remove the install folder. On Windows Inno Setup's uninstaller does this.

    Only a folder that holds this installer's runtime is removed, so a mistyped
    --root cannot delete someone's folder. The user's data is a separate
    folder and stays unless asked for by name.
    """
    root = layout.install_root
    if not layout.runtime_root.is_dir():
        msg = f"{root} is not an Agent Guru install: it has no runtime folder"
        raise ValueError(msg)
    # A running assistant holds these files, and a sign-in entry left behind
    # would point at nothing on every start.
    assistant.request_quit(layout)
    autostart.remove(current_platform())
    try:
        os.kill(int(layout.ollama_pid_file.read_text(encoding="utf-8")), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    shutil.rmtree(root)
    if remove_data and layout.data_dir.is_dir():
        shutil.rmtree(layout.data_dir)
        return f"removed {root} and your data in {layout.data_dir}"
    return f"removed {root}; your data is still in {layout.data_dir}"


def run(argv: list[str]) -> int:
    try:
        args = parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    try:
        layout = default_layout(args.root)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return EXIT_USAGE
    if args.uninstall:
        if not args.yes:
            print("Not approved: add --yes to remove this install.", file=sys.stderr)
            return EXIT_NOT_APPROVED
        try:
            print(uninstall(layout, remove_data=args.remove_data))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return EXIT_CANNOT
        return EXIT_OK
    manifest = mf.load()
    if args.report is not None:
        machine = probes.scan(layout, [], network=False)
        text = json.dumps(report(layout, manifest, machine), indent=1, ensure_ascii=False)
        if args.report == "-":
            print(text)
        else:
            Path(args.report).write_text(text, encoding="utf-8")
        return EXIT_OK
    if args.verify:
        results = _verify_all(layout, manifest, args.model or _installed_model(layout))
        if args.json:
            print(json.dumps({k: {"result": r.label, "detail": r.detail, "needs_person": r.needs_person}
                              for k, r in results.items()}, indent=1))
        else:
            for cid, r in results.items():
                extra = f" (UNVERIFIED until you confirm: {r.needs_person})" if r.needs_person else ""
                print(f"  {r.label:14} {cid}: {r.detail}{extra}")
            if not results:
                print("  nothing is installed here yet")
        return EXIT_FAILED if any(r.label == "FAILED" for r in results.values()) else EXIT_OK
    plan, _machine = make_plan(layout, args, manifest)
    cannot = bool(plan["path_problem"]) or plan["totals"]["fits"] is False
    if args.plan:
        if args.json:
            print(json.dumps(plan, indent=1, ensure_ascii=False, default=str))
        else:
            print_plan(plan)
        return EXIT_CANNOT if cannot else EXIT_OK
    if cannot:
        print_plan(plan, sys.stderr)
        return EXIT_CANNOT
    if not args.yes:
        if not sys.stdin.isatty():
            print("Not approved: run with --plan to see the plan, then --yes to install it.", file=sys.stderr)
            return EXIT_NOT_APPROVED
        print_plan(plan)
        if input("Install this? [y/N] ").strip().lower() not in ("y", "yes"):
            return EXIT_NOT_APPROVED
    context: dict[str, Any] = {"offline_dir": args.offline}
    if os.environ.get("OLLAMA_HOST"):
        context["ollama_host"] = probes.ollama_host(probes.Seams())[0]
    engine = ex.Executor(layout, manifest, plan, context=context)
    try:
        summary = engine.run()
    except ex.AlreadyRunning as exc:
        print(exc, file=sys.stderr)
        return EXIT_BUSY
    except KeyboardInterrupt:
        return EXIT_CANCELLED
    if args.json:
        print(json.dumps(summary.to_dict(), indent=1))
    else:
        if summary.zero_actions:
            print("Nothing to do: every component was already installed and passed its check.")
        for cid in summary.verified:
            print(f"  installed   {cid}")
        for cid in summary.reused:
            print(f"  reused      {cid}")
        for cid, why in summary.failed.items():
            print(f"  FAILED      {cid}: {why}")
        for cid, why in summary.skipped.items():
            print(f"  skipped     {cid}: {why}")
        if summary.refused:
            print(f"  refused: {summary.refused}")
    if summary.refused:
        return EXIT_CANNOT
    if summary.cancelled:
        return EXIT_CANCELLED
    return EXIT_FAILED if summary.failed else EXIT_OK
