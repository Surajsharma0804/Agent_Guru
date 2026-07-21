"""Knowledge Graph Engine.

Provides entity/relationship storage with temporal versioning,
semantic querying, and referential integrity enforcement.

Uses an in-memory graph for testing/development; swap the
_GraphBackend for a real Neo4j driver in production.

Time Complexity:
  - add_entity: O(1) amortized
  - get_entity: O(1)
  - add_relationship: O(1) amortized
  - query_semantic: O(V + E) graph traversal
  - merge_entities: O(degree(v))
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.memory.models import (
    Entity,
    EntityVersion,
    QueryResult,
    Relationship,
    SemanticQuery,
)

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class KnowledgeGraphError(Exception):
    """Base error for Knowledge Graph operations."""


class EntityNotFoundError(KnowledgeGraphError):
    pass


class ReferentialIntegrityError(KnowledgeGraphError):
    pass


class KnowledgeGraph:
    """In-memory Knowledge Graph with temporal versioning.

    Thread-safe via asyncio locks (single-event-loop assumption).
    Replace _entities / _relationships with Neo4j driver calls for production.
    """

    def __init__(self) -> None:
        # entity_id -> Entity
        self._entities: dict[UUID, Entity] = {}
        # relationship_id -> Relationship
        self._relationships: dict[UUID, Relationship] = {}
        # entity_id -> list of relationship_ids
        self._adj: dict[UUID, list[UUID]] = defaultdict(list)
        # Per-entity lock for optimistic concurrency
        self._entity_locks: dict[UUID, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_lock(self, entity_id: UUID) -> asyncio.Lock:
        if entity_id not in self._entity_locks:
            self._entity_locks[entity_id] = asyncio.Lock()
        return self._entity_locks[entity_id]

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    async def add_entity(self, entity: Entity) -> UUID:
        """Store a new entity. Returns its UUID."""
        async with self._get_or_create_lock(entity.id):
            if entity.id in self._entities:
                # Already exists — create a new version instead
                return await self._create_version(
                    entity.id,
                    entity.attributes,
                    entity.confidence,
                    entity.source,
                )
            self._entities[entity.id] = entity.model_copy(deep=True)
            logger.debug("add_entity id=%s", entity.id)
            return entity.id

    async def _create_version(
        self,
        entity_id: UUID,
        attributes: dict[str, Any],
        confidence: float,
        source: str,
    ) -> UUID:
        existing = self._entities[entity_id]
        # Close the current head version
        if existing.versions:
            existing.versions[-1].valid_until = datetime.now(tz=UTC)
        new_version = EntityVersion(
            attributes=attributes,
            confidence=confidence,
            source=source,
        )
        existing.versions.append(new_version)
        existing.attributes = attributes
        existing.confidence = confidence
        existing.updated_at = datetime.now(tz=UTC)
        return entity_id

    async def update_entity(
        self,
        entity_id: UUID,
        updates: dict[str, Any],
        confidence: float | None = None,
        source: str = "",
    ) -> EntityVersion:
        """Update entity attributes, creating a temporal version."""
        async with self._get_or_create_lock(entity_id):
            if entity_id not in self._entities:
                msg = f"Entity {entity_id} not found"
                raise EntityNotFoundError(msg)
            entity = self._entities[entity_id]
            new_attrs = {**entity.attributes, **updates}
            new_conf = confidence if confidence is not None else entity.confidence
            # Close previous head version
            if entity.versions:
                entity.versions[-1].valid_until = datetime.now(tz=UTC)
            version = EntityVersion(
                attributes=new_attrs,
                confidence=new_conf,
                source=source,
            )
            entity.versions.append(version)
            entity.attributes = new_attrs
            entity.confidence = new_conf
            entity.updated_at = datetime.now(tz=UTC)
            return version

    async def get_entity(self, entity_id: UUID) -> Entity:
        if entity_id not in self._entities:
            msg = f"Entity {entity_id} not found"
            raise EntityNotFoundError(msg)
        return self._entities[entity_id].model_copy(deep=True)

    async def get_entity_history(self, entity_id: UUID) -> list[EntityVersion]:
        if entity_id not in self._entities:
            msg = f"Entity {entity_id} not found"
            raise EntityNotFoundError(msg)
        return list(self._entities[entity_id].versions)

    async def delete_entity(self, entity_id: UUID) -> None:
        """Remove entity and all its relationships."""
        async with self._global_lock:
            if entity_id not in self._entities:
                msg = f"Entity {entity_id} not found"
                raise EntityNotFoundError(msg)
            # Remove all relationships involving this entity
            rel_ids = list(self._adj.get(entity_id, []))
            for rel_id in rel_ids:
                rel = self._relationships.pop(rel_id, None)
                if rel:
                    other = (
                        rel.target_entity_id
                        if rel.source_entity_id == entity_id
                        else rel.source_entity_id
                    )
                    if other in self._adj and rel_id in self._adj[other]:
                        self._adj[other].remove(rel_id)
            self._adj.pop(entity_id, None)
            del self._entities[entity_id]
            self._entity_locks.pop(entity_id, None)

    # ------------------------------------------------------------------
    # Relationship operations
    # ------------------------------------------------------------------

    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Store a relationship. Enforces referential integrity."""
        if relationship.source_entity_id not in self._entities:
            msg = f"Source entity {relationship.source_entity_id} not found"
            raise ReferentialIntegrityError(
                msg,
            )
        if relationship.target_entity_id not in self._entities:
            msg = f"Target entity {relationship.target_entity_id} not found"
            raise ReferentialIntegrityError(
                msg,
            )
        rel = relationship.model_copy(deep=True)
        self._relationships[rel.id] = rel
        self._adj[rel.source_entity_id].append(rel.id)
        if rel.bidirectional:
            self._adj[rel.target_entity_id].append(rel.id)
        return rel.id

    async def get_relationships(self, entity_id: UUID) -> list[Relationship]:
        """Return all relationships for an entity."""
        if entity_id not in self._entities:
            msg = f"Entity {entity_id} not found"
            raise EntityNotFoundError(msg)
        result = []
        for rel_id in self._adj.get(entity_id, []):
            if rel_id in self._relationships:
                result.append(self._relationships[rel_id].model_copy(deep=True))
        return result

    # ------------------------------------------------------------------
    # Semantic query
    # ------------------------------------------------------------------

    async def query_semantic(
        self,
        query: SemanticQuery,
        start_entity_id: UUID | None = None,
    ) -> QueryResult:
        """BFS traversal up to max_depth, filtered by min_confidence.

        Time Complexity: O(V + E)
        """
        start = datetime.now(tz=UTC)
        visited_entities: dict[UUID, float] = {}  # entity_id -> relevance
        visited_rels: set[UUID] = set()

        # Seed: all entities if no start given, else just the start
        seeds = self._resolve_seeds(query, start_entity_id)

        queue: deque[tuple[UUID, int, float]] = deque()
        for seed in seeds:
            if seed in self._entities:
                queue.append((seed, 0, 1.0))

        while queue:
            entity_id, depth, relevance = queue.popleft()
            if entity_id in visited_entities:
                continue
            entity = self._entities.get(entity_id)
            if not self._should_visit_entity(entity, query):
                continue
            visited_entities[entity_id] = relevance * entity.confidence
            if depth < query.max_depth:
                self._expand_neighbors(
                    entity_id, depth, relevance, query,
                    visited_entities, visited_rels, queue,
                )

        elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
        entities = [self._entities[eid].model_copy(deep=True) for eid in visited_entities]
        relationships = [self._relationships[rid].model_copy(deep=True) for rid in visited_rels]
        relevance_scores = {str(eid): score for eid, score in visited_entities.items()}
        return QueryResult(
            entities=entities,
            relationships=relationships,
            relevance_scores=relevance_scores,
            execution_time_ms=elapsed,
        )

    def _resolve_seeds(
        self, query: SemanticQuery, start_entity_id: UUID | None,
    ) -> list[UUID]:
        """Resolve BFS seed entities."""
        if start_entity_id is not None:
            return [start_entity_id]
        return [
            eid for eid, e in self._entities.items() if e.confidence >= query.min_confidence
        ]

    @staticmethod
    def _should_visit_entity(entity: Any, query: SemanticQuery) -> bool:
        """Check if an entity passes all filters for visitation."""
        if entity is None:
            return False
        if entity.confidence < query.min_confidence:
            return False
        if query.temporal_filter and (
            entity.updated_at < query.temporal_filter.start
            or entity.updated_at > query.temporal_filter.end
        ):
            return False
        return True

    def _expand_neighbors(
        self,
        entity_id: UUID,
        depth: int,
        relevance: float,
        query: SemanticQuery,
        visited_entities: dict[UUID, float],
        visited_rels: set[UUID],
        queue: deque,
    ) -> None:
        """Expand BFS to neighbors via relationships."""
        for rel_id in self._adj.get(entity_id, []):
            rel = self._relationships.get(rel_id)
            if rel is None or rel.confidence < query.min_confidence:
                continue
            visited_rels.add(rel_id)
            neighbor = (
                rel.target_entity_id
                if rel.source_entity_id == entity_id
                else rel.source_entity_id
            )
            if neighbor not in visited_entities:
                queue.append((neighbor, depth + 1, relevance * rel.confidence))

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    async def merge_entities(self, entity_id_1: UUID, entity_id_2: UUID) -> UUID:
        """Merge entity_2 into entity_1. Returns surviving entity ID."""
        async with self._global_lock:
            if entity_id_1 not in self._entities:
                msg = f"Entity {entity_id_1} not found"
                raise EntityNotFoundError(msg)
            if entity_id_2 not in self._entities:
                msg = f"Entity {entity_id_2} not found"
                raise EntityNotFoundError(msg)

            e1 = self._entities[entity_id_1]
            e2 = self._entities[entity_id_2]

            # Merge attributes (e1 wins on conflict)
            merged_attrs = {**e2.attributes, **e1.attributes}
            e1.attributes = merged_attrs
            # Preserve e2 versions in e1 history
            e1.versions.extend(e2.versions)
            # Higher confidence wins
            e1.confidence = max(e1.confidence, e2.confidence)
            e1.updated_at = datetime.now(tz=UTC)

            # Re-point ALL relationships referencing e2 to e1
            for stored_rel in self._relationships.values():
                changed = False
                if stored_rel.source_entity_id == entity_id_2:
                    stored_rel.source_entity_id = entity_id_1
                    changed = True
                if stored_rel.target_entity_id == entity_id_2:
                    stored_rel.target_entity_id = entity_id_1
                    changed = True
                if changed and stored_rel.id not in self._adj[entity_id_1]:
                    self._adj[entity_id_1].append(stored_rel.id)

            # Remove e2
            del self._entities[entity_id_2]
            self._adj.pop(entity_id_2, None)
            self._entity_locks.pop(entity_id_2, None)

            return entity_id_1

    # ------------------------------------------------------------------
    # Integrity validation
    # ------------------------------------------------------------------

    async def validate_integrity(self) -> dict[str, Any]:
        """Check for dangling references. Returns report dict."""
        dangling: list[str] = []
        for rel_id, rel in self._relationships.items():
            if rel.source_entity_id not in self._entities:
                dangling.append(f"rel {rel_id}: missing source {rel.source_entity_id}")
            if rel.target_entity_id not in self._entities:
                dangling.append(f"rel {rel_id}: missing target {rel.target_entity_id}")
        return {
            "entity_count": len(self._entities),
            "relationship_count": len(self._relationships),
            "dangling_references": dangling,
            "valid": len(dangling) == 0,
        }

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relationship_count(self) -> int:
        return len(self._relationships)
