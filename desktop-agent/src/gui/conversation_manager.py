"""
GURU Conversation Manager - Natural Human-like Dialogue

Manages multi-turn conversations with context awareness, personality,
and natural human-like responses using local AI (Ollama).

Features:
- Real AI responses using Ollama
- Context-aware conversation
- Personality and emotion
- Multi-turn conversation tracking
- Intent recognition
- Natural language understanding
- Memory of previous interactions
- Fallback to templates when AI unavailable
"""

import time
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Import console utilities for cross-platform Unicode support
try:
    from utils.console import safe_print
except ImportError:
    # Fallback if utils not available
    def safe_print(text, **kwargs):
        try:
            print(text, **kwargs)
        except UnicodeEncodeError:
            text = str(text).replace('✓', '[OK]').replace('✗', '[X]').replace('⚠', '[!]')
            print(text, **kwargs)

# Import Ollama engine
try:
    from ai.ollama_engine import get_ollama_engine
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    safe_print("⚠ Ollama engine not available - using template responses")

# Import command executor
try:
    from execution.command_executor import get_command_executor, ExecutionStatus
    COMMAND_EXECUTOR_AVAILABLE = True
except ImportError:
    COMMAND_EXECUTOR_AVAILABLE = False
    safe_print("⚠ Command executor not available - commands will not be executed")


class Intent(Enum):
    """User intent categories"""
    GREETING = "greeting"
    FAREWELL = "farewell"
    QUESTION = "question"
    COMMAND = "command"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"
    GRATITUDE = "gratitude"
    SMALL_TALK = "small_talk"
    HELP = "help"
    UNKNOWN = "unknown"


class Emotion(Enum):
    """GURU emotional states"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    HELPFUL = "helpful"
    CONCERNED = "concerned"
    APOLOGETIC = "apologetic"
    EXCITED = "excited"


@dataclass
class ConversationTurn:
    """Single turn in conversation"""
    user_input: str
    guru_response: str
    intent: Intent
    emotion: Emotion
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Conversation context and state"""
    turns: List[ConversationTurn] = field(default_factory=list)
    user_name: Optional[str] = None
    current_topic: Optional[str] = None
    pending_action: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    session_start: datetime = field(default_factory=datetime.now)


