"""Experience Repository.

Stores complete task execution traces with causal analysis and pattern recognition.

Similarity formula:
  combined = 0.4 * action_sim + 0.3 * state_sim + 0.3 * outcome_sim
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from Agent_Guru.memory.models import (
    CausalLink,
    ExecutionTrace,
    Experience,
    ExperienceQuery,
    Pattern,
    PatternAbstraction,
    PatternType,
)

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class ExperienceRepository:
    """In-memory experience store with similarity search and pattern recognition."""

    def __init__(self) -> None:
        # experience_id -> Experience
        self._experiences: dict[UUID, Experience] = {}
        # task_type -> list[experience_id]
        self._by_task_type: dict[str, list[UUID]] = defaultdict(list)
        # pattern_id -> Pattern
        self._patterns: dict[UUID, Pattern] = {}

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store_experience(self, experience: Experience) -> UUID:
        """Store a complete experience with trace."""
        exp = experience.model_copy(deep=True)
        self._experiences[exp.id] = exp
        self._by_task_type[exp.task_type].append(exp.id)
        logger.debug("store_experience id=%s task=%s", exp.id, exp.task_type)
        return exp.id

    def get_experience(self, experience_id: UUID) -> Experience | None:
        exp = self._experiences.get(experience_id)
        return exp.model_copy(deep=True) if exp else None

    # ------------------------------------------------------------------
    # Causal extraction
    # ------------------------------------------------------------------

    def extract_causal_links(self, trace: ExecutionTrace) -> list[CausalLink]:
        """Extract causal links via temporal correlation between actions and states."""
        links: list[CausalLink] = []
        actions = sorted(trace.actions, key=lambda a: a.timestamp)
        states = sorted(trace.states, key=lambda s: s.timestamp)

        for action in actions:
            # Find states that occurred after this action
            subsequent_states = [s for s in states if s.timestamp > action.timestamp]
            if not subsequent_states:
                continue
            # Nearest subsequent state is most likely caused by this action
            nearest = min(
                subsequent_states,
                key=lambda s: (s.timestamp - action.timestamp).total_seconds(),
            )
            # Causal strength inversely proportional to time gap
            gap = (nearest.timestamp - action.timestamp).total_seconds()
            strength = max(0.1, 1.0 / (1.0 + gap))
            links.append(
                CausalLink(
                    cause_action_id=action.action_id,
                    effect_state_id=nearest.state_id,
                    causal_strength=min(1.0, strength),
                    explanation=f"Action {action.action_type} preceded state change by {gap:.2f}s",
                ),
            )
        return links

    # ------------------------------------------------------------------
    # Similarity and retrieval
    # ------------------------------------------------------------------

    def _action_sequence_similarity(self, t1: ExecutionTrace, t2: ExecutionTrace) -> float:
        """LCS-based similarity of action type sequences."""
        s1 = [a.action_type for a in t1.actions]
        s2 = [a.action_type for a in t2.actions]
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return 2 * dp[m][n] / (m + n)

    def _state_similarity(self, t1: ExecutionTrace, t2: ExecutionTrace) -> float:
        """Key overlap between final states."""
        if not t1.states and not t2.states:
            return 1.0
        if not t1.states or not t2.states:
            return 0.0
        vars1 = t1.states[-1].variables
        vars2 = t2.states[-1].variables
        if not vars1 and not vars2:
            return 1.0
        if not vars1 or not vars2:
            return 0.0
        keys1, keys2 = set(vars1.keys()), set(vars2.keys())
        common = keys1 & keys2
        matching = sum(1 for k in common if str(vars1[k]) == str(vars2[k]))
        return matching / len(keys1 | keys2)

    def calculate_similarity(self, ex1: Experience, ex2: Experience) -> float:
        """Combined similarity: 0.4*action + 0.3*state + 0.3*outcome."""
        action_sim = self._action_sequence_similarity(ex1.execution_trace, ex2.execution_trace)
        state_sim = self._state_similarity(ex1.execution_trace, ex2.execution_trace)
        outcome_sim = 1.0 - abs(ex1.success_score - ex2.success_score)
        return 0.4 * action_sim + 0.3 * state_sim + 0.3 * outcome_sim

    def query_similar_experiences(
        self,
        query: ExperienceQuery,
        reference: Experience,
    ) -> list[Experience]:
        """Return experiences ranked by similarity to reference."""
        candidates = list(self._experiences.values())
        if query.task_type:
            candidates = [e for e in candidates if e.task_type == query.task_type]
        if not query.include_failures:
            candidates = [e for e in candidates if e.success]
        candidates = [e for e in candidates if e.success_score >= query.min_success_score]
        # Exclude the reference itself
        candidates = [e for e in candidates if e.id != reference.id]

        scored = [(e, self.calculate_similarity(reference, e)) for e in candidates]
        scored = [(e, s) for e, s in scored if s >= query.similarity_threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e.model_copy(deep=True) for e, _ in scored[: query.max_results]]

    # ------------------------------------------------------------------
    # Pattern recognition
    # ------------------------------------------------------------------

    def identify_patterns(self, experiences: list[Experience]) -> list[Pattern]:
        """Find common action sequences across experiences."""
        # Group by action type sequence
        seq_groups: dict[str, list[UUID]] = defaultdict(list)
        for exp in experiences:
            seq = ",".join(a.action_type for a in exp.execution_trace.actions)
            if seq:
                seq_groups[seq].append(exp.id)

        patterns: list[Pattern] = []
        for seq, exp_ids in seq_groups.items():
            if len(exp_ids) < 2:  # noqa: PLR2004 - Small integer threshold

                continue
            action_types = seq.split(",")
            # Calculate success rate for this pattern
            successes = sum(
                1
                for eid in exp_ids
                if self._experiences.get(eid) and self._experiences[eid].success
            )
            success_rate = successes / len(exp_ids)
            pattern = Pattern(
                pattern_type=PatternType.ACTION_SEQUENCE,
                abstraction=PatternAbstraction(action_types=action_types),
                occurrences=exp_ids,
                success_rate=success_rate,
            )
            self._patterns[pattern.pattern_id] = pattern
            patterns.append(pattern)
            # Link experiences to this pattern
            for eid in exp_ids:
                exp = self._experiences.get(eid)
                if exp and str(pattern.pattern_id) not in exp.patterns:
                    exp.patterns.append(str(pattern.pattern_id))
        return patterns

    def get_success_factors(self, experience_id: UUID) -> list[CausalLink]:
        """Return causal links for an experience."""
        exp = self._experiences.get(experience_id)
        if exp is None:
            return []
        return list(exp.causal_chain)

    # ------------------------------------------------------------------
    # Temporal ordering
    # ------------------------------------------------------------------

    def get_experiences_by_time(
        self,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[Experience]:
        """Return experiences in temporal order."""
        exps = list(self._experiences.values())
        if task_type:
            exps = [e for e in exps if e.task_type == task_type]
        exps.sort(key=lambda e: e.start_time)
        return [e.model_copy(deep=True) for e in exps[:limit]]

    @property
    def experience_count(self) -> int:
        return len(self._experiences)
