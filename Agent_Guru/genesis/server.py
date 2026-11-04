"""The local server behind the GENESIS window: loopback only, one secret per launch.

The window is a web page served by this process and shown in the OS web view
(or the default browser). Anything else on the machine can reach a loopback
port too, so every rule here is about other programs and other web pages:

- It binds 127.0.0.1 on a port the OS picks, never 0.0.0.0.
- Each launch makes a new secret. The window gets it in the URL fragment,
  which browsers never send to a server or put in a Referer, and sends it
  back in the X-Genesis-Token header on every /api call. A web page on
  another origin cannot add that header without a CORS preflight, and this
  server answers no preflight and sends no Access-Control-Allow-Origin.
- The Host header must be this server's own 127.0.0.1:port or
  localhost:port, so a DNS-rebinding page whose name now points at
  127.0.0.1 is refused. An Origin header, when sent, must be exactly the
  server's own origin.
- Bodies are JSON, at most MAX_BODY bytes, with a Content-Length.
- No endpoint takes a command, a URL or a file path. Static files come only
  from the ui folder, resolved and checked to stay inside it.
- The server stops when the window says it is closing, or when the window's
  heartbeat has been silent for HEARTBEAT_TIMEOUT seconds (a browser tab
  that was closed without a word).

The handlers only read the journal and call the same planner and executor
the command line uses.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from Agent_Guru.genesis import journal as jr

UI_DIR = Path(__file__).resolve().parent / "ui"
MAX_BODY = 64 * 1024
HEARTBEAT_TIMEOUT = 60.0
_STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".json": "application/json",
                 ".ttf": "font/ttf", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png",
                 ".txt": "text/plain; charset=utf-8"}
# What a page may do. default-src 'self' blocks every remote script, style,
# font and image even if a file were edited to load one; connect-src 'self'
# keeps fetch() on this server.
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


class Refused(Exception):
    def __init__(self, status: HTTPStatus, why: str) -> None:
        super().__init__(why)
        self.status = status
        self.why = why


Route = Callable[[dict[str, Any]], tuple[int, Any]]


class GenesisServer:
    """Owns the HTTP server, its secret and its routes. start() returns the URL the window opens."""

    def __init__(self, routes: dict[tuple[str, str], Route], *, ui_dir: Path = UI_DIR,
                 clock: Callable[[], float] = time.monotonic, replay: bool = False, outlives_window: bool = False) -> None:
        self.routes = routes
        self.ui_dir = ui_dir.resolve()
        self.token = secrets.token_urlsafe(32)
        self.clock = clock
        self.replay = replay
        #: Setup ends with its window. The assistant does not: it listens with
        #: no window open, and this server is how a window reaches it again.
        self.outlives_window = outlives_window
        self.last_beat = clock()
        self.stopped = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None
        self.port = 0

    # --- checks, each one a reason a request is refused -----------------

    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def check_host_and_origin(self, headers: Any) -> None:
        host = headers.get("Host", "")
        if host not in self.allowed_hosts():
            raise Refused(HTTPStatus.MISDIRECTED_REQUEST, f"host {host!r} is not this server")
        origins = headers.get_all("Origin") or []
        if len(origins) > 1:
            raise Refused(HTTPStatus.FORBIDDEN, "more than one Origin header")
        if origins and origins[0] not in (self.origin(), f"http://localhost:{self.port}"):
            raise Refused(HTTPStatus.FORBIDDEN, f"origin {origins[0]!r} may not call this server")

    def check_token(self, headers: Any) -> None:
        sent = headers.get("X-Genesis-Token", "")
        if not hmac.compare_digest(sent.encode(), self.token.encode()):
            raise Refused(HTTPStatus.UNAUTHORIZED, "missing or wrong token")

    def static_path(self, url_path: str) -> Path:
        rel = "index.html" if url_path in ("/", "") else url_path.lstrip("/")
        if rel.startswith("ui/"):
            rel = rel[3:]
        if "\\" in rel or "\x00" in rel or any(part in ("..", "") for part in rel.split("/")):
            raise Refused(HTTPStatus.NOT_FOUND, "not a file of the window")
        path = (self.ui_dir / rel).resolve()
        if self.ui_dir not in path.parents or not path.is_file() or path.suffix not in _STATIC_TYPES:
            raise Refused(HTTPStatus.NOT_FOUND, "not a file of the window")
        return path

    def beat(self) -> None:
        self.last_beat = self.clock()

    def heartbeat_lapsed(self) -> bool:
        return self.clock() - self.last_beat > HEARTBEAT_TIMEOUT

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> str:
        outer = self

        class Handler(_Handler):
            server_ref = outer

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, name="genesis-http", daemon=True).start()
        threading.Thread(target=self._watch, name="genesis-heartbeat", daemon=True).start()
        return f"{self.origin()}/#t={self.token}"

    def _watch(self) -> None:
        while not self.stopped.wait(2.0):
            if self.heartbeat_lapsed() and not self.outlives_window:
                self.stop()

    def stop(self) -> None:
        if self.stopped.is_set():
            return
        self.stopped.set()
        if self._httpd is not None:
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()


class _Handler(BaseHTTPRequestHandler):
    server_ref: GenesisServer
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: Any) -> None:  # the journal is the record; request lines would only add noise
        return

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", _CSP)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Any) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"), "application/json")

    def _refuse(self, refused: Refused) -> None:
        self._json(refused.status, {"error": refused.why})

    def _body(self) -> dict[str, Any]:
        length = self.headers.get("Content-Length")
        if length is None:
            raise Refused(HTTPStatus.LENGTH_REQUIRED, "a body needs a Content-Length")
        try:
            size = int(length)
        except ValueError as exc:
            raise Refused(HTTPStatus.BAD_REQUEST, "Content-Length is not a number") from exc
        if size > MAX_BODY or size < 0:
            raise Refused(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, f"bodies are limited to {MAX_BODY} bytes")
        if "json" not in self.headers.get("Content-Type", ""):
            raise Refused(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "the body must be JSON")
        raw = self.rfile.read(size)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError) as exc:
            raise Refused(HTTPStatus.BAD_REQUEST, "the body is not valid JSON") from exc
        if not isinstance(data, dict):
            raise Refused(HTTPStatus.BAD_REQUEST, "the body must be a JSON object")
        return data

    def _api(self, method: str) -> None:
        srv = self.server_ref
        srv.check_token(self.headers)
        route = srv.routes.get((method, urlsplit(self.path).path))
        if route is None:
            raise Refused(HTTPStatus.NOT_FOUND, "no such endpoint")
        body = self._body() if method == "POST" else {}
        if method == "GET":
            query = urlsplit(self.path).query
            body = {k: v for k, _, v in (p.partition("=") for p in query.split("&") if p)}
        srv.beat()
        status, data = route(body)
        if srv.replay and isinstance(data, dict):
            data = {**data, "replay": True, "replay_label": jr.REPLAY_LABEL}
        self._json(status, data)

    def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
        srv = self.server_ref
        try:
            srv.check_host_and_origin(self.headers)
            if urlsplit(self.path).path.startswith("/api/"):
                self._api("GET")
                return
            path = srv.static_path(urlsplit(self.path).path)
            self._send(HTTPStatus.OK, path.read_bytes(), _STATIC_TYPES.get(path.suffix) or
                       mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        except Refused as refused:
            self._refuse(refused)

    def do_POST(self) -> None:  # noqa: N802
        srv = self.server_ref
        try:
            srv.check_host_and_origin(self.headers)
            if not urlsplit(self.path).path.startswith("/api/"):
                raise Refused(HTTPStatus.METHOD_NOT_ALLOWED, "only /api accepts POST")
            self._api("POST")
        except Refused as refused:
            self._refuse(refused)

    def do_OPTIONS(self) -> None:  # noqa: N802
        # A cross-origin preflight. Answering it with any Allow-* header would
        # open the API to that origin; refusing it keeps the browser from
        # sending the real request at all.
        self._json(HTTPStatus.FORBIDDEN, {"error": "cross-origin requests are not accepted"})

    def do_PUT(self) -> None:  # noqa: N802
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "not allowed"})

    do_DELETE = do_PATCH = do_PUT  # noqa: N815
