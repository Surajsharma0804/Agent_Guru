"""Information tools for question answering, definitions, calculations, and unit conversions.

Provides access to knowledge bases and computational tools.
"""

import ast
import math
import re
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
        expression = str(kwargs.get("expression") or "")
        if not expression.strip():
            return {"success": False, "error": "Expression cannot be empty"}
        # Never raises: every failure is a result the caller can say. The
        # old evaluator let SyntaxError, OverflowError and RecursionError
        # escape, so "(1+2", "9**9**9" and a long sum of 5,000 terms took
        # the caller down instead of getting an answer.
        try:
            result = evaluate_expression(expression)
        except CalculationError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # anything unforeseen is still an answer, not a crash
            return {"success": False, "error": f"Could not calculate that ({type(exc).__name__})"}
        shown = _format_number(result)
        return {
            "success": True,
            "result": {"expression": expression, "result": result, "message": f"{expression} = {shown}"},
        }


class CalculationError(ValueError):
    """An expression that cannot be calculated, with the reason in words."""


#: Longest expression accepted, in characters after rewriting.
MAX_EXPRESSION_CHARS = 20_000
#: Largest integer result, in decimal digits. 9**9**9 has about 370 million
#: digits; computing it used gigabytes of memory before any check ran.
MAX_RESULT_DIGITS = 10_000
_MAX_RESULT_BITS = int(MAX_RESULT_DIGITS * 3.33)


def _factorial(n: Any) -> int:
    if not float(n).is_integer() or n < 0:
        msg = "factorial needs a whole number that is not negative"
        raise CalculationError(msg)
    if n > 3000:
        msg = "that factorial is too large to calculate"
        raise CalculationError(msg)
    return math.factorial(int(n))


def _log(x: Any, base: Any = None) -> float:
    return math.log(x) if base is None else math.log(x, base)


_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x), "abs": abs,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "atan2": math.atan2, "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": _log, "ln": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "floor": math.floor, "ceil": math.ceil, "round": round, "factorial": _factorial,
    "gcd": math.gcd, "lcm": math.lcm, "hypot": math.hypot, "degrees": math.degrees, "radians": math.radians,
    "min": min, "max": max,
}
_CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e, "tau": math.tau}

_SPOKEN = [
    (r"^\s*(?:what\s+is|what's|whats|calculate|compute|evaluate|how\s+much\s+is)\s+", ""),
    (r"[?=]+\s*$", ""),
    (r"(?<=\d),(?=\d{3}\b)", ""),  # 1,000 -> 1000
    (r"\bsquare\s+root\s+of\s+", "sqrt "),
    (r"\bcube\s+root\s+of\s+", "cbrt "),
    (r"(\d+(?:\.\d+)?)\s+squared\b", r"(\1**2)"),
    (r"(\d+(?:\.\d+)?)\s+cubed\b", r"(\1**3)"),
    (r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+", r"(\1/100)*"),
    (r"(\d+(?:\.\d+)?)\s*(?:%|percent)(?!\s*[\d(.])", r"(\1/100)"),  # "10 % 3" stays modulo
    (r"\bto\s+the\s+power\s+of\b", "**"),
    (r"\b(?:multiplied\s+by|times)\b", "*"),
    (r"\b(?:divided\s+by|over)\b", "/"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"(?<=[\d)])\s*[x×]\s*(?=[\d(])", "*"),
    (r"÷", "/"),
    (r"[−–]", "-"),
    (r"\^", "**"),
    (r"\b(sqrt|cbrt) (\d+(?:\.\d+)?)", r"\1(\2)"),
]


def _rewrite_spoken(text: str) -> str:
    """The expression as Python arithmetic: "15% of 200" -> "(15/100)*200"."""
    out = text.strip().lower()
    for pattern, replacement in _SPOKEN:
        out = re.sub(pattern, replacement, out)
    return out.strip()


def _check_size(value: Any) -> Any:
    if isinstance(value, complex):
        msg = "the answer is not a real number"
        raise CalculationError(msg)
    if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > _MAX_RESULT_BITS:
        msg = f"the answer would have more than {MAX_RESULT_DIGITS:,} digits"
        raise CalculationError(msg)
    if isinstance(value, float) and math.isinf(value):
        msg = "the answer is too large"
        raise CalculationError(msg)
    return value


def _power(base: Any, exponent: Any) -> Any:
    # Size checked before computing: 10**10**8 would allocate first and fail later.
    if abs(base) > 1 and exponent > 0 and exponent * math.log10(abs(base)) > MAX_RESULT_DIGITS:
        msg = f"the answer would have more than {MAX_RESULT_DIGITS:,} digits"
        raise CalculationError(msg)
    return base ** exponent


_BINARY: dict[type, Any] = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
    ast.Pow: _power,
}
_UNARY: dict[type, Any] = {ast.USub: lambda a: -a, ast.UAdd: lambda a: +a}


