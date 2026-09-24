"""Database initialization script for the Memory System.

Run once before first deployment to create indexes and schema.
Usage: python -m Agent_Guru.memory.scripts.init_db
"""

import logging
import os

from Agent_Guru.memory.config import Neo4jConfig

logger = logging.getLogger(__name__)


def init_neo4j() -> None:
    """Create Neo4j constraints and indexes."""
    try:
        from neo4j import GraphDatabase  # type: ignore[import]

        # SECURITY FIX: this read NEO4J_PASSWORD itself with a fallback to the
        # literal "password", a second copy of the default Neo4jConfig had, so
        # running the script without the variable sent that guessable
        # password to whatever server NEO4J_URI named. Neo4jConfig.auth() is
        # now the one place credentials come from, and it raises, naming
        # NEO4J_PASSWORD, before any connection is attempted.
        cfg = Neo4jConfig()
        driver = GraphDatabase.driver(cfg.uri, auth=cfg.auth())
        with driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            )
            session.run("CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)")
        driver.close()
        logger.info("Neo4j initialized")
    except Exception:
        logger.exception("Neo4j init skipped")


def init_mongo() -> None:
    """Create MongoDB indexes."""
    try:
        from pymongo import MongoClient  # type: ignore[import]

        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "agent_guru_memory")
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[db_name]
        db.preferences.create_index([("user_id", 1), ("preference_type", 1)])
        db.experiences.create_index([("task_type", 1), ("success_score", -1)])
        db.personalities.create_index([("user_id", 1)], unique=True)
        client.close()
        logger.info("MongoDB initialized")
    except Exception:
        logger.exception("MongoDB init skipped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_neo4j()
    init_mongo()
