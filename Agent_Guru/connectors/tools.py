"""The owner's mail, calendar, contacts and files, as tools the assistant can call.

"Did Rahul reply about Friday?", "what's on my calendar tomorrow?",
"find the warranty PDF" had nothing to answer from: the assistant could
open the mail app, not read it. These tools are served in process
through the same toolbox as MCP servers (integration/mcp_tools.py), so
each call gets the policy check, schema check, output guard, taint
labels and, for sending mail or adding an event, the owner's yes.

Each tool uses what the owner connected, in this order:

    mail       Google (Gmail) or Microsoft (Outlook) via OAuth, else IMAP (IMAP_HOST, IMAP_USER, IMAP_PASSWORD)
    sending    Gmail, Outlook, else SMTP (platform/channels)
    calendar   Google or Microsoft, else a local .ics file (CALENDAR_ICS)
    contacts   Google or Microsoft, plus the assistant's own saved contacts
    files      file names under FILES_ROOTS (default: Documents, Desktop, Downloads)

Everything a provider returns is outside text: it is cut to size here,
and the toolbox scans it for instructions before the model sees it.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import email
import email.policy
import imaplib
import os
import re
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

SERVER_NAME = "connectors"
_TIMEOUT = 20.0
_MAX_RESULTS = 10
_MAX_BODY = 4000

_Q = {"type": "object", "properties": {
    "query": {"type": "string", "minLength": 1, "maxLength": 200},
    "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_RESULTS}},
    "required": ["query"], "additionalProperties": False}


def _provider() -> str:
    from Agent_Guru.connectors.oauth import connected

    linked = connected()
    return "google" if linked.get("google") else ("microsoft" if linked.get("microsoft") else "")


async def _get(url: str, provider: str, **params: Any) -> Any:
    import httpx

    from Agent_Guru.connectors.oauth import access_token

    token = await asyncio.to_thread(access_token, provider)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(url, params=params or None, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json()


async def _post(url: str, provider: str, body: Any) -> Any:
    import httpx

    from Agent_Guru.connectors.oauth import access_token

    token = await asyncio.to_thread(access_token, provider)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json() if response.content else {}


def _clip(text: str, limit: int = 300) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


class ConnectorTools:
    """Mail, calendar, contacts and files tools (see the module docstring)."""

    def tool_list(self) -> list[dict[str, Any]]:
        """Only the tools that can work now: the tool loop offers at most 12 a turn, and a mail
        tool with no mail account would only crowd out one that works."""
        provider = _provider()
        mail = bool(provider or os.environ.get("IMAP_HOST"))
        send = bool(provider) or bool(os.environ.get("SMTP_HOST"))
        calendar = bool(provider or os.environ.get("CALENDAR_ICS"))
        usable = {"mail_search": mail, "mail_read": mail, "mail_send": send, "calendar_events": calendar,
                  "calendar_add": bool(provider), "contacts_search": True, "files_search": True}
        return [t for t in self._all_tools() if usable.get(t["name"], False)]

    def _all_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "mail_search", "description": "Search the owner's mail (sender, subject, words). Returns id, from, subject, date and a snippet.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "mail_read", "description": "Read one mail by the id mail_search gave.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {
                 "id": {"type": "string", "minLength": 1, "maxLength": 200}}, "required": ["id"], "additionalProperties": False}},
            {"name": "mail_send", "description": "Send an email from the owner's account. The owner confirms first.",
             "annotations": {"readOnlyHint": False, "openWorldHint": True}, "inputSchema": {"type": "object", "properties": {
                 "to": {"type": "string", "minLength": 3, "maxLength": 200},
                 "subject": {"type": "string", "maxLength": 200},
                 "body": {"type": "string", "minLength": 1, "maxLength": _MAX_BODY}},
                 "required": ["to", "body"], "additionalProperties": False}},
            {"name": "calendar_events", "description": "The owner's calendar events for the next days (default 7).",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {
                 "days": {"type": "integer", "minimum": 1, "maximum": 60}}, "additionalProperties": False}},
            {"name": "calendar_add", "description": "Add an event to the owner's calendar: title, start (ISO 8601 local time), minutes. The owner confirms first.",
             "annotations": {"readOnlyHint": False, "openWorldHint": True}, "inputSchema": {"type": "object", "properties": {
                 "title": {"type": "string", "minLength": 1, "maxLength": 200},
                 "start": {"type": "string", "minLength": 10, "maxLength": 40},
                 "minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
                 "notes": {"type": "string", "maxLength": 1000}},
                 "required": ["title", "start"], "additionalProperties": False}},
            {"name": "contacts_search", "description": "Find a contact's email or phone by name.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "files_search", "description": "Find the owner's files by name in Documents, Desktop and Downloads. Returns paths.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        handler = {
            "mail_search": self._mail_search, "mail_read": self._mail_read, "mail_send": self._mail_send,
            "calendar_events": self._calendar_events, "calendar_add": self._calendar_add,
            "contacts_search": self._contacts_search, "files_search": self._files_search,
        }.get(name)
        if handler is None:
            return f"no tool named {name}", True
        try:
            return await handler(**arguments)
        except Exception as exc:
            from Agent_Guru.connectors.oauth import OAuthError

            if isinstance(exc, OAuthError):
                return str(exc), True
            return f"{name} failed: {type(exc).__name__}: {_clip(str(exc), 200)}", True

    # ---- mail ----

    async def _mail_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        provider = _provider()
        lines: list[str] = []
        if provider == "google":
            listing = await _get("https://gmail.googleapis.com/gmail/v1/users/me/messages", provider, q=query, maxResults=limit)
            for item in listing.get("messages") or []:
                msg = await _get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}", provider,
                                 format="metadata", metadataHeaders=["From", "Subject", "Date"])
                headers = {h["name"]: h["value"] for h in (msg.get("payload") or {}).get("headers") or []}
                lines.append(f"[{item['id']}] {headers.get('Date', '')} | {headers.get('From', '')} | "
                             f"{headers.get('Subject', '')} | {_clip(msg.get('snippet', ''), 160)}")
        elif provider == "microsoft":
            listing = await _get("https://graph.microsoft.com/v1.0/me/messages", provider, **{
                "$search": f'"{query}"', "$top": limit, "$select": "id,from,subject,receivedDateTime,bodyPreview"})
            for m in listing.get("value") or []:
                sender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
                lines.append(f"[{m['id']}] {m.get('receivedDateTime', '')} | {sender} | {m.get('subject', '')} | "
                             f"{_clip(m.get('bodyPreview', ''), 160)}")
        elif os.environ.get("IMAP_HOST"):
            lines = await asyncio.to_thread(_imap_search, query, limit)
        else:
            return "No mail account is connected: python -m Agent_Guru connect google (or microsoft), or set IMAP_HOST.", True
        return ("\n".join(lines) if lines else f"No mail matches {query!r}."), False

    async def _mail_read(self, id: str) -> tuple[str, bool]:  # noqa: A002 - the tool's argument name
        provider = _provider()
        if provider == "google":
            msg = await _get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}", provider, format="raw")
            parsed = email.message_from_bytes(base64.urlsafe_b64decode(msg["raw"] + "=="), policy=email.policy.default)
            return _render(parsed), False
        if provider == "microsoft":
            m = await _get(f"https://graph.microsoft.com/v1.0/me/messages/{id}", provider,
                           **{"$select": "from,subject,receivedDateTime,body"})
            body = re.sub(r"<[^>]+>", " ", (m.get("body") or {}).get("content", ""))
            sender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
            return f"From: {sender}\nSubject: {m.get('subject', '')}\nDate: {m.get('receivedDateTime', '')}\n\n{_clip(body, _MAX_BODY)}", False
        if os.environ.get("IMAP_HOST"):
            return await asyncio.to_thread(_imap_read, id), False
        return "No mail account is connected.", True

    async def _mail_send(self, to: str, body: str, subject: str = "") -> tuple[Any, ...]:
        provider = _provider()
        message = EmailMessage()
        message["To"], message["Subject"] = to, subject or _clip(body.splitlines()[0], 60)
        message.set_content(body)
        if provider == "google":
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            sent = await _post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", provider, {"raw": raw})
            # Gmail answers with the stored message: a confirmed send.
            return f"Sent to {to} (id {sent.get('id', '?')}).", False, bool(sent.get("id"))
        if provider == "microsoft":
            await _post("https://graph.microsoft.com/v1.0/me/sendMail", provider, {"message": {
                "subject": message["Subject"], "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}]}})
            return f"Sent to {to}.", False, True
        from Agent_Guru.platform.channels import channel_for

        channel = channel_for("email")
        if channel is None:
            return "No way to send mail is set up: connect google or microsoft, or set SMTP_HOST.", True
        delivery = await channel.send(to, body, subject=message["Subject"])
        return (f"Sent to {to}.", False, True) if delivery.sent else (f"Not sent: {delivery.error}", True)

    # ---- calendar ----

    async def _calendar_events(self, days: int = 7) -> tuple[str, bool]:
        provider = _provider()
        start = dt.datetime.now().astimezone()
        end = start + dt.timedelta(days=days)
        lines: list[str] = []
        if provider == "google":
            listing = await _get("https://www.googleapis.com/calendar/v3/calendars/primary/events", provider,
                                 timeMin=start.isoformat(), timeMax=end.isoformat(), singleEvents="true",
                                 orderBy="startTime", maxResults=50)
            for e in listing.get("items") or []:
                when = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date", "")
                lines.append(f"{when} | {e.get('summary', '(no title)')} | {_clip(e.get('location', ''), 80)}")
        elif provider == "microsoft":
            listing = await _get("https://graph.microsoft.com/v1.0/me/calendarview", provider,
                                 startDateTime=start.isoformat(), endDateTime=end.isoformat(),
                                 **{"$orderby": "start/dateTime", "$top": 50, "$select": "subject,start,location"})
            for e in listing.get("value") or []:
                lines.append(f"{(e.get('start') or {}).get('dateTime', '')} | {e.get('subject', '')} | "
                             f"{_clip(((e.get('location') or {}).get('displayName') or ''), 80)}")
        elif os.environ.get("CALENDAR_ICS"):
            lines = await asyncio.to_thread(_ics_events, Path(os.environ["CALENDAR_ICS"]), start, end)
        else:
            return "No calendar is connected: python -m Agent_Guru connect google, or set CALENDAR_ICS.", True
        return ("\n".join(lines) if lines else f"Nothing on the calendar in the next {days} days."), False

    async def _calendar_add(self, title: str, start: str, minutes: int = 60, notes: str = "") -> tuple[Any, ...]:
        provider = _provider()
        begin = dt.datetime.fromisoformat(start)
        if begin.tzinfo is None:
            begin = begin.astimezone()
        finish = begin + dt.timedelta(minutes=minutes)
        if provider == "google":
            made = await _post("https://www.googleapis.com/calendar/v3/calendars/primary/events", provider, {
                "summary": title, "description": notes,
                "start": {"dateTime": begin.isoformat()}, "end": {"dateTime": finish.isoformat()}})
            return f"Added {title!r} at {begin:%a %d %b %H:%M} (id {made.get('id', '?')}).", False, bool(made.get("id"))
        if provider == "microsoft":
            made = await _post("https://graph.microsoft.com/v1.0/me/events", provider, {
                "subject": title, "body": {"contentType": "Text", "content": notes},
                "start": {"dateTime": begin.replace(tzinfo=None).isoformat(), "timeZone": "UTC" if begin.utcoffset() == dt.timedelta(0) else str(begin.tzinfo)},
                "end": {"dateTime": finish.replace(tzinfo=None).isoformat(), "timeZone": "UTC" if begin.utcoffset() == dt.timedelta(0) else str(begin.tzinfo)}})
            return f"Added {title!r} at {begin:%a %d %b %H:%M}.", False, bool(made.get("id"))
        return "Adding events needs a connected Google or Microsoft calendar.", True

    # ---- contacts ----

    async def _contacts_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        provider = _provider()
        lines: list[str] = []
        if provider == "google":
            found = await _get("https://people.googleapis.com/v1/people:searchContacts", provider,
                               query=query, readMask="names,emailAddresses,phoneNumbers", pageSize=limit)
            for r in found.get("results") or []:
                p = r.get("person") or {}
                name = ((p.get("names") or [{}])[0]).get("displayName", "")
                mails = ", ".join(e.get("value", "") for e in p.get("emailAddresses") or [])
                phones = ", ".join(n.get("value", "") for n in p.get("phoneNumbers") or [])
                lines.append(f"{name} | {mails} | {phones}")
        elif provider == "microsoft":
            found = await _get("https://graph.microsoft.com/v1.0/me/contacts", provider,
                               **{"$search": f'"{query}"', "$top": limit})
            for c in found.get("value") or []:
                mails = ", ".join(e.get("address", "") for e in c.get("emailAddresses") or [])
                lines.append(f"{c.get('displayName', '')} | {mails} | {', '.join(c.get('mobilePhone') and [c['mobilePhone']] or [])}")
        lines.extend(_saved_contacts(query, limit))
        return ("\n".join(lines) if lines else f"No contact matches {query!r}."), False

    # ---- files ----

    async def _files_search(self, query: str, limit: int = _MAX_RESULTS) -> tuple[str, bool]:
        found = await asyncio.to_thread(_find_files, query, limit)
        return ("\n".join(found) if found else f"No file name matches {query!r}."), False


def _render(message: Any) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    text = part.get_content() if part is not None else ""
    if part is not None and part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return (f"From: {message.get('From', '')}\nSubject: {message.get('Subject', '')}\nDate: {message.get('Date', '')}"
            f"\n\n{_clip(text, _MAX_BODY)}")


def _imap() -> imaplib.IMAP4_SSL:
    box = imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], int(os.environ.get("IMAP_PORT", "993")), timeout=_TIMEOUT)
    box.login(os.environ.get("IMAP_USER", ""), os.environ.get("IMAP_PASSWORD", ""))
    box.select("INBOX", readonly=True)
    return box


def _imap_search(query: str, limit: int) -> list[str]:
    box = _imap()
    try:
        safe = query.replace('"', "")
        _, data = box.search(None, "OR", "SUBJECT", f'"{safe}"', "FROM", f'"{safe}"')
        ids = (data[0] or b"").split()[-limit:][::-1]
        lines = []
        for num in ids:
            _, parts = box.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            header = email.message_from_bytes(parts[0][1], policy=email.policy.default)
            lines.append(f"[{num.decode()}] {header.get('Date', '')} | {header.get('From', '')} | {header.get('Subject', '')}")
        return lines
    finally:
        box.logout()


def _imap_read(num: str) -> str:
    box = _imap()
    try:
        _, parts = box.fetch(num.encode(), "(BODY.PEEK[])")
        return _render(email.message_from_bytes(parts[0][1], policy=email.policy.default))
    finally:
        box.logout()


def _ics_events(path: Path, start: dt.datetime, end: dt.datetime) -> list[str]:
    from Agent_Guru.security.file_policy import check_path

    check_path(path, "read")
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n ", "").replace("\n ", "")
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        fields: dict[str, str] = {}
        for line in block.split("END:VEVENT")[0].splitlines():
            key, _, value = line.partition(":")
            fields.setdefault(key.split(";")[0].upper(), value.strip())
        raw = fields.get("DTSTART", "")
        try:
            when = dt.datetime.strptime(raw[:15], "%Y%m%dT%H%M%S") if "T" in raw else dt.datetime.strptime(raw[:8], "%Y%m%d")
        except ValueError:
            continue
        when = when.replace(tzinfo=dt.UTC).astimezone() if raw.endswith("Z") else when.astimezone()
        if start <= when <= end:
            events.append((when, f"{when:%a %d %b %H:%M} | {fields.get('SUMMARY', '(no title)')} | {_clip(fields.get('LOCATION', ''), 80)}"))
    return [line for _, line in sorted(events)][:50]


def _saved_contacts(query: str, limit: int) -> list[str]:
    """The messaging controller's own saved contacts that match *query*."""
    try:
        from Agent_Guru.platform.controllers.messaging_controller import _load_contacts, _resolve_contacts_path

        data = _load_contacts(_resolve_contacts_path())
    except (OSError, ValueError):
        return []
    q = query.lower()
    items = data.items() if isinstance(data, dict) else []
    return [f"{name} | " + ", ".join(f"{k}: {v}" for k, v in (ids or {}).items())
            for name, ids in items if q in str(name).lower()][:limit]


