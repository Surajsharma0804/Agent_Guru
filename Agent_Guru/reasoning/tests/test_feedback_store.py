"""
Unit tests for feedback storage system.

Tests cover:
- Database initialization
- Feedback storage and retrieval
- Metrics storage and retrieval
- Query operations
- Edge cases and error handling
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Agent_Guru.reasoning.learning.feedback_store import FeedbackStore
from Agent_Guru.reasoning.models.feedback import (
    FeedbackType,
    IntentFeedback,
    ModelPerformanceMetrics,
)


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
async def store(temp_db):
    """Create initialized feedback store."""
    store = FeedbackStore(temp_db)
    await store.initialize()
    return store


class TestFeedbackStoreInitialization:
    """Tests for store initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, temp_db):
        """Test initialization creates database file."""
        store = FeedbackStore(temp_db)
        await store.initialize()

        assert Path(temp_db).exists()

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, temp_db):
        """Test initialization creates required tables."""
        store = FeedbackStore(temp_db)
        await store.initialize()

        # Check tables exist by querying them
        feedback_list = await store.get_feedback_since(since=datetime.utcnow() - timedelta(days=1))
        assert feedback_list == []

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, temp_db):
        """Test initialization can be called multiple times."""
        store = FeedbackStore(temp_db)
        await store.initialize()
        await store.initialize()  # Should not raise

        assert Path(temp_db).exists()


class TestFeedbackStorage:
    """Tests for feedback storage operations."""

    @pytest.mark.asyncio
    async def test_store_feedback(self, store):
        """Test storing feedback."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="set timer for 5 minutes",
            predicted_intent="set_timer",
            predicted_entities={"duration": "5 minutes"},
            predicted_confidence=0.95,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )

        await store.store_feedback(feedback)

        # Verify stored
        retrieved = await store.get_feedback_since(since=datetime.utcnow() - timedelta(hours=1))
        assert len(retrieved) == 1
        assert retrieved[0].feedback_id == "test-123"

    @pytest.mark.asyncio
    async def test_store_multiple_feedback(self, store):
        """Test storing multiple feedback entries."""
        for i in range(5):
            feedback = IntentFeedback(
                feedback_id=f"test-{i}",
                user_id="user-456",
                original_input=f"test input {i}",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0",
            )
            await store.store_feedback(feedback)

        retrieved = await store.get_feedback_since(since=datetime.utcnow() - timedelta(hours=1))
        assert len(retrieved) == 5

    @pytest.mark.asyncio
    async def test_store_feedback_with_correction(self, store):
        """Test storing feedback with correction."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="play music",
            predicted_intent="search_music",
            predicted_entities={},
            predicted_confidence=0.75,
            correct_intent="play_music",
            correct_entities={"action": "play"},
            feedback_type=FeedbackType.INTENT_CORRECTION,
            model_version="v1.0",
        )

        await store.store_feedback(feedback)

        retrieved = await store.get_feedback_since(since=datetime.utcnow() - timedelta(hours=1))
        assert len(retrieved) == 1
        assert retrieved[0].correct_intent == "play_music"
        assert retrieved[0].correct_entities == {"action": "play"}


