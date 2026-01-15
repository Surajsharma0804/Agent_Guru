"""
Ollama Provider - Local LLM Provider Implementation

Production-grade Ollama provider for local model inference.
Supports multiple models with automatic model management.

SECURITY INVARIANTS:
- Local-only operation (no network calls except to localhost)
- Complete privacy (no data leaves the machine)
- No direct execution capability
- All outputs are structured intents only
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import requests

from .exceptions import ModelNotFoundError, ProviderError


class OllamaProvider:
    """
    Ollama provider for local LLM inference.
    
    Features:
    - Multiple model support
    - Automatic model detection
    - Health monitoring
    - Structured output generation
    - Zero network dependency (except localhost)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        models: Optional[List[str]] = None,
        default_model: Optional[str] = None
    ):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama API base URL
            models: List of available models
            default_model: Default model to use
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.models = models or []
        self.default_model = default_model
        self.available_models: List[str] = []
        self.logger = logging.getLogger("llm.ollama_provider")
        self.initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize Ollama provider and detect available models.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing Ollama provider...")
            
            # Check if Ollama is running
            if not await self._check_ollama_available():
                self.logger.error("Ollama is not running or not accessible")
                return False
            
            # Detect available models
            self.available_models = await self._detect_models()
            
            if not self.available_models:
                self.logger.warning("No models found in Ollama")
                return False
            
            # Set default model if not specified
            if not self.default_model and self.available_models:
                self.default_model = self.available_models[0]
            
            self.initialized = True
            self.logger.info(
                f"Ollama provider initialized successfully with {len(self.available_models)} models"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Ollama provider: {e}")
            return False
    
    async def generate(
        self,
        model: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        task_type: Optional[str] = None
    ) -> str:
        """
        Generate response using Ollama model.
        
        Args:
            model: Model name to use
            prompt: Input prompt
            context: Optional context information
            task_type: Type of task being performed
        
        Returns:
            str: Generated response
        
        Raises:
            ProviderError: If generation fails
            ModelNotFoundError: If model not available
        """
        if not self.initialized:
            raise ProviderError("Ollama provider not initialized", provider_name="ollama")
        
        # Validate model availability
        if model not in self.available_models:
            raise ModelNotFoundError(
                f"Model {model} not found in Ollama",
                provider_name="ollama",
                model_name=model,
                available_models=self.available_models
            )
        
        try:
            # Build system prompt based on task type
            system_prompt = self._build_system_prompt(task_type)
            
            # Prepare request
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                }
            }
            
            # Add context if provided
            if context:
                payload["context"] = json.dumps(context)
            
            # Make request to Ollama
            response = await asyncio.to_thread(
                requests.post,
                f"{self.api_url}/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                raise ProviderError(
                    f"Ollama API error: {response.status_code}",
                    provider_name="ollama"
                )
            
            result = response.json()
            generated_text = result.get("response", "")
            
            return generated_text.strip()
            
        except requests.exceptions.Timeout:
            raise ProviderError("Ollama request timeout", provider_name="ollama")
        except requests.exceptions.ConnectionError:
            raise ProviderError("Cannot connect to Ollama", provider_name="ollama")
        except Exception as e:
            raise ProviderError(
                f"Ollama generation failed: {str(e)}",
                provider_name="ollama",
                provider_error=e
            )
    
    async def health_check(self) -> bool:
        """
        Perform health check on Ollama service.
        
        Returns:
            bool: True if healthy
        """
        return await self._check_ollama_available()
    
    async def shutdown(self):
        """Shutdown provider and cleanup resources."""
        self.logger.info("Shutting down Ollama provider")
        self.initialized = False
    
    async def _check_ollama_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            response = await asyncio.to_thread(
                requests.get,
                f"{self.api_url}/tags",
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    async def _detect_models(self) -> List[str]:
        """Detect available models in Ollama."""
        try:
            response = await asyncio.to_thread(
                requests.get,
                f"{self.api_url}/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [model["name"] for model in models]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to detect models: {e}")
            return []
    
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
