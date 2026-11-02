"""
Tests for GitHub conflict resolution functionality.

This module tests:
- Conflict detection
- Pull-rebase strategy
- Retry logic with exponential backoff
- Error notification to Goal Manager
- Integration with existing push/pull operations

Coverage Target: >80% (enforced by CI/CD)
"""

import shutil
import subprocess  # nosec B404 - git on fixed arguments, in tmp_path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from Agent_Guru.platform.github.integrator import (
    GitHubIntegrator,
    GitOperationResult,
    GitConflictError,
    GitAuthenticationError
)


class TestConflictDetection:
    """Unit tests for conflict detection."""
    
    def test_detect_conflicts_no_conflicts(self, mock_integrator):
        """Test conflict detection when no conflicts exist."""
        # Mock status output with no conflicts
        mock_integrator._run_git_command = Mock(return_value=GitOperationResult(
            success=True,
            message="Status OK",
            stdout="M  file1.py\nA  file2.py\n",
            stderr=""
        ))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        assert has_conflicts is False  # nosec B101
        assert conflicted_files == []  # nosec B101
    
    def test_detect_conflicts_with_conflicts(self, mock_integrator):
        """Test conflict detection when conflicts exist."""
        # Mock status output with conflicts (UU = both modified)
        mock_integrator._run_git_command = Mock(return_value=GitOperationResult(
            success=True,
            message="Status OK",
            stdout="UU file1.py\nAA file2.py\nM  file3.py\n",
            stderr=""
        ))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        assert has_conflicts is True  # nosec B101
        assert len(conflicted_files) == 2  # nosec B101
        assert "file1.py" in conflicted_files  # nosec B101
        assert "file2.py" in conflicted_files  # nosec B101
        assert "file3.py" not in conflicted_files  # nosec B101
    
    def test_detect_conflicts_all_conflict_types(self, mock_integrator):
        """Test detection of all conflict marker types."""
        # Test all conflict status codes: UU, AA, DD, AU, UA, DU, UD
        mock_integrator._run_git_command = Mock(return_value=GitOperationResult(
            success=True,
            message="Status OK",
            stdout=(
                "UU file1.py\n"
                "AA file2.py\n"
                "DD file3.py\n"
                "AU file4.py\n"
                "UA file5.py\n"
                "DU file6.py\n"
                "UD file7.py\n"
            ),
            stderr=""
        ))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        assert has_conflicts is True  # nosec B101
        assert len(conflicted_files) == 7  # nosec B101
    
    def test_detect_conflicts_command_failure(self, mock_integrator):
        """Test conflict detection when git command fails."""
        mock_integrator._run_git_command = Mock(return_value=GitOperationResult(
            success=False,
            message="Command failed",
            stderr="fatal: not a git repository"
        ))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        # Should return False, [] on failure (graceful degradation)
        assert has_conflicts is False  # nosec B101
        assert conflicted_files == []  # nosec B101
    
    def test_detect_conflicts_exception_handling(self, mock_integrator):
        """Test conflict detection handles exceptions gracefully."""
        mock_integrator._run_git_command = Mock(side_effect=Exception("Unexpected error"))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        # Should return False, [] on exception
        assert has_conflicts is False  # nosec B101
        assert conflicted_files == []  # nosec B101


