"""Tests for Memory System configuration.

Neo4jConfig used to fall back to the literal password "password" when
NEO4J_PASSWORD was unset, so a deployment that forgot the variable connected
with the most commonly guessed database password and nothing said so.
"""

import pytest

from Agent_Guru.memory.config import MemoryConfig, Neo4jConfig, load_config


class TestNeo4jPassword:
    def test_unset_password_has_no_default(self, monkeypatch):
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        assert Neo4jConfig().password is None  # nosec B101

    def test_unset_password_refuses_to_produce_credentials(self, monkeypatch):
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        with pytest.raises(RuntimeError, match="NEO4J_PASSWORD is not set"):
            Neo4jConfig().auth()

    def test_empty_password_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("NEO4J_PASSWORD", "")

        with pytest.raises(RuntimeError, match="NEO4J_PASSWORD is not set"):
            Neo4jConfig().auth()

    def test_error_names_what_to_set(self, monkeypatch):
        from Agent_Guru.memory.config import Neo4jCredentialsNotConfiguredError

        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        monkeypatch.setenv("NEO4J_USER", "graph_admin")
        monkeypatch.setenv("NEO4J_URI", "bolt://graph.internal:7687")

        with pytest.raises(Neo4jCredentialsNotConfiguredError) as exc_info:
            Neo4jConfig().auth()

        message = str(exc_info.value)
        assert "Set NEO4J_PASSWORD" in message  # nosec B101
        assert "graph_admin" in message  # nosec B101
        assert "bolt://graph.internal:7687" in message  # nosec B101

    def test_configured_password_is_used(self, monkeypatch):
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "operator-chosen")  # nosec B105

        assert Neo4jConfig().auth() == ("neo4j", "operator-chosen")  # nosec B101

    def test_config_still_builds_without_a_password(self, monkeypatch):
        """Desktop startup and the container healthcheck never connect to Neo4j.

        MemoryConfig() is built on every desktop start and load_config() is the
        memory container's healthcheck, so a missing password must not break
        either of them.
        """
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        assert MemoryConfig().neo4j.password is None  # nosec B101
        assert load_config("prod").neo4j.password is None  # nosec B101
