"""
Language-Specific Voice Training and Calibration

Production-grade voice profile calibration system that provides language-specific
speaker verification training, confidence threshold tuning, and multi-language
voice profile management while maintaining security boundaries.

Requirements: 15.5
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .configuration import SupportedLanguages
from .exceptions import ConfigurationError, UnsupportedLanguageError


class TrainingQuality(Enum):
    """Quality assessment for voice training samples."""
    
    EXCELLENT = "excellent"  # High SNR, clear speech, optimal duration
    GOOD = "good"            # Good quality, usable for training
    ACCEPTABLE = "acceptable"  # Acceptable but not ideal
    POOR = "poor"            # Low quality, should be re-recorded
    UNUSABLE = "unusable"    # Cannot be used for training


class CalibrationStatus(Enum):
    """Status of voice calibration for a language."""
    
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_RECALIBRATION = "needs_recalibration"
    FAILED = "failed"


@dataclass
class VoiceSample:
    """A single voice training sample."""
    
    sample_id: str
    language_code: str
    audio_data: bytes
    duration_ms: int
    sample_rate: int
    
    # Quality metrics
    signal_to_noise_ratio: float
    clarity_score: float
    quality: TrainingQuality
    
    # Embedding data
    speaker_embedding: Optional[np.ndarray] = None
    embedding_confidence: Optional[float] = None
    
    # Metadata
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    text_content: Optional[str] = None  # What was spoken (for verification)
    
    # Validation
    is_validated: bool = False
    validation_score: Optional[float] = None
    
    def __post_init__(self):
        """Validate sample after initialization."""
        if self.duration_ms < 1000:
            raise ConfigurationError(
                f"Voice sample too short: {self.duration_ms}ms (minimum 1000ms)",
                config_key="duration_ms"
            )
            
        if self.duration_ms > 30000:
            raise ConfigurationError(
                f"Voice sample too long: {self.duration_ms}ms (maximum 30000ms)",
                config_key="duration_ms"
            )
            
        if not SupportedLanguages.is_supported(self.language_code):
            raise UnsupportedLanguageError(
                f"Language code '{self.language_code}' is not supported",
                requested_language=self.language_code,
                supported_languages=SupportedLanguages.get_language_codes()
            )
            
    def get_audio_hash(self) -> str:
        """Get cryptographic hash of audio data for integrity verification."""
        return hashlib.sha256(self.audio_data).hexdigest()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding audio data for size)."""
        return {
            'sample_id': self.sample_id,
            'language_code': self.language_code,
            'duration_ms': self.duration_ms,
            'sample_rate': self.sample_rate,
            'signal_to_noise_ratio': self.signal_to_noise_ratio,
            'clarity_score': self.clarity_score,
            'quality': self.quality.value,
            'embedding_confidence': self.embedding_confidence,
            'recorded_at': self.recorded_at.isoformat(),
            'text_content': self.text_content,
            'is_validated': self.is_validated,
            'validation_score': self.validation_score,
            'audio_hash': self.get_audio_hash()
        }


