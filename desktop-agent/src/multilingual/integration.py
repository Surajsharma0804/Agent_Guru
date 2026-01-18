"""
GURU Integration Layer

Production-grade integration layer that connects multilingual processing
with existing GURU components while maintaining security boundaries and
ensuring seamless operation with the existing system architecture.

This integration layer provides the bridge between the secure multilingual
pipeline and existing GURU components (Authority State Machine, Voice Pipeline,
Input Engine, LLM Adapter) while maintaining all security invariants.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import existing GURU components
from ..authority.authority_state_machine import AuthorityConfiguration, AuthorityStateMachine
from ..input.windows_input_engine import WindowsInputEngine
from ..language_model.adapter import LLMAdapter
from ..voice.voice_pipeline import PipelineConfig, VoiceProcessingPipeline

# Import multilingual components
from .configuration import ConfigurationController, MultilingualConfig
from .exceptions import MultilingualError, SecurityBoundaryError

# Import PipelineResult for type hints
from .pipeline import MultilingualProcessingPipeline, PipelineResult
from .secure_pipeline import create_secure_multilingual_pipeline
from .types import SecurePipelineResult  # Import from types to avoid circular dependency


@dataclass
class GuruIntegrationConfig:
    """Configuration for GURU integration."""

    # Integration settings
    enable_multilingual_processing: bool = True
    fallback_to_existing_pipeline: bool = True
    maintain_existing_security: bool = True
    preserve_existing_audit: bool = True

    # Performance settings
    max_processing_time_ms: int = 500
    enable_performance_monitoring: bool = True

    # Security settings
    require_authority_validation: bool = True
    enforce_security_boundaries: bool = True

    # Compatibility settings
    backward_compatibility_mode: bool = True
    legacy_command_support: bool = True


class SecureGuruMultilingualIntegration:
    """
    Secure integration layer that connects multilingual processing with existing GURU components.

    This class provides the production-grade bridge between the secure multilingual pipeline
    and existing GURU components while maintaining all security invariants and boundaries.

    SECURITY ARCHITECTURE:
    - All processing flows through existing Authority State Machine
    - No security gate bypasses or parallel pipelines
    - Multilingual processing never weakens security boundaries
    - Authority verification is identical across all languages
    """

    def __init__(
        self,
        multilingual_config: Optional[MultilingualConfig] = None,
        integration_config: Optional[GuruIntegrationConfig] = None,
        guru_config_path: Optional[Path] = None,
        authority_machine: Optional[AuthorityStateMachine] = None,
        voice_pipeline: Optional[VoiceProcessingPipeline] = None,
        input_engine: Optional[WindowsInputEngine] = None,
        llm_adapter: Optional[LLMAdapter] = None,
    ):
        """
        Initialize secure GURU multilingual integration.

        Args:
            multilingual_config: Multilingual configuration
            integration_config: Integration configuration
            guru_config_path: Path to GURU configuration
            authority_machine: Existing GURU Authority State Machine
            voice_pipeline: Existing GURU Voice Processing Pipeline
            input_engine: Existing GURU Input Engine
            llm_adapter: Optional LLM Adapter
        """

        self.logger = logging.getLogger(__name__)

        # Load configurations
        self.integration_config = integration_config or GuruIntegrationConfig()

        if multilingual_config:
            self.multilingual_config = multilingual_config
        else:
            # Load from configuration manager
            config_manager = ConfigurationController(guru_config_path)
            self.multilingual_config = config_manager.load_configuration()

        # Initialize or use existing GURU components
        self.authority_machine = authority_machine or self._create_authority_machine()
        self.voice_pipeline = voice_pipeline or self._create_voice_pipeline()
        self.input_engine = input_engine or self._create_input_engine()
        self.llm_adapter = llm_adapter

        # Initialize secure multilingual pipeline
        if self.integration_config.enable_multilingual_processing:
            self.secure_pipeline = create_secure_multilingual_pipeline(
                config=self.multilingual_config,
                authority_machine=self.authority_machine,
                voice_pipeline=self.voice_pipeline,
                input_engine=self.input_engine,
                llm_adapter=self.llm_adapter,
            )
        else:
            self.secure_pipeline = None

        # Integration state
        self._integration_active = False
        self._fallback_count = 0
        self._security_violations = 0

        # Verify security invariants on initialization
        self._verify_security_invariants()

        self.logger.info("Secure GURU multilingual integration initialized")

    def _create_authority_machine(self) -> AuthorityStateMachine:
        """Create default Authority State Machine if not provided."""

        config = AuthorityConfiguration(
            # Production mode - enforce workstation locking for security
            test_mode_disable_workstation_lock=False
        )

        from src.authority.authority_state_machine import create_authority_state_machine

        return create_authority_state_machine(config)

    def _create_voice_pipeline(self) -> VoiceProcessingPipeline:
        """Create default Voice Processing Pipeline if not provided."""

        config = PipelineConfig(enable_speaker_verification=True, enable_security_validation=True)

        return VoiceProcessingPipeline(config)

    def _create_input_engine(self) -> WindowsInputEngine:
        """Create default Input Engine if not provided."""

        return WindowsInputEngine()

    def _verify_security_invariants(self):
        """Verify that all security invariants are maintained."""

        try:
            # Verify authority machine is functional
            if not self.authority_machine or not hasattr(self.authority_machine, "current_state"):
                raise SecurityBoundaryError(
                    "Authority State Machine not properly initialized", security_violation_type="initialization_failure"
                )

            # Verify secure pipeline integration
            if self.secure_pipeline:
                invariants = self.secure_pipeline.verify_security_invariants()
                failed_invariants = [k for k, v in invariants.items() if not v]

                if failed_invariants:
                    raise SecurityBoundaryError(
                        f"Security invariants failed: {failed_invariants}",
                        security_violation_type="invariant_violation",
                    )

            self.logger.info("Security invariants verified successfully")

        except Exception as e:
            self.logger.error(f"Security invariant verification failed: {e}")
            raise

    def process_voice_command(
        self, audio: bytes, session_id: Optional[str] = None, expected_speaker_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process voice command through secure multilingual pipeline.

        This is the main entry point for secure multilingual voice processing
        that integrates with existing GURU components while maintaining all
        security invariants.

        Args:
            audio: Raw audio data
            session_id: Optional session ID for context
            expected_speaker_id: Expected speaker for verification

        Returns:
            Dictionary containing processed command result
        """

        try:
            # Verify security invariants before processing
            self._verify_security_invariants()

            # Check if multilingual processing is enabled
            if not self.integration_config.enable_multilingual_processing or not self.secure_pipeline:
                return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id)

            # Process through secure multilingual pipeline
            pipeline_result = self.secure_pipeline.process_voice_command(
                audio=audio, session_id=session_id, expected_speaker_id=expected_speaker_id
            )

            # Check if processing was successful
            if not pipeline_result.success:
                self.logger.warning(f"Secure multilingual processing failed: {pipeline_result.error}")

                # Check for security violations
                if pipeline_result.security_violations:
                    self._security_violations += 1
                    self.logger.error(f"Security violations detected: {pipeline_result.security_violations}")

                    # Don't fallback on security violations - fail securely
                    raise SecurityBoundaryError(
                        f"Security violations in multilingual processing: {pipeline_result.security_violations}",
                        security_violation_type="processing_violation",
                    )

                if self.integration_config.fallback_to_existing_pipeline:
                    return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id)
                else:
                    raise MultilingualError(
                        f"Secure multilingual processing failed: {pipeline_result.error}",
                        context={"request_id": pipeline_result.request_id},
                    )

            # Convert to response format
            _response = self._convert_pipeline_result_to_response(pipeline_result)

            self._integration_active = True

            return response

        except SecurityBoundaryError:
            # Re-raise security errors without fallback
            raise

        except Exception as e:
            self.logger.error(f"Secure multilingual integration failed: {e}")

            if self.integration_config.fallback_to_existing_pipeline:
                return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id)
            else:
                raise

    def _fallback_to_existing_pipeline(
        self, audio: bytes, session_id: Optional[str], expected_speaker_id: Optional[str]
    ) -> Dict[str, Any]:
        """Fallback to existing GURU voice processing pipeline."""

        self._fallback_count += 1
        self.logger.info(f"Falling back to existing GURU pipeline (fallback #{self._fallback_count})")

        try:
            # Process through existing voice pipeline
            import numpy as np

            # Convert bytes to numpy array (simplified - would need proper audio conversion)
            audio_array = np.frombuffer(audio, dtype=np.int16)
            sample_rate = 16000  # Assume 16kHz

            # Process through existing voice pipeline
            voice_result = self.voice_pipeline.enforce_voice_authority_boundary(
                audio_data=audio_array,
                sample_rate=sample_rate,
                context={"session_id": session_id, "expected_speaker": expected_speaker_id},
            )

            if voice_result.success:
                # Create response in expected format
                return {
                    "success": True,
                    "action": "VOICE_COMMAND_PROCESSED",
                    "text": voice_result.text,
                    "confidence": voice_result.confidence,
                    "speaker_verified": voice_result.speaker_verified,
                    "processing_time_ms": voice_result.processing_time_ms,
                    "metadata": {
                        "multilingual": False,
                        "fallback_used": True,
                        "fallback_count": self._fallback_count,
                        "session_id": session_id,
                        "expected_speaker": expected_speaker_id,
                        "language": "en",  # Default to English for fallback
                        "processing_mode": "command",
                    },
                }
            else:
                return {
                    "success": False,
                    "error": voice_result.error_message or "Voice processing failed",
                    "metadata": {"multilingual": False, "fallback_used": True, "fallback_count": self._fallback_count},
                }

        except Exception as e:
            self.logger.error(f"Fallback processing failed: {e}")
            return {
                "success": False,
                "error": f"Fallback processing failed: {str(e)}",
                "metadata": {"multilingual": False, "fallback_used": True, "fallback_error": True},
            }

    def _convert_pipeline_result_to_response(self, pipeline_result: SecurePipelineResult) -> Dict[str, Any]:
        """Convert secure pipeline result to response format."""

        _response = {
            "success": pipeline_result.success,
            "request_id": pipeline_result.request_id,
            "session_id": pipeline_result.session_id,
            "processing_time_ms": pipeline_result.total_processing_time_ms,
        }

        if pipeline_result.success:
            # Add successful processing results
            if pipeline_result.multilingual_result:
                ml_result = pipeline_result.multilingual_result

                response.update(
                    {
                        "action": ml_result.canonical_intent.action.value if ml_result.canonical_intent else "UNKNOWN",
                        "parameters": ml_result.canonical_intent.parameters if ml_result.canonical_intent else {},
                        "text": (
                            ml_result.voice_result.stt_result.text
                            if ml_result.voice_result and ml_result.voice_result.stt_result
                            else ""
                        ),
                        "language": ml_result.language_result.language if ml_result.language_result else "unknown",
                        "confidence": ml_result.language_result.confidence if ml_result.language_result else 0.0,
                        "processing_mode": ml_result.mode_result.mode.value if ml_result.mode_result else "unknown",
                    }
                )

            if pipeline_result.authority_result:
                response["authority_granted"] = pipeline_result.authority_result.authority_granted
                response["speaker_verified"] = pipeline_result.authority_result.biometric_verified

            if pipeline_result.execution_result:
                response["execution_result"] = pipeline_result.execution_result

            response["metadata"] = {
                "multilingual": True,
                "security_level": (
                    pipeline_result.multilingual_result.security_level
                    if pipeline_result.multilingual_result
                    else "medium"
                ),
                "authority_state": (
                    pipeline_result.authority_result.authority_state.value
                    if pipeline_result.authority_result
                    else "unknown"
                ),
                "processing_stages": (
                    pipeline_result.multilingual_result.completed_stages if pipeline_result.multilingual_result else []
                ),
                "integration_version": "1.0.0",
            }

        else:
            # Add error information
            response.update(
                {
                    "error": pipeline_result.error,
                    "warnings": pipeline_result.warnings,
                    "security_violations": pipeline_result.security_violations,
                }
            )

        return response

    """
    Integration layer that connects multilingual processing with existing GURU components.

    This class serves as the bridge between the multilingual processing pipeline
    and the existing GURU voice processing, authority, and execution systems.
    """

    def __init__(
        self,
        multilingual_config: Optional[MultilingualConfig] = None,
        integration_config: Optional[GuruIntegrationConfig] = None,
        guru_config_path: Optional[Path] = None,
    ):
        self.logger = logging.getLogger(__name__)

        # Load configurations
        self.integration_config = integration_config or GuruIntegrationConfig()

        if multilingual_config:
            self.multilingual_config = multilingual_config
        else:
            # Load from configuration manager
            config_manager = ConfigurationController(guru_config_path)
            self.multilingual_config = config_manager.load_configuration()

        # Initialize multilingual pipeline
        if self.integration_config.enable_multilingual_processing:
            self.multilingual_pipeline = MultilingualProcessingPipeline(self.multilingual_config)
        else:
            self.multilingual_pipeline = None

        # Integration state
        self._integration_active = False
        self._fallback_count = 0

        self.logger.info("GURU multilingual integration initialized")

    def process_voice_input(
        self,
        audio: bytes,
        session_id: Optional[str] = None,
        expected_speaker_id: Optional[str] = None,
        guru_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process voice input through multilingual pipeline with GURU integration.

        This method serves as the main entry point for multilingual voice processing
        that integrates with existing GURU voice processing pipeline.

        Args:
            audio: Raw audio data
            session_id: Optional session ID for context
            expected_speaker_id: Expected speaker for verification
            guru_context: Optional GURU system context

        Returns:
            Dictionary containing processed command in GURU format
        """

        try:
            # Check if multilingual processing is enabled
            if not self.integration_config.enable_multilingual_processing or not self.multilingual_pipeline:
                return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id, guru_context)

            # Process through multilingual pipeline
            pipeline_result = self.multilingual_pipeline.process_voice_input(
                audio=audio, session_id=session_id, expected_speaker_id=expected_speaker_id
            )

            # Check if processing was successful
            if not pipeline_result.success:
                self.logger.warning(f"Multilingual processing failed: {pipeline_result.error}")

                if self.integration_config.fallback_to_existing_pipeline:
                    return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id, guru_context)
                else:
                    raise MultilingualError(
                        f"Multilingual processing failed: {pipeline_result.error}",
                        context={"request_id": pipeline_result.request_id},
                    )

            # Validate security boundaries
            if self.integration_config.enforce_security_boundaries:
                security_validation = self._validate_security_integration(pipeline_result, guru_context)
                if not security_validation["valid"]:
                    raise SecurityBoundaryError(
                        f"Security boundary validation failed: {security_validation['reason']}",
                        security_violation_type="integration_boundary",
                        attempted_action=(
                            pipeline_result.canonical_intent.action.value
                            if pipeline_result.canonical_intent
                            else "unknown"
                        ),
                    )

            # Convert to GURU command format
            guru_command = self._convert_to_guru_format(pipeline_result, guru_context)

            # Add integration metadata
            guru_command["metadata"]["multilingual_integration"] = {
                "pipeline_request_id": pipeline_result.request_id,
                "processing_time_ms": pipeline_result.total_processing_time_ms,
                "detected_language": (
                    pipeline_result.language_result.language if pipeline_result.language_result else None
                ),
                "processing_mode": pipeline_result.mode_result.mode.value if pipeline_result.mode_result else None,
                "security_level": pipeline_result.security_level,
                "integration_version": "1.0.0",
            }

            self._integration_active = True

            return guru_command

        except Exception as e:
            self.logger.error(f"Multilingual integration failed: {e}")

            if self.integration_config.fallback_to_existing_pipeline:
                return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id, guru_context)
            else:
                raise

    def _fallback_to_existing_pipeline(
        self,
        audio: bytes,
        session_id: Optional[str],
        expected_speaker_id: Optional[str],
        guru_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fallback to existing GURU voice processing pipeline."""

        self._fallback_count += 1
        self.logger.info(f"Falling back to existing GURU pipeline (fallback #{self._fallback_count})")

        # In production, this would call the existing GURU voice processing pipeline
        # For now, we'll return a placeholder command structure

        return {
            "action": "FALLBACK_PROCESSING",
            "parameters": {"audio_length": len(audio), "fallback_reason": "multilingual_processing_unavailable"},
            "metadata": {
                "multilingual": False,
                "fallback_used": True,
                "fallback_count": self._fallback_count,
                "session_id": session_id,
                "expected_speaker": expected_speaker_id,
                "guru_context": guru_context,
            },
        }

    def _validate_security_integration(
        self, pipeline_result: PipelineResult, guru_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate security boundaries for GURU integration."""

        try:
            # Check if authority is required and granted
            if pipeline_result.authority_required and not pipeline_result.authority_granted:
                return {"valid": False, "reason": "Authority required but not granted"}

            # Check security level compatibility
            if guru_context and "security_level" in guru_context:
                guru_security_level = guru_context["security_level"]
                pipeline_security_level = pipeline_result.security_level

                # Ensure multilingual processing doesn't lower security requirements
                security_hierarchy = {"low": 1, "medium": 2, "high": 3}

                if security_hierarchy.get(pipeline_security_level, 2) < security_hierarchy.get(guru_security_level, 2):
                    return {
                        "valid": False,
                        "reason": f"Security level downgrade not allowed: {guru_security_level} -> {pipeline_security_level}",
                    }

            # Check for security validation results
            if pipeline_result.security_result and not pipeline_result.security_result.valid:
                return {
                    "valid": False,
                    "reason": f"Pipeline security validation failed: {pipeline_result.security_result.validation_errors}",
                }

            # Validation passed
            return {"valid": True, "reason": "Security boundaries validated successfully"}

        except Exception as e:
            return {"valid": False, "reason": f"Security validation error: {str(e)}"}

    def _convert_to_guru_format(
        self, pipeline_result: PipelineResult, guru_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Convert pipeline result to GURU command format."""

        if not pipeline_result.guru_command:
            raise MultilingualError(
                "No GURU command available in pipeline result", context={"request_id": pipeline_result.request_id}
            )

        guru_command = pipeline_result.guru_command.copy()

        # Add GURU context if provided
        if guru_context:
            guru_command["metadata"]["guru_context"] = guru_context

        # Ensure required GURU metadata fields
        if "authority_required" not in guru_command["metadata"]:
            guru_command["metadata"]["authority_required"] = pipeline_result.authority_required

        if "security_level" not in guru_command["metadata"]:
            guru_command["metadata"]["security_level"] = pipeline_result.security_level

        # Add integration timestamp
        from datetime import datetime

        guru_command["metadata"]["integration_timestamp"] = datetime.utcnow().isoformat()

        return guru_command

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status and statistics."""

        status = {
            "integration_active": self._integration_active,
            "multilingual_enabled": self.integration_config.enable_multilingual_processing,
            "fallback_enabled": self.integration_config.fallback_to_existing_pipeline,
            "fallback_count": self._fallback_count,
            "security_violations": self._security_violations,
            "authority_state": self.authority_machine.current_state.value,
            "configuration": {
                "multilingual_config": {
                    "enabled_languages": self.multilingual_config.enabled_languages,
                    "primary_language": self.multilingual_config.primary_language,
                    "detection_threshold": self.multilingual_config.detection_threshold,
                },
                "integration_config": {
                    "max_processing_time_ms": self.integration_config.max_processing_time_ms,
                    "require_authority_validation": self.integration_config.require_authority_validation,
                    "enforce_security_boundaries": self.integration_config.enforce_security_boundaries,
                },
            },
        }

        # Add secure pipeline statistics if available
        if self.secure_pipeline:
            status["security_statistics"] = self.secure_pipeline.get_security_statistics()

        # Add authority machine statistics
        status["authority_statistics"] = self.authority_machine.get_state_info()

        return status

    def verify_integration_security(self) -> Dict[str, Any]:
        """Verify integration security and return detailed report."""

        security_report = {
            "overall_status": "SECURE",
            "timestamp": datetime.utcnow().isoformat(),
            "checks_performed": [],
            "violations_found": [],
            "recommendations": [],
        }

        try:
            # Check 1: Authority machine integration
            security_report["checks_performed"].append("authority_machine_integration")
            if not self.authority_machine or not hasattr(self.authority_machine, "current_state"):
                security_report["violations_found"].append("Authority machine not properly integrated")
                security_report["overall_status"] = "CRITICAL"

            # Check 2: Secure pipeline invariants
            if self.secure_pipeline:
                security_report["checks_performed"].append("secure_pipeline_invariants")
                invariants = self.secure_pipeline.verify_security_invariants()
                failed_invariants = [k for k, v in invariants.items() if not v]

                if failed_invariants:
                    security_report["violations_found"].extend(
                        [f"Security invariant failed: {inv}" for inv in failed_invariants]
                    )
                    security_report["overall_status"] = "CRITICAL"

            # Check 3: Security violation count
            security_report["checks_performed"].append("security_violation_tracking")
            if self._security_violations > 0:
                security_report["violations_found"].append(f"Security violations detected: {self._security_violations}")
                if self._security_violations > 5:
                    security_report["overall_status"] = "WARNING"

            # Check 4: Configuration security
            security_report["checks_performed"].append("configuration_security")
            if not self.integration_config.enforce_security_boundaries:
                security_report["violations_found"].append("Security boundary enforcement disabled")
                security_report["overall_status"] = "WARNING"

            # Generate recommendations
            if security_report["violations_found"]:
                security_report["recommendations"].append("Review and address all security violations immediately")
                security_report["recommendations"].append("Verify all security configurations are properly set")
                security_report["recommendations"].append(
                    "Consider disabling multilingual processing until issues are resolved"
                )

            return security_report

        except Exception as e:
            security_report["overall_status"] = "ERROR"
            security_report["violations_found"].append(f"Security verification failed: {str(e)}")
            return security_report

    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update multilingual configuration with security validation."""

        try:
            # Validate configuration updates don't weaken security
            if "integration" in config_updates:
                integration_updates = config_updates["integration"]

                # Prevent disabling security enforcement
                if "enforce_security_boundaries" in integration_updates:
                    if not integration_updates["enforce_security_boundaries"]:
                        self.logger.warning("Attempt to disable security boundary enforcement blocked")
                        return False

                # Update integration configuration
                for key, value in integration_updates.items():
                    if hasattr(self.integration_config, key):
                        setattr(self.integration_config, key, value)

            # Update multilingual configuration
            if "multilingual" in config_updates:
                multilingual_updates = config_updates["multilingual"]

                for key, value in multilingual_updates.items():
                    if hasattr(self.multilingual_config, key):
                        setattr(self.multilingual_config, key, value)

            # Reinitialize secure pipeline if needed
            if (
                config_updates.get("reinitialize_pipeline", False)
                and self.integration_config.enable_multilingual_processing
            ):

                self.secure_pipeline = create_secure_multilingual_pipeline(
                    config=self.multilingual_config,
                    authority_machine=self.authority_machine,
                    voice_pipeline=self.voice_pipeline,
                    input_engine=self.input_engine,
                    llm_adapter=self.llm_adapter,
                )

            # Verify security invariants after update
            self._verify_security_invariants()

            self.logger.info("Multilingual configuration updated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update multilingual configuration: {e}")
            return False

    def enable_multilingual_processing(self) -> bool:
        """Enable multilingual processing with security validation."""

        try:
            # Verify security invariants before enabling
            self._verify_security_invariants()

            if not self.secure_pipeline:
                self.secure_pipeline = create_secure_multilingual_pipeline(
                    config=self.multilingual_config,
                    authority_machine=self.authority_machine,
                    voice_pipeline=self.voice_pipeline,
                    input_engine=self.input_engine,
                    llm_adapter=self.llm_adapter,
                )

            self.integration_config.enable_multilingual_processing = True
            self.logger.info("Secure multilingual processing enabled")
            return True

        except Exception as e:
            self.logger.error(f"Failed to enable multilingual processing: {e}")
            return False

    def disable_multilingual_processing(self) -> bool:
        """Disable multilingual processing (fallback to existing pipeline)."""

        try:
            self.integration_config.enable_multilingual_processing = False

            # Cleanup secure pipeline
            if self.secure_pipeline:
                self.secure_pipeline.cleanup()
                self.secure_pipeline = None

            self.logger.info("Multilingual processing disabled")
            return True

        except Exception as e:
            self.logger.error(f"Failed to disable multilingual processing: {e}")
            return False

    def cleanup(self):
        """Cleanup integration resources and clear sensitive data."""

        try:
            if self.secure_pipeline:
                self.secure_pipeline.cleanup()

            self._integration_active = False

            self.logger.info("Secure GURU multilingual integration cleanup completed")

        except Exception as e:
            self.logger.error(f"Integration cleanup failed: {e}")


def create_secure_guru_integration(
    config_path: Optional[Path] = None,
    enable_multilingual: bool = True,
    authority_machine: Optional[AuthorityStateMachine] = None,
    voice_pipeline: Optional[VoiceProcessingPipeline] = None,
    input_engine: Optional[WindowsInputEngine] = None,
    llm_adapter: Optional[LLMAdapter] = None,
) -> SecureGuruMultilingualIntegration:
    """
    Factory function to create secure GURU multilingual integration.

    Args:
        config_path: Optional path to configuration file
        enable_multilingual: Whether to enable multilingual processing
        authority_machine: Existing GURU Authority State Machine
        voice_pipeline: Existing GURU Voice Processing Pipeline
        input_engine: Existing GURU Input Engine
        llm_adapter: Optional LLM Adapter

    Returns:
        SecureGuruMultilingualIntegration instance
    """

    integration_config = GuruIntegrationConfig(
        enable_multilingual_processing=enable_multilingual,
        enforce_security_boundaries=True,
        require_authority_validation=True,
    )

    return SecureGuruMultilingualIntegration(
        integration_config=integration_config,
        guru_config_path=config_path,
        authority_machine=authority_machine,
        voice_pipeline=voice_pipeline,
        input_engine=input_engine,
        llm_adapter=llm_adapter,
    )


def integrate_with_existing_guru(
    existing_authority_machine: AuthorityStateMachine,
    existing_voice_processor: VoiceProcessingPipeline,
    existing_input_engine: WindowsInputEngine,
    multilingual_config: Optional[MultilingualConfig] = None,
    llm_adapter: Optional[LLMAdapter] = None,
) -> SecureGuruMultilingualIntegration:
    """
    Integrate multilingual processing with existing GURU components.

    This function provides a way to add secure multilingual capabilities to an
    existing GURU installation without disrupting current functionality.

    Args:
        existing_authority_machine: Existing GURU Authority State Machine
        existing_voice_processor: Existing GURU voice processor
        existing_input_engine: Existing GURU Input Engine
        multilingual_config: Optional multilingual configuration
        llm_adapter: Optional LLM Adapter

    Returns:
        SecureGuruMultilingualIntegration instance configured for existing system
    """

    integration_config = GuruIntegrationConfig(
        enable_multilingual_processing=True,
        fallback_to_existing_pipeline=True,
        maintain_existing_security=True,
        preserve_existing_audit=True,
        backward_compatibility_mode=True,
        enforce_security_boundaries=True,
        require_authority_validation=True,
    )

    return SecureGuruMultilingualIntegration(
        multilingual_config=multilingual_config,
        integration_config=integration_config,
        authority_machine=existing_authority_machine,
        voice_pipeline=existing_voice_processor,
        input_engine=existing_input_engine,
        llm_adapter=llm_adapter,
    )
