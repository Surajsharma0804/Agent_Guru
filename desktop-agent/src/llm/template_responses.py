"""
Template Response System - Fallback Responses for LLM Timeouts

Provides pre-defined template responses when LLM requests timeout.
Ensures system remains responsive even when LLM is slow or unavailable.

DESIGN PRINCIPLES:
- Templates are safe, generic responses
- Never claim to have performed actions
- Acknowledge limitations honestly
- Maintain user trust through transparency
"""

from typing import Dict, List, Optional
from enum import Enum
import random
import logging


class ResponseCategory(Enum):
    """Categories of template responses."""
    GREETING = "greeting"
    ACKNOWLEDGMENT = "acknowledgment"
    ERROR = "error"
    TIMEOUT = "timeout"
    CLARIFICATION = "clarification"
    UNAVAILABLE = "unavailable"


class TemplateResponseSystem:
    """
    Template response system for LLM fallback.
    
    Features:
    - Category-based templates
    - Random selection for variety
    - Context-aware responses
    - Honest limitation acknowledgment
    """
    
    def __init__(self):
        """Initialize template response system."""
        self.logger = logging.getLogger("llm.template_responses")
        
        # Template database
        self.templates: Dict[ResponseCategory, List[str]] = {
            ResponseCategory.GREETING: [
                "Hello! How can I help you?",
                "Hi there! What can I do for you?",
                "Hey! Ready to assist.",
                "Hello! I'm here to help.",
            ],
            
            ResponseCategory.ACKNOWLEDGMENT: [
                "Got it.",
                "Understood.",
                "Okay.",
                "I see.",
                "Noted.",
            ],
            
            ResponseCategory.ERROR: [
                "I'm sorry, I couldn't process that.",
                "Something went wrong. Please try again.",
                "I encountered an error. Could you rephrase?",
                "I'm having trouble with that request.",
            ],
            
            ResponseCategory.TIMEOUT: [
                "I'm thinking... This is taking longer than expected.",
                "Processing... Please wait a moment.",
                "Still working on that...",
                "This is taking a bit longer than usual.",
            ],
            
            ResponseCategory.CLARIFICATION: [
                "Could you clarify what you'd like me to do?",
                "I'm not sure I understand. Could you rephrase?",
                "What would you like me to help with?",
                "Could you be more specific?",
            ],
            
            ResponseCategory.UNAVAILABLE: [
                "I'm currently unavailable. Please try again later.",
                "Service temporarily unavailable.",
                "I'm having connectivity issues. Please try again.",
                "Unable to process requests right now.",
            ]
        }
        
        self.logger.info("Template response system initialized")
    
    def get_response(
        self,
        category: ResponseCategory,
        context: Optional[Dict] = None
    ) -> str:
        """
        Get template response for category.
        
        Args:
            category: Response category
            context: Optional context for customization
        
        Returns:
            str: Template response
        """
        if category not in self.templates:
            self.logger.warning(f"Unknown category: {category}")
            return self.get_response(ResponseCategory.ERROR)
        
        templates = self.templates[category]
        
        # Select random template for variety
        response = random.choice(templates)
        
        # Customize based on context if provided
        if context:
            response = self._customize_response(response, context)
        
        self.logger.debug(f"Template response: {category.value} -> {response}")
        
        return response
    
    def get_timeout_response(
        self,
        elapsed_seconds: float,
        context: Optional[Dict] = None
    ) -> str:
        """
        Get timeout-specific response.
        
        Args:
            elapsed_seconds: Time elapsed before timeout
            context: Optional context
        
        Returns:
            str: Timeout response
        """
        if elapsed_seconds < 5:
            return "Processing..."
        elif elapsed_seconds < 10:
            return "Still thinking..."
        else:
            return self.get_response(ResponseCategory.TIMEOUT, context)
    
    def get_error_response(
        self,
        error_type: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Get error-specific response.
        
        Args:
            error_type: Type of error
            context: Optional context
        
        Returns:
            str: Error response
        """
        if error_type == "rate_limit":
            return "I'm receiving too many requests. Please wait a moment."
        elif error_type == "authentication":
            return "Authentication error. Please check configuration."
        elif error_type == "network":
            return "Network error. Please check your connection."
        else:
            return self.get_response(ResponseCategory.ERROR, context)
    
    def _customize_response(
        self,
        response: str,
        context: Dict
    ) -> str:
        """
        Customize response based on context.
        
        Args:
            response: Base response
            context: Context information
        
        Returns:
            str: Customized response
        """
        # Add user name if available
        if 'user_name' in context:
            response = f"{context['user_name']}, {response.lower()}"
        
        # Add specific error details if available
        if 'error_message' in context:
            response = f"{response} ({context['error_message']})"
        
        return response
    
    def add_template(
        self,
        category: ResponseCategory,
        template: str
    ) -> None:
        """
        Add custom template to category.
        
        Args:
            category: Response category
            template: Template string
        """
        if category not in self.templates:
            self.templates[category] = []
        
        self.templates[category].append(template)
        self.logger.info(f"Added template to {category.value}: {template}")
    
    def get_all_templates(self) -> Dict[str, List[str]]:
        """Get all templates organized by category."""
        return {
            category.value: templates
            for category, templates in self.templates.items()
        }