class ConversationManager:
    """
    Manages natural human-like conversations with GURU.
    
    Provides context-aware responses, personality, emotion,
    and multi-turn conversation tracking.
    """
    
    def __init__(self):
        """Initialize conversation manager"""
        self.context = ConversationContext()
        self.current_emotion = Emotion.NEUTRAL
        
        # Initialize Ollama engine for real AI responses
        self.use_ai = OLLAMA_AVAILABLE
        if self.use_ai:
            # Load model from LLM configuration
            model_name = self._get_conversation_model()
            self.ai_engine = get_ollama_engine(model=model_name)
            if not self.ai_engine.available:
                safe_print(f"⚠ Ollama not running or model '{model_name}' not available")
                safe_print("  Fallingback to template responses")
                safe_print("  To enable AI: Install Ollama from https://ollama.ai")
                safe_print(f"  Then run: ollama pull {model_name}")
                self.use_ai = False
        else:
            self.ai_engine = None
        
        # Response templates with personality
        self.responses = {
            Intent.GREETING: [
                "Hello! I'm GURU, your personal assistant. How can I help you today?",
                "Hi there! Great to see you. What can I do for you?",
                "Hey! I'm here and ready to assist. What's on your mind?",
                "Good to hear from you! How may I assist you today?"
            ],
            Intent.FAREWELL: [
                "Goodbye! Feel free to call me anytime you need help.",
                "Take care! I'll be here whenever you need me.",
                "See you later! Don't hesitate to reach out if you need anything.",
                "Bye! Have a great day!"
            ],
            Intent.GRATITUDE: [
                "You're very welcome! Happy to help.",
                "My pleasure! That's what I'm here for.",
                "Anytime! Glad I could assist you.",
                "No problem at all! Feel free to ask me anything else."
            ],
            Intent.HELP: [
                "I can help you with many things! I can open applications, search the web, set reminders, answer questions, and much more. What would you like to do?",
                "I'm here to make your life easier! I can control your computer, answer questions, manage tasks, and assist with various activities. What do you need?",
                "Think of me as your personal assistant! I can help with computer tasks, information lookup, scheduling, and general assistance. How can I help you today?"
            ],
            Intent.SMALL_TALK: [
                "I'm doing great, thanks for asking! How about you?",
                "I'm here and ready to help! What's new with you?",
                "All systems operational! How can I make your day better?",
                "I'm excellent! Always happy to chat with you."
            ]
        }
        
        # Intent keywords (ordered by priority - more specific first)
        self.intent_keywords = {
            Intent.SMALL_TALK: [
                "how are you", "how r you", "how are u", "how r u",
                "what's up", "whats up", "wassup",
                "how's it going", "hows it going",
                "how do you feel", "how you doing",
                "you okay", "you alright", "you good",
                "kaise ho", "kya hal hai"  # Hindi support
            ],
            Intent.HELP: [
                "help", "what can you do", "how do you work",
                "capabilities", "features", "show me",
                "tell me about", "explain"
            ],
            Intent.GREETING: [
                "hello", "hi", "hey", "greetings",
                "good morning", "good afternoon", "good evening",
                "namaste", "namaskar"  # Hindi support
            ],
            Intent.FAREWELL: [
                "goodbye", "bye", "see you", "later", "farewell",
                "good night", "take care", "alvida"  # Hindi support
            ],
            Intent.GRATITUDE: [
                "thank", "thanks", "appreciate", "grateful",
                "dhanyavaad", "shukriya"  # Hindi support
            ],
            Intent.COMMAND: [
                "open", "close", "start", "stop", "run", "execute",
                "launch", "search", "find", "create", "delete",
                "show", "display", "play", "pause", "resume",
                "karo", "kholo", "band karo"  # Hindi support
            ],
            Intent.CONFIRMATION: [
                "yes", "yeah", "yep", "sure", "okay", "ok",
                "correct", "right", "affirmative", "absolutely",
                "haan", "ji", "bilkul"  # Hindi support
            ],
            Intent.NEGATION: [
                "no", "nope", "nah", "not", "never",
                "negative", "incorrect", "wrong",
                "nahin", "nahi", "mat"  # Hindi support
            ],
            Intent.QUESTION: [
                "what", "when", "where", "who", "why", "how",
                "is", "are", "can", "could", "would", "should",
                "kya", "kab", "kahan", "kaun", "kyun", "kaise"  # Hindi support
            ]
        }
        
        safe_print(f"Conversation Manager initialized (AI: {'Ollama' if self.use_ai else 'Templates'})")
    
    def _get_conversation_model(self) -> str:
        """
        Get conversation model from LLM configuration.
        
        Returns:
            Model name for conversation task
        """
        try:
            # Import LLM config manager
            import sys
            from pathlib import Path
            
            # Add src to path if not already there
            src_path = Path(__file__).parent.parent
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
            
            from llm.config_manager import get_llm_config_manager
            
            # Load configuration
            config_manager = get_llm_config_manager()
            config = config_manager.load_configuration()
            
            # Get conversation task configuration
            conversation_config = config.get('tasks', {}).get('conversation', {})
            
            # Check if enabled
            if not conversation_config.get('enabled', True):
                safe_print("⚠ Conversation task is disabled in LLM configuration")
                return "qwen2.5:7b-instruct"  # Default fallback
            
            # Get model name
            model = conversation_config.get('model', 'qwen2.5:7b-instruct')
            
            safe_print(f"✓ Loaded conversation model from config: {model}")
            return model
            
        except Exception as e:
            safe_print(f"⚠ Failed to load conversation model from config: {e}")
            safe_print("  Using default: qwen2.5:7b-instruct")
            return "qwen2.5:7b-instruct"
    
    def process_input(self, user_input: str) -> Tuple[str, Intent, Emotion]:
        """
        Process user input and generate natural response.
        
        Args:
            user_input: User's text input
        
        Returns:
            Tuple of (response_text, detected_intent, emotion)
        """
        # Detect intent
        intent = self._detect_intent(user_input)
        
        # Check if this is a command that should be executed
        if intent == Intent.COMMAND and COMMAND_EXECUTOR_AVAILABLE:
            try:
                executor = get_command_executor()
                result = executor.execute(user_input)
                
                if result.status == ExecutionStatus.SUCCESS:
                    response = result.message
                    emotion = Emotion.HELPFUL
                else:
                    response = f"{result.message}. {result.error or ''}"
                    emotion = Emotion.APOLOGETIC
                
                # Record conversation turn
                turn = ConversationTurn(
                    user_input=user_input,
                    guru_response=response,
                    intent=intent,
                    emotion=emotion,
                    timestamp=datetime.now(),
                    context={"execution_result": result}
                )
                self.context.turns.append(turn)
                
                return response, intent, emotion
                
            except Exception as e:
                safe_print(f"Command execution error: {e}")
                # Fall through to normal conversation
        
        # Determine emotion
        emotion = self._determine_emotion(intent, user_input)
        self.current_emotion = emotion
        
        # Generate response using AI or templates with intelligent fallback
        if self.use_ai and self.ai_engine:
            try:
                # Use Ollama for real AI response with short timeout
                import threading
                
                response_container = [None]
                error_container = [None]
                
                def generate_with_timeout():
                    try:
                        response_container[0] = self.ai_engine.generate_response(user_input)
                    except Exception as e:
                        error_container[0] = e
                
                # Start generation in thread
                gen_thread = threading.Thread(target=generate_with_timeout, daemon=True)
                gen_thread.start()
                
                # Wait max 10 seconds
                gen_thread.join(timeout=10.0)
                
                if response_container[0]:
                    response = response_container[0]
                    
                    # If response is too long for voice, summarize
                    if len(response) > 200:
                        response = response[:200] + "..."
                else:
                    # Timeout or error - use template
                    safe_print("AI response timeout - using template")
                    response = self._generate_template_response(user_input, intent, emotion)
                
            except Exception as e:
                safe_print(f"AI generation error: {e}")
                # Fallback to template
                response = self._generate_template_response(user_input, intent, emotion)
        else:
            # Use template responses
            response = self._generate_template_response(user_input, intent, emotion)
        
        # Record conversation turn
        turn = ConversationTurn(
            user_input=user_input,
            guru_response=response,
            intent=intent,
            emotion=emotion,
            timestamp=datetime.now()
        )
        self.context.turns.append(turn)
        
        # Keep only last 50 turns
        if len(self.context.turns) > 50:
            self.context.turns = self.context.turns[-50:]
        
        return response, intent, emotion
    
    def _generate_template_response(self, user_input: str, intent: Intent, emotion: Emotion) -> str:
        """Generate response using templates (fallback when AI unavailable)"""
        response = self._generate_response(user_input, intent, emotion)
        
        # Add emotional flavor
        response = self._add_emotional_flavor(response, emotion)
        
        # Add context if available
        if self.context.user_name:
            # Occasionally use user's name
            if random.random() < 0.2:
                response = f"{self.context.user_name}, {response[0].lower()}{response[1:]}"
        
        # Record conversation turn
        turn = ConversationTurn(
            user_input=user_input,
            guru_response=response,
            intent=intent,
            emotion=emotion,
            timestamp=datetime.now()
        )
        self.context.turns.append(turn)
        
        # Keep only last 50 turns
        if len(self.context.turns) > 50:
            self.context.turns = self.context.turns[-50:]
        
        return response, intent, emotion
    
    def _detect_intent(self, text: str) -> Intent:
        """Detect user intent from text"""
        text_lower = text.lower()
        
        # Check each intent's keywords
        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return intent
        
        # Default to unknown
        return Intent.UNKNOWN
    
    def _determine_emotion(self, intent: Intent, text: str) -> Emotion:
        """Determine appropriate emotional response"""
        text_lower = text.lower()
        
        # Emotion based on intent
        emotion_map = {
            Intent.GREETING: Emotion.HAPPY,
            Intent.FAREWELL: Emotion.NEUTRAL,
            Intent.GRATITUDE: Emotion.HAPPY,
            Intent.HELP: Emotion.HELPFUL,
            Intent.QUESTION: Emotion.HELPFUL,
            Intent.COMMAND: Emotion.HELPFUL,
            Intent.SMALL_TALK: Emotion.HAPPY,
            Intent.CONFIRMATION: Emotion.HELPFUL,
            Intent.NEGATION: Emotion.CONCERNED
        }
        
        # Check for urgency or problems
        if any(word in text_lower for word in ["urgent", "emergency", "problem", "issue", "error", "broken"]):
            return Emotion.CONCERNED
        
        # Check for excitement
        if any(word in text_lower for word in ["amazing", "awesome", "great", "excellent", "wonderful"]):
            return Emotion.EXCITED
        
        return emotion_map.get(intent, Emotion.NEUTRAL)
    
    def _generate_response(self, user_input: str, intent: Intent, emotion: Emotion) -> str:
        """Generate natural response based on intent and emotion"""
        
        # Get base response from templates
        if intent in self.responses:
            base_response = random.choice(self.responses[intent])
        else:
            # Handle unknown intent
            base_response = self._handle_unknown_intent(user_input)
        
        # Add emotional flavor
        response = self._add_emotional_flavor(base_response, emotion)
        
        # Add context if available
        if self.context.user_name:
            # Occasionally use user's name
            if random.random() < 0.2:
                response = f"{self.context.user_name}, {response[0].lower()}{response[1:]}"
        
        return response
    
    def _handle_unknown_intent(self, user_input: str) -> str:
        """Handle unknown intent with helpful response"""
        responses = [
            "I'm not quite sure I understand. Could you rephrase that?",
            "Hmm, I'm not certain what you mean. Can you explain it differently?",
            "I want to help, but I need a bit more clarity. Could you elaborate?",
            "I'm still learning! Could you try asking that in a different way?",
            "I'm not sure about that one. Can you give me more details?"
        ]
        
        # If it looks like a command, offer to help
        if any(word in user_input.lower() for word in ["open", "run", "start", "launch"]):
            return "I can help you with that! What application or file would you like me to open?"
        
        # If it looks like a question, acknowledge
        if "?" in user_input or any(word in user_input.lower() for word in ["what", "how", "why", "when", "where"]):
            return "That's an interesting question! Let me think about that. Could you provide more context?"
        
        return random.choice(responses)
    
    def _add_emotional_flavor(self, response: str, emotion: Emotion) -> str:
        """Add emotional flavor to response"""
        
        # Emotion-specific additions
        if emotion == Emotion.EXCITED:
            # Add enthusiasm
            if not response.endswith("!"):
                response = response.rstrip(".") + "!"
        
        elif emotion == Emotion.CONCERNED:
            # Add concern
            prefixes = ["Oh, ", "I see. ", "I understand. "]
            if random.random() < 0.5:
                response = random.choice(prefixes) + response
        
        elif emotion == Emotion.APOLOGETIC:
            # Add apology
            prefixes = ["I apologize. ", "I'm sorry. ", "My apologies. "]
            response = random.choice(prefixes) + response
        
        elif emotion == Emotion.HAPPY:
            # Add positivity
            if random.random() < 0.3:
                suffixes = [" 😊", " I'm happy to help!", " Great!"]
                response += random.choice(suffixes)
        
        return response
    
    def set_user_name(self, name: str):
        """Set user's name for personalization"""
        self.context.user_name = name
        safe_print(f"User name set to: {name}")
    
    def get_conversation_history(self, limit: int = 10) -> List[ConversationTurn]:
        """Get recent conversation history"""
        return self.context.turns[-limit:]
    
    def clear_context(self):
        """Clear conversation context"""
        self.context = ConversationContext()
        safe_print("Conversation context cleared")
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current conversation context"""
        return {
            "total_turns": len(self.context.turns),
            "user_name": self.context.user_name,
            "current_topic": self.context.current_topic,
            "current_emotion": self.current_emotion.value,
            "session_duration": (datetime.now() - self.context.session_start).total_seconds(),
            "recent_intents": [turn.intent.value for turn in self.context.turns[-5:]]
        }


def create_conversation_manager() -> ConversationManager:
    """
    Factory function to create conversation manager.
    
    Returns:
        ConversationManager instance
    """
    return ConversationManager()


# Export
__all__ = ['ConversationManager', 'Intent', 'Emotion', 'ConversationTurn', 'create_conversation_manager']
