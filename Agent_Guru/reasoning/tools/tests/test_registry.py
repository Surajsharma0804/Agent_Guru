"""
Tests for tool registry.
"""

import pytest
import asyncio
from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolMetadata,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import ToolRegistry, get_registry


class MockTool(Tool):
    """Mock tool for testing."""

    def __init__(self, delay_ms: int = 0, should_fail: bool = False) -> None:
        super().__init__()
        self.delay_ms = delay_ms
        self.should_fail = should_fail
        self.execution_count = 0

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute mock tool."""
        self.execution_count += 1

        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)

        if self.should_fail:
            raise RuntimeError("Mock tool failure")

        return {"success": True, "result": kwargs, "execution_count": self.execution_count}


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        """Create a fresh registry for each test."""
        return ToolRegistry()

    @pytest.fixture
    def sample_metadata(self) -> ToolMetadata:
        """Create sample tool metadata."""
        return ToolMetadata(
            tool_id="test.tool",
            name="Test Tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="input",
                    type=ToolParameterType.STRING,
                    description="Input text",
                    required=True,
                )
            ],
            capabilities=["testing", "mock"],
        )

    async def test_register_tool(
        self, registry: ToolRegistry, sample_metadata: ToolMetadata
    ) -> None:
        """Test registering a tool."""
        tool = MockTool()
        await registry.register(tool, sample_metadata)

        assert registry.get_tool("test.tool") is tool
        assert registry.get_metadata("test.tool") == sample_metadata

    async def test_register_duplicate_tool_id(
        self, registry: ToolRegistry, sample_metadata: ToolMetadata
    ) -> None:
        """Test that registering duplicate tool ID raises error."""
        tool1 = MockTool()
        tool2 = MockTool()

        await registry.register(tool1, sample_metadata)

        with pytest.raises(ValueError, match="already registered"):
            await registry.register(tool2, sample_metadata)

    async def test_unregister_tool(
        self, registry: ToolRegistry, sample_metadata: ToolMetadata
    ) -> None:
        """Test unregistering a tool."""
        tool = MockTool()
        await registry.register(tool, sample_metadata)

        await registry.unregister("test.tool")

        assert registry.get_tool("test.tool") is None
        assert registry.get_metadata("test.tool") is None

    async def test_unregister_nonexistent_tool(self, registry: ToolRegistry) -> None:
        """Test unregistering a nonexistent tool does not raise error."""
        await registry.unregister("nonexistent.tool")  # Should not raise

    async def test_list_tools(self, registry: ToolRegistry) -> None:
        """Test listing all registered tools."""
        metadata1 = ToolMetadata(
            tool_id="tool1", name="Tool 1", description="First tool", capabilities=["test"]
        )
        metadata2 = ToolMetadata(
            tool_id="tool2", name="Tool 2", description="Second tool", capabilities=["test"]
        )

        await registry.register(MockTool(), metadata1)
        await registry.register(MockTool(), metadata2)

        tools = registry.list_tools()
        assert len(tools) == 2
        assert metadata1 in tools
        assert metadata2 in tools

    async def test_find_by_capability(self, registry: ToolRegistry) -> None:
        """Test finding tools by capability."""
        metadata1 = ToolMetadata(
            tool_id="tool1", name="Tool 1", description="First tool", capabilities=["text", "nlp"]
        )
        metadata2 = ToolMetadata(
            tool_id="tool2",
            name="Tool 2",
            description="Second tool",
            capabilities=["text", "search"],
        )
        metadata3 = ToolMetadata(
            tool_id="tool3", name="Tool 3", description="Third tool", capabilities=["image"]
        )

        await registry.register(MockTool(), metadata1)
        await registry.register(MockTool(), metadata2)
        await registry.register(MockTool(), metadata3)

        # Find by "text" capability
        text_tools = registry.find_by_capability("text")
        assert len(text_tools) == 2
        tool_ids = {t.tool_id for t in text_tools}
        assert "tool1" in tool_ids
        assert "tool2" in tool_ids

        # Find by "image" capability
        image_tools = registry.find_by_capability("image")
        assert len(image_tools) == 1
        assert image_tools[0].tool_id == "tool3"

        # Find by nonexistent capability
        none_tools = registry.find_by_capability("nonexistent")
        assert len(none_tools) == 0

    async def test_find_by_capabilities(self, registry: ToolRegistry) -> None:
        """Test finding tools by multiple capabilities."""
        metadata1 = ToolMetadata(
            tool_id="tool1", name="Tool 1", description="First tool", capabilities=["text", "nlp"]
        )
        metadata2 = ToolMetadata(
            tool_id="tool2",
            name="Tool 2",
            description="Second tool",
            capabilities=["text", "search"],
        )
        metadata3 = ToolMetadata(
            tool_id="tool3",
            name="Tool 3",
            description="Third tool",
            capabilities=["text", "nlp", "search"],
        )

        await registry.register(MockTool(), metadata1)
        await registry.register(MockTool(), metadata2)
        await registry.register(MockTool(), metadata3)

        # Find by multiple capabilities - should rank by match count
        tools = registry.find_by_capabilities(["text", "nlp", "search"])
        assert len(tools) == 3

        # tool3 should be first (matches all 3)
        assert tools[0].tool_id == "tool3"

        # tool1 and tool2 should follow (each matches 2)
        tool_ids = {tools[1].tool_id, tools[2].tool_id}
        assert "tool1" in tool_ids
        assert "tool2" in tool_ids

    async def test_execute_tool_success(
        self, registry: ToolRegistry, sample_metadata: ToolMetadata
    ) -> None:
        """Test successful tool execution."""
        tool = MockTool()
        await registry.register(tool, sample_metadata)

        result = await registry.execute("test.tool", input="hello")

        assert result["success"] is True
        assert result["result"]["input"] == "hello"
        assert "execution_time_ms" in result
        assert tool.execution_count == 1

    async def test_execute_tool_not_found(self, registry: ToolRegistry) -> None:
        """Test executing nonexistent tool raises error."""
        with pytest.raises(ValueError, match="not found"):
            await registry.execute("nonexistent.tool")

    async def test_execute_tool_invalid_parameters(
        self, registry: ToolRegistry, sample_metadata: ToolMetadata
    ) -> None:
        """Test executing tool with invalid parameters raises error."""
        tool = MockTool()
        await registry.register(tool, sample_metadata)

        # Missing required parameter
        with pytest.raises(ValueError, match="Missing required parameters"):
            await registry.execute("test.tool")

    async def test_execute_tool_with_timeout(self, registry: ToolRegistry) -> None:
        """Test tool execution with timeout."""
        metadata = ToolMetadata(
            tool_id="slow.tool", name="Slow Tool", description="A slow tool", parameters=[]
        )

        # Tool that takes 200ms
        tool = MockTool(delay_ms=200)
        await registry.register(tool, metadata)

        # Execute with 100ms timeout - should timeout
        result = await registry.execute("slow.tool", timeout_ms=100)

        assert result["success"] is False
        assert "timed out" in result["error"]
        assert result["execution_time_ms"] >= 100

    async def test_execute_tool_failure(self, registry: ToolRegistry) -> None:
        """Test tool execution failure is handled."""
        metadata = ToolMetadata(
            tool_id="fail.tool", name="Fail Tool", description="A failing tool", parameters=[]
        )

        tool = MockTool(should_fail=True)
        await registry.register(tool, metadata)

        result = await registry.execute("fail.tool")

        assert result["success"] is False
        assert "Mock tool failure" in result["error"]
        assert "execution_time_ms" in result

    async def test_capability_index_updated_on_unregister(self, registry: ToolRegistry) -> None:
        """Test that capability index is updated when tool is unregistered."""
        metadata = ToolMetadata(
            tool_id="test.tool",
            name="Test Tool",
            description="Test",
            capabilities=["test", "mock"],
        )

        await registry.register(MockTool(), metadata)

        # Verify capabilities are indexed
        assert len(registry.find_by_capability("test")) == 1
        assert len(registry.find_by_capability("mock")) == 1

        # Unregister tool
        await registry.unregister("test.tool")

        # Verify capabilities are removed from index
        assert len(registry.find_by_capability("test")) == 0
        assert len(registry.find_by_capability("mock")) == 0

    async def test_concurrent_registration(self, registry: ToolRegistry) -> None:
        """Test concurrent tool registration is thread-safe."""

        async def register_tool(tool_id: str) -> None:
            metadata = ToolMetadata(
                tool_id=tool_id, name=f"Tool {tool_id}", description="Test", capabilities=["test"]
            )
            await registry.register(MockTool(), metadata)

        # Register 10 tools concurrently
        await asyncio.gather(*[register_tool(f"tool{i}") for i in range(10)])

        # All tools should be registered
        tools = registry.list_tools()
        assert len(tools) == 10


class TestGetRegistry:
    """Tests for get_registry function."""

    def test_get_registry_returns_singleton(self) -> None:
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
