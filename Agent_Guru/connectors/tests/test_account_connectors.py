"""The owner's accounts as tools, each against a stand-in for its service, and the OAuth sign-in behind them.

Gmail, Outlook, Google and Outlook calendars and contacts, Drive, Tasks,
Notion, GitHub, Dropbox, Oura, Strava and Spotify answer through httpx's
MockTransport in the shape their APIs document. IMAP mail talks to a
scripted server on this machine; Obsidian notes, an .ics calendar and
file search use folders made for the test. OAuth runs its real
listener, with a stand-in browser and token endpoint. None of it proves
a real account works; it proves the requests sent and that a refusal is
an error the owner hears, not an empty or invented answer.
"""

from __future__ import annotations

import base64
import datetime as dt
import email
import email.policy
import hashlib
import imaplib
import json
import socket
import threading
import time
import urllib.parse
import urllib.request

import httpx
import pytest

from Agent_Guru.connectors import oauth
from Agent_Guru.connectors import tools as connector_tools
from Agent_Guru.connectors.tools import ConnectorTools


@pytest.fixture
def service(monkeypatch):
    """httpx requests go to the first route whose key is in the URL; access tokens are "tok-<provider>"."""
    seen: list[httpx.Request] = []
    routes: dict[str, object] = {}

    def handle(request):
        seen.append(request)
        for key, answer in routes.items():
            if key in str(request.url):
                return answer(request) if callable(answer) else answer
        return httpx.Response(404, json={"error": "no route in the test"})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(oauth, "access_token", lambda provider: f"tok-{provider}")
    monkeypatch.setattr(oauth, "connected", lambda: {"google": True, "microsoft": True, "strava": True, "spotify": True})
    monkeypatch.setattr(connector_tools, "_saved_contacts", lambda query, limit: [])
    return seen, routes


def _use(monkeypatch, provider):
    monkeypatch.setattr(connector_tools, "_provider", lambda: provider)


async def _call(name, **arguments):
    return await ConnectorTools().call(name, arguments)


# ---- Gmail ----

async def test_gmail_search_lists_then_reads_each_header(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "google")
    routes["/messages/m1"] = httpx.Response(200, json={"snippet": "Friday works for me", "payload": {"headers": [
        {"name": "From", "value": "Rahul <rahul@example.org>"}, {"name": "Subject", "value": "Demo"},
        {"name": "Date", "value": "Mon, 26 Oct 2026 10:00:00 +0530"}]}})
    routes["/users/me/messages"] = httpx.Response(200, json={"messages": [{"id": "m1"}]})
    text, is_error = await _call("mail_search", query="from:rahul", limit=3)
    assert not is_error and text == "[m1] Mon, 26 Oct 2026 10:00:00 +0530 | Rahul <rahul@example.org> | Demo | Friday works for me"  # nosec B101
    listing, header = seen
    assert listing.headers["authorization"] == "Bearer tok-google"  # nosec B101
    assert listing.url.params["q"] == "from:rahul" and listing.url.params["maxResults"] == "3"  # nosec B101
    assert header.url.params["format"] == "metadata"  # nosec B101
    assert header.url.params.get_list("metadataHeaders") == ["From", "Subject", "Date"]  # nosec B101


async def test_gmail_read_decodes_the_raw_message(service, monkeypatch):
    _, routes = service
    _use(monkeypatch, "google")
    message = email.message.EmailMessage()
    message["From"], message["Subject"] = "rahul@example.org", "Lease"
    message.set_content("The rent is 25,000 a month.")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
    routes["/messages/m1"] = httpx.Response(200, json={"raw": raw})
    text, is_error = await _call("mail_read", id="m1")
    assert not is_error and "Subject: Lease" in text and "25,000 a month" in text  # nosec B101