@dataclass
class LanguageVoiceProfile:
    """Voice profile for a specific language."""
    
    language_code: str
    user_id: str
    
    # Training samples
    training_samples: List[VoiceSample] = field(default_factory=list)
    
    # Speaker embedding (averaged from samples)
    speaker_template: Optional[np.ndarray] = None
    template_confidence: float = 0.0
    
    # Calibration settings
    calibrated_threshold: float = 0.75  # Default threshold
    optimal_threshold: Optional[float] = None
    
    # Quality metrics
    profile_quality: TrainingQuality = TrainingQuality.POOR
    consistency_score: float = 0.0
    
    # Status
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_STARTED
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    
    # Statistics
    total_verifications: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0
    
    def __post_init__(self):
        """Validate profile after initialization."""
        if not SupportedLanguages.is_supported(self.language_code):
            raise UnsupportedLanguageError(
                f"Language code '{self.language_code}' is not supported",
                requested_language=self.language_code,
                supported_languages=SupportedLanguages.get_language_codes()
            )
            
    def add_training_sample(self, sample: VoiceSample) -> bool:
        """Add a training sample to the profile."""
        if sample.language_code != self.language_code:
            return False
            
        self.training_samples.append(sample)
        self.updated_at = datetime.utcnow()
        
        # Update calibration status
        if self.calibration_status == CalibrationStatus.NOT_STARTED:
            self.calibration_status = CalibrationStatus.IN_PROGRESS
            
        return True
        
    def remove_training_sample(self, sample_id: str) -> bool:
        """Remove a training sample from the profile."""
        original_count = len(self.training_samples)
        self.training_samples = [s for s in self.training_samples if s.sample_id != sample_id]
        
        if len(self.training_samples) < original_count:
            self.updated_at = datetime.utcnow()
            
            # Update status if no samples left
            if not self.training_samples:
                self.calibration_status = CalibrationStatus.NOT_STARTED
                self.speaker_template = None
                
            return True
            
        return False
        
    def get_sample_count(self) -> int:
        """Get number of training samples."""
        return len(self.training_samples)
        
    def get_validated_sample_count(self) -> int:
        """Get number of validated training samples."""
        return sum(1 for s in self.training_samples if s.is_validated)
        
    def get_average_quality(self) -> float:
        """Get average quality score of training samples."""
        if not self.training_samples:
            return 0.0
            
        quality_scores = {
            TrainingQuality.EXCELLENT: 1.0,
            TrainingQuality.GOOD: 0.8,
            TrainingQuality.ACCEPTABLE: 0.6,
            TrainingQuality.POOR: 0.4,
            TrainingQuality.UNUSABLE: 0.0
        }
        
        total_score = sum(quality_scores[s.quality] for s in self.training_samples)
        return total_score / len(self.training_samples)
        
    def is_ready_for_calibration(self) -> bool:
        """Check if profile has enough samples for calibration."""
        # Need at least 3 validated samples for reliable calibration
        return self.get_validated_sample_count() >= 3
        
    def record_verification(self, success: bool):
        """Record a verification attempt."""
        self.total_verifications += 1
        if success:
            self.successful_verifications += 1
        else:
            self.failed_verifications += 1
            
        self.last_used_at = datetime.utcnow()
        
    def get_verification_success_rate(self) -> float:
        """Get verification success rate."""
        if self.total_verifications == 0:
            return 0.0
        return self.successful_verifications / self.total_verifications
        
    def needs_recalibration(self) -> bool:
        """Check if profile needs recalibration."""
        # Recalibrate if success rate drops below 80%
        if self.total_verifications >= 10:
            success_rate = self.get_verification_success_rate()
            if success_rate < 0.8:
                return True
                
        return False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'language_code': self.language_code,
            'user_id': self.user_id,
            'training_samples': [s.to_dict() for s in self.training_samples],
            'template_confidence': self.template_confidence,
            'calibrated_threshold': self.calibrated_threshold,
            'optimal_threshold': self.optimal_threshold,
            'profile_quality': self.profile_quality.value,
            'consistency_score': self.consistency_score,
            'calibration_status': self.calibration_status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'total_verifications': self.total_verifications,
            'successful_verifications': self.successful_verifications,
            'failed_verifications': self.failed_verifications
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LanguageVoiceProfile':
        """Create from dictionary."""
        # Convert enum strings
        if 'profile_quality' in data:
            data['profile_quality'] = TrainingQuality(data['profile_quality'])
        if 'calibration_status' in data:
            data['calibration_status'] = CalibrationStatus(data['calibration_status'])
            
        # Convert datetime strings
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_used_at' in data and data['last_used_at']:
            data['last_used_at'] = datetime.fromisoformat(data['last_used_at'])
            
        # Note: training_samples and speaker_template need special handling
        # They are loaded separately due to size
        data['training_samples'] = []
        data['speaker_template'] = None
        
        return cls(**data)


