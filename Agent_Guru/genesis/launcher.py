"""The installer's entry point: start the local server and show the GENESIS window.

The window is the OS web view (WebView2 on Windows, through pywebview) when it
is available, and the default browser otherwise. A machine without the
WebView2 runtime, or a build without pywebview, still gets a working window
instead of an error; the probe reports which one was used.

    AgentGuru.exe                         the window: setup, or the running assistant once installed
    AgentGuru.exe --background            start the assistant with no window (what runs at sign-in)
    AgentGuru.exe --stop                  ask the running assistant to shut down
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

from Agent_Guru.genesis import assistant
from Agent_Guru.genesis.app import GenesisApp
from Agent_Guru.genesis.layout import Layout, default_layout
from Agent_Guru.genesis.server import GenesisServer


def _webview_available() -> bool:
    try:
        import webview  # noqa: F401  pywebview, bundled with the frozen launcher when present
    except ImportError:
        return False
    from Agent_Guru.genesis.probes import Seams, probe_webview2

    return sys.platform != "win32" or bool(probe_webview2(Seams()).value)


#: How long the window waits for an assistant that has just been started.
WINDOW_WAIT_S = 180.0


def _show(url: str, browser: bool) -> None:
    """Open *url* and return when the window closes. Closing it ends only the window."""
    if not browser and _webview_available():
        import webview

        webview.create_window("Agent Guru", url, width=1240, height=860, background_color="#07090D")
        try:
            webview.start()
        except Exception as exc:  # noqa: BLE001 - no GTK or Qt bindings in a frozen Linux build: use the browser
            print(f"no web view ({type(exc).__name__}); using the default browser", flush=True)
        else:
            return
    webbrowser.open(url)


def _running_window(app: GenesisApp, layout: Layout, wait_s: float = WINDOW_WAIT_S) -> str:
    """The address of the assistant's window, starting the assistant if it is not running; "" if it never came."""
    app.start_assistant()
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        url = assistant.window_url(layout)
        if url:
            return url
        time.sleep(0.25)
    return ""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["genesis"]:
        from Agent_Guru.genesis.cli import run

        return run(argv[1:])
    p = argparse.ArgumentParser(prog="AgentGuru")
    p.add_argument("--root", type=Path)
    p.add_argument("--replay", type=Path, help="show a recorded journal; nothing is installed")
    p.add_argument("--browser", action="store_true", help="use the default browser instead of the web view")
    p.add_argument("--background", action="store_true", help="start the assistant with no window")
    p.add_argument("--stop", action="store_true", help="ask the running assistant to shut down")
    p.add_argument("--setup", action="store_true", help="open setup, even on a finished install")
    args = p.parse_args(argv)
    try:
        layout = default_layout(args.root)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.stop:
        return 0 if assistant.request_quit(layout) or not assistant.window_url(layout) else 1
    started = time.perf_counter()
    app = GenesisApp(layout, replay_journal=args.replay)
    if args.replay is None and not args.setup and app.installed():
        if args.background:
            app.start_assistant()
            return 0
        url = _running_window(app, layout)
        if url:
            _show(url, args.browser)
            return 0
        # It did not come up: setup is where Repair and the log are.
    elif args.background:
        return 0  # Setup was never finished, and nobody is there to see a window at sign-in.
    server = GenesisServer(app.routes(), replay=args.replay is not None)
    app.close = server.stop
    url = server.start()
    print(f"server ready in {time.perf_counter() - started:.2f} s", flush=True)
    if not args.browser and _webview_available():
        import webview

        window = webview.create_window("Agent Guru", url, width=1240, height=860, background_color="#07090D")
        window.events.closed += server.stop
        try:
            webview.start()
        except Exception as exc:  # noqa: BLE001 - no GTK or Qt bindings in a frozen Linux build: use the browser
            print(f"no web view ({type(exc).__name__}); using the default browser", flush=True)
        else:
            server.stop()
            return 0
    webbrowser.open(url)
    server.stopped.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
