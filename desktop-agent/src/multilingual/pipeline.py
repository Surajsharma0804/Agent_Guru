"""
Multilingual Processing Pipeline

Production-grade multilingual processing pipeline that integrates all components
in a secure, deterministic pipeline that maintains GURU's security invariants
while providing comprehensive multilingual capabilities.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from .configuration import MultilingualConfig
from .language_detection import LanguageDetectionEngine, LanguageDetectionResult
from .intent_normalization import IntentNormalizationLayer, CanonicalIntent, ProcessingMode, NormalizationResult
from .voice_processing import MultilingualVoiceProcessor, VoiceProcessingResult
from .mode_classification import MultilingualModeClassifier, ModeClassificationResult
from .audit_logging import MultilingualAuditLogger, MultilingualEvent, MultilingualEventType, LogSeverity
from .exceptions import (
    MultilingualError,
    SecurityBoundaryError,
    PipelineError,
    PerformanceError
)


class PipelineStage(Enum):
    """Pipeline processing stages."""
    
    INITIALIZATION = "initialization"
    AUDIO_INPUT = "audio_input"
    LANGUAGE_DETECTION = "language_detection"
    SPEECH_TO_TEXT = "speech_to_text"
    MODE_CLASSIFICATION = "mode_classification"
    INTENT_NORMALIZATION = "intent_normalization"
    SECURITY_VALIDATION = "security_validation"
    AUTHORITY_CHECK = "authority_check"
    EXECUTION_READY = "execution_ready"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineState(Enum):
    """Pipeline execution states."""
    
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class SecurityValidationResult:
    """Result of security validation in pipeline."""
    
    valid: bool
    security_level: str = "medium"
    authority_required: bool = True
    additional_checks_required: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'valid': self.valid,
            'security_level': self.security_level,
            'authority_required': self.authority_required,
            'additional_checks_required': self.additional_checks_required,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings
        }


@dataclass
class PipelineResult:
    """Comprehensive result of multilingual pipeline processing."""
    
    # Request identification
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    
    # Pipeline execution
    success: bool = False
    state: PipelineState = PipelineState.IDLE
    current_stage: PipelineStage = PipelineStage.INITIALIZATION
    completed_stages: List[PipelineStage] = field(default_factory=list)
    
    # Processing results
    language_result: Optional[LanguageDetectionResult] = None
    voice_result: Optional[VoiceProcessingResult] = None
    mode_result: Optional[ModeClassificationResult] = None
    normalization_result: Optional[NormalizationResult] = None
    security_result: Optional[SecurityValidationResult] = None
    
    # Final output
    canonical_intent: Optional[CanonicalIntent] = None
    guru_command: Optional[Dict[str, Any]] = None
    
    # Performance metrics
    total_processing_time_ms: int = 0
    stage_timings: Dict[str, int] = field(default_factory=dict)
    
    # Error handling
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    abort_reason: Optional[str] = None
    
    # Security context
    authority_required: bool = True
    authority_granted: bool = False
    security_level: str = "medium"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'request_id': self.request_id,
            'session_id': self.session_id,
            'success': self.success,
            'state': self.state.value,
            'current_stage': self.current_stage.value,
            'completed_stages': [stage.value for stage in self.completed_stages],
            'language_result': self.language_result.to_dict() if self.language_result else None,
            'voice_result': self.voice_result.to_dict() if self.voice_result else None,
            'mode_result': self.mode_result.to_dict() if self.mode_result else None,
            'normalization_result': self.normalization_result.to_dict() if self.normalization_result else None,
            'security_result': self.security_result.to_dict() if self.security_result else None,
            'canonical_intent': self.canonical_intent.to_dict() if self.canonical_intent else None,
            'guru_command': self.guru_command,
            'total_processing_time_ms': self.total_processing_time_ms,
            'stage_timings': self.stage_timings,
            'error': self.error,
            'warnings': self.warnings,
            'abort_reason': self.abort_reason,
            'authority_required': self.authority_required,
            'authority_granted': self.authority_granted,
            'security_level': self.security_level
        }


class SecurityValidator:
    """Validates pipeline results against security boundaries."""
    
    def __init__(self, config: MultilingualConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Define security levels and their requirements
        self.security_levels = {
            'low': {
                'max_processing_time_ms': 1000,
                'require_speaker_verification': False,
                'allow_system_commands': False
            },
            'medium': {
                'max_processing_time_ms': 500,
                'require_speaker_verification': True,
                'allow_system_commands': True
            },
            'high': {
                'max_processing_time_ms': 300,
                'require_speaker_verification': True,
                'allow_system_commands': True,
                'require_additional_auth': True
            }
        }
        
    def validate_pipeline_result(self, result: PipelineResult) -> SecurityValidationResult:
        """Validate complete pipeline result against security requirements."""
        
        validation_result = SecurityValidationResult(valid=True)
        
        try:
            # Validate canonical intent if present
            if result.canonical_intent:
                intent_validation = self._validate_canonical_intent(result.canonical_intent)
                if not intent_validation.valid:
                    validation_result.valid = False
                    validation_result.validation_errors.extend(intent_validation.validation_errors)
                    
                validation_result.security_level = result.canonical_intent.security_level
                validation_result.authority_required = result.canonical_intent.requires_authority
                
            # Validate processing performance
            performance_validation = self._validate_performance(result)
            if not performance_validation:
                validation_result.validation_warnings.append("Performance thresholds exceeded")
                
            # Validate speaker verification if required
            if (self.config.require_speaker_verification and 
                result.voice_result and 
                not result.voice_result.speaker_result.verified):
                validation_result.valid = False
                validation_result.validation_errors.append("Speaker verification required but failed")
                
            # Validate language detection confidence
            if (result.language_result and 
                result.language_result.confidence < self.config.detection_threshold):
                validation_result.validation_warnings.append(
                    f"Language detection confidence below threshold: {result.language_result.confidence}"
                )
                
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Security validation failed: {e}")
            return SecurityValidationResult(
                valid=False,
                validation_errors=[f"Security validation error: {str(e)}"]
            )
            
    def _validate_canonical_intent(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate canonical intent against security policies."""
        
        validation_result = SecurityValidationResult(valid=True)
        
        # Check for high-risk actions
        high_risk_actions = {
            'DELETE_FILE', 'SHUTDOWN_SYSTEM', 'RESTART_SYSTEM', 
            'LOCK_SYSTEM', 'MODIFY_SYSTEM_SETTINGS'
        }
        
        if intent.action.value in high_risk_actions:
            validation_result.security_level = "high"
            validation_result.additional_checks_required = True
            validation_result.validation_warnings.append(
                f"High-risk action detected: {intent.action.value}"
            )
            
        # Validate parameters for security issues
        for param_name, param_value in intent.parameters.items():
            if isinstance(param_value, str):
                # Check for path traversal
                if '../' in param_value or '..\\' in param_value:
                    validation_result.valid = False
                    validation_result.validation_errors.append(
                        f"Path traversal detected in parameter '{param_name}'"
                    )
                    
                # Check for command injection
                if any(char in param_value for char in [';', '&', '|', '`', '$']):
                    validation_result.valid = False
                    validation_result.validation_errors.append(
                        f"Command injection risk in parameter '{param_name}'"
                    )
                    
        return validation_result
        
    def _validate_performance(self, result: PipelineResult) -> bool:
        """Validate pipeline performance against thresholds."""
        
        # Check total processing time
        max_time = self.config.max_detection_time_ms * 3  # Allow 3x detection time for full pipeline
        
        if result.total_processing_time_ms > max_time:
            self.logger.warning(
                f"Pipeline processing time exceeded threshold: {result.total_processing_time_ms}ms > {max_time}ms"
            )
            return False
            
        return True


