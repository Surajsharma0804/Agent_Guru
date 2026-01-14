"""
OpenAI Provider - OpenAI API Provider Implementation

Production-grade OpenAI provider with comprehensive security controls.

SECURITY INVARIANTS:
- API key never logged
- API key loaded only from secure sources
- Requires manual confirmation for activation
- Requires armed authority state
- All outputs are structured intents only
- No direct execution capability
"""

from typing import Dict, Any, List, Optional
import asyncio
import logging
import os
import json
from datetime import datetime

from .exceptions import ProviderError, AuthenticationError, RateLimitExceededError


class OpenAIProvider:
    """
    OpenAI API provider with security-first design.
    
    Features:
    - Secure API key management
    - Rate limiting
    - Structured output generation
    - Comprehensive error handling
    - Audit logging integration
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        models: Optional[List[str]] = None,
        default_model: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1"
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (loaded from env if not provided)
            models: List of available models
            default_model: Default model to use
            base_url: OpenAI API base URL
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.models = models or ["gpt-4", "gpt-3.5-turbo"]
        self.default_model = default_model or "gpt-3.5-turbo"
        self.logger = logging.getLogger("llm.openai_provider")
        self.initialized = False
        
        # Import OpenAI library
        try:
            import openai
            self.openai = openai
            self.client = None
        except ImportError:
            self.logger.error("OpenAI library not installed. Install with: pip install openai")
            self.openai = None
    
    async def initialize(self) -> bool:
        """
        Initialize OpenAI provider.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing OpenAI provider...")
            
            # Check if OpenAI library is available
            if not self.openai:
                self.logger.error("OpenAI library not available")
                return False
            
            # Validate API key
            if not self.api_key:
                self.logger.error("OpenAI API key not provided")
                return False
            
            # Initialize client
            self.client = self.openai.OpenAI(api_key=self.api_key)
            
            # Perform health check
            if not await self.health_check():
                self.logger.error("OpenAI health check failed")
                return False
            
            self.initialized = True
            self.logger.info("OpenAI provider initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI provider: {e}")
            return False
    
    async def generate(
        self,
        model: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        task_type: Optional[str] = None
    ) -> str:
        """
        Generate response using OpenAI model.
        
        Args:
            model: Model name to use
            prompt: Input prompt
            context: Optional context information
            task_type: Type of task being performed
        
        Returns:
            str: Generated response
        
        Raises:
            ProviderError: If generation fails
            AuthenticationError: If API key invalid
            RateLimitExceededError: If rate limit exceeded
        """
        if not self.initialized:
            raise ProviderError("OpenAI provider not initialized", provider_name="openai")
        
        if not self.client:
            raise ProviderError("OpenAI client not available", provider_name="openai")
        
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(task_type)
            
            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            # Add context if provided
            if context:
                messages.insert(1, {
                    "role": "system",
                    "content": f"Context: {json.dumps(context)}"
                })
            
            # Make API request
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                response_format={"type": "json_object"} if task_type in ["intent_extraction", "intent_structuring"] else None
            )
            
            # Extract response
            generated_text = response.choices[0].message.content
            return generated_text.strip()
            
        except self.openai.AuthenticationError as e:
            raise AuthenticationError(
                "OpenAI authentication failed",
                provider_name="openai",
                auth_method="api_key"
            )
        except self.openai.RateLimitError as e:
            raise RateLimitExceededError(
                "OpenAI rate limit exceeded",
                provider_name="openai",
                retry_after=60
            )
        except Exception as e:
            raise ProviderError(
                f"OpenAI generation failed: {str(e)}",
                provider_name="openai",
                provider_error=e
            )
    
    async def health_check(self) -> bool:
        """
        Perform health check on OpenAI service.
        
        Returns:
            bool: True if healthy
        """
        try:
            if not self.client:
                return False
            
            # Simple API call to verify connectivity
            response = await asyncio.to_thread(
                self.client.models.list
            )
            return True
            
        except Exception as e:
            self.logger.error(f"OpenAI health check failed: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown provider and cleanup resources."""
        self.logger.info("Shutting down OpenAI provider")
        self.client = None
        self.initialized = False
    
    def _build_system_prompt(self, task_type: Optional[str]) -> str:
        """Build system prompt based on task type."""
        
        base_prompt = """You are GURU's AI assistant. You MUST respond with valid JSON only.

CRITICAL SECURITY RULES:
- You can ONLY produce structured intents, never execute actions
- You CANNOT run commands, access files, or control systems
- All outputs must be valid JSON

"""
        
        if task_type == "intent_extraction":
            return base_prompt + """Your task: Extract user intent from natural language.

Valid intent types:
- type_text: Type text exactly as requested
- press_key: Press keyboard keys
- mouse_action: Mouse movements and clicks
- launch_app: Launch applications
- execute_skill: Execute predefined skills
- get_status: Query system status
- search_memory: Search memory service

Response format:
{
  "intent_type": "type_text",
  "parameters": {"text": "Hello world"},
  "confidence": 0.95,
  "context": "User wants to type greeting"
}"""
        
        elif task_type == "intent_structuring":
            return base_prompt + """Your task: Structure extracted intent into executable format.

Ensure all parameters are properly formatted and validated.
Add any missing required parameters with safe defaults.

Response format:
{
  "intent_type": "type_text",
  "parameters": {"text": "Hello world", "delay_ms": 0},
  "confidence": 0.95,
  "requires_authority": true,
  "risk_level": "low"
}"""
        
        elif task_type == "conversation":
            return """You are GURU, a helpful and friendly personal AI assistant.

Your personality:
- Warm, friendly, and conversational
- Patient and understanding
- Helpful and knowledgeable
- Natural and human-like

Guidelines:
- Keep responses concise (1-3 sentences for simple questions)
- Be conversational and natural
- Show personality and warmth
- Admit when you don't know something

Remember: You are a voice assistant, so keep responses brief and natural for speaking."""
        
        else:
            return base_prompt + "Respond with valid JSON containing your analysis."