def evaluate_expression(text: str) -> int | float:
    """The value of an arithmetic expression, written or spoken; raises CalculationError.

    Only numbers, + - * / // % **, the functions in _FUNCTIONS and pi, e
    and tau are accepted; any other name, attribute, string, subscript or
    keyword is refused before anything is evaluated. The tree is walked
    with an explicit stack, so a long expression cannot exhaust Python's
    recursion limit.
    """
    expression = _rewrite_spoken(text)
    if len(expression) > MAX_EXPRESSION_CHARS:
        msg = "that expression is too long"
        raise CalculationError(msg)
    try:
        tree = ast.parse(expression, mode="eval")
    except RecursionError as exc:
        # Python's parser nests "1+1+...+1" one level per term and gives up
        # at about 2,000 terms on Windows with Python 3.13. Summing the
        # top-level terms one by one has no such limit.
        terms = _top_level_terms(expression)
        if len(terms) < 2:
            msg = "that expression is nested too deeply"
            raise CalculationError(msg) from exc
        total: Any = 0
        for sign, term in terms:
            total = _apply(lambda a, b, s=sign: a + b if s == "+" else a - b, total, evaluate_expression(term))
        return total
    except (SyntaxError, ValueError, MemoryError) as exc:
        msg = "I could not read that as a calculation"
        raise CalculationError(msg) from exc

    values: list[Any] = []
    stack: list[tuple[ast.AST, bool]] = [(tree.body, False)]
    while stack:
        node, ready = stack.pop()
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                msg = "only numbers can be calculated"
                raise CalculationError(msg)
            values.append(node.value)
        elif isinstance(node, ast.Name):
            if node.id not in _CONSTANTS:
                msg = f"I don't know what {node.id} is"
                raise CalculationError(msg)
            values.append(_CONSTANTS[node.id])
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            if ready:
                right, left = values.pop(), values.pop()
                values.append(_apply(_BINARY[type(node.op)], left, right))
            else:
                stack += [(node, True), (node.right, False), (node.left, False)]
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            if ready:
                values.append(_apply(_UNARY[type(node.op)], values.pop()))
            else:
                stack += [(node, True), (node.operand, False)]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS
              and not node.keywords and 1 <= len(node.args) <= 4):
            if ready:
                args = [values.pop() for _ in node.args][::-1]
                values.append(_apply(_FUNCTIONS[node.func.id], *args))
            else:
                stack.append((node, True))
                stack += [(arg, False) for arg in reversed(node.args)]
        else:
            msg = "that is not a calculation I can do"
            raise CalculationError(msg)
    return values.pop()


def _top_level_terms(expression: str) -> list[tuple[str, str]]:
    """Split at + and - outside brackets that are not signs: "1+2*(3-4)-5" -> [+1, +2*(3-4), -5]."""
    terms: list[tuple[str, str]] = []
    depth, start, sign, previous = 0, 0, "+", ""
    for i, ch in enumerate(expression):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch in "+-" and depth == 0 and previous and previous not in "+-*/%(eE":
            terms.append((sign, expression[start:i]))
            sign, start = ch, i + 1
        if not ch.isspace():
            previous = ch
    terms.append((sign, expression[start:]))
    return [(s, t) for s, t in terms if t.strip()]


def _apply(fn: Any, *args: Any) -> Any:
    try:
        return _check_size(fn(*args))
    except ZeroDivisionError as exc:
        msg = "you can't divide by zero"
        raise CalculationError(msg) from exc
    except (OverflowError, MemoryError) as exc:
        msg = "the answer is too large"
        raise CalculationError(msg) from exc
    except (ValueError, TypeError) as exc:
        if isinstance(exc, CalculationError):
            raise
        msg = f"that is outside what the function accepts ({exc})"
        raise CalculationError(msg) from exc


def _format_number(value: int | float) -> str:
    """How a result is said: whole floats without ".0", others to 12 significant digits."""
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.12g}"
    return str(value)

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

