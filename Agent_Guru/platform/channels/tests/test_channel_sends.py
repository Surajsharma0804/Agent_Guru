"""The other channels, each against a stand-in for its service: what is sent, and "sent" only when the service says so.

Telegram, Slack, Discord, Signal, SMS, Matrix, Zulip, the webhooks,
Mastodon, LINE, Viber, Messenger and Reddit talk HTTP: httpx's
MockTransport answers in place of each service, in the shape its API
documents. Email talks to a stand-in SMTP class; IRC and Twitch to a
scripted IRC server on this machine. None of this proves a real account
works; it proves the request each service documents is the one sent,
and that a refusal is never reported as delivered.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import urllib.parse
from typing import Any

import httpx
import pytest

from Agent_Guru.platform import channels
from Agent_Guru.platform.channels import CHANNELS

TEXT = "Running 10 minutes late, café at 7"


@pytest.fixture
def service(monkeypatch):
    """Every httpx request goes to answer(request); the requests are kept in order."""
    seen = []
    state = {"answer": lambda request: httpx.Response(500)}

    def handle(request):
        seen.append(request)
        return state["answer"](request)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handle), **kw))
    for name in [k for k in __import__("os").environ if k.startswith("WEBHOOK_")]:
        monkeypatch.delenv(name)

    def answer(fn):
        state["answer"] = fn

    return seen, answer


def _body(request):
    if request.headers.get("content-type", "").startswith("application/json"):
        return json.loads(request.content)
    return dict(urllib.parse.parse_qsl(request.content.decode()))


def _basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


# name, environment, contact, method, url (a Matrix transaction id is random, so a prefix), what the request
# must carry, the service's answer when it takes the message, the message id that gives, and a refusal.
CASES = [
    ("telegram", {"TELEGRAM_BOT_TOKEN": "123:abc"}, "123456789",
     "POST", "https://api.telegram.org/bot123:abc/sendMessage",
     lambda r: _body(r) == {"chat_id": "123456789", "text": TEXT},
     (200, {"ok": True, "result": {"message_id": 42}}), "42",
     (400, {"ok": False, "description": "Bad Request: chat not found"}), "chat not found"),
    ("slack", {"SLACK_BOT_TOKEN": "xoxb-1"}, "#launch",
     "POST", "https://slack.com/api/chat.postMessage",
     lambda r: r.headers["authorization"] == "Bearer xoxb-1" and _body(r) == {"channel": "launch", "text": TEXT},
     (200, {"ok": True, "ts": "1792233000.000100"}), "1792233000.000100",
     # Slack refuses with 200 and ok false: the status code alone would call it sent.
     (200, {"ok": False, "error": "channel_not_found"}), "channel_not_found"),
    ("discord", {"DISCORD_BOT_TOKEN": "tok"}, "123456789012345678",
     "POST", "https://discord.com/api/v10/channels/123456789012345678/messages",
     lambda r: r.headers["authorization"] == "Bot tok" and _body(r) == {"content": TEXT},
     (200, {"id": "99"}), "99",
     (403, {"message": "Missing Access", "code": 50001}), "Missing Access"),
    ("signal", {"SIGNAL_API_URL": "http://127.0.0.1:8080/", "SIGNAL_NUMBER": "+911111111111"}, "+919999999999",
     "POST", "http://127.0.0.1:8080/v2/send",
     lambda r: _body(r) == {"message": TEXT, "number": "+911111111111", "recipients": ["+919999999999"]},
     (201, {"timestamp": 1792233000123}), "1792233000123",
     (400, {"error": "Invalid recipient"}), "Invalid recipient"),
    ("sms", {"TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t0k", "TWILIO_FROM": "+15550001111"}, "+91 99999 99999",
     "POST", "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages.json",
     lambda r: r.headers["authorization"] == _basic("AC1", "t0k")
     and _body(r) == {"To": "+919999999999", "From": "+15550001111", "Body": TEXT},
     (201, {"sid": "SM1"}), "SM1",
     (400, {"code": 21211, "message": "Invalid 'To' Phone Number"}), "Invalid 'To'"),
    ("matrix", {"MATRIX_HOMESERVER": "https://matrix.example.org/", "MATRIX_ACCESS_TOKEN": "syt_1"}, "!room:example.org",
     "PUT", "https://matrix.example.org/_matrix/client/v3/rooms/%21room%3Aexample.org/send/m.room.message/",
     lambda r: r.headers["authorization"] == "Bearer syt_1" and _body(r) == {"msgtype": "m.text", "body": TEXT},
     (200, {"event_id": "$ev1"}), "$ev1",
     (403, {"errcode": "M_FORBIDDEN", "error": "not in room"}), "M_FORBIDDEN"),
    ("zulip", {"ZULIP_SITE": "https://chat.example.org", "ZULIP_EMAIL": "bot@example.org", "ZULIP_API_KEY": "k1"},
     "rahul@example.org",
     "POST", "https://chat.example.org/api/v1/messages",
     lambda r: r.headers["authorization"] == _basic("bot@example.org", "k1")
     and _body(r) == {"type": "private", "to": '["rahul@example.org"]', "content": TEXT},
     (200, {"result": "success", "id": 7}), "7",
     (400, {"result": "error", "msg": "Invalid email 'rahul@example.org'"}), "Invalid email"),
    ("mastodon", {"MASTODON_URL": "https://social.example.org", "MASTODON_TOKEN": "m1"}, "public",
     "POST", "https://social.example.org/api/v1/statuses",
     lambda r: r.headers["authorization"] == "Bearer m1" and _body(r) == {"status": TEXT, "visibility": "public"},
     (200, {"id": "1100"}), "1100",
     (422, {"error": "Validation failed: Text can't be blank"}), "Validation failed"),
    ("line", {"LINE_CHANNEL_TOKEN": "l1"}, "U" + "0123456789abcdef" * 2,
     "POST", "https://api.line.me/v2/bot/message/push",
     lambda r: r.headers["authorization"] == "Bearer l1"
     and _body(r) == {"to": "U" + "0123456789abcdef" * 2, "messages": [{"type": "text", "text": TEXT}]},
     (200, {}), "",
     (400, {"message": "The request body has 1 error(s)"}), "1 error"),
    ("viber", {"VIBER_TOKEN": "v1"}, "01234567890A=bcdefgh",
     "POST", "https://chatapi.viber.com/pa/send_message",
     lambda r: r.headers["x-viber-auth-token"] == "v1"
     and _body(r) == {"receiver": "01234567890A=bcdefgh", "type": "text", "text": TEXT, "sender": {"name": "Agent Guru"}},
     (200, {"status": 0, "status_message": "ok", "message_token": 5}), "5",
     # Viber refuses with 200 and a non-zero status.
     (200, {"status": 6, "status_message": "notSubscribed"}), "notSubscribed"),
    ("messenger", {"MESSENGER_PAGE_TOKEN": "EAAB"}, "1234567890",
     "POST", "https://graph.facebook.com/v19.0/me/messages?access_token=EAAB",
     lambda r: _body(r) == {"recipient": {"id": "1234567890"}, "messaging_type": "MESSAGE_TAG", "tag": "ACCOUNT_UPDATE",
                            "message": {"text": TEXT}},
     (200, {"recipient_id": "1234567890", "message_id": "m_1"}), "m_1",
     (400, {"error": {"message": "(#100) No matching user found"}}), "No matching user"),
]


def _setup(monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
async def test_the_request_is_the_one_the_service_documents(service, monkeypatch, case):
    name, env, contact, method, url, carries, ok, message_id, _, _ = case
    seen, answer = service
    _setup(monkeypatch, env)
    channel = CHANNELS[name]
    assert channel.configured() and channel.accepts(contact)  # nosec B101
    answer(lambda r: httpx.Response(ok[0], json=ok[1]))
    delivery = await channel.send(contact, TEXT)
    assert delivery.sent and delivery.message_id == message_id, delivery  # nosec B101
    request = seen[-1]
    assert request.method == method and str(request.url).startswith(url) and carries(request)  # nosec B101


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
async def test_a_refusal_is_not_reported_as_sent(service, monkeypatch, case):
    name, env, contact, *_, refused, reason = case
    _, answer = service
    _setup(monkeypatch, env)
    answer(lambda r: httpx.Response(refused[0], json=refused[1]))
    delivery = await CHANNELS[name].send(contact, TEXT)
    assert not delivery.sent and reason in delivery.error, delivery  # nosec B101


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
async def test_a_network_failure_is_an_answer_not_a_crash(service, monkeypatch, case):
    name, env, contact, *_ = case
    _, answer = service
    _setup(monkeypatch, env)

    def down(request):
        raise httpx.ConnectError("connection refused")

    answer(down)
    delivery = await CHANNELS[name].send(contact, TEXT)
    assert not delivery.sent and delivery.error, delivery  # nosec B101
    assert "EAAB" not in delivery.error  # nosec B101  Messenger's token is in its URL; it stays out of the error


async def test_a_service_page_that_is_not_json_is_not_sent(service, monkeypatch):
    """A proxy's 502 page or a captive portal answers HTML; none of it reads as delivered."""
    _, answer = service
    _setup(monkeypatch, {"TELEGRAM_BOT_TOKEN": "1:a", "SLACK_BOT_TOKEN": "x", "MATRIX_HOMESERVER": "https://m.example.org",
                         "MATRIX_ACCESS_TOKEN": "t", "MESSENGER_PAGE_TOKEN": "p"})
    answer(lambda r: httpx.Response(502, text="<html>Bad gateway</html>"))
    for name, to in (("telegram", "123456789"), ("slack", "C0123456"), ("matrix", "!r:example.org"),
                     ("messenger", "1234567890")):
        assert not (await CHANNELS[name].send(to, TEXT)).sent, name  # nosec B101


