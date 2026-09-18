"""Meta-Learning System for Self-Improvement Engine.

This module implements pattern recognition and strategy recommendation
based on historical task execution data. It identifies generalizable
patterns that predict success or failure and recommends optimal strategies
for new tasks.

Performance Requirements:
- Time Complexity: O(n log n) for pattern clustering
- Space Complexity: O(n) where n is number of task executions
- Pattern extraction: <100ms per task
- Strategy recommendation: <50ms per query

Design Decisions:
- Use scikit-learn for pattern clustering (DBSCAN for density-based clustering)
- NumPy for efficient feature extraction and vectorization
- Incremental learning: update patterns as new data arrives
- Pattern confidence scoring based on occurrence frequency
- GPU acceleration optional but recommended for large datasets

Architecture:
1. Feature Extraction: Extract numerical features from task executions
2. Pattern Clustering: Group similar successful/failed executions
3. Pattern Storage: Persist patterns with confidence scores
4. Strategy Recommendation: Match new tasks to known patterns
5. Incremental Updates: Update patterns as new data arrives

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler


class PatternType(Enum):
    """Types of patterns identified by meta-learner."""

    SUCCESS_PATTERN = "success"
    FAILURE_PATTERN = "failure"


@dataclass
class TaskFeatures:
    """Extracted features from a task execution.

    Features are numerical representations of task characteristics
    used for pattern recognition and clustering.

    Attributes:
        task_type_hash: Hash of task type for categorical encoding
        strategy_hash: Hash of strategy ID for categorical encoding
        execution_time_ms: Task execution time in milliseconds
        success: Whether task succeeded (1) or failed (0)
        reasoning_quality: Quality of reasoning (0.0-1.0)
        tool_selection_correct: Whether tool selection was correct (1/0)
        hallucination_detected: Whether hallucination was detected (1/0)
        context_complexity: Complexity score of task context

    """

    task_type_hash: int
    strategy_hash: int
    execution_time_ms: float
    success: int
    reasoning_quality: float
    tool_selection_correct: int
    hallucination_detected: int
    context_complexity: float

    def to_vector(self) -> np.ndarray:
        """Convert features to numerical vector for ML.

        Returns:
            NumPy array of shape (8,) with all features

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        return np.array(
            [
                float(self.task_type_hash % 10000),  # Normalize hash
                float(self.strategy_hash % 10000),  # Normalize hash
                self.execution_time_ms,
                float(self.success),
                self.reasoning_quality,
                float(self.tool_selection_correct),
                float(self.hallucination_detected),
                self.context_complexity,
            ],
            dtype=np.float32,
        )


@dataclass
class Pattern:
    """A learned pattern from task executions.

    Patterns represent clusters of similar task executions that
    share common characteristics leading to success or failure.

    Attributes:
        pattern_id: Unique pattern identifier
        pattern_type: SUCCESS_PATTERN or FAILURE_PATTERN
        centroid: Center point of pattern cluster in feature space
        feature_ranges: Min/max ranges for each feature in pattern
        recommended_strategies: Strategy IDs that work well for this pattern
        confidence: Confidence score (0.0-1.0) based on sample size
        sample_count: Number of executions in this pattern
        created_at: When pattern was first identified
        last_updated: When pattern was last updated

    """

    pattern_id: str
    pattern_type: PatternType
    centroid: np.ndarray
    feature_ranges: dict[str, tuple[float, float]]
    recommended_strategies: list[str]
    confidence: float
    sample_count: int
    created_at: datetime
    last_updated: datetime


