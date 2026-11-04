"""The installer's entry point: start the local server and show the GENESIS window.

The window is the OS web view (WebView2 on Windows, through pywebview) when it
is available, and the default browser otherwise. A machine without the
WebView2 runtime, or a build without pywebview, still gets a working window
instead of an error; the probe reports which one was used.

    AgentGuru.exe                         set up or repair this install
    AgentGuru.exe genesis --plan ...      the command line (cli.py), no window
    python -m Agent_Guru.genesis.launcher --root D:\\AG     from a checkout
    python -m Agent_Guru.genesis.launcher --root D:\\AG --replay run.jsonl
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

from Agent_Guru.genesis.app import GenesisApp
from Agent_Guru.genesis.layout import default_layout
from Agent_Guru.genesis.server import GenesisServer


def _webview_available() -> bool:
    try:
        import webview  # noqa: F401  pywebview, bundled with the frozen launcher when present
    except ImportError:
        return False
    from Agent_Guru.genesis.probes import Seams, probe_webview2

    return sys.platform != "win32" or bool(probe_webview2(Seams()).value)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["genesis"]:
        from Agent_Guru.genesis.cli import run

        return run(argv[1:])
    p = argparse.ArgumentParser(prog="AgentGuru")
    p.add_argument("--root", type=Path)
    p.add_argument("--replay", type=Path, help="show a recorded journal; nothing is installed")
    p.add_argument("--browser", action="store_true", help="use the default browser instead of the web view")
    args = p.parse_args(argv)
    try:
        layout = default_layout(args.root)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    started = time.perf_counter()
    app = GenesisApp(layout, replay_journal=args.replay)
    server = GenesisServer(app.routes(), replay=args.replay is not None)
    app.close = server.stop
    url = server.start()
    print(f"server ready in {time.perf_counter() - started:.2f} s", flush=True)
    if not args.browser and _webview_available():
        import webview

        window = webview.create_window("Agent Guru", url, width=1240, height=860, background_color="#07090D")
        window.events.closed += server.stop
        webview.start()
        server.stop()
        return 0
    webbrowser.open(url)
    server.stopped.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
