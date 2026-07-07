"""
Tests for Semantic LLM Interpreter Prompt Templates

Tests cover:
- PromptContext formatting
- PromptTemplate formatting
- Semantic interpreter prompt generation
- Context injection
- Context compression
- Few-shot example formatting

Coverage Target: 80%+
"""

from Agent_Guru.reasoning.llm.prompt_templates import (
    SEMANTIC_INTERPRETER_EXAMPLES,
    SEMANTIC_INTERPRETER_SYSTEM_PROMPT,
    SEMANTIC_INTERPRETER_TEMPLATE,
    SEMANTIC_INTERPRETER_USER_TEMPLATE,
    PromptContext,
    PromptTemplate,
    compress_context_for_token_limit,
    create_semantic_interpreter_prompt,
    inject_conversation_context,
)


class TestPromptContext:
    """Test PromptContext class."""

    def test_empty_context_formatting(self):
        """Test formatting empty context."""
        context = PromptContext()
        formatted = context.format_for_prompt()
        assert formatted == "No context available."  # nosec B101

    def test_context_with_recent_turns(self):
        """Test formatting context with recent turns."""
        context = PromptContext(recent_turns=["User: Hello", "Agent: Hi there!", "User: Set timer"])
        formatted = context.format_for_prompt()

        assert "Recent conversation:" in formatted  # nosec B101
        assert "1. User: Hello" in formatted  # nosec B101
        assert "2. Agent: Hi there!" in formatted  # nosec B101
        assert "3. User: Set timer" in formatted  # nosec B101

    def test_context_respects_max_turns(self):
        """Test that context respects max_turns limit."""
        context = PromptContext(recent_turns=[f"Turn {i}" for i in range(10)])
        formatted = context.format_for_prompt(max_turns=3)

        # Should only include last 3 turns
        assert "Turn 7" in formatted  # nosec B101
        assert "Turn 8" in formatted  # nosec B101
        assert "Turn 9" in formatted  # nosec B101
        assert "Turn 0" not in formatted  # nosec B101
        assert "Turn 6" not in formatted  # nosec B101

    def test_context_with_tracked_entities(self):
        """Test formatting context with tracked entities."""
        context = PromptContext(tracked_entities={"person": "John", "location": "Seattle"})
        formatted = context.format_for_prompt()

        assert "Tracked entities:" in formatted  # nosec B101
        assert "person: John" in formatted  # nosec B101
        assert "location: Seattle" in formatted  # nosec B101

    def test_context_with_user_preferences(self):
        """Test formatting context with user preferences."""
        context = PromptContext(user_preferences={"timer_sound": "bell", "language": "en"})
        formatted = context.format_for_prompt()

        assert "User preferences:" in formatted  # nosec B101
        assert "timer_sound: bell" in formatted  # nosec B101
        assert "language: en" in formatted  # nosec B101

    def test_context_with_past_actions(self):
        """Test formatting context with past actions."""
        context = PromptContext(
            past_actions=["set_timer(300)", "play_music('workout')", "send_message('John', 'Hi')"]
        )
        formatted = context.format_for_prompt()

        assert "Recent actions:" in formatted  # nosec B101
        # Should only show last 3 actions
        assert "set_timer(300)" in formatted  # nosec B101
        assert "play_music('workout')" in formatted  # nosec B101
        assert "send_message('John', 'Hi')" in formatted  # nosec B101

    def test_context_with_retrieved_memories(self):
        """Test formatting context with retrieved memories."""
        context = PromptContext(
            retrieved_memories=[
                {"memory_type": "episodic", "content": "User called Mom yesterday"},
                {"memory_type": "preference", "content": "User prefers morning workouts"},
            ]
        )
        formatted = context.format_for_prompt()

        assert "Relevant memories:" in formatted  # nosec B101
        assert "[episodic] User called Mom yesterday" in formatted  # nosec B101
        assert "[preference] User prefers morning workouts" in formatted  # nosec B101

    def test_context_with_world_state(self):
        """Test formatting context with world state."""
        context = PromptContext(world_state_summary="Battery: 85%, Network: WiFi, Location: Home")
        formatted = context.format_for_prompt()

        assert "World state:" in formatted  # nosec B101
        assert "Battery: 85%" in formatted  # nosec B101
        assert "Network: WiFi" in formatted  # nosec B101

    def test_context_with_all_fields(self):
        """Test formatting context with all fields populated."""
        context = PromptContext(
            recent_turns=["User: Hello"],
            tracked_entities={"person": "John"},
            user_preferences={"language": "en"},
            past_actions=["set_timer(300)"],
            retrieved_memories=[{"memory_type": "episodic", "content": "Test memory"}],
            world_state_summary="Battery: 50%",
        )
        formatted = context.format_for_prompt()

        assert "Recent conversation:" in formatted  # nosec B101
        assert "Tracked entities:" in formatted  # nosec B101
        assert "User preferences:" in formatted  # nosec B101
        assert "Recent actions:" in formatted  # nosec B101
        assert "Relevant memories:" in formatted  # nosec B101
        assert "World state:" in formatted  # nosec B101


