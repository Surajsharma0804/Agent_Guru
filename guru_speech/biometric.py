"""
Voice Biometric Authentication Module

Provides speaker identification and verification using voice embeddings.
"""

import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import pickle
from pathlib import Path

from .exceptions import GuruSpeechError


class BiometricError(GuruSpeechError):
    """Errors related to voice biometric authentication."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "Biometric", original_error)


@dataclass
class VoiceProfile:
    """Voice profile for a user."""
    
    user_id: str
    """Unique user identifier"""
    
    embeddings: List[np.ndarray]
    """List of voice embeddings"""
    
    created_at: datetime
    """When profile was created"""
    
    updated_at: datetime
    """Last update time"""
    
    enrollment_count: int = 0
    """Number of enrollment samples"""


@dataclass
class AuthenticationResult:
    """Result from voice authentication."""
    
    authenticated: bool
    """Whether authentication succeeded"""
    
    user_id: Optional[str]
    """Identified user ID (if authenticated)"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    similarity_score: float
    """Similarity score with matched profile"""


class VoiceBiometricAuthenticator:
    """
    Voice biometric authentication system.
    
    Supports speaker identification and verification using voice embeddings.
    Uses resemblyzer or speechbrain for embedding extraction.
    """
    
    def __init__(
        self,
        threshold: float = 0.75,
        embedding_size: int = 256,
        model_type: str = "auto"
    ):
        """
        Initialize biometric authenticator.
        
        Args:
            threshold: Authentication threshold (0.0 to 1.0)
            embedding_size: Size of voice embeddings
            model_type: Model type ("resemblyzer", "speechbrain", or "auto")
        """
        self.threshold = threshold
        self.embedding_size = embedding_size
        self.model_type = model_type
        
        self.profiles: Dict[str, VoiceProfile] = {}
        self.encoder = None
        self.encoder_type = None
        
        # Try to initialize encoder
        self._initialize_encoder()
    
    def _initialize_encoder(self) -> None:
        """Initialize voice encoder."""
        # Try resemblyzer first (lightweight)
        if self.model_type in ["auto", "resemblyzer"]:
            try:
                from resemblyzer import VoiceEncoder
                self.encoder = VoiceEncoder()
                self.encoder_type = "resemblyzer"
                print("✅ Resemblyzer voice encoder initialized")
                return
            except ImportError:
                if self.model_type == "resemblyzer":
                    raise BiometricError("Resemblyzer not installed")
        
        # Try speechbrain
        if self.model_type in ["auto", "speechbrain"]:
            try:
                from speechbrain.pretrained import EncoderClassifier
                self.encoder = EncoderClassifier.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb"
                )
                self.encoder_type = "speechbrain"
                print("✅ SpeechBrain voice encoder initialized")
                return
            except ImportError:
                if self.model_type == "speechbrain":
                    raise BiometricError("SpeechBrain not installed")
        
        # Fallback to simple MFCC-based embeddings
        print("⚠️  Using fallback MFCC-based embeddings")
        self.encoder_type = "mfcc"
    
    def extract_embedding(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Extract voice embedding from audio.
        
        Args:
            audio: Audio samples (float32, normalized)
            sample_rate: Sample rate in Hz
            
        Returns:
            Voice embedding vector
        """
        if self.encoder_type == "resemblyzer":
            return self._extract_with_resemblyzer(audio, sample_rate)
        elif self.encoder_type == "speechbrain":
            return self._extract_with_speechbrain(audio, sample_rate)
        else:
            return self._extract_with_mfcc(audio, sample_rate)
    
    def _extract_with_resemblyzer(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract embedding using Resemblyzer."""
        try:
            # Resemblyzer expects 16kHz audio
            if sample_rate != 16000:
                audio = self._resample(audio, sample_rate, 16000)
            
            embedding = self.encoder.embed_utterance(audio)
            return embedding
        except Exception as e:
            raise BiometricError(f"Resemblyzer embedding extraction failed: {e}", e)
    
    def _extract_with_speechbrain(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract embedding using SpeechBrain."""
        try:
            import torch
            
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio).unsqueeze(0)
            
            # Extract embedding
            with torch.no_grad():
                embedding = self.encoder.encode_batch(audio_tensor)
            
            return embedding.squeeze().numpy()
        except Exception as e:
            raise BiometricError(f"SpeechBrain embedding extraction failed: {e}", e)
    
    def _extract_with_mfcc(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Extract simple MFCC-based embedding (fallback).
        
        This is a basic implementation for when proper models aren't available.
        """
        try:
            import librosa
            
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio,
                sr=sample_rate,
                n_mfcc=40,
                n_fft=2048,
                hop_length=512
            )
            
            # Compute statistics over time
            mfcc_mean = np.mean(mfccs, axis=1)
            mfcc_std = np.std(mfccs, axis=1)
            mfcc_delta = np.mean(librosa.feature.delta(mfccs), axis=1)
            
            # Concatenate features
            embedding = np.concatenate([mfcc_mean, mfcc_std, mfcc_delta])
            
            # Normalize
            embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
            
            return embedding
        except ImportError:
            # Ultra-simple fallback without librosa
            # Just use spectral features
            fft = np.fft.rfft(audio)
            magnitude = np.abs(fft)
            
            # Divide into bands and compute energy
            n_bands = self.embedding_size
            band_size = len(magnitude) // n_bands
            
            embedding = np.array([
                np.mean(magnitude[i*band_size:(i+1)*band_size])
                for i in range(n_bands)
            ])
            
            # Normalize
            embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
            
            return embedding
    
    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple resampling."""
        if orig_sr == target_sr:
            return audio
        
        ratio = target_sr / orig_sr
        new_length = int(len(audio) * ratio)
        
        indices = np.arange(new_length) / ratio
        indices_floor = np.floor(indices).astype(int)
        indices_ceil = np.minimum(indices_floor + 1, len(audio) - 1)
        fraction = indices - indices_floor
        
        resampled = (
            audio[indices_floor] * (1 - fraction) +
            audio[indices_ceil] * fraction
        )
        
        return resampled.astype(np.float32)
    
    def enroll(
        self,
        user_id: str,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> None:
        """
        Enroll a user with voice sample.
        
        Args:
            user_id: Unique user identifier
            audio: Audio sample for enrollment
            sample_rate: Sample rate in Hz
        """
        # Extract embedding
        embedding = self.extract_embedding(audio, sample_rate)
        
        # Create or update profile
        if user_id not in self.profiles:
            self.profiles[user_id] = VoiceProfile(
                user_id=user_id,
                embeddings=[embedding],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                enrollment_count=1
            )
        else:
            profile = self.profiles[user_id]
            profile.embeddings.append(embedding)
            profile.updated_at = datetime.now()
            profile.enrollment_count += 1
    
    def authenticate(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        user_id: Optional[str] = None
    ) -> AuthenticationResult:
        """
        Authenticate a speaker.
        
        Args:
            audio: Audio sample to authenticate
            sample_rate: Sample rate in Hz
            user_id: Optional user ID for verification (if None, does identification)
            
        Returns:
            AuthenticationResult with authentication status
        """
        if not self.profiles:
            return AuthenticationResult(
                authenticated=False,
                user_id=None,
                confidence=0.0,
                similarity_score=0.0
            )
        
        # Extract embedding
        embedding = self.extract_embedding(audio, sample_rate)
        
        if user_id is not None:
            # Verification: check against specific user
            return self._verify(embedding, user_id)
        else:
            # Identification: find best match
            return self._identify(embedding)
    
    def _verify(self, embedding: np.ndarray, user_id: str) -> AuthenticationResult:
        """Verify against a specific user."""
        if user_id not in self.profiles:
            return AuthenticationResult(
                authenticated=False,
                user_id=None,
                confidence=0.0,
                similarity_score=0.0
            )
        
        profile = self.profiles[user_id]
        
        # Compute similarity with all enrolled embeddings
        similarities = [
            self._cosine_similarity(embedding, enrolled)
            for enrolled in profile.embeddings
        ]
        
        # Use average similarity
        avg_similarity = np.mean(similarities)
        
        # Authenticate if above threshold
        authenticated = avg_similarity >= self.threshold
        
        return AuthenticationResult(
            authenticated=authenticated,
            user_id=user_id if authenticated else None,
            confidence=avg_similarity,
            similarity_score=avg_similarity
        )
    
    def _identify(self, embedding: np.ndarray) -> AuthenticationResult:
        """Identify the speaker."""
        best_user_id = None
        best_similarity = 0.0
        
        # Compare with all profiles
        for user_id, profile in self.profiles.items():
            # Compute average similarity with this profile
            similarities = [
                self._cosine_similarity(embedding, enrolled)
                for enrolled in profile.embeddings
            ]
            avg_similarity = np.mean(similarities)
            
            if avg_similarity > best_similarity:
                best_similarity = avg_similarity
                best_user_id = user_id
        
        # Authenticate if best match is above threshold
        authenticated = best_similarity >= self.threshold
        
        return AuthenticationResult(
            authenticated=authenticated,
            user_id=best_user_id if authenticated else None,
            confidence=best_similarity,
            similarity_score=best_similarity
        )
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def remove_user(self, user_id: str) -> bool:
        """
        Remove a user profile.
        
        Args:
            user_id: User ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if user_id in self.profiles:
            del self.profiles[user_id]
            return True
        return False
    
    def list_users(self) -> List[str]:
        """Get list of enrolled user IDs."""
        return list(self.profiles.keys())
    
    def get_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """Get voice profile for a user."""
        return self.profiles.get(user_id)
    
    def save_profiles(self, path: str) -> None:
        """
        Save all profiles to file.
        
        Args:
            path: Path to save profiles
        """
        with open(path, 'wb') as f:
            pickle.dump(self.profiles, f)
    
    def load_profiles(self, path: str) -> None:
        """
        Load profiles from file.
        
        Args:
            path: Path to load profiles from
        """
        if not Path(path).exists():
            raise BiometricError(f"Profile file not found: {path}")
        
        with open(path, 'rb') as f:
            self.profiles = pickle.load(f)