async def test_a_discord_user_gets_a_direct_message_channel_first(service, monkeypatch):
    seen, answer = service
    _setup(monkeypatch, {"DISCORD_BOT_TOKEN": "tok"})

    def discord(request):
        if request.url.path.endswith("/users/@me/channels"):
            return httpx.Response(200, json={"id": "555555555555555555", "type": 1})
        return httpx.Response(200, json={"id": "77"})

    answer(discord)
    delivery = await CHANNELS["discord"].send("user:123456789012345678", TEXT)
    assert delivery.sent and delivery.message_id == "77"  # nosec B101
    assert _body(seen[0]) == {"recipient_id": "123456789012345678"}  # nosec B101
    assert seen[1].url.path == "/api/v10/channels/555555555555555555/messages"  # nosec B101


async def test_a_discord_user_who_blocks_direct_messages_is_not_sent(service, monkeypatch):
    seen, answer = service
    _setup(monkeypatch, {"DISCORD_BOT_TOKEN": "tok"})
    answer(lambda r: httpx.Response(403, json={"message": "Cannot send messages to this user", "code": 50007}))
    delivery = await CHANNELS["discord"].send("user:123456789012345678", TEXT)
    assert not delivery.sent and "direct message" in delivery.error and len(seen) == 1  # nosec B101


