"""
Module: agent_guru.platform.github.integrator
Purpose: Core GitHub integration for automated Git operations

This module implements the GitHubIntegrator class that provides:
- Git repository operations (status, add, commit, push, pull, rebase)
- Automatic commit and push workflows
- Conflict detection and resolution
- Repository state validation
- Authentication handling

Performance Requirements:
- Time Complexity: O(n) for n changed files
- Space Complexity: O(n) for file list storage
- Status check: <1s
- Commit+push: <5s (network dependent)

Design Decisions:
- Use subprocess for Git commands (standard, reliable)
- Validate repository state before operations
- Implement retry logic for network operations
- Support both SSH and HTTPS authentication
- Provide detailed error messages with remediation

Author: Agent Guru Platform Team
Date: 2025
Version: 1.0.0
"""

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .message_generator import CommitMessageGenerator, CommitMessageTemplate, TaskContext

logger = logging.getLogger(__name__)


# Custom Exceptions

class GitError(Exception):
    """Base exception for Git operations."""


class GitConflictError(GitError):
    """Raised when Git conflicts are detected."""


class GitAuthenticationError(GitError):
    """Raised when Git authentication fails."""


class GitRemoteError(GitError):
    """Raised when remote operations fail."""


class GitRepositoryError(GitError):
    """Raised when repository is in invalid state."""


# Data Models

@dataclass
class GitOperationResult:
    """Result of a Git operation.

    Attributes:
        success: Whether operation succeeded
        message: Human-readable message
        stdout: Command stdout
        stderr: Command stderr
        return_code: Process return code
        duration_ms: Operation duration in milliseconds
    """
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration_ms: float = 0.0


@dataclass
class GitRepositoryStatus:
    """Current status of Git repository.

    Attributes:
        is_repo: Whether directory is a Git repository
        has_remote: Whether remote is configured
        current_branch: Current branch name
        is_clean: Whether working directory is clean
        staged_files: List of staged files
        unstaged_files: List of unstaged files
        untracked_files: List of untracked files
        ahead_count: Number of commits ahead of remote
        behind_count: Number of commits behind remote
    """
    is_repo: bool
    has_remote: bool
    current_branch: str
    is_clean: bool
    staged_files: list[str] = field(default_factory=list)
    unstaged_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    ahead_count: int = 0
    behind_count: int = 0


@dataclass
class PullRequestResult:
    """Result of pull request creation.

    Attributes:
        success: Whether PR was created successfully
        pr_number: Pull request number
        pr_url: URL to the pull request
        message: Human-readable message
        error: Error message if failed
    """
    success: bool
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class BranchInfo:
    """Information about a Git branch.

    Attributes:
        name: Branch name
        exists_locally: Whether branch exists locally
        exists_remotely: Whether branch exists on remote
        is_current: Whether this is the current branch
        commit_hash: Latest commit hash
    """
    name: str
    exists_locally: bool
    exists_remotely: bool
    is_current: bool
    commit_hash: Optional[str] = None

    @dataclass
    class PullRequestResult:
        """Result of pull request creation.

        Attributes:
            success: Whether PR was created successfully
            pr_number: Pull request number
            pr_url: URL to the pull request
            message: Human-readable message
            error: Error message if failed
        """
        success: bool
        pr_number: Optional[int] = None
        pr_url: Optional[str] = None
        message: str = ""
        error: Optional[str] = None


    @dataclass
    class BranchInfo:
        """Information about a Git branch.

        Attributes:
            name: Branch name
            exists_locally: Whether branch exists locally
            exists_remotely: Whether branch exists on remote
            is_current: Whether this is the current branch
            commit_hash: Latest commit hash
        """
        name: str
        exists_locally: bool
        exists_remotely: bool
        is_current: bool
        commit_hash: Optional[str] = None



