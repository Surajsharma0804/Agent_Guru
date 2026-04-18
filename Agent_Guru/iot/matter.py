"""Matter/Thread IoT device controller.

Requirements: 16.1-16.3, 16.8, 16.10
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from Agent_Guru.core.retry import retry_async

logger = logging.getLogger(__name__)

CONTROL_TIMEOUT_MS = 500
RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)  # Exponential backoff

__all__ = ["DeviceCategory", "DeviceCommand", "DeviceState", "MatterController"]


class DeviceCategory(Enum):
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SENSOR = "sensor"
    PLUG = "plug"
    BLIND = "blind"
    FAN = "fan"
    APPLIANCE = "appliance"


@dataclass
class DeviceState:
    """Current state of an IoT device."""

    device_id: str
    category: DeviceCategory
    room: str
    online: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def serialize(self) -> str:
        return json.dumps(
            {
                "device_id": self.device_id,
                "category": self.category.value,
                "room": self.room,
                "online": self.online,
                "attributes": self.attributes,
                "last_updated": self.last_updated,
            }
        )

    @classmethod
    def deserialize(cls, data: str) -> DeviceState:
        d = json.loads(data)
        return cls(
            device_id=d["device_id"],
            category=DeviceCategory(d["category"]),
            room=d["room"],
            online=d["online"],
            attributes=d["attributes"],
            last_updated=d["last_updated"],
        )


@dataclass
class DeviceCommand:
    """Command to send to an IoT device."""

    device_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)


class MatterController:
    """Controls Matter/Thread IoT devices with local-only execution."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceState] = {}
        self._topology: dict[str, list[str]] = {}  # room -> [device_ids]

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self) -> list[DeviceState]:
        """Discover Matter/Thread devices on local network."""
        # Stub: in production uses python-matter-server
        await asyncio.sleep(0)
        logger.info("Discovered %d devices", len(self._devices))
        return list(self._devices.values())

    def register_device(self, state: DeviceState) -> None:
        """Register a device (used in tests and by platform bridges)."""
        self._devices[state.device_id] = state
        room_devices = self._topology.setdefault(state.room, [])
        if state.device_id not in room_devices:
            room_devices.append(state.device_id)

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    async def control(self, command: DeviceCommand) -> bool:
        """Execute device command with exponential backoff retry via shared retry utility."""
        device = self._devices.get(command.device_id)
        if device is None:
            logger.error("Device %s not registered", command.device_id)
            return False

        async def _attempt() -> bool:
            return await self._send_command(command)

        try:
            result = await retry_async(
                _attempt,
                delays=RETRY_DELAYS,
                exceptions=(RuntimeError, OSError),
                label=f"device:{command.device_id}",
            )
            if result:
                device.attributes.update(command.params)
                device.last_updated = time.time()
            return result
        except (RuntimeError, OSError) as e:
            logger.error("Device %s failed after all retries", command.device_id)
            return False

    async def _send_command(self, command: DeviceCommand) -> bool:
        """Send command to device (stub — local LAN only)."""
        await asyncio.sleep(0)
        device = self._devices.get(command.device_id)
        if device is None or not device.online:
            raise RuntimeError(f"Device {command.device_id} not available")
        return True

    async def get_state(self, device_id: str) -> DeviceState | None:
        """Get current device state."""
        await asyncio.sleep(0)
        return self._devices.get(device_id)

    # ------------------------------------------------------------------
    # Room-based resolution
    # ------------------------------------------------------------------

    async def resolve_room(self, room: str) -> list[DeviceState]:
        """Resolve all devices in a room within 500ms."""
        start = time.perf_counter()
        device_ids = self._topology.get(room, [])
        devices = [self._devices[did] for did in device_ids if did in self._devices]
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Room '%s' resolved in %.1fms (%d devices)", room, elapsed_ms, len(devices))
        return devices
