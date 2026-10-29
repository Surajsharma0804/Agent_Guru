"""The onboarding KeyStore: a master secret the OS keeps, an absolute path, and a checked migration.

It was opened with master_password="" at .guru/onboarding_secrets.db under the working directory,
so anyone holding the file could derive its key, and a different start directory meant a different
store. Every value here is made at run time and none is a real credential.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

import pytest

from Agent_Guru.deployment import onboarding
from Agent_Guru.deployment.onboarding import LLMConfig, OnboardingManager
from Agent_Guru.security import secret_store
from Agent_Guru.security.crypto.errors import KeyStorageError
from Agent_Guru.security.crypto.key_store import KeyStore


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A data folder of its own, and a working directory elsewhere."""
    data = tmp_path / "appdata"
    monkeypatch.setenv("LOCALAPPDATA" if sys.platform == "win32" else "XDG_DATA_HOME", str(data))
    elsewhere = tmp_path / "started_here"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return data / "agent_guru"


@pytest.fixture
def os_credential(monkeypatch):
    """Stands in for the OS credential store: one random master secret per test."""
    kept: dict[str, bytes] = {}

    def credential(name, factory):
        return kept.setdefault(name, factory())

    monkeypatch.setattr(secret_store, "os_credential", credential)
    return kept


def _fake_key() -> str:
    return "fake-" + secrets.token_hex(12)


def test_an_api_key_round_trips_through_the_store(data_dir, os_credential):
    key = _fake_key()
    first = OnboardingManager()
    first._state.llm_config = LLMConfig(provider="openai", api_key=key)
    first._save_state()
    assert key not in (data_dir / "onboarding_state.json").read_text(encoding="utf-8")  # nosec B101
    assert OnboardingManager().get_state().llm_config.api_key == key  # nosec B101


def test_the_store_is_not_opened_with_an_empty_password(data_dir, os_credential):
    key = _fake_key()
    manager = OnboardingManager()
    manager._state.llm_config = LLMConfig(provider="openai", api_key=key)
    manager._save_state()
    anyone = KeyStore(storage_path=str(data_dir / "onboarding_secrets.db"), master_password="")  # nosec B106
    with pytest.raises(KeyStorageError):
        anyone.retrieve_key("onboarding:llm_api_key:openai")
    anyone.close()


def test_a_wrong_secret_cannot_read_the_store(data_dir, os_credential):
    manager = OnboardingManager()
    manager._state.llm_config = LLMConfig(provider="gemini", api_key=_fake_key())
    manager._save_state()
    other = KeyStore(storage_path=str(data_dir / "onboarding_secrets.db"), master_password=secrets.token_hex(32))
    with pytest.raises(KeyStorageError):
        other.retrieve_key("onboarding:llm_api_key:gemini")
    other.close()


def test_with_no_credential_store_no_key_is_kept(data_dir, monkeypatch):
    def none(name, factory):
        raise secret_store.NoCredentialBackend("no operating-system credential store (test)")

    monkeypatch.setattr(secret_store, "os_credential", none)
    seen = []
    monkeypatch.setattr(onboarding.logger, "warning", lambda event, **kw: seen.append(event))
    manager = OnboardingManager()
    key = _fake_key()
    manager._state.llm_config = LLMConfig(provider="openai", api_key=key)
    manager._save_state()
    assert manager._key_store is None and not (data_dir / "onboarding_secrets.db").exists()  # nosec B101
    assert key not in (data_dir / "onboarding_state.json").read_text(encoding="utf-8")  # nosec B101
    assert seen[0] == "onboarding_credentials_not_stored"  # nosec B101  said once, plainly
    assert OnboardingManager().get_state().llm_config.api_key is None  # nosec B101


def test_the_files_are_in_the_data_folder_whatever_the_start_directory(data_dir, os_credential):
    manager = OnboardingManager()
    manager._save_state()
    assert manager._state_path.is_absolute() and manager._state_path.parent == data_dir  # nosec B101
    assert (data_dir / "onboarding_secrets.db").exists()  # nosec B101
    assert not (Path.cwd() / ".guru").exists()  # nosec B101  nothing in the start directory


def test_an_old_store_is_migrated_once_and_left_in_place(data_dir, os_credential, monkeypatch):
    checkout = Path.cwd()  # the test's start directory stands in for both places it may be
    monkeypatch.setattr(onboarding, "__file__", str(checkout / "Agent_Guru" / "deployment" / "onboarding.py"))
    legacy_path = checkout / ".guru" / "onboarding_secrets.db"
    legacy_path.parent.mkdir()
    old = KeyStore(storage_path=str(legacy_path), master_password="")  # nosec B106 - how the old one was made
    key = _fake_key().encode()
    old.store_key("onboarding:llm_api_key:anthropic", key)
    old.close()

    store = OnboardingManager()._key_store
    # The key is now in the new store in the data folder, not read from the old file in place.
    assert Path(store._storage_path).resolve() == (data_dir / "onboarding_secrets.db").resolve()  # nosec B101
    assert store.retrieve_key("onboarding:llm_api_key:anthropic") == key  # nosec B101
    assert legacy_path.exists()  # nosec B101  deleting it is left to the owner
    # A second start does not migrate again over a key changed since.
    store.store_key("onboarding:llm_api_key:anthropic", b"changed")
    store.close()
    assert OnboardingManager()._key_store.retrieve_key("onboarding:llm_api_key:anthropic") == b"changed"  # nosec B101


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is the Windows credential store")
def test_on_windows_the_master_secret_is_kept_by_dpapi(data_dir):
    first = secret_store.os_credential("test_master", lambda: secrets.token_bytes(32))
    assert secret_store.os_credential("test_master", lambda: b"other") == first  # nosec B101
    raw = secret_store.path_for("test_master").read_bytes()
    assert first not in raw  # nosec B101  the file holds the DPAPI-protected form only
