"""Information tools for question answering, definitions, calculations, and unit conversions.

Provides access to knowledge bases and computational tools.
"""

from typing import Any

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
        ),
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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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
            # BUG FIX (Round 21): this used to fabricate a literal template
            # string ("Answer would appear here...") together with a fake
            # "sources": ["Wikipedia", "Knowledge Base"] and a fake
            # "confidence": 0.85 -- presenting completely made-up metadata
            # about a lookup that never happened as if it were real. Wired
            # to the same real, already-tested web-search backend used by
            # reasoning/tools/knowledge/web_search.py (lazy import: see
            # that module's identical fix for why the import is lazy here).
            # This gives genuinely fetched content for most factual
            # questions instead of a template placeholder, and now honestly
            # attributes the source as "web search" -- not "Wikipedia",
            # since we don't control or verify which site the result
            # actually came from.
            from Agent_Guru.platform.features.web_search import search_web

            answer = await search_web(question, max_chars=600)

            if answer:
                return {
                    "success": True,
                    "result": {
                        "question": question,
                        "answer": answer,
                        "sources": ["web search"],
                        "message": f"Answer retrieved for: {question}",
                    },
                }

            return {
                "success": False,
                "error": (
                    "Could not answer the question: no web search backend "
                    "available (duckduckgo-search not installed, the "
                    "instant-answer API was unreachable, and no browser "
                    "fallback was available)."
                ),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to answer question: {e!s}",
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
        ),
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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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
            # BUG FIX (Round 21): this used to fabricate a fake definition
            # ("Definition of 'X' would appear here"), a fake example
            # sentence, and a fake "pronunciation" field -- claiming success
            # with content that was never looked up anywhere, for EVERY
            # word, including words that don't exist. DuckDuckGo's
            # instant-answer API (one of the three tiers inside
            # search_web()) frequently returns real dictionary-style
            # definitions for "define <word>" queries, so this is wired to
            # the same real backend used by web_search.py/QuestionAnswerTool
            # above rather than a dedicated dictionary API this codebase
            # doesn't have credentials for.
            from Agent_Guru.platform.features.web_search import search_web

            definition_text = await search_web(f"define {word}", max_chars=400)

            if definition_text:
                return {
                    "success": True,
                    "result": {
                        "word": word,
                        "definition": definition_text,
                        "message": f"Definition retrieved for: {word}",
                    },
                }

            return {
                "success": False,
                "error": (
                    f"Could not find a definition for '{word}': no web search "
                    "backend available (duckduckgo-search not installed, the "
                    "instant-answer API was unreachable, and no browser "
                    "fallback was available)."
                ),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to define word: {e!s}",
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
        ),
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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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

            # Evaluate expression safely using ast for security
            import ast as _ast
            import operator as _op

            _SAFE_OPS = {
                _ast.Add: _op.add,
                _ast.Sub: _op.sub,
                _ast.Mult: _op.mul,
                _ast.Div: _op.truediv,
                _ast.Mod: _op.mod,
                _ast.Pow: _op.pow,
                _ast.USub: _op.neg,
                _ast.UAdd: _op.pos,
            }

            def _safe_eval(node: _ast.AST) -> float:
                if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
                    return float(node.value)
                if isinstance(node, _ast.BinOp) and type(node.op) in _SAFE_OPS:
                    return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
                if isinstance(node, _ast.UnaryOp) and type(node.op) in _SAFE_OPS:
                    return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
                msg = f"Unsupported expression node: {type(node).__name__}"
                raise ValueError(msg)

            result = _safe_eval(_ast.parse(expression, mode="eval").body)

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

    # Temperature conversion strategies keyed by (from_unit, to_unit)
    _TEMP_CONVERTERS: dict[tuple[str, str], Any] = {
        ("c", "f"): lambda v: (v * 9 / 5) + 32,
        ("f", "c"): lambda v: (v - 32) * 5 / 9,
        ("c", "k"): lambda v: v + 273.15,
        ("k", "c"): lambda v: v - 273.15,
        ("f", "k"): lambda v: (v - 32) * 5 / 9 + 273.15,
        ("k", "f"): lambda v: (v - 273.15) * 9 / 5 + 32,
    }

    @staticmethod
    def _find_unit_category(unit: str) -> str | None:
        """Find the category for a given unit."""
        for category, units in UNIT_CONVERSIONS.items():
            if unit in units:
                return category
        return None

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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
            from_category = self._find_unit_category(from_unit)
            to_category = self._find_unit_category(to_unit)

            if from_category is None:
                return {"success": False, "error": f"Unknown source unit: {from_unit}"}
            if to_category is None:
                return {"success": False, "error": f"Unknown target unit: {to_unit}"}
            if from_category != to_category:
                return {
                    "success": False,
                    "error": f"Cannot convert between {from_category} and {to_category}",
                }

            result = self._convert(value, from_unit, to_unit, from_category)

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
            return {"success": False, "error": f"Failed to convert units: {e!s}"}

    @classmethod
    def _convert(cls, value: float, from_unit: str, to_unit: str, category: str) -> float:
        """Perform the actual unit conversion."""
        if category == "temperature":
            converter = cls._TEMP_CONVERTERS.get((from_unit, to_unit))
            return converter(value) if converter else value
        # Standard conversion through base unit
        from_factor = UNIT_CONVERSIONS[category][from_unit]
        to_factor = UNIT_CONVERSIONS[category][to_unit]
        return value * from_factor / to_factor