async def test_gmail_send_posts_the_message_and_is_confirmed_by_its_id(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "google")
    routes["/messages/send"] = httpx.Response(200, json={"id": "s1", "labelIds": ["SENT"]})
    text, is_error, verified = await _call("mail_send", to="rahul@example.org", body="Running late\nSee you at 7")
    assert not is_error and verified and "id s1" in text  # nosec B101
    sent = email.message_from_bytes(base64.urlsafe_b64decode(json.loads(seen[0].content)["raw"]), policy=email.policy.default)
    assert sent["To"] == "rahul@example.org" and sent["Subject"] == "Running late"  # nosec B101


async def test_a_google_refusal_is_an_error(service, monkeypatch):
    _, routes = service
    _use(monkeypatch, "google")
    routes["/users/me/messages"] = httpx.Response(401, json={"error": {"code": 401, "status": "UNAUTHENTICATED"}})
    text, is_error = await _call("mail_search", query="rahul")
    assert is_error and "401" in text  # nosec B101


# ---- Outlook ----

async def test_outlook_search_quotes_the_words_and_reads_the_sender(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/messages"] = httpx.Response(200, json={"value": [{
        "id": "o1", "receivedDateTime": "2026-10-26T04:30:00Z", "subject": "Demo",
        "from": {"emailAddress": {"address": "rahul@example.org"}}, "bodyPreview": "Friday works"}]})
    text, is_error = await _call("mail_search", query="demo friday")
    assert not is_error and text == "[o1] 2026-10-26T04:30:00Z | rahul@example.org | Demo | Friday works"  # nosec B101
    assert seen[0].url.params["$search"] == '"demo friday"' and seen[0].headers["authorization"] == "Bearer tok-microsoft"  # nosec B101


async def test_outlook_read_strips_the_html(service, monkeypatch):
    _, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/messages/o1"] = httpx.Response(200, json={"subject": "Lease", "receivedDateTime": "2026-10-26T04:30:00Z",
                                                         "from": {"emailAddress": {"address": "a@example.org"}},
                                                         "body": {"content": "<p>Rent is <b>25,000</b></p>"}})
    text, _ = await _call("mail_read", id="o1")
    assert "Rent is 25,000" in text and "<b>" not in text  # nosec B101


async def test_outlook_send_takes_graphs_empty_202_as_sent(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/sendMail"] = httpx.Response(202)
    text, is_error, verified = await _call("mail_send", to="rahul@example.org", subject="Late", body="See you at 7")
    assert not is_error and verified  # nosec B101
    assert json.loads(seen[0].content) == {"message": {"subject": "Late", "body": {"contentType": "Text", "content": "See you at 7"},
                                                       "toRecipients": [{"emailAddress": {"address": "rahul@example.org"}}]}}  # nosec B101


# ---- calendars ----

async def test_google_calendar_lists_the_coming_days_in_order(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "google")
    routes["/calendars/primary/events"] = httpx.Response(200, json={"items": [
        {"summary": "Standup", "start": {"dateTime": "2026-10-27T15:00:00+05:30"}, "location": "Room 2"},
        {"summary": "Holiday", "start": {"date": "2026-10-28"}}]})
    text, _ = await _call("calendar_events", days=3)
    assert text.splitlines() == ["2026-10-27T15:00:00+05:30 | Standup | Room 2", "2026-10-28 | Holiday | "]  # nosec B101
    params = seen[0].url.params
    assert params["singleEvents"] == "true" and params["orderBy"] == "startTime"  # nosec B101
    span = dt.datetime.fromisoformat(params["timeMax"]) - dt.datetime.fromisoformat(params["timeMin"])
    assert span == dt.timedelta(days=3)  # nosec B101


async def test_outlook_calendar_times_are_given_in_local_time(service, monkeypatch):
    """Graph answers in UTC without an offset; the 09:30 UTC standup used to be read out as 09:30."""
    _, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/calendarview"] = httpx.Response(200, json={"value": [{"subject": "Standup", "location": {"displayName": "Teams"},
                                                                     "start": {"dateTime": "2026-10-27T09:30:00.0000000", "timeZone": "UTC"}}]})
    text, _ = await _call("calendar_events", days=2)
    local = dt.datetime(2026, 10, 27, 9, 30, tzinfo=dt.UTC).astimezone().isoformat(timespec="minutes")
    assert text == f"{local} | Standup | Teams"  # nosec B101


