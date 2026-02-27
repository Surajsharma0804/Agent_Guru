"""
Example: Git Integration for Learning Data Versioning

This example demonstrates how to use the GitIntegration class to automatically
commit learning data to GitHub after each task execution.

Features demonstrated:
- Automated commits after task execution
- Improvement report commits
- Offline queue for network failures
- Retry logic with exponential backoff
- Authentication handling
"""

from datetime import datetime
from pathlib import Path
from Agent_Guru.self_improvement import (
    GitIntegration,
    AuthMethod,
    TaskExecution,
    FailureType
)


def example_basic_usage():
    """Basic usage of GitIntegration."""
    print("=== Basic Git Integration Usage ===\n")
    
    # Initialize Git integration
    # In production, use your actual repository path
    repo_path = Path.cwd()  # Current directory
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.SSH,  # Use SSH keys
        auto_push=True  # Automatically push commits
    )
    
    print(f"Initialized Git integration for: {repo_path}")
    print(f"Queue size: {git_integration.get_queue_size()}\n")
    
    # Create a mock task execution
    execution = TaskExecution(
        task_id="example_task_001",
        task_type="code_generation",
        strategy_id="strategy_v1",
        timestamp=datetime.now(),
        success=True,
        execution_time_ms=250.5,
        failure_type=None,
        error_details=None,
        context={"language": "python", "complexity": "medium"}
    )
    
    # Commit execution data
    print("Committing task execution data...")
    success = git_integration.commit_execution_data(
        execution,
        push=False  # Don't push for this example
    )
    
    if success:
        print("✅ Execution data committed successfully\n")
    else:
        print("❌ Commit failed, added to queue\n")


def example_with_authentication():
    """Example with different authentication methods."""
    print("=== Authentication Methods ===\n")
    
    repo_path = Path.cwd()
    
    # Method 1: SSH (recommended for local development)
    print("1. SSH Authentication (uses ~/.ssh/id_rsa)")
    git_ssh = GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.SSH,
        auto_push=False
    )
    print(f"   Initialized with SSH auth\n")
    
    # Method 2: Token (recommended for CI/CD)
    print("2. Token Authentication (uses GitHub token)")
    # In production, load token from environment variable
    token = "ghp_your_token_here"  # Replace with actual token
    git_token = GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.TOKEN,
        auth_token=token,
        auto_push=False
    )
    print(f"   Initialized with token auth\n")
    
    # Method 3: None (for local testing)
    print("3. No Authentication (local only)")
    git_none = GitIntegration(
        repo_path=str(repo_path),
        auth_method=AuthMethod.NONE,
        auto_push=False
    )
    print(f"   Initialized with no auth\n")


def example_improvement_report():
    """Example of committing improvement report."""
    print("=== Improvement Report Commit ===\n")
    
    repo_path = Path.cwd()
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False
    )
    
    # Create improvement report
    report = {
        "total_tasks": 100,
        "baseline_success_rate": 0.70,
        "current_success_rate": 0.88,
        "relative_improvement": 0.18,  # 18% improvement
        "execution_time_improvement": 0.12,
        "reasoning_accuracy_improvement": 0.15,
        "timestamp": datetime.now().isoformat(),
        "confidence_interval": [0.15, 0.21]
    }
    
    print("Committing improvement report...")
    print(f"  Improvement: {report['relative_improvement'] * 100:.1f}%")
    print(f"  Tasks completed: {report['total_tasks']}")
    
    success = git_integration.commit_improvement_report(
        report,
        push=False
    )
    
    if success:
        print("✅ Improvement report committed successfully\n")
    else:
        print("❌ Commit failed\n")


def example_offline_queue():
    """Example of offline queue functionality."""
    print("=== Offline Queue Management ===\n")
    
    repo_path = Path.cwd()
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False,
        max_retries=3,
        initial_backoff=1.0
    )
    
    print(f"Initial queue size: {git_integration.get_queue_size()}")
    
    # Simulate offline operation
    print("\nSimulating offline commits...")
    
    for i in range(3):
        execution = TaskExecution(
            task_id=f"offline_task_{i}",
            task_type="test_type",
            strategy_id="test_strategy",
            timestamp=datetime.now(),
            success=True,
            execution_time_ms=100.0,
            failure_type=None,
            error_details=None,
            context={}
        )
        
        # Commits will be queued if push fails
        git_integration.commit_execution_data(execution, push=False)
    
    print(f"Queue size after commits: {git_integration.get_queue_size()}")
    
    # Process queue when back online
    print("\nProcessing queued commits...")
    processed = git_integration.process_queue()
    print(f"Processed {processed} commits")
    print(f"Remaining in queue: {git_integration.get_queue_size()}\n")


def example_retry_logic():
    """Example of retry logic with exponential backoff."""
    print("=== Retry Logic with Exponential Backoff ===\n")
    
    repo_path = Path.cwd()
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False,
        max_retries=5,
        initial_backoff=1.0,  # Start with 1 second
        max_backoff=60.0      # Max 60 seconds
    )
    
    print("Retry configuration:")
    print(f"  Max retries: {git_integration.max_retries}")
    print(f"  Initial backoff: {git_integration.initial_backoff}s")
    print(f"  Max backoff: {git_integration.max_backoff}s")
    print("\nBackoff progression:")
    print("  Retry 1: 1.0s")
    print("  Retry 2: 2.0s")
    print("  Retry 3: 4.0s")
    print("  Retry 4: 8.0s")
    print("  Retry 5: 16.0s")
    print("\nAfter max retries, commit is queued for later\n")


def example_online_status():
    """Example of checking online status."""
    print("=== Online Status Check ===\n")
    
    repo_path = Path.cwd()
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False
    )
    
    print("Checking if Git remote is accessible...")
    is_online = git_integration.is_online()
    
    if is_online:
        print("✅ Remote is accessible")
        print("   Safe to push commits\n")
    else:
        print("❌ Remote is not accessible")
        print("   Commits will be queued\n")


def example_failure_commit():
    """Example of committing failed execution."""
    print("=== Failed Execution Commit ===\n")
    
    repo_path = Path.cwd()
    
    git_integration = GitIntegration(
        repo_path=str(repo_path),
        auto_push=False
    )
    
    # Create failed execution
    execution = TaskExecution(
        task_id="failed_task_001",
        task_type="complex_reasoning",
        strategy_id="strategy_v2",
        timestamp=datetime.now(),
        success=False,
        execution_time_ms=500.0,
        failure_type=FailureType.REASONING_ERROR,
        error_details={
            "reasoning_step": "step_3",
            "error": "Invalid logical inference"
        },
        context={"complexity": "high"}
    )
    
    print("Committing failed execution...")
    print(f"  Task: {execution.task_type}")
    print(f"  Failure: {execution.failure_type.value}")
    
    success = git_integration.commit_execution_data(
        execution,
        push=False
    )
    
    if success:
        print("✅ Failure data committed for learning\n")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Git Integration Examples")
    print("="*60 + "\n")
    
    try:
        example_basic_usage()
        example_with_authentication()
        example_improvement_report()
        example_offline_queue()
        example_retry_logic()
        example_online_status()
        example_failure_commit()
        
        print("="*60)
        print("All examples completed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Note: Some examples require a valid Git repository")


if __name__ == "__main__":
    main()