async def test_a_zulip_stream_message_names_the_stream_and_topic(service, monkeypatch):
    seen, answer = service
    _setup(monkeypatch, {"ZULIP_SITE": "https://chat.example.org", "ZULIP_EMAIL": "b@example.org", "ZULIP_API_KEY": "k"})
    answer(lambda r: httpx.Response(200, json={"result": "success", "id": 8}))
    assert (await CHANNELS["zulip"].send("stream:general/launch day", TEXT)).sent  # nosec B101
    assert _body(seen[0]) == {"type": "stream", "to": "general", "topic": "launch day", "content": TEXT}  # nosec B101


async def test_a_mastodon_direct_message_mentions_the_person_and_is_not_public(service, monkeypatch):
    seen, answer = service
    _setup(monkeypatch, {"MASTODON_URL": "https://social.example.org", "MASTODON_TOKEN": "m1"})
    answer(lambda r: httpx.Response(200, json={"id": "1101"}))
    assert (await CHANNELS["mastodon"].send("@rahul@social.example.org", TEXT)).sent  # nosec B101
    assert _body(seen[0]) == {"status": f"@rahul@social.example.org {TEXT}", "visibility": "direct"}  # nosec B101


async def test_reddit_signs_in_then_sends_the_private_message(service, monkeypatch):
    seen, answer = service
    _setup(monkeypatch, {"REDDIT_CLIENT_ID": "cid", "REDDIT_CLIENT_SECRET": "cs", "REDDIT_USERNAME": "guru_bot",
                         "REDDIT_PASSWORD": "pw"})

    def reddit(request):
        if request.url.path == "/api/v1/access_token":
            return httpx.Response(200, json={"access_token": "at1", "token_type": "bearer"})
        return httpx.Response(200, json={"json": {"errors": []}})

    answer(reddit)
    delivery = await CHANNELS["reddit"].send("u/rahul_k", "Late\nsee you at 7")
    assert delivery.sent  # nosec B101
    sign_in, compose = seen
    assert sign_in.headers["authorization"] == _basic("cid", "cs")  # nosec B101
    assert _body(sign_in) == {"grant_type": "password", "username": "guru_bot", "password": "pw"}  # nosec B101
    assert str(compose.url) == "https://oauth.reddit.com/api/compose"  # nosec B101
    assert compose.headers["authorization"] == "Bearer at1" and "AgentGuru" in compose.headers["user-agent"]  # nosec B101
    assert _body(compose) == {"to": "rahul_k", "subject": "Late", "text": "Late\nsee you at 7", "api_type": "json"}  # nosec B101


