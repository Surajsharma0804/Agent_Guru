"""
Tool Loader - Automatically load and register all available tools

This module discovers and registers all tools from the tools package.
"""

import asyncio
import logging

_logger = logging.getLogger(__name__)

from Agent_Guru.reasoning.tools.external import (
    CreateCalendarEventTool,
    GetCalendarEventsTool,
    GetDirectionsTool,
    GetNewsTool,
    GetStockPriceTool,
    GetWeatherTool,
    SearchPlacesTool,
    SendEmailTool,
    SendSlackTool,
    SendSMSTool,
    SendTelegramTool,
    SendWhatsAppTool,
)
from Agent_Guru.reasoning.tools.knowledge import (
    CalculateTool,
    ConvertUnitsTool,
    DefineWordTool,
    QuestionAnswerTool,
    SummarizeArticleTool,
    SummarizeDocumentTool,
    SummarizeTextTool,
    TranslateTool,
    WebSearchTool,
)
from Agent_Guru.reasoning.tools.registry import ToolRegistry, get_registry

# Import all tool modules
from Agent_Guru.reasoning.tools.system import (
    CloseAppTool,
    FileCopyTool,
    FileDeleteTool,
    FileMoveTool,
    FileReadTool,
    FileWriteTool,
    OpenAppTool,
    ProcessKillTool,
    ProcessListTool,
    SetBrightnessTool,
    SetVolumeTool,
    SwitchAppTool,
    ToggleBluetoothTool,
    ToggleWifiTool,
)


async def load_all_tools(registry: ToolRegistry | None = None) -> int:
    """Load and register all available tools.

    Args:
        registry: Tool registry to use (uses global if None)

    Returns:
        Number of tools registered
    """
    if registry is None:
        registry = get_registry()

    # List of all tool classes
    tool_classes = [
        # System tools
        OpenAppTool,
        CloseAppTool,
        SwitchAppTool,
        FileReadTool,
        FileWriteTool,
        FileDeleteTool,
        FileMoveTool,
        FileCopyTool,
        SetVolumeTool,
        SetBrightnessTool,
        ToggleWifiTool,
        ToggleBluetoothTool,
        ProcessListTool,
        ProcessKillTool,
        # Knowledge tools
        WebSearchTool,
        TranslateTool,
        SummarizeTextTool,
        SummarizeArticleTool,
        SummarizeDocumentTool,
        QuestionAnswerTool,
        DefineWordTool,
        CalculateTool,
        ConvertUnitsTool,
        # External tools
        SendSMSTool,
        SendWhatsAppTool,
        SendTelegramTool,
        SendSlackTool,
        GetWeatherTool,
        GetDirectionsTool,
        SearchPlacesTool,
        GetNewsTool,
        GetStockPriceTool,
        SendEmailTool,
        CreateCalendarEventTool,
        GetCalendarEventsTool,
    ]

    count = 0
    for tool_class in tool_classes:
        try:
            tool = tool_class()
            # Skip if already registered to avoid duplicate-registration warnings
            if registry.get_tool(tool.metadata.tool_id) is not None:
                continue
            await registry.register(tool, tool.metadata)
            count += 1
        except Exception as e:
            _logger.warning("Failed to register %s: %s", tool_class.__name__, e)

    return count


def load_all_tools_sync() -> int:
    """Synchronous version of load_all_tools.

    Returns:
        Number of tools registered
    """
    try:
        asyncio.get_running_loop()
        # Already in a running event loop — use a thread to avoid deadlock
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, load_all_tools())
            return future.result()
    except RuntimeError:
        # No running loop — safe to call asyncio.run() directly
        return asyncio.run(load_all_tools())

