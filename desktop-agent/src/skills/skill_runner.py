"""
Skill Runner - Main Execution Engine

The SkillRunner is the primary interface for executing skills with comprehensive
security, monitoring, and authority enforcement. It orchestrates all aspects
of skill execution including sandbox creation, monitoring, and cleanup.
"""

import tempfile
import shutil
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime
import logging
import json

from .manifest import SkillManifest, PermissionType
from .sandbox import ProcessSandbox, SandboxConfig, SandboxResult
from .registry import SkillRegistry
from .monitoring import ResourceUsage, SandboxViolation
from .exceptions import (
    SkillExecutionError,
    SkillNotFoundError,
    PermissionDeniedError,
    SandboxEscapeError,
    ResourceLimitExceededError,
    SandboxInitializationError
)


class SkillExecutionContext:
    """Context for skill execution with security and audit information."""
    
    def __init__(self, skill_id: str, user_id: str, session_id: str, 
                 authority_level: str, parameters: Dict[str, Any]):
        self.skill_id = skill_id
        self.user_id = user_id
        self.session_id = session_id
        self.authority_level = authority_level
        self.parameters = parameters
        self.execution_id = f"{skill_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
        # Execution tracking
        self.sandbox_directory: Optional[Path] = None
        self.violations: List[SandboxViolation] = []
        self.resource_usage: Optional[ResourceUsage] = None


class SkillExecutionResult:
    """Result of skill execution with comprehensive information."""
    
    def __init__(self, context: SkillExecutionContext, sandbox_result: SandboxResult):
        self.context = context
        self.sandbox_result = sandbox_result
        
        # Derived properties
        self.success = sandbox_result.success
        self.execution_time_seconds = sandbox_result.execution_time_seconds
        self.output = sandbox_result.stdout
        self.error_output = sandbox_result.stderr
        self.exit_code = sandbox_result.exit_code
        
        # Security information
        self.violations = sandbox_result.violations
        self.has_critical_violations = any(v.severity == "critical" for v in self.violations)
        self.resource_usage = sandbox_result.peak_resource_usage
        
        # Audit information
        self.audit_data = self._create_audit_data()
    
    def _create_audit_data(self) -> Dict[str, Any]:
        """Create audit data for logging."""
        return {
            'execution_id': self.context.execution_id,
            'skill_id': self.context.skill_id,
            'user_id': self.context.user_id,
            'session_id': self.context.session_id,
            'authority_level': self.context.authority_level,
            'start_time': self.context.start_time.isoformat(),
            'end_time': self.context.end_time.isoformat() if self.context.end_time else None,
            'execution_time_seconds': self.execution_time_seconds,
            'success': self.success,
            'exit_code': self.exit_code,
            'violations_count': len(self.violations),
            'critical_violations': self.has_critical_violations,
            'resource_usage': {
                'peak_cpu_percent': self.resource_usage.cpu_percent if self.resource_usage else None,
                'peak_memory_mb': self.resource_usage.memory_mb if self.resource_usage else None,
                'total_disk_mb': (self.resource_usage.disk_read_mb + self.resource_usage.disk_write_mb) if self.resource_usage else None,
                'total_network_kb': (self.resource_usage.network_sent_kb + self.resource_usage.network_recv_kb) if self.resource_usage else None
            } if self.resource_usage else None,
            'parameters_hash': hash(json.dumps(self.context.parameters, sort_keys=True))
        }


