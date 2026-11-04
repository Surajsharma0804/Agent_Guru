"""The GENESIS server refuses every request that does not come from its own window."""

from __future__ import annotations

import http.client
import json

import pytest

from Agent_Guru.genesis import server as sv


@pytest.fixture
def running(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<!doctype html><title>GENESIS</title>", encoding="utf-8")
    (ui / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the ui folder", encoding="utf-8")
    calls = []

    def echo(body):
        calls.append(body)
        return 200, {"got": body}

    srv = sv.GenesisServer({("GET", "/api/ping"): lambda b: (200, {"pong": True}), ("POST", "/api/echo"): echo},
                           ui_dir=ui)
    url = srv.start()
    srv.calls = calls  # type: ignore[attr-defined]
    srv.url = url  # type: ignore[attr-defined]
    yield srv
    srv.stop()


def request(srv, method, path, body=None, headers=None, raw_headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
    h = {"Host": f"127.0.0.1:{srv.port}", "X-Genesis-Token": srv.token}
    h.update(headers or {})
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    if data is not None:
        h.setdefault("Content-Type", "application/json")
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    for k, v in h.items():
        if v is not None:
            conn.putheader(k, v)
    for k, v in raw_headers or []:
        conn.putheader(k, v)
    if data is not None and "Content-Length" not in h:
        conn.putheader("Content-Length", str(len(data)))
    conn.endheaders(data)
    resp = conn.getresponse()
    out = resp.status, dict(resp.getheaders()), resp.read()
    conn.close()
    return out


def test_it_listens_on_loopback_only_on_a_port_the_os_picks(running, tmp_path):
    assert running._httpd.server_address[0] == "127.0.0.1" and running.port > 0  # nosec B101
    other = sv.GenesisServer({}, ui_dir=tmp_path / "ui")
    other.start()
    try:
        assert other.port != running.port and other.token != running.token  # nosec B101  a new secret per launch
    finally:
        other.stop()


def test_the_secret_travels_in_the_fragment_never_in_a_response(running):
    assert running.url == f"http://127.0.0.1:{running.port}/#t={running.token}"  # nosec B101
    status, _, page = request(running, "GET", "/", headers={"X-Genesis-Token": None})
    assert status == 200 and running.token.encode() not in page  # nosec B101


@pytest.mark.parametrize("token", [None, "", "wrong", "x" * 43])
def test_an_api_call_without_the_right_token_is_refused(running, token):
    status, _, body = request(running, "GET", "/api/ping", headers={"X-Genesis-Token": token})
    assert status == 401 and b"token" in body  # nosec B101
    assert request(running, "GET", "/api/ping")[0] == 200  # nosec B101


@pytest.mark.parametrize("host", ["evil.example:80", "127.0.0.1", "127.0.0.1:1", "0.0.0.0:{port}", "[::1]:{port}"])
def test_a_request_for_another_host_is_refused(running, host):
    status, _, _ = request(running, "GET", "/api/ping", headers={"Host": host.format(port=running.port)})
    assert status == 421  # nosec B101  a DNS-rebinding page sends its own name


def test_localhost_by_name_is_this_server(running):
    assert request(running, "GET", "/api/ping", headers={"Host": f"localhost:{running.port}"})[0] == 200  # nosec B101


@pytest.mark.parametrize("origin", ["http://evil.example", "null", "http://127.0.0.1:1", "https://127.0.0.1:{port}"])
def test_a_call_from_another_origin_is_refused(running, origin):
    status, headers, _ = request(running, "POST", "/api/echo", {"a": 1}, headers={"Origin": origin.format(port=running.port)})
    assert status == 403 and running.calls == []  # nosec B101
    assert "Access-Control-Allow-Origin" not in headers  # nosec B101


def test_a_second_origin_header_is_refused(running):
    status, _, _ = request(running, "POST", "/api/echo", {"a": 1},
                           raw_headers=[("Origin", f"http://127.0.0.1:{running.port}"), ("Origin", "http://evil.example")])
    assert status == 403 and running.calls == []  # nosec B101


def test_the_windows_own_origin_is_accepted(running):
    status, _, body = request(running, "POST", "/api/echo", {"a": 1}, headers={"Origin": f"http://127.0.0.1:{running.port}"})
    assert status == 200 and json.loads(body) == {"got": {"a": 1}}  # nosec B101


def test_a_cors_preflight_is_refused_without_any_allow_header(running):
    status, headers, _ = request(running, "OPTIONS", "/api/echo", headers={
        "Origin": "http://evil.example", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-genesis-token"})
    assert status == 403  # nosec B101
    assert not [k for k in headers if k.lower().startswith("access-control-")]  # nosec B101


def test_an_oversized_body_is_refused_before_it_is_read(running):
    big = json.dumps({"pad": "x" * (sv.MAX_BODY + 1)}).encode()
    status, _, _ = request(running, "POST", "/api/echo", big)
    assert status == 413 and running.calls == []  # nosec B101


def test_a_body_without_length_or_not_json_is_refused(running):
    assert request(running, "POST", "/api/echo", None)[0] == 411  # nosec B101
    assert request(running, "POST", "/api/echo", b"a=1", headers={"Content-Type": "application/x-www-form-urlencoded"})[0] == 415  # nosec B101
    assert request(running, "POST", "/api/echo", b"[1, 2]")[0] == 400  # nosec B101
    assert running.calls == []  # nosec B101


@pytest.mark.parametrize("path", ["/../secret.txt", "/ui/../secret.txt", "/%2e%2e/secret.txt", "/ui/..%5csecret.txt",
                                  "/..\\secret.txt", "/ui//etc/hosts", "/C:/Windows/win.ini", "/secret.txt"])
def test_no_file_outside_the_ui_folder_is_served(running, path):
    status, _, body = request(running, "GET", path, headers={"X-Genesis-Token": None})
    assert status == 404 and b"outside the ui folder" not in body  # nosec B101


def test_the_ui_files_are_served_with_a_strict_content_policy(running):
    status, headers, body = request(running, "GET", "/ui/app.js", headers={"X-Genesis-Token": None})
    assert status == 200 and body == b"console.log(1)"  # nosec B101
    assert "default-src 'self'" in headers["Content-Security-Policy"]  # nosec B101
    assert headers["X-Content-Type-Options"] == "nosniff" and "Access-Control-Allow-Origin" not in headers  # nosec B101


def test_unknown_endpoints_and_methods_are_refused(running):
    assert request(running, "GET", "/api/shell")[0] == 404  # nosec B101
    assert request(running, "PUT", "/api/echo", {"a": 1})[0] == 405  # nosec B101
    assert request(running, "POST", "/index.html", {"a": 1})[0] == 405  # nosec B101


def test_the_server_stops_when_the_window_closes(running):
    running.stop()
    assert running.stopped.wait(5)  # nosec B101
    with pytest.raises(OSError):
        for _ in range(50):
            request(running, "GET", "/api/ping")


def test_the_server_stops_when_the_heartbeat_goes_quiet(tmp_path):
    now = [1000.0]
    srv = sv.GenesisServer({}, ui_dir=tmp_path, clock=lambda: now[0])
    assert not srv.heartbeat_lapsed()  # nosec B101
    now[0] += sv.HEARTBEAT_TIMEOUT - 1
    assert not srv.heartbeat_lapsed()  # nosec B101
    srv.beat()
    now[0] += sv.HEARTBEAT_TIMEOUT + 1
    assert srv.heartbeat_lapsed()  # nosec B101


def test_a_replayed_journal_is_labelled_on_every_answer(tmp_path):
    srv = sv.GenesisServer({("GET", "/api/ping"): lambda b: (200, {"pong": True})}, ui_dir=tmp_path, replay=True)
    srv.start()
    try:
        status, _, body = request(srv, "GET", "/api/ping")
    finally:
        srv.stop()
    assert status == 200 and json.loads(body)["replay_label"] == "REPLAY - NOT A REAL RUN"  # nosec B101
