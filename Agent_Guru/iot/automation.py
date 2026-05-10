"""IoT Automation Engine with scene management and NL parsing.

Requirements: 16.4, 16.5, 16.9
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Automation", "AutomationEngine", "Scene"]


@dataclass
class Scene:
    """A named collection of device states."""

    scene_id: str
    name: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class Automation:
    """A trigger → action automation rule."""

    automation_id: str
    trigger: dict[str, Any]
    actions: list[dict[str, Any]]
    enabled: bool = True


class AutomationEngine:
    """Manages scenes and automations with SQLite persistence."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection = sqlite3.connect(db_path)  # persistent; closed in close()
        self._init_db()
        self._automations: dict[str, Automation] = {}

    def close(self) -> None:
        """Release the SQLite connection."""
        self._conn.close()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS scenes "
                "(scene_id TEXT PRIMARY KEY, name TEXT, actions TEXT, created_at REAL)",
            )

    # ------------------------------------------------------------------
    # Scene management
    # ------------------------------------------------------------------

    def create_scene(self, name: str, actions: list[dict[str, Any]]) -> Scene:
        """Create and persist a scene."""
        scene_id = f"scene_{int(time.time() * 1000)}"
        scene = Scene(scene_id=scene_id, name=name, actions=actions)
        with self._conn:
            self._conn.execute(
                "INSERT INTO scenes VALUES (?, ?, ?, ?)",
                (scene_id, name, json.dumps(actions), scene.created_at),
            )
        logger.info("Created scene '%s' (%s)", name, scene_id)
        return scene

    async def activate_scene(self, scene_id: str, controller: Any) -> bool:
        """Activate a scene by executing all its device commands."""
        try:
            with self._conn:
                row = self._conn.execute(
                    "SELECT actions FROM scenes WHERE scene_id = ?",
                    (scene_id,),
                ).fetchone()
        except sqlite3.Error:
            logger.exception("DB error fetching scene %s: %s")
            return False
        if not row:
            logger.warning("Scene %s not found", scene_id)
            return False

        try:
            actions: list[dict[str, Any]] = json.loads(row[0])
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in scene %s: %s")
            return False
        from Agent_Guru.iot.matter import DeviceCommand

        for action in actions:
            try:
                cmd = DeviceCommand(
                    device_id=action["device_id"],
                    action=action["action"],
                    params=action.get("params", {}),
                )
                await controller.control(cmd)
            except KeyError:
                logger.exception("Scene %s action missing field %s — skipping")
                logger.exception("Scene %s action failed: %s — continuing")
        logger.info("Activated scene %s", scene_id)
        return True

    def get_scene(self, scene_id: str) -> Scene | None:
        """Retrieve a scene by ID."""
        try:
            with self._conn:
                row = self._conn.execute(
                    "SELECT scene_id, name, actions, created_at FROM scenes WHERE scene_id = ?",
                    (scene_id,),
                ).fetchone()
        except sqlite3.Error:
            logger.exception("DB error fetching scene %s: %s")
            return None
        if not row:
            return None
        try:
            return Scene(
                scene_id=row[0],
                name=row[1],
                actions=json.loads(row[2]),
                created_at=row[3],
            )
        except (json.JSONDecodeError, TypeError):
            logger.exception("Failed to deserialize scene %s: %s")
            return None

    # ------------------------------------------------------------------
    # Natural language automation parsing
    # ------------------------------------------------------------------

    def parse_nl_automation(self, nl_text: str) -> Automation | None:
        """Parse natural language into a structured automation rule.

        Uses keyword-based parsing as a fast local path; production deployments
        should inject an LLM callable via dependency injection for richer parsing.
        """
        automation_id = f"auto_{int(time.time() * 1000)}"
        trigger: dict[str, Any] = {}
        actions: list[dict[str, Any]] = []

        nl_lower = nl_text.lower()
        if "when i arrive" in nl_lower or "when i get home" in nl_lower:
            trigger = {"type": "location", "event": "arrive_home"}
        elif "at " in nl_lower and ("am" in nl_lower or "pm" in nl_lower):
            trigger = {"type": "time", "expression": nl_text}
        elif "when motion" in nl_lower:
            trigger = {"type": "sensor", "sensor_type": "motion"}
        else:
            trigger = {"type": "voice", "phrase": nl_text}

        if "turn on" in nl_lower or "lights on" in nl_lower:
            actions.append({"action": "turn_on", "category": "light"})
        if "turn off" in nl_lower or "lights off" in nl_lower:
            actions.append({"action": "turn_off", "category": "light"})
        if "lock" in nl_lower:
            actions.append({"action": "lock", "category": "lock"})
        if "thermostat" in nl_lower or "temperature" in nl_lower:
            actions.append({"action": "set_temperature", "category": "thermostat"})

        if not actions:
            return None

        automation = Automation(
            automation_id=automation_id,
            trigger=trigger,
            actions=actions,
        )
        self._automations[automation_id] = automation
        return automation
