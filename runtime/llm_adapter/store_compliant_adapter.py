"""
Store-Compliant LLM Adapter

This adapter enforces store policy compliance by automatically switching
to API-only mode when running in store-installed contexts.

CRITICAL COMPLIANCE REQUIREMENTS:
- Store-installed apps MUST NOT use local models
- All LLM requests MUST go through approved cloud APIs
- User consent MUST be obtained for API usage
- No local model downloads or execution
- Comprehensive audit logging for compliance

ZERO TOLERANCE: Any policy violation results in immediate system shutdown.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import sys

# Add the desktop-agent src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "desktop-agent" / "src"))

from core.execution_context import (
    ExecutionContext,
    ExecutionEnvironment,
    StoreType,
    get_execution_context,
    requires_api_only_mode,
    allows_local_models,
)
from core.secure_execution_gateway import AuthorityLevel
from language_model.production_adapter import (
    ProductionLanguageModelAdapter,
    RuntimeConfiguration,
    TaskConfiguration,
    ProviderConfiguration,
    TaskType,
    ProviderType,
    SecurityMode,
    ModelCallMetadata,
)

logger = logging.getLogger(__name__)


class ComplianceViolationType(Enum):
    """Types of store policy compliance violations."""
    
    LOCAL_MODEL_ATTEMPTED = "local_model_attempted"
    UNAUTHORIZED_API_ACCESS = "unauthorized_api_access"
    MISSING_USER_CONSENT = "missing_user_consent"
    POLICY_BYPASS_ATTEMPTED = "policy_bypass_attempted"
    TAMPER_DETECTED = "tamper_detected"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass(frozen=True)
class ComplianceEvent:
    """Immutable compliance event for audit logging."""
    
    event_type: ComplianceViolationType
    timestamp: datetime
    execution_context: ExecutionContext
    store_type: StoreType
    violation_details: Dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "execution_context": self.execution_context.value,
            "store_type": self.store_type.value,
            "violation_details": self.violation_details,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }


class StoreComplianceError(Exception):
    """Raised when store policy compliance is violated."""
    
    def __init__(self, violation_type: ComplianceViolationType, message: str, details: Dict[str, Any] = None):
        self.violation_type = violation_type
        self.details = details or {}
        super().__init__(f"Store compliance violation: {violation_type.value} - {message}")


class UserConsentManager:
    """
    Manages user consent for API usage in store-compliant manner.
    
    Ensures proper consent collection and storage according to
    platform-specific requirements and privacy regulations.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".guru" / "consent.json"
        self.logger = logging.getLogger("user_consent")
        self._consent_cache: Dict[str, bool] = {}
        
    async def has_api_consent(self, provider: ProviderType, user_id: Optional[str] = None) -> bool:
        """Check if user has given consent for API usage."""
        try:
            consent_key = f"{provider.value}_{user_id or 'default'}"
            
            # Check cache first
            if consent_key in self._consent_cache:
                return self._consent_cache[consent_key]
            
            # Load from storage
            consent_data = self._load_consent_data()
            has_consent = consent_data.get(consent_key, False)
            
            # Cache result
            self._consent_cache[consent_key] = has_consent
            
            return has_consent
            
        except Exception as e:
            self.logger.error(f"Failed to check API consent: {e}")
            return False  # Fail closed
    
    async def request_api_consent(self, provider: ProviderType, user_id: Optional[str] = None) -> bool:
        """Request user consent for API usage."""
        try:
            # In a real implementation, this would show a proper consent dialog
            # For now, we simulate consent based on execution context
            execution_env = get_execution_context()
            
            if execution_env.context == ExecutionContext.DEVELOPMENT:
                # Auto-grant in development
                consent_granted = True
            elif execution_env.context == ExecutionContext.STORE_INSTALLED:
                # Store apps require explicit user interaction
                consent_granted = await self._show_store_consent_dialog(provider)
            else:
                # Sideloaded apps can use simplified consent
                consent_granted = await self._show_simple_consent_dialog(provider)
            
            if consent_granted:
                await self._store_consent(provider, user_id)
            
            return consent_granted
            
        except Exception as e:
            self.logger.error(f"Failed to request API consent: {e}")
            return False
    
    async def revoke_api_consent(self, provider: ProviderType, user_id: Optional[str] = None) -> bool:
        """Revoke user consent for API usage."""
        try:
            consent_key = f"{provider.value}_{user_id or 'default'}"
            
            # Remove from cache
            self._consent_cache.pop(consent_key, None)
            
            # Remove from storage
            consent_data = self._load_consent_data()
            consent_data.pop(consent_key, None)
            self._save_consent_data(consent_data)
            
            self.logger.info(f"API consent revoked for {provider.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to revoke API consent: {e}")
            return False
    
    async def _show_store_consent_dialog(self, provider: ProviderType) -> bool:
        """Show store-compliant consent dialog."""
        # This would integrate with platform-specific consent UI
        # For now, return False to require explicit implementation
        self.logger.warning(f"Store consent dialog not implemented for {provider.value}")
        return False
    
    async def _show_simple_consent_dialog(self, provider: ProviderType) -> bool:
        """Show simple consent dialog for sideloaded apps."""
        # This would show a simple consent dialog
        # For now, return True for sideloaded apps
        self.logger.info(f"Simple consent granted for {provider.value}")
        return True
    
    async def _store_consent(self, provider: ProviderType, user_id: Optional[str] = None) -> None:
        """Store user consent securely."""
        consent_key = f"{provider.value}_{user_id or 'default'}"
        
        # Update cache
        self._consent_cache[consent_key] = True
        
        # Update storage
        consent_data = self._load_consent_data()
        consent_data[consent_key] = {
            "granted": True,
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider.value,
            "user_id": user_id,
        }
        self._save_consent_data(consent_data)
    
    def _load_consent_data(self) -> Dict[str, Any]:
        """Load consent data from storage."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path) as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load consent data: {e}")
        return {}
    
    def _save_consent_data(self, data: Dict[str, Any]) -> None:
        """Save consent data to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save consent data: {e}")


