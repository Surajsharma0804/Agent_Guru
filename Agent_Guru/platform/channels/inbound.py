"""Talk to the assistant from a chat service: the owner's messages become typed turns.

The assistant could be asked something only at the computer, and then
from Telegram only. Each source here is read by polling, so no port is
opened and nothing on this machine becomes reachable from the network:

    telegram  AGENT_GURU_TELEGRAM_INBOUND, TELEGRAM_BOT_TOKEN,
              TELEGRAM_ALLOWED_CHATS (chat ids)
    slack     SLACK_BOT_TOKEN, SLACK_INBOUND_CHANNELS (channel or DM ids the bot is in),
              SLACK_ALLOWED_USERS (user ids)
    discord   DISCORD_BOT_TOKEN, DISCORD_INBOUND_CHANNELS (channel ids),
              DISCORD_ALLOWED_USERS (user ids); the bot needs the message content intent
    matrix    MATRIX_HOMESERVER, MATRIX_ACCESS_TOKEN, MATRIX_INBOUND_ROOMS (room ids),
              MATRIX_ALLOWED_USERS (@user:server)
    email     IMAP_HOST, IMAP_USER, IMAP_PASSWORD (read), SMTP_* (reply),
              EMAIL_ALLOWED_SENDERS (addresses); only mail the owner's mail server
              authenticated (DMARC, or DKIM of the From domain) counts, and
              EMAIL_AUTHSERV_ID (for example mx.google.com) names that server

AGENT_GURU_INBOUND names the sources to run (comma separated, for example
"telegram,matrix"); AGENT_GURU_TELEGRAM_INBOUND still turns Telegram on.

Only senders on a source's allow list are answered. A message from anyone
else is not read to the model: it is logged, published as message.in with
allowed=False, and dropped, and nothing is sent back (a reply would confirm
to a stranger that the assistant is live). An allowed message is the owner
typing: one typed turn, with the same policy and the same yes before a
change; the owner's next message answers the question. Turns from every
source run one at a time, and messages already there when the assistant
starts are skipped, so an old message is never acted on late.

To find ids: `python -m Agent_Guru telegram chats` lists who has written
to the Telegram bot.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import email
import email.policy
import logging
import os
import re
import time
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any

from Agent_Guru.platform.channels import TelegramChannel

logger = logging.getLogger(__name__)

_POLL_S = 25
_MAX_TEXT = 4000


@dataclass(slots=True)
class Incoming:
    """One message: where to answer (chat), who sent it (sender) and what it says."""

    chat: str
    sender: str
    text: str
    #: Whether the service vouched for the sender (email: DMARC or the From domain's DKIM passed).
    verified: bool = True


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _ids(name: str) -> set[str]:
    return {v.strip() for v in _env(name).split(",") if v.strip()}


class Source:
    """A chat service the owner can write to the assistant from."""

    name = ""
    #: Seconds between polls when a poll does not itself wait (Slack, Discord, email).
    interval = 5.0

    def problems(self) -> list[str]:
        """What is missing for this source to run; [] when it can."""
        raise NotImplementedError

    def allowed(self, message: Incoming) -> bool:
        raise NotImplementedError

    async def prime(self) -> None:
        """Note where the conversation is now, so messages already there are not answered."""

    async def fetch(self) -> list[Incoming]:
        raise NotImplementedError

    async def reply(self, chat: str, text: str) -> bool:
        raise NotImplementedError


class TelegramSource(Source):
    name = "telegram"
    interval = 0.0  # getUpdates waits by itself

    def __init__(self, channel: TelegramChannel | None = None) -> None:
        self.channel = channel or TelegramChannel()
        self.offset = 0

    def problems(self) -> list[str]:
        if not self.channel.configured():
            return ["TELEGRAM_BOT_TOKEN is not set"]
        return [] if allowed_chats() else ["TELEGRAM_ALLOWED_CHATS is empty: no chat would be answered"]

    def allowed(self, message: Incoming) -> bool:
        return message.chat in allowed_chats()

    async def prime(self) -> None:
        # It started at offset 0, so a message sent while the assistant was
        # off (hours earlier, "turn off the PC") was acted on at the next start.
        body = await self.channel.call("getUpdates", timeout=0)
        ids = [int(u.get("update_id", 0)) for u in body.get("result") or []]
        self.offset = max(ids) + 1 if ids else 0

    async def fetch(self) -> list[Incoming]:
        body = await self.channel.call("getUpdates", offset=self.offset, timeout=_POLL_S, allowed_updates=["message"])
        out = []
        for update in body.get("result") or []:
            self.offset = max(self.offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or {}
            chat = str((message.get("chat") or {}).get("id", ""))
            text = (message.get("text") or "").strip()
            if chat and text:
                out.append(Incoming(chat, chat, text))
        return out

    async def reply(self, chat: str, text: str) -> bool:
        delivery = await self.channel.send(chat, text)
        if not delivery.sent:
            logger.warning("Telegram reply not delivered: %s", delivery.error)
        return delivery.sent


class SlackSource(Source):
    """conversations.history on each listed channel; the bot's own messages are never read as the owner's."""

    name = "slack"

    def __init__(self) -> None:
        self.latest: dict[str, str] = {}

    def problems(self) -> list[str]:
        missing = [n for n in ("SLACK_BOT_TOKEN", "SLACK_INBOUND_CHANNELS", "SLACK_ALLOWED_USERS") if not _env(n)]
        return [f"{n} is not set" for n in missing]

    def allowed(self, message: Incoming) -> bool:
        return message.sender in _ids("SLACK_ALLOWED_USERS")

    async def _history(self, channel: str, oldest: str | None, limit: int) -> list[dict[str, Any]]:
        import httpx

        params: dict[str, Any] = {"channel": channel, "limit": limit}
        if oldest:
            params["oldest"] = oldest
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get("https://slack.com/api/conversations.history", params=params,
                                        headers={"Authorization": f"Bearer {_env('SLACK_BOT_TOKEN')}"})
        body = response.json()
        if not body.get("ok"):
            msg = f"Slack refused conversations.history: {body.get('error')}"
            raise RuntimeError(msg)
        return body.get("messages") or []

    async def prime(self) -> None:
        for channel in _ids("SLACK_INBOUND_CHANNELS"):
            newest = await self._history(channel, None, 1)
            self.latest[channel] = newest[0]["ts"] if newest else f"{time.time():.6f}"

    async def fetch(self) -> list[Incoming]:
        out = []
        for channel in sorted(_ids("SLACK_INBOUND_CHANNELS")):
            messages = await self._history(channel, self.latest.get(channel), 50)
            for m in sorted(messages, key=lambda m: float(m.get("ts", 0))):
                if float(m.get("ts", 0)) <= float(self.latest.get(channel, 0)):
                    continue
                self.latest[channel] = m["ts"]
                if m.get("bot_id") or m.get("subtype") or not (m.get("text") or "").strip():
                    continue
                out.append(Incoming(channel, str(m.get("user", "")), m["text"].strip()))
        return out

    async def reply(self, chat: str, text: str) -> bool:
        from Agent_Guru.platform.channels import CHANNELS

        delivery = await CHANNELS["slack"].send(chat, text)
        return delivery.sent


class DiscordSource(Source):
    name = "discord"
    api = "https://discord.com/api/v10"

    def __init__(self) -> None:
        self.after: dict[str, str] = {}

    def problems(self) -> list[str]:
        missing = [n for n in ("DISCORD_BOT_TOKEN", "DISCORD_INBOUND_CHANNELS", "DISCORD_ALLOWED_USERS") if not _env(n)]
        return [f"{n} is not set" for n in missing]

    def allowed(self, message: Incoming) -> bool:
        return message.sender in _ids("DISCORD_ALLOWED_USERS")

    async def _messages(self, channel: str, after: str | None, limit: int) -> list[dict[str, Any]]:
        import httpx

        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.api}/channels/{channel}/messages", params=params,
                                        headers={"Authorization": f"Bot {_env('DISCORD_BOT_TOKEN')}"})
        response.raise_for_status()
        return response.json()

    async def prime(self) -> None:
        for channel in _ids("DISCORD_INBOUND_CHANNELS"):
            newest = await self._messages(channel, None, 1)
            self.after[channel] = newest[0]["id"] if newest else "0"

    async def fetch(self) -> list[Incoming]:
        out = []
        for channel in sorted(_ids("DISCORD_INBOUND_CHANNELS")):
            # Snowflake ids grow with time: the largest is the newest.
            for m in sorted(await self._messages(channel, self.after.get(channel), 50), key=lambda m: int(m["id"])):
                self.after[channel] = m["id"]
                author = m.get("author") or {}
                if author.get("bot") or not (m.get("content") or "").strip():
                    continue
                out.append(Incoming(channel, str(author.get("id", "")), m["content"].strip()))
        return out

    async def reply(self, chat: str, text: str) -> bool:
        from Agent_Guru.platform.channels import CHANNELS

        return (await CHANNELS["discord"].send(chat, text)).sent


class MatrixSource(Source):
    """/sync long polling; a room's messages from allowed users, never the assistant's own."""

    name = "matrix"
    interval = 0.0

    def __init__(self) -> None:
        self.since: str | None = None
        self.me = ""

    def problems(self) -> list[str]:
        names = ("MATRIX_HOMESERVER", "MATRIX_ACCESS_TOKEN", "MATRIX_INBOUND_ROOMS", "MATRIX_ALLOWED_USERS")
        return [f"{n} is not set" for n in names if not _env(n)]

    def allowed(self, message: Incoming) -> bool:
        return message.sender in _ids("MATRIX_ALLOWED_USERS") and message.sender != self.me

    async def _get(self, path: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> Any:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{_env('MATRIX_HOMESERVER').rstrip('/')}/_matrix/client/v3/{path}",
                                        params=params, headers={"Authorization": f"Bearer {_env('MATRIX_ACCESS_TOKEN')}"})
        response.raise_for_status()
        return response.json()

    async def prime(self) -> None:
        self.me = (await self._get("account/whoami")).get("user_id", "")
        # A sync with no timeout and an empty timeline filter only finds where "now" is.
        body = await self._get("sync", {"filter": '{"room":{"timeline":{"limit":0}}}', "timeout": 0})
        self.since = body.get("next_batch")

    async def fetch(self) -> list[Incoming]:
        params: dict[str, Any] = {"timeout": _POLL_S * 1000}
        if self.since:
            params["since"] = self.since
        body = await self._get("sync", params, timeout=_POLL_S + 15)
        self.since = body.get("next_batch", self.since)
        rooms = _ids("MATRIX_INBOUND_ROOMS")
        out = []
        for room, data in ((body.get("rooms") or {}).get("join") or {}).items():
            if room not in rooms:
                continue
            for event in (data.get("timeline") or {}).get("events") or []:
                content = event.get("content") or {}
                if event.get("type") == "m.room.message" and content.get("msgtype") == "m.text" and content.get("body"):
                    out.append(Incoming(room, str(event.get("sender", "")), str(content["body"]).strip()))
        return out

    async def reply(self, chat: str, text: str) -> bool:
        from Agent_Guru.platform.channels import CHANNELS

        return (await CHANNELS["matrix"].send(chat, text)).sent


class EmailSource(Source):
    """Unseen mail in INBOX from allowed senders, marked read once answered; the reply goes by SMTP."""

    name = "email"
    interval = 30.0

    def __init__(self) -> None:
        self.first_uid = 0

    def problems(self) -> list[str]:
        names = ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD", "SMTP_HOST", "EMAIL_ALLOWED_SENDERS")
        return [f"{n} is not set" for n in names if not _env(n)]

    def allowed(self, message: Incoming) -> bool:
        return message.verified and message.sender.lower() in {s.lower() for s in _ids("EMAIL_ALLOWED_SENDERS")}

    @staticmethod
    def authenticated(message: Any, sender: str) -> bool:
        """Whether the owner's mail server vouched for *sender*: DMARC passed, or DKIM for its own domain.

        The From header is whatever the sender typed: a mail from a stranger
        with the owner's address in From was taken as the owner, and its
        "yes" could approve an action. Only the topmost Authentication-Results
        counts (the receiving server adds it last; a sender can add fake ones
        below it), and with EMAIL_AUTHSERV_ID set it must be that server's.
        """
        results = message.get_all("Authentication-Results") or []
        if not results:
            return False
        top = " ".join(str(results[0]).split()).lower()
        server = _env("EMAIL_AUTHSERV_ID").lower()
        if server and not top.startswith(server):
            return False
        if re.search(r"\bdmarc=pass\b", top):
            return True
        domain = sender.rpartition("@")[2].lower()
        return bool(domain) and bool(re.search(
            rf"\bdkim=pass\b[^;]*\bheader\.(?:d={re.escape(domain)}\b|i=[^\s;]*@{re.escape(domain)}\b)", top))

    def _box(self) -> Any:
        import imaplib

        box = imaplib.IMAP4_SSL(_env("IMAP_HOST"), int(_env("IMAP_PORT") or 993), timeout=15)
        box.login(_env("IMAP_USER"), _env("IMAP_PASSWORD"))
        box.select("INBOX")
        return box

    def _prime_sync(self) -> None:
        box = self._box()
        try:
            _, data = box.uid("search", None, "ALL")
            uids = [int(u) for u in (data[0] or b"").split()]
            self.first_uid = (max(uids) + 1) if uids else 1
        finally:
            box.logout()

    async def prime(self) -> None:
        await asyncio.to_thread(self._prime_sync)

    def _fetch_sync(self) -> list[Incoming]:
        box = self._box()
        out = []
        try:
            _, data = box.uid("search", None, f"UID {self.first_uid}:* UNSEEN")
            for uid in (data[0] or b"").split():
                if int(uid) < self.first_uid:
                    continue
                _, parts = box.uid("fetch", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), b"")
                message = email.message_from_bytes(raw, policy=email.policy.default)
                sender = parseaddr(str(message.get("From", "")))[1]
                body = message.get_body(preferencelist=("plain",))
                text = body.get_content() if body is not None else ""
                # Only the new text: quoted earlier mail starts at "On ... wrote:" or ">".
                text = re.split(r"\n(?:On .{0,200}wrote:|>)", text, maxsplit=1)[0].strip()
                subject = str(message.get("Subject", "")).strip()
                if text or subject:
                    out.append(Incoming(sender, sender, text or subject, verified=self.authenticated(message, sender)))
                box.uid("store", uid, "+FLAGS", "(\\Seen)")
        finally:
            box.logout()
        return out

    async def fetch(self) -> list[Incoming]:
        return await asyncio.to_thread(self._fetch_sync)

    async def reply(self, chat: str, text: str) -> bool:
        from Agent_Guru.platform.channels import CHANNELS

        return (await CHANNELS["email"].send(chat, text)).sent


SOURCES: dict[str, type[Source]] = {s.name: s for s in (TelegramSource, SlackSource, DiscordSource, MatrixSource, EmailSource)}


def enabled() -> bool:
    return bool(enabled_sources())


def enabled_sources() -> list[str]:
    names = {n.strip().lower() for n in _env("AGENT_GURU_INBOUND").split(",") if n.strip()}
    if _env("AGENT_GURU_TELEGRAM_INBOUND").lower() in {"1", "true", "yes", "on"}:
        names.add("telegram")
    return sorted(n for n in names if n in SOURCES)


def allowed_chats() -> set[str]:
    return _ids("TELEGRAM_ALLOWED_CHATS")


async def serve(source: Source, orchestrator: Any, stop: asyncio.Event, lock: asyncio.Lock | None = None) -> None:
    """Answer the source's allowed senders until *stop* is set. Never raises; errors back off and retry."""
    problems = source.problems()
    if problems:
        logger.warning("%s inbound is on but cannot run: %s", source.name, "; ".join(problems))
        return
    lock = lock or asyncio.Lock()
    backoff = 1.0
    primed = False
    logger.info("%s inbound: answering the owner", source.name)
    while not stop.is_set():
        try:
            if not primed:
                await source.prime()
                primed = True
            messages = await source.fetch()
            backoff = 1.0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("%s poll failed (%s); retrying in %.0fs", source.name, exc, backoff)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), backoff)
            backoff = min(backoff * 2, 60.0)
            continue
        for message in messages:
            if not source.allowed(message):
                logger.warning("%s message from %s ignored: not on the allow list", source.name, message.sender)
                orchestrator.events.publish("message.in", channel=source.name, chat=message.chat, allowed=False)
                continue
            orchestrator.events.publish("message.in", channel=source.name, chat=message.chat, allowed=True,
                                        chars=len(message.text))
            async with lock:
                try:
                    result = await orchestrator.run_text_turn(message.text[:_MAX_TEXT])
                    reply = result.llm_response or (result.action_result if isinstance(result.action_result, str) else "")
                except Exception:
                    logger.exception("%s turn failed", source.name)
                    reply = "Sorry, something went wrong with that."
            try:
                if not await source.reply(message.chat, reply or "Done."):
                    logger.warning("%s reply not delivered", source.name)
            except Exception as exc:
                logger.warning("%s reply failed: %s", source.name, exc)
        if source.interval:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), source.interval)


