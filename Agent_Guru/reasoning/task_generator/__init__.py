"""
Task Generator module for converting LLM outputs into structured Task objects.

This module provides the TaskModelGenerator class that parses LLM reasoning
outputs and converts them into validated, executable Task objects.
"""

from Agent_Guru.reasoning.task_generator.task_decomposer import (
    TaskModelGenerator,
)

__all__ = [
    "TaskModelGenerator",
]

