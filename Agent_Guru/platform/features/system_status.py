"""System status queries for Agent Guru.

Handles commands like:
  'what's my CPU usage?' → '45 percent'
  'how much RAM is free?' → '6.2 gigabytes free'
  'what's my battery?' → '78 percent, plugged in'
  'what's my IP address?' → '192.168.1.5'
  'how much disk space do I have?' → '120 gigabytes free on C drive'

Uses psutil which is already in requirements.txt.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def is_system_status_command(transcript: str) -> bool:
    """Return True if the user is asking about system status."""
    return bool(
        re.search(
            r"\b(cpu|processor|ram|memory|battery|disk|storage|"
            r"ip address|network|wifi speed|internet speed|"
            r"temperature|how hot|gpu|graphics)\b",
            transcript,
            re.IGNORECASE,
        ),
    )


def get_system_status(transcript: str) -> str:
    """Return a natural language system status answer."""
    try:
        import psutil
    except ImportError:
        return "System monitoring requires psutil. Run: pip install psutil"
    t = transcript.lower()

    # CPU
    if re.search(r"\bcpu|processor\b", t):
        cpu = psutil.cpu_percent(interval=0.5)
        cores = psutil.cpu_count(logical=False)
        return f"CPU usage is {cpu:.0f} percent across {cores} cores."

    # RAM / Memory
    if re.search(r"\bram|memory\b", t):
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        used_gb = mem.used / (1024**3)
        free_gb = mem.available / (1024**3)
        pct = mem.percent
        return (
            f"RAM usage is {pct:.0f} percent. "
            f"{used_gb:.1f} gigabytes used, {free_gb:.1f} gigabytes free "
            f"out of {total_gb:.1f} total."
        )

    # Battery
    if re.search(r"\bbattery\b", t):
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected - this device is running on AC power."
        pct = battery.percent
        plugged = "plugged in" if battery.power_plugged else "on battery"
        if battery.power_plugged:
            return f"Battery is at {pct:.0f} percent and {plugged}."
        # Estimate time remaining
        secs_left = battery.secsleft
        if secs_left > 0 and secs_left != psutil.POWER_TIME_UNLIMITED:
            hours = secs_left // 3600
            mins = (secs_left % 3600) // 60
            time_str = f", about {hours} hours and {mins} minutes remaining"
        else:
            time_str = ""
        return f"Battery is at {pct:.0f} percent{time_str}, {plugged}."

    # Disk
    if re.search(r"\bdisk|storage|space\b", t):
        disk = psutil.disk_usage("/")
        free_gb = disk.free / (1024**3)
        total_gb = disk.total / (1024**3)
        used_pct = disk.percent
        return (
            f"Disk usage is {used_pct:.0f} percent. "
            f"{free_gb:.0f} gigabytes free out of {total_gb:.0f} total."
        )

    # IP address
    if re.search(r"\bip address|my ip\b", t):
        try:
            import socket

            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"Your local IP address is {ip}."
        except Exception:
            return "Could not determine IP address."
    # GPU temperature
    if re.search(r"\bgpu|graphics\b", t):
        try:
            import torch

            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                mem_used = torch.cuda.memory_allocated(0) / (1024**3)
                mem_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                return f"GPU is {name}. Using {mem_used:.1f} of {mem_total:.1f} gigabytes VRAM."
        except Exception:
            logger.exception("Operation failed")
        return "No GPU information available."

    # Generic fallback
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    return f"CPU is at {cpu:.0f} percent, RAM is at {mem.percent:.0f} percent."
