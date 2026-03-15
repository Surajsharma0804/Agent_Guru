"""
Tool Loader - Automatically load and register all available tools

This module discovers and registers all tools from the tools package.
"""

import asyncio
from typing import List

from Agent_Guru.reasoning.tools.registry import ToolRegistry, get_registry
from Agent_Guru.reasoning.tools.base import Tool

# Import all tool modules
from Agent_Guru.reasoning.tools.system import (
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
)

from Agent_Guru.reasoning.tools.knowledge import (
    WebSearchTool,
    TranslateTool,
    SummarizeTextTool,
    SummarizeArticleTool,
    SummarizeDocumentTool,
    QuestionAnswerTool,
    DefineWordTool,
    CalculateTool,
    ConvertUnitsTool,
)

from Agent_Guru.reasoning.tools.external import (
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
            print(f"[WARNING] Failed to register {tool_class.__name__}: {e}")
    
    return count


def load_all_tools_sync() -> int:
    """Synchronous version of load_all_tools.
    
    Returns:
        Number of tools registered
    """
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Event loop already running, create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, load_all_tools())
                return future.result()
        else:
            return asyncio.run(load_all_tools())
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(load_all_tools())