class TestConflictResolution:
    """Unit tests for conflict resolution with pull-rebase."""
    
    def test_resolve_conflicts_success_first_attempt(self, mock_integrator):
        """Test successful conflict resolution on first attempt."""
        # Mock successful fetch and pull-rebase
        def mock_command(args):
            if args[0] == "fetch":
                return GitOperationResult(success=True, message="Fetched", stdout="")
            elif args[0] == "pull":
                return GitOperationResult(success=True, message="Pulled", stdout="")
            elif args[0] == "status":
                return GitOperationResult(success=True, message="Status", stdout="")
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.detect_conflicts = Mock(return_value=(False, []))
        
        result = mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
        
        assert result.success is True  # nosec B101
        assert "attempt 1/3" in result.message.lower()  # nosec B101
    
    def test_resolve_conflicts_success_after_retry(self, mock_integrator):
        """Test successful conflict resolution after retry."""
        attempt_count = [0]
        
        def mock_command(args):
            if args[0] == "fetch":
                return GitOperationResult(success=True, message="Fetched", stdout="")
            elif args[0] == "pull":
                attempt_count[0] += 1
                if attempt_count[0] == 1:
                    # First attempt fails with conflict
                    return GitOperationResult(
                        success=False,
                        message="Conflict",
                        stderr="CONFLICT (content): Merge conflict in file.py"
                    )
                else:
                    # Second attempt succeeds
                    return GitOperationResult(success=True, message="Pulled", stdout="")
            elif args[0] == "rebase":
                return GitOperationResult(success=True, message="Aborted", stdout="")
            elif args[0] == "status":
                return GitOperationResult(success=True, message="Status", stdout="")
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.detect_conflicts = Mock(return_value=(False, []))
        
        with patch('time.sleep'):  # Skip actual sleep
            result = mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
        
        assert result.success is True  # nosec B101
        assert "attempt 2/3" in result.message.lower()  # nosec B101
    
    def test_resolve_conflicts_all_attempts_fail(self, mock_integrator):
        """Test conflict resolution when all attempts fail."""
        def mock_command(args):
            if args[0] == "fetch":
                return GitOperationResult(success=True, message="Fetched", stdout="")
            elif args[0] == "pull":
                return GitOperationResult(
                    success=False,
                    message="Conflict",
                    stderr="CONFLICT (content): Merge conflict in file.py"
                )
            elif args[0] == "rebase":
                return GitOperationResult(success=True, message="Aborted", stdout="")
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.detect_conflicts = Mock(return_value=(True, ["file.py"]))
        mock_integrator._notify_goal_manager_of_failure = Mock()
        
        with patch('time.sleep'):  # Skip actual sleep
            with pytest.raises(GitConflictError) as exc_info:
                mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
        
        assert "Failed to resolve conflicts after 3 attempts" in str(exc_info.value)  # nosec B101
        mock_integrator._notify_goal_manager_of_failure.assert_called_once()
    
    def test_resolve_conflicts_existing_conflicts_aborted(self, mock_integrator):
        """Test that existing conflicts are aborted before resolution."""
        abort_called = [False]
        
        def mock_command(args):
            if args[0] == "rebase" and args[1] == "--abort":
                abort_called[0] = True
                return GitOperationResult(success=True, message="Aborted", stdout="")
            elif args[0] == "fetch":
                return GitOperationResult(success=True, message="Fetched", stdout="")
            elif args[0] == "pull":
                return GitOperationResult(success=True, message="Pulled", stdout="")
            elif args[0] == "status":
                return GitOperationResult(success=True, message="Status", stdout="")
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        # First call returns conflicts, second call returns no conflicts
        mock_integrator.detect_conflicts = Mock(side_effect=[
            (True, ["file.py"]),
            (False, [])
        ])
        
        result = mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
        
        assert abort_called[0] is True  # nosec B101
        assert result.success is True  # nosec B101
    
    def test_resolve_conflicts_fetch_failure(self, mock_integrator):
        """Test conflict resolution when fetch fails."""
        def mock_command(args):
            if args[0] == "fetch":
                return GitOperationResult(
                    success=False,
                    message="Fetch failed",
                    stderr="fatal: unable to access remote"
                )
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.detect_conflicts = Mock(return_value=(False, []))
        mock_integrator._notify_goal_manager_of_failure = Mock()
        
        with pytest.raises(GitConflictError):
            mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
    
    @patch('time.sleep')
    def test_resolve_conflicts_exponential_backoff(self, mock_sleep, mock_integrator):
        """Test that exponential backoff is applied between retries."""
        def mock_command(args):
            if args[0] == "fetch":
                return GitOperationResult(success=True, message="Fetched", stdout="")
            elif args[0] == "pull":
                return GitOperationResult(
                    success=False,
                    message="Conflict",
                    stderr="CONFLICT"
                )
            elif args[0] == "rebase":
                return GitOperationResult(success=True, message="Aborted", stdout="")
            return GitOperationResult(success=True, message="OK", stdout="")
        
        mock_integrator._run_git_command = Mock(side_effect=mock_command)
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.detect_conflicts = Mock(return_value=(True, ["file.py"]))
        mock_integrator._notify_goal_manager_of_failure = Mock()
        
        with pytest.raises(GitConflictError):
            mock_integrator.resolve_conflicts_with_rebase(max_attempts=3)
        
        # Verify exponential backoff: 1s, 2s (no sleep after last attempt)
        assert mock_sleep.call_count == 2  # nosec B101
        mock_sleep.assert_any_call(1)  # 2^0 = 1
        mock_sleep.assert_any_call(2)  # 2^1 = 2