async def test_google_calendar_add_sends_the_times_with_their_offset(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "google")
    routes["/calendars/primary/events"] = httpx.Response(200, json={"id": "ev1"})
    text, is_error, verified = await _call("calendar_add", title="Dentist", start="2026-10-28T15:00:00+05:30", minutes=45)
    assert not is_error and verified  # nosec B101
    body = json.loads(seen[0].content)
    assert body["start"] == {"dateTime": "2026-10-28T15:00:00+05:30"} and body["end"] == {"dateTime": "2026-10-28T15:45:00+05:30"}  # nosec B101


@pytest.mark.parametrize("start", ["2026-10-28T15:00:00+05:30", "2026-10-28T09:30:00Z"])
async def test_outlook_calendar_add_sends_utc_which_graph_always_accepts(service, monkeypatch, start):
    """str(tzinfo) used to send "UTC+05:30", a zone name Graph does not have."""
    seen, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/events"] = httpx.Response(201, json={"id": "ev1"})
    _, is_error, verified = await _call("calendar_add", title="Dentist", start=start)
    assert not is_error and verified  # nosec B101
    body = json.loads(seen[0].content)
    assert body["start"] == {"dateTime": "2026-10-28T09:30:00", "timeZone": "UTC"}  # nosec B101
    assert body["end"] == {"dateTime": "2026-10-28T10:30:00", "timeZone": "UTC"}  # nosec B101


async def test_outlook_calendar_add_of_a_local_time_is_that_instant_in_utc(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "microsoft")
    routes["/me/events"] = httpx.Response(201, json={"id": "ev1"})
    await _call("calendar_add", title="Dentist", start="2026-10-28T15:00:00")
    expected = dt.datetime(2026, 10, 28, 15, 0).astimezone().astimezone(dt.UTC).replace(tzinfo=None).isoformat()
    assert json.loads(seen[0].content)["start"] == {"dateTime": expected, "timeZone": "UTC"}  # nosec B101


async def test_an_ics_calendar_gives_the_events_in_range(service, monkeypatch, tmp_path):
    _use(monkeypatch, "")
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    later = dt.datetime.now(dt.UTC) + dt.timedelta(days=20)
    ics = tmp_path / "cal.ics"
    # Bytes, as a calendar export is: write_text on Windows would turn each CRLF into CR CR LF.
    ics.write_bytes(("BEGIN:VCALENDAR\r\n" + "".join(
        f"BEGIN:VEVENT\r\nDTSTART:{when:%Y%m%dT%H%M%S}Z\r\nSUMMARY:{name}\r\nLOCATION:Room\r\n  2\r\nEND:VEVENT\r\n"
        for when, name in ((soon, "Standup"), (later, "Far away"))) + "END:VCALENDAR\r\n").encode())
    monkeypatch.setenv("CALENDAR_ICS", str(ics))
    text, is_error = await _call("calendar_events", days=7)
    local = soon.replace(microsecond=0).astimezone()
    assert not is_error and text == f"{local:%a %d %b %H:%M} | Standup | Room 2"  # nosec B101  folded line unfolded, far event left out


# ---- contacts ----

async def test_google_and_outlook_contacts(service, monkeypatch):
    seen, routes = service
    _use(monkeypatch, "google")
    routes["people:searchContacts"] = httpx.Response(200, json={"results": [{"person": {
        "names": [{"displayName": "Rahul K"}], "emailAddresses": [{"value": "rahul@example.org"}],
        "phoneNumbers": [{"value": "+91 99999 99999"}]}}]})
    text, _ = await _call("contacts_search", query="rahul")
    assert text == "Rahul K | rahul@example.org | +91 99999 99999"  # nosec B101
    assert seen[-1].url.params["readMask"] == "names,emailAddresses,phoneNumbers"  # nosec B101
    _use(monkeypatch, "microsoft")
    routes["/me/contacts"] = httpx.Response(200, json={"value": [{"displayName": "Rahul K", "mobilePhone": "+91 88888 88888",
                                                                 "emailAddresses": [{"address": "rk@example.org"}]}]})
    text, _ = await _call("contacts_search", query="rahul")
    assert text == "Rahul K | rk@example.org | +91 88888 88888"  # nosec B101


