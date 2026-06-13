"""Example: Goal Manager Integration Usage.

This example demonstrates how to use the GoalManagerClient to notify
the Goal Manager about task completions and operation results.

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

import asyncio
from datetime import UTC, datetime

from Agent_Guru.platform.integration import (
    GoalManagerClient,
    OperationResult,
    OperationStatus,
    TaskCompletionNotification,
)


async def example_task_completion_notification() -> None:
    """Example: Send task completion notification to Goal Manager."""
    # Create Goal Manager client
    client = GoalManagerClient(
        base_url="http://localhost:8080",
        timeout=30.0,
        max_retries=3,
    )

    # Connect to Goal Manager
    await client.connect()

    try:
        # Create operation results
        operations = [
            OperationResult(
                operation_id="op-1",
                operation_type="file_write",
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(tz=UTC),
                end_time=datetime.now(tz=UTC),
                execution_time=0.5,
                parameters={"path": "/tmp/user_profile.json"},  # nosec B108  # noqa: S108 - Not a real secret
                result_data={"bytes_written": 1024},
                resource_usage={"cpu_percent": 2.5, "memory_mb": 5.0},
            ),
            OperationResult(
                operation_id="op-2",
                operation_type="command_execution",
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(tz=UTC),
                end_time=datetime.now(tz=UTC),
                execution_time=1.2,
                parameters={"command": "chmod 644 /tmp/user_profile.json"},
                result_data={"exit_code": 0},
                resource_usage={"cpu_percent": 1.0, "memory_mb": 2.0},
            ),
        ]

        # Create task completion notification
        notification = TaskCompletionNotification(
            task_id="task-123",
            task_description="Create user profile file",
            operations=operations,
            overall_status=OperationStatus.SUCCESS,
            metadata={
                "user_id": "user-456",
                "profile_type": "standard",
            },
        )

        # Send notification
        await client.notify_task_completion(notification)

        # Get client statistics
        client.get_statistics()

    finally:
        # Disconnect from Goal Manager
        await client.disconnect()


async def example_operation_result_reporting() -> None:
    """Example: Report individual operation result to Goal Manager."""
    # Use async context manager for automatic connection/disconnection
    async with GoalManagerClient(base_url="http://localhost:8080") as client:
        # Create operation result
        operation = OperationResult(
            operation_id="op-3",
            operation_type="network_request",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(tz=UTC),
            end_time=datetime.now(tz=UTC),
            execution_time=0.8,
            parameters={
                "method": "POST",
                "url": "https://api.example.com/users",
            },
            result_data={
                "status_code": 201,
                "response_body": {"id": "user-789"},
            },
            resource_usage={"cpu_percent": 1.5, "memory_mb": 3.0},
        )

        # Report operation result
        await client.report_operation_result(operation)


async def example_error_handling() -> None:
    """Example: Handle errors and retries."""
    client = GoalManagerClient(
        base_url="http://localhost:8080",
        max_retries=3,
        retry_delay=1.0,
        circuit_breaker_threshold=5,
    )

    await client.connect()

    try:
        # Create notification with failed operation
        notification = TaskCompletionNotification(
            task_id="task-456",
            task_description="Failed operation example",
            operations=[
                OperationResult(
                    operation_id="op-4",
                    operation_type="file_delete",
                    status=OperationStatus.FAILURE,
                    start_time=datetime.now(tz=UTC),
                    end_time=datetime.now(tz=UTC),
                    execution_time=0.1,
                    parameters={"path": "/protected/file.txt"},
                    error_message="Permission denied: Cannot delete protected file",
                ),
            ],
            overall_status=OperationStatus.FAILURE,
        )

        # Send notification (will retry on transient failures)
        status = await client.notify_task_completion(notification)

        if status.value == "failed":
            # Check if circuit breaker opened
            stats = client.get_statistics()
            if stats["circuit_open"]:
                pass

    finally:
        await client.disconnect()


async def example_batch_notifications() -> None:
    """Example: Send multiple notifications efficiently."""
    async with GoalManagerClient(base_url="http://localhost:8080") as client:
        # Create multiple notifications
        notifications = []

        for i in range(5):
            notification = TaskCompletionNotification(
                task_id=f"task-{i}",
                task_description=f"Batch task {i}",
                operations=[
                    OperationResult(
                        operation_id=f"op-{i}",
                        operation_type="file_write",
                        status=OperationStatus.SUCCESS,
                        start_time=datetime.now(tz=UTC),
                        end_time=datetime.now(tz=UTC),
                        execution_time=0.3,
                    ),
                ],
            )
            notifications.append(notification)

        # Send notifications concurrently
        tasks = [client.notify_task_completion(notif) for notif in notifications]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        sum(1 for r in results if r.value == "sent")
        sum(1 for r in results if r.value == "failed")


async def main() -> None:
    """Run all examples."""
    await example_task_completion_notification()

    await example_operation_result_reporting()

    await example_error_handling()

    await example_batch_notifications()


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
