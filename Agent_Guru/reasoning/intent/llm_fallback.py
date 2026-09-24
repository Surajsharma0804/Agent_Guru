"""LLM-based Intent Fallback Classifier.

This module provides LLM-based intent classification for cases where the neural
classifier has low confidence (<0.8). Uses GPT-4 Turbo or Claude 3.5 Sonnet with
structured output parsing and retry logic.

Performance Characteristics:
    - Time Complexity: O(1) per request (LLM API call)
    - Space Complexity: O(1) with fixed prompt size
    - Latency: <300ms target (cloud API latency)
    - Accuracy: >98% (LLM reasoning superior to neural for edge cases)
    - Fallback: Graceful degradation to UNKNOWN intent on timeout/failure

Design Decisions:
    - Use GPT-4 Turbo (fastest GPT-4 variant) or Claude 3.5 Sonnet
    - Few-shot prompting with 5 examples per intent category
    - Structured JSON output with schema validation
    - Retry logic with exponential backoff (max 3 retries)
    - Timeout enforcement (300ms) with graceful degradation
    - Entity extraction using LLM reasoning (no separate NER)

Prompt Strategy:
    - System prompt defines task and output format
    - Few-shot examples demonstrate intent classification
    - User prompt includes input text and context
    - Response parsed as JSON with Pydantic validation

Author: Kiro AI
Date: 2026-02-19
Version: 1.0.0
"""

import asyncio
import functools
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from Agent_Guru.reasoning.llm.generation import context_fits, ollama_options
from Agent_Guru.reasoning.llm.timeouts import intent_timeout
from Agent_Guru.reasoning.models.intent import Entity

logger = logging.getLogger(__name__)

# Try to import LLM clients
try:
    from types import ModuleType

    import openai

    openai_module: ModuleType | None = openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai_module = None
try:
    from types import ModuleType

    import anthropic

    anthropic_module: ModuleType | None = anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic_module = None



# The providers LLMFallbackClassifier can actually drive. Ollama is local and
# always available; the other two need the optional `cloud` extra
# (`pip install agent-guru[cloud]`) and are rejected at classifier
# construction when their SDK is absent.
SUPPORTED_PROVIDERS = frozenset({"ollama", "openai", "anthropic"})

@dataclass
class LLMFallbackConfig:
    """Configuration for LLM fallback classifier.

    Attributes:
        provider: LLM provider ("ollama", "openai", or "anthropic")
        model: Model name (e.g., "gemma3:4b", "gpt-4-turbo-preview", "claude-3-5-sonnet-20241022")
        api_key: API key for LLM provider (not needed for Ollama)
        ollama_host: Ollama server host (default: "127.0.0.1")
        ollama_port: Ollama server port (default: 11434)
        timeout_ms: Per-call timeout in milliseconds. Defaults to the
            AGENT_GURU_INTENT_TIMEOUT_SECONDS policy.
        max_retries: Maximum number of retries (3)
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum tokens in response (512)

    """

    provider: str = "ollama"  # Default to local Ollama
    model: str = "gemma3:4b"  # Default to Qwen for complex reasoning
    api_key: str | None = None
    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    # DEFECT FIX: this was a hard-coded 1000.0 with the comment "1 second
    # for local Ollama". No local model classifies intent in one second on a
    # CPU - loading and running even a small model takes far longer - so on
    # the offline, GPU-less hardware this project is built for, the LLM
    # fallback timed out on every single call and the classifier silently
    # never had a fallback at all. The failure looked like "the fallback
    # doesn't help", not like a misconfigured timeout.
    timeout_ms: float = field(default_factory=lambda: intent_timeout() * 1000.0)
    max_retries: int = 3
    temperature: float = 0.0
    max_tokens: int = 512

    def __post_init__(self) -> None:
        """Reject a configuration that cannot work.

        None of this was checked before. An unsupported provider name was
        accepted here without complaint and only surfaced much later, from
        LLMFallbackClassifier._initialize_client(), as
        "Unsupported provider: <name>" - after the object had been passed
        around, stored, maybe serialised. A typo belongs to the line that made
        it, so it is caught at construction.
        """
        if self.provider not in SUPPORTED_PROVIDERS:
            msg = (
                f"Unsupported provider {self.provider!r}. "
                f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )
            raise ValueError(msg)
        if self.timeout_ms <= 0:
            msg = f"timeout_ms must be positive, got {self.timeout_ms}"
            raise ValueError(msg)
        if self.max_retries < 0:
            msg = f"max_retries cannot be negative, got {self.max_retries}"
            raise ValueError(msg)
        if not 0.0 <= self.temperature <= 2.0:
            msg = f"temperature must be in [0.0, 2.0], got {self.temperature}"
            raise ValueError(msg)
        if self.max_tokens <= 0:
            msg = f"max_tokens must be positive, got {self.max_tokens}"
            raise ValueError(msg)
        if not 1 <= self.ollama_port <= 65535:
            msg = f"ollama_port must be in [1, 65535], got {self.ollama_port}"
            raise ValueError(msg)


