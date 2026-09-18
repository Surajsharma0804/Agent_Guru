"""Translation tool for translating text between languages.

Supports 50+ languages using translation APIs.
"""

from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool

# Common language codes
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "hu": "Hungarian",
    "ro": "Romanian",
    "uk": "Ukrainian",
    "el": "Greek",
    "he": "Hebrew",
    "fa": "Persian",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "ur": "Urdu",
    "sw": "Swahili",
    "am": "Amharic",
    "km": "Khmer",
    "lo": "Lao",
    "my": "Burmese",
    "ne": "Nepali",
    "si": "Sinhala",
    "ka": "Georgian",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "kk": "Kazakh",
    "uz": "Uzbek",
    "mn": "Mongolian",
    "bo": "Tibetan",
}


@tool(
    tool_id="translate.text",
    name="Translate Text",
    description="Translate text between languages",
    parameters=[
        ToolParameter(
            name="text",
            type=ToolParameterType.STRING,
            description="Text to translate",
            required=True,
        ),
        ToolParameter(
            name="target_language",
            type=ToolParameterType.STRING,
            description="Target language code (e.g., 'es' for Spanish, 'fr' for French)",
            required=True,
        ),
        ToolParameter(
            name="source_language",
            type=ToolParameterType.STRING,
            description="Source language code (default: auto-detect)",
            required=False,
            default="auto",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1000,
    capabilities=["translation", "language_processing", "translate"],
    examples=[
        "Translate 'Hello' to Spanish",
        "Translate this text to French",
        "How do you say 'thank you' in Japanese",
    ],
)
class TranslateTool(Tool):
    """Tool for translating text."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute text translation.

        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code

        Returns:
            Execution result with translation

        """
        text = kwargs["text"]
        target_language = kwargs["target_language"].lower()
        source_language = kwargs.get("source_language", "auto").lower()

        # Validate text
        if not text or not text.strip():
            return {
                "success": False,
                "error": "Text cannot be empty",
            }

        # Validate target language
        if target_language not in SUPPORTED_LANGUAGES and target_language != "auto":
            return {
                "success": False,
                "error": f"Unsupported target language: {target_language}. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}",
            }

        # Validate source language
        if source_language not in SUPPORTED_LANGUAGES and source_language != "auto":
            return {
                "success": False,
                "error": f"Unsupported source language: {source_language}. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())} or 'auto'",
            }

        try:
            # BUG FIX (Round 21): this used to return a fabricated string
            # literally reading "[Translation of 'X' to Spanish]" -- NOT a
            # real translation -- while claiming success with a fake
            # "detected_language" too. This is a materially worse kind of
            # fake than, say, the weather/stock placeholders elsewhere in
            # this audit: a user who doesn't speak the target language has
            # no way to notice the translation is fabricated nonsense,
            # whereas a wrong stock price is at least independently
            # checkable. Unlike web_search.py/information.py's fixes this
            # round, a generic web search snippet is not a safe substitute
            # here either -- scraped, unstructured text from a "translate X
            # to Y" query is not reliably an actual translation of the
            # input, so returning that as "the translation" would still be
            # presenting an unverifiable, possibly-wrong string as fact.
            # Honestly failing until a real translation API/model is wired
            # up is the correct behavior for a companion whose mandate
            # explicitly includes multilingual interaction done right, not
            # multilingual interaction that silently lies.
            return {
                "success": False,
                "error": (
                    "Translation is not available: no translation API is "
                    "configured in this build of Agent Guru."
                ),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to translate text: {e!s}",
            }