# ---- Drive, Tasks, Notion, GitHub, Dropbox ----

async def test_drive_search_escapes_a_quote_in_the_name(service):
    seen, routes = service
    routes["/drive/v3/files"] = httpx.Response(200, json={"files": [
        {"name": "Rahul's lease.pdf", "modifiedTime": "2026-10-01T10:00:00Z", "webViewLink": "https://drive.example/1"}]})
    text, _ = await _call("drive_search", query="rahul's lease")
    assert text == "Rahul's lease.pdf | 2026-10-01 | https://drive.example/1"  # nosec B101
    assert seen[0].url.params["q"] == ("(name contains 'rahul\\'s lease' or fullText contains 'rahul\\'s lease') "
                                       "and trashed = false")  # nosec B101


async def test_tasks_list_and_add(service):
    seen, routes = service
    routes["/lists/@default/tasks"] = lambda r: (httpx.Response(200, json={"id": "t9"}) if r.method == "POST" else
                                                httpx.Response(200, json={"items": [{"title": "Pay rent", "due": "2026-11-01T00:00:00.000Z"},
                                                                                    {"title": "Call mom"}]}))
    text, _ = await _call("tasks_list")
    assert text == "Pay rent (due 2026-11-01)\nCall mom" and seen[0].url.params["showCompleted"] == "false"  # nosec B101
    _, is_error, verified = await _call("task_add", title="Book tickets", due="2026-11-02")
    assert not is_error and verified  # nosec B101
    assert json.loads(seen[1].content) == {"title": "Book tickets", "notes": "", "due": "2026-11-02T00:00:00.000Z"}  # nosec B101


async def test_notion_github_and_dropbox_use_the_owners_tokens(service, monkeypatch):
    seen, routes = service
    monkeypatch.setenv("NOTION_TOKEN", "secret_n")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_1")
    monkeypatch.setenv("DROPBOX_TOKEN", "sl.d")
    routes["api.notion.com"] = httpx.Response(200, json={"results": [{"url": "https://notion.so/p1", "last_edited_time": "2026-10-20T08:00:00Z",
                                                                     "properties": {"Name": {"type": "title", "title": [{"plain_text": "Trip plan"}]}}}]})
    routes["api.github.com"] = httpx.Response(200, json=[{"repository": {"full_name": "suraj/agent"}, "reason": "review_requested",
                                                          "subject": {"type": "PullRequest", "title": "Fix voice"}}])
    routes["api.dropboxapi.com"] = httpx.Response(200, json={"matches": [{"metadata": {"metadata": {"path_display": "/Docs/lease.pdf"}}}]})
    assert (await _call("notion_search", query="trip"))[0] == "Trip plan | 2026-10-20 | https://notion.so/p1"  # nosec B101
    assert (await _call("github_notifications"))[0] == "suraj/agent | PullRequest | Fix voice | review_requested"  # nosec B101
    assert (await _call("dropbox_search", query="lease"))[0] == "/Docs/lease.pdf"  # nosec B101
    notion, github, dropbox = seen
    assert notion.headers["authorization"] == "Bearer secret_n" and notion.headers["notion-version"]  # nosec B101
    assert github.headers["authorization"] == "Bearer ghp_1"  # nosec B101
    assert dropbox.headers["authorization"] == "Bearer sl.d" and json.loads(dropbox.content)["query"] == "lease"  # nosec B101


@pytest.mark.parametrize("tool, env, host", [("notion_search", "NOTION_TOKEN", "api.notion.com"),
                                             ("github_notifications", "GITHUB_TOKEN", "api.github.com"),
                                             ("dropbox_search", "DROPBOX_TOKEN", "api.dropboxapi.com")])
