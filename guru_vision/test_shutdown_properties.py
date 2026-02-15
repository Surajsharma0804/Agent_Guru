"""
Property-Based Tests for GuruVision Engine Shutdown and Resource Cleanup

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the shutdown mechanism.

Properties tested:
- Property 23: Resource Cleanup on Shutdown
"""

import pytest
import numpy as np
import tempfile
import os
import shutil
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings, HealthCheck
from guru_vision.engine import GuruVisionEngine


# Custom strategies for generating test data

@st.composite
def engine_state(draw):
    """
    Generate a valid engine state configuration.
    
    This represents different configurations the engine might be in
    when shutdown is called.
    """
    return {
        'enable_liveness': draw(st.booleans()),
        'enable_emotion': draw(st.booleans()),
        'enable_tracking': draw(st.booleans()),
        'use_gpu': draw(st.booleans()),
        'has_pending_db_changes': draw(st.booleans()),
    }


def create_temp_dirs():
    """Create temporary directories for testing."""
    temp_dir = tempfile.mkdtemp()
    model_dir = os.path.join(temp_dir, "model")
    db_dir = os.path.join(temp_dir, "database")
    log_dir = os.path.join(temp_dir, "logs")
    
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(db_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    
    return {
        'temp_dir': temp_dir,
        'model_dir': model_dir,
        'db_dir': db_dir,
        'log_dir': log_dir
    }


def cleanup_temp_dirs(dirs):
    """Clean up temporary directories."""
    if dirs and 'temp_dir' in dirs:
        shutil.rmtree(dirs['temp_dir'], ignore_errors=True)


def create_mock_engine_with_state(state):
    """
    Create a mocked GuruVisionEngine with the specified state.
    
    Args:
        state: Dictionary containing engine configuration state
        
    Returns:
        Tuple of (engine, temp_dirs, mock_database)
    """
    temp_dirs = create_temp_dirs()
    
    try:
        with patch('guru_vision.config.GuruVisionConfig') as mock_config_class, \
             patch('guru_vision.utils.logging.setup_logging'), \
             patch('guru_vision.utils.logging.get_logger') as mock_get_logger, \
             patch('guru_vision.detection.detector.FaceDetector'), \
             patch('guru_vision.alignment.aligner.FaceAligner'), \
             patch('guru_vision.recognition.recognizer.FaceRecognizer') as mock_recognizer_class, \
             patch('guru_vision.liveness.detector.LivenessDetector') as mock_liveness_class, \
             patch('guru_vision.emotion.recognizer.EmotionRecognizer') as mock_emotion_class, \
             patch('guru_vision.tracking.tracker.FaceTracker'), \
             patch('guru_vision.database.face_db.FaceDatabase') as mock_db_class:
            
            # Configure mock config
            mock_config = Mock()
            mock_config.log_level = "INFO"
            mock_config.log_file = os.path.join(temp_dirs['log_dir'], "test.log")
            mock_config.log_max_size_mb = 100
            mock_config.use_gpu = state['use_gpu']
            mock_config.onnx_model_path = os.path.join(temp_dirs['model_dir'], "model.onnx")
            mock_config.database_path = os.path.join(temp_dirs['db_dir'], "db.json")
            mock_config.enable_liveness = state['enable_liveness']
            mock_config.enable_emotion = state['enable_emotion']
            mock_config.enable_tracking = state['enable_tracking']
            mock_config.enable_low_light_enhancement = False
            mock_config.liveness_model_path = "liveness.onnx"
            mock_config.tracker_algorithm = "deepsort"
            mock_config.tracker_max_age = 30
            mock_config.recognition_threshold = 0.6
            mock_config.detection_confidence = 0.5
            mock_config.to_dict = Mock(return_value={})
            mock_config_class.return_value = mock_config
            
            # Configure mock logger
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            # Configure mock recognizer with session
            mock_recognizer = Mock()
            mock_recognizer.session = Mock()
            mock_recognizer_class.return_value = mock_recognizer
            
            # Configure mock liveness detector with session
            mock_liveness = Mock()
            mock_liveness.session = Mock()
            mock_liveness.model_loaded = state['enable_liveness']
            mock_liveness_class.return_value = mock_liveness
            
            # Configure mock emotion recognizer with session
            mock_emotion = Mock()
            mock_emotion.session = Mock()
            mock_emotion.model_loaded = state['enable_emotion']
            mock_emotion_class.return_value = mock_emotion
            
            # Configure mock database
            mock_db = Mock()
            mock_db.get_all_identities = Mock(return_value=[])
            mock_db.save = Mock()
            mock_db_class.return_value = mock_db
            
            # Create engine
            engine = GuruVisionEngine()
            engine.initialize()
            
            return engine, temp_dirs, mock_db
            
    except Exception as e:
        cleanup_temp_dirs(temp_dirs)
        raise


# Property 23: Resource Cleanup on Shutdown
# **Validates: Requirements 20.3, 20.4**

@given(state=engine_state())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_23_resource_cleanup_on_shutdown(state):
    """
    Property 23: Resource Cleanup on Shutdown
    
    For any system shutdown, all camera resources should be released and any
    pending database changes should be saved to disk.
    
    **Validates: Requirements 20.3, 20.4**
    
    Requirement 20.3: WHEN the GuruVision_System shuts down, THE GuruVision_System
    SHALL release all camera resources
    
    Requirement 20.4: WHEN the GuruVision_System shuts down, THE GuruVision_System
    SHALL save any pending database changes
    
    This property verifies that regardless of the engine's configuration state
    (enabled features, GPU usage, etc.), shutdown always:
    1. Saves the database
    2. Clears all module references
    3. Sets initialized flag to False
    4. Sets shutdown flag to True
    """
    engine = None
    temp_dirs = None
    mock_db = None
    
    try:
        # Create engine with the given state
        engine, temp_dirs, mock_db = create_mock_engine_with_state(state)
        
        # Verify engine is initialized before shutdown
        assert engine.initialized is True, \
            "Engine should be initialized before shutdown"
        
        # Store references to verify cleanup
        initial_detector = engine.detector
        initial_aligner = engine.aligner
        initial_recognizer = engine.recognizer
        initial_liveness = engine.liveness_detector
        initial_emotion = engine.emotion_recognizer
        initial_tracker = engine.tracker
        initial_database = engine.database
        
        # Verify modules are initialized (not None)
        assert initial_detector is not None, \
            "Detector should be initialized"
        assert initial_aligner is not None, \
            "Aligner should be initialized"
        assert initial_recognizer is not None, \
            "Recognizer should be initialized"
        
        # Liveness, emotion, and tracker may be None if disabled
        if state['enable_liveness']:
            assert initial_liveness is not None, \
                "Liveness detector should be initialized when enabled"
        
        if state['enable_emotion']:
            assert initial_emotion is not None, \
                "Emotion recognizer should be initialized when enabled"
        
        if state['enable_tracking']:
            assert initial_tracker is not None, \
                "Tracker should be initialized when enabled"
        
        assert initial_database is not None, \
            "Database should be initialized"
        
        # Call shutdown
        engine.shutdown()
        
        # Property verification: Database should be saved
        # Requirement 20.4: Save any pending database changes
        mock_db.save.assert_called_once(), \
            "Database save() should be called exactly once during shutdown"
        
        # Property verification: All module references should be cleared
        # Requirement 20.3: Release all camera resources (and other resources)
        assert engine.detector is None, \
            "Detector reference should be cleared after shutdown"
        assert engine.aligner is None, \
            "Aligner reference should be cleared after shutdown"
        assert engine.recognizer is None, \
            "Recognizer reference should be cleared after shutdown"
        assert engine.liveness_detector is None, \
            "Liveness detector reference should be cleared after shutdown"
        assert engine.emotion_recognizer is None, \
            "Emotion recognizer reference should be cleared after shutdown"
        assert engine.tracker is None, \
            "Tracker reference should be cleared after shutdown"
        assert engine.database is None, \
            "Database reference should be cleared after shutdown"
        
        # Property verification: Initialized flag should be False
        assert engine.initialized is False, \
            "Engine should be marked as not initialized after shutdown"
        
        # Property verification: Shutdown flag should be True
        assert engine._shutdown_requested is True, \
            "Shutdown flag should be set to True after shutdown"
        
    finally:
        # Clean up temporary directories
        if temp_dirs:
            cleanup_temp_dirs(temp_dirs)


@given(state=engine_state())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_shutdown_idempotency(state):
    """
    Property: Shutdown Idempotency
    
    For any engine state, calling shutdown multiple times should be safe
    and should not cause errors or duplicate resource cleanup operations.
    
    This ensures that shutdown can be called multiple times without side effects,
    which is important for error handling and signal handlers.
    """
    engine = None
    temp_dirs = None
    mock_db = None
    
    try:
        # Create engine with the given state
        engine, temp_dirs, mock_db = create_mock_engine_with_state(state)
        
        # Call shutdown first time
        engine.shutdown()
        
        # Verify database was saved once
        assert mock_db.save.call_count == 1, \
            "Database should be saved once on first shutdown"
        
        # Reset the mock to track subsequent calls
        mock_db.save.reset_mock()
        
        # Call shutdown second time
        engine.shutdown()
        
        # Verify database save was NOT called again
        assert mock_db.save.call_count == 0, \
            "Database save should not be called on subsequent shutdown calls"
        
        # Verify engine state remains consistent
        assert engine.initialized is False, \
            "Engine should remain not initialized"
        assert engine._shutdown_requested is True, \
            "Shutdown flag should remain True"
        assert engine.database is None, \
            "Database reference should remain None"
        
    finally:
        # Clean up temporary directories
        if temp_dirs:
            cleanup_temp_dirs(temp_dirs)


@given(state=engine_state())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_shutdown_with_database_error(state):
    """
    Property: Shutdown Resilience to Database Errors
    
    For any engine state, if the database save operation fails during shutdown,
    the shutdown should still complete and clean up other resources.
    
    This ensures that a database error doesn't prevent proper resource cleanup.
    """
    engine = None
    temp_dirs = None
    mock_db = None
    
    try:
        # Create engine with the given state
        engine, temp_dirs, mock_db = create_mock_engine_with_state(state)
        
        # Configure database to raise an error on save
        mock_db.save.side_effect = Exception("Database save failed")
        
        # Call shutdown - should not raise exception
        try:
            engine.shutdown()
        except Exception as e:
            pytest.fail(f"Shutdown should not raise exception even if database save fails: {e}")
        
        # Verify shutdown completed despite database error
        assert engine._shutdown_requested is True, \
            "Shutdown flag should be set even if database save fails"
        assert engine.initialized is False, \
            "Engine should be marked as not initialized even if database save fails"
        
        # Verify all module references are still cleared
        assert engine.detector is None, \
            "Detector should be cleared even if database save fails"
        assert engine.aligner is None, \
            "Aligner should be cleared even if database save fails"
        assert engine.recognizer is None, \
            "Recognizer should be cleared even if database save fails"
        assert engine.database is None, \
            "Database reference should be cleared even if save fails"
        
    finally:
        # Clean up temporary directories
        if temp_dirs:
            cleanup_temp_dirs(temp_dirs)


@given(
    state=engine_state(),
    num_shutdowns=st.integers(min_value=1, max_value=5)
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_multiple_shutdown_calls(state, num_shutdowns):
    """
    Property: Multiple Shutdown Calls Safety
    
    For any engine state and any number of shutdown calls, the engine should
    handle all calls gracefully without errors, and the database should only
    be saved once (on the first call).
    """
    engine = None
    temp_dirs = None
    mock_db = None
    
    try:
        # Create engine with the given state
        engine, temp_dirs, mock_db = create_mock_engine_with_state(state)
        
        # Call shutdown multiple times
        for i in range(num_shutdowns):
            try:
                engine.shutdown()
            except Exception as e:
                pytest.fail(f"Shutdown call {i+1} raised exception: {e}")
        
        # Verify database was saved exactly once (on first shutdown)
        assert mock_db.save.call_count == 1, \
            f"Database should be saved exactly once, but was called {mock_db.save.call_count} times"
        
        # Verify final state is consistent
        assert engine._shutdown_requested is True, \
            "Shutdown flag should be True after all shutdown calls"
        assert engine.initialized is False, \
            "Engine should be not initialized after all shutdown calls"
        assert engine.database is None, \
            "Database reference should be None after all shutdown calls"
        
    finally:
        # Clean up temporary directories
        if temp_dirs:
            cleanup_temp_dirs(temp_dirs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
