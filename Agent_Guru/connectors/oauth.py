"""OAuth 2.0 for the owner's accounts: sign in once in the browser, tokens kept encrypted.

Reading the owner's mail or calendar needs their consent on the
provider's own page; a password typed into the assistant would be both
weaker and against the providers' terms. This runs the installed-app
flow: authorization code with PKCE (S256) and a random state, the
browser sent to the provider, the redirect caught by a one-shot listener
on 127.0.0.1 that closes as soon as it has the code. Tokens are kept
with DPAPI (security/secret_store.py) and refreshed when they expire;
nothing is written in plain text and no password is ever seen.

Client ids come from the environment or .env (the owner registers their
own app with the provider):

    Google     GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
    Microsoft  MS_OAUTH_CLIENT_ID          (a public client; no secret)

    python -m Agent_Guru connect google        sign in
    python -m Agent_Guru connect status        who is connected
    python -m Agent_Guru connect remove google forget the tokens
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Any

_LOGIN_TIMEOUT_S = 300
_REFRESH_MARGIN_S = 120


@dataclass(frozen=True, slots=True)
class Provider:
    name: str
    auth_url: str
    token_url: str
    scopes: tuple[str, ...]
    client_id_env: str
    client_secret_env: str = ""
    #: Strava wants its scopes separated by commas; every other provider by spaces.
    scope_separator: str = " "

    def client_id(self) -> str:
        return os.environ.get(self.client_id_env, "").strip()

    def client_secret(self) -> str:
        return os.environ.get(self.client_secret_env, "").strip() if self.client_secret_env else ""


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        name="google",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",  # nosec B106 - a URL, not a password
        scopes=(
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/contacts.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/tasks",
        ),
        client_id_env="GOOGLE_OAUTH_CLIENT_ID", client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
    ),
    "microsoft": Provider(
        name="microsoft",
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",  # nosec B106 - a URL
        scopes=("offline_access", "Mail.Read", "Mail.Send", "Calendars.ReadWrite", "Contacts.Read"),
        client_id_env="MS_OAUTH_CLIENT_ID",
    ),
    "strava": Provider(
        name="strava",
        auth_url="https://www.strava.com/oauth/authorize",
        token_url="https://www.strava.com/oauth/token",  # nosec B106 - a URL
        scopes=("read", "activity:read_all"),
        client_id_env="STRAVA_CLIENT_ID", client_secret_env="STRAVA_CLIENT_SECRET", scope_separator=",",
    ),
    "spotify": Provider(
        name="spotify",
        auth_url="https://accounts.spotify.com/authorize",
        token_url="https://accounts.spotify.com/api/token",  # nosec B106 - a URL
        scopes=("user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing"),
        client_id_env="SPOTIFY_CLIENT_ID",
    ),
}


class OAuthError(RuntimeError):
    """Signing in or refreshing failed; the message says why, never a token."""


def _secret_name(provider: str) -> str:
    return f"oauth_tokens_{provider}"


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class _Catcher(http.server.BaseHTTPRequestHandler):
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 - the http.server name
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        if "code" in query or "error" in query:
            type(self).result.update(query)
            body = b"Signed in. You can close this tab and go back to Agent Guru."
        else:
            body = b"Waiting for the sign-in redirect."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: Any) -> None:
        return


def _post_token(provider: Provider, data: dict[str, str]) -> dict[str, Any]:
    import httpx

    if provider.client_secret():
        data = {**data, "client_secret": provider.client_secret()}
    try:
        response = httpx.post(provider.token_url, data={**data, "client_id": provider.client_id()}, timeout=20)
        body = response.json()
    except Exception as exc:
        msg = f"{provider.name}: the token request failed: {type(exc).__name__}"
        raise OAuthError(msg) from exc
    if "access_token" not in body:
        msg = f"{provider.name}: {body.get('error_description') or body.get('error') or 'no token in the answer'}"
        raise OAuthError(msg)
    return body


def _store(provider: str, body: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    from Agent_Guru.security import secret_store

    tokens = {
        "access_token": body["access_token"],
        # A refresh answer often leaves the refresh token out: keep the old one.
        "refresh_token": body.get("refresh_token") or (previous or {}).get("refresh_token", ""),
        "expires_at": time.time() + float(body.get("expires_in", 3600)),
        "scope": body.get("scope", (previous or {}).get("scope", "")),
    }
    secret_store.save_json(_secret_name(provider), tokens)
    return tokens


def sign_in(provider_name: str, *, open_browser: bool = True) -> dict[str, Any]:
    """Run the browser sign-in for *provider_name* and keep its tokens; OAuthError says what failed."""
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        msg = f"no provider called {provider_name}; known: {', '.join(PROVIDERS)}"
        raise OAuthError(msg)
    if not provider.client_id():
        msg = f"set {provider.client_id_env} in the environment or .env first (your own app's client id)"
        raise OAuthError(msg)
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    catcher = type("Catcher", (_Catcher,), {"result": {}})
    server = http.server.HTTPServer(("127.0.0.1", 0), catcher)
    redirect = f"http://127.0.0.1:{server.server_port}/"
    params = {
        "client_id": provider.client_id(), "response_type": "code", "redirect_uri": redirect,
        "scope": provider.scope_separator.join(provider.scopes), "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent",
    }
    url = f"{provider.auth_url}?{urllib.parse.urlencode(params)}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        print(f"Sign in to {provider.name} in the browser. If it does not open, visit:\n{url}")  # noqa: T201
        if open_browser:
            webbrowser.open(url)
        deadline = time.monotonic() + _LOGIN_TIMEOUT_S
        while not catcher.result and time.monotonic() < deadline:
            time.sleep(0.2)
    finally:
        server.shutdown()
        server.server_close()
    result = catcher.result
    if not result:
        msg = f"{provider.name}: no sign-in within {_LOGIN_TIMEOUT_S // 60} minutes"
        raise OAuthError(msg)
    if result.get("state") != state:
        msg = f"{provider.name}: the redirect's state did not match; nothing was kept"
        raise OAuthError(msg)
    if "error" in result:
        msg = f"{provider.name}: {result.get('error_description') or result['error']}"
        raise OAuthError(msg)
    body = _post_token(provider, {
        "grant_type": "authorization_code", "code": result["code"],
        "redirect_uri": redirect, "code_verifier": verifier,
    })
    return _store(provider.name, body)


def access_token(provider_name: str) -> str:
    """A valid access token for *provider_name*, refreshed if needed; OAuthError when not connected."""
    from Agent_Guru.security import secret_store

    provider = PROVIDERS[provider_name]
    tokens = secret_store.load_json(_secret_name(provider_name))
    if not tokens:
        msg = f"{provider_name} is not connected; run: python -m Agent_Guru connect {provider_name}"
        raise OAuthError(msg)
    if tokens.get("expires_at", 0) - _REFRESH_MARGIN_S > time.time():
        return tokens["access_token"]
    if not tokens.get("refresh_token"):
        msg = f"{provider_name} needs signing in again; run: python -m Agent_Guru connect {provider_name}"
        raise OAuthError(msg)
    try:
        body = _post_token(provider, {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
    except OAuthError as exc:
        # A revoked or expired grant only said "google: Token has been expired or revoked.", which the
        # assistant read out with no way forward; the fix is always to sign in again.
        msg = f"{exc}; sign in again: python -m Agent_Guru connect {provider_name}"
        raise OAuthError(msg) from exc
    return _store(provider_name, body, tokens)["access_token"]


def connected() -> dict[str, bool]:
    from Agent_Guru.security import secret_store

    return {name: secret_store.path_for(_secret_name(name)).exists() for name in PROVIDERS}


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru connect", description="Connect the owner's accounts.")
    parser.add_argument("action", nargs="?", default="status", help="a provider to sign in, 'status' or 'remove'")
    parser.add_argument("provider", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.action == "status":
        for name, is_connected in connected().items():
            print(f"{name:10} {'connected' if is_connected else 'not connected'}")  # noqa: T201  the command's output
        return 0
    if args.action == "remove":
        from Agent_Guru.security import secret_store

        removed = secret_store.delete(_secret_name(args.provider))
        print(f"{args.provider}: {'tokens removed' if removed else 'was not connected'}")  # noqa: T201
        return 0
    try:
        sign_in(args.action)
    except OAuthError as exc:
        print(exc)  # noqa: T201
        return 1
    print(f"{args.action} connected.")  # noqa: T201
    return 0
