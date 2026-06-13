"""Example: Voice-Driven System Control Commands.

Demonstrates parsing voice commands and routing them to the system.
"""

import asyncio

from Agent_Guru.speech.agent_orchestration_client import AgentOrchestrationClient
from Agent_Guru.speech.commands.command_parser import CommandParser
from Agent_Guru.speech.goal_manager_client import GoalManagerClient


async def main() -> None:
    parser = CommandParser()
    orch_client = AgentOrchestrationClient()  # No system = graceful stub
    gm_client = GoalManagerClient()  # No manager = graceful stub

    voice_inputs = [
        "open browser",
        "set volume to 60 percent",
        "scroll down",
        "remind me to call John tomorrow",
        "create a task to review the quarterly report",
    ]

    for text in voice_inputs:
        command = parser.interpret(text)

        if command.is_command:
            # Route to orchestration
            await orch_client.route_command(command)

            # Create goal for task-like commands
            if (
                command.action_id in ("GENERIC_COMMAND",)
                or "task" in text.lower()
                or "remind" in text.lower()
            ):
                await gm_client.create_task(text)
        else:
            pass


if __name__ == "__main__":
    asyncio.run(main())
