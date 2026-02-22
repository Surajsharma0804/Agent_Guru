"""
Intent Detection Engine - Hybrid Approach with Fast-Path Router

This module provides the main Intent Detection Engine that integrates all intent
detection components into a unified pipeline with intelligent routing.

Architecture:
    1. Fast-Path Router (80% of commands, <50ms)
       - Trie-based pattern matching
       - Direct Task creation without LLM
       - Bypasses neural models for speed

    2. Neural Classifier (15% of commands, <50ms with GPU)
       - DeBERTa-v3-large fine-tuned model
       - GPU-accelerated inference with ONNX Runtime
       - High accuracy (>95%) for common intents

    3. LLM Fallback (5% of commands, <300ms)
       - GPT-4 Turbo or Claude 3.5 Sonnet
       - Handles edge cases and ambiguous inputs
       - Highest accuracy (>98%) but slower

Performance Characteristics:
    - Time Complexity: O(n) where n is input length
    - Space Complexity: O(1) with caching
    - Average Latency: <100ms (80% fast-path at <50ms)
    - P95 Latency: <200ms
    - Accuracy: >95% overall

Routing Logic:
    1. Try Fast-Path Router first (pattern matching)
       - If match found with confidence >0.95: DONE
       - If no match: proceed to neural classifier

    2. Try Neural Classifier (GPU-accelerated)
       - If confidence >=0.8: DONE
       - If confidence <0.8: proceed to LLM fallback

    3. Try LLM Fallback (cloud API)
       - Always returns result (may be UNKNOWN)
       - Highest accuracy for edge cases

Online Learning:
    - Collect user feedback on intent corrections
    - Store feedback for periodic model retraining
    - Track model performance over time with drift detection

Author: Kiro AI
Date: 2026-02-19
Version: 1.0.0
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from Agent_Guru.reasoning.intent.fast_router import FastIntentRouter, PatternMatch
from Agent_Guru.reasoning.intent.llm_fallback import (
    LLMClassificationResult,
    LLMFallbackClassifier,
    LLMFallbackConfig,
)
from Agent_Guru.reasoning.intent.ner_extractor import (
    NERConfig,
    NEREntityExtractor,
)
from Agent_Guru.reasoning.intent.neural_classifier import (
    ClassificationResult,
    ClassifierConfig,
    NeuralIntentClassifier,
)
from Agent_Guru.reasoning.learning.feedback_store import FeedbackStore
from Agent_Guru.reasoning.learning.online_learner import OnlineLearner
from Agent_Guru.reasoning.models.intent import Entity, Intent


@dataclass
class IntentEngineConfig:
    """Configuration for Intent Detection Engine.

    Attributes:
        patterns_file: Path to intent patterns YAML
        neural_config: Neural classifier configuration
        ner_config: NER extractor configuration
        llm_config: LLM fallback configuration
        enable_fast_path: Whether to use fast-path router
        enable_neural: Whether to use neural classifier
        enable_llm_fallback: Whether to use LLM fallback
        enable_online_learning: Whether to enable online learning
        feedback_db_path: Path to feedback database
    """

    patterns_file: str = "Agent_Guru/reasoning/data/intent_patterns.yaml"
    neural_config: ClassifierConfig | None = None
    ner_config: NERConfig | None = None
    llm_config: LLMFallbackConfig | None = None
    enable_fast_path: bool = True
    enable_neural: bool = True
    enable_llm_fallback: bool = True
    enable_online_learning: bool = True
    feedback_db_path: str = "Agent_Guru/reasoning/data/feedback.db"


@dataclass
class DetectionResult:
    """Result from intent detection.

    Attributes:
        intent: Detected intent with entities
        detection_method: Method used ("fast_path", "neural", "llm_fallback")
        latency_ms: Total detection time in milliseconds
        fast_path_attempted: Whether fast-path was attempted
        neural_attempted: Whether neural classifier was attempted
        llm_attempted: Whether LLM fallback was attempted
        confidence: Final confidence score
    """

    intent: Intent
    detection_method: str
    latency_ms: float
    fast_path_attempted: bool
    neural_attempted: bool
    llm_attempted: bool
    confidence: float


class IntentDetectionEngine:
    """Hybrid Intent Detection Engine with intelligent routing.

    Time Complexity: O(n) where n is input length
    Space Complexity: O(1) with caching

    Example:
        >>> engine = IntentDetectionEngine()
        >>> engine.initialize()
        >>> result = await engine.detect_intent_async("set timer for 5 minutes")
        >>> print(f"Intent: {result.intent.intent_type}")
        >>> print(f"Method: {result.detection_method}")
        >>> print(f"Latency: {result.latency_ms}ms")

    Routing Strategy:
        1. Fast-Path Router (80% coverage, <50ms)
        2. Neural Classifier (15% coverage, <50ms with GPU)
        3. LLM Fallback (5% coverage, <300ms)
    """

    def __init__(self, config: IntentEngineConfig | None = None) -> None:
        """Initialize Intent Detection Engine.

        Args:
            config: Engine configuration (uses defaults if None)
        """
        self.config = config or IntentEngineConfig()

        # Components (initialized lazily)
        self.fast_router: FastIntentRouter | None = None
        self.neural_classifier: NeuralIntentClassifier | None = None
        self.ner_extractor: NEREntityExtractor | None = None
        self.llm_fallback: LLMFallbackClassifier | None = None
        self.feedback_store: FeedbackStore | None = None
        self.online_learner: OnlineLearner | None = None

        # Metrics
        self.total_detections = 0
        self.fast_path_hits = 0
        self.neural_hits = 0
        self.llm_hits = 0
        self.total_latency_ms = 0.0

        # Initialization flag
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all components.

        Raises:
            RuntimeError: If initialization fails
        """
        if self._initialized:
            return

        print("Initializing Intent Detection Engine...")

        # Initialize Fast-Path Router
        if self.config.enable_fast_path:
            self.fast_router = FastIntentRouter()
            patterns_path = Path(self.config.patterns_file)
            if patterns_path.exists():
                self.fast_router.load_patterns(self.config.patterns_file)
                print(
                    f"✓ Fast-Path Router initialized ({len(self.fast_router._patterns)} patterns)"
                )
            else:
                print(f"⚠ Patterns file not found: {self.config.patterns_file}")
                print("⚠ Fast-Path Router disabled")
                self.fast_router = None

        # Initialize Neural Classifier
        if self.config.enable_neural:
            try:
                neural_config = self.config.neural_config or ClassifierConfig()
                self.neural_classifier = NeuralIntentClassifier(neural_config)
                self.neural_classifier.load_model()
                print("✓ Neural Classifier initialized")
            except Exception as e:
                print(f"⚠ Neural Classifier initialization failed: {e}")
                print("⚠ Neural Classifier disabled")
                self.neural_classifier = None

        # Initialize NER Extractor
        if self.config.enable_neural:  # NER is used with neural classifier
            try:
                ner_config = self.config.ner_config or NERConfig()
                self.ner_extractor = NEREntityExtractor(ner_config)
                self.ner_extractor.load_model()
                print("✓ NER Extractor initialized")
            except Exception as e:
                print(f"⚠ NER Extractor initialization failed: {e}")
                print("⚠ NER Extractor disabled")
                self.ner_extractor = None

        # Initialize LLM Fallback
        if self.config.enable_llm_fallback:
            try:
                llm_config = self.config.llm_config or LLMFallbackConfig()
                self.llm_fallback = LLMFallbackClassifier(llm_config)
                print("✓ LLM Fallback initialized")
            except Exception as e:
                print(f"⚠ LLM Fallback initialization failed: {e}")
                print("⚠ LLM Fallback disabled")
                self.llm_fallback = None

        # Initialize Online Learning
        if self.config.enable_online_learning:
            try:
                self.feedback_store = FeedbackStore(self.config.feedback_db_path)
                self.online_learner = OnlineLearner(self.feedback_store)
                print("✓ Online Learning initialized")
            except Exception as e:
                print(f"⚠ Online Learning initialization failed: {e}")
                print("⚠ Online Learning disabled")
                self.feedback_store = None
                self.online_learner = None

        self._initialized = True
        print("✓ Intent Detection Engine ready")

    async def detect_intent_async(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> DetectionResult:
        """Detect intent asynchronously with hybrid routing.

        Time Complexity: O(n) where n is input length
        Space Complexity: O(1)

        Args:
            text: Input text to classify
            context: Optional conversation context
            user_id: Optional user ID for personalization

        Returns:
            Detection result with intent and metadata

        Raises:
            RuntimeError: If engine not initialized
        """
        if not self._initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")

        start_time = time.perf_counter()

        # Track which methods were attempted
        fast_path_attempted = False
        neural_attempted = False
        llm_attempted = False

        # Step 1: Try Fast-Path Router
        if self.fast_router:
            fast_path_attempted = True
            match = self.fast_router.match(text)

            if match and match.confidence >= 0.95:
                # Fast-path success!
                intent = self._create_intent_from_fast_path(match, text)
                latency_ms = (time.perf_counter() - start_time) * 1000

                self._update_metrics("fast_path", latency_ms)

                return DetectionResult(
                    intent=intent,
                    detection_method="fast_path",
                    latency_ms=latency_ms,
                    fast_path_attempted=True,
                    neural_attempted=False,
                    llm_attempted=False,
                    confidence=match.confidence,
                )

        # Step 2: Try Neural Classifier
        if self.neural_classifier:
            neural_attempted = True
            neural_result = await asyncio.get_event_loop().run_in_executor(
                None, self.neural_classifier.classify, text
            )

            # Check if confidence is high enough
            if neural_result.confidence >= 0.8:
                # Neural classifier success!
                # Extract entities using NER
                entities = {}
                if self.ner_extractor:
                    ner_result = self.ner_extractor.extract(text)
                    entities = ner_result.entities

                intent = self._create_intent_from_neural(neural_result, text, entities)
                latency_ms = (time.perf_counter() - start_time) * 1000

                self._update_metrics("neural", latency_ms)

                return DetectionResult(
                    intent=intent,
                    detection_method="neural",
                    latency_ms=latency_ms,
                    fast_path_attempted=fast_path_attempted,
                    neural_attempted=True,
                    llm_attempted=False,
                    confidence=neural_result.confidence,
                )

        # Step 3: Try LLM Fallback
        if self.llm_fallback:
            llm_attempted = True
            llm_result = await self.llm_fallback.classify_async(text, context)

            intent = self._create_intent_from_llm(llm_result, text)
            latency_ms = (time.perf_counter() - start_time) * 1000

            self._update_metrics("llm_fallback", latency_ms)

            return DetectionResult(
                intent=intent,
                detection_method="llm_fallback",
                latency_ms=latency_ms,
                fast_path_attempted=fast_path_attempted,
                neural_attempted=neural_attempted,
                llm_attempted=True,
                confidence=llm_result.confidence,
            )

        # Fallback: Return UNKNOWN intent
        intent = Intent(
            intent_type="unknown",
            entities={},
            confidence=0.0,
            requires_reasoning=False,
            original_input=text,
            resolved_input=text,
            detection_method="rule",  # Use 'rule' instead of 'fallback'
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        return DetectionResult(
            intent=intent,
            detection_method="fallback",
            latency_ms=latency_ms,
            fast_path_attempted=fast_path_attempted,
            neural_attempted=neural_attempted,
            llm_attempted=llm_attempted,
            confidence=0.0,
        )

    def detect_intent(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> DetectionResult:
        """Detect intent synchronously (wrapper for async method).

        Args:
            text: Input text to classify
            context: Optional conversation context
            user_id: Optional user ID for personalization

        Returns:
            Detection result with intent and metadata
        """
        # Run async method in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new task
            future = asyncio.ensure_future(self.detect_intent_async(text, context, user_id))
            return loop.run_until_complete(future)
        else:
            # If no loop is running, run directly
            return loop.run_until_complete(self.detect_intent_async(text, context, user_id))

    def _create_intent_from_fast_path(self, match: PatternMatch, text: str) -> Intent:
        """Create Intent object from fast-path match.

        Args:
            match: Pattern match result
            text: Original input text

        Returns:
            Intent object
        """
        return Intent(
            intent_type=match.intent_type,
            entities=match.entities,
            confidence=match.confidence,
            requires_reasoning=False,  # Fast-path intents are simple
            original_input=text,
            resolved_input=text,
            detection_method="rule",  # Fast-path uses rule-based matching
        )

    def _create_intent_from_neural(
        self,
        result: ClassificationResult,
        text: str,
        entities: dict[str, Entity],
    ) -> Intent:
        """Create Intent object from neural classifier result.

        Args:
            result: Neural classification result
            text: Original input text
            entities: Extracted entities from NER

        Returns:
            Intent object
        """
        # Determine if reasoning is required based on intent type
        requires_reasoning = self._requires_reasoning(result.intent_type)

        return Intent(
            intent_type=result.intent_type,
            entities=entities,
            confidence=result.confidence,
            requires_reasoning=requires_reasoning,
            original_input=text,
            resolved_input=text,
            detection_method="neural",
            alternative_intents=result.alternative_intents,
        )

    def _create_intent_from_llm(self, result: LLMClassificationResult, text: str) -> Intent:
        """Create Intent object from LLM fallback result.

        Args:
            result: LLM classification result
            text: Original input text

        Returns:
            Intent object
        """
        # Determine if reasoning is required
        requires_reasoning = self._requires_reasoning(result.intent_type)

        return Intent(
            intent_type=result.intent_type,
            entities=result.entities,
            confidence=result.confidence,
            requires_reasoning=requires_reasoning,
            original_input=text,
            resolved_input=text,
            detection_method="llm",  # LLM fallback uses llm method
        )

    def _requires_reasoning(self, intent_type: str) -> bool:
        """Determine if intent requires LLM reasoning.

        Args:
            intent_type: Intent type

        Returns:
            True if reasoning required, False otherwise
        """
        # Simple intents that don't require reasoning
        simple_intents = {
            "set_timer",
            "set_alarm",
            "query_time",
            "query_date",
            "play_music",
            "pause_media",
            "stop_media",
            "next_track",
            "previous_track",
            "volume_up",
            "volume_down",
            "cancel_timer",
            "cancel_alarm",
        }

        return intent_type not in simple_intents

    def record_feedback(
        self,
        text: str,
        predicted_intent: str,
        correct_intent: str,
        user_id: str | None = None,
    ) -> None:
        """Record user feedback for online learning.

        Args:
            text: Original input text
            predicted_intent: Intent predicted by engine
            correct_intent: Correct intent (from user feedback)
            user_id: Optional user ID
        """
        if self.feedback_store:
            self.feedback_store.add_feedback(
                input_text=text,
                predicted_intent=predicted_intent,
                correct_intent=correct_intent,
                user_id=user_id,
            )

    def trigger_retraining(self) -> None:
        """Trigger model retraining with collected feedback.

        This should be called periodically (e.g., weekly) to update models
        based on user feedback.
        """
        if self.online_learner:
            self.online_learner.retrain_models()

    def _update_metrics(self, method: str, latency_ms: float) -> None:
        """Update detection metrics.

        Args:
            method: Detection method used
            latency_ms: Detection latency
        """
        self.total_detections += 1
        self.total_latency_ms += latency_ms

        if method == "fast_path":
            self.fast_path_hits += 1
        elif method == "neural":
            self.neural_hits += 1
        elif method == "llm_fallback":
            self.llm_hits += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get detection metrics.

        Returns:
            Dictionary with metrics
        """
        if self.total_detections == 0:
            return {
                "total_detections": 0,
                "average_latency_ms": 0.0,
                "fast_path_percent": 0.0,
                "neural_percent": 0.0,
                "llm_percent": 0.0,
            }

        metrics = {
            "total_detections": self.total_detections,
            "average_latency_ms": self.total_latency_ms / self.total_detections,
            "fast_path_hits": self.fast_path_hits,
            "neural_hits": self.neural_hits,
            "llm_hits": self.llm_hits,
            "fast_path_percent": (self.fast_path_hits / self.total_detections) * 100,
            "neural_percent": (self.neural_hits / self.total_detections) * 100,
            "llm_percent": (self.llm_hits / self.total_detections) * 100,
        }

        # Add component metrics
        if self.fast_router:
            metrics["fast_router"] = self.fast_router.get_metrics()
        if self.neural_classifier:
            metrics["neural_classifier"] = self.neural_classifier.get_metrics()
        if self.llm_fallback:
            metrics["llm_fallback"] = self.llm_fallback.get_metrics()

        return metrics

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics for monitoring.

        Returns:
            Dictionary with routing statistics
        """
        if self.total_detections == 0:
            return {
                "total_detections": 0,
                "routing_distribution": {},
                "target_fast_path_percent": 80.0,
                "actual_fast_path_percent": 0.0,
                "performance_vs_target": "N/A",
            }

        fast_path_percent = (self.fast_path_hits / self.total_detections) * 100
        target_percent = 80.0

        return {
            "total_detections": self.total_detections,
            "routing_distribution": {
                "fast_path": self.fast_path_hits,
                "neural": self.neural_hits,
                "llm_fallback": self.llm_hits,
            },
            "target_fast_path_percent": target_percent,
            "actual_fast_path_percent": fast_path_percent,
            "performance_vs_target": (
                "✓ Meeting target"
                if fast_path_percent >= target_percent
                else f"⚠ Below target ({fast_path_percent:.1f}% vs {target_percent}%)"
            ),
        }
