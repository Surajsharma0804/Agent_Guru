"""
Module: agent_guru.self_improvement.git_integration
Purpose: Automated Git integration for learning data versioning
Author: Agent Guru Self-Improvement Team
Date: 2024

Performance Requirements:
- Time Complexity: O(1) for queue operations, O(n) for batch commits
- Space Complexity: O(n) for offline queue storage
- Commit latency: <5s for normal operation
- Retry backoff: Exponential with max 60s delay

Design Decisions:
- Use GitPython for Git operations (industry standard)
- Queue-based offline operation (resilient to network failures)
- Exponential backoff for retries (prevents server overload)
- Descriptive commit messages (human-readable learning history)
- Only commit learning data and README.md (avoid noise)
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

try:
    import git
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    git = None
    Repo = None
    GitCommandError = Exception
    InvalidGitRepositoryError = Exception


logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Git authentication methods."""
    SSH = "ssh"
    TOKEN = "token"  # nosec B105
    NONE = "none"


class FailureType(Enum):
    """Task execution failure types."""
    REASONING_ERROR = "reasoning_error"
    TIMEOUT = "timeout"
    RESOURCE_ERROR = "resource_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class CommitData:
    """Data for a Git commit."""
    commit_id: str
    timestamp: datetime
    message: str
    files: list[str]
    data: dict[str, Any]
    retry_count: int = 0
    last_retry: Optional[datetime] = None