@pytest.mark.parametrize("token_answer, compose_answer, reason", [
    ((401, {"message": "Unauthorized"}), None, "sign-in failed"),
    ((200, {"access_token": "at1"}), (200, {"json": {"errors": [["USER_DOESNT_EXIST", "that user doesn't exist", "to"]]}}),
     "USER_DOESNT_EXIST"),
])
async def test_reddit_refusals_are_not_sent(service, monkeypatch, token_answer, compose_answer, reason):
    seen, answer = service
    _setup(monkeypatch, {"REDDIT_CLIENT_ID": "cid", "REDDIT_CLIENT_SECRET": "cs", "REDDIT_USERNAME": "u",
                         "REDDIT_PASSWORD": "pw"})
    answer(lambda r: httpx.Response(*token_answer[:1], json=token_answer[1]) if r.url.path == "/api/v1/access_token"
           else httpx.Response(compose_answer[0], json=compose_answer[1]))
    delivery = await CHANNELS["reddit"].send("rahul_k", TEXT)
    # Reddit answers a missing user with 200 and the error inside "json".
    assert not delivery.sent and reason in delivery.error  # nosec B101
    assert len(seen) == (1 if compose_answer is None else 2)  # nosec B101


@pytest.mark.parametrize("name, url, shape", [
    ("teams", "https://example.webhook.office.com/webhookb2/x",
     lambda b: b["type"] == "message" and b["attachments"][0]["content"]["body"][0]["text"] == TEXT),
    ("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/x", lambda b: b == {"msg_type": "text", "content": {"text": TEXT}}),
    ("mattermost", "https://chat.example.org/hooks/x", lambda b: b == {"text": TEXT}),
    ("webhook", "https://hooks.example.org/family", lambda b: b == {"text": TEXT}),
])
async def test_each_webhook_gets_the_shape_its_service_reads(service, monkeypatch, name, url, shape):
    seen, answer = service
    monkeypatch.setenv("WEBHOOK_FAMILY_URL", url)
    channel = CHANNELS[name]
    assert channel.configured() and channel.accepts("family") and not channel.accepts("work")  # nosec B101
    answer(lambda r: httpx.Response(200, text="1"))
    assert (await channel.send("family", TEXT)).sent  # nosec B101
    assert str(seen[0].url) == url and shape(json.loads(seen[0].content))  # nosec B101


