"""secp256k1 keys, BIP340 Schnorr signatures and ECDH, for the Nostr channel.

No installed package signs with BIP340 (cryptography has no secp256k1
Schnorr, and coincurve and secp256k1 are not dependencies), and a Nostr
relay accepts only events signed that way. This is the arithmetic of
BIP340 as its specification states it, in plain Python integers. A
signature took 172 ms on the development laptop (affine coordinates, one
modular inverse per step), which is nothing beside a relay round trip.

It is checked against every official BIP340 test vector
(tests/test_secp256k1.py). It is not constant time: a signing key used
here must not be one whose timing an attacker on the same machine could
measure, which for a personal assistant's own Nostr key is acceptable.
"""

from __future__ import annotations

import hashlib

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)

Point = tuple[int, int] | None


def _add(a: Point, b: Point) -> Point:
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] != b[1] or a[1] == 0):
        return None
    if a == b:
        slope = 3 * a[0] * a[0] * pow(2 * a[1], P - 2, P) % P
    else:
        slope = (b[1] - a[1]) * pow(b[0] - a[0], P - 2, P) % P
    x = (slope * slope - a[0] - b[0]) % P
    return x, (slope * (a[0] - x) - a[1]) % P


def _mul(point: Point, scalar: int) -> Point:
    result: Point = None
    for i in range(256):
        if (scalar >> i) & 1:
            result = _add(result, point)
        point = _add(point, point)
    return result


def _tagged(tag: str, data: bytes) -> bytes:
    digest = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(digest + digest + data).digest()


def _lift_x(x: int) -> Point:
    if x >= P:
        return None
    c = (pow(x, 3, P) + 7) % P
    y = pow(c, (P + 1) // 4, P)
    if pow(y, 2, P) != c:
        return None
    return x, y if y % 2 == 0 else P - y


def _int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _bytes(x: int) -> bytes:
    return x.to_bytes(32, "big")


def public_key(secret: bytes) -> bytes:
    """The 32-byte x-only public key of a 32-byte secret key."""
    d = _int(secret)
    if not 1 <= d < N:
        msg = "the secret key is out of range"
        raise ValueError(msg)
    point = _mul(G, d)
    assert point is not None  # nosec B101 - d is in [1, N)
    return _bytes(point[0])


def sign(message: bytes, secret: bytes, aux: bytes) -> bytes:
    """A 64-byte BIP340 signature of *message* (any length) with *secret*; *aux* is 32 fresh random bytes."""
    d0 = _int(secret)
    if not 1 <= d0 < N:
        msg = "the secret key is out of range"
        raise ValueError(msg)
    if len(aux) != 32:
        msg = "aux must be 32 bytes"
        raise ValueError(msg)
    point = _mul(G, d0)
    assert point is not None  # nosec B101
    d = d0 if point[1] % 2 == 0 else N - d0
    t = _bytes(d ^ _int(_tagged("BIP0340/aux", aux)))
    k0 = _int(_tagged("BIP0340/nonce", t + _bytes(point[0]) + message)) % N
    if k0 == 0:
        msg = "the nonce came out zero; sign again with other aux bytes"
        raise ValueError(msg)
    r = _mul(G, k0)
    assert r is not None  # nosec B101
    k = k0 if r[1] % 2 == 0 else N - k0
    e = _int(_tagged("BIP0340/challenge", _bytes(r[0]) + _bytes(point[0]) + message)) % N
    signature = _bytes(r[0]) + _bytes((k + e * d) % N)
    if not verify(message, _bytes(point[0]), signature):
        msg = "the signature did not verify"
        raise ArithmeticError(msg)
    return signature


def verify(message: bytes, public: bytes, signature: bytes) -> bool:
    """Whether *signature* is a valid BIP340 signature of *message* by the x-only key *public*."""
    if len(public) != 32 or len(signature) != 64:
        return False
    point = _lift_x(_int(public))
    r, s = _int(signature[:32]), _int(signature[32:])
    if point is None or r >= P or s >= N:
        return False
    e = _int(_tagged("BIP0340/challenge", signature[:32] + public + message)) % N
    minus_e = _mul(point, N - e)
    found = _add(_mul(G, s), minus_e)
    return found is not None and found[1] % 2 == 0 and found[0] == r


def shared_x(secret: bytes, public: bytes) -> bytes:
    """The x coordinate of secret * public (an x-only key): the ECDH secret Nostr's NIP-04 uses."""
    point = _lift_x(_int(public))
    if point is None:
        msg = "not a public key on the curve"
        raise ValueError(msg)
    shared = _mul(point, _int(secret))
    if shared is None:
        msg = "the shared point is at infinity"
        raise ValueError(msg)
    return _bytes(shared[0])