async def test_a_refused_token_is_an_error_not_an_empty_result(service, monkeypatch, tool, env, host):
    _, routes = service
    monkeypatch.setenv(env, "revoked")
    routes[host] = httpx.Response(401, json={"message": "Bad credentials"})
    text, is_error = await _call(tool, **({"query": "x"} if tool != "github_notifications" else {}))
    assert is_error and "401" in text  # nosec B101


# ---- Oura, Strava, Spotify ----

async def test_oura_joins_sleep_and_activity_by_day(service, monkeypatch):
    seen, routes = service
    monkeypatch.setenv("OURA_TOKEN", "o1")
    routes["daily_sleep"] = httpx.Response(200, json={"data": [{"day": "2026-10-25", "score": 81}]})
    routes["daily_activity"] = httpx.Response(200, json={"data": [{"day": "2026-10-25", "score": 74, "steps": 8200}]})
    text, is_error = await _call("health_summary", days=3)
    assert not is_error and text == "2026-10-25: sleep 81, activity 74, 8200 steps"  # nosec B101
    assert seen[0].url.params["start_date"] == (dt.date.today() - dt.timedelta(days=3)).isoformat()  # nosec B101


async def test_an_expired_oura_token_is_an_error_not_no_data(service, monkeypatch):
    _, routes = service
    monkeypatch.setenv("OURA_TOKEN", "expired")
    routes["ouraring"] = httpx.Response(401, json={"detail": "Invalid token"})
    text, is_error = await _call("health_summary")
    assert is_error and "401" in text and "No Oura data" not in text  # nosec B101


async def test_strava_lists_recent_activities(service):
    seen, routes = service
    routes["athlete/activities"] = httpx.Response(200, json=[{"start_date_local": "2026-10-25T06:30:00Z", "sport_type": "Run",
                                                              "name": "Morning run", "distance": 5230.0, "moving_time": 1710}])
    text, _ = await _call("strava_activities", limit=2)
    assert text == "2026-10-25 | Run | Morning run | 5.2 km | 28 min" and seen[0].url.params["per_page"] == "2"  # nosec B101
    assert seen[0].headers["authorization"] == "Bearer tok-strava"  # nosec B101


@pytest.mark.parametrize("answer, expected, is_error", [
    (httpx.Response(204), "Nothing is playing on Spotify.", False),
    (httpx.Response(200, json={"item": {"name": "Kun Faya Kun", "artists": [{"name": "A. R. Rahman"}]}}), "Kun Faya Kun by A. R. Rahman", False),
    # The 401 used to come back as the song "? by ", a success.
    (httpx.Response(401, json={"error": {"status": 401, "message": "The access token expired"}}), "401", True),
])
async def test_spotify_now_playing(service, answer, expected, is_error):
    _, routes = service
    routes["currently-playing"] = answer
    text, error = await _call("music_now")
    assert error is is_error and expected in text  # nosec B101


async def test_spotify_play_searches_then_plays_the_track(service):
    seen, routes = service
    routes["/v1/search"] = httpx.Response(200, json={"tracks": {"items": [{"uri": "spotify:track:1"}]}})
    routes["/me/player/play"] = httpx.Response(204)
    text, is_error, verified = await _call("music_control", action="play", query="kun faya kun")
    assert not is_error and verified  # nosec B101
    search, play = seen
    assert search.url.params["q"] == "kun faya kun" and search.url.params["type"] == "track"  # nosec B101
    assert play.method == "PUT" and json.loads(play.content) == {"uris": ["spotify:track:1"]}  # nosec B101


@pytest.mark.parametrize("answer, expected", [
    (httpx.Response(404, json={"error": {"status": 404, "message": "Player command failed: No active device found",
                                         "reason": "NO_ACTIVE_DEVICE"}}), "open Spotify on a device first"),
    (httpx.Response(403, json={"error": {"status": 403, "message": "Player command failed: Premium required",
                                         "reason": "PREMIUM_REQUIRED"}}), "Premium required"),
    (httpx.Response(401, json={"error": {"status": 401, "message": "The access token expired"}}), "The access token expired"),
])
async def test_a_spotify_refusal_says_why(service, answer, expected):
    """Every refusal used to tell the owner to open Spotify on a device."""
    _, routes = service
    routes["/me/player/pause"] = answer
    text, is_error = await _call("music_control", action="pause")
    assert is_error and expected in text  # nosec B101
    if "device" not in expected:
        assert "device" not in text  # nosec B101


