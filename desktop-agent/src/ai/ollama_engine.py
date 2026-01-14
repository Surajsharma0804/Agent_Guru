"""
Ollama AI Engine

Production-grade local AI engine using Ollama for natural conversation.
Provides real-time, context-aware responses without external API dependencies.
"""

import json
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Import console utilities for cross-platform Unicode support
try:
    from utils.console import safe_print
except ImportError:
    def safe_print(text, **kwargs):
        try:
            print(text, **kwargs)
        except UnicodeEncodeError:
            text = str(text).replace('✓', '[OK]').replace('✗', '[X]').replace('⚠', '[!]')
            print(text, **kwargs)


@dataclass
class Message:
    """Conversation message"""
    role: str  # 'system', 'user', 'assistant'
    content: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class OllamaEngine:
    """
    Production-grade Ollama AI engine.
    
    Features:
    - Local AI inference (no external APIs)
    - Context-aware conversation
    - Personality customization
    - Multi-language support
    - Streaming responses
    - Error recovery
    """
    
    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        system_prompt: Optional[str] = None
    ):
        """
        Initialize Ollama engine.
        
        Args:
            model: Ollama model name (llama2, mistral, etc.)
            base_url: Ollama API base URL
            system_prompt: System prompt defining AI personality
        """
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.chat_url = f"{base_url}/api/chat"
        
        # Default system prompt
        if system_prompt is None:
            system_prompt = """You are GURU, a helpful and friendly personal AI assistant.

Your personality:
- Warm, friendly, and conversational
- Patient and understanding
- Helpful and knowledgeable
- Natural and human-like
- Supportive and encouraging

Guidelines:
- Keep responses concise (1-3 sentences for simple questions)
- Be conversational and natural
- Use the user's language (English, Hindi, or mixed)
- Show personality and warmth
- Ask clarifying questions when needed
- Admit when you don't know something

Remember: You are a voice assistant, so keep responses brief and natural for speaking."""
        
        self.system_prompt = system_prompt
        
        # Conversation history
        self.conversation_history: List[Message] = []
        self.max_history = 10  # Keep last 10 exchanges
        
        # Lazy availability check - don't block initialization
        self._availability_checked = False
        self._available = False
        
        safe_print(f"Ollama engine created (Model: {model}, will check availability on first use)")
    
    @property
    def available(self) -> bool:
        """Check if Ollama is available (lazy evaluation)"""
        if not self._availability_checked:
            self._available = self._check_availability()
            self._availability_checked = True
            
            if self._available:
                safe_print(f"✓ Ollama engine available (Model: {self.model})")
            else:
                safe_print(f"⚠ Ollama not available at {self.base_url}")
                safe_print("  Install Ollama from: https://ollama.ai")
                safe_print(f"  Then run: ollama pull {self.model}")
        
        return self._available
    
    def _check_availability(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def generate_response(self, user_input: str, stream: bool = False) -> str:
        """
        Generate AI response to user input.
        
        Args:
            user_input: User's message
            stream: Whether to stream response (not implemented yet)
        
        Returns:
            AI-generated response
        """
        if not self.available:
            return self._fallback_response(user_input)
        
        try:
            # Add user message to history
            user_message = Message(role="user", content=user_input)
            self.conversation_history.append(user_message)
            
            # Build messages for API
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for msg in self.conversation_history[-self.max_history:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Call Ollama API
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                }
            }
            
            response = requests.post(
                self.chat_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                assistant_response = result.get("message", {}).get("content", "")
                
                # Add assistant response to history
                assistant_message = Message(role="assistant", content=assistant_response)
                self.conversation_history.append(assistant_message)
                
                # Trim history if too long
                if len(self.conversation_history) > self.max_history * 2:
                    self.conversation_history = self.conversation_history[-self.max_history * 2:]
                
                return assistant_response.strip()
            else:
                print(f"Ollama API error: {response.status_code}")
                return self._fallback_response(user_input)
        
        except requests.exceptions.Timeout:
            print("Ollama request timeout")
            return "I'm thinking a bit slowly right now. Could you ask that again?"
        
        except Exception as e:
            print(f"Ollama error: {e}")
            return self._fallback_response(user_input)
    
    def _fallback_response(self, user_input: str) -> str:
        """Fallback response when Ollama is not available"""
        user_lower = user_input.lower()
        
        # Simple pattern matching for common queries
        if any(word in user_lower for word in ["hello", "hi", "hey", "namaste"]):
            return "Hello! I'm GURU. How can I help you today?"
        
        elif any(word in user_lower for word in ["how are you", "kaise ho", "what's up"]):
            return "I'm doing great, thank you for asking! How can I assist you?"
        
        elif any(word in user_lower for word in ["thank", "thanks", "dhanyavaad"]):
            return "You're welcome! Happy to help anytime."
        
        elif any(word in user_lower for word in ["bye", "goodbye", "alvida"]):
            return "Goodbye! Feel free to call me whenever you need help."
        
        elif "?" in user_input:
            return "That's a great question! To give you the best answer, I need Ollama running. You can install it from ollama.ai and run 'ollama pull llama2'."
        
        else:
            return "I understand. To have more natural conversations, please install Ollama from ollama.ai and run 'ollama pull llama2'."
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("Conversation history cleared")
    
    def get_history(self) -> List[Message]:
        """Get conversation history"""
        return self.conversation_history
    
    def set_system_prompt(self, prompt: str):
        """Update system prompt"""
        self.system_prompt = prompt
        print("System prompt updated")


# Global engine instance
_ollama_engine: Optional[OllamaEngine] = None


def get_ollama_engine(model: str = "llama2") -> OllamaEngine:
    """Get global Ollama engine instance"""
    global _ollama_engine
    if _ollama_engine is None:
        _ollama_engine = OllamaEngine(model=model)
    return _ollama_engine


def generate_response(user_input: str) -> str:
    """
    Convenience function to generate AI response.
    
    Args:
        user_input: User's message
    
    Returns:
        AI-generated response
    """
    engine = get_ollama_engine()
    return engine.generate_response(user_input)


if __name__ == "__main__":
    # Test Ollama engine
    engine = OllamaEngine()
    
    if engine.available:
        print("\nTesting Ollama engine...")
        
        test_inputs = [
            "Hello! How are you?",
            "What can you help me with?",
            "Tell me a joke",
            "Thank you!",
        ]
        
        for user_input in test_inputs:
            print(f"\nUser: {user_input}")
            response = engine.generate_response(user_input)
            print(f"GURU: {response}")
    else:
        print("\nOllama not available. Install from: https://ollama.ai")
        print("Then run: ollama pull llama2")
