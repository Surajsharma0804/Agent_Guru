"""Experience Repository.

Stores complete task execution traces with causal analysis and pattern recognition.

Similarity formula:
  combined = 0.4 * action_sim + 0.3 * state_sim + 0.3 * outcome_sim
"""

from __future__ import annotations

import heapq
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
        """LCS-based similarity of action type sequences.

        SPACE FIX: this allocated the full (m+1) x (n+1) DP table -- O(m*n)
        integers -- when the only value ever read out of it is dp[m][n], the
        LCS length. Each row depends solely on the row above it, so a single
        rolling row is sufficient and the table was pure waste: two execution
        traces of 500 actions each held a quarter of a million list slots for
        one number, and the scattered row allocations defeat cache locality on
        the inner loop as well.

        Space Complexity: O(min(m, n)) -- the sequences are swapped so the row
        is the shorter of the two. Was O(m * n).
        Time Complexity: O(m * n), unchanged. The result is identical.
        """
        s1 = [a.action_type for a in t1.actions]
        s2 = [a.action_type for a in t2.actions]
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        total = len(s1) + len(s2)
        # Iterate the longer sequence, keep a row as long as the shorter one.
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        n = len(s2)

        previous = [0] * (n + 1)
        current = [0] * (n + 1)
        for item in s1:
            for j in range(1, n + 1):
                if item == s2[j - 1]:
                    current[j] = previous[j - 1] + 1
                else:
                    left = current[j - 1]
                    up = previous[j]
                    current[j] = left if left > up else up
            previous, current = current, previous

        return 2 * previous[n] / total

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
        # One pass over the store instead of four successive list rebuilds,
        # and the cheap predicates are checked BEFORE the expensive LCS
        # similarity so a filtered-out experience is never scored at all.
        wants_type = query.task_type
        include_failures = query.include_failures
        min_score = query.min_success_score
        ref_id = reference.id

        scored: list[tuple[float, int, Experience]] = []
        for tiebreak, exp in enumerate(self._experiences.values()):
            if exp.id == ref_id:
                continue
            if wants_type and exp.task_type != wants_type:
                continue
            if not include_failures and not exp.success:
                continue
            if exp.success_score < min_score:
                continue
            similarity = self.calculate_similarity(reference, exp)
            if similarity >= query.similarity_threshold:
                # tiebreak keeps the ordering of equally-similar experiences
                # deterministic and identical to the previous stable sort.
                scored.append((similarity, -tiebreak, exp))

        if query.max_results <= 0:
            return []
        # nlargest is O(k log n) rather than sorting every candidate to take k.
        top = heapq.nlargest(query.max_results, scored, key=lambda item: item[:2])
        return [exp.model_copy(deep=True) for _, _, exp in top]

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
            if len(exp_ids) < 2:
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

    def get_all_experiences(self) -> list[Experience]:
        """Return every stored experience, unfiltered and untruncated.

        Added so callers that need the full set (e.g. aggregating success
        rates across the whole repository) don't have to either reach into
        this class's private `_experiences` dict directly, or use
        `get_experiences_by_time()` and risk silently losing data past its
        default `limit=100`.
        """
        return [e.model_copy(deep=True) for e in self._experiences.values()]

    @property
    def experience_count(self) -> int:
        return len(self._experiences)