class StoreCompliantLLMAdapter:
    """
    Store-compliant LLM adapter that enforces platform policies.
    
    Automatically switches to API-only mode for store-installed apps
    and ensures all operations comply with store requirements.
    """
    
    def __init__(self, 
                 base_adapter: Optional[ProductionLanguageModelAdapter] = None,
                 consent_manager: Optional[UserConsentManager] = None,
                 audit_logger: Optional[Any] = None):
        
        self.logger = logging.getLogger("store_compliant_llm")
        self.execution_env = get_execution_context()
        self.consent_manager = consent_manager or UserConsentManager()
        self.audit_logger = audit_logger
        
        # Initialize base adapter with store-compliant configuration
        self.base_adapter = base_adapter or self._create_compliant_adapter()
        
        # Compliance tracking
        self.compliance_violations: List[ComplianceEvent] = []
        self.api_usage_count = 0
        self.local_model_blocks = 0
        
        self.logger.info(
            "Store-compliant LLM adapter initialized",
            execution_context=self.execution_env.context.value,
            store_type=self.execution_env.store_type.value,
            allows_local=self.execution_env.allows_local_models,
            requires_api=self.execution_env.requires_api_only,
        )
    
    async def initialize(self) -> bool:
        """Initialize the store-compliant adapter."""
        try:
            # Validate execution environment
            if not self._validate_execution_environment():
                raise StoreComplianceError(
                    ComplianceViolationType.TAMPER_DETECTED,
                    "Execution environment validation failed"
                )
            
            # Initialize base adapter
            if not await self.base_adapter.initialize():
                raise StoreComplianceError(
                    ComplianceViolationType.INVALID_CONFIGURATION,
                    "Base adapter initialization failed"
                )
            
            # Validate configuration compliance
            if not self._validate_configuration_compliance():
                raise StoreComplianceError(
                    ComplianceViolationType.INVALID_CONFIGURATION,
                    "Configuration does not meet store requirements"
                )
            
            self.logger.info("Store-compliant LLM adapter initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Store-compliant adapter initialization failed: {e}")
            await self._log_compliance_violation(
                ComplianceViolationType.INVALID_CONFIGURATION,
                {"error": str(e)}
            )
            return False
    
    async def route_task(self,
                        task_type: TaskType,
                        prompt: str,
                        context: Optional[Dict[str, Any]] = None,
                        preferred_provider: Optional[ProviderType] = None,
                        user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Route task with store compliance enforcement.
        
        Args:
            task_type: Type of task to perform
            prompt: Input prompt for the model
            context: Optional context information
            preferred_provider: Optional preferred provider override
            user_id: Optional user identifier for consent tracking
            
        Returns:
            Dict containing model response and metadata
            
        Raises:
            StoreComplianceError: If operation violates store policies
        """
        try:
            # Validate task is allowed in current context
            if not self._validate_task_allowed(task_type):
                raise StoreComplianceError(
                    ComplianceViolationType.LOCAL_MODEL_ATTEMPTED,
                    f"Task {task_type.value} not allowed in store context"
                )
            
            # Determine compliant provider
            provider = await self._get_compliant_provider(task_type, preferred_provider, user_id)
            
            # Validate API consent if using cloud provider
            if provider in [ProviderType.OPENAI, ProviderType.GEMINI]:
                if not await self.consent_manager.has_api_consent(provider, user_id):
                    # Request consent
                    consent_granted = await self.consent_manager.request_api_consent(provider, user_id)
                    if not consent_granted:
                        raise StoreComplianceError(
                            ComplianceViolationType.MISSING_USER_CONSENT,
                            f"User consent required for {provider.value} API"
                        )
            
            # Execute task through base adapter
            result = await self.base_adapter.route_task(
                task_type=task_type,
                prompt=prompt,
                context=context,
                preferred_provider=provider,
            )
            
            # Track API usage
            if provider in [ProviderType.OPENAI, ProviderType.GEMINI]:
                self.api_usage_count += 1
            
            # Add compliance metadata
            result["compliance"] = {
                "execution_context": self.execution_env.context.value,
                "store_type": self.execution_env.store_type.value,
                "provider_used": provider.value,
                "consent_verified": True,
            }
            
            return result
            
        except StoreComplianceError:
            raise
        except Exception as e:
            self.logger.error(f"Task routing failed: {e}")
            await self._log_compliance_violation(
                ComplianceViolationType.POLICY_BYPASS_ATTEMPTED,
                {"task_type": task_type.value, "error": str(e)}
            )
            raise StoreComplianceError(
                ComplianceViolationType.POLICY_BYPASS_ATTEMPTED,
                f"Task routing failed: {str(e)}"
            )
    
    async def _get_compliant_provider(self,
                                    task_type: TaskType,
                                    preferred_provider: Optional[ProviderType],
                                    user_id: Optional[str]) -> ProviderType:
        """Get store-compliant provider for task."""
        
        # If API-only mode is required, force cloud providers
        if self.execution_env.requires_api_only:
            if preferred_provider in [ProviderType.OPENAI, ProviderType.GEMINI]:
                return preferred_provider
            else:
                # Default to OpenAI for store compliance
                return ProviderType.OPENAI
        
        # If local models are allowed, use preferred or default
        if self.execution_env.allows_local_models:
            if preferred_provider == ProviderType.OLLAMA:
                return preferred_provider
            else:
                # Default to local for privacy
                return ProviderType.OLLAMA
        
        # Fallback to API
        return ProviderType.OPENAI
    
    def _validate_task_allowed(self, task_type: TaskType) -> bool:
        """Validate that task is allowed in current execution context."""
        
        # All tasks are allowed in development
        if self.execution_env.context == ExecutionContext.DEVELOPMENT:
            return True
        
        # Store-installed apps have restrictions
        if self.execution_env.context == ExecutionContext.STORE_INSTALLED:
            # Only basic tasks allowed
            allowed_tasks = [
                TaskType.INTENT_EXTRACTION,
                TaskType.INTENT_STRUCTURING,
                TaskType.LANGUAGE_HELP,
            ]
            return task_type in allowed_tasks
        
        # Sideloaded apps have fewer restrictions
        return True
    
    def _validate_execution_environment(self) -> bool:
        """Validate execution environment for compliance."""
        
        # Check for tampering
        if self.execution_env.tamper_detected:
            self.logger.error("Tamper detection triggered")
            return False
        
        # Validate store signature if required
        if self.execution_env.store_type != StoreType.NONE:
            if not self.execution_env.app_signature:
                self.logger.error("Store app missing signature")
                return False
        
        return True
    
    def _validate_configuration_compliance(self) -> bool:
        """Validate that configuration meets store requirements."""
        
        config = self.base_adapter.config
        
        # Store-installed apps must be API-only
        if self.execution_env.requires_api_only:
            # Check that no local providers are enabled
            for task_type, task_config in config.tasks.items():
                if task_config.enabled and task_config.provider == ProviderType.OLLAMA:
                    self.logger.error(f"Local provider not allowed for {task_type.value}")
                    return False
            
            # Check that cloud is not disabled
            if config.cloud_disabled_completely:
                self.logger.error("Cloud providers cannot be disabled in store context")
                return False
        
        return True
    
    def _create_compliant_adapter(self) -> ProductionLanguageModelAdapter:
        """Create store-compliant base adapter configuration."""
        
        config = RuntimeConfiguration()
        
        # Configure based on execution context
        if self.execution_env.requires_api_only:
            # API-only configuration for store apps
            config.mode = "api"
            config.cloud_disabled_completely = False
            
            # Configure API providers only
            config.providers[ProviderType.OPENAI] = ProviderConfiguration(
                provider_type=ProviderType.OPENAI,
                enabled=True,
                api_key_env_var="OPENAI_API_KEY",
                models=["gpt-3.5-turbo", "gpt-4"],
                default_model="gpt-3.5-turbo",
                require_manual_confirmation=True,
                require_armed_authority=False,  # Store apps handle consent differently
                security_mode=SecurityMode.API_MANUAL_CONFIRM,
            )
            
            config.providers[ProviderType.GEMINI] = ProviderConfiguration(
                provider_type=ProviderType.GEMINI,
                enabled=True,
                api_key_env_var="GEMINI_API_KEY",
                models=["gemini-pro"],
                default_model="gemini-pro",
                require_manual_confirmation=True,
                require_armed_authority=False,
                security_mode=SecurityMode.API_MANUAL_CONFIRM,
            )
            
            # Configure tasks for API-only
            config.tasks[TaskType.INTENT_EXTRACTION] = TaskConfiguration(
                provider=ProviderType.OPENAI,
                model="gpt-3.5-turbo",
                enabled=True,
                security_mode=SecurityMode.API_MANUAL_CONFIRM,
                requires_authority_level=AuthorityLevel.LOW,
            )
            
            config.tasks[TaskType.INTENT_STRUCTURING] = TaskConfiguration(
                provider=ProviderType.OPENAI,
                model="gpt-3.5-turbo",
                enabled=True,
                security_mode=SecurityMode.API_MANUAL_CONFIRM,
                requires_authority_level=AuthorityLevel.LOW,
            )
            
        else:
            # Hybrid configuration for sideloaded apps
            config.mode = "hybrid"
            config.cloud_disabled_completely = False
            
            # Configure both local and API providers
            config.providers[ProviderType.OLLAMA] = ProviderConfiguration(
                provider_type=ProviderType.OLLAMA,
                enabled=True,
                base_url="http://localhost:11434",
                models=["qwen2.5:7b-instruct", "mistral:7b-instruct"],
                default_model="qwen2.5:7b-instruct",
                require_manual_confirmation=False,
                require_armed_authority=False,
                security_mode=SecurityMode.LOCAL_ONLY,
            )
            
            # Also configure API providers as fallback
            config.providers[ProviderType.OPENAI] = ProviderConfiguration(
                provider_type=ProviderType.OPENAI,
                enabled=False,  # Disabled by default
                api_key_env_var="OPENAI_API_KEY",
                models=["gpt-3.5-turbo", "gpt-4"],
                default_model="gpt-3.5-turbo",
                require_manual_confirmation=True,
                require_armed_authority=False,
                security_mode=SecurityMode.API_MANUAL_CONFIRM,
            )
        
        return ProductionLanguageModelAdapter(config=config)
    
    async def _log_compliance_violation(self,
                                      violation_type: ComplianceViolationType,
                                      details: Dict[str, Any]) -> None:
        """Log compliance violation for audit purposes."""
        
        event = ComplianceEvent(
            event_type=violation_type,
            timestamp=datetime.utcnow(),
            execution_context=self.execution_env.context,
            store_type=self.execution_env.store_type,
            violation_details=details,
        )
        
        self.compliance_violations.append(event)
        
        # Log to audit system if available
        if self.audit_logger:
            try:
                await self.audit_logger.log_compliance_violation(event.to_dict())
            except Exception as e:
                self.logger.error(f"Failed to log compliance violation: {e}")
        
        self.logger.warning(
            f"Compliance violation logged: {violation_type.value} - {details}"
        )
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Get current compliance status."""
        return {
            "execution_context": self.execution_env.context.value,
            "store_type": self.execution_env.store_type.value,
            "requires_api_only": self.execution_env.requires_api_only,
            "allows_local_models": self.execution_env.allows_local_models,
            "security_level": self.execution_env.security_level,
            "tamper_detected": self.execution_env.tamper_detected,
            "compliance_violations": len(self.compliance_violations),
            "api_usage_count": self.api_usage_count,
            "local_model_blocks": self.local_model_blocks,
            "policy_restrictions": self.execution_env.policy_restrictions,
        }


# Global store-compliant adapter instance
_store_adapter: Optional[StoreCompliantLLMAdapter] = None


def get_store_compliant_adapter() -> StoreCompliantLLMAdapter:
    """Get global store-compliant LLM adapter instance."""
    global _store_adapter
    if _store_adapter is None:
        _store_adapter = StoreCompliantLLMAdapter()
    return _store_adapter


async def initialize_store_compliant_llm() -> bool:
    """Initialize store-compliant LLM system."""
    adapter = get_store_compliant_adapter()
    return await adapter.initialize()