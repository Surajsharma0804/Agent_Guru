"""
Unit tests for the FaceRecognizer class.

Tests basic functionality of embedding extraction and identity matching.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from guru_vision.recognition.recognizer import FaceRecognizer, MatchResult


class TestFaceRecognizerInitialization:
    """Test FaceRecognizer initialization."""
    
    def test_init_missing_onnxruntime(self):
        """Test that ImportError is raised when onnxruntime is not available."""
        with patch.dict('sys.modules', {'onnxruntime': None}):
            with pytest.raises(ImportError, match="ONNX Runtime is not installed"):
                FaceRecognizer("dummy_path.onnx")
    
    def test_init_model_not_found(self):
        """Test that RuntimeError is raised when model file doesn't exist."""
        with pytest.raises(RuntimeError, match="Model file not found"):
            FaceRecognizer("nonexistent_model.onnx")
    
    @patch('onnxruntime.InferenceSession')
    @patch('os.path.exists')
    def test_init_gpu_enabled(self, mock_exists, mock_session):
        """Test initialization with GPU enabled."""
        mock_exists.return_value = True
        mock_session_instance = MagicMock()
        mock_session_instance.get_inputs.return_value = [MagicMock(name='input', shape=[1, 3, 112, 112])]
        mock_session_instance.get_outputs.return_value = [MagicMock(name='output')]
        mock_session_instance.get_providers.return_value = ['CUDAExecutionProvider']
        mock_session.return_value = mock_session_instance
        
        recognizer = FaceRecognizer("model.onnx", use_gpu=True)
        
        # Verify GPU provider was requested
        call_args = mock_session.call_args
        # call_args is a tuple of (args, kwargs), providers are in kwargs
        providers = call_args[1]['providers']
        assert 'CUDAExecutionProvider' in providers
        assert recognizer.use_gpu is True
    
    @patch('onnxruntime.InferenceSession')
    @patch('os.path.exists')
    def test_init_cpu_only(self, mock_exists, mock_session):
        """Test initialization with CPU only."""
        mock_exists.return_value = True
        mock_session_instance = MagicMock()
        mock_session_instance.get_inputs.return_value = [MagicMock(name='input', shape=[1, 3, 112, 112])]
        mock_session_instance.get_outputs.return_value = [MagicMock(name='output')]
        mock_session_instance.get_providers.return_value = ['CPUExecutionProvider']
        mock_session.return_value = mock_session_instance
        
        recognizer = FaceRecognizer("model.onnx", use_gpu=False)
        
        # Verify only CPU provider was requested
        call_args = mock_session.call_args
        # call_args is a tuple of (args, kwargs), providers are in kwargs
        providers = call_args[1]['providers']
        assert providers == ['CPUExecutionProvider']
        assert recognizer.use_gpu is False


class TestExtractEmbedding:
    """Test extract_embedding method."""
    
    @patch('onnxruntime.InferenceSession')
    @patch('os.path.exists')
    def setup_recognizer(self, mock_exists, mock_session):
        """Helper to create a mocked recognizer."""
        mock_exists.return_value = True
        mock_session_instance = MagicMock()
        mock_session_instance.get_inputs.return_value = [MagicMock(name='input', shape=[1, 3, 112, 112])]
        mock_session_instance.get_outputs.return_value = [MagicMock(name='output')]
        mock_session_instance.get_providers.return_value = ['CPUExecutionProvider']
        mock_session.return_value = mock_session_instance
        return FaceRecognizer("model.onnx", use_gpu=False)
    
    def test_extract_embedding_invalid_shape(self):
        """Test that ValueError is raised for invalid input shape."""
        recognizer = self.setup_recognizer()
        
        # Wrong shape
        invalid_face = np.zeros((100, 100, 3), dtype=np.uint8)
        
        with pytest.raises(ValueError, match="Input face must be 112x112x3"):
            recognizer.extract_embedding(invalid_face)
    
    def test_extract_embedding_valid_input(self):
        """Test embedding extraction with valid input."""
        recognizer = self.setup_recognizer()
        
        # Create valid input
        aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Mock the ONNX session to return a dummy embedding
        dummy_embedding = np.random.randn(1, 512).astype(np.float32)
        recognizer.session.run = MagicMock(return_value=[dummy_embedding])
        
        # Extract embedding
        embedding = recognizer.extract_embedding(aligned_face)
        
        # Verify output shape
        assert embedding.shape == (512,)
        
        # Verify L2 normalization (embedding should have unit length)
        norm = np.linalg.norm(embedding)
        assert np.isclose(norm, 1.0, atol=1e-6)
    
    def test_extract_embedding_preprocessing(self):
        """Test that preprocessing is done correctly."""
        recognizer = self.setup_recognizer()
        
        # Create test input with known values
        aligned_face = np.ones((112, 112, 3), dtype=np.uint8) * 127
        
        # Mock the ONNX session to capture input
        captured_input = None
        def capture_run(output_names, input_dict):
            nonlocal captured_input
            captured_input = input_dict[recognizer.input_name]
            return [np.random.randn(1, 512).astype(np.float32)]
        
        recognizer.session.run = capture_run
        
        # Extract embedding
        recognizer.extract_embedding(aligned_face)
        
        # Verify preprocessing: (127 / 127.5) - 1.0 ≈ -0.00392
        assert captured_input is not None
        assert captured_input.shape == (1, 3, 112, 112)
        # Check normalization
        expected_value = (127.0 / 127.5) - 1.0
        assert np.allclose(captured_input[0, 0, 0, 0], expected_value, atol=0.01)