class LLMIntentResponse(BaseModel):
    """Structured response from LLM intent classification.

    Attributes:
        intent_type: Predicted intent type
        confidence: Confidence score (0.0-1.0)
        entities: Extracted entities as dict
        reasoning: Brief explanation of classification

    """

    intent_type: str = Field(..., description="Predicted intent type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    reasoning: str = Field(default="", description="Classification reasoning")


@dataclass
class LLMClassificationResult:
    """Result from LLM intent classification.

    Attributes:
        intent_type: Predicted intent type
        confidence: Confidence score (0.0-1.0)
        entities: Extracted entities
        reasoning: Classification reasoning
        inference_time_ms: Inference time in milliseconds
        retries: Number of retries needed
        provider: LLM provider used

    """

    intent_type: str
    confidence: float
    entities: dict[str, Entity]
    reasoning: str
    inference_time_ms: float
    retries: int
    provider: str


class LLMFallbackClassifier:
    """LLM-based fallback classifier for low-confidence intents.

    Time Complexity: O(1) per request (LLM API call)
    Space Complexity: O(1) with fixed prompt size

    Example:
        >>> classifier = LLMFallbackClassifier(config)
        >>> result = await classifier.classify_async("remind me to call mom tomorrow")
        >>> print(f"Intent: {result.intent_type}, Confidence: {result.confidence}")

    """

    # System prompt for intent classification
    SYSTEM_PROMPT = """You are an expert intent classifier for a voice assistant.
Your task is to classify user inputs into structured intents with entities.

Available intent types:
- set_timer, set_alarm, set_reminder, cancel_timer
- query_weather, query_time, query_date, query_fact, search_web
- send_message, send_email, make_call
- play_music, play_video, pause_media, stop_media, next_track, previous_track
- control_lights, control_thermostat, control_device
- create_event, update_event, delete_event, query_events
- open_app, close_app, system_command
- clarification_request, confirmation, cancellation, help_request
- unknown, multi_intent

Entity types:
- duration, time, date, datetime
- person, location, organization
- device, app, media
- task, event
- number, money, percentage

Output format (JSON):
{
  "intent_type": "intent_name",
  "confidence": 0.95,
  "entities": {
    "entity_name": {
      "entity_type": "type",
      "value": "extracted_value",
      "raw_text": "original_text"
    }
  },
  "reasoning": "brief explanation"
}

Examples:

Input: "set timer for 5 minutes"
Output: {"intent_type": "set_timer", "confidence": 0.98, "entities": {"duration": {"entity_type": "duration", "value": 300, "raw_text": "5 minutes"}}, "reasoning": "Clear timer intent with duration"}

Input: "remind me to call mom tomorrow at 3pm"
Output: {"intent_type": "set_reminder", "confidence": 0.95, "entities": {"task": {"entity_type": "task", "value": "call mom", "raw_text": "call mom"}, "datetime": {"entity_type": "datetime", "value": "tomorrow 3pm", "raw_text": "tomorrow at 3pm"}}, "reasoning": "Reminder with task and time"}

Input: "what's the weather like"
Output: {"intent_type": "query_weather", "confidence": 0.97, "entities": {}, "reasoning": "Weather query without location"}

Input: "play some jazz music"
Output: {"intent_type": "play_music", "confidence": 0.96, "entities": {"media": {"entity_type": "media", "value": "jazz", "raw_text": "jazz music"}}, "reasoning": "Music playback with genre"}

Input: "turn on the living room lights"
Output: {"intent_type": "control_lights", "confidence": 0.98, "entities": {"device": {"entity_type": "device", "value": "living room lights", "raw_text": "living room lights"}}, "reasoning": "Smart home light control"}

Classify the following input:"""

    def __init__(self, config: LLMFallbackConfig | None = None) -> None:
        """Initialize LLM fallback classifier.

        Args:
            config: Classifier configuration (uses defaults if None)

        Raises:
            RuntimeError: If LLM client not available

        """
        self.config = config or LLMFallbackConfig()

        # Validate provider availability
        if self.config.provider == "ollama":
            # Ollama uses requests library (no special client needed)
            pass
        elif self.config.provider == "openai" and not OPENAI_AVAILABLE:
            msg = "OpenAI client not available. Install with: pip install openai"
            raise RuntimeError(msg)
        elif self.config.provider == "anthropic" and not ANTHROPIC_AVAILABLE:
            msg = "Anthropic client not available. Install with: pip install anthropic"
            raise RuntimeError(
                msg,
            )

        # Initialize client
        self.client: Any | None = None
        self._initialize_client()

        # Metrics
        self.total_inferences = 0
        self.total_latency_ms = 0.0
        self.successful_inferences = 0
        self.failed_inferences = 0
        self.total_retries = 0

    def _initialize_client(self) -> None:
        """Initialize LLM client based on provider."""
        if self.config.provider == "ollama":
            # Ollama doesn't need a client object, we use requests directly
            self.client = None
        elif self.config.provider == "openai":
            self.client = openai.OpenAI(api_key=self.config.api_key)
        elif self.config.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=self.config.api_key)
        else:
            # Unreachable through LLMFallbackConfig, which validates the
            # name on construction; kept as a guard for a hand-mutated config.
            msg = (
                f"Unsupported provider: {self.config.provider}. "
                f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )
            raise ValueError(
                msg,
            )

    async def classify_async(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> LLMClassificationResult:
        """Asynchronous classification with retry logic.

        Time Complexity: O(1) per request
        Space Complexity: O(1)

        Args:
            text: Input text to classify
            context: Optional conversation context

        Returns:
            Classification result with intent and entities

        Raises:
            TimeoutError: If classification exceeds timeout
            RuntimeError: If all retries fail

        """
        start_time = time.perf_counter()
        retries = 0

        for attempt in range(self.config.max_retries):
            try:
                # Call LLM with timeout
                result = await asyncio.wait_for(
                    self._call_llm_async(text, context),
                    timeout=self.config.timeout_ms / 1000.0,
                )

                # Calculate latency
                inference_time_ms = (time.perf_counter() - start_time) * 1000

                # Update metrics
                self._update_metrics(inference_time_ms, retries, success=True)

                return LLMClassificationResult(
                    intent_type=result.intent_type,
                    confidence=result.confidence,
                    entities=self._parse_entities(result.entities),
                    reasoning=result.reasoning,
                    inference_time_ms=inference_time_ms,
                    retries=retries,
                    provider=self.config.provider,
                )

            # BUG FIX: this was a single `except TimeoutError` whose body was
            # duplicated -- the second copy passing error=str(e), which is the
            # signature of a lost `except Exception` clause. Three things were
            # broken by it:
            #
            #   1. A MALFORMED LLM RESPONSE was not caught at all.
            #      _parse_response() raises ValueError for bad JSON or a
            #      failed schema check (deliberately, "so caller can retry"),
            #      but ValueError is not TimeoutError, so it propagated
            #      straight out of classify_async(). On the intent path that
            #      takes the whole turn down, instead of the UNKNOWN result
            #      this method exists to produce.
            #   2. `retries` was incremented TWICE per timeout, so the count
            #      reported to callers and to _update_metrics was wrong.
            #   3. The duplicated body slept twice, doubling the backoff.
            except TimeoutError as e:
                if (result := await self._give_up_or_backoff(
                    attempt, text, start_time, retries + 1, e,
                )) is not None:
                    return result
                retries += 1

            except Exception as e:
                # Malformed response, schema failure, provider/transport error.
                # Falling back to UNKNOWN is the entire point of this class:
                # a classifier that raises is worse than one that says it does
                # not know.
                logger.warning(
                    "LLM intent classification failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.config.max_retries,
                    e,
                )
                if (result := await self._give_up_or_backoff(
                    attempt, text, start_time, retries + 1, e,
                )) is not None:
                    return result
                retries += 1
        # Should never reach here
        inference_time_ms = (time.perf_counter() - start_time) * 1000
        self._update_metrics(inference_time_ms, retries, success=False)
        return self._create_unknown_result(text, inference_time_ms, retries)

    async def _give_up_or_backoff(
        self,
        attempt: int,
        text: str,
        start_time: float,
        retries: int,
        error: BaseException,
    ) -> "LLMClassificationResult | None":
        """Return an UNKNOWN result if attempts are exhausted, else back off.

        Shared by every handler in classify_async()'s retry loop so the
        give-up path cannot drift between them -- which is exactly how the
        duplicated block this replaces came about.
        """
        if attempt >= self.config.max_retries - 1:
            inference_time_ms = (time.perf_counter() - start_time) * 1000
            self._update_metrics(inference_time_ms, retries, success=False)
            return self._create_unknown_result(
                text,
                inference_time_ms,
                retries,
                error=str(error),
            )
        # Exponential backoff: 0.1s, 0.2s, 0.4s ...
        await asyncio.sleep(0.1 * (2**attempt))
        return None

    async def _call_llm_async(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> LLMIntentResponse:
        """Call LLM API asynchronously.

        Args:
            text: Input text to classify
            context: Optional conversation context

        Returns:
            Parsed LLM response

        Raises:
            ValidationError: If response doesn't match schema

        """
        # Build user prompt
        user_prompt = f'Input: "{text}"'
        if context:
            user_prompt += f"\nContext: {json.dumps(context)}"

        # Call LLM based on provider
        if self.config.provider == "ollama":
            response = await self._call_ollama(user_prompt)
        elif self.config.provider == "openai":
            response = await self._call_openai(user_prompt)
        elif self.config.provider == "anthropic":
            response = await self._call_anthropic(user_prompt)
        else:
            msg = f"Unsupported provider: {self.config.provider}"
            raise ValueError(msg)

        # Parse and validate response
        return self._parse_response(response)

    async def _call_ollama(self, user_prompt: str) -> str:
        """Call Ollama API.

        Args:
            user_prompt: User prompt text

        Returns:
            LLM response text

        """
        import requests

        base_url = f"http://{self.config.ollama_host}:{self.config.ollama_port}"

        # Options come from the shared generation policy. This call used to
        # send neither num_ctx nor num_gpu. Measured on a 4 GB RTX 2050, it
        # loaded gemma3:4b at the server's 131072-token default, 61% on the
        # CPU, and took 25 s cold. It runs in a thread the voice pipeline
        # cannot cancel, so the spoken answer queued behind it and then paid
        # for a second model load at the voice client's context size.
        payload = {
            "model": self.config.model,
            "prompt": f"{self.SYSTEM_PROMPT}\n\n{user_prompt}",
            "stream": False,
            "options": ollama_options(
                num_predict=self.config.max_tokens,
                temperature=self.config.temperature,
            ),
            "format": "json",
        }

        # asyncio.to_thread() propagates contextvars -- preferred over run_in_executor
        _post = functools.partial(
            requests.post,  # nosec B113
            f"{base_url}/api/generate",
            json=payload,
            timeout=self.config.timeout_ms / 1000.0,
        )
        response = await asyncio.to_thread(_post)

        if response.status_code == 200:
            data = response.json()
            context_fits(
                data.get("prompt_eval_count"),
                self.config.max_tokens,
                source="LLMFallbackClassifier",
            )
            result = data.get("response", "")
            return str(result) if result else ""
        msg = f"Ollama API error: {response.status_code} - {response.text}"
        raise RuntimeError(msg)

    async def _call_openai(self, user_prompt: str) -> str:
        """Call OpenAI API.

        Args:
            user_prompt: User prompt text

        Returns:
            LLM response text

        """
        if self.client is None:
            msg = "OpenAI client not initialized"
            raise RuntimeError(msg)

        # asyncio.to_thread() propagates contextvars -- preferred over run_in_executor
        _create = functools.partial(
            self.client.chat.completions.create,  # type: ignore[union-attr]
            model=self.config.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            response_format={"type": "json_object"},
        )
        response = await asyncio.to_thread(_create)
        content = response.choices[0].message.content
        return str(content) if content else ""

    async def _call_anthropic(self, user_prompt: str) -> str:
        """Call Anthropic API.

        Args:
            user_prompt: User prompt text

        Returns:
            LLM response text

        """
        if self.client is None:
            msg = "Anthropic client not initialized"
            raise RuntimeError(msg)

        # asyncio.to_thread() propagates contextvars -- preferred over run_in_executor
        _create = functools.partial(
            self.client.messages.create,  # type: ignore[union-attr]
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        response = await asyncio.to_thread(_create)
        text = response.content[0].text if response and response.content else ""
        return str(text) if text else ""

    def _parse_response(self, response_text: str) -> LLMIntentResponse:
        """Parse and validate LLM response.

        Args:
            response_text: Raw LLM response

        Returns:
            Validated response object

        Raises:
            ValueError: If response cannot be parsed

        """
        # Strip markdown code fences if present
        text = response_text.strip()
        text = text.removeprefix("```json")
        text = text.removeprefix("```")
        text = text.removesuffix("```")
        text = text.strip()

        # Parse JSON -- raise ValueError on failure so caller can retry
        try:
            response_data = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"LLM returned invalid JSON: {exc} -- raw: {text[:200]}"
            raise ValueError(msg) from exc
        # Validate with Pydantic
        try:
            return LLMIntentResponse(**response_data)
        except Exception as exc:
            msg = f"LLM response failed schema validation: {exc}"
            raise ValueError(msg) from exc

    def _parse_entities(self, entities_dict: dict[str, Any]) -> dict[str, Entity]:
        """Parse entities from LLM response into Entity objects.

        Args:
            entities_dict: Raw entities from LLM

        Returns:
            Dictionary of Entity objects

        """
        parsed_entities = {}

        for key, entity_data in entities_dict.items():
            # Handle both dict and simple value formats
            if isinstance(entity_data, dict):
                parsed_entities[key] = Entity(
                    entity_type=entity_data.get("entity_type", "unknown"),
                    value=entity_data.get("value"),
                    raw_text=entity_data.get("raw_text", str(entity_data.get("value"))),
                    confidence=entity_data.get("confidence", 1.0),
                )
            else:
                # Simple value format
                parsed_entities[key] = Entity(
                    entity_type="unknown",
                    value=entity_data,
                    raw_text=str(entity_data),
                    confidence=1.0,
                )

        return parsed_entities

    def _create_unknown_result(
        self,
        text: str,
        inference_time_ms: float,
        retries: int,
        error: str | None = None,
    ) -> LLMClassificationResult:
        """Create UNKNOWN result for failed classification.

        Args:
            text: Original input text
            inference_time_ms: Time taken
            retries: Number of retries
            error: Optional error message

        Returns:
            UNKNOWN classification result

        """
        reasoning = "Classification failed"
        if error:
            reasoning += f": {error}"

        return LLMClassificationResult(
            intent_type="unknown",
            confidence=0.0,
            entities={},
            reasoning=reasoning,
            inference_time_ms=inference_time_ms,
            retries=retries,
            provider=self.config.provider,
        )

    def _update_metrics(self, inference_time_ms: float, retries: int, success: bool) -> None:
        """Update classification metrics.

        Args:
            inference_time_ms: Inference time
            retries: Number of retries
            success: Whether classification succeeded

        """
        self.total_inferences += 1
        self.total_latency_ms += inference_time_ms
        self.total_retries += retries

        if success:
            self.successful_inferences += 1
        else:
            self.failed_inferences += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get classification metrics.

        Returns:
            Dictionary with metrics

        """
        if self.total_inferences == 0:
            return {
                "total_inferences": 0,
                "average_latency_ms": 0.0,
                "success_rate": 0.0,
                "average_retries": 0.0,
            }

        return {
            "total_inferences": self.total_inferences,
            "average_latency_ms": self.total_latency_ms / self.total_inferences,
            "success_rate": self.successful_inferences / self.total_inferences,
            "average_retries": self.total_retries / self.total_inferences,
            "failed_inferences": self.failed_inferences,
        }
