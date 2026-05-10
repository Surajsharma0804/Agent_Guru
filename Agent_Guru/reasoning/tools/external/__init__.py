"""External API tools for email, messaging, calendar, maps, news, and stocks.

This module provides tools for integrating with external services.
"""

from Agent_Guru.reasoning.tools.external.calendar import (
    CreateCalendarEventTool,
    GetCalendarEventsTool,
)
from Agent_Guru.reasoning.tools.external.email import SendEmailTool
from Agent_Guru.reasoning.tools.external.information import (
    GetNewsTool,
    GetStockPriceTool,
)
from Agent_Guru.reasoning.tools.external.maps import (
    GetDirectionsTool,
    GetWeatherTool,
    SearchPlacesTool,
)
from Agent_Guru.reasoning.tools.external.messaging import (
    SendSlackTool,
    SendSMSTool,
    SendTelegramTool,
    SendWhatsAppTool,
)

__all__ = [
    # Calendar
    "CreateCalendarEventTool",
    "GetCalendarEventsTool",
    "GetDirectionsTool",
    # Information
    "GetNewsTool",
    "GetStockPriceTool",
    # Maps
    "GetWeatherTool",
    "SearchPlacesTool",
    # Email
    "SendEmailTool",
    # Messaging
    "SendSMSTool",
    "SendSlackTool",
    "SendTelegramTool",
    "SendWhatsAppTool",
]
