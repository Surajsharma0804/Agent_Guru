"""Tests for the database initialization script.

init_neo4j() used to read NEO4J_PASSWORD with a fallback to the literal
"password", so running it without the variable sent that guessable password
to whatever server NEO4J_URI named.
"""

import logging
import sys
import types

import pytest

from Agent_Guru.memory.scripts import init_db


@pytest.fixture
def driver_calls(monkeypatch):
    """Replace the neo4j package with one that records driver() calls."""
    calls = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run(self, query):
            pass

    class _Driver:
        def session(self):
            return _Session()

        def close(self):
            pass

    class _GraphDatabase:
        @staticmethod
        def driver(uri, auth):
            calls.append((uri, auth))
            return _Driver()

    monkeypatch.setitem(sys.modules, "neo4j", types.SimpleNamespace(GraphDatabase=_GraphDatabase))
    return calls


class TestInitNeo4jCredentials:
    def test_unset_password_is_never_sent_to_the_server(self, monkeypatch, driver_calls):
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        init_db.init_neo4j()

        assert driver_calls == []  # nosec B101

    def test_unset_password_is_reported_by_name(self, monkeypatch, driver_calls, caplog):
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        with caplog.at_level(logging.ERROR, logger=init_db.__name__):
            init_db.init_neo4j()

        assert "NEO4J_PASSWORD is not set" in caplog.text  # nosec B101

    def test_configured_credentials_are_used(self, monkeypatch, driver_calls):
        monkeypatch.setenv("NEO4J_URI", "bolt://graph.internal:7687")
        monkeypatch.setenv("NEO4J_USER", "graph_admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "operator-chosen")  # nosec B105

        init_db.init_neo4j()

        assert driver_calls == [  # nosec B101
            ("bolt://graph.internal:7687", ("graph_admin", "operator-chosen")),
        ]
