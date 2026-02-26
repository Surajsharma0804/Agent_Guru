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

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from Agent_Guru.platform.github.integrator import (
    GitHubIntegrator,
    GitOperationResult,
    GitConflictError,
    GitAuthenticationError,
    GitRemoteError
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
        
        assert has_conflicts is False
        assert conflicted_files == []
    
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
        
        assert has_conflicts is True
        assert len(conflicted_files) == 2
        assert "file1.py" in conflicted_files
        assert "file2.py" in conflicted_files
        assert "file3.py" not in conflicted_files
    
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
        
        assert has_conflicts is True
        assert len(conflicted_files) == 7
    
    def test_detect_conflicts_command_failure(self, mock_integrator):
        """Test conflict detection when git command fails."""
        mock_integrator._run_git_command = Mock(return_value=GitOperationResult(
            success=False,
            message="Command failed",
            stderr="fatal: not a git repository"
        ))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        # Should return False, [] on failure (graceful degradation)
        assert has_conflicts is False
        assert conflicted_files == []
    
    def test_detect_conflicts_exception_handling(self, mock_integrator):
        """Test conflict detection handles exceptions gracefully."""
        mock_integrator._run_git_command = Mock(side_effect=Exception("Unexpected error"))
        
        has_conflicts, conflicted_files = mock_integrator.detect_conflicts()
        
        # Should return False, [] on exception
        assert has_conflicts is False
        assert conflicted_files == []


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
        
        assert result.success is True
        assert "attempt 1/3" in result.message.lower()
    
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
        
        assert result.success is True
        assert "attempt 2/3" in result.message.lower()
    
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
        
        assert "Failed to resolve conflicts after 3 attempts" in str(exc_info.value)
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
        
        assert abort_called[0] is True
        assert result.success is True
    
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
        assert mock_sleep.call_count == 2
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
        
        assert result.success is True
        assert "attempt 1/3" in result.message.lower()
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
        
        assert result.success is True
        assert mock_integrator.resolve_conflicts_with_rebase.call_count == 1
        assert mock_integrator.push.call_count == 2
    
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
        
        assert result.success is False
        assert "Push failed after 3 attempts" in result.message
        mock_integrator._notify_goal_manager_of_failure.assert_called_once()
    
    def test_push_authentication_error_no_retry(self, mock_integrator):
        """Test that authentication errors are not retried."""
        mock_integrator.get_status = Mock(return_value=Mock(current_branch="main"))
        mock_integrator.push = Mock(side_effect=GitAuthenticationError("Auth failed"))
        
        with pytest.raises(GitAuthenticationError):
            mock_integrator.push_with_conflict_resolution(max_retries=3)
        
        # Should only attempt once (no retry for auth errors)
        assert mock_integrator.push.call_count == 1
    
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
        
        assert result.success is False
        assert mock_integrator.resolve_conflicts_with_rebase.call_count == 3


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
        assert "GOAL_MANAGER_NOTIFICATION" in caplog.text
        assert "test_operation" in caplog.text
        assert "attempts=3" in caplog.text
    
    def test_notify_goal_manager_handles_exception(self, mock_integrator, caplog):
        """Test that notification handles exceptions gracefully."""
        # This should not raise an exception
        mock_integrator._notify_goal_manager_of_failure(
            operation="test",
            error_message="x" * 1000,  # Very long message
            attempt_count=5
        )
        
        # Should still log something
        assert "GOAL_MANAGER_NOTIFICATION" in caplog.text


# Integration Tests

@pytest.mark.integration
class TestConflictResolutionIntegration:
    """Integration tests for conflict resolution workflow."""
    
    def test_full_conflict_resolution_workflow(self, temp_git_repo):
        """Test complete conflict resolution workflow with real Git repository."""
        # This test requires a real Git repository setup
        # Skip if not in integration test environment
        pytest.skip("Requires real Git repository setup")
    
    def test_push_with_conflict_resolution_integration(self, temp_git_repo):
        """Test push with conflict resolution in real repository."""
        pytest.skip("Requires real Git repository setup")


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


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary Git repository for integration tests."""
    import subprocess
    
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Initialize Git repository
    subprocess.run(["git", "init"], cwd=str(repo_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_path),
        check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo_path),
        check=True
    )
    
    return repo_path