class TestPromptTemplate:
    """Test PromptTemplate class."""

    def test_template_initialization(self):
        """Test template initialization."""
        template = PromptTemplate(
            system_prompt="System prompt",
            user_prompt_template="User: {user_input}",
            few_shot_examples=[{"input": "test", "output": {}}],
        )

        assert template.system_prompt == "System prompt"  # nosec B101
        assert template.user_prompt_template == "User: {user_input}"  # nosec B101
        assert len(template.few_shot_examples) == 1  # nosec B101

    def test_format_user_prompt_basic(self):
        """Test basic user prompt formatting."""
        template = PromptTemplate(
            system_prompt="System",
            user_prompt_template="Input: {user_input}\nContext: {context}\nTools: {available_tools}{examples}",
            few_shot_examples=[],
        )

        prompt = template.format_user_prompt(
            user_input="Set timer",
            context=None,
            available_tools=["timer_tool"],
            include_examples=False,
        )

        assert "Input: Set timer" in prompt  # nosec B101
        assert "Context: No context available." in prompt  # nosec B101
        assert "Tools: timer_tool" in prompt  # nosec B101

    def test_format_user_prompt_with_context(self):
        """Test user prompt formatting with context."""
        template = PromptTemplate(
            system_prompt="System",
            user_prompt_template="Input: {user_input}\nContext: {context}",
            few_shot_examples=[],
        )

        context = PromptContext(recent_turns=["User: Hello"])
        prompt = template.format_user_prompt(
            user_input="Set timer", context=context, include_examples=False
        )

        assert "Input: Set timer" in prompt  # nosec B101
        assert "Recent conversation:" in prompt  # nosec B101
        assert "User: Hello" in prompt  # nosec B101

    def test_format_user_prompt_with_examples(self):
        """Test user prompt formatting with few-shot examples."""
        template = PromptTemplate(
            system_prompt="System",
            user_prompt_template="{examples}Input: {user_input}",
            few_shot_examples=[
                {"input": "Example 1", "output": {"goal": "Test"}},
                {"input": "Example 2", "output": {"goal": "Test 2"}},
            ],
        )

        prompt = template.format_user_prompt(
            user_input="Set timer", include_examples=True, max_examples=2
        )

        assert "Examples:" in prompt  # nosec B101
        assert "Input: Example 1" in prompt  # nosec B101
        assert "Input: Example 2" in prompt  # nosec B101
        assert "Input: Set timer" in prompt  # nosec B101

    def test_format_user_prompt_limits_examples(self):
        """Test that max_examples limits number of examples."""
        template = PromptTemplate(
            system_prompt="System",
            user_prompt_template="{examples}Input: {user_input}",
            few_shot_examples=[{"input": f"Example {i}", "output": {}} for i in range(5)],
        )

        prompt = template.format_user_prompt(
            user_input="Set timer", include_examples=True, max_examples=2
        )

        # Should only include 2 examples
        assert prompt.count("Input: Example") == 2  # nosec B101