async def poll(orchestrator: Any, stop: asyncio.Event, channel: TelegramChannel | None = None) -> None:
    """Run every enabled source until *stop* is set, one turn at a time across all of them."""
    lock = asyncio.Lock()
    names = enabled_sources()
    sources: list[Source] = [TelegramSource(channel) if n == "telegram" else SOURCES[n]() for n in names]
    if not sources:
        return
    await asyncio.gather(*(serve(s, orchestrator, stop, lock) for s in sources))


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru telegram", description="The Telegram bot.")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("chats", help="who has written to the bot recently, with their chat ids")
    args = parser.parse_args(argv)
    channel = TelegramChannel()
    if args.action == "chats":
        if not channel.configured():
            print("Set TELEGRAM_BOT_TOKEN in the environment or .env first.")  # noqa: T201  the command's output
            return 1
        body = asyncio.run(channel.call("getUpdates", timeout=0))
        seen: dict[str, str] = {}
        for update in body.get("result") or []:
            chat = (update.get("message") or {}).get("chat") or {}
            if chat.get("id") is not None:
                seen[str(chat["id"])] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
        for chat_id, who in seen.items():
            print(f"{chat_id:>15}  {who}")  # noqa: T201
        if not seen:
            print("No messages yet: send the bot a message, then run this again.")  # noqa: T201
        return 0
    on = enabled_sources()
    print(f"Inbound sources on: {', '.join(on) or 'none'} (AGENT_GURU_INBOUND)")  # noqa: T201
    for name, cls in SOURCES.items():
        problems = (TelegramSource(channel) if name == "telegram" else cls()).problems()
        print(f"  {name:9} {'ready' if not problems else '; '.join(problems)}")  # noqa: T201
    return 0
