"""
Failure Analyzer for Self-Improvement Engine.

This module analyzes failures to identify patterns and root causes.
Categorizes failures and extracts common patterns for learning.

Performance Requirements:
- Time Complexity: O(1) for failure storage, O(n) for pattern matching
- Space Complexity: O(n) where n is number of failures
- Latency: <10ms for failure analysis (target from requirements)

Design Decisions:
- Store complete execution context for debugging
- Extract specific failure details based on type
- Use feature-based pattern matching with threshold
- Track pattern occurrence for trend analysis
- Support all failure types: reasoning_error, tool_error, hallucination, timeout, resource_error, unknown

Author: Kiro AI
Date: 2024
"""

import sqlite3
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from Agent_Guru.self_improvement.connection_pool import ConnectionPool


class FailureType(Enum):
    """Types of failures the system can learn from."""
    REASONING_ERROR = "reasoning_error"
    TOOL_ERROR = "tool_error"
    HALLUCINATION = "hallucination"
    TIMEOUT = "timeout"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN = "unknown"


@dataclass
class TaskExecution:
    """Record of a single task execution."""
    task_id: str
    task_type: str
    strategy_id: str
    timestamp: datetime
    success: bool
    execution_time_ms: float
    failure_type: Optional[FailureType]
    error_details: Optional[Dict[str, Any]]
    context: Dict[str, Any]


@dataclass
class FailurePattern:
    """A pattern identified across multiple failures."""
    pattern_id: str
    failure_type: FailureType
    common_features: Dict[str, Any]
    occurrence_count: int
    confidence_score: float
    first_seen: datetime
    last_seen: datetime