class TestSemanticInterpreterTemplate:
    """Test semantic interpreter template."""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "Semantic LLM Interpreter" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "Task object" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101

    def test_system_prompt_includes_task_structure(self):
        """Test that system prompt includes task structure."""
        assert "goal" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "task_type" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "entities" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "steps" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "confidence" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101

    def test_system_prompt_includes_task_types(self):
        """Test that system prompt includes all task types."""
        assert "single_step" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "multi_step" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "conversational" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101
        assert "memory_query" in SEMANTIC_INTERPRETER_SYSTEM_PROMPT  # nosec B101

    def test_user_template_has_placeholders(self):
        """Test that user template has required placeholders."""
        assert "{user_input}" in SEMANTIC_INTERPRETER_USER_TEMPLATE  # nosec B101
        assert "{context}" in SEMANTIC_INTERPRETER_USER_TEMPLATE  # nosec B101
        assert "{available_tools}" in SEMANTIC_INTERPRETER_USER_TEMPLATE  # nosec B101
        assert "{examples}" in SEMANTIC_INTERPRETER_USER_TEMPLATE  # nosec B101

    def test_examples_cover_all_task_types(self):
        """Test that examples cover all task types."""
        task_types = set()
        for example in SEMANTIC_INTERPRETER_EXAMPLES:
            output = example.get("output", {})
            task_type = output.get("task_type")
            if task_type:
                task_types.add(task_type)

        assert "single_step" in task_types  # nosec B101
        assert "multi_step" in task_types  # nosec B101
        assert "conversational" in task_types  # nosec B101
        assert "memory_query" in task_types  # nosec B101

    def test_examples_have_valid_structure(self):
        """Test that all examples have valid structure."""
        for example in SEMANTIC_INTERPRETER_EXAMPLES:
            assert "input" in example  # nosec B101
            assert "output" in example  # nosec B101

            output = example["output"]
            assert "goal" in output  # nosec B101
            assert "task_type" in output  # nosec B101
            assert "entities" in output  # nosec B101
            assert "steps" in output  # nosec B101
            assert "confidence" in output  # nosec B101
            assert "requires_confirmation" in output  # nosec B101
            assert "estimated_duration" in output  # nosec B101

            # Validate steps
            for step in output["steps"]:
                assert "step_id" in step  # nosec B101
                assert "description" in step  # nosec B101
                assert "tool_id" in step  # nosec B101
                assert "parameters" in step  # nosec B101
                assert "estimated_duration" in step  # nosec B101
                assert "status" in step  # nosec B101

    def test_template_object_exists(self):
        """Test that template object is created."""
        assert SEMANTIC_INTERPRETER_TEMPLATE  # nosec B101
        assert SEMANTIC_INTERPRETER_TEMPLATE.system_prompt  # nosec B101
        assert SEMANTIC_INTERPRETER_TEMPLATE.user_prompt_template  # nosec B101
        assert SEMANTIC_INTERPRETER_TEMPLATE.few_shot_examples  # nosec B101


class TestCreateSemanticInterpreterPrompt:
    """Test create_semantic_interpreter_prompt function."""

    def test_basic_prompt_creation(self):
        """Test basic prompt creation."""
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer for 5 minutes"
        )

        assert system_prompt  # nosec B101
        assert user_prompt  # nosec B101
        assert "Set timer for 5 minutes" in user_prompt  # nosec B101

    def test_prompt_with_context(self):
        """Test prompt creation with context."""
        context = PromptContext(
            recent_turns=["User: Hello", "Agent: Hi!"], tracked_entities={"duration": "5 minutes"}
        )

        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer", context=context
        )

        assert "Recent conversation:" in user_prompt  # nosec B101
        assert "User: Hello" in user_prompt  # nosec B101
        assert "Tracked entities:" in user_prompt  # nosec B101
        assert "duration: 5 minutes" in user_prompt  # nosec B101

    def test_prompt_with_available_tools(self):
        """Test prompt creation with available tools."""
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer", available_tools=["timer_tool", "music_tool", "weather_tool"]
        )

        assert "timer_tool" in user_prompt  # nosec B101
        assert "music_tool" in user_prompt  # nosec B101
        assert "weather_tool" in user_prompt  # nosec B101

    def test_prompt_with_examples(self):
        """Test prompt creation with examples."""
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer", include_examples=True, max_examples=2
        )

        assert "Examples:" in user_prompt  # nosec B101

    def test_prompt_without_examples(self):
        """Test prompt creation without examples."""
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer", include_examples=False
        )

        assert "Examples:" not in user_prompt  # nosec B101

    def test_prompt_returns_tuple(self):
        """Test that function returns tuple of two strings."""
        result = create_semantic_interpreter_prompt("Set timer")

        assert isinstance(result, tuple)  # nosec B101
        assert len(result) == 2  # nosec B101
        assert isinstance(result[0], str)  # nosec B101
        assert isinstance(result[1], str)  # nosec B101