class TestMatchIdentity:
    """Test match_identity method."""
    
    @patch('onnxruntime.InferenceSession')
    @patch('os.path.exists')
    def setup_recognizer(self, mock_exists, mock_session):
        """Helper to create a mocked recognizer."""
        mock_exists.return_value = True
        mock_session_instance = MagicMock()
        mock_session_instance.get_inputs.return_value = [MagicMock(name='input', shape=[1, 3, 112, 112])]
        mock_session_instance.get_outputs.return_value = [MagicMock(name='output')]
        mock_session_instance.get_providers.return_value = ['CPUExecutionProvider']
        mock_session.return_value = mock_session_instance
        return FaceRecognizer("model.onnx", use_gpu=False)
    
    def test_match_identity_invalid_embedding(self):
        """Test that ValueError is raised for invalid embedding."""
        recognizer = self.setup_recognizer()
        mock_db = Mock()
        
        # Wrong shape
        invalid_embedding = np.zeros((256,))
        
        with pytest.raises(ValueError, match="512-dimensional numpy array"):
            recognizer.match_identity(invalid_embedding, mock_db)
    
    def test_match_identity_invalid_threshold(self):
        """Test that ValueError is raised for invalid threshold."""
        recognizer = self.setup_recognizer()
        mock_db = Mock()
        
        valid_embedding = np.random.randn(512).astype(np.float32)
        
        with pytest.raises(ValueError, match="Threshold must be between 0.0 and 1.0"):
            recognizer.match_identity(valid_embedding, mock_db, threshold=1.5)
    
    def test_match_identity_found(self):
        """Test successful identity match."""
        recognizer = self.setup_recognizer()
        
        # Mock database that returns a match
        mock_db = Mock()
        mock_db.search.return_value = {
            'identity': 'John Doe',
            'confidence': 0.85,
            'permission_level': 'admin'
        }
        
        embedding = np.random.randn(512).astype(np.float32)
        result = recognizer.match_identity(embedding, mock_db, threshold=0.6)
        
        # Verify result
        assert isinstance(result, MatchResult)
        assert result.identity == 'John Doe'
        assert result.confidence == 0.85
        assert result.permission_level == 'admin'
        
        # Verify database was called correctly
        mock_db.search.assert_called_once()
        call_args = mock_db.search.call_args
        assert np.array_equal(call_args[0][0], embedding)
        assert call_args[0][1] == 0.6
    
    def test_match_identity_not_found(self):
        """Test when no identity matches above threshold."""
        recognizer = self.setup_recognizer()
        
        # Mock database that returns None (no match)
        mock_db = Mock()
        mock_db.search.return_value = None
        
        embedding = np.random.randn(512).astype(np.float32)
        result = recognizer.match_identity(embedding, mock_db, threshold=0.6)
        
        # Verify result is "Unknown"
        assert isinstance(result, MatchResult)
        assert result.identity == "Unknown"
        assert result.confidence == 0.0
        assert result.permission_level == "guest"
    
    def test_match_identity_custom_threshold(self):
        """Test matching with custom threshold."""
        recognizer = self.setup_recognizer()
        
        mock_db = Mock()
        mock_db.search.return_value = {
            'identity': 'Jane Smith',
            'confidence': 0.75,
            'permission_level': 'user'
        }
        
        embedding = np.random.randn(512).astype(np.float32)
        result = recognizer.match_identity(embedding, mock_db, threshold=0.7)
        
        # Verify custom threshold was passed to database
        call_args = mock_db.search.call_args
        assert call_args[0][1] == 0.7


class TestMatchResult:
    """Test MatchResult dataclass."""
    
    def test_match_result_creation(self):
        """Test creating a MatchResult."""
        result = MatchResult(
            identity="Test User",
            confidence=0.92,
            permission_level="admin"
        )
        
        assert result.identity == "Test User"
        assert result.confidence == 0.92
        assert result.permission_level == "admin"
