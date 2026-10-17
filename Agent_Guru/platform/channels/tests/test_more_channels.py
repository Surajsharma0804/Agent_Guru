"""X, XMPP and Nostr: signed and spoken the way each service requires, and "sent" only when it says so.

X has no test server, so its OAuth 1.0a signature is checked against the
worked example in X's documentation. XMPP talks to a scripted server
over real TLS. Nostr publishes to a relay on this machine that checks
the event's id and BIP340 signature before answering OK.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import ssl

import pytest

from Agent_Guru.platform import channels
from Agent_Guru.platform.channels import (
    CHANNELS,
    _bech32_decode,
    canonical,
    nip04_decrypt,
    nip04_encrypt,
    nostr_event,
    oauth1_header,
    secp256k1,
)


def test_x_signature_matches_the_documented_example():
    """X's "Creating a signature" example: the signature it prints is hCtSmYh+iHYCEqBWrE7C7hYmtUk=."""
    header = oauth1_header(
        "POST", "https://api.twitter.com/1.1/statuses/update.json",
        {"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
        {"consumer_key": "xvz1evFS4wEEPTGEFPHBog", "consumer_secret": "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
         "token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
         "token_secret": "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", timestamp="1318622958",
    )
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in header  # nosec B101


def test_new_channels_are_registered_with_their_spoken_names(monkeypatch):
    assert {"x", "xmpp", "nostr"} <= set(CHANNELS) and {"x", "xmpp", "nostr"} <= channels.API_ONLY  # nosec B101
    assert canonical("Twitter") == "x" and canonical("jabber") == "xmpp"  # nosec B101
    assert CHANNELS["x"].accepts("@rahul_k") and CHANNELS["x"].accepts("public")  # nosec B101
    assert not CHANNELS["x"].accepts("rahul k")  # nosec B101
    assert CHANNELS["xmpp"].accepts("friend@example.org") and not CHANNELS["xmpp"].accepts("x'@y")  # nosec B101


# NIP-19's examples of the same encodings.
_NPUB = "npub10elfcs4fr0l0r8af98jlmgdh9c8tcxjvz9qkw038js35mp4dma8qzvjptg"
_NPUB_HEX = "7e7e9c42a91bfef19fa929e5fda1b72e0ebc1a4c1141673e2794234d86addf4e"
_NSEC = "nsec1vl029mgpspedva04g90vltkh6fvh240zqtv9k0t9af8935ke9laqsnlfe5"
_NSEC_HEX = "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa"


def test_nostr_keys_decode_as_nip19_shows():
    assert _bech32_decode(_NPUB, "npub").hex() == _NPUB_HEX  # nosec B101
    assert _bech32_decode(_NSEC, "nsec").hex() == _NSEC_HEX  # nosec B101
    broken = _NPUB[:-1] + ("q" if _NPUB[-1] != "q" else "p")
    with pytest.raises(ValueError, match="checksum"):
        _bech32_decode(broken, "npub")
    with pytest.raises(ValueError):
        _bech32_decode(_NSEC, "npub")


def test_a_nostr_event_is_signed_over_its_id():
    secret = bytes.fromhex(_NSEC_HEX)
    event = nostr_event(secret, 1, "hello", [], 1700000000, bytes(32))
    import hashlib

    serial = json.dumps([0, event["pubkey"], 1700000000, 1, [], "hello"], separators=(",", ":"))
    assert event["id"] == hashlib.sha256(serial.encode()).hexdigest()  # nosec B101
    assert secp256k1.verify(bytes.fromhex(event["id"]), bytes.fromhex(event["pubkey"]),  # nosec B101
                            bytes.fromhex(event["sig"]))


def test_a_direct_message_opens_only_for_the_two_people():
    a, b, c = bytes(31) + b"\x07", bytes(31) + b"\x0b", bytes(31) + b"\x0d"
    sealed = nip04_encrypt(a, secp256k1.public_key(b), "meet at 6", bytes(range(16)))
    assert "meet" not in sealed and "?iv=" in sealed  # nosec B101
    assert nip04_decrypt(b, secp256k1.public_key(a), sealed) == "meet at 6"  # nosec B101
    with pytest.raises(ValueError):
        nip04_decrypt(c, secp256k1.public_key(a), sealed)


async def _relay(accept: bool):
    from websockets.asyncio.server import serve

    got = []

    async def handler(ws):
        async for raw in ws:
            kind, event = json.loads(raw)
            ok = kind == "EVENT" and secp256k1.verify(
                bytes.fromhex(event["id"]), bytes.fromhex(event["pubkey"]), bytes.fromhex(event["sig"]))
            got.append(event)
            await ws.send(json.dumps(["OK", event["id"], ok and accept, "" if accept else "blocked: test"]))

    server = await serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}", got


async def test_nostr_sent_only_when_a_relay_accepts(monkeypatch):
    pytest.importorskip("websockets")
    server, url, got = await _relay(accept=True)
    monkeypatch.setenv("NOSTR_SECRET", _NSEC)
    monkeypatch.setenv("NOSTR_RELAYS", url)
    try:
        nostr = CHANNELS["nostr"]
        assert nostr.configured()  # nosec B101
        delivery = await nostr.send(_NPUB, "the train is late")
        assert delivery.sent and delivery.message_id == got[-1]["id"]  # nosec B101
        assert got[-1]["kind"] == 4 and got[-1]["tags"] == [["p", _NPUB_HEX]]  # nosec B101
        assert "train" not in got[-1]["content"]  # nosec B101  encrypted
        public = await nostr.send("public", "hello nostr")
        assert public.sent and got[-1]["kind"] == 1 and got[-1]["content"] == "hello nostr"  # nosec B101
    finally:
        server.close()
    server, url, _ = await _relay(accept=False)
    monkeypatch.setenv("NOSTR_RELAYS", url)
    try:
        refused = await CHANNELS["nostr"].send("public", "hello")
        assert not refused.sent and "blocked" in refused.error  # nosec B101
    finally:
        server.close()


def _certificate(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / "server.crt", tmp_path / "server.key"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_file, key_file


async def _xmpp_server(tmp_path, *, tls=True, password="pw", refuse_message=False):
    """A scripted XMPP server: STARTTLS, SASL PLAIN, bind, then one message and a ping."""
    import base64

    cert_file, key_file = _certificate(tmp_path)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_file, key_file)
    seen = {"auth": None, "message": None}
    features = ("<stream:features>" + ("<starttls xmlns='urn:ietf:params:xml:ns:xmpp-tls'/>" if tls else "")
                + "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'><mechanism>PLAIN</mechanism></mechanisms>"
                "</stream:features>")
    header = "<stream:stream xmlns='jabber:client' xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>"

    async def handle(reader, writer):
        async def read_until(marker: bytes) -> bytes:
            data = b""
            while marker not in data:
                chunk = await reader.read(65536)
                if not chunk:
                    raise ConnectionError
                data += chunk
            return data

        try:
            await read_until(b"<stream:stream")
            writer.write((header + features).encode())
            data = await read_until(b">")
            if b"<starttls" not in data:
                seen["auth"] = data
                return
            writer.write(b"<proceed xmlns='urn:ietf:params:xml:ns:xmpp-tls'/>")
            await writer.drain()
            await writer.start_tls(context)
            await read_until(b"<stream:stream")
            writer.write((header + features).encode())
            auth = await read_until(b"</auth>")
            seen["auth"] = auth
            token = auth.split(b">", 1)[1].split(b"<", 1)[0]
            if base64.b64decode(token).split(b"\0")[2].decode() != password:
                writer.write(b"<failure xmlns='urn:ietf:params:xml:ns:xmpp-sasl'><not-authorized/></failure>")
                return
            writer.write(b"<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>")
            await read_until(b"<stream:stream")
            writer.write((header + "<stream:features><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'/></stream:features>").encode())
            await read_until(b"</iq>")
            writer.write(b"<iq type='result' id='bind1'><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
                         b"<jid>me@localhost/agent-guru</jid></bind></iq>")
            data = await read_until(b"urn:xmpp:ping")
            seen["message"] = data
            if refuse_message:
                writer.write(b"<message type='error' id='msg1'><error type='cancel'>"
                             b"<service-unavailable xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error></message>")
            writer.write(b"<iq type='result' id='ping1'/>")
            await writer.drain()
            await read_until(b"</stream:stream>")
        except (ConnectionError, ssl.SSLError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], cert_file, seen


@pytest.fixture
def xmpp_env(monkeypatch):
    def setup(port, cert_file, password="pw"):
        monkeypatch.setenv("XMPP_JID", "me@localhost")
        monkeypatch.setenv("XMPP_PASSWORD", password)
        monkeypatch.setenv("XMPP_SERVER", f"localhost:{port}")
        monkeypatch.setenv("XMPP_CA_FILE", str(cert_file))
    return setup


async def test_xmpp_sends_over_tls_and_escapes_the_text(tmp_path, xmpp_env):
    server, port, cert, seen = await _xmpp_server(tmp_path)
    xmpp_env(port, cert)
    try:
        delivery = await CHANNELS["xmpp"].send("friend@localhost", "5 < 6 & 'yes'")
    finally:
        server.close()
    assert delivery.sent, delivery.error  # nosec B101
    assert b"<body>5 &lt; 6 &amp; 'yes'</body>" in seen["message"]  # nosec B101


async def test_xmpp_reports_a_refused_message_as_not_sent(tmp_path, xmpp_env):
    server, port, cert, _ = await _xmpp_server(tmp_path, refuse_message=True)
    xmpp_env(port, cert)
    try:
        delivery = await CHANNELS["xmpp"].send("nobody@localhost", "hi")
    finally:
        server.close()
    assert not delivery.sent and "service-unavailable" in delivery.error  # nosec B101


async def test_xmpp_wrong_password_is_not_sent(tmp_path, xmpp_env):
    server, port, cert, _ = await _xmpp_server(tmp_path)
    xmpp_env(port, cert, password="wrong")
    try:
        delivery = await CHANNELS["xmpp"].send("friend@localhost", "hi")
    finally:
        server.close()
    assert not delivery.sent and "sign-in" in delivery.error  # nosec B101


async def test_xmpp_never_sends_the_password_without_tls(tmp_path, xmpp_env):
    server, port, cert, seen = await _xmpp_server(tmp_path, tls=False)
    xmpp_env(port, cert)
    try:
        delivery = await CHANNELS["xmpp"].send("friend@localhost", "hi")
    finally:
        server.close()
    assert not delivery.sent and "TLS" in delivery.error  # nosec B101
    assert seen["auth"] is None or b"<auth" not in seen["auth"]  # nosec B101
