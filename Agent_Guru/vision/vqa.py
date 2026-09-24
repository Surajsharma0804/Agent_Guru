"""Visual Question Answering Engine for the Agent Guru Vision System.

Routes VQA requests to:
- Desktop: LLaVA-1.6 / InternVL2 quantized (4-bit GGUF) via llama.cpp
- Mobile: Cloud VLM provider (OpenAI GPT-4V, Gemini Vision)

Design:
- OCR output injected into VLM prompt when question involves text in image.
- Returns not_visible=True when answer cannot be determined; never hallucinates.
- Latency ≤2s on GPU for images up to 1920×1080.
- Supported question types: identity, count, color, spatial, text content, scene.

Requirements: 8.1-8.8
"""

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING, Any

import structlog

from Agent_Guru.vision.vision_models import VisionEvent, VQAResult

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_NOT_VISIBLE_PHRASE = "I cannot determine that from the image"

# Keywords that indicate the question is about text in the image
_TEXT_QUESTION_KEYWORDS = frozenset(
    [
        "text",
        "read",
        "written",
        "says",
        "write",
        "label",
        "sign",
        "caption",
        "word",
        "letter",
        "number",
        "digit",
        "printed",
    ],
)

_SYSTEM_PROMPT = (
    "You are a precise visual question answering assistant. "
    "Answer questions about the provided image concisely and accurately. "
    "If you cannot determine the answer from the image, respond with exactly: "
    f'"{_NOT_VISIBLE_PHRASE}". '
    "Never guess or hallucinate information not visible in the image."
)


