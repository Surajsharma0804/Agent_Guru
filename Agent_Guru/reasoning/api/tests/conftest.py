"""Fixtures for the reasoning API tests."""

import secrets

import pytest


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Give every test in this package its own random JWT_SECRET.

    auth.py no longer falls back to a built-in secret, so these tests would
    otherwise need the person running them to export one. This does not
    reopen the hole the fallback was: it lives in a test-only conftest that
    pytest loads only for this directory, production code has no path that
    reaches it, and the value is freshly random for each test, so it is never
    a known string and no test can pass by matching one. Tests that need the
    secret to be missing remove it with monkeypatch.delenv.
    """
    secret = secrets.token_urlsafe(48)
    monkeypatch.setenv("JWT_SECRET", secret)
    return secret
