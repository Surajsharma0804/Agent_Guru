"""Visual Question Answering Engine for the Agent Guru Vision System.

Routes VQA requests to:
- Desktop: the local Ollama model the assistant already runs (gemma4, whose
  weights include a vision tower), with the image attached to the request.
- Mobile: a cloud VLM (OpenAI or Gemini), if configured.

The desktop path used to load llava-1.6-mistral-7b through llama.cpp on every
question: a 7B model read from disk per call, which cannot share a 4 GB GPU
with gemma4, built without the CLIP projector llama.cpp needs to see an image
at all, from a model file and package that were not installed. It answered
"I cannot determine that from the image" to everything. It now asks the model
Ollama keeps loaded, so there is no second model and no per-question load,
and it uses the shared Ollama settings (model name, think flag, context and
GPU options) so the request cannot make Ollama reload the model.

Design:
- OCR output injected into the prompt when the question is about text.
- not_visible=True when the model says it cannot tell; error is set instead
  when no model answered, so a failure is not passed off as an unclear image.
- Every call is bounded: the HTTP request by its own timeout, and the await by
  asyncio.wait_for, so a stalled model cannot hold the caller.

Requirements: 8.1-8.8
"""

from __future__ import annotations

import asyncio
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

#: Gemini model for the mobile cloud path. gemini-pro-vision, the previous
#: hard-coded name, was retired by Google; override with
#: AGENT_GURU_VQA_GEMINI_MODEL when this one is.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
#: OpenAI model for the mobile cloud path; override with AGENT_GURU_VQA_OPENAI_MODEL.
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _is_text_question(question: str) -> bool:
    """Return True when the question is likely about text content in the image."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in _TEXT_QUESTION_KEYWORDS)


#: Longest side, in pixels, of an image sent to a model. The vision towers of
#: the Gemma models served here work at 896 px. A full 3840x2160 screenshot
#: sent as it was crashed Ollama's model runner on a 4 GB GPU, and then the
#: Ollama server, so images are scaled down before encoding.
MAX_IMAGE_SIDE = 896


def _downscale(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= MAX_IMAGE_SIDE:
        return image
    scale = MAX_IMAGE_SIDE / longest
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    try:
        import cv2  # type: ignore[import]

        return cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    except ImportError:
        import numpy as np
        from PIL import Image  # type: ignore[import]

        return np.asarray(Image.fromarray(image).resize(size, Image.Resampling.LANCZOS))


def _encode_image_base64(image: np.ndarray) -> str:
    """Encode an RGB image as base64 JPEG, scaled to MAX_IMAGE_SIDE at most.

    The fallback used to base64 the raw pixel buffer, which is not an image
    format any model accepts, so a missing cv2 produced requests that could
    only fail. Without cv2 this now uses Pillow, and without either it raises.
    """
    image = _downscale(image)
    try:
        import cv2  # type: ignore[import]
    except ImportError:
        import io

        from PIL import Image  # type: ignore[import]

        out = io.BytesIO()
        Image.fromarray(image).convert("RGB").save(out, format="JPEG")
        return base64.b64encode(out.getvalue()).decode("utf-8")

    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        msg = "cv2 could not encode the image as JPEG"
        raise ValueError(msg)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


class VQAEngine:
    """Visual Question Answering engine with on-device and cloud routing.

    Args:
        platform: "desktop" asks the local Ollama model; "mobile" a cloud VLM.
        cloud_provider: Cloud provider name ("openai" or "gemini").
        _infer_fn: Optional callable for testing; replaces all VLM inference.
            Signature: ``(image: np.ndarray, prompt: str) -> str``
            Returns the raw answer string.
        timeout_s: Seconds one answer may take. Defaults to the shared
            OLLAMA_TIMEOUT_SECONDS policy.
        ollama_url: Base URL of the Ollama server.

    """

    def __init__(
        self,
        platform: str = "desktop",
        cloud_provider: str = "openai",
        _infer_fn: Callable[..., Any] | None = None,
        *,
        timeout_s: float | None = None,
        ollama_url: str = "http://127.0.0.1:11434",
    ) -> None:
        from Agent_Guru.reasoning.llm.timeouts import generate_timeout

        self._platform = platform
        self._cloud_provider = cloud_provider
        self._infer_fn = _infer_fn
        self._timeout_s = timeout_s if timeout_s is not None else generate_timeout()
        self._ollama_url = ollama_url.rstrip("/")
        # Built once and reused; it used to be constructed on every question.
        self._openai_client: Any = None
        logger.info(
            "VQAEngine initialised",
            platform=platform,
            cloud_provider=cloud_provider,
        )

    # ------------------------------------------------------------------
    # OCR injection
    # ------------------------------------------------------------------

    async def _get_ocr_text(self, image: np.ndarray) -> str | None:
        """Run OCR on the image and return extracted text, or None on failure.

        This used to create a new event loop and call run_until_complete on it
        from inside answer(), which is a coroutine: Python refuses to run a
        loop while another runs on the same thread, the error was swallowed,
        and OCR grounding never happened. It is awaited now.
        """
        try:
            from Agent_Guru.vision.ocr import OCREngine

            result = await OCREngine().extract(image)
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
        """Ask the Ollama model the assistant already runs, with the image attached.

        Raises on any failure; answer() turns that into VQAResult.error.
        """
        import requests

        from Agent_Guru.reasoning.llm.generation import (
            OLLAMA_THINK,
            ollama_model,
            ollama_options,
        )
        from Agent_Guru.reasoning.llm.timeouts import connect_timeout

        # The conversation model by default, so a visual question does not
        # make Ollama swap models (only one fits a 4 GB GPU). Measured with
        # Ollama 0.34.4 on the development laptop, gemma4's vision answered
        # 4 of 4 concrete questions wrongly (black text read as "White", a red
        # circle and blue square as "abstract shapes in black, white, and
        # gray") although the image reached it, while gemma3:4b answered all
        # 4 correctly through this same code, at the cost of a model swap
        # (11.7 s for the first question). AGENT_GURU_VQA_MODEL picks the
        # vision model.
        vqa_model = os.environ.get("AGENT_GURU_VQA_MODEL", "").strip() or ollama_model()
        payload = {
            "model": vqa_model,
            "system": _SYSTEM_PROMPT,
            "prompt": prompt,
            "images": [_encode_image_base64(image)],
            "stream": False,
            # gemma4 spends its whole budget reasoning and returns "" without this.
            "think": OLLAMA_THINK,
            "options": ollama_options(num_predict=256, temperature=0.0),
        }
        response = requests.post(
            f"{self._ollama_url}/api/generate",
            json=payload,
            timeout=(connect_timeout(), self._timeout_s),
        )
        if response.status_code != 200:
            msg = f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
            raise RuntimeError(msg)
        return str(response.json().get("response", "")).strip()

    def _call_cloud_vlm(self, image: np.ndarray, prompt: str) -> str:
        """Call the configured cloud VLM provider (OpenAI or Gemini)."""
        if self._cloud_provider == "openai":
            return self._call_openai(_encode_image_base64(image), prompt)
        if self._cloud_provider == "gemini":
            return self._call_gemini(image, prompt)
        msg = f"Unknown cloud VQA provider {self._cloud_provider!r}"
        raise ValueError(msg)

    def _call_openai(self, img_b64: str, prompt: str) -> str:
        """Call an OpenAI vision model."""
        import openai  # type: ignore[import]

        if self._openai_client is None:
            # The SDK's own defaults are a 600 s timeout and 2 retries.
            self._openai_client = openai.OpenAI(timeout=self._timeout_s, max_retries=0)
        response = self._openai_client.chat.completions.create(
            model=os.environ.get("AGENT_GURU_VQA_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
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
        return (response.choices[0].message.content or "").strip()

    def _call_gemini(self, image: np.ndarray, prompt: str) -> str:
        """Call a Gemini vision model."""
        import google.generativeai as genai  # type: ignore[import]
        from PIL import Image as PILImage  # type: ignore[import]

        model = genai.GenerativeModel(
            os.environ.get("AGENT_GURU_VQA_GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        )
        response = model.generate_content(
            [_SYSTEM_PROMPT + "\n\n" + prompt, PILImage.fromarray(image)],
            request_options={"timeout": self._timeout_s},
        )
        return response.text.strip()

    def _infer(self, image: np.ndarray, prompt: str) -> str:
        if self._infer_fn is not None:
            return str(self._infer_fn(image, prompt))
        if self._platform == "desktop":
            return self._call_local_llm(image, prompt)
        return self._call_cloud_vlm(image, prompt)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def answer(self, image: np.ndarray, question: str) -> VQAResult:
        """Answer a natural language question about an image.

        The model call runs in a worker thread so the event loop keeps running
        (it used to block the loop for the whole inference), and is bounded by
        timeout_s.

        Args:
            image: uint8 RGB array of shape (H, W, 3).
            question: Natural language question string.

        Returns:
            VQAResult with answer, confidence, and metadata flags; error is set
            when no model could answer.

        """
        grounded_in_ocr = False
        ocr_text: str | None = None

        if _is_text_question(question):
            ocr_text = await self._get_ocr_text(image)
            if ocr_text:
                grounded_in_ocr = True

        prompt = self._build_prompt(question, ocr_text)

        try:
            # The HTTP request carries its own timeout, so the thread ends soon
            # after; the margin lets that timeout, not this one, report first.
            raw_answer = await asyncio.wait_for(
                asyncio.to_thread(self._infer, image, prompt),
                timeout=self._timeout_s + 5.0,
            )
        except Exception as exc:
            reason = "timed out" if isinstance(exc, TimeoutError) else f"{type(exc).__name__}: {exc}"
            logger.warning("VQAEngine: no answer", platform=self._platform, error=reason)
            return VQAResult(
                question=question,
                answer="I could not analyse the image.",
                confidence=0.0,
                grounded_in_ocr=grounded_in_ocr,
                not_visible=False,
                error=reason,
            )

        not_visible = not raw_answer or _NOT_VISIBLE_PHRASE.lower() in raw_answer.lower()
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
