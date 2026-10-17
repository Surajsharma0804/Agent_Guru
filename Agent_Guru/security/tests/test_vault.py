"""Credentials kept in the vault reach the environment encrypted at rest, and never override it."""

from __future__ import annotations

import io
import sys

import pytest

from Agent_Guru.security import secret_store, vault


@pytest.fixture(autouse=True)
def data_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_store, "path_for", lambda name: tmp_path / f"{name}.dpapi")
    return tmp_path


def test_a_stored_credential_fills_an_unset_variable():
    vault.put("TELEGRAM_BOT_TOKEN", "123:abc")
    env = {}
    assert vault.apply(env) == ["TELEGRAM_BOT_TOKEN"] and env["TELEGRAM_BOT_TOKEN"] == "123:abc"  # nosec B101


def test_the_environment_still_wins():
    vault.put("XMPP_PASSWORD", "from-vault")
    env = {"XMPP_PASSWORD": "from-env"}
    assert vault.apply(env) == [] and env["XMPP_PASSWORD"] == "from-env"  # nosec B101


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows only")
def test_the_value_is_not_in_the_file_in_plain_text(data_folder):
    vault.put("X_API_SECRET", "very-secret-value-1234")
    raw = (data_folder / "vault.dpapi").read_bytes()
    assert b"very-secret-value-1234" not in raw and b"X_API_SECRET" not in raw  # nosec B101


def test_bad_names_and_values_are_refused():
    for name, value in (("lowercase", "x"), ("A", "x"), ("OK_NAME", ""), ("OK_NAME", "two\nlines")):
        with pytest.raises(ValueError):
            vault.put(name, value)
    assert vault.names() == []  # nosec B101


def test_remove_and_list_show_names_only(capsys):
    vault.put("NOSTR_SECRET", "nsec1abc")
    assert vault.run(["list"]) == 0  # nosec B101
    shown = capsys.readouterr().out
    assert "NOSTR_SECRET" in shown and "nsec1abc" not in shown  # nosec B101
    assert vault.remove("NOSTR_SECRET") and not vault.remove("NOSTR_SECRET")  # nosec B101


def test_set_reads_the_value_from_input_not_the_command_line(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("piped-value\n"))
    assert vault.run(["set", "IMAP_PASSWORD"]) == 0  # nosec B101
    env = {}
    vault.apply(env)
    assert env == {"IMAP_PASSWORD": "piped-value"}  # nosec B101


def test_an_unreadable_vault_does_not_stop_the_start(monkeypatch):
    def broken(name):
        raise OSError("cannot decrypt")

    monkeypatch.setattr(secret_store, "load_json", broken)
    assert vault.apply({}) == []  # nosec B101