class TestInjectConversationContext:
    """Test inject_conversation_context function."""

    def test_basic_context_injection(self):
        """Test basic context injection."""
        context = inject_conversation_context(
            recent_turns=["User: Hello"],
            tracked_entities={"person": "John"},
            user_preferences={"language": "en"},
            past_actions=["set_timer(300)"],
        )

        assert isinstance(context, PromptContext)  # nosec B101
        assert context.recent_turns == ["User: Hello"]  # nosec B101
        assert context.tracked_entities == {"person": "John"}  # nosec B101
        assert context.user_preferences == {"language": "en"}  # nosec B101
        assert context.past_actions == ["set_timer(300)"]  # nosec B101

    def test_context_injection_with_memories(self):
        """Test context injection with memories."""
        memories = [{"memory_type": "episodic", "content": "Test"}]

        context = inject_conversation_context(
            recent_turns=[],
            tracked_entities={},
            user_preferences={},
            past_actions=[],
            retrieved_memories=memories,
        )

        assert context.retrieved_memories == memories  # nosec B101

    def test_context_injection_with_world_state(self):
        """Test context injection with world state."""
        context = inject_conversation_context(
            recent_turns=[],
            tracked_entities={},
            user_preferences={},
            past_actions=[],
            world_state_summary="Battery: 50%",
        )

        assert context.world_state_summary == "Battery: 50%"  # nosec B101

    def test_context_injection_with_none_memories(self):
        """Test context injection with None memories."""
        context = inject_conversation_context(
            recent_turns=[],
            tracked_entities={},
            user_preferences={},
            past_actions=[],
            retrieved_memories=None,
        )

        assert context.retrieved_memories == []  # nosec B101


class TestCompressContextForTokenLimit:
    """Test compress_context_for_token_limit function."""

    def test_compress_large_context(self):
        """Test compressing large context."""
        context = PromptContext(
            recent_turns=[f"Turn {i}" for i in range(10)],
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(10)},
            user_preferences={"pref1": "val1", "pref2": "val2"},
            past_actions=[f"action_{i}" for i in range(10)],
            retrieved_memories=[
                {"memory_type": "episodic", "content": f"Memory {i}"} for i in range(10)
            ],
            world_state_summary="Very long world state summary " * 50,
        )

        compressed = compress_context_for_token_limit(context, max_tokens=100)

        # Should have fewer items
        assert len(compressed.recent_turns) <= 2  # nosec B101
        assert len(compressed.tracked_entities) <= 3  # nosec B101
        assert len(compressed.past_actions) == 0  # Removed first  # nosec B101
        assert len(compressed.retrieved_memories) <= 3  # nosec B101

        # Check formatted length
        formatted = compressed.format_for_prompt()
        assert len(formatted) <= 100 * 4  # Rough approximation  # nosec B101

    def test_compress_already_small_context(self):
        """Test compressing already small context."""
        context = PromptContext(recent_turns=["Turn 1"], tracked_entities={"entity": "value"})

        compressed = compress_context_for_token_limit(context, max_tokens=1000)

        # Should keep everything
        assert len(compressed.recent_turns) == 1  # nosec B101
        assert len(compressed.tracked_entities) == 1  # nosec B101

    def test_compress_removes_past_actions_first(self):
        """Test that compression removes past actions first."""
        context = PromptContext(
            recent_turns=["Turn 1", "Turn 2"],
            tracked_entities={"entity": "value"},
            past_actions=["action1", "action2", "action3"],
        )

        compressed = compress_context_for_token_limit(context, max_tokens=50)

        # Past actions should be removed first
        assert len(compressed.past_actions) == 0  # nosec B101

    def test_compress_aggressive_mode(self):
        """Test aggressive compression for very small token limit."""
        context = PromptContext(
            recent_turns=[f"Turn {i}" for i in range(5)],
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(5)},
            user_preferences={"pref1": "val1"},
            retrieved_memories=[
                {"memory_type": "episodic", "content": f"Memory {i}"} for i in range(5)
            ],
        )

        compressed = compress_context_for_token_limit(context, max_tokens=20)

        # Should be very aggressive
        assert len(compressed.recent_turns) <= 1  # nosec B101
        assert len(compressed.tracked_entities) <= 1  # nosec B101
        assert len(compressed.retrieved_memories) <= 2  # nosec B101
        assert len(compressed.user_preferences) == 0  # Removed in last resort  # nosec B101


