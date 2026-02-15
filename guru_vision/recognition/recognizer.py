"""
GuruVision Face Recognition Module

This module provides face embedding extraction and identity matching using
ONNX Runtime for fast, cross-platform inference.

Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 11.2, 11.3, 11.4, 11.5
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
import os


@dataclass
class MatchResult:
    """
    Result of identity matching operation.
    
    Attributes:
        identity: Name of the matched identity or "Unknown"
        confidence: Similarity score (0.0 to 1.0)
        permission_level: Permission level of the matched identity
    """
    identity: str
    confidence: float
    permission_level: str


class FaceRecognizer:
    """
    Face recognition using ONNX Runtime for embedding extraction and matching.
    
    This class extracts 512-dimensional embeddings from aligned face images
    and matches them against a face database using cosine similarity.
    
    Supports both CPU and GPU inference backends for flexible deployment.
    
    Requirements: 11.2, 11.3, 11.4, 11.5
    """
    
    def __init__(self, model_path: str, use_gpu: bool = True):
        """
        Initialize the face recognizer with an ONNX model.
        
        Args:
            model_path: Path to the ONNX model file (.onnx)
            use_gpu: Whether to use GPU acceleration if available (default: True)
        
        Raises:
            ImportError: If ONNX Runtime is not installed
            RuntimeError: If model file is not found or cannot be loaded
        
        Requirements: 11.2, 11.3, 11.4, 11.5
        """
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "ONNX Runtime is not installed. Please install it with: "
                "pip install onnxruntime or onnxruntime-gpu"
            )
        
        # Validate model path
        if not os.path.exists(model_path):
            raise RuntimeError(
                f"Model file not found at {model_path}. "
                "Please ensure the ONNX model is available."
            )
        
        # Configure ONNX Runtime session options
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Set execution providers based on GPU availability
        # Requirements: 11.3, 11.4, 11.5
        if use_gpu:
            # Try GPU first, fall back to CPU if GPU unavailable
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        else:
            providers = ['CPUExecutionProvider']
        
        # Create ONNX Runtime inference session
        try:
            self.session = ort.InferenceSession(
                model_path, 
                sess_options, 
                providers=providers
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model: {e}")
        
        # Get model input/output details
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_name = self.session.get_outputs()[0].name
        
        # Store configuration
        self.model_path = model_path
        self.use_gpu = use_gpu
        
        # Check which provider is actually being used
        self.active_provider = self.session.get_providers()[0]

    
    def extract_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """
        Extract a 512-dimensional embedding vector from an aligned face image.
        
        This method:
        1. Preprocesses the aligned face (normalize to [-1, 1], convert to CHW format)
        2. Runs ONNX inference to extract the embedding
        3. L2-normalizes the embedding vector
        4. Returns the 512-dimensional embedding
        
        Args:
            aligned_face: Aligned face image of shape (112, 112, 3) in BGR format
        
        Returns:
            512-dimensional embedding vector as numpy array of shape (512,)
        
        Raises:
            ValueError: If input image has invalid shape or format
            RuntimeError: If inference fails
        
        Requirements: 5.1
        """
        # Validate input shape
        if aligned_face.shape != (112, 112, 3):
            raise ValueError(
                f"Input face must be 112x112x3, got shape {aligned_face.shape}"
            )
        
        # Preprocess: normalize to [-1, 1] and convert to CHW format
        # 1. Convert to float32
        face_float = aligned_face.astype(np.float32)
        
        # 2. Normalize from [0, 255] to [-1, 1]
        # Formula: (pixel / 127.5) - 1.0
        face_normalized = (face_float / 127.5) - 1.0
        
        # 3. Convert from HWC (Height, Width, Channels) to CHW (Channels, Height, Width)
        face_chw = np.transpose(face_normalized, (2, 0, 1))
        
        # 4. Add batch dimension: (1, 3, 112, 112)
        face_batch = np.expand_dims(face_chw, axis=0)
        
        # Run ONNX inference
        try:
            outputs = self.session.run(
                [self.output_name],
                {self.input_name: face_batch}
            )
            embedding = outputs[0]
        except Exception as e:
            raise RuntimeError(f"ONNX inference failed: {e}")
        
        # Remove batch dimension: (1, 512) -> (512,)
        embedding = embedding.flatten()
        
        # Validate output shape
        if embedding.shape != (512,):
            raise RuntimeError(
                f"Model output has unexpected shape {embedding.shape}, expected (512,)"
            )
        
        # L2-normalize the embedding
        # This ensures the embedding has unit length, which is important for
        # cosine similarity computation
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding

    
    def match_identity(
        self, 
        embedding: np.ndarray, 
        database, 
        threshold: float = 0.6
    ) -> MatchResult:
        """
        Match an embedding against the face database.
        
        This method calls database.search() with the provided threshold and
        returns a MatchResult with identity, confidence, and permission_level.
        
        If no match is found above the threshold, returns "Unknown" identity
        with confidence 0.0 and "guest" permission level.
        
        Args:
            embedding: 512-dimensional embedding vector to match
            database: FaceDatabase instance to search against
            threshold: Minimum similarity score for a match (default: 0.6)
        
        Returns:
            MatchResult with identity, confidence, and permission_level
        
        Raises:
            ValueError: If embedding is invalid or threshold is out of range
        
        Requirements: 5.3, 5.4, 5.5, 5.6
        """
        # Validate embedding
        if not isinstance(embedding, np.ndarray) or embedding.shape != (512,):
            raise ValueError(
                f"Embedding must be a 512-dimensional numpy array, got shape {embedding.shape if isinstance(embedding, np.ndarray) else 'not an array'}"
            )
        
        # Validate threshold
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"Threshold must be between 0.0 and 1.0, got {threshold}"
            )
        
        # Search database for best match
        # The database.search() method returns a dict with keys:
        # 'identity', 'confidence', 'permission_level'
        # or None if no match above threshold
        match_dict = database.search(embedding, threshold)
        
        # If match found, create MatchResult from the dictionary
        if match_dict is not None:
            return MatchResult(
                identity=match_dict['identity'],
                confidence=match_dict['confidence'],
                permission_level=match_dict['permission_level']
            )
        
        # No match found - return "Unknown" with default guest permission
        # Requirements: 5.4 - When no stored embedding exceeds threshold, return "Unknown"
        return MatchResult(
            identity="Unknown",
            confidence=0.0,
            permission_level="guest"
        )