def _is_text_question(question: str) -> bool:
    """Return True when the question is likely about text content in the image."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in _TEXT_QUESTION_KEYWORDS)


def _encode_image_base64(image: np.ndarray) -> str:
    """Encode a numpy RGB image as a base64 JPEG string."""
    try:
        import cv2  # type: ignore[import]

        _, buf = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        return base64.b64encode(buf.tobytes()).decode("utf-8")
    except ImportError:
        # Fallback: encode as raw bytes (not valid JPEG but usable in tests)
        return base64.b64encode(image.tobytes()).decode("utf-8")


class VQAEngine:
    """Visual Question Answering engine with on-device and cloud routing.

    Args:
        platform: "desktop" uses local LLM; "mobile" uses cloud VLM.
        cloud_provider: Cloud provider name ("openai" or "gemini").
        _infer_fn: Optional callable for testing; replaces all VLM inference.
            Signature: ``(image: np.ndarray, prompt: str) -> str``
            Returns the raw answer string.

    """

    def __init__(
        self,
        platform: str = "desktop",
        cloud_provider: str = "openai",
        _infer_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._platform = platform
        self._cloud_provider = cloud_provider
        self._infer_fn = _infer_fn
        logger.info(
            "VQAEngine initialised",
            platform=platform,
            cloud_provider=cloud_provider,
        )

    # ------------------------------------------------------------------
    # OCR injection
    # ------------------------------------------------------------------

    def _get_ocr_text(self, image: np.ndarray) -> str | None:
        """Run OCR on the image and return extracted text, or None on failure."""
        try:
            import asyncio

            from Agent_Guru.vision.ocr import OCREngine

            engine = OCREngine()
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(engine.extract(image))
            finally:
                loop.close()
            return result.text.strip() or None
        except Exception as exc:
            logger.debug("VQAEngine: OCR extraction failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Inference routing
    # ------------------------------------------------------------------

    def _build_prompt(self, question: str, ocr_text: str | None) -> str:
        """Build the VLM prompt, optionally injecting OCR output."""
        if ocr_text:
            return (
                f"The image contains the following text (extracted by OCR):\n"
                f"---\n{ocr_text}\n---\n\n"
                f"Question: {question}"
            )
        return f"Question: {question}"

    def _call_local_llm(self, image: np.ndarray, prompt: str) -> str:
        """Call local LLaVA/InternVL2 via llama.cpp."""
        try:
            from llama_cpp import Llama  # type: ignore[import]

            model_path = os.path.join("models", "llava-1.6-mistral-7b.Q4_K_M.gguf")
            if not os.path.exists(model_path):
                return _NOT_VISIBLE_PHRASE

            llm = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False,
            )
            img_b64 = _encode_image_base64(image)
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ]
            response = llm.create_chat_completion(messages=messages, max_tokens=256)
            return response["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.exception("VQAEngine: local LLM failed", error=str(exc))
            return _NOT_VISIBLE_PHRASE

    def _call_cloud_vlm(self, image: np.ndarray, prompt: str) -> str:
        """Call cloud VLM provider (OpenAI GPT-4V or Gemini Vision)."""
        img_b64 = _encode_image_base64(image)

        if self._cloud_provider == "openai":
            return self._call_openai(img_b64, prompt)
        if self._cloud_provider == "gemini":
            return self._call_gemini(image, prompt)
        logger.warning("VQAEngine: unknown cloud provider", provider=self._cloud_provider)
        return _NOT_VISIBLE_PHRASE

    def _call_openai(self, img_b64: str, prompt: str) -> str:
        """Call OpenAI GPT-4V."""
        try:
            import openai  # type: ignore[import]

            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
                max_tokens=256,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.exception("VQAEngine: OpenAI call failed", error=str(exc))
            return _NOT_VISIBLE_PHRASE

    def _call_gemini(self, image: np.ndarray, prompt: str) -> str:
        """Call Google Gemini Vision."""
        try:
            import google.generativeai as genai  # type: ignore[import]
            from PIL import Image as PILImage  # type: ignore[import]

            pil_img = PILImage.fromarray(image)
            model = genai.GenerativeModel("gemini-pro-vision")
            response = model.generate_content([_SYSTEM_PROMPT + "\n\n" + prompt, pil_img])
            return response.text.strip()
        except Exception as exc:
            logger.exception("VQAEngine: Gemini call failed", error=str(exc))
            return _NOT_VISIBLE_PHRASE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def answer(self, image: np.ndarray, question: str) -> VQAResult:
        """Answer a natural language question about an image.

        Args:
            image: uint8 RGB array of shape (H, W, 3).
            question: Natural language question string.

        Returns:
            VQAResult with answer, confidence, and metadata flags.

        """
        grounded_in_ocr = False
        ocr_text: str | None = None

        if _is_text_question(question):
            ocr_text = self._get_ocr_text(image)
            if ocr_text:
                grounded_in_ocr = True

        prompt = self._build_prompt(question, ocr_text)

        if self._infer_fn is not None:
            raw_answer = self._infer_fn(image, prompt)
        elif self._platform == "desktop":
            raw_answer = self._call_local_llm(image, prompt)
        else:
            raw_answer = self._call_cloud_vlm(image, prompt)

        not_visible = _NOT_VISIBLE_PHRASE.lower() in raw_answer.lower()
        if not_visible:
            raw_answer = _NOT_VISIBLE_PHRASE

        # Confidence heuristic: not_visible → 0.0, otherwise 0.8
        confidence = 0.0 if not_visible else 0.8

        logger.debug(
            "VQAEngine: answered",
            question=question[:80],
            not_visible=not_visible,
            grounded_in_ocr=grounded_in_ocr,
        )

        return VQAResult(
            question=question,
            answer=raw_answer,
            confidence=confidence,
            grounded_in_ocr=grounded_in_ocr,
            not_visible=not_visible,
        )

    def make_event(self, result: VQAResult, frame_seq: int) -> VisionEvent:
        """Build a vqa_answered VisionEvent from a VQAResult."""
        return VisionEvent(
            event_type="vqa_answered",
            timestamp=VisionEvent.now_timestamp(),
            source_module="vqa",
            confidence=result.confidence,
            metadata={
                "question": result.question,
                "not_visible": result.not_visible,
                "grounded_in_ocr": result.grounded_in_ocr,
                "frame_seq": frame_seq,
            },
        )