@dataclass
class MultilingualVoiceProfile:
    """Complete voice profile across multiple languages."""
    
    user_id: str
    profile_name: str = "default"
    
    # Language-specific profiles
    language_profiles: Dict[str, LanguageVoiceProfile] = field(default_factory=dict)
    
    # Global settings
    global_verification_threshold: float = 0.75
    adaptive_threshold_enabled: bool = True
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    
    def get_or_create_language_profile(self, language_code: str) -> LanguageVoiceProfile:
        """Get or create a language-specific voice profile."""
        if language_code not in self.language_profiles:
            self.language_profiles[language_code] = LanguageVoiceProfile(
                language_code=language_code,
                user_id=self.user_id,
                calibrated_threshold=self.global_verification_threshold
            )
            self.updated_at = datetime.utcnow()
            
        return self.language_profiles[language_code]
        
    def get_language_profile(self, language_code: str) -> Optional[LanguageVoiceProfile]:
        """Get language-specific voice profile if it exists."""
        return self.language_profiles.get(language_code)
        
    def has_language_profile(self, language_code: str) -> bool:
        """Check if a language profile exists."""
        return language_code in self.language_profiles
        
    def get_calibrated_languages(self) -> List[str]:
        """Get list of languages with completed calibration."""
        return [
            lang for lang, profile in self.language_profiles.items()
            if profile.calibration_status == CalibrationStatus.COMPLETED
        ]
        
    def get_languages_needing_calibration(self) -> List[str]:
        """Get list of languages that need calibration."""
        return [
            lang for lang, profile in self.language_profiles.items()
            if profile.calibration_status in [
                CalibrationStatus.NOT_STARTED,
                CalibrationStatus.NEEDS_RECALIBRATION
            ]
        ]
        
    def get_overall_calibration_status(self) -> CalibrationStatus:
        """Get overall calibration status across all languages."""
        if not self.language_profiles:
            return CalibrationStatus.NOT_STARTED
            
        statuses = [p.calibration_status for p in self.language_profiles.values()]
        
        if all(s == CalibrationStatus.COMPLETED for s in statuses):
            return CalibrationStatus.COMPLETED
        elif any(s == CalibrationStatus.FAILED for s in statuses):
            return CalibrationStatus.FAILED
        elif any(s == CalibrationStatus.IN_PROGRESS for s in statuses):
            return CalibrationStatus.IN_PROGRESS
        elif any(s == CalibrationStatus.NEEDS_RECALIBRATION for s in statuses):
            return CalibrationStatus.NEEDS_RECALIBRATION
        else:
            return CalibrationStatus.NOT_STARTED
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'profile_name': self.profile_name,
            'language_profiles': {
                lang: profile.to_dict() 
                for lang, profile in self.language_profiles.items()
            },
            'global_verification_threshold': self.global_verification_threshold,
            'adaptive_threshold_enabled': self.adaptive_threshold_enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultilingualVoiceProfile':
        """Create from dictionary."""
        # Convert datetime strings
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        # Convert language profiles
        if 'language_profiles' in data:
            data['language_profiles'] = {
                lang: LanguageVoiceProfile.from_dict(profile_data)
                for lang, profile_data in data['language_profiles'].items()
            }
            
        return cls(**data)


