"""
Tests for GuruVision event system and callbacks.

This module tests the event registration and emission functionality
of the GuruVisionEngine.

Requirements: 13.3, 13.5
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from guru_vision.engine import GuruVisionEngine


class TestEventSystem:
    """Test suite for event system and callbacks."""
    
    def test_register_callback_valid_event_types(self):
        """Test registering callbacks for all valid event types."""
        engine = GuruVisionEngine()
        
        # Valid event types
        valid_events = [
            'identity_recognized',
            'new_identity',
            'permission_changed',
            'error',
            'system_ready'
        ]
        
        for event_type in valid_events:
            callback = Mock()
            engine.register_callback(event_type, callback)
            
            # Verify callback was registered
            assert callback in engine.callbacks[event_type]
    
    def test_register_callback_invalid_event_type(self):
        """Test that registering callback with invalid event type raises ValueError."""
        engine = GuruVisionEngine()
        callback = Mock()
        
        with pytest.raises(ValueError, match="Invalid event_type"):
            engine.register_callback('invalid_event', callback)
    
    def test_register_callback_non_callable(self):
        """Test that registering non-callable raises ValueError."""
        engine = GuruVisionEngine()
        
        with pytest.raises(ValueError, match="Callback must be a callable"):
            engine.register_callback('identity_recognized', "not_a_function")
    
    def test_register_multiple_callbacks_same_event(self):
        """Test registering multiple callbacks for the same event type."""
        engine = GuruVisionEngine()
        
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()
        
        engine.register_callback('identity_recognized', callback1)
        engine.register_callback('identity_recognized', callback2)
        engine.register_callback('identity_recognized', callback3)
        
        # All callbacks should be registered
        assert len(engine.callbacks['identity_recognized']) == 3
        assert callback1 in engine.callbacks['identity_recognized']
        assert callback2 in engine.callbacks['identity_recognized']
        assert callback3 in engine.callbacks['identity_recognized']
    
    def test_emit_event_triggers_callbacks(self):
        """Test that emitting an event triggers all registered callbacks."""
        engine = GuruVisionEngine()
        
        callback1 = Mock()
        callback2 = Mock()
        
        engine.register_callback('identity_recognized', callback1)
        engine.register_callback('identity_recognized', callback2)
        
        # Emit event
        event_data = {
            'identity': 'John Doe',
            'confidence': 0.95,
            'timestamp': '2024-01-15T10:30:00Z'
        }
        engine._emit_event('identity_recognized', event_data)
        
        # Both callbacks should be called with event data
        callback1.assert_called_once_with(event_data)
        callback2.assert_called_once_with(event_data)
    
    def test_emit_event_no_callbacks(self):
        """Test that emitting an event with no callbacks doesn't raise error."""
        engine = GuruVisionEngine()
        
        # Should not raise any exception
        event_data = {'test': 'data'}
        engine._emit_event('identity_recognized', event_data)
    
    def test_emit_event_callback_exception_handled(self):
        """Test that exceptions in callbacks are caught and logged."""
        engine = GuruVisionEngine()
        engine.logger = Mock()
        
        # Create callback that raises exception
        def failing_callback(data):
            raise RuntimeError("Callback error")
        
        engine.register_callback('identity_recognized', failing_callback)
        
        # Emit event - should not raise exception
        event_data = {'test': 'data'}
        engine._emit_event('identity_recognized', event_data)
        
        # Logger should have recorded the error
        assert engine.logger.error.called
    
    def test_system_ready_event_emitted_on_initialization(self):
        """Test that system_ready event is emitted after successful initialization."""
        engine = GuruVisionEngine()
        
        callback = Mock()
        engine.register_callback('system_ready', callback)
        
        # Mock all dependencies
        with patch('guru_vision.config.GuruVisionConfig') as mock_config, \
             patch('guru_vision.utils.logging.setup_logging'), \
             patch('guru_vision.utils.logging.get_logger'), \
             patch('guru_vision.detection.detector.FaceDetector'), \
             patch('guru_vision.alignment.aligner.FaceAligner'), \
             patch('guru_vision.recognition.recognizer.FaceRecognizer'), \
             patch('guru_vision.liveness.detector.LivenessDetector'), \
             patch('guru_vision.emotion.recognizer.EmotionRecognizer'), \
             patch('guru_vision.tracking.tracker.FaceTracker'), \
             patch('guru_vision.database.face_db.FaceDatabase'):
            
            # Configure mock config
            mock_config_instance = MagicMock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.to_dict.return_value = {}
            
            # Initialize engine
            engine.initialize()
            
            # Callback should have been called
            assert callback.called
            call_args = callback.call_args[0][0]
            assert 'timestamp' in call_args
            assert 'config' in call_args
            assert 'num_identities' in call_args
    
    def test_new_identity_event_emitted_on_add(self):
        """Test that new_identity event is emitted when adding identity."""
        engine = GuruVisionEngine()
        
        callback = Mock()
        engine.register_callback('new_identity', callback)
        
        # Mock initialization
        engine.initialized = True
        engine.logger = Mock()
        engine.detector = Mock()
        engine.aligner = Mock()
        engine.recognizer = Mock()
        engine.database = Mock()
        
        # Mock detection and embedding extraction
        mock_detection = Mock()
        mock_detection.confidence = 0.9
        mock_detection.bbox = (0, 0, 100, 100)
        engine.detector.detect.return_value = [mock_detection]
        
        engine.aligner.align.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        engine.recognizer.extract_embedding.return_value = np.random.randn(512)
        engine.database.add_identity.return_value = True
        
        # Add identity
        test_image = np.zeros((224, 224, 3), dtype=np.uint8)
        images = [test_image] * 5
        engine.add_identity('Test User', images, 'user')
        
        # Callback should have been called
        assert callback.called
        call_args = callback.call_args[0][0]
        assert call_args['identity'] == 'Test User'
        assert call_args['permission_level'] == 'user'
        assert 'num_embeddings' in call_args
        assert 'timestamp' in call_args
    
    def test_permission_changed_event_emitted_on_update(self):
        """Test that permission_changed event is emitted when updating permission."""
        engine = GuruVisionEngine()
        
        callback = Mock()
        engine.register_callback('permission_changed', callback)
        
        # Mock initialization
        engine.initialized = True
        engine.logger = Mock()
        engine.database = Mock()
        engine.database.update_permission.return_value = True
        
        # Update permission
        engine.update_permission('Test User', 'admin')
        
        # Callback should have been called
        assert callback.called
        call_args = callback.call_args[0][0]
        assert call_args['identity'] == 'Test User'
        assert call_args['new_permission_level'] == 'admin'
        assert 'timestamp' in call_args
    
    def test_error_event_emitted_on_detection_failure(self):
        """Test that error event is emitted when face detection fails."""
        engine = GuruVisionEngine()
        
        callback = Mock()
        engine.register_callback('error', callback)
        
        # Mock initialization
        engine.initialized = True
        engine.logger = Mock()
        engine.config = Mock()
        engine.config.enable_low_light_enhancement = False
        engine.config.detection_confidence = 0.5
        engine.config.enable_tracking = False
        engine.detector = Mock()
        
        # Make detector raise exception
        engine.detector.detect.side_effect = RuntimeError("Detection failed")
        
        # Process frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.process_frame(test_frame)
        
        # Error callback should have been called
        assert callback.called
        call_args = callback.call_args[0][0]
        assert call_args['component'] == 'face_detection'
        assert call_args['error_type'] == 'RuntimeError'
        assert 'Detection failed' in call_args['error_message']
        assert 'timestamp' in call_args
        assert 'frame_id' in call_args
    
    def test_identity_recognized_event_emitted_on_recognition(self):
        """Test that identity_recognized event is emitted when identity is recognized."""
        engine = GuruVisionEngine()
        
        callback = Mock()
        engine.register_callback('identity_recognized', callback)
        
        # Mock initialization
        engine.initialized = True
        engine.logger = Mock()
        engine.config = Mock()
        engine.config.enable_low_light_enhancement = False
        engine.config.detection_confidence = 0.5
        engine.config.enable_tracking = False
        engine.config.enable_liveness = False
        engine.config.enable_emotion = False
        engine.config.recognition_threshold = 0.6
        
        engine.detector = Mock()
        engine.aligner = Mock()
        engine.recognizer = Mock()
        engine.database = Mock()
        
        # Mock detection
        mock_detection = Mock()
        mock_detection.bbox = (100, 100, 200, 200)
        mock_detection.confidence = 0.9
        engine.detector.detect.return_value = [mock_detection]
        
        # Mock alignment and recognition
        engine.aligner.align.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        engine.recognizer.extract_embedding.return_value = np.random.randn(512)
        
        # Mock match result
        mock_match = Mock()
        mock_match.identity = 'John Doe'
        mock_match.confidence = 0.95
        mock_match.permission_level = 'user'
        engine.recognizer.match_identity.return_value = mock_match
        
        # Process frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.process_frame(test_frame)
        
        # Identity recognized callback should have been called
        assert callback.called
        call_args = callback.call_args[0][0]
        assert call_args['identity'] == 'John Doe'
        assert call_args['confidence'] == 0.95
        assert call_args['permission_level'] == 'user'
        assert 'timestamp' in call_args
        assert 'frame_id' in call_args
        assert 'tracking_id' in call_args


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
