"""The Nostr channel's signatures are BIP340's, checked against the specification's own test vectors.

bip340_vectors.csv is test-vectors.csv from the BIP340 specification
(github.com/bitcoin/bips, bip-0340), unchanged, used under CC0-1.0, one
of the licenses BIP340's code is offered under ("License-Code:
BSD-2-Clause OR MIT OR CC0-1.0"). A relay rejects an event
whose signature is not exactly BIP340, so every vector must hold: the
exact signature bytes where a secret key is given, and the verdict
(including every rejected case) for all of them.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from Agent_Guru.platform.channels import secp256k1

_ROWS = list(csv.DictReader(Path(__file__).with_name("bip340_vectors.csv").open(encoding="ascii")))


@pytest.mark.parametrize("row", _ROWS, ids=[r["index"] for r in _ROWS])
def test_official_vector(row):
    public = bytes.fromhex(row["public key"])
    message = bytes.fromhex(row["message"])
    signature = bytes.fromhex(row["signature"])
    if row["secret key"]:
        secret = bytes.fromhex(row["secret key"])
        assert secp256k1.public_key(secret) == public  # nosec B101
        assert secp256k1.sign(message, secret, bytes.fromhex(row["aux_rand"])) == signature  # nosec B101
    assert secp256k1.verify(message, public, signature) is (row["verification result"] == "TRUE")  # nosec B101


def test_all_nineteen_vectors_are_there():
    assert len(_ROWS) == 19  # nosec B101


def test_ecdh_gives_both_sides_the_same_secret():
    a, b = bytes(31) + b"\x07", bytes(31) + b"\x0b"
    assert secp256k1.shared_x(a, secp256k1.public_key(b)) == secp256k1.shared_x(b, secp256k1.public_key(a))  # nosec B101


def test_out_of_range_keys_are_refused():
    with pytest.raises(ValueError):
        secp256k1.public_key(bytes(32))
    with pytest.raises(ValueError):
        secp256k1.sign(b"m", secp256k1.N.to_bytes(32, "big"), bytes(32))
