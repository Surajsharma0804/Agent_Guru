"""Core data models for the Memory System.

All models use Pydantic v2 for validation. Confidence scores are
constrained to [0.0, 1.0]. All identifiers are UUIDs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(str, Enum):
    PERSON = "person"
    PLACE = "place"
    CONCEPT = "concept"
    OBJECT = "object"
    EVENT = "event"
    OTHER = "other"


class RelationshipType(str, Enum):
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    CAUSES = "causes"
    PRECEDES = "precedes"
    SIMILAR_TO = "similar_to"
    OPPOSITE_OF = "opposite_of"
    INSTANCE_OF = "instance_of"
    OTHER = "other"


class PreferenceType(str, Enum):
    COMMUNICATION_STYLE = "communication_style"
    TOPIC = "topic"
    FORMAT = "format"
    TIMING = "timing"
    DETAIL_LEVEL = "detail_level"
    OTHER = "other"


class EvidenceType(str, Enum):
    EXPLICIT_STATEMENT = "explicit_statement"
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    FEEDBACK = "feedback"


class SignalType(str, Enum):
    EXPLICIT_CHOICE = "explicit_choice"
    IMPLICIT_BEHAVIOR = "implicit_behavior"
    FEEDBACK = "feedback"
    CORRECTION = "correction"


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class PatternType(str, Enum):
    ACTION_SEQUENCE = "action_sequence"
    STATE_TRANSITION = "state_transition"
    OUTCOME_PATTERN = "outcome_pattern"


class ItemType(str, Enum):
    ENTITY = "entity"
    PREFERENCE = "preference"
    EXPERIENCE = "experience"


class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricType(str, Enum):
    # Knowledge Graph
    ENTITY_COUNT = "entity_count"
    RELATIONSHIP_COUNT = "relationship_count"
    GRAPH_DENSITY = "graph_density"
    QUERY_ACCURACY = "query_accuracy"
    QUERY_LATENCY = "query_latency"
    # Preference
    PREFERENCE_PREDICTION_ACCURACY = "preference_prediction_accuracy"
    AVERAGE_CONFIDENCE = "average_confidence"
    PREFERENCE_SHIFT_RATE = "preference_shift_rate"
    # Experience
    EXPERIENCE_COUNT = "experience_count"
    PATTERN_COUNT = "pattern_count"
    RETRIEVAL_RELEVANCE = "retrieval_relevance"
    # Personality
    PERSONALITY_CONSISTENCY = "personality_consistency"
    USER_SATISFACTION = "user_satisfaction"
    ADAPTATION_RATE = "adaptation_rate"
    # System
    DEDUPLICATION_RATE = "deduplication_rate"
    GITHUB_SYNC_SUCCESS_RATE = "github_sync_success_rate"
    MEMORY_USAGE = "memory_usage"
    OPERATION_THROUGHPUT = "operation_throughput"


# ---------------------------------------------------------------------------
# Confidence validator (reusable)
# ---------------------------------------------------------------------------


def _validate_confidence(v: float) -> float:
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"confidence must be in [0.0, 1.0], got {v}")
    return v


# ---------------------------------------------------------------------------
# Knowledge Graph models
# ---------------------------------------------------------------------------


class EntityVersion(BaseModel):
    version_id: UUID = Field(default_factory=uuid4)
    attributes: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    confidence: float = Field(default=1.0)
    source: str = ""

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: EntityType = EntityType.OTHER
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=1.0)
    source: str = ""
    versions: list[EntityVersion] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class Relationship(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType = RelationshipType.RELATED_TO
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime | None = None
    bidirectional: bool = False

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class TimeRange(BaseModel):
    start: datetime
    end: datetime


class SemanticQuery(BaseModel):
    query_type: str = "ENTITY_LOOKUP"
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    max_depth: int = 3
    min_confidence: float = 0.0
    temporal_filter: TimeRange | None = None

    @field_validator("min_confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class QueryResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    relevance_scores: dict[str, float] = Field(default_factory=dict)
    execution_time_ms: int = 0


# ---------------------------------------------------------------------------
# Preference Learning models
# ---------------------------------------------------------------------------


class PreferenceEvidence(BaseModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    evidence_type: EvidenceType = EvidenceType.FEEDBACK
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    weight: float = Field(default=1.0)
    description: str = ""

    @field_validator("weight")
    @classmethod
    def check_weight(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(f"weight must be >= 0.0, got {v}")
        return v


class Preference(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    preference_type: PreferenceType = PreferenceType.OTHER
    context: dict[str, str] = Field(default_factory=dict)
    value: Any = None
    confidence: float = Field(default=0.5)
    evidence: list[PreferenceEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_confirmed: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class PreferenceSignal(BaseModel):
    user_id: UUID
    signal_type: SignalType = SignalType.FEEDBACK
    context: dict[str, str] = Field(default_factory=dict)
    value: Any = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PreferenceQuery(BaseModel):
    user_id: UUID
    preference_type: PreferenceType | None = None
    context: dict[str, str] = Field(default_factory=dict)
    min_confidence: float = 0.0

    @field_validator("min_confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


# ---------------------------------------------------------------------------
# Experience Repository models
# ---------------------------------------------------------------------------


class Action(BaseModel):
    action_id: UUID = Field(default_factory=uuid4)
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0


class State(BaseModel):
    state_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    variables: dict[str, Any] = Field(default_factory=dict)


class CausalLink(BaseModel):
    cause_action_id: UUID
    effect_state_id: UUID
    causal_strength: float = Field(default=0.5)
    explanation: str = ""

    @field_validator("causal_strength")
    @classmethod
    def check_strength(cls, v: float) -> float:
        return _validate_confidence(v)


class ExecutionTrace(BaseModel):
    actions: list[Action] = Field(default_factory=list)
    states: list[State] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)


class Experience(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_type: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    success_score: float = Field(default=1.0)
    execution_trace: ExecutionTrace = Field(default_factory=ExecutionTrace)
    causal_chain: list[CausalLink] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("success_score")
    @classmethod
    def check_score(cls, v: float) -> float:
        return _validate_confidence(v)


class ExperienceQuery(BaseModel):
    task_type: str | None = None
    similarity_threshold: float = 0.5
    min_success_score: float = 0.0
    max_results: int = 10
    include_failures: bool = False

    @field_validator("similarity_threshold", "min_success_score")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)


class PatternAbstraction(BaseModel):
    action_types: list[str] = Field(default_factory=list)
    state_keys: list[str] = Field(default_factory=list)
    description: str = ""


class Pattern(BaseModel):
    pattern_id: UUID = Field(default_factory=uuid4)
    pattern_type: PatternType = PatternType.ACTION_SEQUENCE
    abstraction: PatternAbstraction = Field(default_factory=PatternAbstraction)
    occurrences: list[UUID] = Field(default_factory=list)
    success_rate: float = Field(default=0.0)

    @field_validator("success_rate")
    @classmethod
    def check_rate(cls, v: float) -> float:
        return _validate_confidence(v)


# ---------------------------------------------------------------------------
# Personality Evolution models
# ---------------------------------------------------------------------------


class PersonalityParameters(BaseModel):
    formality: float = Field(default=0.5)
    verbosity: float = Field(default=0.5)
    humor: float = Field(default=0.5)
    technical_depth: float = Field(default=0.5)
    empathy: float = Field(default=0.5)
    proactivity: float = Field(default=0.5)

    @field_validator("formality", "verbosity", "humor", "technical_depth", "empathy", "proactivity")
    @classmethod
    def check_param(cls, v: float) -> float:
        return _validate_confidence(v)


class PersonalityMetrics(BaseModel):
    consistency_score: float = Field(default=1.0)
    user_satisfaction: float = Field(default=0.5)
    interaction_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("consistency_score", "user_satisfaction")
    @classmethod
    def check_score(cls, v: float) -> float:
        return _validate_confidence(v)


class PersonalitySnapshot(BaseModel):
    version: int
    parameters: PersonalityParameters
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trigger: str = ""


class PersonalityProfile(BaseModel):
    user_id: UUID
    version: int = 1
    parameters: PersonalityParameters = Field(default_factory=PersonalityParameters)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metrics: PersonalityMetrics = Field(default_factory=PersonalityMetrics)
    evolution_history: list[PersonalitySnapshot] = Field(default_factory=list)


class InteractionFeedback(BaseModel):
    user_id: UUID
    interaction_id: UUID = Field(default_factory=uuid4)
    feedback_type: FeedbackType = FeedbackType.NEUTRAL
    feedback_aspects: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Deduplication models
# ---------------------------------------------------------------------------


class MergeStrategy(BaseModel):
    strategy_type: str = "UNION"
    conflict_resolution: str = "WEIGHTED_AVERAGE"
    preserve_history: bool = True


class DuplicationCandidate(BaseModel):
    item_type: ItemType
    item_id_1: UUID
    item_id_2: UUID
    similarity_score: float
    similarity_breakdown: dict[str, float] = Field(default_factory=dict)
    merge_strategy: MergeStrategy = Field(default_factory=MergeStrategy)

    @field_validator("similarity_score")
    @classmethod
    def check_score(cls, v: float) -> float:
        return _validate_confidence(v)


class MergeResult(BaseModel):
    merged_id: UUID
    source_ids: list[UUID]
    merge_timestamp: datetime = Field(default_factory=datetime.utcnow)
    preserved_data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GitHub Sync models
# ---------------------------------------------------------------------------


class SyncOperation(BaseModel):
    operation_id: UUID = Field(default_factory=uuid4)
    operation_type: str = "UPDATE"
    file_path: str = "README.md"
    content: str = ""
    commit_message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: SyncStatus = SyncStatus.PENDING
    retry_count: int = 0
    last_error: str | None = None


# ---------------------------------------------------------------------------
# Metrics models
# ---------------------------------------------------------------------------


class MetricSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metric_type: MetricType
    value: float
    metadata: dict[str, str] = Field(default_factory=dict)


class Trend(BaseModel):
    metric_type: MetricType
    direction: str = "stable"  # "improving", "degrading", "stable"
    slope: float = 0.0
    data_points: int = 0


class Alert(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    metric_type: MetricType
    threshold: float
    current_value: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Dashboard(BaseModel):
    time_range: TimeRange
    metrics: dict[str, list[MetricSnapshot]] = Field(default_factory=dict)
    alerts: list[Alert] = Field(default_factory=list)
    trends: dict[str, Trend] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Verifier integration models
# ---------------------------------------------------------------------------


class VerificationResult(BaseModel):
    verified: bool
    confidence: float = Field(default=0.0)
    explanation: str = ""
    sources: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return _validate_confidence(v)