async def test_the_webhook_signature_is_over_the_bytes_sent(service, monkeypatch):
    """The receiver checks the HMAC over the raw body it got; the signature used to be over other bytes."""
    seen, answer = service
    monkeypatch.setenv("WEBHOOK_FAMILY_URL", "https://hooks.example.org/family")
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cret")
    answer(lambda r: httpx.Response(200))
    assert (await CHANNELS["webhook"].send("family", TEXT)).sent  # nosec B101
    request = seen[0]
    expected = hmac.new(b"s3cret", request.content, hashlib.sha256).hexdigest()
    assert request.headers["x-signature"] == expected  # nosec B101
    assert json.loads(request.content) == {"text": TEXT}  # nosec B101


async def test_a_webhook_refusal_is_not_sent(service, monkeypatch):
    _, answer = service
    monkeypatch.setenv("WEBHOOK_FAMILY_URL", "https://hooks.example.org/family")
    answer(lambda r: httpx.Response(404, text="no such hook"))
    delivery = await CHANNELS["webhook"].send("family", TEXT)
    assert not delivery.sent and "404" in delivery.error  # nosec B101


class FakeSmtp:
    """Stands in for smtplib.SMTP and SMTP_SSL; records what the channel asked of the server."""

    made: list[FakeSmtp] = []
    refuse: dict[str, tuple[int, bytes]] = {}

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.ssl_context, self.calls, self.sent = host, port, context, [], None
        FakeSmtp.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.calls.append("send")
        self.sent = message
        return dict(FakeSmtp.refuse)


