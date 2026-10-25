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
        from Agent_Guru.connectors.oauth import connected

        linked = connected()
        google = bool(linked.get("google"))
        usable = {"mail_search": mail, "mail_read": mail, "mail_send": send, "calendar_events": calendar,
                  "calendar_add": bool(provider), "contacts_search": True, "files_search": True, "news": True,
                  "drive_search": google, "tasks_list": google, "task_add": google,
                  "notion_search": bool(os.environ.get("NOTION_TOKEN")),
                  "notes_search": bool(os.environ.get("OBSIDIAN_VAULT")),
                  "github_notifications": bool(os.environ.get("GITHUB_TOKEN")),
                  "dropbox_search": bool(os.environ.get("DROPBOX_TOKEN")),
                  "health_summary": bool(os.environ.get("OURA_TOKEN")),
                  "strava_activities": bool(linked.get("strava")),
                  "music_now": bool(linked.get("spotify")), "music_control": bool(linked.get("spotify")),
                  "slack_search": bool(os.environ.get("SLACK_USER_TOKEN")),
                  "meetings_search": bool(os.environ.get("GRANOLA_API_KEY")),
                  "meeting_read": bool(os.environ.get("GRANOLA_API_KEY"))}
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
            {"name": "news", "description": "Today's headlines with links: source 'headlines' (the owner's feeds) or 'hackernews'.",
             "annotations": {"readOnlyHint": True, "openWorldHint": True}, "inputSchema": {"type": "object", "properties": {
                 "source": {"type": "string", "enum": ["headlines", "hackernews"]},
                 "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_RESULTS}}, "additionalProperties": False}},
            {"name": "drive_search", "description": "Find files in the owner's Google Drive by name or content.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "tasks_list", "description": "The owner's open Google Tasks.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "task_add", "description": "Add a Google Task (optional due date YYYY-MM-DD). The owner confirms first.",
             "annotations": {"readOnlyHint": False}, "inputSchema": {"type": "object", "properties": {
                 "title": {"type": "string", "minLength": 1, "maxLength": 200},
                 "due": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                 "notes": {"type": "string", "maxLength": 1000}}, "required": ["title"], "additionalProperties": False}},
            {"name": "notion_search", "description": "Search the owner's Notion pages by title.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "notes_search", "description": "Search the owner's Obsidian notes; returns the note and the matching line.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "github_notifications", "description": "The owner's unread GitHub notifications.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "dropbox_search", "description": "Find files in the owner's Dropbox by name.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "health_summary", "description": "The owner's sleep and activity scores for the last days (Oura).",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {
                 "days": {"type": "integer", "minimum": 1, "maximum": 14}}, "additionalProperties": False}},
            {"name": "strava_activities", "description": "The owner's recent Strava activities: type, distance, time.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {
                 "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_RESULTS}}, "additionalProperties": False}},
            {"name": "music_now", "description": "What is playing on the owner's Spotify.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "music_control", "description": "Spotify playback: play (optionally a search query), pause, next, previous. The owner confirms first.",
             "annotations": {"readOnlyHint": False}, "inputSchema": {"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["play", "pause", "next", "previous"]},
                 "query": {"type": "string", "maxLength": 200}}, "required": ["action"], "additionalProperties": False}},
            {"name": "slack_search", "description": "Search the owner's Slack messages (words, from:@name, in:#channel). Returns when, who, where and the text.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "meetings_search", "description": "Find the owner's meeting notes in Granola by words in the title or summary. Returns id, date, title and summary.",
             "annotations": {"readOnlyHint": True}, "inputSchema": _Q},
            {"name": "meeting_read", "description": "Read one Granola meeting note by the id meetings_search gave: summary, attendees and transcript.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {
                 "id": {"type": "string", "minLength": 1, "maxLength": 100}}, "required": ["id"], "additionalProperties": False}},
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        handler = {
            "mail_search": self._mail_search, "mail_read": self._mail_read, "mail_send": self._mail_send,
            "calendar_events": self._calendar_events, "calendar_add": self._calendar_add,
            "contacts_search": self._contacts_search, "files_search": self._files_search,
            "news": self._news, "drive_search": self._drive_search, "tasks_list": self._tasks_list,
            "task_add": self._task_add, "notion_search": self._notion_search, "notes_search": self._notes_search,
            "github_notifications": self._github, "dropbox_search": self._dropbox_search,
            "health_summary": self._health, "strava_activities": self._strava,
            "music_now": self._music_now, "music_control": self._music_control,
            "slack_search": self._slack_search, "meetings_search": self._meetings_search, "meeting_read": self._meeting_read,
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

    # ---- Slack and Granola ----

    async def _slack_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        """Slack's search.messages, with the owner's user token (SLACK_USER_TOKEN, search:read scope).

        The bot token Slack sending uses cannot search: search is a user's view.
        """
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get("https://slack.com/api/search.messages", params={"query": query, "count": limit},
                                        headers={"Authorization": f"Bearer {os.environ['SLACK_USER_TOKEN']}"})
        body = response.json()
        if not body.get("ok"):
            return f"Slack refused the search: {body.get('error', response.status_code)}", True
        lines = []
        for m in ((body.get("messages") or {}).get("matches") or [])[:limit]:
            when = dt.datetime.fromtimestamp(float(m.get("ts", 0) or 0)).strftime("%Y-%m-%d %H:%M")
            where = (m.get("channel") or {}).get("name", "")
            lines.append(f"{when} | {m.get('username') or m.get('user', '')} | #{where} | {_clip(m.get('text', ''), 240)}")
        return ("\n".join(lines) if lines else f"No Slack message matches {query!r}."), False

    async def _granola(self, path: str, **params: Any) -> Any:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(f"https://public-api.granola.ai/v1/{path}", params=params or None,
                                        headers={"Authorization": f"Bearer {os.environ['GRANOLA_API_KEY']}"})
        response.raise_for_status()
        return response.json()

    async def _meetings_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        words = [w for w in query.lower().split() if len(w) > 2]
        found: list[str] = []
        cursor = None
        for _ in range(4):  # the most recent 120 notes at most
            page = await self._granola("notes", page_size=30, **({"cursor": cursor} if cursor else {}))
            for note in page.get("notes") or []:
                summary = (note.get("summary") or {}).get("markdown") or note.get("summary_text") or ""
                haystack = f"{note.get('title', '')} {summary}".lower()
                if not words or all(w in haystack for w in words):
                    found.append(f"[{note.get('id', '')}] {str(note.get('created_at', ''))[:10]} | "
                                 f"{note.get('title') or '(untitled)'} | {_clip(summary, 200)}")
            cursor = page.get("cursor")
            if len(found) >= limit or not page.get("hasMore") or not cursor:
                break
        return ("\n".join(found[:limit]) if found else f"No meeting note matches {query!r}."), False

    async def _meeting_read(self, id: str) -> tuple[str, bool]:  # noqa: A002 - the tool's argument name
        note = await self._granola(f"notes/{id}", include="transcript")
        attendees = ", ".join(a.get("name") or a.get("email") or "" for a in note.get("attendees") or [] if a)
        summary = (note.get("summary") or {}).get("markdown") or ""
        turns = []
        for turn in note.get("transcript") or []:
            speaker = turn.get("speaker")
            speaker = speaker.get("source", "") if isinstance(speaker, dict) else (speaker or "")
            turns.append(f"{speaker}: {turn.get('text', '')}")
        lines = [
            f"{note.get('title') or '(untitled)'} ({str(note.get('created_at', ''))[:16]})",
            f"Attendees: {attendees or 'not listed'}", "Summary:", summary, "Transcript:", *turns,
        ]
        return "\n".join(lines)[:_MAX_BODY], False

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
                lines.append(f"{_graph_local(e.get('start') or {})} | {e.get('subject', '')} | "
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
            # Graph wants a Windows or IANA zone name. str(tzinfo) gave "UTC+05:30" for a start with an
            # offset and "IST" on Linux, neither of which Graph knows; the same instant in UTC always works.
            def utc(moment: dt.datetime) -> str:
                return moment.astimezone(dt.UTC).replace(tzinfo=None).isoformat()

            made = await _post("https://graph.microsoft.com/v1.0/me/events", provider, {
                "subject": title, "body": {"contentType": "Text", "content": notes},
                "start": {"dateTime": utc(begin), "timeZone": "UTC"},
                "end": {"dateTime": utc(finish), "timeZone": "UTC"}})
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


    # ---- more sources ----

    async def _news(self, source: str = "headlines", limit: int = 5) -> tuple[str, bool]:
        import httpx

        if source == "hackernews":
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                ids = (await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")).json()[:limit]
                items = await asyncio.gather(*(client.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json") for i in ids))
            lines = []
            for r in items:
                item = r.json() or {}
                lines.append(f"{item.get('title', '')} ({item.get('score', 0)} points) - "
                             f"{item.get('url') or 'https://news.ycombinator.com/item?id=' + str(item.get('id'))}")
            return "\n".join(lines) or "Hacker News did not answer.", not lines
        from Agent_Guru.platform.features.briefing import _get_news_headlines

        feeds = [u.strip() for u in os.environ.get("NEWS_FEEDS", "").split(",") if u.strip()] or [
            "https://feeds.bbci.co.uk/news/rss.xml"]
        per_feed = max(1, limit // len(feeds))
        lists = await asyncio.gather(*(_get_news_headlines(per_feed, url, with_links=True) for url in feeds))
        lines = [line for items in lists for line in items][:limit]
        return ("\n".join(lines) if lines else "No headlines: the feeds did not answer."), not lines

    async def _drive_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        safe = query.replace("\\", "").replace("'", "\\'")
        found = await _get("https://www.googleapis.com/drive/v3/files", "google",
                           q=f"(name contains '{safe}' or fullText contains '{safe}') and trashed = false",
                           pageSize=limit, fields="files(id,name,mimeType,modifiedTime,webViewLink)")
        lines = [f"{f.get('name')} | {f.get('modifiedTime', '')[:10]} | {f.get('webViewLink', '')}" for f in found.get("files") or []]
        return ("\n".join(lines) if lines else f"Nothing in Drive matches {query!r}."), False

    async def _tasks_list(self) -> tuple[str, bool]:
        found = await _get("https://tasks.googleapis.com/tasks/v1/lists/@default/tasks", "google",
                           showCompleted="false", maxResults=50)
        lines = [f"{t.get('title', '')}" + (f" (due {t['due'][:10]})" if t.get("due") else "") for t in found.get("items") or []]
        return ("\n".join(lines) if lines else "No open tasks."), False

    async def _task_add(self, title: str, due: str = "", notes: str = "") -> tuple[Any, ...]:
        body: dict[str, Any] = {"title": title, "notes": notes}
        if due:
            body["due"] = f"{due}T00:00:00.000Z"
        made = await _post("https://tasks.googleapis.com/tasks/v1/lists/@default/tasks", "google", body)
        return f"Added the task {title!r}.", False, bool(made.get("id"))

    async def _notion_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post("https://api.notion.com/v1/search", json={"query": query, "page_size": limit},
                                         headers={"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                                                  "Notion-Version": "2022-06-28"})
        response.raise_for_status()
        lines = []
        for r in response.json().get("results") or []:
            title = ""
            for prop in (r.get("properties") or {}).values():
                if prop.get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in prop.get("title") or [])
            lines.append(f"{title or '(untitled)'} | {r.get('last_edited_time', '')[:10]} | {r.get('url', '')}")
        return ("\n".join(lines) if lines else f"Nothing in Notion matches {query!r}."), False

    async def _notes_search(self, query: str, limit: int = 8) -> tuple[str, bool]:
        found = await asyncio.to_thread(_search_vault, Path(os.environ["OBSIDIAN_VAULT"]).expanduser(), query, limit)
        return ("\n".join(found) if found else f"No note mentions {query!r}."), False

    async def _github(self) -> tuple[str, bool]:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get("https://api.github.com/notifications",
                                        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                                 "Accept": "application/vnd.github+json"})
        response.raise_for_status()
        lines = [f"{n['repository']['full_name']} | {n['subject']['type']} | {n['subject']['title']} | {n.get('reason', '')}"
                 for n in response.json()[:20]]
        return ("\n".join(lines) if lines else "No unread GitHub notifications."), False

    async def _dropbox_search(self, query: str, limit: int = 5) -> tuple[str, bool]:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post("https://api.dropboxapi.com/2/files/search_v2",
                                         json={"query": query, "options": {"max_results": limit}},
                                         headers={"Authorization": f"Bearer {os.environ['DROPBOX_TOKEN']}"})
        response.raise_for_status()
        lines = [((m.get("metadata") or {}).get("metadata") or {}).get("path_display", "") for m in response.json().get("matches") or []]
        lines = [line for line in lines if line]
        return ("\n".join(lines) if lines else f"Nothing in Dropbox matches {query!r}."), False

    async def _health(self, days: int = 7) -> tuple[str, bool]:
        import httpx

        start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        headers = {"Authorization": f"Bearer {os.environ['OURA_TOKEN']}"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            answers = [await client.get(f"https://api.ouraring.com/v2/usercollection/{kind}", params={"start_date": start},
                                        headers=headers) for kind in ("daily_sleep", "daily_activity")]
        # An expired token used to read as "No Oura data for those days": Oura's 401 body has no "data".
        for answer in answers:
            answer.raise_for_status()
        sleep, active = (answer.json() for answer in answers)
        by_day: dict[str, list[str]] = {}
        for d in sleep.get("data") or []:
            by_day.setdefault(d.get("day", ""), []).append(f"sleep {d.get('score')}")
        for d in active.get("data") or []:
            by_day.setdefault(d.get("day", ""), []).append(f"activity {d.get('score')}, {d.get('steps', 0)} steps")
        lines = [f"{day}: {', '.join(v)}" for day, v in sorted(by_day.items())]
        return ("\n".join(lines) if lines else "No Oura data for those days."), False

    async def _strava(self, limit: int = 5) -> tuple[str, bool]:
        found = await _get("https://www.strava.com/api/v3/athlete/activities", "strava", per_page=limit)
        lines = [f"{a.get('start_date_local', '')[:10]} | {a.get('sport_type') or a.get('type')} | {a.get('name', '')} | "
                 f"{(a.get('distance') or 0) / 1000:.1f} km | {int(a.get('moving_time') or 0) // 60} min" for a in found or []]
        return ("\n".join(lines) if lines else "No Strava activities."), False

    async def _music_now(self) -> tuple[str, bool]:
        import httpx

        from Agent_Guru.connectors.oauth import access_token

        token = await asyncio.to_thread(access_token, "spotify")
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get("https://api.spotify.com/v1/me/player/currently-playing",
                                        headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 204 or not response.content:
            return "Nothing is playing on Spotify.", False
        # A refused token used to come back as the song "? by ", a success the model read out.
        response.raise_for_status()
        item = response.json().get("item") or {}
        artists = ", ".join(a.get("name", "") for a in item.get("artists") or [])
        return f"{item.get('name', '?')} by {artists}", False

    async def _music_control(self, action: str, query: str = "") -> tuple[Any, ...]:
        import httpx

        from Agent_Guru.connectors.oauth import access_token

        token = await asyncio.to_thread(access_token, "spotify")
        headers = {"Authorization": f"Bearer {token}"}
        base = "https://api.spotify.com/v1/me/player"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            body: dict[str, Any] | None = None
            if action == "play" and query:
                search = await client.get("https://api.spotify.com/v1/search", params={"q": query, "type": "track", "limit": 1},
                                          headers=headers)
                # A refused search is not "Spotify found nothing".
                search.raise_for_status()
                tracks = (search.json().get("tracks") or {}).get("items") or []
                if not tracks:
                    return f"Spotify found nothing for {query!r}.", True
                body = {"uris": [tracks[0]["uri"]]}
            method, path = {"play": ("PUT", "/play"), "pause": ("PUT", "/pause"),
                            "next": ("POST", "/next"), "previous": ("POST", "/previous")}[action]
            response = await client.request(method, base + path, headers=headers, json=body)
        if response.status_code in (200, 202, 204):
            return f"Spotify: {action}" + (f" {query}" if query else "") + ".", False, True
        # Every refusal used to say "open Spotify on a device first", also for a free account (403,
        # PREMIUM_REQUIRED) or an expired token (401), so the owner opened Spotify and it still failed.
        try:
            error = response.json().get("error") or {}
        except ValueError:
            error = {}
        if error.get("reason") == "NO_ACTIVE_DEVICE" or (response.status_code == 404 and not error.get("reason")):
            return f"Spotify refused ({response.status_code}): open Spotify on a device first.", True
        why = error.get("message") or response.reason_phrase
        return f"Spotify refused ({response.status_code}): {_clip(str(why), 160)}.", True


def _search_vault(vault: Path, query: str, limit: int) -> list[str]:
    from Agent_Guru.security.file_policy import sensitive_reason

    words = [w for w in re.split(r"\W+", query.lower()) if w]
    found: list[str] = []
    deadline = time.monotonic() + 5.0
    for path in vault.rglob("*.md"):
        if ".obsidian" in path.parts or ".trash" in path.parts or sensitive_reason(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        if all(w in low for w in words):
            line = next((ln.strip() for ln in text.splitlines() if words and words[0] in ln.lower()), "")
            found.append(f"{path.relative_to(vault)} | {_clip(line, 160)}")
            if len(found) >= limit or time.monotonic() > deadline:
                break
    return found


def _graph_local(when: dict[str, Any]) -> str:
    """A Graph {dateTime, timeZone} in the owner's local time.

    Graph gives event times in UTC unless asked otherwise, without an
    offset; they were shown as they came, so a 15:00 meeting in India
    was read out as 09:30.
    """
    raw = when.get("dateTime", "")
    if not raw or when.get("timeZone", "UTC") != "UTC":
        return raw
    try:
        moment = dt.datetime.fromisoformat(raw[:26])
    except ValueError:
        return raw
    return moment.replace(tzinfo=dt.UTC).astimezone().isoformat(timespec="minutes")


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
        # Inside an IMAP quoted string a backslash escapes the next character, so "Ramesh \" swallowed
        # the closing quote and the server answered BAD.
        # A CR or LF would end the command early and start another; only newer patch releases of imaplib
        # refuse them, so they are taken out here whatever Python the owner runs.
        safe = re.sub(r"[\x00\r\n]+", " ", query).replace('"', "").replace("\\", "")
        if safe.isascii():
            _, data = box.search(None, "OR", "SUBJECT", f'"{safe}"', "FROM", f'"{safe}"')
            found = (data[0] or b"").split()
        else:
            # imaplib sends commands as ASCII, so a search for "राहुल" raised UnicodeEncodeError before
            # reaching the server. RFC 3501 sends such a string as a UTF-8 literal; imaplib takes one
            # literal per command, so subject and sender are searched apart and joined.
            matched: set[bytes] = set()
            for field in ("SUBJECT", "FROM"):
                box.literal = safe.encode()
                _, data = box.search("UTF-8", field)
                matched.update((data[0] or b"").split())
            found = sorted(matched, key=int)
        ids = found[-limit:][::-1]
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
             for name in ("mail_search", "mail_read", "calendar_events", "contacts_search", "files_search", "news",
                          "drive_search", "tasks_list", "notion_search", "notes_search", "github_notifications",
                          "dropbox_search", "health_summary", "strava_activities", "music_now",
                          "slack_search", "meetings_search", "meeting_read")}
    rules["task_add"] = ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE)
    rules["music_control"] = ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE)
    rules["mail_send"] = ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)
    rules["calendar_add"] = ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=30.0, tools=rules)