class TestPushWithConflictResolution:
    """Unit tests for push with automatic conflict resolution."""
    
    def test_push_success_first_attempt(self, mock_integrator):
        """Test successful push on first attempt (no conflicts)."""
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(return_value=GitOperationResult(
            success=True,
            message="Pushed",
            stdout="",
            stderr=""
        ))
        
        result = mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        assert result.success is True  # nosec B101
        assert "attempt 1/3" in result.message.lower()  # nosec B101
        mock_integrator.push.assert_called_once()
    
    def test_push_with_conflict_resolution_success(self, mock_integrator):
        """Test push with conflict resolution succeeds after rebase."""
        attempt_count = [0]
        
        def mock_push(branch=None, force=False):
            attempt_count[0] += 1
            if attempt_count[0] == 1:
                # First push rejected
                return GitOperationResult(
                    success=False,
                    message="Rejected",
                    stderr="! [rejected] main -> main (non-fast-forward)"
                )
            else:
                # Second push succeeds
                return GitOperationResult(
                    success=True,
                    message="Pushed",
                    stdout="",
                    stderr=""
                )
        
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(side_effect=mock_push)
        mock_integrator.resolve_conflicts_with_rebase = Mock(return_value=GitOperationResult(
            success=True,
            message="Resolved",
            stdout="",
            stderr=""
        ))
        
        result = mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        assert result.success is True  # nosec B101
        assert mock_integrator.resolve_conflicts_with_rebase.call_count == 1  # nosec B101
        assert mock_integrator.push.call_count == 2  # nosec B101
    
    def test_push_all_retries_fail(self, mock_integrator):
        """Test push when all retry attempts fail."""
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(return_value=GitOperationResult(
            success=False,
            message="Failed",
            stderr="fatal: unable to access remote"
        ))
        mock_integrator._notify_goal_manager_of_failure = Mock()
        
        result = mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        assert result.success is False  # nosec B101
        assert "Push failed after 3 attempts" in result.message  # nosec B101
        mock_integrator._notify_goal_manager_of_failure.assert_called_once()
    
    def test_push_authentication_error_no_retry(self, mock_integrator):
        """Test that authentication errors are not retried."""
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(side_effect=GitAuthenticationError("Auth failed"))
        
        with pytest.raises(GitAuthenticationError):
            mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        # Should only attempt once (no retry for auth errors)
        assert mock_integrator.push.call_count == 1  # nosec B101
    
    def test_push_conflict_resolution_fails(self, mock_integrator):
        """Test push when conflict resolution fails."""
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(return_value=GitOperationResult(
            success=False,
            message="Rejected",
            stderr="! [rejected] main -> main (non-fast-forward)"
        ))
        mock_integrator.resolve_conflicts_with_rebase = Mock(return_value=GitOperationResult(
            success=False,
            message="Resolution failed",
            stderr="Cannot resolve conflicts"
        ))
        mock_integrator._notify_goal_manager_of_failure = Mock()
        
        result = mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        assert result.success is False  # nosec B101
        assert mock_integrator.resolve_conflicts_with_rebase.call_count == 3  # nosec B101


class TestGoalManagerNotification:
    """Unit tests for Goal Manager notification."""
    
    def test_notify_goal_manager_logs_error(self, mock_integrator, caplog):
        """Test that Goal Manager notification logs error."""
        mock_integrator._notify_goal_manager_of_failure(
            operation="test_operation",
            error_message="Test error message",
            attempt_count=3
        )
        
        # Check that error was logged
        assert "GOAL_MANAGER_NOTIFICATION" in caplog.text  # nosec B101
        assert "test_operation" in caplog.text  # nosec B101
        assert "attempts=3" in caplog.text  # nosec B101
    
    def test_notify_goal_manager_handles_exception(self, mock_integrator, caplog):
        """Test that notification handles exceptions gracefully."""
        # This should not raise an exception
        mock_integrator._notify_goal_manager_of_failure(
            operation="test",
            error_message="x" * 1000,  # Very long message
            attempt_count=5
        )
        
        # Should still log something
        assert "GOAL_MANAGER_NOTIFICATION" in caplog.text  # nosec B101


# Integration Tests

_GIT = shutil.which("git")