class MultilingualProcessingPipeline:
    """
    Production-grade multilingual processing pipeline that integrates all
    multilingual components in a secure, deterministic processing flow.
    """
    
    def __init__(self, config: MultilingualConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize pipeline components
        self.language_detector = LanguageDetectionEngine(config)
        self.voice_processor = MultilingualVoiceProcessor(config)
        self.mode_classifier = MultilingualModeClassifier(config)
        self.intent_normalizer = IntentNormalizationLayer(config)
        self.audit_logger = MultilingualAuditLogger(config)
        self.security_validator = SecurityValidator(config)
        
        # Pipeline state
        self._current_requests: Dict[str, PipelineResult] = {}
        
        # Pipeline statistics
        self._pipeline_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'aborted_requests': 0,
            'average_processing_time_ms': 0.0,
            'stage_failure_counts': {stage.value: 0 for stage in PipelineStage}
        }
        
    def process_voice_input(
        self,
        audio: bytes,
        session_id: Optional[str] = None,
        expected_speaker_id: Optional[str] = None,
        processing_mode_hint: Optional[ProcessingMode] = None
    ) -> PipelineResult:
        """
        Process voice input through complete multilingual pipeline.
        
        Pipeline Order:
        1. Audio Input Validation
        2. Language Detection
        3. Speech-to-Text Processing
        4. Mode Classification
        5. Intent Normalization (if command mode)
        6. Security Validation
        7. Authority Check Integration
        
        Args:
            audio: Raw audio data
            session_id: Optional session ID for context
            expected_speaker_id: Expected speaker for verification
            processing_mode_hint: Optional mode hint
            
        Returns:
            PipelineResult with complete processing details
        """
        
        start_time = time.time()
        result = PipelineResult(session_id=session_id)
        
        try:
            # Track request
            self._current_requests[result.request_id] = result
            
            # Log pipeline start
            self.audit_logger.log_event(
                MultilingualEvent(
                    event_type=MultilingualEventType.PIPELINE_STARTED,
                    session_id=session_id,
                    request_id=result.request_id,
                    processing_stage="pipeline_start",
                    additional_data={
                        'audio_length': len(audio),
                        'expected_speaker': expected_speaker_id,
                        'mode_hint': processing_mode_hint.value if processing_mode_hint else None
                    }
                )
            )
            
            result.state = PipelineState.PROCESSING
            
            # Stage 1: Audio Input Validation
            if not self._validate_audio_input(audio, result):
                return self._abort_pipeline(result, "Invalid audio input")
                
            # Stage 2: Language Detection
            if not self._process_language_detection(audio, result):
                return self._abort_pipeline(result, "Language detection failed")
                
            # Stage 3: Speech-to-Text Processing
            if not self._process_speech_to_text(audio, result, expected_speaker_id):
                return self._abort_pipeline(result, "Speech-to-text processing failed")
                
            # Stage 4: Mode Classification
            if not self._process_mode_classification(result, processing_mode_hint):
                return self._abort_pipeline(result, "Mode classification failed")
                
            # Stage 5: Intent Normalization (if command mode)
            if result.mode_result.mode == ProcessingMode.COMMAND:
                if not self._process_intent_normalization(result):
                    return self._abort_pipeline(result, "Intent normalization failed")
            else:
                # For dictation mode, create simple text intent
                self._create_dictation_intent(result)
                
            # Stage 6: Security Validation
            if not self._process_security_validation(result):
                return self._abort_pipeline(result, "Security validation failed")
                
            # Stage 7: Generate GURU Command
            if not self._generate_guru_command(result):
                return self._abort_pipeline(result, "GURU command generation failed")
                
            # Pipeline completed successfully
            result.success = True
            result.state = PipelineState.COMPLETED
            result.current_stage = PipelineStage.COMPLETED
            result.total_processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log successful completion
            self.audit_logger.log_event(
                MultilingualEvent(
                    event_type=MultilingualEventType.PIPELINE_COMPLETED,
                    session_id=session_id,
                    request_id=result.request_id,
                    processing_stage="pipeline_completion",
                    success=True,
                    detected_language=result.language_result.language if result.language_result else None,
                    processing_mode=result.mode_result.mode.value if result.mode_result else None,
                    authority_required=result.authority_required,
                    authority_granted=result.authority_granted,
                    additional_data={
                        'total_processing_time_ms': result.total_processing_time_ms,
                        'canonical_action': result.canonical_intent.action.value if result.canonical_intent else None
                    }
                )
            )
            
            # Update statistics
            self._update_pipeline_stats(result)
            
            return result
            
        except Exception as e:
            return self._handle_pipeline_exception(result, e, start_time)
            
        finally:
            # Clean up request tracking
            self._current_requests.pop(result.request_id, None)
            
    def _validate_audio_input(self, audio: bytes, result: PipelineResult) -> bool:
        """Validate audio input."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.AUDIO_INPUT
        
        try:
            # Basic audio validation
            if not audio or len(audio) == 0:
                result.error = "Empty audio input"
                return False
                
            # Check minimum audio length (e.g., 100ms at 16kHz = 3200 bytes)
            min_audio_length = 3200
            if len(audio) < min_audio_length:
                result.warnings.append(f"Audio input very short: {len(audio)} bytes")
                
            # Check maximum audio length (e.g., 30 seconds at 16kHz = ~960KB)
            max_audio_length = 960000
            if len(audio) > max_audio_length:
                result.error = f"Audio input too long: {len(audio)} bytes"
                return False
                
            result.completed_stages.append(PipelineStage.AUDIO_INPUT)
            result.stage_timings['audio_input'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Audio validation failed: {str(e)}"
            return False
            
    def _process_language_detection(self, audio: bytes, result: PipelineResult) -> bool:
        """Process language detection stage."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.LANGUAGE_DETECTION
        
        try:
            # Perform language detection
            language_result = self.language_detector.detect_language(
                audio, 
                result.session_id
            )
            
            result.language_result = language_result
            
            if not language_result.success:
                result.error = f"Language detection failed: {language_result.error}"
                self._pipeline_stats['stage_failure_counts']['language_detection'] += 1
                return False
                
            # Check confidence threshold
            if language_result.confidence < self.config.detection_threshold:
                result.warnings.append(
                    f"Language detection confidence below threshold: {language_result.confidence}"
                )
                
            # Log language detection
            self.audit_logger.log_language_detection(
                detected_language=language_result.language,
                confidence=language_result.confidence,
                processing_time_ms=language_result.processing_time_ms,
                method=language_result.method.value,
                session_id=result.session_id,
                success=True
            )
            
            result.completed_stages.append(PipelineStage.LANGUAGE_DETECTION)
            result.stage_timings['language_detection'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Language detection stage failed: {str(e)}"
            self._pipeline_stats['stage_failure_counts']['language_detection'] += 1
            return False
            
    def _process_speech_to_text(
        self, 
        audio: bytes, 
        result: PipelineResult, 
        expected_speaker_id: Optional[str]
    ) -> bool:
        """Process speech-to-text stage."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.SPEECH_TO_TEXT
        
        try:
            # Perform voice processing (includes STT and speaker verification)
            voice_result = self.voice_processor.process_voice_command(
                audio=audio,
                session_id=result.session_id,
                expected_speaker_id=expected_speaker_id,
                require_speaker_verification=self.config.require_speaker_verification
            )
            
            result.voice_result = voice_result
            
            if not voice_result.success:
                result.error = f"Voice processing failed: {voice_result.error}"
                self._pipeline_stats['stage_failure_counts']['speech_to_text'] += 1
                return False
                
            # Check speaker verification if required
            if (self.config.require_speaker_verification and 
                voice_result.speaker_result and 
                not voice_result.speaker_result.verified):
                result.error = "Speaker verification failed"
                result.authority_granted = False
                return False
            else:
                result.authority_granted = True
                
            # Log voice processing
            self.audit_logger.log_voice_processing(
                processing_time_ms=voice_result.total_processing_time_ms,
                language=result.language_result.language,
                speaker_verified=voice_result.speaker_result.verified if voice_result.speaker_result else False,
                speech_confidence=voice_result.stt_result.confidence if voice_result.stt_result else 0.0,
                session_id=result.session_id,
                success=True
            )
            
            result.completed_stages.append(PipelineStage.SPEECH_TO_TEXT)
            result.stage_timings['speech_to_text'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Speech-to-text stage failed: {str(e)}"
            self._pipeline_stats['stage_failure_counts']['speech_to_text'] += 1
            return False
            
    def _process_mode_classification(
        self, 
        result: PipelineResult, 
        mode_hint: Optional[ProcessingMode]
    ) -> bool:
        """Process mode classification stage."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.MODE_CLASSIFICATION
        
        try:
            # Get transcribed text
            if not result.voice_result or not result.voice_result.stt_result:
                result.error = "No transcribed text available for mode classification"
                return False
                
            transcribed_text = result.voice_result.stt_result.text
            detected_language = result.language_result.language
            
            # Perform mode classification
            mode_result = self.mode_classifier.classify_mode(
                text=transcribed_text,
                language=detected_language,
                session_id=result.session_id
            )
            
            result.mode_result = mode_result
            
            if not mode_result.success:
                result.error = f"Mode classification failed: {mode_result.error}"
                self._pipeline_stats['stage_failure_counts']['mode_classification'] += 1
                return False
                
            # Apply mode hint if provided and confidence is low
            if mode_hint and mode_result.confidence < 0.7:
                mode_result.mode = mode_hint
                mode_result.confidence = 0.8
                mode_result.warnings.append("Applied mode hint due to low confidence")
                
            # Log mode classification
            self.audit_logger.log_mode_classification(
                detected_mode=mode_result.mode.value,
                confidence=mode_result.confidence,
                processing_time_ms=mode_result.processing_time_ms,
                language=detected_language,
                transition_type=mode_result.transition_type.value,
                session_id=result.session_id,
                mode_switched=mode_result.mode_switched,
                success=True
            )
            
            result.completed_stages.append(PipelineStage.MODE_CLASSIFICATION)
            result.stage_timings['mode_classification'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Mode classification stage failed: {str(e)}"
            self._pipeline_stats['stage_failure_counts']['mode_classification'] += 1
            return False
            
    def _process_intent_normalization(self, result: PipelineResult) -> bool:
        """Process intent normalization stage."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.INTENT_NORMALIZATION
        
        try:
            # Get transcribed text and language
            transcribed_text = result.voice_result.stt_result.text
            detected_language = result.language_result.language
            processing_mode = result.mode_result.mode
            
            # Perform intent normalization
            normalization_result = self.intent_normalizer.normalize_intent(
                text=transcribed_text,
                language=detected_language,
                mode=processing_mode
            )
            
            result.normalization_result = normalization_result
            
            if not normalization_result.success:
                result.error = f"Intent normalization failed: {normalization_result.error}"
                self._pipeline_stats['stage_failure_counts']['intent_normalization'] += 1
                return False
                
            result.canonical_intent = normalization_result.canonical_intent
            
            # Log intent normalization
            self.audit_logger.log_intent_normalization(
                original_language=detected_language,
                canonical_action=result.canonical_intent.action.value,
                processing_time_ms=normalization_result.processing_time_ms,
                confidence=result.canonical_intent.confidence,
                pattern_matched=normalization_result.pattern_matched,
                session_id=result.session_id,
                success=True
            )
            
            result.completed_stages.append(PipelineStage.INTENT_NORMALIZATION)
            result.stage_timings['intent_normalization'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Intent normalization stage failed: {str(e)}"
            self._pipeline_stats['stage_failure_counts']['intent_normalization'] += 1
            return False
            
    def _create_dictation_intent(self, result: PipelineResult):
        """Create dictation intent for dictation mode."""
        
        from .intent_normalization import CanonicalIntent, IntentAction
        
        transcribed_text = result.voice_result.stt_result.text
        detected_language = result.language_result.language
        
        result.canonical_intent = CanonicalIntent(
            action=IntentAction.TYPE_TEXT,
            parameters={'text': transcribed_text, 'preserve_exact': True},
            original_text=transcribed_text,
            original_language=detected_language,
            processing_mode=ProcessingMode.DICTATION,
            confidence=1.0,
            normalization_path=f"{detected_language} -> DICTATION",
            requires_authority=True,
            security_level="low"
        )
        
        result.completed_stages.append(PipelineStage.INTENT_NORMALIZATION)
        
    def _process_security_validation(self, result: PipelineResult) -> bool:
        """Process security validation stage."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.SECURITY_VALIDATION
        
        try:
            # Perform security validation
            security_result = self.security_validator.validate_pipeline_result(result)
            result.security_result = security_result
            
            if not security_result.valid:
                result.error = f"Security validation failed: {'; '.join(security_result.validation_errors)}"
                self._pipeline_stats['stage_failure_counts']['security_validation'] += 1
                
                # Log security validation failure
                self.audit_logger.log_security_validation(
                    validation_passed=False,
                    security_level=security_result.security_level,
                    canonical_action=result.canonical_intent.action.value if result.canonical_intent else "unknown",
                    session_id=result.session_id,
                    reason=result.error
                )
                
                return False
                
            # Update result with security context
            result.authority_required = security_result.authority_required
            result.security_level = security_result.security_level
            
            # Add warnings to result
            result.warnings.extend(security_result.validation_warnings)
            
            # Log successful security validation
            self.audit_logger.log_security_validation(
                validation_passed=True,
                security_level=security_result.security_level,
                canonical_action=result.canonical_intent.action.value if result.canonical_intent else "unknown",
                session_id=result.session_id
            )
            
            result.completed_stages.append(PipelineStage.SECURITY_VALIDATION)
            result.stage_timings['security_validation'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"Security validation stage failed: {str(e)}"
            self._pipeline_stats['stage_failure_counts']['security_validation'] += 1
            return False
            
    def _generate_guru_command(self, result: PipelineResult) -> bool:
        """Generate GURU command from canonical intent."""
        
        stage_start = time.time()
        result.current_stage = PipelineStage.EXECUTION_READY
        
        try:
            if not result.canonical_intent:
                result.error = "No canonical intent available for GURU command generation"
                return False
                
            # Convert canonical intent to GURU command format
            result.guru_command = result.canonical_intent.to_guru_command()
            
            # Add pipeline metadata
            result.guru_command['metadata']['pipeline_result'] = {
                'request_id': result.request_id,
                'session_id': result.session_id,
                'total_processing_time_ms': result.total_processing_time_ms,
                'security_level': result.security_level,
                'authority_required': result.authority_required,
                'authority_granted': result.authority_granted
            }
            
            result.completed_stages.append(PipelineStage.EXECUTION_READY)
            result.stage_timings['execution_ready'] = int((time.time() - stage_start) * 1000)
            
            return True
            
        except Exception as e:
            result.error = f"GURU command generation failed: {str(e)}"
            return False
            
    def _abort_pipeline(self, result: PipelineResult, reason: str) -> PipelineResult:
        """Abort pipeline processing with safe cleanup."""
        
        result.state = PipelineState.ABORTED
        result.current_stage = PipelineStage.FAILED
        result.abort_reason = reason
        result.success = False
        
        # Log pipeline abort
        self.audit_logger.log_event(
            MultilingualEvent(
                event_type=MultilingualEventType.PIPELINE_FAILED,
                session_id=result.session_id,
                request_id=result.request_id,
                processing_stage=result.current_stage.value,
                success=False,
                error_message=reason,
                additional_data={
                    'completed_stages': [stage.value for stage in result.completed_stages],
                    'abort_reason': reason
                }
            ),
            LogSeverity.ERROR
        )
        
        self._pipeline_stats['aborted_requests'] += 1
        
        return result
        
    def _handle_pipeline_exception(
        self, 
        result: PipelineResult, 
        exception: Exception, 
        start_time: float
    ) -> PipelineResult:
        """Handle unexpected pipeline exceptions."""
        
        result.state = PipelineState.FAILED
        result.current_stage = PipelineStage.FAILED
        result.error = f"Pipeline exception: {str(exception)}"
        result.success = False
        result.total_processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Log pipeline failure
        self.audit_logger.log_event(
            MultilingualEvent(
                event_type=MultilingualEventType.PIPELINE_FAILED,
                session_id=result.session_id,
                request_id=result.request_id,
                processing_stage=result.current_stage.value,
                success=False,
                error_message=str(exception),
                additional_data={
                    'exception_type': type(exception).__name__,
                    'completed_stages': [stage.value for stage in result.completed_stages]
                }
            ),
            LogSeverity.ERROR
        )
        
        self._pipeline_stats['failed_requests'] += 1
        
        self.logger.error(f"Pipeline processing failed: {exception}", exc_info=True)
        
        return result
        
    def _update_pipeline_stats(self, result: PipelineResult):
        """Update pipeline processing statistics."""
        
        self._pipeline_stats['total_requests'] += 1
        
        if result.success:
            self._pipeline_stats['successful_requests'] += 1
        else:
            self._pipeline_stats['failed_requests'] += 1
            
        # Update average processing time
        current_avg = self._pipeline_stats['average_processing_time_ms']
        total_requests = self._pipeline_stats['total_requests']
        
        new_avg = ((current_avg * (total_requests - 1)) + result.total_processing_time_ms) / total_requests
        self._pipeline_stats['average_processing_time_ms'] = new_avg
        
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        
        total = self._pipeline_stats['total_requests']
        
        return {
            **self._pipeline_stats,
            'success_rate': (
                self._pipeline_stats['successful_requests'] / max(1, total)
            ),
            'failure_rate': (
                self._pipeline_stats['failed_requests'] / max(1, total)
            ),
            'abort_rate': (
                self._pipeline_stats['aborted_requests'] / max(1, total)
            ),
            'component_statistics': {
                'language_detection': self.language_detector.get_detection_statistics(),
                'voice_processing': self.voice_processor.get_processing_statistics(),
                'mode_classification': self.mode_classifier.get_classification_statistics(),
                'intent_normalization': self.intent_normalizer.get_normalization_statistics(),
                'audit_logging': self.audit_logger.get_audit_statistics()
            }
        }
        
    def cleanup(self):
        """Cleanup pipeline resources and clear caches."""
        
        # Cleanup individual components
        self.language_detector.cleanup()
        self.voice_processor.cleanup()
        self.mode_classifier.cleanup()
        self.intent_normalizer.clear_cache()
        
        # Clear current requests
        self._current_requests.clear()
        
        self.logger.info("Multilingual pipeline cleanup completed")