class TestFeedbackRetrieval:
    """Tests for feedback retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_feedback_since(self, store):
        """Test retrieving feedback since a time."""
        # Store old feedback
        old_feedback = IntentFeedback(
            feedback_id="old-123",
            user_id="user-456",
            timestamp=datetime.utcnow() - timedelta(days=10),
            original_input="old input",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(old_feedback)

        # Store recent feedback
        recent_feedback = IntentFeedback(
            feedback_id="recent-123",
            user_id="user-456",
            original_input="recent input",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(recent_feedback)

        # Get feedback from last 7 days
        retrieved = await store.get_feedback_since(since=datetime.utcnow() - timedelta(days=7))

        assert len(retrieved) == 1
        assert retrieved[0].feedback_id == "recent-123"

    @pytest.mark.asyncio
    async def test_get_feedback_by_model_version(self, store):
        """Test filtering feedback by model version."""
        # Store feedback for v1.0
        feedback_v1 = IntentFeedback(
            feedback_id="v1-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(feedback_v1)

        # Store feedback for v2.0
        feedback_v2 = IntentFeedback(
            feedback_id="v2-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v2.0",
        )
        await store.store_feedback(feedback_v2)

        # Get v1.0 feedback only
        retrieved = await store.get_feedback_since(
            since=datetime.utcnow() - timedelta(hours=1), model_version="v1.0"
        )

        assert len(retrieved) == 1
        assert retrieved[0].model_version == "v1.0"

    @pytest.mark.asyncio
    async def test_get_corrections_for_training(self, store):
        """Test retrieving corrections for training."""
        # Store positive feedback
        positive = IntentFeedback(
            feedback_id="positive-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(positive)

        # Store correction
        correction = IntentFeedback(
            feedback_id="correction-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="wrong",
            predicted_entities={},
            predicted_confidence=0.9,
            correct_intent="correct",
            feedback_type=FeedbackType.INTENT_CORRECTION,
            model_version="v1.0",
        )
        await store.store_feedback(correction)

        # Get corrections only
        corrections = await store.get_corrections_for_training(model_version="v1.0")

        assert len(corrections) == 1
        assert corrections[0].feedback_id == "correction-123"

    @pytest.mark.asyncio
    async def test_get_corrections_with_limit(self, store):
        """Test limiting number of corrections returned."""
        # Store 5 corrections
        for i in range(5):
            correction = IntentFeedback(
                feedback_id=f"correction-{i}",
                user_id="user-456",
                original_input=f"test {i}",
                predicted_intent="wrong",
                predicted_entities={},
                predicted_confidence=0.9,
                correct_intent="correct",
                feedback_type=FeedbackType.INTENT_CORRECTION,
                model_version="v1.0",
            )
            await store.store_feedback(correction)

        # Get only 3
        corrections = await store.get_corrections_for_training(model_version="v1.0", limit=3)

        assert len(corrections) == 3


class TestMetricsStorage:
    """Tests for metrics storage operations."""

    @pytest.mark.asyncio
    async def test_store_metrics(self, store):
        """Test storing performance metrics."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03,
        )

        await store.store_metrics(metrics)

        # Verify stored
        retrieved = await store.get_latest_metrics("v1.0")
        assert retrieved is not None
        assert retrieved.metric_id == "metric-123"

    @pytest.mark.asyncio
    async def test_get_latest_metrics(self, store):
        """Test retrieving latest metrics."""
        # Store old metrics
        old_metrics = ModelPerformanceMetrics(
            metric_id="old-123",
            model_version="v1.0",
            timestamp=datetime.utcnow() - timedelta(days=7),
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03,
        )
        await store.store_metrics(old_metrics)

        # Store recent metrics
        recent_metrics = ModelPerformanceMetrics(
            metric_id="recent-123",
            model_version="v1.0",
            total_predictions=200,
            correct_predictions=190,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03,
        )
        await store.store_metrics(recent_metrics)

        # Get latest
        retrieved = await store.get_latest_metrics("v1.0")
        assert retrieved.metric_id == "recent-123"

    @pytest.mark.asyncio
    async def test_get_latest_metrics_no_data(self, store):
        """Test retrieving metrics when none exist."""
        retrieved = await store.get_latest_metrics("v1.0")
        assert retrieved is None


class TestFeedbackCount:
    """Tests for feedback counting operations."""

    @pytest.mark.asyncio
    async def test_get_feedback_count(self, store):
        """Test counting feedback entries."""
        # Store 3 feedback entries
        for i in range(3):
            feedback = IntentFeedback(
                feedback_id=f"test-{i}",
                user_id="user-456",
                original_input=f"test {i}",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0",
            )
            await store.store_feedback(feedback)

        count = await store.get_feedback_count()
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_feedback_count_by_model_version(self, store):
        """Test counting feedback by model version."""
        # Store feedback for v1.0
        for i in range(2):
            feedback = IntentFeedback(
                feedback_id=f"v1-{i}",
                user_id="user-456",
                original_input=f"test {i}",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0",
            )
            await store.store_feedback(feedback)

        # Store feedback for v2.0
        feedback = IntentFeedback(
            feedback_id="v2-0",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v2.0",
        )
        await store.store_feedback(feedback)

        count = await store.get_feedback_count(model_version="v1.0")
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_feedback_count_since(self, store):
        """Test counting feedback since a time."""
        # Store old feedback
        old_feedback = IntentFeedback(
            feedback_id="old-123",
            user_id="user-456",
            timestamp=datetime.utcnow() - timedelta(days=10),
            original_input="old",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(old_feedback)

        # Store recent feedback
        recent_feedback = IntentFeedback(
            feedback_id="recent-123",
            user_id="user-456",
            original_input="recent",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0",
        )
        await store.store_feedback(recent_feedback)

        count = await store.get_feedback_count(since=datetime.utcnow() - timedelta(days=7))
        assert count == 1
