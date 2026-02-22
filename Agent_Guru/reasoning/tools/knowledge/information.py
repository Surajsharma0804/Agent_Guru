"""
Information tools for question answering, definitions, calculations, and unit conversions.

Provides access to knowledge bases and computational tools.
"""

import asyncio
import re
from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="knowledge.question_answer",
    name="Question Answer",
    description="Answer questions using knowledge bases (Wikipedia, etc.)",
    parameters=[
        ToolParameter(
            name="question",
            type=ToolParameterType.STRING,
            description="Question to answer",
            required=True,
        )
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1500,
    capabilities=["question_answering", "knowledge_retrieval", "qa"],
    examples=[
        "What is the capital of France",
        "Who invented the telephone",
        "When was the Eiffel Tower built",
    ],
)
class QuestionAnswerTool(Tool):
    """Tool for answering questions."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute question answering.

        Args:
            question: Question to answer

        Returns:
            Execution result with answer
        """
        question = kwargs["question"]

        # Validate question
        if not question or not question.strip():
            return {
                "success": False,
                "error": "Question cannot be empty",
            }

        try:
            # Note: In a real implementation, this would:
            # 1. Query Wikipedia API or other knowledge bases
            # 2. Use LLM for answer extraction
            # 3. Provide sources and confidence scores
            return {
                "success": True,
                "result": {
                    "question": question,
                    "answer": "Answer would appear here based on knowledge base query",
                    "sources": ["Wikipedia", "Knowledge Base"],
                    "confidence": 0.85,
                    "message": f"Answer retrieved for: {question}",
                    "note": "This is a placeholder. Real implementation would query knowledge bases.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to answer question: {str(e)}",
            }


@tool(
    tool_id="knowledge.define_word",
    name="Define Word",
    description="Get the definition of a word",
    parameters=[
        ToolParameter(
            name="word",
            type=ToolParameterType.STRING,
            description="Word to define",
            required=True,
        )
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=500,
    capabilities=["dictionary", "definition", "word_lookup"],
    examples=[
        "Define 'serendipity'",
        "What does 'ephemeral' mean",
        "Define the word 'ubiquitous'",
    ],
)
class DefineWordTool(Tool):
    """Tool for defining words."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute word definition.

        Args:
            word: Word to define

        Returns:
            Execution result with definition
        """
        word = kwargs["word"]

        # Validate word
        if not word or not word.strip():
            return {
                "success": False,
                "error": "Word cannot be empty",
            }

        try:
            # Note: In a real implementation, this would use a dictionary API
            return {
                "success": True,
                "result": {
                    "word": word,
                    "definitions": [
                        {
                            "part_of_speech": "noun",
                            "definition": f"Definition of '{word}' would appear here",
                            "example": f"Example usage of '{word}' in a sentence",
                        }
                    ],
                    "pronunciation": f"Pronunciation of '{word}'",
                    "message": f"Definition retrieved for: {word}",
                    "note": "This is a placeholder. Real implementation would use dictionary API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to define word: {str(e)}",
            }


@tool(
    tool_id="knowledge.calculate",
    name="Calculate",
    description="Perform mathematical calculations",
    parameters=[
        ToolParameter(
            name="expression",
            type=ToolParameterType.STRING,
            description="Mathematical expression to evaluate",
            required=True,
        )
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=100,
    capabilities=["calculation", "math", "compute"],
    examples=[
        "Calculate 2 + 2",
        "What is 15% of 200",
        "Compute the square root of 144",
    ],
)
class CalculateTool(Tool):
    """Tool for calculations."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute calculation.

        Args:
            expression: Mathematical expression

        Returns:
            Execution result with calculation result
        """
        expression = kwargs["expression"]

        # Validate expression
        if not expression or not expression.strip():
            return {
                "success": False,
                "error": "Expression cannot be empty",
            }

        try:
            # Sanitize expression (only allow safe characters)
            safe_chars = set("0123456789+-*/().% ")
            if not all(c in safe_chars for c in expression):
                return {
                    "success": False,
                    "error": "Expression contains invalid characters",
                }

            # Evaluate expression safely
            # Note: In production, use a proper math parser library
            result = eval(expression, {"__builtins__": {}}, {})

            return {
                "success": True,
                "result": {
                    "expression": expression,
                    "result": result,
                    "message": f"{expression} = {result}",
                },
            }

        except ZeroDivisionError:
            return {
                "success": False,
                "error": "Division by zero",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to calculate: {str(e)}",
            }


# Unit conversion factors (to base unit)
UNIT_CONVERSIONS = {
    # Length (base: meter)
    "length": {
        "m": 1.0,
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "mi": 1609.34,
        "yd": 0.9144,
        "ft": 0.3048,
        "in": 0.0254,
    },
    # Weight (base: kilogram)
    "weight": {
        "kg": 1.0,
        "g": 0.001,
        "mg": 0.000001,
        "lb": 0.453592,
        "oz": 0.0283495,
        "ton": 1000.0,
    },
    # Temperature (special handling)
    "temperature": {
        "c": "celsius",
        "f": "fahrenheit",
        "k": "kelvin",
    },
    # Volume (base: liter)
    "volume": {
        "l": 1.0,
        "ml": 0.001,
        "gal": 3.78541,
        "qt": 0.946353,
        "pt": 0.473176,
        "cup": 0.236588,
        "fl_oz": 0.0295735,
    },
}


@tool(
    tool_id="knowledge.convert_units",
    name="Convert Units",
    description="Convert between different units of measurement",
    parameters=[
        ToolParameter(
            name="value",
            type=ToolParameterType.FLOAT,
            description="Value to convert",
            required=True,
        ),
        ToolParameter(
            name="from_unit",
            type=ToolParameterType.STRING,
            description="Source unit (e.g., 'km', 'lb', 'c')",
            required=True,
        ),
        ToolParameter(
            name="to_unit",
            type=ToolParameterType.STRING,
            description="Target unit (e.g., 'mi', 'kg', 'f')",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=100,
    capabilities=["unit_conversion", "conversion", "measurement"],
    examples=[
        "Convert 5 kilometers to miles",
        "How many pounds is 10 kilograms",
        "Convert 100 Celsius to Fahrenheit",
    ],
)
class ConvertUnitsTool(Tool):
    """Tool for unit conversion."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute unit conversion.

        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Execution result with converted value
        """
        value = kwargs["value"]
        from_unit = kwargs["from_unit"].lower()
        to_unit = kwargs["to_unit"].lower()

        try:
            # Find unit category
            from_category = None
            to_category = None

            for category, units in UNIT_CONVERSIONS.items():
                if from_unit in units:
                    from_category = category
                if to_unit in units:
                    to_category = category

            if from_category is None:
                return {
                    "success": False,
                    "error": f"Unknown source unit: {from_unit}",
                }

            if to_category is None:
                return {
                    "success": False,
                    "error": f"Unknown target unit: {to_unit}",
                }

            if from_category != to_category:
                return {
                    "success": False,
                    "error": f"Cannot convert between {from_category} and {to_category}",
                }

            # Handle temperature conversion (special case)
            if from_category == "temperature":
                if from_unit == "c" and to_unit == "f":
                    result = (value * 9 / 5) + 32
                elif from_unit == "f" and to_unit == "c":
                    result = (value - 32) * 5 / 9
                elif from_unit == "c" and to_unit == "k":
                    result = value + 273.15
                elif from_unit == "k" and to_unit == "c":
                    result = value - 273.15
                elif from_unit == "f" and to_unit == "k":
                    result = (value - 32) * 5 / 9 + 273.15
                elif from_unit == "k" and to_unit == "f":
                    result = (value - 273.15) * 9 / 5 + 32
                else:
                    result = value  # Same unit
            else:
                # Standard conversion through base unit
                from_factor = UNIT_CONVERSIONS[from_category][from_unit]
                to_factor = UNIT_CONVERSIONS[to_category][to_unit]
                result = value * from_factor / to_factor

            return {
                "success": True,
                "result": {
                    "original_value": value,
                    "original_unit": from_unit,
                    "converted_value": round(result, 6),
                    "converted_unit": to_unit,
                    "message": f"{value} {from_unit} = {round(result, 6)} {to_unit}",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to convert units: {str(e)}",
            }
