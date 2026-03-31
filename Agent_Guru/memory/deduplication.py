"""Deduplication Engine.

Detects and merges semantically similar entities, preferences, and experiences.

Similarity thresholds:
  >= 0.85  → automatic merge
  0.70-0.85 → flagged for review
  < 0.70   → distinct items

Time Complexity:
  - calculate_similarity: O(|attrs|)
  - detect_duplicates: O(n²) over items (acceptable for n < 10K)
  - merge: O(1) amortized
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from Agent_Guru.memory.models import (
    DuplicationCandidate,
    Entity,
    Experience,
    ItemType,
    MergeResult,
    Preference,
)

logger = logging.getLogger(__name__)


class DeduplicationEngine:
    """Semantic deduplication for entities, preferences, and experiences."""

    def __init__(
        self,
        auto_merge_threshold: float = 0.85,
        review_threshold: float = 0.70,
    ) -> None:
        self.auto_merge_threshold = auto_merge_threshold
        self.review_threshold = review_threshold
        # Merge history: merged_id -> MergeResult
        self._merge_history: dict[UUID, MergeResult] = {}

    # ------------------------------------------------------------------
    # Similarity calculations
    # ------------------------------------------------------------------

    def _attribute_overlap(self, a: dict[str, Any], b: dict[str, Any]) -> float:
        """Jaccard similarity over attribute keys and values."""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        common_keys = keys_a & keys_b
        if not common_keys:
            return 0.0
        matching = sum(1 for k in common_keys if str(a[k]) == str(b[k]))
        union = len(keys_a | keys_b)
        return matching / union

    def calculate_entity_similarity(self, e1: Entity, e2: Entity) -> tuple[float, dict[str, float]]:
        """Compute similarity between two entities.

        Returns (overall_score, breakdown).
        """
        attr_sim = self._attribute_overlap(e1.attributes, e2.attributes)
        type_sim = 1.0 if e1.type == e2.type else 0.0
        # Weighted combination
        score = 0.7 * attr_sim + 0.3 * type_sim
        return score, {"attribute_overlap": attr_sim, "type_match": type_sim}

    def calculate_preference_similarity(self, p1: Preference, p2: Preference) -> tuple[float, dict[str, float]]:
        """Compute similarity between two preferences."""
        if p1.user_id != p2.user_id:
            return 0.0, {"user_match": 0.0}
        type_sim = 1.0 if p1.preference_type == p2.preference_type else 0.0
        ctx_sim = self._attribute_overlap(dict(p1.context), dict(p2.context))
        val_sim = 1.0 if str(p1.value) == str(p2.value) else 0.0
        score = 0.3 * type_sim + 0.4 * ctx_sim + 0.3 * val_sim
        return score, {"type_match": type_sim, "context_overlap": ctx_sim, "value_match": val_sim}

    def calculate_experience_similarity(self, ex1: Experience, ex2: Experience) -> tuple[float, dict[str, float]]:
        """Compute similarity between two experiences."""
        type_sim = 1.0 if ex1.task_type == ex2.task_type else 0.0
        outcome_sim = 1.0 - abs(ex1.success_score - ex2.success_score)
        # Action sequence similarity: compare action types
        acts1 = [a.action_type for a in ex1.execution_trace.actions]
        acts2 = [a.action_type for a in ex2.execution_trace.actions]
        action_sim = self._sequence_similarity(acts1, acts2)
        score = 0.3 * type_sim + 0.3 * action_sim + 0.4 * outcome_sim
        return score, {"type_match": type_sim, "action_sim": action_sim, "outcome_sim": outcome_sim}

    def _sequence_similarity(self, s1: list[str], s2: list[str]) -> float:
        """Normalized edit distance similarity."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        # Simple LCS-based similarity
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        lcs = dp[m][n]
        return 2 * lcs / (m + n)

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def detect_entity_duplicates(
        self, entities: list[Entity], threshold: float | None = None
    ) -> list[DuplicationCandidate]:
        """Find pairs of entities above the similarity threshold."""
        threshold = threshold if threshold is not None else self.review_threshold
        candidates: list[DuplicationCandidate] = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                score, breakdown = self.calculate_entity_similarity(entities[i], entities[j])
                if score >= threshold:
                    candidates.append(
                        DuplicationCandidate(
                            item_type=ItemType.ENTITY,
                            item_id_1=entities[i].id,
                            item_id_2=entities[j].id,
                            similarity_score=score,
                            similarity_breakdown=breakdown,
                        )
                    )
        return candidates

    def detect_preference_duplicates(
        self, preferences: list[Preference], threshold: float | None = None
    ) -> list[DuplicationCandidate]:
        threshold = threshold if threshold is not None else self.review_threshold
        candidates: list[DuplicationCandidate] = []
        for i in range(len(preferences)):
            for j in range(i + 1, len(preferences)):
                score, breakdown = self.calculate_preference_similarity(preferences[i], preferences[j])
                if score >= threshold:
                    candidates.append(
                        DuplicationCandidate(
                            item_type=ItemType.PREFERENCE,
                            item_id_1=preferences[i].id,
                            item_id_2=preferences[j].id,
                            similarity_score=score,
                            similarity_breakdown=breakdown,
                        )
                    )
        return candidates

    def detect_experience_duplicates(
        self, experiences: list[Experience], threshold: float | None = None
    ) -> list[DuplicationCandidate]:
        threshold = threshold if threshold is not None else self.review_threshold
        candidates: list[DuplicationCandidate] = []
        for i in range(len(experiences)):
            for j in range(i + 1, len(experiences)):
                score, breakdown = self.calculate_experience_similarity(experiences[i], experiences[j])
                if score >= threshold:
                    candidates.append(
                        DuplicationCandidate(
                            item_type=ItemType.EXPERIENCE,
                            item_id_1=experiences[i].id,
                            item_id_2=experiences[j].id,
                            similarity_score=score,
                            similarity_breakdown=breakdown,
                        )
                    )
        return candidates

    # ------------------------------------------------------------------
    # Merge operations
    # ------------------------------------------------------------------

    def merge_entities(self, e1: Entity, e2: Entity) -> tuple[Entity, MergeResult]:
        """Merge e2 into e1. Returns merged entity and result record."""
        merged_attrs = {**e2.attributes, **e1.attributes}  # e1 wins on conflict
        merged = e1.model_copy(
            update={
                "attributes": merged_attrs,
                "confidence": max(e1.confidence, e2.confidence),
                "versions": e1.versions + e2.versions,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )
        result = MergeResult(
            merged_id=merged.id,
            source_ids=[e1.id, e2.id],
            preserved_data={"attributes": merged_attrs},
        )
        self._merge_history[result.merged_id] = result
        logger.debug("merge_entities %s + %s -> %s", e1.id, e2.id, merged.id)
        return merged, result

    def merge_preferences(self, p1: Preference, p2: Preference) -> tuple[Preference, MergeResult]:
        """Merge p2 into p1. Combines evidence lists, updates confidence."""
        combined_evidence = p1.evidence + p2.evidence
        new_confidence = min(1.0, (p1.confidence + p2.confidence) / 2 + 0.05)
        merged = p1.model_copy(
            update={
                "evidence": combined_evidence,
                "confidence": new_confidence,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )
        result = MergeResult(
            merged_id=merged.id,
            source_ids=[p1.id, p2.id],
            preserved_data={"evidence_count": len(combined_evidence)},
        )
        self._merge_history[result.merged_id] = result
        return merged, result

    def merge_experiences(self, ex1: Experience, ex2: Experience) -> tuple[Experience, MergeResult]:
        """Merge ex2 into ex1. Combines patterns, updates success score."""
        combined_patterns = list(set(ex1.patterns + ex2.patterns))
        avg_score = (ex1.success_score + ex2.success_score) / 2
        merged = ex1.model_copy(
            update={
                "patterns": combined_patterns,
                "success_score": avg_score,
                "causal_chain": ex1.causal_chain + ex2.causal_chain,
            }
        )
        result = MergeResult(
            merged_id=merged.id,
            source_ids=[ex1.id, ex2.id],
            preserved_data={"patterns": combined_patterns, "success_score": avg_score},
        )
        self._merge_history[result.merged_id] = result
        return merged, result

    def get_merge_history(self) -> list[MergeResult]:
        return list(self._merge_history.values())