def _roots() -> list[Path]:
    configured = [Path(p).expanduser() for p in os.environ.get("FILES_ROOTS", "").split(os.pathsep) if p.strip()]
    home = Path.home()
    return configured or [home / "Documents", home / "Desktop", home / "Downloads"]


def _find_files(query: str, limit: int, budget_s: float = 5.0) -> list[str]:
    from Agent_Guru.security.file_policy import sensitive_reason

    words = [w for w in re.split(r"\W+", query.lower()) if w]
    deadline = time.monotonic() + budget_s
    found: list[str] = []
    for root in _roots():
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Hidden and package folders hold nothing the owner asks for by name.
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".git"}]
            for filename in filenames:
                if all(w in filename.lower() for w in words):
                    path = Path(dirpath) / filename
                    if not sensitive_reason(path):
                        found.append(str(path))
                        if len(found) >= limit:
                            return found
            if time.monotonic() > deadline:
                return found
    return found


def connectors_server() -> Any:
    """The ServerConfig for the connector tools; local is filled in by the caller."""
    from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

    rules = {name: ToolRule(allow=True, risk=ToolRisk.READ_ONLY)
             for name in ("mail_search", "mail_read", "calendar_events", "contacts_search", "files_search")}
    rules["mail_send"] = ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)
    rules["calendar_add"] = ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=30.0, tools=rules)