@pytest.fixture
def smtp(monkeypatch):
    FakeSmtp.made, FakeSmtp.refuse = [], {}
    monkeypatch.setattr(channels.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(channels.smtplib, "SMTP_SSL", FakeSmtp)
    for key, value in {"SMTP_HOST": "smtp.example.org", "SMTP_USER": "me@example.org", "SMTP_PASSWORD": "pw",
                       "SMTP_FROM": "Guru <me@example.org>"}.items():
        monkeypatch.setenv(key, value)
    return FakeSmtp


@pytest.mark.parametrize("port, steps", [("587", ["starttls", ("login", "me@example.org", "pw"), "send", "quit"]),
                                         ("465", [("login", "me@example.org", "pw"), "send", "quit"])])
async def test_email_logs_in_over_tls_before_it_sends(smtp, monkeypatch, port, steps):
    monkeypatch.setenv("SMTP_PORT", port)
    delivery = await CHANNELS["email"].send("rahul@example.org", TEXT)
    server = smtp.made[0]
    assert delivery.sent and (server.host, server.port) == ("smtp.example.org", int(port))  # nosec B101
    # STARTTLS before the password on 587; on 465 the connection is TLS from the start.
    assert server.calls == steps  # nosec B101
    assert (port == "465") == (server.ssl_context is not None)  # nosec B101
    message = server.sent
    assert message["To"] == "rahul@example.org" and message["From"] == "Guru <me@example.org>"  # nosec B101
    assert message["Subject"] == TEXT and message.get_content().strip() == TEXT  # nosec B101


async def test_an_email_the_server_refuses_is_not_sent(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "587")
    smtp.refuse = {"rahul@example.org": (550, b"No such user")}
    delivery = await CHANNELS["email"].send("rahul@example.org", TEXT)
    assert not delivery.sent and "refused rahul@example.org" in delivery.error  # nosec B101


async def test_an_email_address_cannot_carry_another_header():
    assert not CHANNELS["email"].accepts("rahul@example.org\nBcc: all@example.org")  # nosec B101


@pytest.fixture
async def irc_server(monkeypatch):
    """A scripted IRC server on this machine, plain TCP: the channel's TLS context is replaced with none."""
    heard: list[str] = []
    script: dict[str, Any] = {"welcome": [":srv 001 guru :Welcome"], "on_privmsg": [], "answer_ping": True}

    async def handle(reader, writer):
        while line := await reader.readline():
            text = line.decode().rstrip("\r\n")
            heard.append(text)
            out = []
            if text.startswith("USER") and script["welcome"] is None:
                break
            if text.startswith("USER"):
                out = [":srv PING :check-you"] + script["welcome"]
            elif text.startswith("PRIVMSG"):
                out = script["on_privmsg"]
            elif text.startswith("PING") and script["answer_ping"]:
                out = [f":srv PONG srv {text[5:]}"]
            for reply in out:
                writer.write((reply + "\r\n").encode())
            await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(channels.ssl, "create_default_context", lambda: None)
    for prefix in ("IRC", "TWITCH"):
        monkeypatch.setenv(f"{prefix}_SERVER", f"127.0.0.1:{port}")
        monkeypatch.setenv(f"{prefix}_NICK", "guru")
    yield heard, script
    server.close()
    await server.wait_closed()


async def test_irc_waits_for_the_welcome_then_joins_and_speaks(irc_server, monkeypatch):
    heard, _ = irc_server
    monkeypatch.setenv("IRC_PASSWORD", "pw")
    delivery = await CHANNELS["irc"].send("#family", "line one\nline two")
    assert delivery.sent, delivery  # nosec B101
    assert heard[:3] == ["PASS pw", "NICK guru", "USER guru 0 * :Agent Guru"]  # nosec B101
    assert "PONG :check-you" in heard  # nosec B101  the server's ping before the welcome is answered
    spoken = [h for h in heard if h.startswith(("JOIN", "PRIVMSG"))]
    assert spoken == ["JOIN #family", "PRIVMSG #family :line one", "PRIVMSG #family :line two"]  # nosec B101


async def test_twitch_is_the_same_channel_under_its_own_settings(irc_server):
    heard, _ = irc_server
    assert (await CHANNELS["twitch"].send("#somechannel", TEXT)).sent  # nosec B101
    assert f"PRIVMSG #somechannel :{TEXT}" in heard  # nosec B101


@pytest.mark.parametrize("refusal", [":srv 401 guru nobody :No such nick/channel",
                                     ":srv 404 guru #quiet :Cannot send to channel",
                                     ":srv 474 guru #quiet :Cannot join channel (+b)"])
async def test_a_message_irc_refuses_is_not_sent(irc_server, refusal):
    """IRC confirms nothing it accepts; the channel used to call these sent."""
    _, script = irc_server
    script["on_privmsg"] = [refusal]
    delivery = await CHANNELS["irc"].send("#quiet" if "#" in refusal else "nobody", TEXT)
    assert not delivery.sent and refusal.split()[1] in delivery.error  # nosec B101


async def test_a_nick_in_use_is_not_sent(irc_server):
    heard, script = irc_server
    script["welcome"] = [":srv 433 * guru :Nickname is already in use"]
    delivery = await CHANNELS["irc"].send("#family", TEXT)
    assert not delivery.sent and "433" in delivery.error  # nosec B101
    assert not [h for h in heard if h.startswith("PRIVMSG")]  # nosec B101


async def test_a_server_that_closes_before_the_welcome_is_not_sent(irc_server):
    _, script = irc_server
    script["welcome"] = None
    delivery = await asyncio.wait_for(CHANNELS["irc"].send("#family", TEXT), 30)
    assert not delivery.sent and "closed the connection" in delivery.error  # nosec B101