class FailureAnalyzer:
    """
    Analyzes failures to identify patterns and root causes.
    
    Categorizes failures and extracts common patterns for learning.
    
    Time Complexity:
    - analyze_failure: O(n) where n is number of existing patterns
    - get_failure_patterns: O(n log n) for sorting
    
    Space Complexity: O(n) where n is number of failures stored
    
    Performance Targets:
    - Failure analysis: <10ms
    - Pattern matching: <5ms
    - Database operations: <1ms per query
    """
    
    def __init__(self, connection_pool: ConnectionPool):
        """
        Initialize failure analyzer.
        
        Args:
            connection_pool: Database connection pool
        """
        self.pool = connection_pool
        self._pattern_match_threshold = 0.7  # 70% feature similarity
    
    def analyze_failure(self, execution: TaskExecution) -> None:
        """
        Analyze a failed task execution.
        
        Categorizes failure, extracts context, and identifies patterns.
        
        Args:
            execution: Failed task execution record
            
        Time Complexity: O(n) where n is number of existing patterns
        Performance Target: <10ms
        
        Validates: Requirements 1.1, 1.2, 1.6
        """
        start_time = time.time()
        
        # Store failure with full context
        self._store_failure(execution)
        
        # Extract specific failure details based on type
        if execution.failure_type == FailureType.REASONING_ERROR:
            self._analyze_reasoning_error(execution)
        elif execution.failure_type == FailureType.TOOL_ERROR:
            self._analyze_tool_error(execution)
        elif execution.failure_type == FailureType.HALLUCINATION:
            self._analyze_hallucination(execution)
        
        # Update failure patterns
        self._update_failure_patterns(execution)
        
        # Performance monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 10:
            print(f"WARNING: Failure analysis took {elapsed_ms:.2f}ms (target: <10ms)")
    
    def _store_failure(self, execution: TaskExecution) -> None:
        """
        Store failure in database with complete execution context.
        
        Args:
            execution: Failed task execution
            
        Time Complexity: O(1)
        Validates: Requirements 1.1, 1.6
        """
        with self.pool.transaction() as conn:
            cursor = conn.cursor()
            
            # Generate unique failure ID
            failure_id = f"failure_{execution.task_id}_{int(time.time() * 1000)}"
            
            # Extract specific failure details
            reasoning_step = None
            tool_name = None
            hallucination_content = None
            
            if execution.error_details:
                reasoning_step = execution.error_details.get("reasoning_step")
                tool_name = execution.error_details.get("tool_name")
                hallucination_content = execution.error_details.get("hallucination_content")
            
            cursor.execute("""
                INSERT INTO failures (
                    id, task_id, task_type, strategy_id, failure_type,
                    timestamp, execution_time_ms, execution_context, error_details,
                    reasoning_step, tool_name, hallucination_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                failure_id,
                execution.task_id,
                execution.task_type,
                execution.strategy_id,
                execution.failure_type.value,
                execution.timestamp.isoformat(),
                execution.execution_time_ms,
                json.dumps(execution.context),
                json.dumps(execution.error_details or {}),
                reasoning_step,
                tool_name,
                hallucination_content
            ))
    
    def _analyze_reasoning_error(self, execution: TaskExecution) -> None:
        """
        Analyze reasoning error to identify logical mistake.
        
        Extracts the specific logical step where reasoning diverged.
        
        Args:
            execution: Failed task execution with reasoning error
            
        Validates: Requirements 1.3
        """
        if not execution.error_details:
            return
        
        reasoning_step = execution.error_details.get("reasoning_step")
        if reasoning_step:
            # Record the specific logical step where reasoning diverged
            # This helps Strategy Optimizer learn better reasoning patterns
            # Future enhancement: integrate with LLM Runtime to get full reasoning trace
            pass
    
    def _analyze_tool_error(self, execution: TaskExecution) -> None:
        """
        Analyze tool error to identify misuse pattern.
        
        Records which tool was misused and how.
        
        Args:
            execution: Failed task execution with tool error
            
        Validates: Requirements 1.4
        """
        if not execution.error_details:
            return
        
        tool_name = execution.error_details.get("tool_name")
        if tool_name:
            # Record which tool was misused
            # This helps Strategy Optimizer avoid similar mistakes
            # Future enhancement: track correct vs incorrect tool usage patterns
            pass
    
    def _analyze_hallucination(self, execution: TaskExecution) -> None:
        """
        Analyze hallucination to identify fabricated information.
        
        Records what was fabricated vs what was correct.
        
        Args:
            execution: Failed task execution with hallucination
            
        Validates: Requirements 1.5
        """
        if not execution.error_details:
            return
        
        hallucination_content = execution.error_details.get("hallucination_content")
        if hallucination_content:
            # Record what was fabricated
            # This helps Prompt Evolution System refine prompts
            # Future enhancement: track hallucination patterns by prompt type
            pass
    
    def _update_failure_patterns(self, execution: TaskExecution) -> None:
        """
        Update failure patterns based on new failure.
        
        Identifies common patterns across multiple failures.
        
        Args:
            execution: Failed task execution
            
        Time Complexity: O(n) where n is number of existing patterns
        Validates: Requirements 1.7
        """
        # Extract features from failure
        features = self._extract_failure_features(execution)
        
        # Find matching patterns
        matching_pattern = self._find_matching_pattern(
            execution.failure_type, features
        )
        
        if matching_pattern:
            # Update existing pattern
            self._increment_pattern_count(matching_pattern.pattern_id)
        else:
            # Create new pattern
            self._create_new_pattern(execution.failure_type, features)
    
    def _extract_failure_features(self, execution: TaskExecution) -> Dict[str, Any]:
        """
        Extract features from failure for pattern matching.
        
        Args:
            execution: Failed task execution
            
        Returns:
            Dictionary of features
            
        Time Complexity: O(1)
        """
        features = {
            "task_type": execution.task_type,
            "strategy_id": execution.strategy_id,
            "failure_type": execution.failure_type.value
        }
        
        # Add specific failure details if available
        if execution.error_details:
            # Include relevant error details for pattern matching
            for key in ["tool_name", "reasoning_step", "error_category", "error_message"]:
                if key in execution.error_details:
                    features[key] = execution.error_details[key]
        
        return features
    
    def _find_matching_pattern(
        self,
        failure_type: FailureType,
        features: Dict[str, Any]
    ) -> Optional[FailurePattern]:
        """
        Find existing pattern matching these features.
        
        Uses feature similarity threshold for matching.
        
        Args:
            failure_type: Type of failure
            features: Feature dictionary
            
        Returns:
            Matching pattern or None
            
        Time Complexity: O(n) where n is number of patterns
        Performance Target: <5ms
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pattern_id, failure_type, common_features, 
                       occurrence_count, confidence_score, first_seen, last_seen
                FROM failure_patterns
                WHERE failure_type = ?
            """, (failure_type.value,))
            
            for row in cursor.fetchall():
                stored_features = json.loads(row[2])
                if self._features_match(features, stored_features):
                    return FailurePattern(
                        pattern_id=row[0],
                        failure_type=FailureType(row[1]),
                        common_features=stored_features,
                        occurrence_count=row[3],
                        confidence_score=row[4],
                        first_seen=datetime.fromisoformat(row[5]),
                        last_seen=datetime.fromisoformat(row[6])
                    )
        
        return None
    
    def _features_match(
        self,
        features1: Dict[str, Any],
        features2: Dict[str, Any]
    ) -> bool:
        """
        Check if two feature sets match above threshold.
        
        Critical features (tool_name, reasoning_step, error_category) must match exactly.
        Other features use similarity threshold.
        
        Args:
            features1: First feature set
            features2: Second feature set
            
        Returns:
            True if similarity >= threshold, False otherwise
            
        Time Complexity: O(k) where k is number of features
        """
        # Critical features that must match exactly
        critical_features = {"tool_name", "reasoning_step", "error_category"}
        
        # Check critical features first
        for feature in critical_features:
            if feature in features1 and feature in features2:
                if features1[feature] != features2[feature]:
                    return False  # Critical feature mismatch
        
        # Check overall similarity for non-critical features
        common_keys = set(features1.keys()) & set(features2.keys())
        if not common_keys:
            return False
        
        matching = sum(
            1 for k in common_keys
            if features1[k] == features2[k]
        )
        
        similarity = matching / len(common_keys)
        return similarity >= self._pattern_match_threshold
    
    def _increment_pattern_count(self, pattern_id: str) -> None:
        """
        Increment occurrence count for pattern.
        
        Args:
            pattern_id: Pattern identifier
            
        Time Complexity: O(1)
        """
        with self.pool.transaction() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE failure_patterns
                SET occurrence_count = occurrence_count + 1,
                    last_seen = ?,
                    confidence_score = MIN(1.0, confidence_score + 0.05)
                WHERE pattern_id = ?
            """, (datetime.now().isoformat(), pattern_id))
    
    def _create_new_pattern(
        self,
        failure_type: FailureType,
        features: Dict[str, Any]
    ) -> None:
        """
        Create new failure pattern.
        
        Args:
            failure_type: Type of failure
            features: Feature dictionary
            
        Time Complexity: O(1)
        """
        with self.pool.transaction() as conn:
            cursor = conn.cursor()
            
            # Generate unique pattern_id using timestamp + random component
            import random
            pattern_id = f"pattern_{int(time.time() * 1000000)}_{random.randint(1000, 9999)}"
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO failure_patterns (
                    pattern_id, failure_type, common_features,
                    occurrence_count, confidence_score, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern_id,
                failure_type.value,
                json.dumps(features),
                1,
                0.1,  # Initial low confidence
                now,
                now
            ))
    
    def get_failure_patterns(
        self,
        failure_type: Optional[FailureType] = None,
        min_occurrences: int = 2,
        min_confidence: float = 0.0
    ) -> List[FailurePattern]:
        """
        Get identified failure patterns.
        
        Args:
            failure_type: Optional filter by failure type
            min_occurrences: Minimum occurrences to include
            min_confidence: Minimum confidence score to include
            
        Returns:
            List of failure patterns sorted by occurrence count
            
        Time Complexity: O(n log n) for sorting
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT pattern_id, failure_type, common_features,
                       occurrence_count, confidence_score, first_seen, last_seen
                FROM failure_patterns
                WHERE occurrence_count >= ? AND confidence_score >= ?
            """
            params: List[Any] = [min_occurrences, min_confidence]
            
            if failure_type:
                query += " AND failure_type = ?"
                params.append(failure_type.value)
            
            query += " ORDER BY occurrence_count DESC, confidence_score DESC"
            
            cursor.execute(query, params)
            
            patterns = [
                FailurePattern(
                    pattern_id=row[0],
                    failure_type=FailureType(row[1]),
                    common_features=json.loads(row[2]),
                    occurrence_count=row[3],
                    confidence_score=row[4],
                    first_seen=datetime.fromisoformat(row[5]),
                    last_seen=datetime.fromisoformat(row[6])
                )
                for row in cursor.fetchall()
            ]
            
            return patterns
    
    def get_failure_count(
        self,
        failure_type: Optional[FailureType] = None,
        task_type: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> int:
        """
        Get count of failures matching criteria.
        
        Args:
            failure_type: Optional filter by failure type
            task_type: Optional filter by task type
            since: Optional filter by timestamp
            
        Returns:
            Count of matching failures
            
        Time Complexity: O(1) with indexes
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM failures WHERE 1=1"
            params: List[Any] = []
            
            if failure_type:
                query += " AND failure_type = ?"
                params.append(failure_type.value)
            
            if task_type:
                query += " AND task_type = ?"
                params.append(task_type)
            
            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            return result[0] if result else 0
    
    def record_hallucination(
        self,
        prompt_id: str,
        hallucination_content: str,
        task_id: Optional[str] = None
    ) -> None:
        """
        Record a hallucination for prompt evolution.
        
        Called by LLM Runtime when hallucination detected.
        
        Args:
            prompt_id: ID of prompt that led to hallucination
            hallucination_content: The fabricated content
            task_id: Optional task ID for context
            
        Time Complexity: O(1)
        Validates: Requirements 1.5
        """
        # Create a synthetic failure record for the hallucination
        execution = TaskExecution(
            task_id=task_id or f"hallucination_{int(time.time() * 1000)}",
            task_type="llm_response",
            strategy_id="unknown",
            timestamp=datetime.now(),
            success=False,
            execution_time_ms=0.0,
            failure_type=FailureType.HALLUCINATION,
            error_details={
                "prompt_id": prompt_id,
                "hallucination_content": hallucination_content
            },
            context={"source": "llm_runtime"}
        )
        
        self.analyze_failure(execution)
    
    def get_recent_failures(
        self,
        limit: int = 10,
        failure_type: Optional[FailureType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent failures for debugging.
        
        Args:
            limit: Maximum number of failures to return
            failure_type: Optional filter by failure type
            
        Returns:
            List of failure records
            
        Time Complexity: O(n) where n is limit
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT id, task_id, task_type, strategy_id, failure_type,
                       timestamp, execution_time_ms, execution_context, error_details,
                       reasoning_step, tool_name, hallucination_content
                FROM failures
            """
            params: List[Any] = []
            
            if failure_type:
                query += " WHERE failure_type = ?"
                params.append(failure_type.value)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            failures = []
            for row in cursor.fetchall():
                failures.append({
                    "id": row[0],
                    "task_id": row[1],
                    "task_type": row[2],
                    "strategy_id": row[3],
                    "failure_type": row[4],
                    "timestamp": row[5],
                    "execution_time_ms": row[6],
                    "execution_context": json.loads(row[7]),
                    "error_details": json.loads(row[8]),
                    "reasoning_step": row[9],
                    "tool_name": row[10],
                    "hallucination_content": row[11]
                })
            
            return failures
