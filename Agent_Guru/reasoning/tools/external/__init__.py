"""
External API tools for email, messaging, calendar, maps, news, and stocks.

This module provides tools for integrating with external services.
"""

from Agent_Guru.reasoning.tools.external.email import SendEmailTool
from Agent_Guru.reasoning.tools.external.messaging import (
    SendSMSTool,
    SendWhatsAppTool,
    SendTelegramTool,
    SendSlackTool,
)
from Agent_Guru.reasoning.tools.external.calendar import (
    CreateCalendarEventTool,
    GetCalendarEventsTool,
)
from Agent_Guru.reasoning.tools.external.maps import (
    GetWeatherTool,
    GetDirectionsTool,
    SearchPlacesTool,
)
from Agent_Guru.reasoning.tools.external.information import (
    GetNewsTool,
    GetStockPriceTool,
)

__all__ = [
    # Email
    "SendEmailTool",
    # Messaging
    "SendSMSTool",
    "SendWhatsAppTool",
    "SendTelegramTool",
    "SendSlackTool",
    # Calendar
    "CreateCalendarEventTool",
    "GetCalendarEventsTool",
    # Maps
    "GetWeatherTool",
    "GetDirectionsTool",
    "SearchPlacesTool",
    # Information
    "GetNewsTool",
    "GetStockPriceTool",
]
