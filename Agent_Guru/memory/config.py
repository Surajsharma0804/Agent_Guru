"""Configuration management for the Memory System.

Supports multiple environments via MEMORY_ENV env var: dev, staging, prod.
All values can be overridden via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


class Neo4jCredentialsNotConfiguredError(RuntimeError):
    """NEO4J_PASSWORD is not set, so there is no credential to connect with."""


@dataclass
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    # SECURITY FIX: this fell back to the literal "password" when NEO4J_PASSWORD
    # was unset, so a deployment that forgot the variable connected with the
    # most commonly guessed database password there is, and nothing said the
    # value had not come from the operator. Unset now means None, and auth()
    # refuses to hand out credentials.
    #
    # Reading the variable here does not raise, because MemoryConfig() is
    # built on every desktop start (main.py, core/agent_guru.py) and by the
    # memory container's healthcheck, and none of those connect to Neo4j.
    # Failing there would break users who never use Neo4j. The check belongs
    # at the point credentials are actually needed.
    password: str | None = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD") or None)
    max_connection_pool_size: int = 50

    def auth(self) -> tuple[str, str]:
        """Return (user, password) for the Neo4j driver.

        Raises:
            Neo4jCredentialsNotConfiguredError: If NEO4J_PASSWORD is unset or
                empty. The message names the variable and says what to set.

        """
        if not self.password:
            raise Neo4jCredentialsNotConfiguredError(
                "NEO4J_PASSWORD is not set. There is no default Neo4j password. "
                "Set NEO4J_PASSWORD to the password of the Neo4j user "
                f"'{self.user}' (NEO4J_USER) on {self.uri} (NEO4J_URI).",
            )
        return (self.user, self.password)


@dataclass
class MongoConfig:
    uri: str = field(default_factory=lambda: os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    database: str = field(default_factory=lambda: os.getenv("MONGO_DB", "agent_guru_memory"))
    max_pool_size: int = 50


@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = 6379
    db: int = 0
    max_connections: int = 50


@dataclass
class GitHubSyncConfig:
    repository_url: str = field(default_factory=lambda: os.getenv("GITHUB_REPO_URL", ""))
    branch: str = "main"
    auth_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    batch_window_ms: int = 5000
    max_retries: int = 5
    retry_backoff_ms: int = 100


@dataclass
class DeduplicationConfig:
    auto_merge_threshold: float = 0.85
    review_threshold: float = 0.70
    batch_size: int = 100


@dataclass
class MemoryConfig:
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    mongo: MongoConfig = field(default_factory=MongoConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    github_sync: GitHubSyncConfig = field(default_factory=GitHubSyncConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    # Preference temporal decay half-life in seconds (default: 30 days)
    preference_decay_lambda: float = 2.67e-7
    # Personality consistency max change per update
    personality_max_change: float = 0.1
    # Verification required before storage
    require_verification: bool = True


def load_config(env: str | None = None) -> MemoryConfig:
    """Load MemoryConfig for the given environment (dev/staging/prod).

    Environment-specific defaults can be extended here; all values
    are still overridable via environment variables.
    """
    env = env or os.getenv("MEMORY_ENV", "dev")
    cfg = MemoryConfig()
    if env == "prod":
        cfg.require_verification = True
        cfg.deduplication.auto_merge_threshold = 0.90
    elif env == "staging":
        cfg.require_verification = True
    # dev: defaults as-is
    return cfg
