"""
Profile individual reasoning components to identify bottlenecks.

This script profiles key components in isolation to understand their
performance characteristics.

Usage:
    python Agent_Guru/reasoning/profile_components.py
    
    # With py-spy for flame graphs:
    py-spy record -o component_profile.svg -- python Agent_Guru/reasoning/profile_components.py
"""

import cProfile
import pstats
import io
import time
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def profile_function(func, *args, **kwargs):
    """
    Profile a function and return statistics.
    
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
    ps.sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    return result, s.getvalue(), end_time - start_time


def profile_intent_detection():
    """Profile intent detection component."""
    print("\n" + "=" * 80)
    print("PROFILING: Intent Detection")
    print("=" * 80)
    
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
                updated_at=time.time()
            )
            
            start = time.perf_counter()
            try:
                result = engine.detect_intent(text, state)
                elapsed = time.perf_counter() - start
                total_time += elapsed
                print(f"  {elapsed*1000:6.1f}ms - {text}")
            except Exception as e:
                print(f"  ERROR - {text}: {e}")
        
        avg_time = total_time / len(test_inputs)
        print(f"\nAverage: {avg_time*1000:.1f}ms")
        print(f"Target: <200ms (Fast path: <50ms)")
        
        if avg_time * 1000 < 200:
            print("✓ PASS")
        else:
            print("✗ FAIL - Exceeds target")
            
    except Exception as e:
        print(f"✗ Could not profile intent detection: {e}")


def profile_fast_router():
    """Profile fast intent router."""
    print("\n" + "=" * 80)
    print("PROFILING: Fast Intent Router")
    print("=" * 80)
    
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
                print(f"  {elapsed*1000:6.1f}ms - HIT  - {text}")
            else:
                print(f"  {elapsed*1000:6.1f}ms - MISS - {text}")
        
        avg_time = total_time / len(test_inputs)
        hit_rate = hits / len(test_inputs) * 100
        
        print(f"\nAverage: {avg_time*1000:.1f}ms")
        print(f"Hit rate: {hit_rate:.0f}%")
        print(f"Target: <50ms, >80% hit rate")
        
        if avg_time * 1000 < 50 and hit_rate > 80:
            print("✓ PASS")
        else:
            print("✗ FAIL - Does not meet targets")
            
    except Exception as e:
        print(f"✗ Could not profile fast router: {e}")


def profile_llm_reasoning():
    """Profile LLM reasoning component."""
    print("\n" + "=" * 80)
    print("PROFILING: LLM Reasoning")
    print("=" * 80)
    
    try:
        from Agent_Guru.reasoning.llm.reasoning import LLMReasoningCore
        from Agent_Guru.reasoning.models.intent import Intent
        from Agent_Guru.reasoning.models.conversation import ConversationState
        
        core = LLMReasoningCore()
        
        # Test intent
        intent = Intent(
            intent_type="send_message",
            entities={"recipient": "John", "message": "I'll be late"},
            confidence=0.9,
            requires_reasoning=True,
            original_input="send a message to John saying I'll be late"
        )
        
        state = ConversationState(
            conversation_id="test",
            user_id="test_user",
            turns=[],
            entities={},
            created_at=time.time(),
            updated_at=time.time()
        )
        
        start = time.perf_counter()
        try:
            result = core.reason(intent, state)
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - Reasoning completed")
            print(f"  Steps: {len(result.steps) if hasattr(result, 'steps') else 'N/A'}")
        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - ERROR: {e}")
        
        print(f"\nTarget: <400ms")
        
        if elapsed * 1000 < 400:
            print("✓ PASS")
        else:
            print("✗ FAIL - Exceeds target")
            
    except Exception as e:
        print(f"✗ Could not profile LLM reasoning: {e}")


def profile_tool_selection():
    """Profile tool selection component."""
    print("\n" + "=" * 80)
    print("PROFILING: Tool Selection")
    print("=" * 80)
    
    try:
        from Agent_Guru.reasoning.tools.selector import ToolSelector
        from Agent_Guru.reasoning.models.task import Task, TaskType, TaskStatus
        
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
            retry_count=0
        )
        
        start = time.perf_counter()
        try:
            result = selector.select_tool(task)
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - Tool selected")
            print(f"  Tool: {result.tool.tool_id if hasattr(result, 'tool') else 'N/A'}")
        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - ERROR: {e}")
        
        print(f"\nTarget: <50ms")
        
        if elapsed * 1000 < 50:
            print("✓ PASS")
        else:
            print("✗ FAIL - Exceeds target")
            
    except Exception as e:
        print(f"✗ Could not profile tool selection: {e}")


def profile_safety_gate():
    """Profile safety gate component."""
    print("\n" + "=" * 80)
    print("PROFILING: Safety Gate")
    print("=" * 80)
    
    try:
        from Agent_Guru.reasoning.safety.gate import SafetyGate
        from Agent_Guru.reasoning.tools.base import Tool, ToolParameter, ParameterType
        
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
                    description="Message recipient"
                ),
                ToolParameter(
                    name="message",
                    type=ParameterType.STRING,
                    required=True,
                    description="Message content"
                )
            ],
            is_sensitive=True,
            estimated_latency=0.5
        )
        
        parameters = {"recipient": "John", "message": "Hello"}
        
        start = time.perf_counter()
        try:
            result = gate.validate_action(tool, parameters, "test_user")
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - Validation completed")
            print(f"  Allowed: {result.allowed if hasattr(result, 'allowed') else 'N/A'}")
            print(f"  Requires confirmation: {result.requires_confirmation if hasattr(result, 'requires_confirmation') else 'N/A'}")
        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - ERROR: {e}")
        
        print(f"\nTarget: <50ms")
        
        if elapsed * 1000 < 50:
            print("✓ PASS")
        else:
            print("✗ FAIL - Exceeds target")
            
    except Exception as e:
        print(f"✗ Could not profile safety gate: {e}")


def profile_response_generation():
    """Profile response generation component."""
    print("\n" + "=" * 80)
    print("PROFILING: Response Generation")
    print("=" * 80)
    
    try:
        from Agent_Guru.reasoning.response.template_generator import TemplateResponseGenerator
        from Agent_Guru.reasoning.models.result import ExecutionResult
        from Agent_Guru.reasoning.models.intent import Intent, InputSource
        
        generator = TemplateResponseGenerator()
        
        # Test result
        result = ExecutionResult(
            success=True,
            result_data={"timer_id": "123", "duration": "5 minutes"},
            error=None,
            execution_time=0.1,
            action_id="test_action"
        )
        
        intent = Intent(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.9,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes"
        )
        
        start = time.perf_counter()
        try:
            response = generator.generate_response(result, intent, InputSource.TEXT, {})
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - Response generated")
            print(f"  Text: {response.text[:60] if hasattr(response, 'text') else 'N/A'}...")
        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  {elapsed*1000:.1f}ms - ERROR: {e}")
        
        print(f"\nTarget: <150ms")
        
        if elapsed * 1000 < 150:
            print("✓ PASS")
        else:
            print("✗ FAIL - Exceeds target")
            
    except Exception as e:
        print(f"✗ Could not profile response generation: {e}")


def main():
    """Main profiling function."""
    print("=" * 80)
    print("REASONING COMPONENT PROFILER")
    print("=" * 80)
    print("\nThis script profiles individual components to identify bottlenecks.")
    print("For detailed flame graphs, run:")
    print("  py-spy record -o component_profile.svg -- python Agent_Guru/reasoning/profile_components.py")
    print()
    
    # Profile each component
    profile_fast_router()
    profile_intent_detection()
    profile_llm_reasoning()
    profile_tool_selection()
    profile_safety_gate()
    profile_response_generation()
    
    print("\n" + "=" * 80)
    print("PROFILING COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the timings above to identify slow components")
    print("2. Run with py-spy for detailed flame graphs:")
    print("   py-spy record -o component_profile.svg -- python Agent_Guru/reasoning/profile_components.py")
    print("3. Focus optimization on components exceeding their targets")
    print("4. Implement optimizations in task 34.2")


if __name__ == "__main__":
    main()
