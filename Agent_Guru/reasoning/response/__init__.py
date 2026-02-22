"""
Response Generation Module

This module provides template-based and LLM-based response generation
for the Core Reasoning Engine.

Components:
- TemplateGenerator: Fast template-based response generation (<100ms)
- RichContentGenerator: Structured data generation for UI cards, images, buttons
- ClientCapability: Client capability enumeration for adaptive content
"""

from Agent_Guru.reasoning.response.rich_content_generator import (
    ClientCapability,
    ContentType,
    RichContentGenerator,
)
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator

__all__ = [
    "TemplateGenerator",
    "RichContentGenerator",
    "ClientCapability",
    "ContentType",
]
