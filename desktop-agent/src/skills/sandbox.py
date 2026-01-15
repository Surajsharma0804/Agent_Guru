"""
Process Isolation Sandbox

Implements comprehensive process-level sandboxing for skill execution with:
- Process isolation using subprocess with restricted environment
- Resource monitoring and enforcement
- File system access control
- Network access restrictions
- Sandbox escape detection and prevention
"""

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import SandboxInitializationError
from .manifest import SkillManifest
from .monitoring import ResourceMonitor, SandboxMonitor, SandboxViolation


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    working_directory: Path
    allowed_paths: List[Path]
    environment_variables: Dict[str, str]
    python_path: List[str]
    timeout_seconds: int
    enable_network: bool = False
    enable_ui_access: bool = False
    
    def validate(self) -> List[str]:
        """Validate sandbox configuration."""
        errors = []
        
        if not self.working_directory.exists():
            errors.append(f"Working directory does not exist: {self.working_directory}")
        
        for path in self.allowed_paths:
            if not path.exists():
                errors.append(f"Allowed path does not exist: {path}")
        
        if self.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        
        return errors


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_seconds: float
    peak_resource_usage: Optional[Any]  # ResourceUsage from monitoring
    violations: List[SandboxViolation]
    error_message: Optional[str] = None


class ProcessSandbox:
    """Process-level sandbox for skill execution."""
    
    def __init__(self, manifest: SkillManifest, config: SandboxConfig):
        self.manifest = manifest
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Monitoring components
        self._resource_monitor: Optional[ResourceMonitor] = None
        self._sandbox_monitor: Optional[SandboxMonitor] = None
        
        # Process management
        self._process: Optional[subprocess.Popen] = None
        self._process_id: Optional[int] = None
        self._start_time: Optional[datetime] = None
        
        # Violation tracking
        self._violations: List[SandboxViolation] = []
        self._resource_violations: List[str] = []
        self._terminated_due_to_violation = False
        
        # Validate configuration
        config_errors = config.validate()
        if config_errors:
            raise SandboxInitializationError(
                f"Invalid sandbox configuration: {'; '.join(config_errors)}"
            )
    
    def execute_skill(self, skill_script: str, parameters: Dict[str, Any]) -> SandboxResult:
        """Execute skill in sandbox with comprehensive monitoring."""
        self.logger.info(f"Starting sandbox execution for skill {self.manifest.skill_id}")
        
        try:
            # Prepare sandbox environment
            sandbox_env = self._prepare_sandbox_environment()
            
            # Create skill execution script
            script_path = self._create_execution_script(skill_script, parameters)
            
            # Start process with restrictions
            self._start_process(script_path, sandbox_env)
            
            # Start monitoring
            self._start_monitoring()
            
            # Wait for completion or timeout
            result = self._wait_for_completion()
            
            # Stop monitoring
            self._stop_monitoring()
            
            # Cleanup
            self._cleanup_sandbox()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Sandbox execution failed: {e}")
            self._cleanup_sandbox()
            
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_seconds=0.0,
                peak_resource_usage=None,
                violations=[],
                error_message=str(e)
            )
    
    def _prepare_sandbox_environment(self) -> Dict[str, str]:
        """Prepare restricted environment for skill execution."""
        # Start with minimal environment
        sandbox_env = {
            'PATH': '',
            'PYTHONPATH': '',
            'TEMP': str(self.config.working_directory / 'temp'),
            'TMP': str(self.config.working_directory / 'temp'),
            'HOME': str(self.config.working_directory),
            'USERPROFILE': str(self.config.working_directory)
        }
        
        # Add Python to PATH if needed
        python_exe = sys.executable
        python_dir = str(Path(python_exe).parent)
        sandbox_env['PATH'] = python_dir
        
        # Set PYTHONPATH to allowed directories only
        if self.config.python_path:
            sandbox_env['PYTHONPATH'] = os.pathsep.join(str(p) for p in self.config.python_path)
        
        # Add manifest-specified environment variables (with validation)
        for key, value in self.config.environment_variables.items():
            # Validate environment variable names and values
            if self._is_safe_env_var(key, value):
                sandbox_env[key] = value
            else:
                self.logger.warning(f"Rejected unsafe environment variable: {key}={value}")
        
        # Disable network access unless explicitly allowed
        if not self.config.enable_network:
            sandbox_env['NO_PROXY'] = '*'
            sandbox_env['HTTP_PROXY'] = 'http://127.0.0.1:1'  # Invalid proxy to block HTTP
            sandbox_env['HTTPS_PROXY'] = 'http://127.0.0.1:1'  # Invalid proxy to block HTTPS
        
        return sandbox_env
    
    def _create_execution_script(self, skill_script: str, parameters: Dict[str, Any]) -> Path:
        """Create Python script for skill execution with safety wrappers."""
        script_content = f'''#!/usr/bin/env python3
"""
Sandboxed skill execution wrapper
Generated automatically - DO NOT MODIFY
"""

import sys
import os
import json
import traceback
from pathlib import Path

# Sandbox safety imports
import signal
import resource
import tempfile

def setup_resource_limits():
    """Set up process resource limits."""
    try:
        # Memory limit (in bytes)
        memory_limit = {self.manifest.resource_limits.max_memory_mb} * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        
        # CPU time limit (in seconds)
        cpu_limit = {self.manifest.resource_limits.max_execution_time_seconds}
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        
        # File descriptor limit
        fd_limit = {self.manifest.resource_limits.max_file_handles}
        resource.setrlimit(resource.RLIMIT_NOFILE, (fd_limit, fd_limit))
        
    except Exception as e:

def validate_file_access(path):
    """Validate file access against allowed paths."""
    allowed_paths = {[str(p) for p in self.config.allowed_paths]}
    path_obj = Path(path).resolve()
    
    for allowed_path in allowed_paths:
        try:
            path_obj.relative_to(Path(allowed_path).resolve())
            return True
        except ValueError:
            continue
    
    return False

def safe_open(path, mode='r', **kwargs):
    """Safe file opening with path validation."""
    if not validate_file_access(path):
        raise PermissionError(f"Access denied to path: {{path}}")
    return open(path, mode, **kwargs)

def main():
    """Main skill execution function."""
    try:
        # Set up resource limits
        setup_resource_limits()
        
        # Change to working directory
        os.chdir(r"{self.config.working_directory}")
        
        # Create temp directory
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        # Load parameters
        parameters = {json.dumps(parameters)}
        
        # Execute skill code
        skill_globals = {{
            '__name__': '__main__',
            '__file__': __file__,
            'parameters': parameters,
            'safe_open': safe_open,
            'validate_file_access': validate_file_access
        }}
        
        # Execute the actual skill code
        exec("""{skill_script}""", skill_globals)
        
        
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        # Write script to temporary file
        script_path = self.config.working_directory / f"skill_{self.manifest.skill_id}.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return script_path
    
    def _start_process(self, script_path: Path, env: Dict[str, str]) -> None:
        """Start the sandboxed process."""
        try:
            # Prepare command
            cmd = [sys.executable, str(script_path)]
            
            # Start process with restrictions
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.config.working_directory),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                # Security: Create new process group
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                preexec_fn=None if os.name == 'nt' else os.setsid
            )
            
            self._process_id = self._process.pid
            self._start_time = datetime.now()
            
            self.logger.info(f"Started sandboxed process {self._process_id} for skill {self.manifest.skill_id}")
            
        except Exception as e:
            raise SandboxInitializationError(f"Failed to start sandboxed process: {e}")
    
    def _start_monitoring(self) -> None:
        """Start resource and sandbox monitoring."""
        if not self._process_id:
            return
        
        # Start resource monitoring
        self._resource_monitor = ResourceMonitor(
            process_id=self._process_id,
            limits=self.manifest.resource_limits,
            violation_callback=self._handle_resource_violation
        )
        self._resource_monitor.start_monitoring()
        
        # Start sandbox monitoring
        allowed_paths = [str(p) for p in self.config.allowed_paths]
        self._sandbox_monitor = SandboxMonitor(
            process_id=self._process_id,
            allowed_paths=allowed_paths,
            violation_callback=self._handle_sandbox_violation
        )
        self._sandbox_monitor.start_monitoring()
    
    def _stop_monitoring(self) -> None:
        """Stop all monitoring."""
        if self._resource_monitor:
            self._resource_monitor.stop_monitoring()
        
        if self._sandbox_monitor:
            self._sandbox_monitor.stop_monitoring()
    
    def _wait_for_completion(self) -> SandboxResult:
        """Wait for process completion with timeout and monitoring."""
        if not self._process:
            raise SandboxInitializationError("No process to wait for")
        
        try:
            # Wait for process with timeout
            stdout, stderr = self._process.communicate(timeout=self.config.timeout_seconds)
            exit_code = self._process.returncode
            
            # Calculate execution time
            execution_time = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0.0
            
            # Get peak resource usage
            peak_usage = None
            if self._resource_monitor:
                peak_usage = self._resource_monitor.get_peak_usage()
            
            # Collect violations
            all_violations = self._violations.copy()
            if self._sandbox_monitor:
                all_violations.extend(self._sandbox_monitor.get_violations())
            
            # Determine success
            success = (
                exit_code == 0 and 
                not self._terminated_due_to_violation and
                not any(v.severity == "critical" for v in all_violations)
            )
            
            return SandboxResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time_seconds=execution_time,
                peak_resource_usage=peak_usage,
                violations=all_violations,
                error_message=None if success else "Execution failed or violations detected"
            )
            
        except subprocess.TimeoutExpired:
            # Process timed out - terminate it
            self._terminate_process()
            
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Process timed out after {self.config.timeout_seconds} seconds",
                execution_time_seconds=self.config.timeout_seconds,
                peak_resource_usage=None,
                violations=self._violations,
                error_message="Execution timeout"
            )
        
        except Exception as e:
            self.logger.error(f"Error waiting for process completion: {e}")
            self._terminate_process()
            
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_seconds=0.0,
                peak_resource_usage=None,
                violations=self._violations,
                error_message=str(e)
            )
    
    def _handle_resource_violation(self, violation_type: str, usage) -> None:
        """Handle resource limit violations."""
        self.logger.warning(f"Resource violation detected: {violation_type}")
        self._resource_violations.append(violation_type)
        
        # Terminate process on critical resource violations
        critical_violations = ["memory", "cpu_percent"]
        if any(critical in violation_type for critical in critical_violations):
            self.logger.error(f"Critical resource violation: {violation_type} - terminating process")
            self._terminated_due_to_violation = True
            self._terminate_process()
    
    def _handle_sandbox_violation(self, violation: SandboxViolation) -> None:
        """Handle sandbox escape violations."""
        self.logger.warning(f"Sandbox violation detected: {violation.description}")
        self._violations.append(violation)
        
        # Terminate process on critical violations
        if violation.severity == "critical":
            self.logger.error(f"Critical sandbox violation: {violation.description} - terminating process")
            self._terminated_due_to_violation = True
            self._terminate_process()
    
    def _terminate_process(self) -> None:
        """Forcefully terminate the sandboxed process."""
        if not self._process:
            return
        
        try:
            if os.name == 'nt':
                # Windows: Terminate process group
                self._process.terminate()
                time.sleep(1)
                if self._process.poll() is None:
                    self._process.kill()
            else:
                # Unix: Kill process group
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                time.sleep(1)
                if self._process.poll() is None:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            
            self.logger.info(f"Terminated sandboxed process {self._process_id}")
            
        except Exception as e:
            self.logger.error(f"Error terminating process: {e}")
    
    def _cleanup_sandbox(self) -> None:
        """Clean up sandbox resources."""
        try:
            # Remove temporary files
            temp_dir = self.config.working_directory / "temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Remove execution script
            script_path = self.config.working_directory / f"skill_{self.manifest.skill_id}.py"
            if script_path.exists():
                script_path.unlink()
            
            self.logger.debug(f"Cleaned up sandbox for skill {self.manifest.skill_id}")
            
        except Exception as e:
            self.logger.warning(f"Error during sandbox cleanup: {e}")
    
    def _is_safe_env_var(self, key: str, value: str) -> bool:
        """Check if environment variable is safe to set."""
        # Deny dangerous environment variables
        dangerous_vars = {
            'PATH', 'PYTHONPATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
            'HOME', 'USERPROFILE', 'TEMP', 'TMP', 'TMPDIR',
            'HTTP_PROXY', 'HTTPS_PROXY', 'FTP_PROXY', 'NO_PROXY'
        }
        
        if key.upper() in dangerous_vars:
            return False
        
        # Check for suspicious values
        if any(suspicious in value.lower() for suspicious in ['cmd', 'powershell', 'bash', 'sh', '..', '/']):
            return False
        
        return True
    
    def get_violations(self) -> List[SandboxViolation]:
        """Get all recorded violations."""
        all_violations = self._violations.copy()
        if self._sandbox_monitor:
            all_violations.extend(self._sandbox_monitor.get_violations())
        return all_violations
    
    def has_critical_violations(self) -> bool:
        """Check if any critical violations occurred."""
        return any(v.severity == "critical" for v in self.get_violations())