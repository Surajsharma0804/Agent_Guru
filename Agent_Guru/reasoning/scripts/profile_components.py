"""Profile individual reasoning components to identify bottlenecks.

This script profiles key components in isolation to understand their
performance characteristics.

Usage:
    python Agent_Guru/reasoning/profile_components.py

    # With py-spy for flame graphs:
    py-spy record -o component_profile.svg -- python Agent_Guru/reasoning/profile_components.py
"""

import cProfile
import io
import logging
import os
import pstats
import sys
import time

logger = logging.getLogger(__name__)

# Add parent directory to path so this script can be run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def profile_function(func, *args, **kwargs):
    """Profile a function and return statistics.

    Args:
        func: Function to profile
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Tuple of (result, stats_string, elapsed_time)

    """
    profiler = cProfile.Profile()

    start_time = time.perf_counter()
    profiler.enable()

    try:
        result = func(*args, **kwargs)
    except Exception as e:
        result = f"ERROR: {e}"
    profiler.disable()
    end_time = time.perf_counter()

    # Get stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats("cumulative")
    ps.print_stats(20)  # Top 20 functions

    return result, s.getvalue(), end_time - start_time


def profile_intent_detection() -> None:
    """Profile intent detection component."""
    try:
        from Agent_Guru.reasoning.intent.engine import IntentDetectionEngine
        from Agent_Guru.reasoning.models.conversation import ConversationState

        engine = IntentDetectionEngine()

        # Test inputs
        test_inputs = [
            "set a timer for 5 minutes",
            "what's the weather like today",
            "send a message to John",
            "play some music",
            "turn on the lights",
        ]

        total_time = 0
        for text in test_inputs:
            state = ConversationState(
                conversation_id="test",
                user_id="test_user",
                turns=[],
                entities={},
                created_at=time.time(),
                updated_at=time.time(),
            )

            start = time.perf_counter()
            try:
                engine.detect_intent(text, state)
                elapsed = time.perf_counter() - start
                total_time += elapsed
            except Exception:
                logger.exception("Operation failed")
        avg_time = total_time / len(test_inputs)

        if avg_time * 1000 < 200:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def profile_fast_router() -> None:
    """Profile fast intent router."""
    try:
        from Agent_Guru.reasoning.intent.fast_router import FastIntentRouter

        router = FastIntentRouter()

        # Test inputs that should hit fast path
        test_inputs = [
            "set timer 5 minutes",
            "weather",
            "play music",
            "lights on",
            "what time",
        ]

        total_time = 0
        hits = 0

        for text in test_inputs:
            start = time.perf_counter()
            result = router.match(text)
            elapsed = time.perf_counter() - start
            total_time += elapsed

            if result:
                hits += 1
            else:
                pass

        avg_time = total_time / len(test_inputs)
        hit_rate = hits / len(test_inputs) * 100

        if avg_time * 1000 < 50 and hit_rate > 80:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def profile_llm_reasoning() -> None:
    """Profile LLM reasoning component."""
    try:
        from Agent_Guru.reasoning.llm.reasoning import LLMReasoningCore
        from Agent_Guru.reasoning.models.conversation import ConversationState
        from Agent_Guru.reasoning.models.intent import Intent

        core = LLMReasoningCore()

        # Test intent
        intent = Intent(
            intent_type="send_message",
            entities={"recipient": "John", "message": "I'll be late"},
            confidence=0.9,
            requires_reasoning=True,
            original_input="send a message to John saying I'll be late",
        )

        state = ConversationState(
            conversation_id="test",
            user_id="test_user",
            turns=[],
            entities={},
            created_at=time.time(),
            updated_at=time.time(),
        )

        start = time.perf_counter()
        try:
            core.reason(intent, state)
            elapsed = time.perf_counter() - start
        except Exception:
            elapsed = time.perf_counter() - start
        if elapsed * 1000 < 400:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def profile_tool_selection() -> None:
    """Profile tool selection component."""
    try:
        from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskType
        from Agent_Guru.reasoning.tools.selector import ToolSelector

        selector = ToolSelector()

        # Test task
        task = Task(
            goal="Set a timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        start = time.perf_counter()
        try:
            selector.select_tool(task)
            elapsed = time.perf_counter() - start
        except Exception:
            elapsed = time.perf_counter() - start
        if elapsed * 1000 < 50:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def profile_safety_gate() -> None:
    """Profile safety gate component."""
    try:
        from Agent_Guru.reasoning.safety.gate import SafetyGate
        from Agent_Guru.reasoning.tools.base import ParameterType, Tool, ToolParameter

        gate = SafetyGate()

        # Test tool
        tool = Tool(
            tool_id="send_message",
            name="Send Message",
            description="Send a text message",
            parameters=[
                ToolParameter(
                    name="recipient",
                    type=ParameterType.STRING,
                    required=True,
                    description="Message recipient",
                ),
                ToolParameter(
                    name="message",
                    type=ParameterType.STRING,
                    required=True,
                    description="Message content",
                ),
            ],
            is_sensitive=True,
            estimated_latency=0.5,
        )

        parameters = {"recipient": "John", "message": "Hello"}

        start = time.perf_counter()
        try:
            gate.validate_action(tool, parameters, "test_user")
            elapsed = time.perf_counter() - start
        except Exception:
            elapsed = time.perf_counter() - start
        if elapsed * 1000 < 50:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def profile_response_generation() -> None:
    """Profile response generation component."""
    try:
        from Agent_Guru.reasoning.models.intent import InputSource, Intent
        from Agent_Guru.reasoning.models.result import ExecutionResult
        from Agent_Guru.reasoning.response.template_generator import TemplateResponseGenerator

        generator = TemplateResponseGenerator()

        # Test result
        result = ExecutionResult(
            success=True,
            result_data={"timer_id": "123", "duration": "5 minutes"},
            error=None,
            execution_time=0.1,
            action_id="test_action",
        )

        intent = Intent(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.9,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
        )

        start = time.perf_counter()
        try:
            generator.generate_response(result, intent, InputSource.TEXT, {})
            elapsed = time.perf_counter() - start
        except Exception:
            elapsed = time.perf_counter() - start
        if elapsed * 1000 < 150:
            pass
        else:
            pass

    except Exception:
        logger.exception("Operation failed")


def main() -> None:
    """Main profiling function."""
    # Profile each component
    profile_fast_router()
    profile_intent_detection()
    profile_llm_reasoning()
    profile_tool_selection()
    profile_safety_gate()
    profile_response_generation()


if __name__ == "__main__":
    main()
