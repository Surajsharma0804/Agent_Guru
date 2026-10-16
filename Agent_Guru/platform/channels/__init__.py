"""Messaging channels that deliver through a service's API: Telegram, Slack, email.

On the desktop, Telegram, Slack and email messages were only "prefilled":
the app opened with the text in it and the owner had to press send, so
"tell Rahul on Telegram I'm late" never reached Rahul unless someone was
at the keyboard. When the owner has configured a channel, the messaging
controller now delivers through it and reports "sent" only when the
service confirmed it; otherwise it falls back to prefilling as before.

Each channel reads its credentials from the environment (or .env), never
from settings.toml, which refuses secrets:

    Telegram  TELEGRAM_BOT_TOKEN          contacts: a chat id, or @username for a channel
    Slack     SLACK_BOT_TOKEN             contacts: a channel or user id (C..., U..., D...)
    Email     SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (STARTTLS, or SSL on 465)

The bot sends as itself; it does not send as the owner.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT_S = 15.0
_MAX_CHARS = 4000


@dataclass(slots=True)
class Delivery:
    """What a channel did: sent (the service confirmed it) or not, with an id or the reason."""

    sent: bool
    message_id: str = ""
    error: str = ""


class Channel:
    """One messaging service the assistant can send through."""

    name = ""

    def configured(self) -> bool:
        raise NotImplementedError

    def accepts(self, contact: str) -> bool:
        """Whether *contact* is an address this channel can send to as it is."""
        raise NotImplementedError

    async def send(self, contact: str, text: str) -> Delivery:
        raise NotImplementedError


class TelegramChannel(Channel):
    name = "telegram"
    api = "https://api.telegram.org"

    def _token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    def configured(self) -> bool:
        return bool(self._token())

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"-?\d{3,20}|@[A-Za-z][A-Za-z0-9_]{4,31}", contact.strip()))

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(f"{self.api}/bot{self._token()}/{method}", json=params)
        try:
            body = response.json()
        except ValueError:
            body = {"ok": False, "description": f"HTTP {response.status_code}"}
        return body

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            body = await self.call("sendMessage", chat_id=contact.strip(), text=text[:_MAX_CHARS])
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if body.get("ok"):
            return Delivery(True, message_id=str((body.get("result") or {}).get("message_id", "")))
        return Delivery(False, error=str(body.get("description") or "Telegram refused it")[:200])


class SlackChannel(Channel):
    name = "slack"

    def _token(self) -> str:
        return os.environ.get("SLACK_BOT_TOKEN", "").strip()

    def configured(self) -> bool:
        return bool(self._token())

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[CDGU][A-Z0-9]{6,15}|#[a-z0-9._-]{1,80}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._token()}"},
                    json={"channel": contact.strip().lstrip("#"), "text": text[:_MAX_CHARS]},
                )
            body = response.json()
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if body.get("ok"):
            return Delivery(True, message_id=str(body.get("ts", "")))
        return Delivery(False, error=str(body.get("error") or "Slack refused it")[:200])


class EmailChannel(Channel):
    name = "email"

    def _config(self) -> dict[str, str]:
        return {k: os.environ.get(f"SMTP_{k}", "").strip() for k in ("HOST", "PORT", "USER", "PASSWORD", "FROM")}

    def configured(self) -> bool:
        c = self._config()
        return bool(c["HOST"] and (c["FROM"] or c["USER"]))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact.strip()))

    def _send_sync(self, contact: str, subject: str, text: str) -> str:
        c = self._config()
        port = int(c["PORT"] or 587)
        message = EmailMessage()
        message["From"] = c["FROM"] or c["USER"]
        message["To"] = contact.strip()
        message["Subject"] = subject
        message.set_content(text)
        context = ssl.create_default_context()
        if port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(c["HOST"], port, timeout=_TIMEOUT_S, context=context)
        else:
            server = smtplib.SMTP(c["HOST"], port, timeout=_TIMEOUT_S)
        with server:
            if port != 465:
                server.starttls(context=context)
            if c["USER"]:
                server.login(c["USER"], c["PASSWORD"])
            refused = server.send_message(message)
        if refused:
            msg = f"the server refused {', '.join(refused)}"
            raise RuntimeError(msg)
        return message.get("Message-ID", "") or ""

    async def send(self, contact: str, text: str, subject: str = "") -> Delivery:
        subject = subject or (text.strip().splitlines()[0][:60] if text.strip() else "Message")
        try:
            message_id = await asyncio.wait_for(asyncio.to_thread(self._send_sync, contact, subject, text), _TIMEOUT_S + 5)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        return Delivery(True, message_id=message_id)


CHANNELS: dict[str, Channel] = {c.name: c for c in (TelegramChannel(), SlackChannel(), EmailChannel())}


def channel_for(app: str) -> Channel | None:
    """The configured API channel for *app*, or None (then the app is prefilled as before)."""
    channel = CHANNELS.get(app.strip().lower())
    return channel if channel is not None and channel.configured() else None