class MetaLearner:
    """Meta-learning system for pattern recognition and strategy recommendation.

    Analyzes historical task executions to identify patterns that predict
    success or failure. Recommends optimal strategies for new tasks based
    on pattern matching.

    Time Complexity:
        - Feature extraction: O(1) per task
        - Pattern clustering: O(n log n) where n is number of tasks
        - Pattern matching: O(k) where k is number of patterns
        - Incremental update: O(1) amortized

    Space Complexity: O(n) where n is number of task executions

    Example:
        >>> learner = MetaLearner("data/self_improvement.db")
        >>> learner.process_execution(task_execution)
        >>> strategies = learner.recommend_strategies("task_type", context)
        >>> print(f"Recommended: {strategies}")

    """

    def __init__(
        self,
        storage_path: str,
        min_samples: int = 5,
        eps: float = 0.5,
        min_confidence: float = 0.6,
    ) -> None:
        """Initialize meta-learner.

        Args:
            storage_path: Path to SQLite database
            min_samples: Minimum samples for pattern formation (DBSCAN)
            eps: Maximum distance for pattern clustering (DBSCAN)
            min_confidence: Minimum confidence for pattern recommendations

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        self.storage_path = storage_path
        self.min_samples = min_samples
        self.eps = eps
        self.min_confidence = min_confidence

        # BUG FIX (thread-safety): a StandardScaler used to be created
        # here and stored as self.scaler, shared across every call to
        # _cluster_features(). That method always does a full
        # fit_transform() (never an incremental partial_fit), and nothing
        # in this class ever reads the scaler's fitted state afterward --
        # it was already effectively call-local. Sharing it as instance
        # state meant concurrent calls to _cluster_features() (reachable
        # via concurrent SelfImprovementEngine.record_task_execution()
        # calls) raced on the same StandardScaler's internal fitted
        # state, concretely reproduced as scikit-learn raising
        # AttributeError: 'float' object has no attribute 'astype'.
        # _cluster_features() now creates its own local StandardScaler()
        # per call instead -- see there for details.

        # Cache for patterns (loaded on demand).
        # BUG FIX: guarded by a lock. record_task_execution() invalidates
        # this cache and is explicitly reachable concurrently (see the
        # StandardScaler race noted above), while get_strategy_recommendations()
        # read the attribute twice -- once to test for None and populate it,
        # then AGAIN to pass it downstream. An invalidation landing between
        # those two reads passed None into _match_patterns(), which iterates
        # it. Readers now resolve the cache once, under the lock, into a
        # local reference that a concurrent invalidation cannot pull away.
        self._cache_lock = threading.Lock()
        self._pattern_cache: list[Pattern] | None = None
        self._cache_timestamp: datetime | None = None

        # Initialize pattern storage table
        self._init_pattern_storage()

    def _init_pattern_storage(self) -> None:
        """Initialize pattern storage table.

        Creates meta_patterns table if it doesn't exist.

        Time Complexity: O(1)
        Space Complexity: O(1)
        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meta_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    centroid BLOB NOT NULL,
                    feature_ranges TEXT NOT NULL,
                    recommended_strategies TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,

                    CHECK (pattern_type IN ('success', 'failure')),
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
                    CHECK (sample_count > 0)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meta_patterns_type
                ON meta_patterns(pattern_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meta_patterns_confidence
                ON meta_patterns(confidence DESC)
            """)

            conn.commit()

    def process_execution(self, execution: Any) -> None:
        """Process a task execution for meta-learning.

        Extracts features and triggers incremental pattern update.

        Args:
            execution: TaskExecution object with task details

        Time Complexity: O(1) amortized
        Space Complexity: O(1)

        """
        # Extract features
        features = self.extract_features(execution)

        # Store features for later clustering
        self._store_execution_features(execution, features)

        # Invalidate pattern cache (will be rebuilt on next query)
        with self._cache_lock:
            self._pattern_cache = None

        # Trigger incremental update if enough new data
        if self._should_update_patterns():
            self.update_patterns()

    def extract_features(self, execution: Any) -> TaskFeatures:
        """Extract numerical features from task execution.

        Converts task execution into numerical feature vector for ML.

        Args:
            execution: TaskExecution object

        Returns:
            TaskFeatures with extracted numerical features

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        # Hash task type and strategy for categorical encoding
        task_type_hash = self._hash_string(execution.task_type)
        strategy_hash = self._hash_string(execution.strategy_id)

        # Extract numerical features
        execution_time_ms = float(execution.execution_time_ms)
        success = 1 if execution.success else 0

        # Get reasoning quality from error details or default
        reasoning_quality = 0.0
        tool_selection_correct = 0
        hallucination_detected = 0

        if hasattr(execution, "error_details") and execution.error_details:
            reasoning_quality = float(execution.error_details.get("reasoning_quality", 0.0))
            tool_selection_correct = (
                1 if execution.error_details.get("tool_selection_correct") else 0
            )
            hallucination_detected = (
                1 if execution.error_details.get("hallucination_detected") else 0
            )
        elif execution.success:
            # Successful executions have high reasoning quality
            reasoning_quality = 1.0
            tool_selection_correct = 1

        # Calculate context complexity
        context_complexity = self._calculate_context_complexity(execution.context)

        return TaskFeatures(
            task_type_hash=task_type_hash,
            strategy_hash=strategy_hash,
            execution_time_ms=execution_time_ms,
            success=success,
            reasoning_quality=reasoning_quality,
            tool_selection_correct=tool_selection_correct,
            hallucination_detected=hallucination_detected,
            context_complexity=context_complexity,
        )

    def _hash_string(self, s: str) -> int:
        """Hash string to integer for categorical encoding.

        Args:
            s: String to hash

        Returns:
            Integer hash value

        Time Complexity: O(len(s))
        Space Complexity: O(1)

        """
        return int(hashlib.md5(s.encode(), usedforsecurity=False).hexdigest()[:8], 16)

    def _calculate_context_complexity(self, context: dict[str, Any]) -> float:
        """Calculate complexity score for task context.

        Measures how complex the task context is based on:
        - Number of context keys
        - Depth of nested structures
        - Total size of context data

        Args:
            context: Task context dictionary

        Returns:
            Complexity score (0.0-1.0)

        Time Complexity: O(n) where n is context size
        Space Complexity: O(1)

        """
        if not context:
            return 0.0

        # Count keys
        num_keys = len(context)

        # Measure depth
        max_depth = self._get_dict_depth(context)

        # Measure size
        context_str = json.dumps(context)
        size_kb = len(context_str) / 1024.0

        # Normalize to 0-1 range
        return min(
            1.0,
            (
                (num_keys / 20.0) * 0.4  # Max 20 keys
                + (max_depth / 5.0) * 0.3  # Max depth 5
                + (size_kb / 10.0) * 0.3  # Max 10KB
            ),
        )

    def _get_dict_depth(self, d: dict, current_depth: int = 1) -> int:
        """Get maximum depth of nested dictionary.

        Args:
            d: Dictionary to measure
            current_depth: Current recursion depth

        Returns:
            Maximum depth

        Time Complexity: O(n) where n is total elements
        Space Complexity: O(d) where d is depth (recursion stack)

        """
        if not isinstance(d, dict) or not d:
            return current_depth

        return max(
            self._get_dict_depth(v, current_depth + 1) if isinstance(v, dict) else current_depth
            for v in d.values()
        )

    def _store_execution_features(self, execution: Any, features: TaskFeatures) -> None:
        """Store execution features for later clustering.

        Args:
            execution: TaskExecution object
            features: Extracted features

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            # Create execution_features table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_features (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    features BLOB NOT NULL,
                    timestamp TEXT NOT NULL,

                    CHECK (success IN (0, 1))
                )
            """)

            # Store features as binary blob
            feature_vector = features.to_vector()
            feature_blob = feature_vector.tobytes()

            cursor.execute(
                """
                INSERT OR REPLACE INTO execution_features (
                    task_id, task_type, strategy_id, success, features, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    execution.task_id,
                    execution.task_type,
                    execution.strategy_id,
                    1 if execution.success else 0,
                    feature_blob,
                    execution.timestamp.isoformat(),
                ),
            )

            conn.commit()

    def _should_update_patterns(self) -> bool:
        """Check if patterns should be updated.

        Updates patterns when:
        - Enough new executions since last update (>10)
        - Or no patterns exist yet

        Returns:
            True if patterns should be updated

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            # Count total executions
            cursor.execute("SELECT COUNT(*) FROM execution_features")
            total_count = cursor.fetchone()[0]

            # Count existing patterns
            cursor.execute("SELECT COUNT(*) FROM meta_patterns")
            pattern_count = cursor.fetchone()[0]

        # Update if no patterns or enough new data
        return bool(pattern_count == 0 or total_count % 10 == 0)

    def update_patterns(self) -> None:
        """Update patterns using clustering on all execution data.

        Performs DBSCAN clustering on successful and failed executions
        separately to identify patterns.

        Time Complexity: O(n log n) where n is number of executions
        Space Complexity: O(n)
        """
        # Load all execution features
        success_features, success_data = self._load_features(success=True)
        failure_features, failure_data = self._load_features(success=False)

        # Cluster successful executions
        if len(success_features) >= self.min_samples:
            success_patterns = self._cluster_features(
                success_features,
                success_data,
                PatternType.SUCCESS_PATTERN,
            )
            self._store_patterns(success_patterns, PatternType.SUCCESS_PATTERN)

        # Cluster failed executions
        if len(failure_features) >= self.min_samples:
            failure_patterns = self._cluster_features(
                failure_features,
                failure_data,
                PatternType.FAILURE_PATTERN,
            )
            self._store_patterns(failure_patterns, PatternType.FAILURE_PATTERN)

    def _load_features(self, success: bool) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Load execution features from database.

        Args:
            success: Load successful (True) or failed (False) executions

        Returns:
            Tuple of (feature_matrix, execution_data)

        Time Complexity: O(n) where n is number of executions
        Space Complexity: O(n)

        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT task_id, task_type, strategy_id, features
                FROM execution_features
                WHERE success = ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """,
                (1 if success else 0,),
            )

            rows = cursor.fetchall()

        if not rows:
            return np.array([]), []

        # Convert binary blobs to feature vectors
        features = []
        data = []

        for task_id, task_type, strategy_id, feature_blob in rows:
            feature_vector = np.frombuffer(feature_blob, dtype=np.float32)
            features.append(feature_vector)
            data.append({"task_id": task_id, "task_type": task_type, "strategy_id": strategy_id})

        return np.array(features), data

    def _cluster_features(
        self,
        features: np.ndarray,
        data: list[dict[str, Any]],
        pattern_type: PatternType,
    ) -> list[Pattern]:
        """Cluster features using DBSCAN.

        Args:
            features: Feature matrix (n_samples, n_features)
            data: Execution data for each sample
            pattern_type: Type of pattern (success/failure)

        Returns:
            List of identified patterns

        Time Complexity: O(n log n)
        Space Complexity: O(n)

        """
        # BUG FIX (thread-safety): use a fresh, function-local scaler
        # instead of a shared self.scaler instance. fit_transform() always
        # recomputes mean_/var_/scale_ from `features` from scratch on
        # every call regardless of any prior fit, and nothing reads the
        # scaler's fitted state after this line (the pattern centroid and
        # feature ranges below are computed from the original, unscaled
        # `features` array, not features_scaled) -- so this produces
        # byte-identical output to the previous single-threaded behavior,
        # while removing the shared mutable state that made concurrent
        # calls corrupt scikit-learn's internal fit state.
        features_scaled = StandardScaler().fit_transform(features)

        # Cluster with DBSCAN
        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = clustering.fit_predict(features_scaled)

        # Extract patterns from clusters
        patterns = []
        unique_labels = set(labels)

        for label in unique_labels:
            if label == -1:  # Skip noise points
                continue

            # Get cluster members
            mask = labels == label
            cluster_features = features[mask]
            cluster_data = [d for i, d in enumerate(data) if mask[i]]

            # Calculate pattern properties
            centroid = np.mean(cluster_features, axis=0)
            feature_ranges = self._calculate_feature_ranges(cluster_features)
            recommended_strategies = self._extract_strategies(cluster_data)
            confidence = self._calculate_confidence(len(cluster_data))

            # Create pattern
            pattern_id = self._generate_pattern_id(pattern_type, centroid)
            pattern = Pattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                centroid=centroid,
                feature_ranges=feature_ranges,
                recommended_strategies=recommended_strategies,
                confidence=confidence,
                sample_count=len(cluster_data),
                created_at=datetime.now(tz=UTC),
                last_updated=datetime.now(tz=UTC),
            )

            patterns.append(pattern)

        return patterns

    def _calculate_feature_ranges(self, features: np.ndarray) -> dict[str, tuple[float, float]]:
        """Calculate min/max ranges for each feature.

        Args:
            features: Feature matrix

        Returns:
            Dictionary mapping feature names to (min, max) tuples

        Time Complexity: O(n * m) where n=samples, m=features
        Space Complexity: O(m)

        """
        feature_names = [
            "task_type_hash",
            "strategy_hash",
            "execution_time_ms",
            "success",
            "reasoning_quality",
            "tool_selection_correct",
            "hallucination_detected",
            "context_complexity",
        ]

        ranges = {}
        for i, name in enumerate(feature_names):
            ranges[name] = (float(np.min(features[:, i])), float(np.max(features[:, i])))

        return ranges

    def _extract_strategies(self, cluster_data: list[dict[str, Any]]) -> list[str]:
        """Extract most common strategies from cluster.

        Args:
            cluster_data: Execution data for cluster members

        Returns:
            List of strategy IDs sorted by frequency

        Time Complexity: O(n log n)
        Space Complexity: O(n)

        """
        strategy_counts: dict[str, int] = {}

        for data in cluster_data:
            strategy_id = data["strategy_id"]
            strategy_counts[strategy_id] = strategy_counts.get(strategy_id, 0) + 1

        # Sort by frequency
        sorted_strategies = sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top 3 strategies
        return [s[0] for s in sorted_strategies[:3]]

    def _calculate_confidence(self, sample_count: int) -> float:
        """Calculate confidence score based on sample size.

        Args:
            sample_count: Number of samples in pattern

        Returns:
            Confidence score (0.0-1.0)

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        # Confidence increases with sample size, plateaus at 50 samples
        return min(1.0, sample_count / 50.0)

    def _generate_pattern_id(self, pattern_type: PatternType, centroid: np.ndarray) -> str:
        """Generate unique pattern ID.

        Args:
            pattern_type: Type of pattern
            centroid: Pattern centroid

        Returns:
            Unique pattern ID

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        centroid_hash = hashlib.md5(centroid.tobytes(), usedforsecurity=False).hexdigest()[:8]
        return f"{pattern_type.value}_{centroid_hash}"

    def _store_patterns(self, patterns: list[Pattern], pattern_type: PatternType) -> None:
        """Store patterns in database, replacing the prior set for this type.

        BUG FIX: update_patterns() fully recomputes a pattern_type's cluster
        set from scratch on every call, but pattern_id is derived from the
        cluster centroid's hash, so a re-clustering over a shifted recency
        window almost always produces different pattern_ids -- INSERT OR
        REPLACE alone never actually replaced the prior run's rows.
        Reproduced concretely: two successive update_patterns() calls left
        both runs' pattern rows in the table at once, growing meta_patterns
        unboundedly and causing recommend_strategies() to keep matching
        against stale, superseded patterns forever. Deleting this type's
        existing rows before inserting the freshly computed set (in the
        same transaction) restores this class's own documented "Update
        patterns as new data arrives" semantics -- replace, not accumulate.

        Args:
            patterns: List of patterns to store (all of the same pattern_type)
            pattern_type: The pattern type being replaced

        Time Complexity: O(n) where n is number of patterns
        Space Complexity: O(1)

        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM meta_patterns WHERE pattern_type = ?",
                (pattern_type.value,),
            )

            # One prepared statement for the whole batch instead of one
            # execute() per pattern: same rows, same order, but the statement
            # is parsed and bound once rather than len(patterns) times.
            cursor.executemany(
                """
                    INSERT OR REPLACE INTO meta_patterns (
                        pattern_id, pattern_type, centroid, feature_ranges,
                        recommended_strategies, confidence, sample_count,
                        created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        pattern.pattern_id,
                        pattern.pattern_type.value,
                        pattern.centroid.tobytes(),
                        json.dumps(pattern.feature_ranges),
                        json.dumps(pattern.recommended_strategies),
                        pattern.confidence,
                        pattern.sample_count,
                        pattern.created_at.isoformat(),
                        pattern.last_updated.isoformat(),
                    )
                    for pattern in patterns
                ],
            )

            conn.commit()

    def recommend_strategies(
        self,
        task_type: str,
        context: dict[str, Any] | None = None,
    ) -> list[str]:
        """Recommend strategies for a new task based on patterns.

        Matches task characteristics against known success patterns
        and returns recommended strategies.

        Args:
            task_type: Type of task
            context: Optional task context

        Returns:
            List of recommended strategy IDs sorted by confidence

        Time Complexity: O(k) where k is number of patterns
        Space Complexity: O(k)

        """
        # Load patterns if not cached. Resolved once into a local so a
        # concurrent invalidation cannot turn it back into None mid-use.
        with self._cache_lock:
            patterns = self._pattern_cache
            if patterns is None:
                patterns = self._load_patterns()
                self._pattern_cache = patterns

        # Extract features for new task (create dummy execution)
        task_features = self._extract_task_features(task_type, context or {})

        # Find matching success patterns
        matching_patterns = self._match_patterns(
            task_features,
            patterns,
            PatternType.SUCCESS_PATTERN,
        )

        # Extract recommended strategies
        recommendations = []
        for pattern, _similarity in matching_patterns:
            if pattern.confidence >= self.min_confidence:
                recommendations.extend(pattern.recommended_strategies)

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for strategy in recommendations:
            if strategy not in seen:
                seen.add(strategy)
                unique_recommendations.append(strategy)

        return unique_recommendations

    def _load_patterns(self) -> list[Pattern]:
        """Load all patterns from database.

        Returns:
            List of all patterns

        Time Complexity: O(n) where n is number of patterns
        Space Complexity: O(n)

        """
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT pattern_id, pattern_type, centroid, feature_ranges,
                       recommended_strategies, confidence, sample_count,
                       created_at, last_updated
                FROM meta_patterns
                ORDER BY confidence DESC
            """)

            patterns = []
            for row in cursor.fetchall():
                pattern = Pattern(
                    pattern_id=row[0],
                    pattern_type=PatternType(row[1]),
                    centroid=np.frombuffer(row[2], dtype=np.float32),
                    feature_ranges=json.loads(row[3]),
                    recommended_strategies=json.loads(row[4]),
                    confidence=row[5],
                    sample_count=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                    last_updated=datetime.fromisoformat(row[8]),
                )
                patterns.append(pattern)

        return patterns

    def _extract_task_features(self, task_type: str, context: dict[str, Any]) -> np.ndarray:
        """Extract features for a new task (without execution data).

        Args:
            task_type: Type of task
            context: Task context

        Returns:
            Feature vector

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        task_type_hash = self._hash_string(task_type)
        context_complexity = self._calculate_context_complexity(context)

        # Create feature vector with defaults for unknown values
        return np.array(
            [
                float(task_type_hash % 10000),
                0.0,  # strategy_hash unknown
                0.0,  # execution_time_ms unknown
                0.0,  # success unknown
                0.0,  # reasoning_quality unknown
                0.0,  # tool_selection_correct unknown
                0.0,  # hallucination_detected unknown
                context_complexity,
            ],
            dtype=np.float32,
        )

    def _match_patterns(
        self,
        task_features: np.ndarray,
        patterns: list[Pattern],
        pattern_type: PatternType,
    ) -> list[tuple[Pattern, float]]:
        """Match task features against patterns.

        Args:
            task_features: Feature vector for new task
            patterns: List of patterns to match against
            pattern_type: Type of patterns to match

        Returns:
            List of (pattern, similarity) tuples sorted by similarity

        Time Complexity: O(k) where k is number of patterns
        Space Complexity: O(k)

        """
        matches = []

        for pattern in patterns:
            if pattern.pattern_type != pattern_type:
                continue

            # Calculate similarity (inverse of Euclidean distance)
            distance = np.linalg.norm(task_features - pattern.centroid)
            similarity = 1.0 / (1.0 + distance)

            matches.append((pattern, similarity))

        # Sort by similarity
        matches.sort(key=lambda x: x[1], reverse=True)

        return [(p, float(s)) for p, s in matches[:5]]  # Return top 5 matches

    def analyze_feature_correlations(self) -> dict[str, float]:
        """Analyze correlation between task features and success.

        Calculates Pearson correlation coefficient between each feature
        and task success to identify which features predict success.

        Returns:
            Dictionary mapping feature names to correlation coefficients

        Time Complexity: O(n) where n is number of executions
        Space Complexity: O(n)

        """
        # Load all execution features
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT features, success
                FROM execution_features
                ORDER BY timestamp DESC
                LIMIT 1000
            """)

            rows = cursor.fetchall()

        if len(rows) < 10:
            # Not enough data for correlation analysis
            return {}

        # Convert to arrays
        features_list = []
        success_list = []

        for feature_blob, success in rows:
            feature_vector = np.frombuffer(feature_blob, dtype=np.float32)
            features_list.append(feature_vector)
            success_list.append(float(success))

        features_matrix = np.array(features_list)
        success_array = np.array(success_list)

        # Calculate correlations for each feature
        feature_names = [
            "task_type_hash",
            "strategy_hash",
            "execution_time_ms",
            "success",
            "reasoning_quality",
            "tool_selection_correct",
            "hallucination_detected",
            "context_complexity",
        ]

        correlations = {}
        for i, name in enumerate(feature_names):
            if name == "success":
                continue  # Skip success feature itself

            feature_values = features_matrix[:, i]

            # Calculate Pearson correlation
            correlation = np.corrcoef(feature_values, success_array)[0, 1]

            # Handle NaN (constant feature)
            if np.isnan(correlation):
                correlation = 0.0

            correlations[name] = float(correlation)

        return correlations
