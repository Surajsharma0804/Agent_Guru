"""
Integration tests for command permission checking with command executor
"""

import pytest
from Agent_Guru.platform.permissions.command_checker import (
    CommandPermissionChecker,
    CommandCategory,
    DangerLevel
)
from Agent_Guru.platform.permissions.model_manager import (
    PermissionModelManager,
    OperationContext,
    OperationType
)


class TestCommandExecutorIntegration:
    """Integration tests with command executor."""
    
    @pytest.fixture
    def permission_manager(self, tmp_path):
        """Create permission manager with test configuration."""
        config_path = tmp_path / "test_permissions.yaml"
        
        config_content = """
version: "1.0"
environment: "development"

file_system:
  allowed_paths:
    - path: "/tmp/test"
      permissions: ["read", "write"]
  blocked_extensions: []
  max_file_size: 104857600

commands:
  allowed_patterns:
    - "^git .*"
    - "^npm (install|test|build)"
    - "^python3? .*\\\\.py$"
    - "^ls .*"
    - "^cat .*"
  blocked_patterns:
    - ".*rm -rf.*"
    - ".*sudo.*"

network:
  allowed_domains:
    - "api.github.com"
  allowed_methods:
    - "GET"
    - "POST"
  rate_limits:
    default: 100

resources:
  max_cpu_percent: 80.0
  max_memory_bytes: 2147483648

quotas:
  file_operations:
    per_hour: 1000
    per_day: 10000
  command_executions:
    per_hour: 500
    per_day: 5000
  network_requests:
    per_hour: 10000
    per_day: 100000

lockdown_mode:
  enabled: false
  allowed_operations: []
"""
        
        config_path.write_text(config_content)
        return PermissionModelManager(config_path)
    
    def test_command_validation_with_permission_manager(self, permission_manager):
        """Test command validation integrated with permission manager."""
        context = OperationContext(user_id="test_user")
        
        # Test allowed command
        allowed = permission_manager.is_command_allowed("git status", context)
        assert allowed
        
        # Test blocked command
        blocked = permission_manager.is_command_allowed("rm -rf /", context)
        assert not blocked
        
        # Test command blocked by pattern (sudo)
        sudo_blocked = permission_manager.is_command_allowed("sudo apt install", context)
        assert not sudo_blocked
    
    def test_command_quota_enforcement(self, permission_manager):
        """Test command execution quota enforcement."""
        context = OperationContext(user_id="test_user")
        
        # Execute commands up to quota
        for i in range(5):
            quota_status = permission_manager.check_quota(
                OperationType.COMMAND_EXECUTION,
                context
            )
            assert quota_status.available
        
        # Check quota status
        quota_status = permission_manager.check_quota(
            OperationType.COMMAND_EXECUTION,
            context
        )
        assert quota_status.current_hour == 6  # 5 + 1 from check
    
    def test_lockdown_mode_blocks_commands(self, permission_manager):
        """Test that lockdown mode blocks all commands."""
        context = OperationContext(user_id="test_user")
        
        # Enable lockdown mode
        permission_manager.enter_lockdown_mode()
        
        # All commands should be blocked
        assert not permission_manager.is_command_allowed("git status", context)
        assert not permission_manager.is_command_allowed("ls -la", context)
        
        # Exit lockdown mode
        permission_manager.exit_lockdown_mode()
        
        # Commands should work again
        assert permission_manager.is_command_allowed("git status", context)