class TestPromptTemplateIntegration:
    """Integration tests for prompt template system."""

    def test_end_to_end_prompt_generation(self):
        """Test end-to-end prompt generation."""
        # Create context
        context = inject_conversation_context(
            recent_turns=["User: What's the weather?", "Agent: It's sunny, 72°F"],
            tracked_entities={"location": "Seattle"},
            user_preferences={"temperature_unit": "fahrenheit"},
            past_actions=["query_weather('Seattle')"],
            retrieved_memories=[
                {"memory_type": "preference", "content": "User prefers detailed weather info"}
            ],
            world_state_summary="Battery: 85%, Network: WiFi",
        )

        # Generate prompts
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="What about tomorrow?",
            context=context,
            available_tools=["weather_tool", "calendar_tool"],
            include_examples=True,
            max_examples=2,
        )

        # Verify system prompt
        assert "Semantic LLM Interpreter" in system_prompt  # nosec B101
        assert "Task object" in system_prompt  # nosec B101

        # Verify user prompt includes all context
        assert "What about tomorrow?" in user_prompt  # nosec B101
        assert "Recent conversation:" in user_prompt  # nosec B101
        assert "What's the weather?" in user_prompt  # nosec B101
        assert "Tracked entities:" in user_prompt  # nosec B101
        assert "location: Seattle" in user_prompt  # nosec B101
        assert "User preferences:" in user_prompt  # nosec B101
        assert "temperature_unit: fahrenheit" in user_prompt  # nosec B101
        assert "Recent actions:" in user_prompt  # nosec B101
        assert "query_weather('Seattle')" in user_prompt  # nosec B101
        assert "Relevant memories:" in user_prompt  # nosec B101
        assert "User prefers detailed weather info" in user_prompt  # nosec B101
        assert "World state:" in user_prompt  # nosec B101
        assert "Battery: 85%" in user_prompt  # nosec B101
        assert "weather_tool" in user_prompt  # nosec B101
        assert "calendar_tool" in user_prompt  # nosec B101
        assert "Examples:" in user_prompt  # nosec B101

    def test_minimal_prompt_generation(self):
        """Test minimal prompt generation without context."""
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer for 5 minutes", include_examples=False
        )

        assert system_prompt  # nosec B101
        assert "Set timer for 5 minutes" in user_prompt  # nosec B101
        assert "No context available" in user_prompt  # nosec B101

    def test_prompt_with_compressed_context(self):
        """Test prompt generation with compressed context."""
        # Create large context
        large_context = PromptContext(
            recent_turns=[f"Turn {i}" for i in range(20)],
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(20)},
            user_preferences={f"pref_{i}": f"val_{i}" for i in range(10)},
            past_actions=[f"action_{i}" for i in range(20)],
        )

        # Compress it
        compressed = compress_context_for_token_limit(large_context, max_tokens=200)

        # Generate prompt
        system_prompt, user_prompt = create_semantic_interpreter_prompt(
            user_input="Set timer", context=compressed, include_examples=False
        )

        assert system_prompt  # nosec B101
        assert "Set timer" in user_prompt  # nosec B101
        # Should have compressed context
        assert len(user_prompt) < 2000  # Reasonable size  # nosec B101


# Property-based tests would go here if using Hypothesis
# For now, we have comprehensive unit tests covering all functionality
