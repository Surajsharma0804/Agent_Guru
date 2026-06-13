"""Example: Git Integration for Learning Data Versioning.

This example demonstrates how to use the GitIntegration class to automatically
commit learning data to GitHub after each task execution.

Features demonstrated:
- Automated commits after task execution
- Improvement report commits
- Offline queue for network failures
- Retry logic with exponential backoff
- Authentication handling
"""

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from Agent_Guru.self_improvement import AuthMethod, FailureType, GitIntegration, TaskExecution

logger = logging.getLogger(__name__)


def example_basic_usage() -> None:
    """Basic usage of GitIntegration."""
    # Initialize Git integration
    # In production, use your actual repository path
    repo_path = Path.cwd()  # Current directory

    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.SSH,  # Use SSH keys
        auto_push=True,  # Automatically push commits
    )

    # Create a mock task execution
    execution = TaskExecution(
        task_id="example_task_001",
        task_type="code_generation",
        strategy_id="strategy_v1",
        timestamp=datetime.now(tz=UTC),
        success=True,
        execution_time_ms=250.5,
        failure_type=None,
        error_details=None,
        context={"language": "python", "complexity": "medium"},
    )

    # Commit execution data
    success = git_integration.commit_execution_data(
        execution,
        push=False,  # Don't push for this example
    )

    if success:
        pass
    else:
        pass


def example_with_authentication() -> None:
    """Example with different authentication methods."""
    repo_path = Path.cwd()

    # Method 1: SSH (recommended for local development)
    GitIntegration(repo_path=str(repo_path), auth_method=AuthMethod.SSH, auto_push=False)

    # Method 2: Token (recommended for CI/CD)
    # In production, load token from environment variable
    token = os.environ["GITHUB_TOKEN"]
    GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.TOKEN,
        auth_token=token,
        auto_push=False,
    )

    # Method 3: None (for local testing)
    GitIntegration(repo_path=str(repo_path), auth_method=AuthMethod.NONE, auto_push=False)


def example_improvement_report() -> None:
    """Example of committing improvement report."""
    repo_path = Path.cwd()

    git_integration = GitIntegration(repo_path=str(repo_path), auto_push=False)

    # Create improvement report
    report = {
        "total_tasks": 100,
        "baseline_success_rate": 0.70,
        "current_success_rate": 0.88,
        "relative_improvement": 0.18,  # 18% improvement
        "execution_time_improvement": 0.12,
        "reasoning_accuracy_improvement": 0.15,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "confidence_interval": [0.15, 0.21],
    }

    success = git_integration.commit_improvement_report(report, push=False)

    if success:
        pass
    else:
        pass


def example_offline_queue() -> None:
    """Example of offline queue functionality."""
    repo_path = Path.cwd()

    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False,
        max_retries=3,
        initial_backoff=1.0,
    )

    # Simulate offline operation

    for i in range(3):
        execution = TaskExecution(
            task_id=f"offline_task_{i}",
            task_type="test_type",
            strategy_id="test_strategy",
            timestamp=datetime.now(tz=UTC),
            success=True,
            execution_time_ms=100.0,
            failure_type=None,
            error_details=None,
            context={},
        )

        # Commits will be queued if push fails
        git_integration.commit_execution_data(execution, push=False)

    # Process queue when back online
    git_integration.process_queue()


def example_retry_logic() -> None:
    """Example of retry logic with exponential backoff."""
    repo_path = Path.cwd()

    GitIntegration(
        repo_path=str(repo_path),
        auto_push=False,
        max_retries=5,
        initial_backoff=1.0,  # Start with 1 second
        max_backoff=60.0,  # Max 60 seconds
    )


def example_online_status() -> None:
    """Example of checking online status."""
    repo_path = Path.cwd()

    git_integration = GitIntegration(repo_path=str(repo_path), auto_push=False)

    is_online = git_integration.is_online()

    if is_online:
        pass
    else:
        pass


def example_failure_commit() -> None:
    """Example of committing failed execution."""
    repo_path = Path.cwd()

    git_integration = GitIntegration(repo_path=str(repo_path), auto_push=False)

    # Create failed execution
    execution = TaskExecution(
        task_id="failed_task_001",
        task_type="complex_reasoning",
        strategy_id="strategy_v2",
        timestamp=datetime.now(tz=UTC),
        success=False,
        execution_time_ms=500.0,
        failure_type=FailureType.REASONING_ERROR,
        error_details={"reasoning_step": "step_3", "error": "Invalid logical inference"},
        context={"complexity": "high"},
    )

    success = git_integration.commit_execution_data(execution, push=False)

    if success:
        pass


def main() -> None:
    """Run all examples."""
    try:
        example_basic_usage()
        example_with_authentication()
        example_improvement_report()
        example_offline_queue()
        example_retry_logic()
        example_online_status()
        example_failure_commit()

    except Exception:
        logger.exception("Operation failed")


if __name__ == "__main__":
    main()