class TestCommandCheckerWithRealPatterns:
    """Integration tests with realistic command patterns."""
    
    def test_git_workflow_integration(self):
        """Test complete git workflow."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r"^git .*")
        
        git_workflow = [
            "git init",
            "git add .",
            "git commit -m 'Initial commit'",
            "git branch develop",
            "git checkout develop",
            "git merge main",
            "git push origin develop",
            "git pull origin main",
            "git log --oneline",
            "git diff HEAD~1",
        ]
        
        for cmd in git_workflow:
            result = checker.validate_command(cmd)
            assert result.allowed, f"Git command rejected: {cmd}"
            assert result.category == CommandCategory.VERSION_CONTROL
    
    def test_npm_workflow_integration(self):
        """Test complete npm workflow."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r"^npm .*")
        
        npm_workflow = [
            "npm init -y",
            "npm install express",
            "npm install --save-dev jest",
            "npm test",
            "npm run build",
            "npm run dev",
            "npm audit",
            "npm update",
        ]
        
        for cmd in npm_workflow:
            result = checker.validate_command(cmd)
            assert result.allowed, f"NPM command rejected: {cmd}"
            assert result.category == CommandCategory.PACKAGE_MANAGEMENT
    
    def test_python_development_integration(self):
        """Test Python development workflow."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r"^python3? .*")
        checker.add_allowed_pattern(r"^pip3? .*")
        
        python_workflow = [
            "python script.py",
            "python -m pytest",
            "python -m venv venv",
            "pip install -r requirements.txt",
            "pip install numpy pandas",
            "python -m pip install --upgrade pip",
        ]
        
        for cmd in python_workflow:
            result = checker.validate_command(cmd)
            assert result.allowed, f"Python command rejected: {cmd}"
    
    def test_docker_workflow_integration(self):
        """Test Docker workflow with read-only commands."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r"^docker (ps|images|logs|inspect)")
        
        allowed_commands = [
            "docker ps",
            "docker ps -a",
            "docker images",
            "docker logs container_name",
            "docker inspect container_id",
        ]
        
        blocked_commands = [
            "docker rm container",
            "docker rmi image",
            "docker run image",
        ]
        
        for cmd in allowed_commands:
            result = checker.validate_command(cmd)
            assert result.allowed, f"Docker command rejected: {cmd}"
        
        for cmd in blocked_commands:
            result = checker.validate_command(cmd)
            assert not result.allowed, f"Docker command should be blocked: {cmd}"
    
    def test_kubernetes_workflow_integration(self):
        """Test Kubernetes workflow with read-only commands."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r"^kubectl get .*")
        checker.add_allowed_pattern(r"^kubectl describe .*")
        
        allowed_commands = [
            "kubectl get pods",
            "kubectl get services",
            "kubectl get deployments",
            "kubectl describe pod pod-name",
            "kubectl describe service service-name",
        ]
        
        blocked_commands = [
            "kubectl delete pod pod-name",
            "kubectl apply -f config.yaml",
            "kubectl create deployment",
        ]
        
        for cmd in allowed_commands:
            result = checker.validate_command(cmd)
            assert result.allowed, f"Kubectl command rejected: {cmd}"
        
        for cmd in blocked_commands:
            result = checker.validate_command(cmd)
            assert not result.allowed, f"Kubectl command should be blocked: {cmd}"


class TestCommandSecurityIntegration:
    """Integration tests for security features."""
    
    def test_layered_security_validation(self):
        """Test multiple layers of security validation."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")  # Allow everything
        checker.add_blocked_pattern(r".*secret.*")  # Block secrets
        
        # Test layered blocking
        test_cases = [
            ("cat secret.txt", False, "Blocked by pattern"),
            ("rm -rf /", False, "Dangerous command"),
            ("ls; rm file", False, "Injection attack"),
            ("ls -la", True, "Safe command"),
        ]
        
        for cmd, should_allow, reason in test_cases:
            result = checker.validate_command(cmd)
            assert result.allowed == should_allow, \
                f"{reason}: {cmd} (expected {should_allow}, got {result.allowed})"
    
    def test_comprehensive_injection_prevention(self):
        """Test comprehensive injection attack prevention."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        injection_attacks = [
            "ls; rm -rf /",
            "cat file && rm file",
            "echo test | rm file",
            "ls `whoami`",
            "cat $(cat /etc/passwd)",
            "ls <(echo test)",
            "cat >(cat)",
        ]
        
        for attack in injection_attacks:
            result = checker.validate_command(attack)
            assert not result.allowed, f"Injection not prevented: {attack}"
            assert "injection" in result.reason.lower() or \
                   result.danger_level == DangerLevel.CRITICAL
    
    def test_argument_validation_integration(self):
        """Test argument validation with real commands."""
        checker = CommandPermissionChecker()
        checker.add_allowed_pattern(r".*")
        
        # Commands with suspicious arguments
        suspicious_commands = [
            "cat ../../etc/passwd",  # Path traversal
            "echo $HOME",  # Environment variable
            "ls file;rm",  # Suspicious character
        ]
        
        for cmd in suspicious_commands:
            result = checker.validate_command(cmd, validate_args=True)
            # Should either be blocked or have warnings
            if result.allowed:
                assert len(result.warnings) > 0, \
                    f"No warnings for suspicious command: {cmd}"


class TestCommandPerformanceIntegration:
    """Integration tests for performance."""
    
    def test_large_pattern_set_performance(self):
        """Test performance with large number of patterns."""
        checker = CommandPermissionChecker()
        
        # Add 100 allowed patterns
        for i in range(100):
            checker.add_allowed_pattern(f"^command{i} .*")
        
        # Validation should still be fast
        import time
        start = time.time()
        
        for i in range(100):
            checker.validate_command(f"command{i} test")
        
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 1 second for 100 validations)
        assert elapsed < 1.0, f"Validation too slow: {elapsed}s"
    
    def test_complex_pattern_performance(self):
        """Test performance with complex regex patterns."""
        checker = CommandPermissionChecker()
        
        # Add complex patterns
        complex_patterns = [
            r"^(git|svn|hg) (status|commit|push|pull|checkout|branch|merge|rebase|log|diff).*",
            r"^(npm|yarn|pnpm) (install|test|build|run|start|dev|lint|format).*",
            r"^(docker|podman) (ps|images|logs|inspect|stats|top|version).*",
            r"^(kubectl|oc) (get|describe|logs|exec|port-forward|proxy) .*",
        ]
        
        for pattern in complex_patterns:
            checker.add_allowed_pattern(pattern)
        
        # Test validation performance
        import time
        start = time.time()
        
        test_commands = [
            "git status",
            "npm install",
            "docker ps",
            "kubectl get pods",
        ]
        
        for _ in range(100):
            for cmd in test_commands:
                checker.validate_command(cmd)
        
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 2.0, f"Complex pattern validation too slow: {elapsed}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