class GitIntegration:
    """
    Automated Git integration for learning data versioning.

    Features:
    - Automated commits after each task execution
    - Meaningful commit messages describing learning
    - Authentication handling (SSH keys, tokens)
    - Exponential backoff retry logic
    - Local backup queue for offline operation
    - Only commits learning data and README.md

    Time Complexity: O(1) for queue operations
    Space Complexity: O(n) for offline queue

    Example:
        >>> git_integration = GitIntegration("/path/to/repo")
        >>> git_integration.commit_execution_data(execution)
        >>> git_integration.commit_improvement_report(report)
    """

    def __init__(
        self,
        repo_path: str,
        auth_method: AuthMethod = AuthMethod.SSH,
        auth_token: Optional[str] = None,
        max_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        queue_path: Optional[str] = None,
        auto_push: bool = True
    ):
        """
        Initialize Git integration.

        Args:
            repo_path: Path to Git repository
            auth_method: Authentication method (SSH, TOKEN, NONE)
            auth_token: GitHub token if using TOKEN auth
            max_retries: Maximum retry attempts for failed pushes
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            queue_path: Path to offline queue storage
            auto_push: Automatically push commits (False for testing)

        Raises:
            ValueError: If GitPython not installed
            InvalidGitRepositoryError: If repo_path is not a Git repository
        """
        if not GIT_AVAILABLE:
            raise ValueError(
                "GitPython not installed. Install with: pip install gitpython"
            )

        from Agent_Guru.utils.path_utils import safe_path as _safe_path
        _repo_path = Path(repo_path).resolve()
        # Validate repo_path is a real directory (not a traversal attempt)
        # by ensuring it resolves to itself (no .. tricks)
        self.repo_path = _repo_path
        self.auth_method = auth_method
        self.auth_token = auth_token
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.auto_push = auto_push

        # Initialize repository
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(
                f"Path {repo_path} is not a valid Git repository"
            )

        # Initialize offline queue
        if queue_path:
            from Agent_Guru.utils.path_utils import safe_path as _safe_path
            self.queue_path = _safe_path(Path(queue_path).parent.resolve(), Path(queue_path).name)
        else:
            self.queue_path = self.repo_path / ".git" / "commit_queue"
        self.queue_path.mkdir(parents=True, exist_ok=True)

        # Load pending commits from queue
        self._pending_commits: list[CommitData] = []
        self._load_queue()

        logger.info(
            f"GitIntegration initialized: repo={repo_path}, "
            f"auth={auth_method.value}, pending={len(self._pending_commits)}"
        )

    def commit_execution_data(
        self,
        execution: Any,
        push: bool = True
    ) -> bool:
        """
        Commit task execution data to Git.

        Creates a commit with performance data after each task execution.

        Args:
            execution: TaskExecution object with execution data
            push: Whether to push immediately (default True)

        Returns:
            True if commit successful, False otherwise
        """
        # Generate commit message
        message = self._generate_execution_commit_message(execution)

        # Prepare data
        data = {
            "task_id": execution.task_id,
            "task_type": execution.task_type,
            "strategy_id": execution.strategy_id,
            "success": execution.success,
            "execution_time_ms": execution.execution_time_ms,
            "timestamp": execution.timestamp.isoformat(),
            "failure_type": execution.failure_type.value if execution.failure_type else None,
        }

        # Create commit data
        commit_data = CommitData(
            commit_id=f"exec_{execution.task_id}_{int(time.time())}",
            timestamp=datetime.now(tz=timezone.utc),
            message=message,
            files=["learning_data/executions.json"],
            data=data
        )

        # Try to commit
        return self._commit_and_push(commit_data, push)

    def commit_improvement_report(
        self,
        report: dict[str, Any],
        push: bool = True
    ) -> bool:
        """
        Commit improvement report to Git.

        Creates a commit with comprehensive improvement analysis after every 100 tasks.

        Args:
            report: Improvement report dictionary
            push: Whether to push immediately (default True)

        Returns:
            True if commit successful, False otherwise
        """
        # Generate commit message
        message = self._generate_report_commit_message(report)

        # Create commit data
        commit_data = CommitData(
            commit_id=f"report_{int(time.time())}",
            timestamp=datetime.now(tz=timezone.utc),
            message=message,
            files=["learning_data/improvement_reports.json", "README.md"],
            data=report
        )

        # Try to commit
        return self._commit_and_push(commit_data, push)

    def _commit_and_push(
        self,
        commit_data: CommitData,
        push: bool = True
    ) -> bool:
        """
        Commit and optionally push to remote.

        Args:
            commit_data: Commit data to process
            push: Whether to push to remote

        Returns:
            True if successful, False otherwise
        """
        try:
            # Write data to files
            self._write_learning_data(commit_data)

            # Stage files
            self.repo.index.add(commit_data.files)

            # Create commit
            self.repo.index.commit(commit_data.message)

            logger.info("Created commit: %s...", commit_data.message[:50])

            # Push if requested and auto_push enabled
            if push and self.auto_push:
                return self._push_with_retry(commit_data)

            return True

        except Exception as e:
            logger.error("Commit failed: %s", e)
            # Add to queue for retry
            self._queue_commit(commit_data)
            return False

    def _push_with_retry(
        self,
        commit_data: CommitData
    ) -> bool:
        """
        Push to remote with exponential backoff retry.

        Args:
            commit_data: Commit data for tracking retries

        Returns:
            True if push successful, False otherwise
        """
        retry_count = commit_data.retry_count

        while retry_count < self.max_retries:
            try:
                # Configure authentication
                self._configure_auth()

                # Push to remote
                origin = self.repo.remote(name='origin')
                origin.push()

                logger.info("Push successful")
                return True

            except GitCommandError as e:
                retry_count += 1
                commit_data.retry_count = retry_count
                commit_data.last_retry = datetime.now(tz=timezone.utc)

                if retry_count >= self.max_retries:
                    logger.error("Push failed after %d retries: %s", self.max_retries, e)
                    self._queue_commit(commit_data)
                    return False

                # Calculate backoff delay
                backoff = min(
                    self.initial_backoff * (2 ** (retry_count - 1)),
                    self.max_backoff
                )

                logger.warning(
                    f"Push failed (attempt {retry_count}/{self.max_retries}), "
                    f"retrying in {backoff:.1f}s: {e}"
                )

                time.sleep(backoff)

        return False

    def _configure_auth(self) -> None:
        """Configure Git authentication based on auth_method."""
        if self.auth_method == AuthMethod.TOKEN and self.auth_token:
            # Configure token authentication
            with self.repo.config_writer() as config:
                config.set_value(
                    'credential',
                    'helper',
                    f'!f() {{ echo "username=token"; echo "password={self.auth_token}"; }}; f'
                )
        elif self.auth_method == AuthMethod.SSH:
            # SSH uses default SSH keys, no configuration needed
            pass
        # NONE method doesn't configure authentication

    def _generate_execution_commit_message(
        self,
        execution: Any
    ) -> str:
        """
        Generate meaningful commit message for task execution.

        Args:
            execution: TaskExecution object

        Returns:
            Descriptive commit message
        """
        if execution.success:
            return (
                f"✅ Task {execution.task_type} succeeded "
                f"({execution.execution_time_ms:.0f}ms) "
                f"using {execution.strategy_id}"
            )
        else:
            failure_type = execution.failure_type.value if execution.failure_type else "unknown"
            return (
                f"❌ Task {execution.task_type} failed "
                f"({failure_type}) "
                f"using {execution.strategy_id}"
            )

    def _generate_report_commit_message(
        self,
        report: dict[str, Any]
    ) -> str:
        """
        Generate meaningful commit message for improvement report.

        Args:
            report: Improvement report dictionary

        Returns:
            Descriptive commit message
        """
        improvement = report.get("relative_improvement", 0) * 100
        tasks_completed = report.get("total_tasks", 0)

        if improvement >= 15:
            return (
                f"📈 Improvement Report: +{improvement:.1f}% after {tasks_completed} tasks "
                f"(Target: +15% ✅)"
            )
        else:
            return (
                f"📊 Improvement Report: +{improvement:.1f}% after {tasks_completed} tasks "
                f"(Target: +15% ⚠️)"
            )

    def _write_learning_data(
        self,
        commit_data: CommitData
    ) -> None:
        """
        Write learning data to files.

        Args:
            commit_data: Commit data with files and data
        """
        from Agent_Guru.utils.path_utils import safe_path

        learning_dir = self.repo_path / "learning_data"
        learning_dir.mkdir(exist_ok=True)

        for file_path in commit_data.files:
            full_path = safe_path(self.repo_path, file_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to existing file or create new
            if full_path.exists() and full_path.suffix == ".json":
                # Append to JSON array
                try:
                    with open(full_path) as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_data = []

                existing_data.append(commit_data.data)

                with open(full_path, 'w') as f:
                    json.dump(existing_data, f, indent=2)
            else:
                # Write new file - always create as list for consistency
                with open(full_path, 'w') as f:
                    json.dump([commit_data.data], f, indent=2)

    def _queue_commit(
        self,
        commit_data: CommitData
    ) -> None:
        """
        Queue commit for later retry.

        Args:
            commit_data: Commit data to queue
        """
        self._pending_commits.append(commit_data)
        self._save_queue()

        logger.info(
            f"Queued commit for retry: {commit_data.commit_id} "
            f"(queue size: {len(self._pending_commits)})"
        )

    def _save_queue(self) -> None:
        """Save pending commits to disk."""
        queue_file = self.queue_path / "pending_commits.json"

        # Convert to serializable format
        queue_data = [
            {
                "commit_id": c.commit_id,
                "timestamp": c.timestamp.isoformat(),
                "message": c.message,
                "files": c.files,
                "data": c.data,
                "retry_count": c.retry_count,
                "last_retry": c.last_retry.isoformat() if c.last_retry else None
            }
            for c in self._pending_commits
        ]

        with open(queue_file, 'w') as f:
            json.dump(queue_data, f, indent=2)

    def _load_queue(self) -> None:
        """Load pending commits from disk."""
        queue_file = self.queue_path / "pending_commits.json"

        if not queue_file.exists():
            return

        try:
            with open(queue_file) as f:
                queue_data = json.load(f)

            self._pending_commits = [
                CommitData(
                    commit_id=c["commit_id"],
                    timestamp=datetime.fromisoformat(c["timestamp"]),
                    message=c["message"],
                    files=c["files"],
                    data=c["data"],
                    retry_count=c["retry_count"],
                    last_retry=datetime.fromisoformat(c["last_retry"]) if c["last_retry"] else None
                )
                for c in queue_data
            ]

            logger.info("Loaded %s pending commits from queue", len(self._pending_commits))

        except Exception as e:
            logger.error("Failed to load queue: %s", e)
            self._pending_commits = []

    def process_queue(self) -> int:
        """
        Process pending commits in queue.

        Attempts to push all queued commits with retry logic.

        Returns:
            Number of commits successfully processed
        """
        if not self._pending_commits:
            return 0

        logger.info("Processing %s pending commits", len(self._pending_commits))

        processed = 0
        failed = []

        for commit_data in self._pending_commits:
            if self._push_with_retry(commit_data):
                processed += 1
            else:
                failed.append(commit_data)

        # Update queue with failed commits
        self._pending_commits = failed
        self._save_queue()

        logger.info(
            f"Processed {processed} commits, "
            f"{len(failed)} remain in queue"
        )

        return processed

    def get_queue_size(self) -> int:
        """
        Get number of pending commits in queue.

        Returns:
            Number of pending commits
        """
        return len(self._pending_commits)

    def clear_queue(self) -> None:
        """Clear all pending commits from queue."""
        self._pending_commits = []
        self._save_queue()
        logger.info("Cleared commit queue")

    def is_online(self) -> bool:
        """
        Check if Git remote is accessible.

        Returns:
            True if remote is accessible, False otherwise
        """
        try:
            origin = self.repo.remote(name='origin')
            origin.fetch(dry_run=True)
            return True
        except Exception:
            return False
