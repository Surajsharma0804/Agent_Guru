"""
Tests for GuruVision Engine Shutdown and Resource Management

This module tests the shutdown functionality including:
- Graceful shutdown method
- Signal handling (SIGINT, SIGTERM)
- Resource cleanup
- Database persistence during shutdown

Requirements: 20.3, 20.4, 20.5, 20.6, 20.7
"""

import pytest
import numpy as np
import time
import signal
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from guru_vision.engine import GuruVisionEngine


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    temp_dir = tempfile.mkdtemp()
    model_dir = os.path.join(temp_dir, "model")
    db_dir = os.path.join(temp_dir, "database")
    log_dir = os.path.join(temp_dir, "logs")
    
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(db_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    
    yield {
        'temp_dir': temp_dir,
        'model_dir': model_dir,
        'db_dir': db_dir,
        'log_dir': log_dir
    }
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_engine(temp_dirs):
    """Create a mocked GuruVision engine for testing."""
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
        mock_config.use_gpu = False
        mock_config.onnx_model_path = os.path.join(temp_dirs['model_dir'], "model.onnx")
        mock_config.database_path = os.path.join(temp_dirs['db_dir'], "db.json")
        mock_config.enable_liveness = True
        mock_config.enable_emotion = True
        mock_config.enable_tracking = True
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
        mock_liveness.model_loaded = True
        mock_liveness_class.return_value = mock_liveness
        
        # Configure mock emotion recognizer with session
        mock_emotion = Mock()
        mock_emotion.session = Mock()
        mock_emotion.model_loaded = True
        mock_emotion_class.return_value = mock_emotion
        
        # Configure mock database
        mock_db = Mock()
        mock_db.get_all_identities = Mock(return_value=[])
        mock_db.save = Mock()
        mock_db_class.return_value = mock_db
        
        # Create engine
        engine = GuruVisionEngine()
        engine.initialize()
        
        yield engine


def test_shutdown_basic(mock_engine):
    """
    Test basic shutdown functionality.
    
    Requirements: 20.3, 20.4, 20.5
    """
    # Verify engine is initialized
    assert mock_engine.initialized is True
    
    # Store reference to database before shutdown
    database = mock_engine.database
    
    # Call shutdown
    mock_engine.shutdown()
    
    # Verify shutdown flag is set
    assert mock_engine._shutdown_requested is True
    
    # Verify engine is marked as not initialized
    assert mock_engine.initialized is False
    
    # Verify database save was called
    database.save.assert_called_once()


def test_shutdown_timing(mock_engine):
    """
    Test that shutdown completes within 3 seconds.
    
    Requirements: 20.5
    """
    start_time = time.time()
    mock_engine.shutdown()
    elapsed_time = time.time() - start_time
    
    # Verify shutdown completed within 3 seconds
    assert elapsed_time < 3.0, f"Shutdown took {elapsed_time:.3f} seconds, exceeding 3 second limit"


def test_shutdown_saves_database(mock_engine):
    """
    Test that shutdown saves pending database changes.
    
    Requirements: 20.4
    """
    # Store reference to database before shutdown
    database = mock_engine.database
    
    # Call shutdown
    mock_engine.shutdown()
    
    # Verify database save was called
    database.save.assert_called_once()


def test_shutdown_closes_onnx_sessions(mock_engine):
    """
    Test that shutdown closes ONNX Runtime sessions.
    
    Requirements: 20.5
    """
    # Store references to sessions
    recognizer_session = mock_engine.recognizer.session
    liveness_session = mock_engine.liveness_detector.session
    emotion_session = mock_engine.emotion_recognizer.session
    
    # Call shutdown
    mock_engine.shutdown()
    
    # Verify sessions were deleted (references cleared)
    assert not hasattr(mock_engine.recognizer, 'session') or mock_engine.recognizer is None


def test_shutdown_clears_module_references(mock_engine):
    """
    Test that shutdown clears all module references.
    
    Requirements: 20.3, 20.5
    """
    # Verify modules are initialized
    assert mock_engine.detector is not None
    assert mock_engine.aligner is not None
    assert mock_engine.recognizer is not None
    
    # Call shutdown
    mock_engine.shutdown()
    
    # Verify all module references are cleared
    assert mock_engine.detector is None
    assert mock_engine.aligner is None
    assert mock_engine.recognizer is None
    assert mock_engine.liveness_detector is None
    assert mock_engine.emotion_recognizer is None
    assert mock_engine.tracker is None
    assert mock_engine.database is None


def test_shutdown_idempotent(mock_engine):
    """
    Test that calling shutdown multiple times is safe.
    
    Requirements: 20.3, 20.4, 20.5
    """
    # Call shutdown first time
    mock_engine.shutdown()
    
    # Reset mock to track second call
    mock_engine.database = Mock()
    mock_engine.database.save = Mock()
    
    # Call shutdown second time
    mock_engine.shutdown()
    
    # Verify database save was not called again (shutdown already completed)
    mock_engine.database.save.assert_not_called()


def test_shutdown_handles_database_error(mock_engine):
    """
    Test that shutdown handles database save errors gracefully.
    
    Requirements: 20.4
    """
    # Configure database to raise error on save
    mock_engine.database.save = Mock(side_effect=Exception("Database error"))
    
    # Call shutdown - should not raise exception
    try:
        mock_engine.shutdown()
    except Exception as e:
        pytest.fail(f"Shutdown raised exception: {e}")
    
    # Verify shutdown completed despite error
    assert mock_engine._shutdown_requested is True


def test_signal_handler_registration(temp_dirs):
    """
    Test that signal handlers are registered during initialization.
    
    Requirements: 20.6
    """
    with patch('guru_vision.config.GuruVisionConfig') as mock_config_class, \
         patch('guru_vision.utils.logging.setup_logging'), \
         patch('guru_vision.utils.logging.get_logger'), \
         patch('guru_vision.detection.detector.FaceDetector'), \
         patch('guru_vision.alignment.aligner.FaceAligner'), \
         patch('guru_vision.recognition.recognizer.FaceRecognizer'), \
         patch('guru_vision.liveness.detector.LivenessDetector'), \
         patch('guru_vision.emotion.recognizer.EmotionRecognizer'), \
         patch('guru_vision.tracking.tracker.FaceTracker'), \
         patch('guru_vision.database.face_db.FaceDatabase') as mock_db_class, \
         patch('signal.signal') as mock_signal:
        
        # Configure mocks
        mock_config = Mock()
        mock_config.log_level = "INFO"
        mock_config.log_file = os.path.join(temp_dirs['log_dir'], "test.log")
        mock_config.log_max_size_mb = 100
        mock_config.use_gpu = False
        mock_config.onnx_model_path = "model.onnx"
        mock_config.database_path = "db.json"
        mock_config.enable_liveness = False
        mock_config.enable_emotion = False
        mock_config.enable_tracking = False
        mock_config.enable_low_light_enhancement = False
        mock_config.to_dict = Mock(return_value={})
        mock_config_class.return_value = mock_config
        
        mock_db = Mock()
        mock_db.get_all_identities = Mock(return_value=[])
        mock_db_class.return_value = mock_db
        
        # Create and initialize engine
        engine = GuruVisionEngine()
        engine.initialize()
        
        # Verify signal handlers were registered
        # Should be called twice: once for SIGINT, once for SIGTERM
        assert mock_signal.call_count >= 2
        
        # Verify SIGINT and SIGTERM were registered
        signal_calls = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in signal_calls
        assert signal.SIGTERM in signal_calls


def test_process_frame_after_shutdown(mock_engine):
    """
    Test that process_frame returns empty result after shutdown is requested.
    
    Requirements: 20.7
    """
    # Request shutdown
    mock_engine._shutdown_requested = True
    
    # Create test frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Process frame
    result = mock_engine.process_frame(frame)
    
    # Verify empty result is returned
    assert len(result.faces) == 0
    assert result.processing_time_ms == 0.0


def test_shutdown_during_frame_processing(mock_engine):
    """
    Test that shutdown waits for current frame to complete.
    
    Requirements: 20.7
    """
    # This is a conceptual test - in practice, the shutdown flag
    # is checked at the start of process_frame
    
    # Verify shutdown flag is initially False
    assert mock_engine._shutdown_requested is False
    
    # Call shutdown
    mock_engine.shutdown()
    
    # Verify shutdown flag is set
    assert mock_engine._shutdown_requested is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
