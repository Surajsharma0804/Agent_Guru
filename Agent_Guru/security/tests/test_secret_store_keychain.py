"""Off Windows, secrets are encrypted with a key the system keychain holds, when there is one.

A real Linux install found the credential store writing a cloud key in plain text: without DPAPI it
kept the value as it was, in a file only its owner could read. Now the keychain holds a key, the file
holds ciphertext, and with no keychain encrypted_at_rest() says so.
"""

from __future__ import annotations

import sys
import types

import pytest

from Agent_Guru.security import secret_store as ss


@pytest.fixture
def keychain(monkeypatch):
    """A working keyring backend in memory, on a machine that is not Windows."""
    stored: dict[str, str] = {}
    fail = types.ModuleType("keyring.backends.fail")
    fail.Keyring = type("Keyring", (), {})
    backends = types.ModuleType("keyring.backends")
    backends.fail = fail
    keyring = types.ModuleType("keyring")
    keyring.backends = backends
    keyring.get_keyring = lambda: types.SimpleNamespace(priority=5)
    keyring.get_password = lambda service, name: stored.get(name)
    keyring.set_password = lambda service, name, value: stored.__setitem__(name, value)
    for name, module in (("keyring", keyring), ("keyring.backends", backends), ("keyring.backends.fail", fail)):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(ss, "_on_windows", lambda: False)
    return stored


def test_with_a_keychain_the_file_holds_no_plain_text(keychain, tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "path_for", lambda name: tmp_path / f"{name}.dpapi")
    ss.save("cloud", b"sk-a-provider-key")
    raw = (tmp_path / "cloud.dpapi").read_bytes()
    assert raw.startswith(ss._MARK) and b"sk-a-provider-key" not in raw  # nosec B101
    assert ss.load("cloud") == b"sk-a-provider-key" and ss.encrypted_at_rest()  # nosec B101
    assert list(keychain) == ["store-key"]  # nosec B101  only the key is in the keychain


def test_a_file_written_before_this_is_still_read(keychain, tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "path_for", lambda name: tmp_path / f"{name}.dpapi")
    (tmp_path / "old.dpapi").write_bytes(b"older-value")
    assert ss.load("old") == b"older-value"  # nosec B101


def test_with_no_keychain_it_says_so_and_still_works(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_on_windows", lambda: False)
    monkeypatch.setitem(sys.modules, "keyring", None)
    monkeypatch.setattr(ss, "path_for", lambda name: tmp_path / f"{name}.dpapi")
    assert ss.encrypted_at_rest() is False  # nosec B101
    ss.save("cloud", b"value")
    assert ss.load("cloud") == b"value"  # nosec B101


def test_an_encrypted_file_without_its_keychain_is_an_error_not_garbage(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_on_windows", lambda: False)
    monkeypatch.setitem(sys.modules, "keyring", None)
    monkeypatch.setattr(ss, "path_for", lambda name: tmp_path / f"{name}.dpapi")
    (tmp_path / "cloud.dpapi").write_bytes(ss._MARK + b"ciphertext")
    with pytest.raises(ss.NoCredentialBackend):
        ss.load("cloud")
