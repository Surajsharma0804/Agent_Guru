"""Configuration management for the Memory System.

Supports multiple environments via MEMORY_ENV env var: dev, staging, prod.
All values can be overridden via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    max_connection_pool_size: int = 50


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
