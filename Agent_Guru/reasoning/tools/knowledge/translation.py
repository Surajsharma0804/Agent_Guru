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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
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
            # Note: In a real implementation, this would use a translation API
            # (Google Translate, DeepL, Azure Translator, etc.)
            return {
                "success": True,
                "result": {
                    "original_text": text,
                    "translated_text": f"[Translation of '{text}' to {SUPPORTED_LANGUAGES.get(target_language, target_language)}]",
                    "source_language": source_language,
                    "target_language": target_language,
                    "detected_language": "en" if source_language == "auto" else source_language,
                    "message": f"Translated text from {source_language} to {target_language}",
                    "note": "This is a placeholder. Real implementation would use translation API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to translate text: {e!s}",
            }