def _git(cwd, *args):
    """Run git in cwd and return stdout; a failure here is a broken fixture, so it raises."""
    return subprocess.run([_GIT, *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout  # nosec B603


@pytest.mark.integration
@pytest.mark.skipif(_GIT is None, reason="needs the git executable on PATH")
class TestConflictResolutionIntegration:
    """push_with_conflict_resolution against real repositories: a bare remote and two clones.

    Both tests here used to skip unconditionally with "Requires real Git repository setup", while
    a fixture that built a real repository sat unused, so nothing ran the rebase-and-retry path
    against git itself. Everything is local (the remote is a bare repository in tmp_path); the
    backoff sleep between rebase attempts is skipped so a run does not wait 1 s and 2 s for it.
    """

    @pytest.fixture
    def clones(self, tmp_path, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda seconds: None)
        remote = tmp_path / "remote.git"
        _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
        made = {}
        for name in ("mine", "theirs"):
            path = tmp_path / name
            _git(tmp_path, "clone", "-q", str(remote), str(path))
            _git(path, "config", "user.email", f"{name}@example.com")
            _git(path, "config", "user.name", name)
            _git(path, "config", "commit.gpgsign", "false")
            _git(path, "checkout", "-q", "-B", "main")
            made[name] = path
        (made["mine"] / "notes.txt").write_text("first line\n", encoding="utf-8")
        _git(made["mine"], "add", "notes.txt")
        _git(made["mine"], "commit", "-q", "-m", "Start the notes")
        _git(made["mine"], "push", "-q", "origin", "main")
        _git(made["theirs"], "pull", "-q", "origin", "main")
        return SimpleNamespace(remote=remote, **made)

    @staticmethod
    def _commit(path, filename, text, message):
        (path / filename).write_text(text, encoding="utf-8")
        _git(path, "add", filename)
        _git(path, "commit", "-q", "-m", message)

    def test_full_conflict_resolution_workflow(self, clones):
        """A push rejected because the remote moved on is rebased onto it and pushed again."""
        self._commit(clones.theirs, "theirs.txt", "from the other clone\n", "Their change")
        _git(clones.theirs, "push", "-q", "origin", "main")
        self._commit(clones.mine, "mine.txt", "from this clone\n", "My change")

        integrator = GitHubIntegrator(repo_path=str(clones.mine), remote_name="origin", default_branch="main")
        result = integrator.push_with_conflict_resolution(branch="main")

        assert result.success is True, result.message  # nosec B101
        subjects = _git(clones.remote, "log", "--format=%s", "main").splitlines()
        assert subjects == ["My change", "Their change", "Start the notes"]  # nosec B101

    def test_push_with_conflict_resolution_integration(self, clones):
        """Two edits of the same line cannot be rebased: the push fails and the clone is left usable."""
        self._commit(clones.theirs, "notes.txt", "their first line\n", "Their edit")
        _git(clones.theirs, "push", "-q", "origin", "main")
        self._commit(clones.mine, "notes.txt", "my first line\n", "My edit")

        integrator = GitHubIntegrator(repo_path=str(clones.mine), remote_name="origin", default_branch="main")
        try:
            pushed = integrator.push_with_conflict_resolution(branch="main").success
        except GitConflictError:
            pushed = False

        assert pushed is False  # nosec B101
        # The remote keeps the other clone's commit, and this clone is not left mid-rebase with
        # conflict markers in the file: the rebase was aborted and the local commit is intact.
        assert _git(clones.remote, "log", "-1", "--format=%s", "main").strip() == "Their edit"  # nosec B101
        assert not (clones.mine / ".git" / "rebase-merge").exists()  # nosec B101
        assert not (clones.mine / ".git" / "rebase-apply").exists()  # nosec B101
        assert _git(clones.mine, "log", "-1", "--format=%s").strip() == "My edit"  # nosec B101
        assert (clones.mine / "notes.txt").read_text(encoding="utf-8") == "my first line\n"  # nosec B101


# Fixtures

@pytest.fixture
def mock_integrator(tmp_path):
    """Create a mock GitHubIntegrator for testing."""
    # Create a temporary directory that looks like a Git repo
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    
    integrator = GitHubIntegrator(
        repo_path=str(repo_path),
        remote_name="origin",
        default_branch="main",
        max_retries=3,
        timeout=30
    )
    
    return integrator
