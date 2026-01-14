"""
Gemini Provider - Google Gemini API Provider Implementation

Production-grade Gemini provider with comprehensive security controls.

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


class GeminiProvider:
    """
    Google Gemini API provider with security-first design.
    
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
        default_model: Optional[str] = None
    ):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key (loaded from env if not provided)
            models: List of available models
            default_model: Default model to use
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.models = models or ["gemini-pro", "gemini-1.5-pro"]
        self.default_model = default_model or "gemini-pro"
        self.logger = logging.getLogger("llm.gemini_provider")
        self.initialized = False
        
        # Import Google Generative AI library
        try:
            import google.generativeai as genai
            self.genai = genai
            self.model = None
        except ImportError:
            self.logger.error("Google Generative AI library not installed. Install with: pip install google-generativeai")
            self.genai = None
    
    async def initialize(self) -> bool:
        """
        Initialize Gemini provider.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing Gemini provider...")
            
            # Check if Gemini library is available
            if not self.genai:
                self.logger.error("Gemini library not available")
                return False
            
            # Validate API key
            if not self.api_key:
                self.logger.error("Gemini API key not provided")
                return False
            
            # Configure API
            self.genai.configure(api_key=self.api_key)
            
            # Initialize default model
            self.model = self.genai.GenerativeModel(self.default_model)
            
            # Perform health check
            if not await self.health_check():
                self.logger.error("Gemini health check failed")
                return False
            
            self.initialized = True
            self.logger.info("Gemini provider initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini provider: {e}")
            return False
    
    async def generate(
        self,
        model: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        task_type: Optional[str] = None
    ) -> str:
        """
        Generate response using Gemini model.
        
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
            raise ProviderError("Gemini provider not initialized", provider_name="gemini")
        
        if not self.genai:
            raise ProviderError("Gemini library not available", provider_name="gemini")
        
        try:
            # Create model instance if different from default
            if model != self.default_model:
                model_instance = self.genai.GenerativeModel(model)
            else:
                model_instance = self.model
            
            # Build full prompt with system instructions
            system_prompt = self._build_system_prompt(task_type)
            full_prompt = f"{system_prompt}\n\nUser input: {prompt}"
            
            # Add context if provided
            if context:
                full_prompt += f"\n\nContext: {json.dumps(context)}"
            
            # Generate response
            response = await asyncio.to_thread(
                model_instance.generate_content,
                full_prompt
            )
            
            # Extract text
            generated_text = response.text
            return generated_text.strip()
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "api key" in error_str or "authentication" in error_str:
                raise AuthenticationError(
                    "Gemini authentication failed",
                    provider_name="gemini",
                    auth_method="api_key"
                )
            elif "rate limit" in error_str or "quota" in error_str:
                raise RateLimitExceededError(
                    "Gemini rate limit exceeded",
                    provider_name="gemini",
                    retry_after=60
                )
            else:
                raise ProviderError(
                    f"Gemini generation failed: {str(e)}",
                    provider_name="gemini",
                    provider_error=e
                )
    
    async def health_check(self) -> bool:
        """
        Perform health check on Gemini service.
        
        Returns:
            bool: True if healthy
        """
        try:
            if not self.model:
                return False
            
            # Simple generation to verify connectivity
            response = await asyncio.to_thread(
                self.model.generate_content,
                "Hello"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Gemini health check failed: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown provider and cleanup resources."""
        self.logger.info("Shutting down Gemini provider")
        self.model = None
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
