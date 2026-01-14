"""
LLM System Integration Layer

Integrates the model router with the existing GURU system components:
- Authority State Machine
- Audit Logger
- Voice Pipeline
- Intent Processing
- Execution Engine

This layer ensures proper security boundaries and audit logging.
"""

from typing import Dict, Any, Optional
import asyncio
import logging
from pathlib import Path

from .model_router import (
    ModelRouter,
    RouterConfiguration,
    TaskType,
    ProviderType,
    get_model_router
)
from .intent import StructuredIntent, IntentValidator
from .exceptions import (
    LLMException,
    IntentValidationError,
    IsolationBreachError,
    TaskRoutingError
)


class LLMSystemIntegration:
    """
    Production-grade integration layer for LLM system.
    
    Responsibilities:
    - Initialize model router with system configuration
    - Connect to audit logger
    - Validate authority state before LLM calls
    - Process voice input through LLM pipeline
    - Validate and sanitize LLM outputs
    - Handle failures with fail-closed behavior
    
    SECURITY GUARANTEE: All LLM outputs pass through validation
    before reaching execution engine.
    """
    
    def __init__(
        self,
        config_file: Optional[Path] = None,
        audit_logger: Optional[Any] = None,
        authority_machine: Optional[Any] = None
    ):
        """
        Initialize LLM system integration.
        
        Args:
            config_file: Path to LLM configuration file
            audit_logger: System audit logger instance
            authority_machine: Authority state machine instance
        """
        self.logger = logging.getLogger("llm.integration")
        self.audit_logger = audit_logger
        self.authority_machine = authority_machine
        
        # Initialize model router
        self.router = get_model_router(
            config_file=config_file,
            audit_logger=audit_logger
        )
        
        # Intent validator
        self.intent_validator = IntentValidator()
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.security_violations = 0
        
        self.initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize LLM system integration.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing LLM System Integration...")
            
            # Initialize model router
            if not await self.router.initialize():
                self.logger.error("Failed to initialize model router")
                return False
            
            # Audit log initialization
            if self.audit_logger:
                self.audit_logger.log_system_event(
                    "llm_system_initialized",
                    {
                        'router_mode': self.router.config.mode,
                        'available_providers': [p.value for p in self.router.providers.keys()],
                        'configured_tasks': len(self.router.config.tasks)
                    }
                )
            
            self.initialized = True
            self.logger.info("LLM System Integration initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM System Integration: {e}")
            return False
    
    async def process_voice_command(
        self,
        transcribed_text: str,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice command through LLM pipeline.
        
        Pipeline:
        1. Check authority state
        2. Extract intent using LLM
        3. Structure intent using LLM
        4. Validate intent
        5. Return structured intent for execution
        
        Args:
            transcribed_text: Transcribed voice command
            language: Detected language
            context: Optional context information
        
        Returns:
            Dict containing structured intent and metadata
        """
        if not self.initialized:
            return self._error_response("LLM system not initialized")
        
        self.total_requests += 1
        
        try:
            # Check authority state
            if self.authority_machine and not self.authority_machine.is_armed:
                return self._error_response(
                    "Authority not granted",
                    requires_authority=True
                )
            
            # Build context
            full_context = context or {}
            full_context['language'] = language
            full_context['source'] = 'voice'
            
            # Step 1: Extract intent
            self.logger.debug("Extracting intent from voice command")
            intent_extraction_result = await self.router.route_task(
                task_type=TaskType.INTENT_EXTRACTION,
                prompt=transcribed_text,
                context=full_context
            )
            
            if not intent_extraction_result['success']:
                return self._error_response(
                    f"Intent extraction failed: {intent_extraction_result.get('error')}",
                    phase="intent_extraction"
                )
            
            extracted_intent = intent_extraction_result['result']
            
            # Step 2: Structure intent
            self.logger.debug("Structuring extracted intent")
            intent_structuring_result = await self.router.route_task(
                task_type=TaskType.INTENT_STRUCTURING,
                prompt=extracted_intent,
                context=full_context
            )
            
            if not intent_structuring_result['success']:
                return self._error_response(
                    f"Intent structuring failed: {intent_structuring_result.get('error')}",
                    phase="intent_structuring"
                )
            
            structured_intent_json = intent_structuring_result['result']
            
            # Step 3: Validate intent
            self.logger.debug("Validating structured intent")
            try:
                structured_intent = self.intent_validator.validate_raw_response(
                    structured_intent_json
                )
            except IntentValidationError as e:
                self.security_violations += 1
                if self.audit_logger:
                    self.audit_logger.log_security_event(
                        "intent_validation_failed",
                        {
                            'error': str(e),
                            'validation_errors': e.validation_errors
                        }
                    )
                return self._error_response(
                    f"Intent validation failed: {str(e)}",
                    phase="validation",
                    security_violation=True
                )
            except IsolationBreachError as e:
                self.security_violations += 1
                if self.audit_logger:
                    self.audit_logger.log_emergency_event(
                        "isolation_breach_attempt",
                        {
                            'breach_type': e.breach_type,
                            'attempted_action': e.attempted_action,
                            'message': str(e)
                        }
                    )
                return self._error_response(
                    "SECURITY VIOLATION: Isolation breach detected",
                    phase="validation",
                    security_violation=True,
                    critical=True
                )
            
            # Step 4: Sanitize parameters
            structured_intent.parameters = self.intent_validator.sanitize_parameters(
                structured_intent.parameters
            )
            
            # Success
            self.successful_requests += 1
            
            # Audit log
            if self.audit_logger:
                self.audit_logger.log_system_event(
                    "voice_command_processed",
                    {
                        'intent_type': structured_intent.intent_type.value,
                        'confidence': structured_intent.confidence,
                        'risk_level': structured_intent.risk_level,
                        'requires_authority': structured_intent.requires_authority
                    }
                )
            
            return {
                'success': True,
                'intent': structured_intent.to_dict(),
                'metadata': {
                    'extraction_metadata': intent_extraction_result.get('metadata'),
                    'structuring_metadata': intent_structuring_result.get('metadata')
                }
            }
            
        except Exception as e:
            self.failed_requests += 1
            self.logger.error(f"Voice command processing failed: {e}")
            
            if self.audit_logger:
                self.audit_logger.log_system_event(
                    "voice_command_processing_failed",
                    {
                        'error': str(e),
                        'error_type': type(e).__name__
                    }
                )
            
            return self._error_response(
                f"Processing failed: {str(e)}",
                phase="processing"
            )
    
    async def generate_conversation_response(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate conversational response (non-executing).
        
        This is for natural conversation that does NOT result in
        system actions. No authority required.
        
        Args:
            user_input: User's conversational input
            context: Optional context information
        
        Returns:
            Dict containing response and metadata
        """
        if not self.initialized:
            return self._error_response("LLM system not initialized")
        
        try:
            # Route to conversation task
            result = await self.router.route_task(
                task_type=TaskType.CONVERSATION,
                prompt=user_input,
                context=context
            )
            
            if not result['success']:
                return self._error_response(
                    f"Conversation generation failed: {result.get('error')}"
                )
            
            return {
                'success': True,
                'response': result['result'],
                'metadata': result.get('metadata')
            }
            
        except Exception as e:
            self.logger.error(f"Conversation generation failed: {e}")
            return self._error_response(f"Conversation failed: {str(e)}")
    
    async def switch_provider_for_task(
        self,
        task_type: TaskType,
        new_provider: ProviderType,
        new_model: str
    ) -> bool:
        """
        Switch provider for a specific task.
        
        Args:
            task_type: Task to reconfigure
            new_provider: New provider to use
            new_model: New model to use
        
        Returns:
            bool: True if switch successful
        """
        try:
            # Check authority for API providers
            if new_provider in [ProviderType.OPENAI, ProviderType.GEMINI]:
                if self.authority_machine and not self.authority_machine.is_armed:
                    self.logger.warning(
                        "Cannot switch to API provider without armed authority"
                    )
                    return False
            
            # Perform switch
            success = await self.router.switch_provider(
                task_type=task_type,
                new_provider=new_provider,
                new_model=new_model,
                require_confirmation=True
            )
            
            if success and self.audit_logger:
                self.audit_logger.log_system_event(
                    "provider_switched_via_integration",
                    {
                        'task_type': task_type.value,
                        'new_provider': new_provider.value,
                        'new_model': new_model
                    }
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Provider switch failed: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        router_status = self.router.get_router_status()
        
        return {
            'initialized': self.initialized,
            'router': router_status,
            'integration_statistics': {
                'total_requests': self.total_requests,
                'successful_requests': self.successful_requests,
                'failed_requests': self.failed_requests,
                'security_violations': self.security_violations,
                'success_rate': self.successful_requests / max(self.total_requests, 1)
            },
            'authority_state': self.authority_machine.get_state_info() if self.authority_machine else None
        }
    
    def _error_response(
        self,
        error_message: str,
        phase: Optional[str] = None,
        requires_authority: bool = False,
        security_violation: bool = False,
        critical: bool = False
    ) -> Dict[str, Any]:
        """Create standardized error response."""
        self.failed_requests += 1
        
        return {
            'success': False,
            'error': error_message,
            'phase': phase,
            'requires_authority': requires_authority,
            'security_violation': security_violation,
            'critical': critical
        }


# Global integration instance
_llm_integration: Optional[LLMSystemIntegration] = None


def get_llm_integration(
    config_file: Optional[Path] = None,
    audit_logger: Optional[Any] = None,
    authority_machine: Optional[Any] = None
) -> LLMSystemIntegration:
    """Get global LLM system integration instance."""
    global _llm_integration
    if _llm_integration is None:
        _llm_integration = LLMSystemIntegration(
            config_file=config_file,
            audit_logger=audit_logger,
            authority_machine=authority_machine
        )
    return _llm_integration


async def initialize_llm_system(
    config_file: Optional[Path] = None,
    audit_logger: Optional[Any] = None,
    authority_machine: Optional[Any] = None
) -> bool:
    """
    Initialize LLM system with full integration.
    
    This is the primary entry point for system initialization.
    
    Args:
        config_file: Path to LLM configuration file
        audit_logger: System audit logger instance
        authority_machine: Authority state machine instance
    
    Returns:
        bool: True if initialization successful
    """
    integration = get_llm_integration(
        config_file=config_file,
        audit_logger=audit_logger,
        authority_machine=authority_machine
    )
    
    return await integration.initialize()