class SkillRunner:
    """Main skill execution engine with comprehensive security and monitoring."""
    
    def __init__(self, registry: SkillRegistry, 
                 authority_checker: Optional[Callable[[str], bool]] = None,
                 audit_logger: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.registry = registry
        self.authority_checker = authority_checker or (lambda level: True)  # Default: allow all
        self.audit_logger = audit_logger or (lambda data: None)  # Default: no logging
        self.logger = logging.getLogger(__name__)
        
        # Execution tracking
        self._active_executions: Dict[str, SkillExecutionContext] = {}
        
        # Security callbacks
        self._violation_handlers: List[Callable[[SandboxViolation], None]] = []
        self._resource_violation_handlers: List[Callable[[str, ResourceUsage], None]] = []
    
    def add_violation_handler(self, handler: Callable[[SandboxViolation], None]) -> None:
        """Add handler for sandbox violations."""
        self._violation_handlers.append(handler)
    
    def add_resource_violation_handler(self, handler: Callable[[str, ResourceUsage], None]) -> None:
        """Add handler for resource violations."""
        self._resource_violation_handlers.append(handler)
    
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any],
                     user_id: str, session_id: str, authority_level: str) -> SkillExecutionResult:
        """Execute a skill with comprehensive security and monitoring."""
        
        # Create execution context
        context = SkillExecutionContext(
            skill_id=skill_id,
            user_id=user_id,
            session_id=session_id,
            authority_level=authority_level,
            parameters=parameters
        )
        
        self.logger.info(f"Starting skill execution: {context.execution_id}")
        
        try:
            # Pre-execution validation
            self._validate_execution_request(context)
            
            # Get skill manifest
            manifest = self.registry.get_skill(skill_id)
            
            # Record execution start
            self.registry.record_execution_start(skill_id)
            self._active_executions[context.execution_id] = context
            
            # Create sandbox and execute
            sandbox_result = self._execute_in_sandbox(manifest, context)
            
            # Create result
            context.end_time = datetime.now()
            result = SkillExecutionResult(context, sandbox_result)
            
            # Audit logging
            self.audit_logger(result.audit_data)
            
            # Handle violations
            self._handle_execution_violations(result)
            
            self.logger.info(f"Skill execution completed: {context.execution_id} (success: {result.success})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Skill execution failed: {context.execution_id} - {e}")
            
            # Create error result
            context.end_time = datetime.now()
            error_result = SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_seconds=(context.end_time - context.start_time).total_seconds(),
                peak_resource_usage=None,
                violations=[],
                error_message=str(e)
            )
            
            result = SkillExecutionResult(context, error_result)
            self.audit_logger(result.audit_data)
            
            return result
            
        finally:
            # Cleanup
            self.registry.record_execution_end(skill_id)
            self._active_executions.pop(context.execution_id, None)
            
            # Cleanup sandbox directory
            if context.sandbox_directory and context.sandbox_directory.exists():
                try:
                    shutil.rmtree(context.sandbox_directory)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup sandbox directory: {e}")
    
    def _validate_execution_request(self, context: SkillExecutionContext) -> None:
        """Validate skill execution request."""
        
        # Check if skill exists
        try:
            manifest = self.registry.get_skill(context.skill_id)
        except SkillNotFoundError:
            raise SkillExecutionError(
                context.skill_id,
                "Skill not found in registry",
                exit_code=-1
            )
        
        # Check authority level
        if not self.registry.check_execution_permission(context.skill_id, context.authority_level):
            required_level = manifest.requires_authority_level()
            raise PermissionDeniedError(
                context.skill_id,
                f"authority_level_{required_level}",
                f"execute_skill (current: {context.authority_level}, required: {required_level})"
            )
        
        # Check rate limits
        if not self.registry.check_rate_limit(context.skill_id):
            stats = self.registry.get_execution_stats(context.skill_id)
            raise ResourceLimitExceededError(
                context.skill_id,
                "rate_limit",
                max(stats['calls_last_minute'], stats['calls_last_hour']),
                max(manifest.max_calls_per_minute, manifest.max_calls_per_hour)
            )
        
        # Validate parameters against manifest (basic validation)
        self._validate_parameters(manifest, context.parameters)
    
    def _validate_parameters(self, manifest: SkillManifest, parameters: Dict[str, Any]) -> None:
        """Validate parameters against skill requirements."""
        
        # Check for required parameters (if defined in metadata)
        required_params = manifest.metadata.get('required_parameters', [])
        for param in required_params:
            if param not in parameters:
                raise SkillExecutionError(
                    manifest.skill_id,
                    f"Required parameter missing: {param}",
                    exit_code=-1
                )
        
        # Validate file paths if filesystem access is requested
        if PermissionType.FILESYSTEM_READ in manifest.permissions.permissions or \
           PermissionType.FILESYSTEM_WRITE in manifest.permissions.permissions:
            
            for key, value in parameters.items():
                if isinstance(value, str) and ('path' in key.lower() or 'file' in key.lower()):
                    if not manifest.permissions.validate_filesystem_access(value):
                        raise PermissionDeniedError(
                            manifest.skill_id,
                            "filesystem_access",
                            f"Access denied to path: {value}"
                        )
        
        # Validate network hosts if network access is requested
        if PermissionType.NETWORK_ACCESS in manifest.permissions.permissions:
            for key, value in parameters.items():
                if isinstance(value, str) and ('host' in key.lower() or 'url' in key.lower()):
                    # Extract host from URL if needed
                    host = value
                    if '://' in value:
                        host = value.split('://')[1].split('/')[0].split(':')[0]
                    
                    if not manifest.permissions.validate_network_access(host):
                        raise PermissionDeniedError(
                            manifest.skill_id,
                            "network_access",
                            f"Access denied to host: {host}"
                        )
    
    def _execute_in_sandbox(self, manifest: SkillManifest, context: SkillExecutionContext) -> SandboxResult:
        """Execute skill in sandbox environment."""
        
        # Create temporary sandbox directory
        context.sandbox_directory = Path(tempfile.mkdtemp(prefix=f"skill_{manifest.skill_id}_"))
        
        # Prepare allowed paths
        allowed_paths = [context.sandbox_directory]
        for path_str in manifest.permissions.filesystem_paths:
            allowed_paths.append(Path(path_str).resolve())
        
        # Create sandbox configuration
        sandbox_config = SandboxConfig(
            working_directory=context.sandbox_directory,
            allowed_paths=allowed_paths,
            environment_variables={},
            python_path=[str(Path(__file__).parent.parent)],  # Add src directory to Python path
            timeout_seconds=manifest.resource_limits.max_execution_time_seconds,
            enable_network=PermissionType.NETWORK_ACCESS in manifest.permissions.permissions,
            enable_ui_access=PermissionType.UI_AUTOMATION in manifest.permissions.permissions
        )
        
        # Create sandbox
        sandbox = ProcessSandbox(manifest, sandbox_config)
        
        # Load skill code
        skill_code = self._load_skill_code(manifest)
        
        # Execute in sandbox
        return sandbox.execute_skill(skill_code, context.parameters)
    
    def _load_skill_code(self, manifest: SkillManifest) -> str:
        """Load skill code from entry point."""
        skill_file_path = self.registry.get_skill_file_path(manifest.skill_id)
        if not skill_file_path:
            raise SkillExecutionError(
                manifest.skill_id,
                "Skill file path not found in registry",
                exit_code=-1
            )
        
        entry_point_path = skill_file_path.parent / manifest.entry_point
        if not entry_point_path.exists():
            raise SkillExecutionError(
                manifest.skill_id,
                f"Entry point not found: {entry_point_path}",
                exit_code=-1
            )
        
        try:
            with open(entry_point_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise SkillExecutionError(
                manifest.skill_id,
                f"Failed to load skill code: {e}",
                exit_code=-1
            )
    
    def _handle_execution_violations(self, result: SkillExecutionResult) -> None:
        """Handle violations detected during execution."""
        
        for violation in result.violations:
            self.logger.warning(f"Skill violation: {violation.description}")
            
            # Call violation handlers
            for handler in self._violation_handlers:
                try:
                    handler(violation)
                except Exception as e:
                    self.logger.error(f"Error in violation handler: {e}")
            
            # Handle critical violations
            if violation.severity == "critical":
                self.logger.error(f"Critical violation in skill {result.context.skill_id}: {violation.description}")
                
                # Could implement additional responses like:
                # - Temporarily disable the skill
                # - Alert administrators
                # - Increase monitoring for this skill
    
    def get_active_executions(self) -> List[SkillExecutionContext]:
        """Get list of currently active skill executions."""
        return list(self._active_executions.values())
    
    def terminate_execution(self, execution_id: str) -> bool:
        """Terminate an active skill execution."""
        if execution_id not in self._active_executions:
            return False
        
        # In a full implementation, this would signal the sandbox to terminate
        # For now, we just log the termination request
        context = self._active_executions[execution_id]
        self.logger.warning(f"Termination requested for execution: {execution_id} (skill: {context.skill_id})")
        
        return True
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get overall execution statistics."""
        active_count = len(self._active_executions)
        active_skills = list(set(ctx.skill_id for ctx in self._active_executions.values()))
        
        return {
            'active_executions': active_count,
            'active_skills': active_skills,
            'total_registered_skills': len(self.registry.list_skills()),
            'registry_info': self.registry.export_registry_info()
        }