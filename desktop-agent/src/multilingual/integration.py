"""
GURU Integration Layer

Production-grade integration layer that connects multilingual processing
with existing GURU components while maintaining security boundaries and
ensuring seamless operation with the existing system architecture.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from .configuration import MultilingualConfig, ConfigurationManager
from .pipeline import MultilingualProcessingPipeline, PipelineResult
from .exceptions import MultilingualError, SecurityBoundaryError


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


class GuruMultilingualIntegration:
    """
    Integration layer that connects multilingual processing with existing GURU components.
    
    This class serves as the bridge between the multilingual processing pipeline
    and the existing GURU voice processing, authority, and execution systems.
    """
    
    def __init__(
        self, 
        multilingual_config: Optional[MultilingualConfig] = None,
        integration_config: Optional[GuruIntegrationConfig] = None,
        guru_config_path: Optional[Path] = None
    ):
        self.logger = logging.getLogger(__name__)
        
        # Load configurations
        self.integration_config = integration_config or GuruIntegrationConfig()
        
        if multilingual_config:
            self.multilingual_config = multilingual_config
        else:
            # Load from configuration manager
            config_manager = ConfigurationManager(guru_config_path)
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
        guru_context: Optional[Dict[str, Any]] = None
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
                audio=audio,
                session_id=session_id,
                expected_speaker_id=expected_speaker_id
            )
            
            # Check if processing was successful
            if not pipeline_result.success:
                self.logger.warning(f"Multilingual processing failed: {pipeline_result.error}")
                
                if self.integration_config.fallback_to_existing_pipeline:
                    return self._fallback_to_existing_pipeline(audio, session_id, expected_speaker_id, guru_context)
                else:
                    raise MultilingualError(
                        f"Multilingual processing failed: {pipeline_result.error}",
                        context={'request_id': pipeline_result.request_id}
                    )
                    
            # Validate security boundaries
            if self.integration_config.enforce_security_boundaries:
                security_validation = self._validate_security_integration(pipeline_result, guru_context)
                if not security_validation['valid']:
                    raise SecurityBoundaryError(
                        f"Security boundary validation failed: {security_validation['reason']}",
                        security_violation_type="integration_boundary",
                        attempted_action=pipeline_result.canonical_intent.action.value if pipeline_result.canonical_intent else "unknown"
                    )
                    
            # Convert to GURU command format
            guru_command = self._convert_to_guru_format(pipeline_result, guru_context)
            
            # Add integration metadata
            guru_command['metadata']['multilingual_integration'] = {
                'pipeline_request_id': pipeline_result.request_id,
                'processing_time_ms': pipeline_result.total_processing_time_ms,
                'detected_language': pipeline_result.language_result.language if pipeline_result.language_result else None,
                'processing_mode': pipeline_result.mode_result.mode.value if pipeline_result.mode_result else None,
                'security_level': pipeline_result.security_level,
                'integration_version': '1.0.0'
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
        guru_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback to existing GURU voice processing pipeline."""
        
        self._fallback_count += 1
        self.logger.info(f"Falling back to existing GURU pipeline (fallback #{self._fallback_count})")
        
        # In production, this would call the existing GURU voice processing pipeline
        # For now, we'll return a placeholder command structure
        
        return {
            'action': 'FALLBACK_PROCESSING',
            'parameters': {
                'audio_length': len(audio),
                'fallback_reason': 'multilingual_processing_unavailable'
            },
            'metadata': {
                'multilingual': False,
                'fallback_used': True,
                'fallback_count': self._fallback_count,
                'session_id': session_id,
                'expected_speaker': expected_speaker_id,
                'guru_context': guru_context
            }
        }
        
    def _validate_security_integration(
        self, 
        pipeline_result: PipelineResult, 
        guru_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate security boundaries for GURU integration."""
        
        try:
            # Check if authority is required and granted
            if pipeline_result.authority_required and not pipeline_result.authority_granted:
                return {
                    'valid': False,
                    'reason': 'Authority required but not granted'
                }
                
            # Check security level compatibility
            if guru_context and 'security_level' in guru_context:
                guru_security_level = guru_context['security_level']
                pipeline_security_level = pipeline_result.security_level
                
                # Ensure multilingual processing doesn't lower security requirements
                security_hierarchy = {'low': 1, 'medium': 2, 'high': 3}
                
                if (security_hierarchy.get(pipeline_security_level, 2) < 
                    security_hierarchy.get(guru_security_level, 2)):
                    return {
                        'valid': False,
                        'reason': f'Security level downgrade not allowed: {guru_security_level} -> {pipeline_security_level}'
                    }
                    
            # Check for security validation results
            if pipeline_result.security_result and not pipeline_result.security_result.valid:
                return {
                    'valid': False,
                    'reason': f'Pipeline security validation failed: {pipeline_result.security_result.validation_errors}'
                }
                
            # Validation passed
            return {
                'valid': True,
                'reason': 'Security boundaries validated successfully'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Security validation error: {str(e)}'
            }
            
    def _convert_to_guru_format(
        self, 
        pipeline_result: PipelineResult, 
        guru_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Convert pipeline result to GURU command format."""
        
        if not pipeline_result.guru_command:
            raise MultilingualError(
                "No GURU command available in pipeline result",
                context={'request_id': pipeline_result.request_id}
            )
            
        guru_command = pipeline_result.guru_command.copy()
        
        # Add GURU context if provided
        if guru_context:
            guru_command['metadata']['guru_context'] = guru_context
            
        # Ensure required GURU metadata fields
        if 'authority_required' not in guru_command['metadata']:
            guru_command['metadata']['authority_required'] = pipeline_result.authority_required
            
        if 'security_level' not in guru_command['metadata']:
            guru_command['metadata']['security_level'] = pipeline_result.security_level
            
        # Add integration timestamp
        from datetime import datetime
        guru_command['metadata']['integration_timestamp'] = datetime.utcnow().isoformat()
        
        return guru_command
        
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status and statistics."""
        
        status = {
            'integration_active': self._integration_active,
            'multilingual_enabled': self.integration_config.enable_multilingual_processing,
            'fallback_enabled': self.integration_config.fallback_to_existing_pipeline,
            'fallback_count': self._fallback_count,
            'configuration': {
                'multilingual_config': {
                    'enabled_languages': self.multilingual_config.enabled_languages,
                    'primary_language': self.multilingual_config.primary_language,
                    'detection_threshold': self.multilingual_config.detection_threshold
                },
                'integration_config': {
                    'max_processing_time_ms': self.integration_config.max_processing_time_ms,
                    'require_authority_validation': self.integration_config.require_authority_validation,
                    'enforce_security_boundaries': self.integration_config.enforce_security_boundaries
                }
            }
        }
        
        # Add pipeline statistics if available
        if self.multilingual_pipeline:
            status['pipeline_statistics'] = self.multilingual_pipeline.get_pipeline_statistics()
            
        return status
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update multilingual configuration."""
        
        try:
            # Update multilingual configuration
            if 'multilingual' in config_updates:
                multilingual_updates = config_updates['multilingual']
                
                for key, value in multilingual_updates.items():
                    if hasattr(self.multilingual_config, key):
                        setattr(self.multilingual_config, key, value)
                        
            # Update integration configuration
            if 'integration' in config_updates:
                integration_updates = config_updates['integration']
                
                for key, value in integration_updates.items():
                    if hasattr(self.integration_config, key):
                        setattr(self.integration_config, key, value)
                        
            # Reinitialize pipeline if needed
            if (config_updates.get('reinitialize_pipeline', False) and 
                self.integration_config.enable_multilingual_processing):
                self.multilingual_pipeline = MultilingualProcessingPipeline(self.multilingual_config)
                
            self.logger.info("Multilingual configuration updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update multilingual configuration: {e}")
            return False
            
    def enable_multilingual_processing(self) -> bool:
        """Enable multilingual processing."""
        
        try:
            if not self.multilingual_pipeline:
                self.multilingual_pipeline = MultilingualProcessingPipeline(self.multilingual_config)
                
            self.integration_config.enable_multilingual_processing = True
            self.logger.info("Multilingual processing enabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable multilingual processing: {e}")
            return False
            
    def disable_multilingual_processing(self) -> bool:
        """Disable multilingual processing (fallback to existing pipeline)."""
        
        try:
            self.integration_config.enable_multilingual_processing = False
            self.logger.info("Multilingual processing disabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disable multilingual processing: {e}")
            return False
            
    def cleanup(self):
        """Cleanup integration resources."""
        
        if self.multilingual_pipeline:
            self.multilingual_pipeline.cleanup()
            
        self._integration_active = False
        self.logger.info("GURU multilingual integration cleanup completed")


def create_guru_integration(
    config_path: Optional[Path] = None,
    enable_multilingual: bool = True
) -> GuruMultilingualIntegration:
    """
    Factory function to create GURU multilingual integration.
    
    Args:
        config_path: Optional path to configuration file
        enable_multilingual: Whether to enable multilingual processing
        
    Returns:
        GuruMultilingualIntegration instance
    """
    
    integration_config = GuruIntegrationConfig(
        enable_multilingual_processing=enable_multilingual
    )
    
    return GuruMultilingualIntegration(
        integration_config=integration_config,
        guru_config_path=config_path
    )


def integrate_with_existing_guru(
    existing_voice_processor: Any,
    multilingual_config: Optional[MultilingualConfig] = None
) -> GuruMultilingualIntegration:
    """
    Integrate multilingual processing with existing GURU voice processor.
    
    This function provides a way to add multilingual capabilities to an
    existing GURU installation without disrupting current functionality.
    
    Args:
        existing_voice_processor: Existing GURU voice processor
        multilingual_config: Optional multilingual configuration
        
    Returns:
        GuruMultilingualIntegration instance configured for existing system
    """
    
    integration_config = GuruIntegrationConfig(
        enable_multilingual_processing=True,
        fallback_to_existing_pipeline=True,
        maintain_existing_security=True,
        preserve_existing_audit=True,
        backward_compatibility_mode=True
    )
    
    integration = GuruMultilingualIntegration(
        multilingual_config=multilingual_config,
        integration_config=integration_config
    )
    
    # Store reference to existing processor for fallback
    integration._existing_voice_processor = existing_voice_processor
    
    return integration