class GitHubIntegrator:
    """
    Automated Git operations for Agent Guru.

    Provides comprehensive Git repository management including:
    - Repository status checking
    - File staging and committing
    - Push to remote with retry
    - Pull and rebase for conflict resolution
    - Branch management

    Time Complexity: O(n) where n is number of changed files
    Space Complexity: O(n) for file list storage

    Example:
        >>> integrator = GitHubIntegrator("/path/to/repo")
        >>> status = integrator.get_status()
        >>> if not status.is_clean:
        ...     result = integrator.commit_and_push(
        ...         message="feat: Add new feature",
        ...         files=["file1.py", "file2.py"]
        ...     )
        ...     print(f"Commit successful: {result.success}")

    Performance Benchmarks:
        - Status check: ~100ms (local operation)
        - Commit: ~200ms (local operation)
        - Push: ~2-5s (network dependent)
        - Pull+rebase: ~3-8s (network dependent)
    """

    def __init__(
        self,
        repo_path: str,
        remote_name: str = "origin",
        default_branch: str = "main",
        max_retries: int = 3,
        timeout: int = 30
    ) -> None:
        """Initialize GitHub integrator.

        Args:
            repo_path: Path to Git repository
            remote_name: Name of remote (default: "origin")
            default_branch: Default branch name (default: "main")
            max_retries: Maximum retry attempts for network operations
            timeout: Command timeout in seconds

        Raises:
            ValueError: If repo_path is invalid
            GitRepositoryError: If not a valid Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self.remote_name = remote_name
        self.default_branch = default_branch
        self.max_retries = max_retries
        self.timeout = timeout

        # Initialize message generator
        self.message_generator = CommitMessageGenerator(repo_root=self.repo_path)

        # Validate repository
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        if not self._is_git_repository():
            raise GitRepositoryError(
                f"Not a Git repository: {repo_path}\n"
                f"Remediation: Run 'git init' or clone a repository"
            )

        logger.info(
            f"GitHubIntegrator initialized: repo={repo_path}, "
            f"remote={remote_name}, branch={default_branch}"
        )

    def get_status(self) -> GitRepositoryStatus:
        """Get current repository status.

        Time Complexity: O(n) where n is number of files
        Space Complexity: O(n) for file lists

        Returns:
            GitRepositoryStatus with current state

        Raises:
            GitError: If status check fails
        """
        try:
            # Check if it's a repository
            is_repo = self._is_git_repository()
            if not is_repo:
                return GitRepositoryStatus(
                    is_repo=False,
                    has_remote=False,
                    current_branch="",
                    is_clean=False
                )

            # Get current branch
            branch_result = self._run_git_command(["branch", "--show-current"])
            current_branch = branch_result.stdout.strip()

            # Check remote
            remote_result = self._run_git_command(["remote", "get-url", self.remote_name])
            has_remote = remote_result.success

            # Get file status
            status_result = self._run_git_command(["status", "--porcelain"])
            staged, unstaged, untracked = self._parse_status_output(status_result.stdout)

            is_clean = not (staged or unstaged or untracked)

            # Get ahead/behind count
            ahead, behind = 0, 0
            if has_remote:
                ahead, behind = self._get_ahead_behind_count(current_branch)

            return GitRepositoryStatus(
                is_repo=True,
                has_remote=has_remote,
                current_branch=current_branch,
                is_clean=is_clean,
                staged_files=staged,
                unstaged_files=unstaged,
                untracked_files=untracked,
                ahead_count=ahead,
                behind_count=behind
            )

        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            raise GitError(f"Status check failed: {e}") from e

    def add_files(self, files: list[str]) -> GitOperationResult:
        """Stage files for commit.

        Time Complexity: O(n) where n is number of files
        Space Complexity: O(1)

        Args:
            files: List of file paths to stage (relative to repo root)

        Returns:
            GitOperationResult with operation status

        Raises:
            ValueError: If files list is empty
            GitError: If staging fails
        """
        if not files:
            raise ValueError("Files list cannot be empty")

        start_time = datetime.now()

        try:
            # Validate files exist
            for file_path in files:
                full_path = self.repo_path / file_path
                if not full_path.exists():
                    logger.warning(f"File does not exist: {file_path}")

            # Stage files
            result = self._run_git_command(["add", *files])

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if result.success:
                return GitOperationResult(
                    success=True,
                    message=f"Staged {len(files)} file(s)",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.return_code,
                    duration_ms=duration_ms
                )
            else:
                raise GitError(f"Failed to stage files: {result.stderr}")

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to add files: {e}")
            return GitOperationResult(
                success=False,
                message=f"Failed to stage files: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    def commit(self, message: str, allow_empty: bool = False) -> GitOperationResult:
        """Create a commit with staged changes.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            message: Commit message
            allow_empty: Allow empty commits

        Returns:
            GitOperationResult with commit hash

        Raises:
            ValueError: If message is empty
            GitError: If commit fails
        """
        if not message or not message.strip():
            raise ValueError("Commit message cannot be empty")

        start_time = datetime.now()

        try:
            # Build commit command
            cmd = ["commit", "-m", message]
            if allow_empty:
                cmd.append("--allow-empty")

            result = self._run_git_command(cmd)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if result.success:
                # Extract commit hash
                commit_hash = self._get_last_commit_hash()
                return GitOperationResult(
                    success=True,
                    message=f"Commit created: {commit_hash[:8]}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.return_code,
                    duration_ms=duration_ms
                )
            else:
                # Check if nothing to commit
                if "nothing to commit" in result.stdout.lower():
                    return GitOperationResult(
                        success=True,
                        message="Nothing to commit (working directory clean)",
                        stdout=result.stdout,
                        duration_ms=duration_ms
                    )
                raise GitError(f"Commit failed: {result.stderr}")

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to commit: {e}")
            return GitOperationResult(
                success=False,
                message=f"Commit failed: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    def push(
        self,
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False
    ) -> GitOperationResult:
        """Push commits to remote repository.

        Time Complexity: O(1) (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to push (default: current branch)
            force: Force push (use with caution)
            set_upstream: Set upstream tracking

        Returns:
            GitOperationResult with push status

        Raises:
            GitRemoteError: If push fails
            GitAuthenticationError: If authentication fails
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            # Build push command
            cmd = ["push", self.remote_name, branch]
            if force:
                cmd.append("--force")
            if set_upstream:
                cmd.insert(1, "--set-upstream")

            # Retry logic for network operations
            last_error = None
            for attempt in range(self.max_retries):
                result = self._run_git_command(cmd)

                if result.success:
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                    return GitOperationResult(
                        success=True,
                        message=f"Pushed to {self.remote_name}/{branch}",
                        stdout=result.stdout,
                        stderr=result.stderr,
                        return_code=result.return_code,
                        duration_ms=duration_ms
                    )

                # Check error type
                stderr_lower = result.stderr.lower()
                if "authentication" in stderr_lower or "permission denied" in stderr_lower:
                    raise GitAuthenticationError(
                        f"Authentication failed: {result.stderr}\n"
                        f"Remediation: Check SSH keys or access token"
                    )

                if "rejected" in result.stderr.lower():
                    raise GitConflictError(
                        f"Push rejected (conflicts): {result.stderr}\n"
                        f"Remediation: Pull and rebase before pushing"
                    )

                last_error = result.stderr
                logger.warning(f"Push attempt {attempt + 1} failed: {last_error}")

            # All retries failed
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            raise GitRemoteError(
                f"Push failed after {self.max_retries} attempts: {last_error}"
            )

        except (GitAuthenticationError, GitConflictError, GitRemoteError):
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to push: {e}")
            return GitOperationResult(
                success=False,
                message=f"Push failed: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    def pull(self, branch: str | None = None, rebase: bool = True) -> GitOperationResult:
        """Pull changes from remote repository.

        Time Complexity: O(1) (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to pull (default: current branch)
            rebase: Use rebase instead of merge

        Returns:
            GitOperationResult with pull status

        Raises:
            GitRemoteError: If pull fails
            GitConflictError: If conflicts detected
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            # Build pull command
            cmd = ["pull", self.remote_name, branch]
            if rebase:
                cmd.append("--rebase")

            result = self._run_git_command(cmd)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if result.success:
                return GitOperationResult(
                    success=True,
                    message=f"Pulled from {self.remote_name}/{branch}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.return_code,
                    duration_ms=duration_ms
                )
            else:
                # Check for conflicts
                if "conflict" in result.stderr.lower() or "conflict" in result.stdout.lower():
                    raise GitConflictError(
                        f"Conflicts detected during pull: {result.stderr}\n"
                        f"Remediation: Resolve conflicts manually"
                    )
                raise GitRemoteError(f"Pull failed: {result.stderr}")

        except (GitConflictError, GitRemoteError):
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to pull: {e}")
            return GitOperationResult(
                success=False,
                message=f"Pull failed: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    def commit_and_push(
        self,
        message: str,
        files: list[str] | None = None,
        branch: str | None = None
    ) -> GitOperationResult:
        """Commit changes and push to remote (convenience method).

        Time Complexity: O(n) where n is number of files
        Space Complexity: O(n) for file list

        Args:
            message: Commit message
            files: Files to commit (None = all changes)
            branch: Branch to push to (None = current branch)

        Returns:
            GitOperationResult with combined operation status
        """
        start_time = datetime.now()

        try:
            # Stage files
            if files:
                add_result = self.add_files(files)
                if not add_result.success:
                    return add_result
            else:
                # Stage all changes
                add_result = self._run_git_command(["add", "-A"])
                if not add_result.success:
                    return GitOperationResult(
                        success=False,
                        message=f"Failed to stage files: {add_result.stderr}",
                        stderr=add_result.stderr
                    )

            # Commit
            commit_result = self.commit(message)
            if not commit_result.success:
                return commit_result

            # Push
            push_result = self.push(branch)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            return GitOperationResult(
                success=push_result.success,
                message=f"Committed and pushed: {commit_result.message}",
                stdout=f"{commit_result.stdout}\n{push_result.stdout}",
                stderr=f"{commit_result.stderr}\n{push_result.stderr}",
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to commit and push: {e}")
            return GitOperationResult(
                success=False,
                message=f"Commit and push failed: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    # Private helper methods

    def _is_git_repository(self) -> bool:
        """Check if directory is a Git repository."""
        git_dir = self.repo_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _run_git_command(
        self,
        args: list[str],
        check: bool = False
    ) -> GitOperationResult:
        """Run a Git command.

        Args:
            args: Git command arguments
            check: Raise exception on non-zero return code

        Returns:
            GitOperationResult with command output
        """
        cmd = ["git", *args]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=check
            )

            return GitOperationResult(
                success=result.returncode == 0,
                message="Command executed",
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode
            )

        except subprocess.TimeoutExpired:
            return GitOperationResult(
                success=False,
                message=f"Command timed out after {self.timeout}s",
                stderr=f"Timeout: {' '.join(cmd)}"
            )
        except Exception as e:
            return GitOperationResult(
                success=False,
                message=f"Command failed: {e}",
                stderr=str(e)
            )

    def _parse_status_output(self, output: str) -> tuple[list[str], list[str], list[str]]:
        """Parse git status --porcelain output.

        Returns:
            Tuple of (staged, unstaged, untracked) file lists
        """
        staged = []
        unstaged = []
        untracked = []

        for line in output.splitlines():
            if not line:
                continue

            status_code = line[:2]
            file_path = line[3:].strip()

            # Staged files (first character)
            if status_code[0] in ('A', 'M', 'D', 'R', 'C'):
                staged.append(file_path)

            # Unstaged files (second character)
            if status_code[1] in ('M', 'D'):
                unstaged.append(file_path)

            # Untracked files
            if status_code == '??':
                untracked.append(file_path)

        return staged, unstaged, untracked

    def _get_ahead_behind_count(self, branch: str) -> tuple[int, int]:
        """Get number of commits ahead/behind remote.

        Returns:
            Tuple of (ahead_count, behind_count)
        """
        try:
            # Fetch remote refs
            self._run_git_command(["fetch", self.remote_name, "--quiet"])

            # Get ahead count
            ahead_result = self._run_git_command([
                "rev-list",
                "--count",
                f"{self.remote_name}/{branch}..HEAD"
            ])
            ahead = int(ahead_result.stdout.strip()) if ahead_result.success else 0

            # Get behind count
            behind_result = self._run_git_command([
                "rev-list",
                "--count",
                f"HEAD..{self.remote_name}/{branch}"
            ])
            behind = int(behind_result.stdout.strip()) if behind_result.success else 0

            return ahead, behind

        except Exception as e:
            logger.warning(f"Failed to get ahead/behind count: {e}")
            return 0, 0

    def _get_last_commit_hash(self) -> str:
        """Get hash of last commit."""
        result = self._run_git_command(["rev-parse", "HEAD"])
        return result.stdout.strip() if result.success else ""

    def generate_commit_message(
        self,
        task_id: str,
        task_description: str,
        changed_files: Optional[list[str]] = None,
        task_type: str = "Task"
    ) -> str:
        """Generate descriptive commit message from task context.

        Time Complexity: O(n) where n is number of changed files
        Space Complexity: O(n) for file analysis

        Args:
            task_id: Task identifier (e.g., "24.3")
            task_description: Human-readable task description
            changed_files: List of changed files (None = auto-detect)
            task_type: Type of task (Task, Feature, Bugfix, etc.)

        Returns:
            Formatted commit message

        Raises:
            ValueError: If task_id or task_description is empty
            GitError: If auto-detection fails

        Example:
            >>> integrator = GitHubIntegrator("/path/to/repo")
            >>> message = integrator.generate_commit_message(
            ...     task_id="24.3",
            ...     task_description="Implement commit message generation",
            ...     task_type="Task"
            ... )
            >>> print(message)
            [Task 24.3] Implement commit message generation

            Changes:
            - 1 file(s) changed
            - Components: github
            - File types: .py

            Auto-committed by Agent_Guru
        """
        # Validate inputs
        if not task_id or not task_id.strip():
            raise ValueError("Task ID cannot be empty")
        if not task_description or not task_description.strip():
            raise ValueError("Task description cannot be empty")

        # Auto-detect changed files if not provided
        if changed_files is None:
            status = self.get_status()
            changed_files = (
                status.staged_files +
                status.unstaged_files +
                status.untracked_files
            )

            if not changed_files:
                raise GitError(
                    "No changed files detected. "
                    "Remediation: Make changes or provide file list explicitly"
                )

        # Build file stats for better analysis
        file_stats = self._get_file_stats(changed_files)

        # Create task context
        context = TaskContext(
            task_id=task_id,
            task_description=task_description,
            task_type=task_type
        )

        # Generate message
        message = self.message_generator.generate_message(
            context=context,
            changed_files=changed_files,
            file_stats=file_stats
        )

        logger.info(
            f"Generated commit message: task_id={task_id}, "
            f"files={len(changed_files)}"
        )

        return message

    def set_message_template(self, template: CommitMessageTemplate) -> None:
        """Set custom commit message template.

        Args:
            template: Custom message template

        Example:
            >>> from agent_guru.platform.github.message_generator import DETAILED_TEMPLATE
            >>> integrator.set_message_template(DETAILED_TEMPLATE)
        """
        self.message_generator.set_template(template)
        logger.info("Commit message template updated")

    def auto_commit_and_push(
        self,
        task_id: str,
        task_description: str,
        changed_files: Optional[list[str]] = None,
        task_type: str = "Task",
        branch: Optional[str] = None
    ) -> GitOperationResult:
        """Automatically generate commit message, commit, and push.

        Convenience method that combines message generation with commit and push.

        Time Complexity: O(n) where n is number of files
        Space Complexity: O(n) for file list

        Args:
            task_id: Task identifier
            task_description: Task description
            changed_files: Files to commit (None = all changes)
            task_type: Type of task
            branch: Branch to push to (None = current branch)

        Returns:
            GitOperationResult with combined operation status

        Example:
            >>> result = integrator.auto_commit_and_push(
            ...     task_id="24.3",
            ...     task_description="Implement commit message generation",
            ...     task_type="Task"
            ... )
            >>> print(f"Success: {result.success}")
        """
        try:
            # Generate commit message
            message = self.generate_commit_message(
                task_id=task_id,
                task_description=task_description,
                changed_files=changed_files,
                task_type=task_type
            )

            # Commit and push
            return self.commit_and_push(
                message=message,
                files=changed_files,
                branch=branch
            )

        except Exception as e:
            logger.error(f"Auto commit and push failed: {e}")
            return GitOperationResult(
                success=False,
                message=f"Auto commit and push failed: {e}",
                stderr=str(e)
            )

    def _get_file_stats(self, files: list[str]) -> dict[str, str]:
        """Get file status for each file (A=added, M=modified, D=deleted).

        Args:
            files: List of file paths

        Returns:
            Dict mapping file path to status code
        """
        file_stats = {}

        try:
            # Get status for all files
            status_result = self._run_git_command(["status", "--porcelain"])

            if status_result.success:
                for line in status_result.stdout.splitlines():
                    if not line:
                        continue

                    status_code = line[:2].strip()
                    file_path = line[3:].strip()

                    # Map status codes
                    if status_code in ('A', 'AM'):
                        file_stats[file_path] = 'A'
                    elif status_code in ('D', 'AD'):
                        file_stats[file_path] = 'D'
                    elif status_code in ('M', 'MM', '??'):
                        file_stats[file_path] = 'M'
                    else:
                        file_stats[file_path] = 'M'  # Default to modified

            # Fill in missing files with default status
            for file_path in files:
                if file_path not in file_stats:
                    file_stats[file_path] = 'M'

        except Exception as e:
            logger.warning(f"Failed to get file stats: {e}")
            # Return default stats
            file_stats = dict.fromkeys(files, 'M')

        return file_stats

    def detect_conflicts(self) -> tuple[bool, list[str]]:
        """Detect if there are merge conflicts in the repository.

        Time Complexity: O(n) where n is number of conflicted files
        Space Complexity: O(n) for conflict list

        Returns:
            Tuple of (has_conflicts, conflicted_files)
            - has_conflicts: True if conflicts exist
            - conflicted_files: List of files with conflicts

        Example:
            >>> has_conflicts, files = integrator.detect_conflicts()
            >>> if has_conflicts:
            ...     print(f"Conflicts in: {files}")
        """
        try:
            # Check for conflict markers in status
            status_result = self._run_git_command(["status", "--porcelain"])

            if not status_result.success:
                logger.warning("Failed to check conflict status")
                return False, []

            conflicted_files = []

            for line in status_result.stdout.splitlines():
                if not line:
                    continue

                status_code = line[:2]
                file_path = line[3:].strip()

                # Check for conflict markers (UU, AA, DD, AU, UA, DU, UD)
                if status_code in ('UU', 'AA', 'DD', 'AU', 'UA', 'DU', 'UD'):
                    conflicted_files.append(file_path)

            has_conflicts = len(conflicted_files) > 0

            if has_conflicts:
                logger.warning(f"Detected {len(conflicted_files)} conflicted file(s)")

            return has_conflicts, conflicted_files

        except Exception as e:
            logger.error(f"Failed to detect conflicts: {e}")
            return False, []

    def resolve_conflicts_with_rebase(
        self,
        branch: Optional[str] = None,
        max_attempts: int = 3
    ) -> GitOperationResult:
        """Attempt to resolve conflicts using pull-rebase strategy.

        This method implements the conflict resolution workflow:
        1. Detect if conflicts exist
        2. Attempt pull with rebase
        3. If conflicts occur, abort and retry
        4. Retry up to max_attempts times
        5. If all attempts fail, notify and return error

        Time Complexity: O(1) per attempt (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to pull from (None = current branch)
            max_attempts: Maximum retry attempts (default: 3)

        Returns:
            GitOperationResult with resolution status

        Raises:
            GitConflictError: If conflicts cannot be resolved automatically

        Example:
            >>> result = integrator.resolve_conflicts_with_rebase()
            >>> if result.success:
            ...     print("Conflicts resolved successfully")
            ... else:
            ...     print(f"Failed to resolve: {result.message}")
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            logger.info(
                f"Starting conflict resolution: branch={branch}, "
                f"max_attempts={max_attempts}"
            )

            # Check if conflicts already exist
            has_conflicts, conflicted_files = self.detect_conflicts()
            if has_conflicts:
                logger.warning(
                    f"Existing conflicts detected in {len(conflicted_files)} file(s): "
                    f"{', '.join(conflicted_files[:5])}"
                )
                # Abort any in-progress rebase
                self._run_git_command(["rebase", "--abort"])

            # Attempt pull-rebase with retry logic
            last_error = None
            attempt_details = []

            for attempt in range(1, max_attempts + 1):
                logger.info(f"Conflict resolution attempt {attempt}/{max_attempts}")

                try:
                    # Fetch latest changes
                    fetch_result = self._run_git_command([
                        "fetch",
                        self.remote_name,
                        branch
                    ])

                    if not fetch_result.success:
                        error_msg = f"Fetch failed: {fetch_result.stderr}"
                        attempt_details.append(f"Attempt {attempt}: {error_msg}")
                        last_error = error_msg
                        logger.warning(error_msg)
                        continue

                    # Attempt pull with rebase
                    pull_result = self._run_git_command([
                        "pull",
                        "--rebase",
                        self.remote_name,
                        branch
                    ])

                    if pull_result.success:
                        # Success! Check if there are any remaining conflicts
                        has_conflicts, _ = self.detect_conflicts()
                        if not has_conflicts:
                            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                            logger.info(
                                f"Conflict resolution successful on attempt {attempt}"
                            )
                            return GitOperationResult(
                                success=True,
                                message=f"Conflicts resolved successfully (attempt {attempt}/{max_attempts})",
                                stdout=pull_result.stdout,
                                stderr=pull_result.stderr,
                                return_code=pull_result.return_code,
                                duration_ms=duration_ms
                            )

                    # Check for conflicts in output
                    stderr_lower = pull_result.stderr.lower()
                    stdout_lower = pull_result.stdout.lower()

                    if "conflict" in stderr_lower or "conflict" in stdout_lower:
                        # Conflicts detected - abort rebase
                        logger.warning(f"Conflicts detected on attempt {attempt}")
                        self._run_git_command(["rebase", "--abort"])

                        error_msg = f"Conflicts during rebase: {pull_result.stderr}"
                        attempt_details.append(f"Attempt {attempt}: {error_msg}")
                        last_error = error_msg

                        # Wait before retry (exponential backoff)
                        if attempt < max_attempts:
                            import time
                            wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                            logger.info(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)

                        continue

                    # Other error
                    error_msg = f"Pull-rebase failed: {pull_result.stderr}"
                    attempt_details.append(f"Attempt {attempt}: {error_msg}")
                    last_error = error_msg
                    logger.warning(error_msg)

                except Exception as e:
                    error_msg = f"Exception during attempt: {str(e)}"
                    attempt_details.append(f"Attempt {attempt}: {error_msg}")
                    last_error = str(e)
                    logger.error(error_msg)

            # All attempts failed
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Build detailed error message
            error_details = "\n".join(attempt_details)
            error_message = (
                f"Failed to resolve conflicts after {max_attempts} attempts.\n\n"
                f"Attempt details:\n{error_details}\n\n"
                f"Last error: {last_error}\n\n"
                f"Remediation:\n"
                f"1. Manually resolve conflicts in the repository\n"
                f"2. Check for uncommitted changes that may be causing issues\n"
                f"3. Verify network connectivity to remote repository\n"
                f"4. Contact repository administrator if access issues persist"
            )

            logger.error(error_message)

            # Notify Goal Manager (if available)
            self._notify_goal_manager_of_failure(
                operation="conflict_resolution",
                error_message=error_message,
                attempt_count=max_attempts
            )

            raise GitConflictError(error_message)

        except GitConflictError:
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = f"Conflict resolution failed with exception: {e}"
            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="conflict_resolution",
                error_message=error_message,
                attempt_count=max_attempts
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=str(e),
                duration_ms=duration_ms
            )

    def push_with_conflict_resolution(
        self,
        branch: Optional[str] = None,
        force: bool = False,
        max_retries: int = 3
    ) -> GitOperationResult:
        """Push with automatic conflict resolution using pull-rebase.

        This method implements the complete push workflow with conflict handling:
        1. Attempt push
        2. If rejected due to conflicts, pull-rebase
        3. Retry push
        4. Repeat up to max_retries times

        Time Complexity: O(1) per attempt (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to push (None = current branch)
            force: Force push (use with caution)
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            GitOperationResult with push status

        Example:
            >>> result = integrator.push_with_conflict_resolution()
            >>> if result.success:
            ...     print("Pushed successfully")
            ... else:
            ...     print(f"Push failed: {result.message}")
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            logger.info(
                f"Starting push with conflict resolution: branch={branch}, "
                f"max_retries={max_retries}"
            )

            last_error = None

            for attempt in range(1, max_retries + 1):
                logger.info(f"Push attempt {attempt}/{max_retries}")

                try:
                    # Attempt push
                    push_result = self.push(branch=branch, force=force)

                    if push_result.success:
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                        logger.info(f"Push successful on attempt {attempt}")
                        return GitOperationResult(
                            success=True,
                            message=f"Pushed successfully (attempt {attempt}/{max_retries})",
                            stdout=push_result.stdout,
                            stderr=push_result.stderr,
                            return_code=push_result.return_code,
                            duration_ms=duration_ms
                        )

                    # Check if rejection is due to conflicts
                    stderr_lower = push_result.stderr.lower()
                    if "rejected" in stderr_lower and not force:
                        logger.warning(
                            f"Push rejected on attempt {attempt}, attempting conflict resolution"
                        )

                        # Attempt conflict resolution
                        resolve_result = self.resolve_conflicts_with_rebase(
                            branch=branch,
                            max_attempts=2  # Fewer attempts for nested resolution
                        )

                        if not resolve_result.success:
                            last_error = resolve_result.message
                            logger.error(f"Conflict resolution failed: {last_error}")
                            continue

                        # Conflict resolved, retry push on next iteration
                        logger.info("Conflict resolved, will retry push")
                        continue

                    # Other push error
                    last_error = push_result.message
                    logger.warning(f"Push failed on attempt {attempt}: {last_error}")

                except GitAuthenticationError as e:
                    # Don't retry authentication errors
                    logger.error(f"Authentication error: {e}")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Exception during push attempt {attempt}: {e}")

            # All attempts failed
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = (
                f"Push failed after {max_retries} attempts.\n"
                f"Last error: {last_error}\n\n"
                f"Remediation:\n"
                f"1. Check network connectivity\n"
                f"2. Verify repository permissions\n"
                f"3. Manually resolve any conflicts\n"
                f"4. Try force push if appropriate (use with caution)"
            )

            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="push_with_conflict_resolution",
                error_message=error_message,
                attempt_count=max_retries
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=last_error or "Unknown error",
                duration_ms=duration_ms
            )

        except GitAuthenticationError:
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = f"Push with conflict resolution failed: {e}"
            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="push_with_conflict_resolution",
                error_message=error_message,
                attempt_count=max_retries
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=str(e),
                duration_ms=duration_ms
            )

    def _notify_goal_manager_of_failure(
        self,
        operation: str,
        error_message: str,
        attempt_count: int
    ) -> None:
        """Notify Goal Manager of operation failure.

        This method sends a notification to the Goal Manager component
        when a Git operation fails after all retry attempts.

        Args:
            operation: Name of the failed operation
            error_message: Detailed error message
            attempt_count: Number of attempts made

        Note:
            This is a placeholder for integration with Goal Manager.
            Actual implementation will depend on Goal Manager API.
        """
        try:
            # TODO: Integrate with Goal Manager component
            # For now, just log the notification
            logger.error(
                f"GOAL_MANAGER_NOTIFICATION: "
                f"operation={operation}, "
                f"attempts={attempt_count}, "
                f"error={error_message[:200]}"
            )

            # Future implementation:
            # from agent_guru.agents.goal_manager import GoalManager
            # goal_manager = GoalManager()
            # goal_manager.notify_operation_failure(
            #     component="github_integrator",
            #     operation=operation,
            #     error_message=error_message,
            #     attempt_count=attempt_count,
            #     timestamp=datetime.now()
            # )

        except Exception as e:
            logger.warning(f"Failed to notify Goal Manager: {e}")

    def detect_conflicts(self) -> tuple[bool, list[str]]:
        """Detect if there are merge conflicts in the repository.

        Time Complexity: O(n) where n is number of conflicted files
        Space Complexity: O(n) for conflict list

        Returns:
            Tuple of (has_conflicts, conflicted_files)
            - has_conflicts: True if conflicts exist
            - conflicted_files: List of files with conflicts

        Example:
            >>> has_conflicts, files = integrator.detect_conflicts()
            >>> if has_conflicts:
            ...     print(f"Conflicts in: {files}")
        """
        try:
            # Check for conflict markers in status
            status_result = self._run_git_command(["status", "--porcelain"])

            if not status_result.success:
                logger.warning("Failed to check conflict status")
                return False, []

            conflicted_files = []

            for line in status_result.stdout.splitlines():
                if not line:
                    continue

                status_code = line[:2]
                file_path = line[3:].strip()

                # Check for conflict markers (UU, AA, DD, AU, UA, DU, UD)
                if status_code in ('UU', 'AA', 'DD', 'AU', 'UA', 'DU', 'UD'):
                    conflicted_files.append(file_path)

            has_conflicts = len(conflicted_files) > 0

            if has_conflicts:
                logger.warning(f"Detected {len(conflicted_files)} conflicted file(s)")

            return has_conflicts, conflicted_files

        except Exception as e:
            logger.error(f"Failed to detect conflicts: {e}")
            return False, []

    def resolve_conflicts_with_rebase(
        self,
        branch: Optional[str] = None,
        max_attempts: int = 3
    ) -> GitOperationResult:
        """Attempt to resolve conflicts using pull-rebase strategy.

        This method implements the conflict resolution workflow:
        1. Detect if conflicts exist
        2. Attempt pull with rebase
        3. If conflicts occur, abort and retry
        4. Retry up to max_attempts times
        5. If all attempts fail, notify and return error

        Time Complexity: O(1) per attempt (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to pull from (None = current branch)
            max_attempts: Maximum retry attempts (default: 3)

        Returns:
            GitOperationResult with resolution status

        Raises:
            GitConflictError: If conflicts cannot be resolved automatically

        Example:
            >>> result = integrator.resolve_conflicts_with_rebase()
            >>> if result.success:
            ...     print("Conflicts resolved successfully")
            ... else:
            ...     print(f"Failed to resolve: {result.message}")
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            logger.info(
                f"Starting conflict resolution: branch={branch}, "
                f"max_attempts={max_attempts}"
            )

            # Check if conflicts already exist
            has_conflicts, conflicted_files = self.detect_conflicts()
            if has_conflicts:
                logger.warning(
                    f"Existing conflicts detected in {len(conflicted_files)} file(s): "
                    f"{', '.join(conflicted_files[:5])}"
                )
                # Abort any in-progress rebase
                self._run_git_command(["rebase", "--abort"])

            # Attempt pull-rebase with retry logic
            last_error = None
            attempt_details = []

            for attempt in range(1, max_attempts + 1):
                logger.info(f"Conflict resolution attempt {attempt}/{max_attempts}")

                try:
                    # Fetch latest changes
                    fetch_result = self._run_git_command([
                        "fetch",
                        self.remote_name,
                        branch
                    ])

                    if not fetch_result.success:
                        error_msg = f"Fetch failed: {fetch_result.stderr}"
                        attempt_details.append(f"Attempt {attempt}: {error_msg}")
                        last_error = error_msg
                        logger.warning(error_msg)
                        continue

                    # Attempt pull with rebase
                    pull_result = self._run_git_command([
                        "pull",
                        "--rebase",
                        self.remote_name,
                        branch
                    ])

                    if pull_result.success:
                        # Success! Check if there are any remaining conflicts
                        has_conflicts, _ = self.detect_conflicts()
                        if not has_conflicts:
                            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                            logger.info(
                                f"Conflict resolution successful on attempt {attempt}"
                            )
                            return GitOperationResult(
                                success=True,
                                message=f"Conflicts resolved successfully (attempt {attempt}/{max_attempts})",
                                stdout=pull_result.stdout,
                                stderr=pull_result.stderr,
                                return_code=pull_result.return_code,
                                duration_ms=duration_ms
                            )

                    # Check for conflicts in output
                    stderr_lower = pull_result.stderr.lower()
                    stdout_lower = pull_result.stdout.lower()

                    if "conflict" in stderr_lower or "conflict" in stdout_lower:
                        # Conflicts detected - abort rebase
                        logger.warning(f"Conflicts detected on attempt {attempt}")
                        self._run_git_command(["rebase", "--abort"])

                        error_msg = f"Conflicts during rebase: {pull_result.stderr}"
                        attempt_details.append(f"Attempt {attempt}: {error_msg}")
                        last_error = error_msg

                        # Wait before retry (exponential backoff)
                        if attempt < max_attempts:
                            import time
                            wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                            logger.info(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)

                        continue

                    # Other error
                    error_msg = f"Pull-rebase failed: {pull_result.stderr}"
                    attempt_details.append(f"Attempt {attempt}: {error_msg}")
                    last_error = error_msg
                    logger.warning(error_msg)

                except Exception as e:
                    error_msg = f"Exception during attempt: {str(e)}"
                    attempt_details.append(f"Attempt {attempt}: {error_msg}")
                    last_error = str(e)
                    logger.error(error_msg)

            # All attempts failed
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Build detailed error message
            error_details = "\n".join(attempt_details)
            error_message = (
                f"Failed to resolve conflicts after {max_attempts} attempts.\n\n"
                f"Attempt details:\n{error_details}\n\n"
                f"Last error: {last_error}\n\n"
                f"Remediation:\n"
                f"1. Manually resolve conflicts in the repository\n"
                f"2. Check for uncommitted changes that may be causing issues\n"
                f"3. Verify network connectivity to remote repository\n"
                f"4. Contact repository administrator if access issues persist"
            )

            logger.error(error_message)

            # Notify Goal Manager (if available)
            self._notify_goal_manager_of_failure(
                operation="conflict_resolution",
                error_message=error_message,
                attempt_count=max_attempts
            )

            raise GitConflictError(error_message)

        except GitConflictError:
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = f"Conflict resolution failed with exception: {e}"
            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="conflict_resolution",
                error_message=error_message,
                attempt_count=max_attempts
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=str(e),
                duration_ms=duration_ms
            )

    def push_with_conflict_resolution(
        self,
        branch: Optional[str] = None,
        force: bool = False,
        max_retries: int = 3
    ) -> GitOperationResult:
        """Push with automatic conflict resolution using pull-rebase.

        This method implements the complete push workflow with conflict handling:
        1. Attempt push
        2. If rejected due to conflicts, pull-rebase
        3. Retry push
        4. Repeat up to max_retries times

        Time Complexity: O(1) per attempt (network operation)
        Space Complexity: O(1)

        Args:
            branch: Branch to push (None = current branch)
            force: Force push (use with caution)
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            GitOperationResult with push status

        Example:
            >>> result = integrator.push_with_conflict_resolution()
            >>> if result.success:
            ...     print("Pushed successfully")
            ... else:
            ...     print(f"Push failed: {result.message}")
        """
        start_time = datetime.now()

        try:
            # Get current branch if not specified
            if branch is None:
                status = self.get_status()
                branch = status.current_branch

            logger.info(
                f"Starting push with conflict resolution: branch={branch}, "
                f"max_retries={max_retries}"
            )

            last_error = None

            for attempt in range(1, max_retries + 1):
                logger.info(f"Push attempt {attempt}/{max_retries}")

                try:
                    # Attempt push
                    push_result = self.push(branch=branch, force=force)

                    if push_result.success:
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                        logger.info(f"Push successful on attempt {attempt}")
                        return GitOperationResult(
                            success=True,
                            message=f"Pushed successfully (attempt {attempt}/{max_retries})",
                            stdout=push_result.stdout,
                            stderr=push_result.stderr,
                            return_code=push_result.return_code,
                            duration_ms=duration_ms
                        )

                    # Check if rejection is due to conflicts
                    stderr_lower = push_result.stderr.lower()
                    if "rejected" in stderr_lower and not force:
                        logger.warning(
                            f"Push rejected on attempt {attempt}, attempting conflict resolution"
                        )

                        # Attempt conflict resolution
                        resolve_result = self.resolve_conflicts_with_rebase(
                            branch=branch,
                            max_attempts=2  # Fewer attempts for nested resolution
                        )

                        if not resolve_result.success:
                            last_error = resolve_result.message
                            logger.error(f"Conflict resolution failed: {last_error}")
                            continue

                        # Conflict resolved, retry push on next iteration
                        logger.info("Conflict resolved, will retry push")
                        continue

                    # Other push error
                    last_error = push_result.message
                    logger.warning(f"Push failed on attempt {attempt}: {last_error}")

                except GitAuthenticationError as e:
                    # Don't retry authentication errors
                    logger.error(f"Authentication error: {e}")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Exception during push attempt {attempt}: {e}")

            # All attempts failed
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = (
                f"Push failed after {max_retries} attempts.\n"
                f"Last error: {last_error}\n\n"
                f"Remediation:\n"
                f"1. Check network connectivity\n"
                f"2. Verify repository permissions\n"
                f"3. Manually resolve any conflicts\n"
                f"4. Try force push if appropriate (use with caution)"
            )

            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="push_with_conflict_resolution",
                error_message=error_message,
                attempt_count=max_retries
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=last_error or "Unknown error",
                duration_ms=duration_ms
            )

        except GitAuthenticationError:
            raise
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_message = f"Push with conflict resolution failed: {e}"
            logger.error(error_message)

            # Notify Goal Manager
            self._notify_goal_manager_of_failure(
                operation="push_with_conflict_resolution",
                error_message=error_message,
                attempt_count=max_retries
            )

            return GitOperationResult(
                success=False,
                message=error_message,
                stderr=str(e),
                duration_ms=duration_ms
            )

    def _notify_goal_manager_of_failure(
        self,
        operation: str,
        error_message: str,
        attempt_count: int
    ) -> None:
        """Notify Goal Manager of operation failure.

        This method sends a notification to the Goal Manager component
        when a Git operation fails after all retry attempts.

        Args:
            operation: Name of the failed operation
            error_message: Detailed error message
            attempt_count: Number of attempts made

        Note:
            This is a placeholder for integration with Goal Manager.
            Actual implementation will depend on Goal Manager API.
        """
        try:
            # TODO: Integrate with Goal Manager component
            # For now, just log the notification
            logger.error(
                f"GOAL_MANAGER_NOTIFICATION: "
                f"operation={operation}, "
                f"attempts={attempt_count}, "
                f"error={error_message[:200]}"
            )

            # Future implementation:
            # from agent_guru.agents.goal_manager import GoalManager
            # goal_manager = GoalManager()
            # goal_manager.notify_operation_failure(
            #     component="github_integrator",
            #     operation=operation,
            #     error_message=error_message,
            #     attempt_count=attempt_count,
            #     timestamp=datetime.now()
            # )

        except Exception as e:
            logger.warning(f"Failed to notify Goal Manager: {e}")


    def create_branch(
        self,
        branch_name: str,
        base_branch: Optional[str] = None
    ) -> GitOperationResult:
        """Create a new branch.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to create from (None = current branch)

        Returns:
            GitOperationResult with branch creation status

        Raises:
            ValueError: If branch_name is empty
            GitError: If branch creation fails

        Example:
            >>> result = integrator.create_branch("feature/new-feature")
            >>> if result.success:
            ...     print(f"Branch created: {branch_name}")
        """
        if not branch_name or not branch_name.strip():
            raise ValueError("Branch name cannot be empty")

        start_time = datetime.now()

        try:
            # Check if branch already exists
            branch_info = self.get_branch_info(branch_name)
            if branch_info.exists_locally:
                return GitOperationResult(
                    success=False,
                    message=f"Branch '{branch_name}' already exists locally",
                    stderr=f"Branch exists: {branch_name}"
                )

            # Create branch
            cmd = ["checkout", "-b", branch_name]
            if base_branch:
                cmd.append(base_branch)

            result = self._run_git_command(cmd)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if result.success:
                logger.info(f"Created branch: {branch_name}")
                return GitOperationResult(
                    success=True,
                    message=f"Branch '{branch_name}' created successfully",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.return_code,
                    duration_ms=duration_ms
                )
            else:
                raise GitError(f"Failed to create branch: {result.stderr}")

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to create branch: {e}")
            return GitOperationResult(
                success=False,
                message=f"Branch creation failed: {e}",
                stderr=str(e),
                duration_ms=duration_ms
            )

    def get_branch_info(self, branch_name: str) -> BranchInfo:
        """Get information about a branch.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            branch_name: Name of the branch

        Returns:
            BranchInfo with branch details

        Example:
            >>> info = integrator.get_branch_info("main")
            >>> print(f"Exists locally: {info.exists_locally}")
        """
        try:
            # Check if branch exists locally
            local_result = self._run_git_command(["branch", "--list", branch_name])
            exists_locally = bool(local_result.stdout.strip())

            # Check if branch exists remotely
            remote_result = self._run_git_command([
                "ls-remote",
                "--heads",
                self.remote_name,
                f"refs/heads/{branch_name}"
            ])
            exists_remotely = bool(remote_result.stdout.strip())

            # Check if it's the current branch
            status = self.get_status()
            is_current = status.current_branch == branch_name

            # Get commit hash if branch exists
            commit_hash = None
            if exists_locally:
                hash_result = self._run_git_command(["rev-parse", branch_name])
                if hash_result.success:
                    commit_hash = hash_result.stdout.strip()

            return BranchInfo(
                name=branch_name,
                exists_locally=exists_locally,
                exists_remotely=exists_remotely,
                is_current=is_current,
                commit_hash=commit_hash
            )

        except Exception as e:
            logger.error(f"Failed to get branch info: {e}")
            return BranchInfo(
                name=branch_name,
                exists_locally=False,
                exists_remotely=False,
                is_current=False
            )

    def generate_pr_description(
        self,
        task_id: str,
        task_description: str,
        changed_files: Optional[list[str]] = None,
        task_type: str = "Task"
    ) -> str:
        """Generate pull request description from task context.

        Time Complexity: O(n) where n is number of changed files
        Space Complexity: O(n) for file analysis

        Args:
            task_id: Task identifier (e.g., "24.5")
            task_description: Human-readable task description
            changed_files: List of changed files (None = auto-detect)
            task_type: Type of task (Task, Feature, Bugfix, etc.)

        Returns:
            Formatted PR description in Markdown

        Example:
            >>> description = integrator.generate_pr_description(
            ...     task_id="24.5",
            ...     task_description="Implement PR creation",
            ...     task_type="Task"
            ... )
        """
        # Auto-detect changed files if not provided
        if changed_files is None:
            status = self.get_status()
            changed_files = (
                status.staged_files +
                status.unstaged_files +
                status.untracked_files
            )

        # Analyze files
        file_stats = self._get_file_stats(changed_files)

        # Group files by component
        components = set()
        file_types = set()
        for file_path in changed_files:
            # Extract component from path (e.g., "Agent_Guru/platform/github" -> "github")
            parts = Path(file_path).parts
            if len(parts) >= 3 and parts[0] == "Agent_Guru":
                components.add(parts[2])

            # Extract file extension
            ext = Path(file_path).suffix
            if ext:
                file_types.add(ext)

        # Build description
        description_parts = [
            f"## [{task_type} {task_id}] {task_description}",
            "",
            "### Summary",
            f"This PR implements {task_type} {task_id}: {task_description}",
            "",
            "### Changes",
            f"- **Files changed**: {len(changed_files)}",
            f"- **Components**: {', '.join(sorted(components)) if components else 'N/A'}",
            f"- **File types**: {', '.join(sorted(file_types)) if file_types else 'N/A'}",
            "",
            "### Files Modified",
        ]

        # Add file list with status
        for file_path in sorted(changed_files)[:20]:  # Limit to 20 files
            status_symbol = {
                'A': '✨',  # Added
                'M': '📝',  # Modified
                'D': '🗑️'   # Deleted
            }.get(file_stats.get(file_path, 'M'), '📝')
            description_parts.append(f"- {status_symbol} `{file_path}`")

        if len(changed_files) > 20:
            description_parts.append(f"- ... and {len(changed_files) - 20} more files")

        description_parts.extend([
            "",
            "### Testing",
            "- [ ] Unit tests added/updated",
            "- [ ] Integration tests added/updated",
            "- [ ] All tests passing",
            "",
            "### Checklist",
            "- [ ] Code follows project style guidelines",
            "- [ ] Documentation updated",
            "- [ ] No breaking changes",
            "",
            "---",
            "*Auto-generated by Agent_Guru*"
        ])

        return "\n".join(description_parts)

    def create_pull_request(
        self,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str = "main",
        draft: bool = False
    ) -> PullRequestResult:
        """Create a pull request using GitHub CLI.

        This method requires GitHub CLI (gh) to be installed and authenticated.

        Time Complexity: O(1) (network operation)
        Space Complexity: O(1)

        Args:
            title: PR title
            description: PR description (Markdown supported)
            source_branch: Source branch (head)
            target_branch: Target branch (base)
            draft: Create as draft PR

        Returns:
            PullRequestResult with PR details

        Raises:
            ValueError: If title or source_branch is empty
            GitError: If PR creation fails

        Example:
            >>> result = integrator.create_pull_request(
            ...     title="[Task 24.5] Implement PR creation",
            ...     description="This PR adds PR creation functionality",
            ...     source_branch="feature/pr-creation",
            ...     target_branch="main"
            ... )
            >>> if result.success:
            ...     print(f"PR created: {result.pr_url}")
        """
        if not title or not title.strip():
            raise ValueError("PR title cannot be empty")
        if not source_branch or not source_branch.strip():
            raise ValueError("Source branch cannot be empty")

        start_time = datetime.now()

        try:
            # Validate source branch exists
            source_info = self.get_branch_info(source_branch)
            if not source_info.exists_locally and not source_info.exists_remotely:
                return PullRequestResult(
                    success=False,
                    message=f"Source branch '{source_branch}' does not exist",
                    error=f"Branch not found: {source_branch}"
                )

            # Push source branch if not on remote
            if source_info.exists_locally and not source_info.exists_remotely:
                logger.info(f"Pushing source branch '{source_branch}' to remote")
                push_result = self.push(branch=source_branch, set_upstream=True)
                if not push_result.success:
                    return PullRequestResult(
                        success=False,
                        message=f"Failed to push source branch: {push_result.message}",
                        error=push_result.stderr
                    )

            # Check if GitHub CLI is available
            gh_check = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if gh_check.returncode != 0:
                return PullRequestResult(
                    success=False,
                    message="GitHub CLI (gh) is not installed or not in PATH",
                    error=(
                        "GitHub CLI is required for PR creation.\n"
                        "Install from: https://cli.github.com/\n"
                        "Then authenticate with: gh auth login"
                    )
                )

            # Build gh pr create command
            cmd = [
                "gh", "pr", "create",
                "--title", title,
                "--body", description,
                "--base", target_branch,
                "--head", source_branch
            ]

            if draft:
                cmd.append("--draft")

            # Create PR
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            (datetime.now() - start_time).total_seconds() * 1000

            if result.returncode == 0:
                # Extract PR URL from output
                pr_url = result.stdout.strip()

                # Extract PR number from URL (e.g., https://github.com/user/repo/pull/123)
                pr_number = None
                if "/pull/" in pr_url:
                    try:
                        pr_number = int(pr_url.split("/pull/")[-1])
                    except (ValueError, IndexError):
                        pass

                logger.info(f"PR created successfully: {pr_url}")

                return PullRequestResult(
                    success=True,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    message=f"Pull request created: #{pr_number}" if pr_number else "Pull request created"
                )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Failed to create PR: {error_msg}")

                return PullRequestResult(
                    success=False,
                    message=f"Failed to create pull request: {error_msg}",
                    error=error_msg
                )

        except subprocess.TimeoutExpired:
            return PullRequestResult(
                success=False,
                message=f"PR creation timed out after {self.timeout}s",
                error="Timeout"
            )
        except Exception as e:
            (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to create PR: {e}")
            return PullRequestResult(
                success=False,
                message=f"PR creation failed: {e}",
                error=str(e)
            )

    def create_pr_from_task(
        self,
        task_id: str,
        task_description: str,
        source_branch: Optional[str] = None,
        target_branch: str = "main",
        task_type: str = "Task",
        draft: bool = False
    ) -> PullRequestResult:
        """Create a pull request from task context (convenience method).

        This method combines branch creation, commit, push, and PR creation
        into a single workflow.

        Time Complexity: O(n) where n is number of changed files
        Space Complexity: O(n) for file analysis

        Args:
            task_id: Task identifier
            task_description: Task description
            source_branch: Source branch (None = auto-generate from task_id)
            target_branch: Target branch (default: "main")
            task_type: Type of task
            draft: Create as draft PR

        Returns:
            PullRequestResult with PR details

        Example:
            >>> result = integrator.create_pr_from_task(
            ...     task_id="24.5",
            ...     task_description="Implement PR creation",
            ...     task_type="Task"
            ... )
            >>> if result.success:
            ...     print(f"PR created: {result.pr_url}")
        """
        try:
            # Auto-generate branch name if not provided
            if source_branch is None:
                # Convert task_id to branch name (e.g., "24.5" -> "task-24-5")
                safe_task_id = task_id.replace(".", "-").replace(" ", "-").lower()
                source_branch = f"task-{safe_task_id}"

            # Check if we're already on the source branch
            status = self.get_status()
            if status.current_branch != source_branch:
                # Create and checkout branch if it doesn't exist
                branch_info = self.get_branch_info(source_branch)
                if not branch_info.exists_locally:
                    create_result = self.create_branch(source_branch, target_branch)
                    if not create_result.success:
                        return PullRequestResult(
                            success=False,
                            message=f"Failed to create branch: {create_result.message}",
                            error=create_result.stderr
                        )
                else:
                    # Checkout existing branch
                    checkout_result = self._run_git_command(["checkout", source_branch])
                    if not checkout_result.success:
                        return PullRequestResult(
                            success=False,
                            message=f"Failed to checkout branch: {checkout_result.stderr}",
                            error=checkout_result.stderr
                        )

            # Generate PR title and description
            pr_title = f"[{task_type} {task_id}] {task_description}"
            pr_description = self.generate_pr_description(
                task_id=task_id,
                task_description=task_description,
                task_type=task_type
            )

            # Create PR
            return self.create_pull_request(
                title=pr_title,
                description=pr_description,
                source_branch=source_branch,
                target_branch=target_branch,
                draft=draft
            )

        except Exception as e:
            logger.error(f"Failed to create PR from task: {e}")
            return PullRequestResult(
                success=False,
                message=f"PR creation from task failed: {e}",
                error=str(e)
            )
