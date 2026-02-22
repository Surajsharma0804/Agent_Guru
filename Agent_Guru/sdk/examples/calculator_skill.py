"""
Example calculator skill for Agent Guru.

This skill demonstrates a simple computational skill with no
external dependencies or permissions required.
"""

import math
from typing import Dict, Union
from Agent_Guru.sdk import Skill, skill_capability


class CalculatorSkill(Skill):
    """Mathematical calculation skill."""

    def __init__(self):
        """Initialize calculator skill."""
        super().__init__()

    @skill_capability("calculate", "Perform mathematical calculations")
    async def calculate(self, expression: str) -> Dict[str, Union[float, str]]:
        """Evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            Calculation result dictionary
        """
        try:
            # Safe evaluation (limited to math operations)
            allowed_names = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "pi": math.pi,
                "e": math.e,
            }

            result = eval(expression, {"__builtins__": {}}, allowed_names)

            return {
                "expression": expression,
                "result": float(result),
                "success": True,
            }

        except Exception as e:
            return {
                "expression": expression,
                "error": str(e),
                "success": False,
            }

    @skill_capability("convert_units", "Convert between units")
    async def convert_units(
        self, value: float, from_unit: str, to_unit: str
    ) -> Dict[str, Union[float, str]]:
        """Convert a value from one unit to another.

        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Conversion result dictionary
        """
        # Conversion factors (to base unit)
        conversions = {
            # Length (meters)
            "m": 1.0,
            "km": 1000.0,
            "cm": 0.01,
            "mm": 0.001,
            "mi": 1609.34,
            "ft": 0.3048,
            "in": 0.0254,
            # Weight (grams)
            "g": 1.0,
            "kg": 1000.0,
            "mg": 0.001,
            "lb": 453.592,
            "oz": 28.3495,
            # Temperature (special case)
            "c": None,
            "f": None,
            "k": None,
        }

        try:
            # Handle temperature conversions separately
            if from_unit.lower() in ["c", "f", "k"]:
                result = self._convert_temperature(
                    value, from_unit.lower(), to_unit.lower()
                )
            else:
                # Standard unit conversion
                from_factor = conversions.get(from_unit.lower())
                to_factor = conversions.get(to_unit.lower())

                if from_factor is None or to_factor is None:
                    raise ValueError(f"Unknown unit: {from_unit} or {to_unit}")

                # Convert to base unit, then to target unit
                base_value = value * from_factor
                result = base_value / to_factor

            return {
                "value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "result": result,
                "success": True,
            }

        except Exception as e:
            return {
                "value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "error": str(e),
                "success": False,
            }

    def _convert_temperature(
        self, value: float, from_unit: str, to_unit: str
    ) -> float:
        """Convert temperature between C, F, and K.

        Args:
            value: Temperature value
            from_unit: Source unit (c, f, k)
            to_unit: Target unit (c, f, k)

        Returns:
            Converted temperature
        """
        # Convert to Celsius first
        if from_unit == "c":
            celsius = value
        elif from_unit == "f":
            celsius = (value - 32) * 5 / 9
        elif from_unit == "k":
            celsius = value - 273.15
        else:
            raise ValueError(f"Unknown temperature unit: {from_unit}")

        # Convert from Celsius to target
        if to_unit == "c":
            return celsius
        elif to_unit == "f":
            return celsius * 9 / 5 + 32
        elif to_unit == "k":
            return celsius + 273.15
        else:
            raise ValueError(f"Unknown temperature unit: {to_unit}")


# Generate manifest when run as script
if __name__ == "__main__":
    from pathlib import Path
    from Agent_Guru.sdk import ManifestGenerator

    manifest = ManifestGenerator.generate_and_save(
        skill_class=CalculatorSkill,
        output_path=Path("calculator_skill_manifest.json"),
        skill_id="com.example.calculator",
        version="1.0.0",
        name="Calculator Skill",
        description="Performs mathematical calculations and unit conversions",
        author="Example Developer",
        required_permissions=[],  # No permissions needed
        max_latency=1000,
        dependencies=[],  # No external dependencies
    )

    print("Manifest generated successfully!")
    print(f"Capabilities: {manifest['capabilities']}")