class VoiceCalibrationOrchestrator:
    """
    Orchestrates voice training and calibration across multiple languages.
    
    Provides comprehensive voice profile management with language-specific
    calibration, threshold tuning, and quality assessment while maintaining
    security boundaries and user privacy.
    
    This orchestrator coordinates:
    - Multi-language voice model training
    - Speaker enrollment and verification
    - Calibration threshold optimization
    - Quality assessment and validation
    - Profile persistence and caching
    """
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.profiles_dir = profiles_dir or Path("config/voice_profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self._profiles_cache: Dict[str, MultilingualVoiceProfile] = {}
        self._cache_lock = Lock()
        
        # Minimum requirements for calibration
        self.min_samples_per_language = 3
        self.min_sample_duration_ms = 1000
        self.max_sample_duration_ms = 30000
        
    def load_profile(self, user_id: str, profile_name: str = "default") -> MultilingualVoiceProfile:
        """Load multilingual voice profile from file or create default."""
        cache_key = f"{user_id}:{profile_name}"
        
        with self._cache_lock:
            # Check cache first
            if cache_key in self._profiles_cache:
                return self._profiles_cache[cache_key]
                
            # Load from file
            profile_file = self._get_profile_file(user_id, profile_name)
            
            if profile_file.exists():
                try:
                    with open(profile_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    profile = MultilingualVoiceProfile.from_dict(data)
                    self._profiles_cache[cache_key] = profile
                    
                    self.logger.info(f"Loaded voice profile for user {user_id}, profile {profile_name}")
                    return profile
                    
                except Exception as e:
                    self.logger.error(f"Failed to load voice profile: {e}")
                    # Fall through to create default
                    
            # Create default profile
            profile = MultilingualVoiceProfile(user_id=user_id, profile_name=profile_name)
            self._profiles_cache[cache_key] = profile
            self.save_profile(profile)
            
            return profile
            
    def save_profile(self, profile: MultilingualVoiceProfile) -> bool:
        """Save multilingual voice profile to file."""
        try:
            profile_file = self._get_profile_file(profile.user_id, profile.profile_name)
            profile_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update timestamp
            profile.updated_at = datetime.utcnow()
            
            # Save to file
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
                
            # Update cache
            cache_key = f"{profile.user_id}:{profile.profile_name}"
            with self._cache_lock:
                self._profiles_cache[cache_key] = profile
                
            self.logger.info(f"Saved voice profile for user {profile.user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save voice profile: {e}")
            return False
            
    def add_training_sample(
        self,
        user_id: str,
        language_code: str,
        audio_data: bytes,
        duration_ms: int,
        sample_rate: int,
        profile_name: str = "default"
    ) -> Tuple[bool, Optional[str]]:
        """
        Add a training sample for a specific language.
        
        Returns:
            Tuple of (success, sample_id or error_message)
        """
        try:
            # Load profile
            profile = self.load_profile(user_id, profile_name)
            
            # Get or create language profile
            lang_profile = profile.get_or_create_language_profile(language_code)
            
            # Assess sample quality
            quality_metrics = self._assess_sample_quality(audio_data, duration_ms, sample_rate)
            
            # Create sample
            sample_id = self._generate_sample_id(user_id, language_code)
            sample = VoiceSample(
                sample_id=sample_id,
                language_code=language_code,
                audio_data=audio_data,
                duration_ms=duration_ms,
                sample_rate=sample_rate,
                signal_to_noise_ratio=quality_metrics['snr'],
                clarity_score=quality_metrics['clarity'],
                quality=quality_metrics['quality']
            )
            
            # Add to profile
            if not lang_profile.add_training_sample(sample):
                return False, "Failed to add sample to profile"
                
            # Save audio data separately
            self._save_sample_audio(user_id, profile_name, sample)
            
            # Save profile
            self.save_profile(profile)
            
            self.logger.info(f"Added training sample {sample_id} for {language_code}")
            return True, sample_id
            
        except Exception as e:
            self.logger.error(f"Failed to add training sample: {e}")
            return False, str(e)
            
    def calibrate_language_profile(
        self,
        user_id: str,
        language_code: str,
        profile_name: str = "default"
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Calibrate voice profile for a specific language.
        
        Returns:
            Tuple of (success, calibration_results or error_message)
        """
        try:
            # Load profile
            profile = self.load_profile(user_id, profile_name)
            
            # Get language profile
            lang_profile = profile.get_language_profile(language_code)
            if not lang_profile:
                return False, {"error": "No training samples for this language"}
                
            # Check if ready for calibration
            if not lang_profile.is_ready_for_calibration():
                return False, {
                    "error": "Insufficient training samples",
                    "required": self.min_samples_per_language,
                    "current": lang_profile.get_validated_sample_count()
                }
                
            # Perform calibration
            calibration_results = self._perform_calibration(lang_profile)
            
            # Update profile with calibration results
            lang_profile.speaker_template = calibration_results['speaker_template']
            lang_profile.template_confidence = calibration_results['template_confidence']
            lang_profile.optimal_threshold = calibration_results['optimal_threshold']
            lang_profile.calibrated_threshold = calibration_results['optimal_threshold']
            lang_profile.profile_quality = calibration_results['profile_quality']
            lang_profile.consistency_score = calibration_results['consistency_score']
            lang_profile.calibration_status = CalibrationStatus.COMPLETED
            lang_profile.updated_at = datetime.utcnow()
            
            # Save profile
            self.save_profile(profile)
            
            self.logger.info(f"Calibrated voice profile for {language_code}")
            return True, calibration_results
            
        except Exception as e:
            self.logger.error(f"Failed to calibrate profile: {e}")
            return False, {"error": str(e)}
            
    def get_calibration_status(
        self,
        user_id: str,
        language_code: Optional[str] = None,
        profile_name: str = "default"
    ) -> Dict[str, Any]:
        """Get calibration status for a language or all languages."""
        try:
            profile = self.load_profile(user_id, profile_name)
            
            if language_code:
                # Get status for specific language
                lang_profile = profile.get_language_profile(language_code)
                if not lang_profile:
                    return {
                        'language': language_code,
                        'status': CalibrationStatus.NOT_STARTED.value,
                        'sample_count': 0,
                        'ready_for_calibration': False
                    }
                    
                return {
                    'language': language_code,
                    'status': lang_profile.calibration_status.value,
                    'sample_count': lang_profile.get_sample_count(),
                    'validated_samples': lang_profile.get_validated_sample_count(),
                    'ready_for_calibration': lang_profile.is_ready_for_calibration(),
                    'profile_quality': lang_profile.profile_quality.value,
                    'consistency_score': lang_profile.consistency_score,
                    'verification_success_rate': lang_profile.get_verification_success_rate()
                }
            else:
                # Get status for all languages
                return {
                    'overall_status': profile.get_overall_calibration_status().value,
                    'calibrated_languages': profile.get_calibrated_languages(),
                    'languages_needing_calibration': profile.get_languages_needing_calibration(),
                    'language_details': {
                        lang: {
                            'status': lp.calibration_status.value,
                            'sample_count': lp.get_sample_count(),
                            'ready_for_calibration': lp.is_ready_for_calibration()
                        }
                        for lang, lp in profile.language_profiles.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get calibration status: {e}")
            return {'error': str(e)}
            
    def _get_profile_file(self, user_id: str, profile_name: str) -> Path:
        """Get path to profile file."""
        return self.profiles_dir / user_id / f"{profile_name}.json"
        
    def _generate_sample_id(self, user_id: str, language_code: str) -> str:
        """Generate unique sample ID."""
        timestamp = datetime.utcnow().isoformat()
        data = f"{user_id}:{language_code}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
        
    def _save_sample_audio(self, user_id: str, profile_name: str, sample: VoiceSample) -> bool:
        """Save audio data for a sample separately."""
        try:
            audio_dir = self.profiles_dir / user_id / profile_name / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            audio_file = audio_dir / f"{sample.sample_id}.wav"
            with open(audio_file, 'wb') as f:
                f.write(sample.audio_data)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save sample audio: {e}")
            return False
            
    def _assess_sample_quality(
        self,
        audio_data: bytes,
        duration_ms: int,
        sample_rate: int
    ) -> Dict[str, Any]:
        """Assess quality of a voice sample."""
        # Placeholder implementation - would use actual audio analysis
        # In production, this would analyze SNR, clarity, etc.
        
        # For now, return reasonable defaults
        snr = 20.0  # dB
        clarity = 0.85
        
        # Determine quality based on metrics
        if snr >= 25 and clarity >= 0.9:
            quality = TrainingQuality.EXCELLENT
        elif snr >= 20 and clarity >= 0.8:
            quality = TrainingQuality.GOOD
        elif snr >= 15 and clarity >= 0.7:
            quality = TrainingQuality.ACCEPTABLE
        elif snr >= 10:
            quality = TrainingQuality.POOR
        else:
            quality = TrainingQuality.UNUSABLE
            
        return {
            'snr': snr,
            'clarity': clarity,
            'quality': quality
        }
        
    def _perform_calibration(self, lang_profile: LanguageVoiceProfile) -> Dict[str, Any]:
        """Perform calibration for a language profile."""
        # Placeholder implementation - would use actual speaker verification
        # In production, this would:
        # 1. Extract speaker embeddings from all samples
        # 2. Create averaged speaker template
        # 3. Determine optimal threshold through cross-validation
        # 4. Assess profile quality and consistency
        
        # For now, return reasonable defaults
        speaker_template = np.random.rand(512)  # Placeholder embedding
        template_confidence = 0.92
        optimal_threshold = 0.78
        consistency_score = 0.88
        
        # Determine profile quality
        avg_quality = lang_profile.get_average_quality()
        if avg_quality >= 0.9:
            profile_quality = TrainingQuality.EXCELLENT
        elif avg_quality >= 0.8:
            profile_quality = TrainingQuality.GOOD
        elif avg_quality >= 0.6:
            profile_quality = TrainingQuality.ACCEPTABLE
        else:
            profile_quality = TrainingQuality.POOR
            
        return {
            'speaker_template': speaker_template,
            'template_confidence': template_confidence,
            'optimal_threshold': optimal_threshold,
            'profile_quality': profile_quality,
            'consistency_score': consistency_score,
            'sample_count': lang_profile.get_sample_count(),
            'validated_samples': lang_profile.get_validated_sample_count()
        }
