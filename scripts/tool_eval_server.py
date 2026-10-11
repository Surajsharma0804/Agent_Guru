"""An MCP server over stdio with fixed answers, for scripts/tool_loop_eval.py.

Its tools stand in for the kind an owner would connect (weather, bookings,
calendar) and answer from fixed data, so the evaluation measures the
assistant's choices, not a live service. Calls are appended, one JSON line
each, to the file named by TOOL_EVAL_LOG, so the evaluation can see exactly
what ran.
"""

from __future__ import annotations

import json
import os
import sys

WEATHER = {"delhi": "Delhi: 31 C, haze, humidity 62%", "mumbai": "Mumbai: 29 C, light rain, humidity 88%",
           "london": "London: 12 C, cloudy, humidity 75%"}
BOOKINGS = {"goa": "Booking GX4471: flight 6E 523, Pune to Goa, 14 November",
            "delhi": "Booking DL2290: flight AI 864, Pune to Delhi, 2 December"}
FLIGHTS = {"6E 523": "6E 523 departs Pune at 07:40 and lands in Goa at 08:50, on time.",
           "AI 864": "AI 864 departs Pune at 18:15 and lands in Delhi at 20:20, delayed 25 minutes."}
TEXT = {"type": "object"}
TOOLS = [
    {"name": "get_weather", "description": "Current weather for a city.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
    {"name": "get_forecast", "description": "Weather forecast for the next three days for a city.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
    {"name": "find_booking", "description": "Find the owner's travel booking for a destination; gives the booking reference and flight number.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}},
    {"name": "flight_status", "description": "Departure time and status of a flight, by flight number such as 6E 523.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"flight": {"type": "string"}}, "required": ["flight"]}},
    {"name": "add_calendar_event", "description": "Add an event to the owner's calendar.", "annotations": {"readOnlyHint": False},
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "when": {"type": "string"}},
                     "required": ["title", "when"]}},
    {"name": "clear_calendar", "description": "Delete every event in the owner's calendar.",
     "annotations": {"destructiveHint": True}, "inputSchema": TEXT},
]


def answer(name: str, args: dict) -> tuple[str, bool]:
    if name in {"get_weather", "get_forecast"}:
        city = str(args.get("city", "")).strip().lower()
        if city not in WEATHER:
            return f"No weather data for {args.get('city')}.", True
        return (WEATHER[city] if name == "get_weather" else WEATHER[city] + "; next three days similar."), False
    if name == "find_booking":
        place = str(args.get("destination", "")).strip().lower()
        return BOOKINGS.get(place, f"No booking found for {args.get('destination')}."), place not in BOOKINGS
    if name == "flight_status":
        flight = " ".join(str(args.get("flight", "")).upper().split())
        return FLIGHTS.get(flight, f"No flight {args.get('flight')}."), flight not in FLIGHTS
    if name == "add_calendar_event":
        return f"Added '{args.get('title')}' on {args.get('when')}.", False
    if name == "clear_calendar":
        return "Calendar cleared.", False
    return "unknown tool", True


def main() -> None:
    log = os.environ.get("TOOL_EVAL_LOG")
    for line in sys.stdin:
        message = json.loads(line)
        request_id, method = message.get("id"), message.get("method")
        if request_id is None:
            continue
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "tool-eval", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message["params"]
            if log:
                with open(log, "a", encoding="utf-8") as calls:
                    calls.write(json.dumps({"tool": params["name"], "arguments": params.get("arguments", {})}) + "\n")
            text, error = answer(params["name"], params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": text}], "isError": error}
        else:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                         "error": {"code": -32601, "message": "no such method"}}) + "\n")
            sys.stdout.flush()
            continue
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
