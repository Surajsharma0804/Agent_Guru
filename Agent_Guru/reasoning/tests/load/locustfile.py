"""Locust load test scenarios for the Core Reasoning Engine.

Run with:
    locust -f locustfile.py --host=http://localhost:8000

Ramp-up test:
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 60s

Sustained load test:
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 5 --run-time 300s

Requirements: 10.1 - Respond to common commands within 1.5s end-to-end
"""

import secrets
import uuid

from locust import HttpUser, between, task

# ---------------------------------------------------------------------------
# Test data generators
# ---------------------------------------------------------------------------

TIMER_COMMANDS = (
    "Set a timer for 5 minutes",
    "Set a timer for 10 minutes",
    "Set a 30 second timer",
    "Remind me in 1 hour",
    "Set an alarm for 7 AM",
)

WEATHER_COMMANDS = (
    "What's the weather today?",
    "Will it rain tomorrow?",
    "What's the temperature outside?",
    "Weather forecast for this week",
    "Is it going to be sunny today?",
)

MUSIC_COMMANDS = (
    "Play some jazz music",
    "Play my morning playlist",
    "Skip this song",
    "Turn up the volume",
    "Pause the music",
)

MESSAGING_COMMANDS = (
    "Send a message to John saying I'll be late",
    "Read my latest messages",
    "Call Mom",
    "Text Sarah that I'm on my way",
    "Check my notifications",
)

SYSTEM_COMMANDS = (
    "Turn off the lights",
    "Set the thermostat to 72 degrees",
    "Lock the front door",
    "Turn on the TV",
    "Dim the bedroom lights to 50 percent",
)

# Ramp-up configuration constants
SPAWN_RATE_BASELINE = 1  # users/second for baseline test
SPAWN_RATE_PRODUCTION = 10  # users/second for production load test
SPAWN_RATE_PEAK = 50  # users/second for peak load test

USER_COUNT_BASELINE = 10
USER_COUNT_PRODUCTION = 100
USER_COUNT_PEAK = 500
USER_COUNT_STRESS = 1000

# Latency target from Requirement 10.1
LATENCY_TARGET_MS = 1500


def _random_user_id() -> str:
    """Generate a random user identifier for test data isolation."""
    return f"load-test-user-{uuid.uuid4().hex[:8]}"


def _random_conversation_id() -> str:
    """Generate a random conversation identifier."""
    return f"conv-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Locust User class
# ---------------------------------------------------------------------------


class ReasoningEngineUser(HttpUser):
    """Simulates realistic user behavior against the Core Reasoning Engine API.

    Each virtual user maintains its own session context (user_id,
    conversation_id) and cycles through common command categories with
    realistic wait times between requests.

    Wait time: 1–3 seconds between tasks (simulates natural speech cadence).
    """

    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Initialize per-user session state."""
        self.user_id = _random_user_id()
        self.conversation_id = _random_conversation_id()

    # ------------------------------------------------------------------
    # Task methods – weighted to reflect real-world usage distribution
    # ------------------------------------------------------------------

    @task(3)
    def set_timer(self) -> None:
        """Send a timer command (high-frequency intent)."""
        command = secrets.choice(TIMER_COMMANDS)
        self._send_command(command)

    @task(3)
    def query_weather(self) -> None:
        """Send a weather query (high-frequency intent)."""
        command = secrets.choice(WEATHER_COMMANDS)
        self._send_command(command)

    @task(2)
    def play_music(self) -> None:
        """Send a music control command."""
        command = secrets.choice(MUSIC_COMMANDS)
        self._send_command(command)

    @task(2)
    def send_message(self) -> None:
        """Send a messaging command."""
        command = secrets.choice(MESSAGING_COMMANDS)
        self._send_command(command)

    @task(1)
    def system_control(self) -> None:
        """Send a smart-home / system control command (lower frequency)."""
        command = secrets.choice(SYSTEM_COMMANDS)
        self._send_command(command)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _send_command(self, command: str) -> None:
        """POST a command to the reasoning engine endpoint."""
        payload = {
            "text": command,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "source": "text",
        }
        with self.client.post(
            "/api/v1/reason",
            json=payload,
            catch_response=True,
            name="POST /api/v1/reason",
        ) as response:
            if response.elapsed.total_seconds() * 1000 > LATENCY_TARGET_MS:
                response.failure(
                    f"Latency {response.elapsed.total_seconds() * 1000:.0f}ms "
                    f"exceeds {LATENCY_TARGET_MS}ms target",
                )
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.success()
