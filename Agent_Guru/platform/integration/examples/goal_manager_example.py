"""
Example: Goal Manager Integration Usage

This example demonstrates how to use the GoalManagerClient to notify
the Goal Manager about task completions and operation results.

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

import asyncio
from datetime import datetime

from Agent_Guru.platform.integration import (
    GoalManagerClient,
    OperationResult,
    OperationStatus,
    TaskCompletionNotification,
)


async def example_task_completion_notification():
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
                start_time=datetime.now(),
                end_time=datetime.now(),
                execution_time=0.5,
                parameters={"path": "/tmp/user_profile.json"},  # nosec B108
                result_data={"bytes_written": 1024},
                resource_usage={"cpu_percent": 2.5, "memory_mb": 5.0},
            ),
            OperationResult(
                operation_id="op-2",
                operation_type="command_execution",
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
                end_time=datetime.now(),
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
        status = await client.notify_task_completion(notification)

        print(f"Notification status: {status}")

        # Get client statistics
        stats = client.get_statistics()
        print(f"Client statistics: {stats}")

    finally:
        # Disconnect from Goal Manager
        await client.disconnect()


async def example_operation_result_reporting():
    """Example: Report individual operation result to Goal Manager."""

    # Use async context manager for automatic connection/disconnection
    async with GoalManagerClient(base_url="http://localhost:8080") as client:
        # Create operation result
        operation = OperationResult(
            operation_id="op-3",
            operation_type="network_request",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
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
        status = await client.report_operation_result(operation)

        print(f"Operation report status: {status}")


async def example_error_handling():
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
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    execution_time=0.1,
                    parameters={"path": "/protected/file.txt"},
                    error_message="Permission denied: Cannot delete protected file",
                )
            ],
            overall_status=OperationStatus.FAILURE,
        )

        # Send notification (will retry on transient failures)
        status = await client.notify_task_completion(notification)

        if status.value == "failed":
            print("Failed to send notification after retries")

            # Check if circuit breaker opened
            stats = client.get_statistics()
            if stats["circuit_open"]:
                print("Circuit breaker is open - Goal Manager may be unavailable")

    finally:
        await client.disconnect()


async def example_batch_notifications():
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
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        execution_time=0.3,
                    )
                ],
            )
            notifications.append(notification)

        # Send notifications concurrently
        tasks = [
            client.notify_task_completion(notif)
            for notif in notifications
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        successful = sum(1 for r in results if r.value == "sent")
        failed = sum(1 for r in results if r.value == "failed")

        print(f"Sent: {successful}, Failed: {failed}")


async def main():
    """Run all examples."""

    print("=" * 60)
    print("Goal Manager Integration Examples")
    print("=" * 60)

    print("\n1. Task Completion Notification")
    print("-" * 60)
    await example_task_completion_notification()

    print("\n2. Operation Result Reporting")
    print("-" * 60)
    await example_operation_result_reporting()

    print("\n3. Error Handling")
    print("-" * 60)
    await example_error_handling()

    print("\n4. Batch Notifications")
    print("-" * 60)
    await example_batch_notifications()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
