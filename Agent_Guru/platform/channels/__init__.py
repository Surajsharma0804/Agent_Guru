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
import json
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
        # Named in full, not built from a prefix, so each setting can be found where it is read.
        names = {"HOST": "SMTP_HOST", "PORT": "SMTP_PORT", "USER": "SMTP_USER", "PASSWORD": "SMTP_PASSWORD", "FROM": "SMTP_FROM"}  # nosec B105 - variable names, not secrets
        return {k: os.environ.get(v, "").strip() for k, v in names.items()}

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


async def _post_json(url: str, body: dict[str, Any], headers: dict[str, str] | None = None,
                     auth: tuple[str, str] | None = None, form: bool = False,
                     raw: bytes | None = None) -> tuple[int, Any]:
    """POST *body* as JSON (or a form); *raw* sends those exact bytes instead, for a body that was signed."""
    import httpx

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        if raw is not None:
            response = await client.post(url, content=raw, headers={"Content-Type": "application/json", **(headers or {})},
                                         auth=auth)
        elif form:
            response = await client.post(url, data=body, headers=headers, auth=auth)
        else:
            response = await client.post(url, json=body, headers=headers, auth=auth)
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text[:300]
    return response.status_code, payload


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


class DiscordChannel(Channel):
    """A Discord bot (DISCORD_BOT_TOKEN): a channel id, or a user id for a direct message."""

    name = "discord"
    api = "https://discord.com/api/v10"

    def configured(self) -> bool:
        return bool(_env("DISCORD_BOT_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"(user:)?\d{15,22}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        headers = {"Authorization": f"Bot {_env('DISCORD_BOT_TOKEN')}"}
        target = contact.strip()
        try:
            if target.startswith("user:"):
                code, body = await _post_json(f"{self.api}/users/@me/channels", {"recipient_id": target[5:]}, headers)
                if code >= 300:
                    return Delivery(False, error=f"could not open a direct message: {body}"[:200])
                target = body["id"]
            code, body = await _post_json(f"{self.api}/channels/{target}/messages", {"content": text[:2000]}, headers)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300 and isinstance(body, dict) and body.get("id"):
            return Delivery(True, message_id=str(body["id"]))
        return Delivery(False, error=f"Discord answered {code}: {body}"[:200])


class SignalChannel(Channel):
    """Signal through a signal-cli REST server the owner runs (SIGNAL_API_URL, SIGNAL_NUMBER)."""

    name = "signal"

    def configured(self) -> bool:
        return bool(_env("SIGNAL_API_URL") and _env("SIGNAL_NUMBER"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"\+\d{7,15}|group\.[A-Za-z0-9+/=]{10,}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            code, body = await _post_json(f"{_env('SIGNAL_API_URL').rstrip('/')}/v2/send", {
                "message": text[:_MAX_CHARS], "number": _env("SIGNAL_NUMBER"), "recipients": [contact.strip()]})
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300:
            return Delivery(True, message_id=str((body or {}).get("timestamp", "")) if isinstance(body, dict) else "")
        return Delivery(False, error=f"Signal answered {code}: {body}"[:200])


class TwilioSmsChannel(Channel):
    """SMS through Twilio (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM)."""

    name = "sms"

    def configured(self) -> bool:
        return bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and _env("TWILIO_FROM"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"\+\d{7,15}", contact.strip().replace(" ", "")))

    async def send(self, contact: str, text: str) -> Delivery:
        sid = _env("TWILIO_ACCOUNT_SID")
        try:
            code, body = await _post_json(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                {"To": contact.strip().replace(" ", ""), "From": _env("TWILIO_FROM"), "Body": text[:1600]},
                auth=(sid, _env("TWILIO_AUTH_TOKEN")), form=True)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300 and isinstance(body, dict) and body.get("sid"):
            return Delivery(True, message_id=body["sid"])
        return Delivery(False, error=f"Twilio answered {code}: {body}"[:200])


class MatrixChannel(Channel):
    """Matrix (MATRIX_HOMESERVER, MATRIX_ACCESS_TOKEN): a room id like !abc:example.org."""

    name = "matrix"

    def configured(self) -> bool:
        return bool(_env("MATRIX_HOMESERVER") and _env("MATRIX_ACCESS_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"![A-Za-z0-9]+:[A-Za-z0-9.\-]+", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        import secrets as _secrets
        import urllib.parse

        import httpx

        url = (f"{_env('MATRIX_HOMESERVER').rstrip('/')}/_matrix/client/v3/rooms/"
               f"{urllib.parse.quote(contact.strip(), safe='')}/send/m.room.message/{_secrets.token_hex(8)}")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                response = await client.put(url, json={"msgtype": "m.text", "body": text[:_MAX_CHARS]},
                                            headers={"Authorization": f"Bearer {_env('MATRIX_ACCESS_TOKEN')}"})
            body = response.json()
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if response.status_code < 300 and body.get("event_id"):
            return Delivery(True, message_id=body["event_id"])
        return Delivery(False, error=f"Matrix answered {response.status_code}: {body}"[:200])


class ZulipChannel(Channel):
    """Zulip (ZULIP_SITE, ZULIP_EMAIL, ZULIP_API_KEY): a user's email, or stream:NAME/TOPIC."""

    name = "zulip"

    def configured(self) -> bool:
        return bool(_env("ZULIP_SITE") and _env("ZULIP_EMAIL") and _env("ZULIP_API_KEY"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+|stream:[^/]+/.+", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        target = contact.strip()
        if target.startswith("stream:"):
            stream, _, topic = target[7:].partition("/")
            body = {"type": "stream", "to": stream, "topic": topic, "content": text[:_MAX_CHARS]}
        else:
            body = {"type": "private", "to": json.dumps([target]), "content": text[:_MAX_CHARS]}
        try:
            code, answer = await _post_json(f"{_env('ZULIP_SITE').rstrip('/')}/api/v1/messages", body,
                                            auth=(_env("ZULIP_EMAIL"), _env("ZULIP_API_KEY")), form=True)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300 and isinstance(answer, dict) and answer.get("result") == "success":
            return Delivery(True, message_id=str(answer.get("id", "")))
        return Delivery(False, error=f"Zulip answered {code}: {answer}"[:200])


class WebhookChannel(Channel):
    """Incoming webhooks: Teams, Google Chat, Mattermost, Rocket.Chat, Feishu, or any URL that takes JSON.

    The owner names each hook in the environment, WEBHOOK_<NAME>_URL
    (WEBHOOK_FAMILY_URL, WEBHOOK_TEAM_URL); the contact is that name.
    The JSON shape follows the URL: Teams and Feishu want their own
    fields, the rest take {"text": ...}. A generic hook gets the message
    signed with WEBHOOK_SECRET (HMAC-SHA256 in X-Signature) when it is set.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def _url(self, contact: str) -> str:
        key = re.sub(r"[^A-Za-z0-9]", "_", contact.strip()).upper()
        return _env(f"WEBHOOK_{key}_URL")

    def configured(self) -> bool:
        return any(k.startswith("WEBHOOK_") and k.endswith("_URL") and v.strip() for k, v in os.environ.items())

    def accepts(self, contact: str) -> bool:
        return bool(self._url(contact))

    async def send(self, contact: str, text: str) -> Delivery:
        import hashlib
        import hmac

        url = self._url(contact)
        if "office.com" in url or "logic.azure.com" in url or self.name == "teams":
            body: dict[str, Any] = {"type": "message", "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {"type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "text": text, "wrap": True}]}}]}
        elif "feishu" in url or "larksuite" in url:
            body = {"msg_type": "text", "content": {"text": text}}
        else:
            body = {"text": text[:_MAX_CHARS]}
        # The signature is over the bytes sent. It used to be over json.dumps(body) while httpx sent its own
        # compact UTF-8 encoding of the same body, so the two never matched and a receiver that checks
        # X-Signature refused every message, signed or not, with nothing wrong on the owner's side.
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {}
        secret = _env("WEBHOOK_SECRET")
        if secret:
            headers["X-Signature"] = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        try:
            code, answer = await _post_json(url, body, headers, raw=raw)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300:
            return Delivery(True)
        return Delivery(False, error=f"the webhook answered {code}: {answer}"[:200])


class MastodonChannel(Channel):
    """Mastodon (MASTODON_URL, MASTODON_TOKEN): "public" posts on the owner's timeline, @user@server sends a direct message."""

    name = "mastodon"

    def configured(self) -> bool:
        return bool(_env("MASTODON_URL") and _env("MASTODON_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return contact.strip() == "public" or bool(re.fullmatch(r"@[\w.]+(@[\w.\-]+)?", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        target = contact.strip()
        status = text[:480] if target == "public" else f"{target} {text}"[:480]
        body = {"status": status, "visibility": "public" if target == "public" else "direct"}
        try:
            code, answer = await _post_json(f"{_env('MASTODON_URL').rstrip('/')}/api/v1/statuses", body,
                                            {"Authorization": f"Bearer {_env('MASTODON_TOKEN')}"})
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300 and isinstance(answer, dict) and answer.get("id"):
            return Delivery(True, message_id=str(answer["id"]))
        return Delivery(False, error=f"Mastodon answered {code}: {answer}"[:200])


class LineChannel(Channel):
    """LINE Messaging API (LINE_CHANNEL_TOKEN): a user, group or room id."""

    name = "line"

    def configured(self) -> bool:
        return bool(_env("LINE_CHANNEL_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[UCR][0-9a-f]{32}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            code, answer = await _post_json("https://api.line.me/v2/bot/message/push",
                                            {"to": contact.strip(), "messages": [{"type": "text", "text": text[:5000]}]},
                                            {"Authorization": f"Bearer {_env('LINE_CHANNEL_TOKEN')}"})
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300:
            return Delivery(True)
        return Delivery(False, error=f"LINE answered {code}: {answer}"[:200])


class ViberChannel(Channel):
    """A Viber bot (VIBER_TOKEN): the receiver's Viber user id."""

    name = "viber"

    def configured(self) -> bool:
        return bool(_env("VIBER_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9+/=]{16,}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            code, answer = await _post_json("https://chatapi.viber.com/pa/send_message", {
                "receiver": contact.strip(), "type": "text", "text": text[:7000], "sender": {"name": "Agent Guru"}},
                {"X-Viber-Auth-Token": _env("VIBER_TOKEN")})
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if code < 300 and isinstance(answer, dict) and answer.get("status") == 0:
            return Delivery(True, message_id=str(answer.get("message_token", "")))
        return Delivery(False, error=f"Viber answered {code}: {answer}"[:200])


class MessengerChannel(Channel):
    """Facebook Messenger through a page (MESSENGER_PAGE_TOKEN): the person's page-scoped id."""

    name = "messenger"

    def configured(self) -> bool:
        return bool(_env("MESSENGER_PAGE_TOKEN"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"\d{10,20}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            code, answer = await _post_json(
                f"https://graph.facebook.com/v19.0/me/messages?access_token={_env('MESSENGER_PAGE_TOKEN')}",
                {"recipient": {"id": contact.strip()}, "messaging_type": "MESSAGE_TAG", "tag": "ACCOUNT_UPDATE",
                 "message": {"text": text[:2000]}})
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}"[:200])
        if code < 300 and isinstance(answer, dict) and answer.get("message_id"):
            return Delivery(True, message_id=answer["message_id"])
        return Delivery(False, error=f"Messenger answered {code}: {answer}"[:200])


class RedditChannel(Channel):
    """Reddit private messages through a script app (REDDIT_CLIENT_ID, _SECRET, _USERNAME, _PASSWORD): u/name."""

    name = "reddit"

    def configured(self) -> bool:
        return all(_env(f"REDDIT_{k}") for k in ("CLIENT_ID", "CLIENT_SECRET", "USERNAME", "PASSWORD"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"(u/)?[A-Za-z0-9_\-]{3,20}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        agent = {"User-Agent": "AgentGuru/1.0 (personal assistant)"}
        try:
            code, token = await _post_json("https://www.reddit.com/api/v1/access_token", {
                "grant_type": "password", "username": _env("REDDIT_USERNAME"), "password": _env("REDDIT_PASSWORD")},
                agent, auth=(_env("REDDIT_CLIENT_ID"), _env("REDDIT_CLIENT_SECRET")), form=True)
            if code >= 300 or not isinstance(token, dict) or "access_token" not in token:
                return Delivery(False, error=f"Reddit sign-in failed ({code})")
            code, answer = await _post_json("https://oauth.reddit.com/api/compose", {
                "to": contact.strip().removeprefix("u/"), "subject": text.split("\n", 1)[0][:100] or "Message",
                "text": text[:10000], "api_type": "json"},
                {**agent, "Authorization": f"Bearer {token['access_token']}"}, form=True)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        errors = ((answer or {}).get("json") or {}).get("errors") if isinstance(answer, dict) else None
        if code < 300 and not errors:
            return Delivery(True)
        return Delivery(False, error=f"Reddit answered {code}: {errors or answer}"[:200])


class IrcChannel(Channel):
    """IRC over TLS (IRC_SERVER host:port, IRC_NICK, IRC_PASSWORD optional): #channel or nick.

    Twitch chat is IRC too: IRC_SERVER irc.chat.twitch.tv:6697 with an
    oauth: token as IRC_PASSWORD. Each message is one connection: join,
    say it, quit; the assistant keeps no idle socket open.

    IRC acknowledges nothing it accepts, only what it refuses, so after the
    message the server is pinged: it answers in order, and a refusal (no
    such nick, cannot send to channel, banned) arrives before the pong.
    """

    # Replies that mean the JOIN or the PRIVMSG did not reach anyone.
    _REFUSED = {"401", "403", "404", "405", "407", "411", "412", "442", "471", "473", "474", "475", "477", "489"}

    def __init__(self, name: str = "irc", prefix: str = "IRC") -> None:
        self.name, self._p = name, prefix

    def configured(self) -> bool:
        return bool(_env(f"{self._p}_SERVER") and _env(f"{self._p}_NICK"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"#?[A-Za-z0-9_\-\[\]\\`^{}|]{1,50}", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        import asyncio

        import secrets

        host, _, port = _env(f"{self._p}_SERVER").partition(":")
        target = contact.strip()
        lines = [line for line in text.replace("\r", "").split("\n") if line.strip()][:5]
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port or 6697), ssl=ssl.create_default_context()), _TIMEOUT_S)
            nick = _env(f"{self._p}_NICK")
            if _env(f"{self._p}_PASSWORD"):
                writer.write(f"PASS {_env(self._p + '_PASSWORD')}\r\n".encode())
            writer.write(f"NICK {nick}\r\nUSER {nick} 0 * :Agent Guru\r\n".encode())
            await writer.drain()
            deadline = asyncio.get_running_loop().time() + _TIMEOUT_S

            async def reply() -> tuple[str, str]:
                """The next line from the server and its command or numeric; PINGs are answered on the way."""
                while True:
                    left = max(0.1, deadline - asyncio.get_running_loop().time())
                    line = (await asyncio.wait_for(reader.readline(), left)).decode(errors="replace")
                    if not line:
                        raise ConnectionError("the IRC server closed the connection")
                    parts = line.split()
                    command = parts[1] if len(parts) > 1 and parts[0].startswith(":") else (parts[0] if parts else "")
                    if command == "PING":
                        # A server may send its PING with a :prefix; the token after PING is echoed back.
                        writer.write(("PONG" + line.rstrip("\r\n").split("PING", 1)[1] + "\r\n").encode())
                        continue
                    return line.strip(), command

            # Wait for the welcome (001) before speaking.
            while True:
                line, command = await reply()
                if command == "001":
                    break
                if command in ("432", "433", "464", "465"):
                    return Delivery(False, error=line[:200])
            if target.startswith("#"):
                writer.write(f"JOIN {target}\r\n".encode())
            for line in lines:
                writer.write(f"PRIVMSG {target} :{line[:400]}\r\n".encode())
            # It used to report "sent" here, so a message to a nick that was not online, or to a channel
            # the bot was banned from, read as delivered while the server had answered 401 or 404.
            token = f"agentguru-{secrets.token_hex(4)}"
            writer.write(f"PING :{token}\r\n".encode())
            await writer.drain()
            while True:
                line, command = await reply()
                if command in self._REFUSED:
                    return Delivery(False, error=line[:200])
                if command == "PONG" and token in line:
                    break
            writer.write(b"QUIT :bye\r\n")
            await writer.drain()
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        finally:
            # Every early return used to leave the TLS socket open until the server timed it out.
            if writer is not None:
                writer.close()
        return Delivery(True)


def oauth1_header(method: str, url: str, query: dict[str, str], keys: dict[str, str],
                  nonce: str, timestamp: str) -> str:
    """The OAuth 1.0a (HMAC-SHA1) Authorization header X's user-context API requires.

    *query* holds the URL's query and any form fields; a JSON body is not
    signed. Checked against the worked example in X's documentation.
    """
    import base64
    import hashlib
    import hmac
    import urllib.parse

    def enc(value: str) -> str:
        return urllib.parse.quote(value, safe="-._~")

    oauth = {"oauth_consumer_key": keys["consumer_key"], "oauth_nonce": nonce,
             "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": timestamp,
             "oauth_token": keys["token"], "oauth_version": "1.0"}
    pairs = sorted((enc(k), enc(v)) for k, v in {**query, **oauth}.items())
    base = "&".join([method.upper(), enc(url), enc("&".join(f"{k}={v}" for k, v in pairs))])
    key = f"{enc(keys['consumer_secret'])}&{enc(keys['token_secret'])}"
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(oauth.items()))


class XChannel(Channel):
    """X (formerly Twitter), with the owner's app keys (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET).

    "public" posts on the owner's timeline; @name sends a direct message,
    which X allows only where that account accepts messages from the owner.
    """

    name = "x"
    api = "https://api.x.com/2"

    def _keys(self) -> dict[str, str]:
        return {"consumer_key": _env("X_API_KEY"), "consumer_secret": _env("X_API_SECRET"),
                "token": _env("X_ACCESS_TOKEN"), "token_secret": _env("X_ACCESS_SECRET")}

    def configured(self) -> bool:
        return all(self._keys().values())

    def accepts(self, contact: str) -> bool:
        return contact.strip() == "public" or bool(re.fullmatch(r"@?[A-Za-z0-9_]{1,15}", contact.strip()))

    def _auth(self, method: str, url: str) -> dict[str, str]:
        import secrets
        import time

        return {"Authorization": oauth1_header(method, url, {}, self._keys(), secrets.token_hex(16), str(int(time.time())))}

    async def send(self, contact: str, text: str) -> Delivery:
        import httpx

        target = contact.strip()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                if target == "public":
                    url = f"{self.api}/tweets"
                    response = await client.post(url, json={"text": text[:280]}, headers=self._auth("POST", url))
                    data = response.json().get("data") or {}
                    sent_id = data.get("id", "")
                else:
                    who = f"{self.api}/users/by/username/{target.lstrip('@')}"
                    found = await client.get(who, headers=self._auth("GET", who))
                    user = (found.json().get("data") or {}).get("id")
                    if found.status_code >= 300 or not user:
                        return Delivery(False, error=f"X has no account {target} ({found.status_code})")
                    url = f"{self.api}/dm_conversations/with/{user}/messages"
                    response = await client.post(url, json={"text": text[:10000]}, headers=self._auth("POST", url))
                    sent_id = (response.json().get("data") or {}).get("dm_event_id", "")
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        if response.status_code < 300 and sent_id:
            return Delivery(True, message_id=str(sent_id))
        return Delivery(False, error=f"X answered {response.status_code}: {response.text[:200]}")


class XmppChannel(Channel):
    """XMPP (Jabber) as XMPP_JID with XMPP_PASSWORD; XMPP_SERVER host:port if not the JID's domain on 5222.

    STARTTLS is required before the password is sent (SASL PLAIN only over
    TLS); XMPP_CA_FILE trusts a server certificate the system does not.
    XMPP has no delivery receipt a server must give, so after the message
    the server is pinged: it handles a stream in order, so a message it
    refused comes back as an error before the pong, and "sent" means the
    server took it. One connection per message, closed after.
    """

    name = "xmpp"

    def configured(self) -> bool:
        return bool(re.fullmatch(r"[^@\s/]+@[^@\s/]+", _env("XMPP_JID")) and _env("XMPP_PASSWORD"))

    def accepts(self, contact: str) -> bool:
        return bool(re.fullmatch(r"[^@\s/<>&'\"]+@[^@\s/<>&'\"]+", contact.strip()))

    async def send(self, contact: str, text: str) -> Delivery:
        try:
            return await asyncio.wait_for(self._send(contact.strip(), text), _TIMEOUT_S * 2)
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])

    async def _send(self, contact: str, text: str) -> Delivery:
        import base64
        from xml.sax.saxutils import escape  # nosec B406 - escapes outgoing text; nothing is parsed with it

        user, domain = _env("XMPP_JID").split("@", 1)
        host, _, port = (_env("XMPP_SERVER") or domain).partition(":")
        reader, writer = await asyncio.open_connection(host, int(port or 5222))
        buffer = b""

        async def until(*patterns: bytes) -> bytes:
            nonlocal buffer
            while True:
                for pattern in patterns:
                    found = re.search(pattern, buffer, re.DOTALL)
                    if found:
                        buffer = buffer[found.end():]
                        return found.group(0)
                chunk = await reader.read(65536)
                if not chunk:
                    msg = "the XMPP server closed the connection"
                    raise ConnectionError(msg)
                buffer += chunk

        def open_stream() -> None:
            writer.write((f"<?xml version='1.0'?><stream:stream to='{escape(domain)}' xmlns='jabber:client' "
                          "xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>").encode())

        try:
            open_stream()
            features = await until(rb"<stream:features.*?</stream:features>")
            if b"urn:ietf:params:xml:ns:xmpp-tls" not in features:
                return Delivery(False, error="the XMPP server does not offer TLS; the password is not sent")
            writer.write(b"<starttls xmlns='urn:ietf:params:xml:ns:xmpp-tls'/>")
            if b"<failure" in await until(rb"<proceed[^>]*/>", rb"<failure[^>]*/?>"):
                return Delivery(False, error="the XMPP server refused STARTTLS")
            context = ssl.create_default_context(cafile=_env("XMPP_CA_FILE") or None)
            await writer.start_tls(context, server_hostname=domain)
            buffer = b""
            open_stream()
            features = await until(rb"<stream:features.*?</stream:features>")
            if b">PLAIN<" not in features:
                return Delivery(False, error="the XMPP server offers no PLAIN sign-in over TLS")
            token = base64.b64encode(f"\0{user}\0{_env('XMPP_PASSWORD')}".encode()).decode()
            writer.write(f"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>{token}</auth>".encode())
            if b"<failure" in await until(rb"<success[^>]*(/>|>.*?</success>)", rb"<failure.*?</failure>"):
                return Delivery(False, error="the XMPP server refused the sign-in")
            buffer = b""
            open_stream()
            await until(rb"<stream:features.*?</stream:features>")
            writer.write(b"<iq type='set' id='bind1'><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
                         b"<resource>agent-guru</resource></bind></iq>")
            await until(rb"<iq[^>]*id=['\"]bind1['\"][^>]*>.*?</iq>")
            writer.write(f"<message to='{escape(contact)}' type='chat' id='msg1'><body>{escape(text[:_MAX_CHARS])}</body></message>"
                         f"<iq type='get' id='ping1' to='{escape(domain)}'><ping xmlns='urn:xmpp:ping'/></iq>".encode())
            answer = await until(rb"<message[^>]*type=['\"]error['\"].*?</message>",
                                 rb"<iq[^>]*id=['\"]ping1['\"][^>]*(/>|>.*?</iq>)")
            writer.write(b"</stream:stream>")
            await writer.drain()
        finally:
            writer.close()
        if answer.startswith(b"<message"):
            return Delivery(False, error=f"the XMPP server refused the message: {answer[:200].decode(errors='replace')}")
        return Delivery(True, message_id="msg1")


def _bech32_decode(text: str, prefix: str) -> bytes:
    """The 32-byte payload of a Nostr npub or nsec (BIP173 bech32, checksum checked)."""
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    text = text.strip().lower()
    hrp, _, data = text.rpartition("1")
    if hrp != prefix or len(data) < 7 or any(c not in alphabet for c in data):
        msg = f"not a {prefix} key"
        raise ValueError(msg)
    values = [alphabet.index(c) for c in data]
    check = 1
    for v in [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + values:
        top = check >> 25
        check = (check & 0x1FFFFFF) << 5 ^ v
        for i, g in enumerate((0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)):
            check ^= g if (top >> i) & 1 else 0
    if check != 1:
        msg = f"the {prefix} key's checksum is wrong"
        raise ValueError(msg)
    acc, bits, out = 0, 0, bytearray()
    for v in values[:-6]:
        acc, bits = (acc << 5) | v, bits + 5
        while bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    if len(out) != 32:
        msg = f"the {prefix} key is not 32 bytes"
        raise ValueError(msg)
    return bytes(out)


def _nostr_key(text: str, prefix: str) -> bytes:
    text = text.strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", text):
        return bytes.fromhex(text)
    return _bech32_decode(text, prefix)


def nostr_event(secret: bytes, kind: int, content: str, tags: list[list[str]], created_at: int,
                aux: bytes) -> dict[str, Any]:
    """A signed Nostr event (NIP-01): id is the SHA-256 of its canonical JSON, sig BIP340 over the id."""
    import hashlib

    from Agent_Guru.platform.channels import secp256k1

    pubkey = secp256k1.public_key(secret).hex()
    serial = json.dumps([0, pubkey, created_at, kind, tags, content], separators=(",", ":"), ensure_ascii=False)
    event_id = hashlib.sha256(serial.encode()).digest()
    return {"id": event_id.hex(), "pubkey": pubkey, "created_at": created_at, "kind": kind, "tags": tags,
            "content": content, "sig": secp256k1.sign(event_id, secret, aux).hex()}


def nip04_encrypt(secret: bytes, peer: bytes, text: str, iv: bytes) -> str:
    """NIP-04 direct-message content: AES-256-CBC under the ECDH x coordinate, "<ciphertext>?iv=<iv>"."""
    import base64

    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    from Agent_Guru.platform.channels import secp256k1

    padder = padding.PKCS7(128).padder()
    plain = padder.update(text.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(secp256k1.shared_x(secret, peer)), modes.CBC(iv)).encryptor()
    sealed = encryptor.update(plain) + encryptor.finalize()
    return f"{base64.b64encode(sealed).decode()}?iv={base64.b64encode(iv).decode()}"


def nip04_decrypt(secret: bytes, peer: bytes, content: str) -> str:
    import base64

    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    from Agent_Guru.platform.channels import secp256k1

    sealed, _, iv = content.partition("?iv=")
    decryptor = Cipher(algorithms.AES(secp256k1.shared_x(secret, peer)), modes.CBC(base64.b64decode(iv))).decryptor()
    plain = decryptor.update(base64.b64decode(sealed)) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(plain) + unpadder.finalize()).decode()


class NostrChannel(Channel):
    """Nostr, signed with the owner's key (NOSTR_SECRET, nsec or hex) and sent to NOSTR_RELAYS (wss URLs, comma separated).

    "public" posts a note (kind 1); an npub or hex key gets an encrypted
    direct message (NIP-04, kind 4: the text is encrypted, who wrote to
    whom is visible on the relay). "Sent" means at least one relay
    answered OK for the event.
    """

    name = "nostr"

    def _relays(self) -> list[str]:
        return [r.strip() for r in _env("NOSTR_RELAYS").split(",") if r.strip().startswith(("wss://", "ws://"))]

    def configured(self) -> bool:
        try:
            _nostr_key(_env("NOSTR_SECRET"), "nsec")
        except ValueError:
            return False
        return bool(self._relays())

    def accepts(self, contact: str) -> bool:
        if contact.strip() == "public":
            return True
        try:
            _nostr_key(contact, "npub")
        except ValueError:
            return False
        return True

    async def send(self, contact: str, text: str) -> Delivery:
        import secrets
        import time

        try:
            secret = _nostr_key(_env("NOSTR_SECRET"), "nsec")
            if contact.strip() == "public":
                event = nostr_event(secret, 1, text[:_MAX_CHARS], [], int(time.time()), secrets.token_bytes(32))
            else:
                peer = _nostr_key(contact, "npub")
                content = nip04_encrypt(secret, peer, text[:_MAX_CHARS], secrets.token_bytes(16))
                event = nostr_event(secret, 4, content, [["p", peer.hex()]], int(time.time()), secrets.token_bytes(32))
        except Exception as exc:
            return Delivery(False, error=f"{type(exc).__name__}: {exc}"[:200])
        answers = await asyncio.gather(*(self._publish(r, event) for r in self._relays()))
        if any(ok for ok, _ in answers):
            return Delivery(True, message_id=event["id"])
        return Delivery(False, error="; ".join(why for _, why in answers)[:200] or "no relay")

    async def _publish(self, relay: str, event: dict[str, Any]) -> tuple[bool, str]:
        try:
            from websockets.asyncio.client import connect
        except ImportError:
            return False, "the websockets package is not installed"
        try:
            async with asyncio.timeout(_TIMEOUT_S):
                async with connect(relay, open_timeout=_TIMEOUT_S, max_size=1 << 20) as ws:
                    await ws.send(json.dumps(["EVENT", event]))
                    while True:
                        reply = json.loads(await ws.recv())
                        if isinstance(reply, list) and reply[:2] == ["OK", event["id"]]:
                            return bool(reply[2]), f"{relay}: {reply[3] if len(reply) > 3 else ''}"
        except Exception as exc:
            return False, f"{relay}: {type(exc).__name__}: {exc}"


CHANNELS: dict[str, Channel] = {c.name: c for c in (
    TelegramChannel(), SlackChannel(), EmailChannel(), DiscordChannel(), SignalChannel(), TwilioSmsChannel(),
    MatrixChannel(), ZulipChannel(), MastodonChannel(), LineChannel(), ViberChannel(), MessengerChannel(),
    RedditChannel(), IrcChannel(), IrcChannel("twitch", "TWITCH"), XChannel(), XmppChannel(), NostrChannel(),
    *(WebhookChannel(n) for n in ("teams", "google_chat", "mattermost", "rocketchat", "feishu", "webhook")),
)}

#: Spoken names for the same app.
ALIASES = {
    "microsoft teams": "teams", "ms teams": "teams", "google chat": "google_chat", "googlechat": "google_chat",
    "rocket chat": "rocketchat", "rocket.chat": "rocketchat", "lark": "feishu", "text": "sms",
    "text message": "sms", "twilio": "sms", "element": "matrix",
    "twitter": "x", "jabber": "xmpp",
}

#: Apps with no desktop app to prefill: only a configured channel can reach them.
API_ONLY = frozenset(set(CHANNELS) - {"telegram", "slack", "email", "sms"})


def canonical(app: str) -> str:
    name = app.strip().lower()
    return ALIASES.get(name, name)


def channel_for(app: str) -> Channel | None:
    """The configured API channel for *app*, or None (then the app is prefilled as before)."""
    channel = CHANNELS.get(canonical(app))
    return channel if channel is not None and channel.configured() else None
