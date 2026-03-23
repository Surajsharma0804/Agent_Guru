"""
Example: Voice-Driven System Control Commands

Demonstrates parsing voice commands and routing them to the system.
"""

import asyncio

from Agent_Guru.speech.agent_orchestration_client import AgentOrchestrationClient
from Agent_Guru.speech.commands.command_parser import CommandParser
from Agent_Guru.speech.goal_manager_client import GoalManagerClient


async def main():
    parser = CommandParser()
    orch_client = AgentOrchestrationClient()   # No system = graceful stub
    gm_client = GoalManagerClient()            # No manager = graceful stub

    voice_inputs = [
        "open browser",
        "set volume to 60 percent",
        "scroll down",
        "remind me to call John tomorrow",
        "create a task to review the quarterly report",
    ]

    for text in voice_inputs:
        print(f"\nInput: '{text}'")
        command = parser.interpret(text)

        if command.is_command:
            print(f"  Action: {command.action_id}")
            print(f"  Parameters: {command.parameters}")
            print(f"  Confidence: {command.confidence:.2f}")

            # Route to orchestration
            route_result = await orch_client.route_command(command)
            print(f"  Routed: {route_result.success}")

            # Create goal for task-like commands
            if command.action_id in ("GENERIC_COMMAND",) or "task" in text.lower() or "remind" in text.lower():
                task_result = await gm_client.create_task(text)
                print(f"  Task created: {task_result.success} — {task_result.confirmation_text}")
        else:
            print("  Not recognized as a command")


if __name__ == "__main__":
    asyncio.run(main())