async def test_a_refused_spotify_search_is_not_nothing_found(service):
    seen, routes = service
    routes["/v1/search"] = httpx.Response(401, json={"error": {"status": 401, "message": "The access token expired"}})
    text, is_error = await _call("music_control", action="play", query="kun faya kun")
    assert is_error and "401" in text and "found nothing" not in text and len(seen) == 1  # nosec B101


# ---- local sources ----

async def test_obsidian_notes_and_file_names(service, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Trips").mkdir()
    (vault / "Trips" / "Goa.md").write_text("# Goa\nFlight 6E 523 on 14 Nov\n", encoding="utf-8")
    (vault / ".obsidian" / "cache.md").write_text("Flight 6E 523", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    text, _ = await _call("notes_search", query="flight 6E")
    assert text.replace("\\", "/") == "Trips/Goa.md | Flight 6E 523 on 14 Nov"  # nosec B101  the app's own folder is skipped
    docs = tmp_path / "docs"
    (docs / "node_modules").mkdir(parents=True)
    (docs / "Lease agreement 2026.pdf").write_bytes(b"%PDF")
    (docs / "node_modules" / "lease.js").write_text("x", encoding="utf-8")
    monkeypatch.setenv("FILES_ROOTS", str(docs))
    text, _ = await _call("files_search", query="lease 2026")
    assert text == str(docs / "Lease agreement 2026.pdf")  # nosec B101


# ---- IMAP ----

class ImapServer:
    """A scripted IMAP4rev1 server: three messages, SEARCH answers by criteria, literals accepted."""

    HEADERS = {b"2": b"From: Ramesh <r@example.org>\r\nSubject: Rent\r\nDate: Sun, 25 Oct 2026 09:00:00 +0530\r\n\r\n",
               b"3": "From: राहुल <rahul@example.org>\r\nSubject: नमस्ते\r\nDate: Mon, 26 Oct 2026 09:00:00 +0530\r\n\r\n".encode()}

    def __init__(self):
        self.commands: list[bytes] = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        f = conn.makefile("rwb")
        f.write(b"* OK ready\r\n")
        f.flush()
        while line := f.readline():
            if line.rstrip().endswith(b"}"):
                size = int(line.rstrip()[line.rindex(b"{") + 1:-1])
                f.write(b"+ go\r\n")
                f.flush()
                line = line.rstrip()[: line.rindex(b"{")] + b"<" + f.read(size) + b">" + f.readline()
            self.commands.append(line)
            tag, command = line.split()[0], line.split()[1].upper()
            out = {b"CAPABILITY": b"* CAPABILITY IMAP4rev1\r\n", b"LOGIN": b"", b"EXAMINE": b"* 3 EXISTS\r\n",
                   b"LOGOUT": b"* BYE\r\n"}.get(command)
            if command == b"SEARCH":
                out = b"* SEARCH " + (b"3" if b"SUBJECT" in line and b"CHARSET" in line else b"2 3") + b"\r\n"
            elif command == b"FETCH":
                num = line.split()[2]
                data = self.HEADERS[num] + (b"Body of " + num if b"BODY.PEEK[]" in line else b"")
                out = b"* " + num + b" FETCH (BODY[] {" + str(len(data)).encode() + b"}\r\n" + data + b")\r\n"
            f.write((out or b"") + tag + b" OK done\r\n")
            f.flush()
            if command == b"LOGOUT":
                break
        conn.close()

    def close(self):
        self.sock.close()


@pytest.fixture
def imap(service, monkeypatch):
    server = ImapServer()
    _use(monkeypatch, "")
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port, timeout=None: imaplib.IMAP4(host, port, timeout=timeout))
    monkeypatch.setenv("IMAP_HOST", "127.0.0.1")
    monkeypatch.setenv("IMAP_PORT", str(server.port))
    monkeypatch.setenv("IMAP_USER", "me")
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    yield server
    server.close()


async def test_imap_search_lists_the_newest_first_read_only(imap):
    text, is_error = await _call("mail_search", query="rent")
    assert not is_error and text.splitlines()[0].startswith("[3]") and text.splitlines()[1].startswith("[2] ")  # nosec B101
    assert "Ramesh <r@example.org> | Rent" in text  # nosec B101
    sent = b"".join(imap.commands)
    assert b'SEARCH OR SUBJECT "rent" FROM "rent"' in sent and b"EXAMINE INBOX" in sent  # nosec B101  never SELECT: read only


async def test_imap_search_for_a_name_in_hindi(imap):
    """imaplib sends ASCII only: this raised UnicodeEncodeError before reaching the server."""
    text, is_error = await _call("mail_search", query="राहुल")
    assert not is_error and "राहुल <rahul@example.org>" in text  # nosec B101
    searches = [c for c in imap.commands if b"SEARCH" in c]
    assert [s.split(b" ", 1)[1] for s in searches] == [
        b"SEARCH CHARSET UTF-8 SUBJECT <" + "राहुल".encode() + b">\r\n",
        b"SEARCH CHARSET UTF-8 FROM <" + "राहुल".encode() + b">\r\n"]  # nosec B101


@pytest.mark.parametrize("query, quoted", [("Ramesh \\", b'"Ramesh "'), ('rent\r\nA1 DELETE "Archive"', b'"rent A1 DELETE Archive"')])
async def test_an_imap_query_cannot_break_the_command(imap, query, quoted):
    """A trailing backslash escaped the closing quote; a line break would start another command."""
    _, is_error = await _call("mail_search", query=query)
    assert not is_error  # nosec B101
    search = next(c for c in imap.commands if b"SEARCH" in c)
    assert search.endswith(b"SUBJECT " + quoted + b" FROM " + quoted + b"\r\n")  # nosec B101
    assert not any(c.split()[1] == b"DELETE" for c in imap.commands)  # nosec B101


async def test_imap_read_renders_the_message(imap):
    text, is_error = await _call("mail_read", id="2")
    assert not is_error and "Subject: Rent" in text and "Body of 2" in text  # nosec B101


# ---- OAuth ----

@pytest.fixture
def vault(monkeypatch):
    """The token store, in memory: nothing is written to the owner's secrets folder."""
    from Agent_Guru.security import secret_store

    kept: dict[str, object] = {}
    monkeypatch.setattr(secret_store, "save_json", lambda name, value: kept.__setitem__(name, value))
    monkeypatch.setattr(secret_store, "load_json", lambda name: kept.get(name))
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.example")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "csecret")
    return kept


@pytest.fixture
def token_endpoint(monkeypatch):
    asked: list[dict[str, str]] = []
    answer = {"value": httpx.Response(200, json={"access_token": "at1", "refresh_token": "rt1", "expires_in": 3600, "scope": "s"})}

    def post(url, data, timeout):
        asked.append({"url": url, **data})
        return answer["value"]

    monkeypatch.setattr(httpx, "post", post)
    return asked, answer


def _browser(monkeypatch, state=None, extra=None):
    """A stand-in browser: the owner signs in and the provider redirects to the listener."""
    opened: list[dict[str, str]] = []

    def visit(url):
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        opened.append(query)
        back = {"code": "c1", "state": state or query["state"], **(extra or {})}
        target = f"{query['redirect_uri']}?{urllib.parse.urlencode(back)}"
        threading.Thread(target=lambda: urllib.request.urlopen(target, timeout=10).read(), daemon=True).start()  # nosec B310 - the test's own listener
        return True

    monkeypatch.setattr(oauth.webbrowser, "open", visit)
    return opened


def test_sign_in_uses_pkce_and_keeps_the_tokens(vault, token_endpoint, monkeypatch):
    asked, _ = token_endpoint
    opened = _browser(monkeypatch)
    tokens = oauth.sign_in("google")
    (query,), (exchange,) = opened, asked
    assert query["code_challenge_method"] == "S256" and query["response_type"] == "code"  # nosec B101
    assert query["redirect_uri"].startswith("http://127.0.0.1:") and "gmail.readonly" in query["scope"]  # nosec B101
    # The verifier sent with the code is the one the challenge was made from.
    challenge = base64.urlsafe_b64encode(hashlib.sha256(exchange["code_verifier"].encode()).digest()).rstrip(b"=").decode()
    assert challenge == query["code_challenge"]  # nosec B101
    assert exchange["url"] == "https://oauth2.googleapis.com/token" and exchange["grant_type"] == "authorization_code"  # nosec B101
    assert exchange["code"] == "c1" and exchange["client_secret"] == "csecret" and exchange["redirect_uri"] == query["redirect_uri"]  # nosec B101
    assert tokens["access_token"] == "at1" and vault["oauth_tokens_google"]["refresh_token"] == "rt1"  # nosec B101


def test_a_redirect_with_another_state_keeps_nothing(vault, token_endpoint, monkeypatch):
    asked, _ = token_endpoint
    _browser(monkeypatch, state="forged")
    with pytest.raises(oauth.OAuthError, match="state did not match"):
        oauth.sign_in("google")
    assert not asked and not vault  # nosec B101  the code was never exchanged


def test_a_sign_in_the_owner_declines_is_reported(vault, token_endpoint, monkeypatch):
    _browser(monkeypatch, extra={"error": "access_denied"})
    with pytest.raises(oauth.OAuthError, match="access_denied"):
        oauth.sign_in("google")
    assert not vault  # nosec B101


def test_a_fresh_token_is_used_without_asking_the_provider(vault, token_endpoint):
    asked, _ = token_endpoint
    vault["oauth_tokens_google"] = {"access_token": "live", "refresh_token": "rt1", "expires_at": time.time() + 3000}
    assert oauth.access_token("google") == "live" and not asked  # nosec B101


def test_an_expiring_token_is_refreshed_and_the_refresh_token_kept(vault, token_endpoint):
    asked, answer = token_endpoint
    vault["oauth_tokens_google"] = {"access_token": "old", "refresh_token": "rt1", "expires_at": time.time() + 30}
    answer["value"] = httpx.Response(200, json={"access_token": "new", "expires_in": 3599})
    assert oauth.access_token("google") == "new"  # nosec B101
    assert asked[0]["grant_type"] == "refresh_token" and asked[0]["refresh_token"] == "rt1"  # nosec B101
    # Google's refresh answer has no refresh token; the old one must survive or the next refresh fails.
    assert vault["oauth_tokens_google"]["refresh_token"] == "rt1"  # nosec B101


def test_a_revoked_grant_tells_the_owner_to_sign_in_again(vault, token_endpoint):
    _, answer = token_endpoint
    vault["oauth_tokens_google"] = {"access_token": "old", "refresh_token": "rt1", "expires_at": time.time() - 10}
    answer["value"] = httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
    with pytest.raises(oauth.OAuthError) as raised:
        oauth.access_token("google")
    assert "expired or revoked" in str(raised.value) and "connect google" in str(raised.value)  # nosec B101
    assert "rt1" not in str(raised.value)  # nosec B101


def test_a_tool_whose_account_is_not_connected_says_how_to_connect(monkeypatch):
    monkeypatch.setattr(connector_tools, "_provider", lambda: "google")

    def not_connected(provider):
        raise oauth.OAuthError(f"{provider} is not connected; run: python -m Agent_Guru connect {provider}")

    monkeypatch.setattr(oauth, "access_token", not_connected)
    import asyncio

    text, is_error = asyncio.run(ConnectorTools().call("mail_search", {"query": "rahul"}))
    assert is_error and text == "google is not connected; run: python -m Agent_Guru connect google"  # nosec B101
