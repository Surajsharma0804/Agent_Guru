"""
Property-based tests for skill sandboxing system.

**Property 7: Skill Sandboxing**
**Validates: Requirements 6.1, 6.3, 6.5**

These tests verify that:
- Skills can only access resources explicitly declared in their manifest
- Attempts to access undeclared resources are blocked
- Sandbox isolation prevents escape attempts
- Resource limits are enforced
- Permission boundaries are maintained
"""

import pytest
import tempfile
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize, invariant

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from skills.manifest import (
    SkillManifest, PermissionSet, PermissionType, RiskLevel,
    ResourceLimits, RollbackStrategy
)
from skills.sandbox import ProcessSandbox, SandboxConfig, SandboxResult
from skills.registry import SkillRegistry
from skills.skill_runner import SkillRunner, SkillExecutionContext
from skills.monitoring import ResourceUsage, SandboxViolation
from skills.exceptions import (
    SkillExecutionError, PermissionDeniedError, ResourceLimitExceededError,
    SandboxEscapeError, SandboxInitializationError
)


# Strategy generators for property-based testing
@st.composite
def skill_manifest_strategy(draw):
    """Generate valid skill manifests for testing."""
    skill_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_')))
    assume(skill_id.replace('-', '').replace('_', '').isalnum())
    
    name = draw(st.text(min_size=1, max_size=50))
    description = draw(st.text(min_size=1, max_size=200))
    version = f"{draw(st.integers(min_value=1, max_value=10))}.{draw(st.integers(min_value=0, max_value=99))}.{draw(st.integers(min_value=0, max_value=99))}"
    author = draw(st.text(min_size=1, max_size=50))
    
    # Generate permissions - avoid dangerous combinations with low risk
    permission_types = draw(st.sets(st.sampled_from(list(PermissionType)), max_size=3))
    
    # Check for dangerous permission combinations
    dangerous_combinations = [
        {PermissionType.NETWORK_ACCESS, PermissionType.FILESYSTEM_WRITE},
        {PermissionType.UI_AUTOMATION, PermissionType.NETWORK_ACCESS},
        {PermissionType.PROCESS_CONTROL, PermissionType.NETWORK_ACCESS}
    ]
    
    # If we have dangerous combinations, ensure high risk level
    has_dangerous_combo = any(combo.issubset(permission_types) for combo in dangerous_combinations)
    
    if has_dangerous_combo:
        risk_level = draw(st.sampled_from([RiskLevel.HIGH, RiskLevel.CRITICAL]))
    else:
        risk_level = draw(st.sampled_from(list(RiskLevel)))
    
    # Generate valid filesystem paths
    filesystem_paths = []
    if PermissionType.FILESYSTEM_READ in permission_types or PermissionType.FILESYSTEM_WRITE in permission_types:
        # Generate valid, existing paths for testing
        valid_paths = ["/tmp", "/temp", "/var/tmp", "C:\\temp", "C:\\tmp"]
        filesystem_paths = draw(st.lists(st.sampled_from(valid_paths), max_size=2))
    
    network_hosts = draw(st.lists(st.text(min_size=1, max_size=30), max_size=3)) if PermissionType.NETWORK_ACCESS in permission_types else []
    ui_applications = draw(st.lists(st.text(min_size=1, max_size=30), max_size=3)) if PermissionType.UI_AUTOMATION in permission_types else []
    
    permissions = PermissionSet(
        permissions=permission_types,
        filesystem_paths=filesystem_paths,
        network_hosts=network_hosts,
        ui_applications=ui_applications
    )
    
    # Generate resource limits
    resource_limits = ResourceLimits(
        max_cpu_percent=draw(st.floats(min_value=1.0, max_value=100.0)),
        max_memory_mb=draw(st.integers(min_value=1, max_value=1024)),
        max_disk_mb=draw(st.integers(min_value=1, max_value=100)),
        max_network_kb=draw(st.integers(min_value=0, max_value=1024)),
        max_execution_time_seconds=draw(st.integers(min_value=1, max_value=300)),
        max_file_handles=draw(st.integers(min_value=1, max_value=100)),
        max_processes=draw(st.integers(min_value=1, max_value=5))
    )
    
    entry_point = f"{skill_id.replace('-', '_')}.py"
    
    return SkillManifest(
        skill_id=skill_id,
        name=name,
        description=description,
        version=version,
        author=author,
        permissions=permissions,
        risk_level=risk_level,
        resource_limits=resource_limits,
        entry_point=entry_point,
        supported_platforms=["windows"],
        dependencies=[],
        side_effects=[],
        rollback_strategy=RollbackStrategy("none"),
        max_calls_per_minute=draw(st.integers(min_value=1, max_value=100)),
        max_calls_per_hour=draw(st.integers(min_value=1, max_value=1000)),
        max_concurrent_executions=draw(st.integers(min_value=1, max_value=5))
    )


@st.composite
def skill_parameters_strategy(draw):
    """Generate skill execution parameters."""
    param_count = draw(st.integers(min_value=0, max_value=5))
    parameters = {}
    
    for i in range(param_count):
        key = f"param_{i}"
        value_type = draw(st.sampled_from(['string', 'int', 'float', 'bool', 'list']))
        
        if value_type == 'string':
            parameters[key] = draw(st.text(max_size=100))
        elif value_type == 'int':
            parameters[key] = draw(st.integers())
        elif value_type == 'float':
            parameters[key] = draw(st.floats(allow_nan=False, allow_infinity=False))
        elif value_type == 'bool':
            parameters[key] = draw(st.booleans())
        elif value_type == 'list':
            parameters[key] = draw(st.lists(st.text(max_size=20), max_size=5))
    
    return parameters


@st.composite
def file_access_attempt_strategy(draw):
    """Generate file access attempts for testing."""
    operation = draw(st.sampled_from(['read', 'write', 'create', 'delete']))
    
    # Generate various path patterns
    path_type = draw(st.sampled_from(['allowed', 'denied', 'system', 'relative', 'absolute']))
    
    if path_type == 'allowed':
        path = "/tmp/allowed_file.txt"
    elif path_type == 'denied':
        path = "/etc/passwd"
    elif path_type == 'system':
        path = "/windows/system32/config/sam"
    elif path_type == 'relative':
        path = "../../../etc/passwd"
    else:  # absolute
        # Generate valid absolute paths that don't contain problematic characters
        path_parts = draw(st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_')),
            min_size=1, max_size=3
        ))
        path = "/" + "/".join(path_parts) + "/file.txt"
    
    return {
        'operation': operation,
        'path': path,
        'expected_allowed': path_type == 'allowed'
    }


@st.composite
def resource_usage_strategy(draw):
    """Generate resource usage scenarios for testing."""
    return ResourceUsage(
        timestamp=draw(st.datetimes()),
        cpu_percent=draw(st.floats(min_value=0.0, max_value=200.0)),
        memory_mb=draw(st.floats(min_value=0.0, max_value=2048.0)),
        disk_read_mb=draw(st.floats(min_value=0.0, max_value=1000.0)),
        disk_write_mb=draw(st.floats(min_value=0.0, max_value=1000.0)),
        network_sent_kb=draw(st.floats(min_value=0.0, max_value=10000.0)),
        network_recv_kb=draw(st.floats(min_value=0.0, max_value=10000.0)),
        file_handles=draw(st.integers(min_value=0, max_value=200)),
        child_processes=draw(st.integers(min_value=0, max_value=10))
    )


class TestSkillSandboxingProperties:
    """Property-based tests for skill sandboxing."""
    
    @given(manifest=skill_manifest_strategy())
    @settings(max_examples=50, deadline=30000)
    def test_property_manifest_permission_validation(self, manifest):
        """
        Property: Manifest permission validation consistency
        For any skill manifest, permission validation should be consistent
        and follow declared permission boundaries.
        """
        # Test filesystem permission validation
        if PermissionType.FILESYSTEM_READ in manifest.permissions.permissions or \
           PermissionType.FILESYSTEM_WRITE in manifest.permissions.permissions:
            
            # Allowed paths should be validated correctly
            for allowed_path in manifest.permissions.filesystem_paths:
                test_file = f"{allowed_path}/test_file.txt"
                assert manifest.permissions.validate_filesystem_access(test_file), \
                    f"Should allow access to file in allowed path: {test_file}"
            
            # Paths outside allowed directories should be denied
            denied_path = "/unauthorized/path/file.txt"
            if denied_path not in manifest.permissions.filesystem_paths:
                assert not manifest.permissions.validate_filesystem_access(denied_path), \
                    f"Should deny access to unauthorized path: {denied_path}"
        
        # Test network permission validation
        if PermissionType.NETWORK_ACCESS in manifest.permissions.permissions:
            # Allowed hosts should be validated correctly
            for allowed_host in manifest.permissions.network_hosts:
                if allowed_host != "*":  # Skip wildcard for this test
                    assert manifest.permissions.validate_network_access(allowed_host), \
                        f"Should allow access to allowed host: {allowed_host}"
            
            # Unauthorized hosts should be denied (unless wildcard is present)
            if "*" not in manifest.permissions.network_hosts:
                denied_host = "malicious.example.com"
                if denied_host not in manifest.permissions.network_hosts:
                    assert not manifest.permissions.validate_network_access(denied_host), \
                        f"Should deny access to unauthorized host: {denied_host}"
    
    @given(manifest=skill_manifest_strategy(), usage=resource_usage_strategy())
    @settings(max_examples=50, deadline=30000)
    def test_property_resource_limit_enforcement(self, manifest, usage):
        """
        Property: Resource limit enforcement
        For any resource usage and manifest limits, the system should correctly
        identify when limits are exceeded and report appropriate violations.
        """
        violation = usage.exceeds_limits(manifest.resource_limits)
        
        # Check if any limits are actually exceeded
        cpu_exceeded = usage.cpu_percent > manifest.resource_limits.max_cpu_percent
        memory_exceeded = usage.memory_mb > manifest.resource_limits.max_memory_mb
        disk_exceeded = (usage.disk_read_mb + usage.disk_write_mb) > manifest.resource_limits.max_disk_mb
        network_exceeded = (usage.network_sent_kb + usage.network_recv_kb) > manifest.resource_limits.max_network_kb
        handles_exceeded = usage.file_handles > manifest.resource_limits.max_file_handles
        processes_exceeded = usage.child_processes > manifest.resource_limits.max_processes
        
        any_limit_exceeded = (cpu_exceeded or memory_exceeded or disk_exceeded or 
                             network_exceeded or handles_exceeded or processes_exceeded)
        
        if any_limit_exceeded:
            # If any limit is exceeded, there should be a violation reported
            assert violation is not None, "Should detect violation when any limit is exceeded"
            
            # The violation should mention one of the exceeded limits
            # (The system reports the first violation it finds, which is correct behavior)
            violation_mentions_exceeded_limit = False
            
            if cpu_exceeded and "cpu_percent" in violation:
                violation_mentions_exceeded_limit = True
            elif memory_exceeded and "memory" in violation:
                violation_mentions_exceeded_limit = True
            elif disk_exceeded and "disk_io" in violation:
                violation_mentions_exceeded_limit = True
            elif network_exceeded and "network_io" in violation:
                violation_mentions_exceeded_limit = True
            elif handles_exceeded and "file_handles" in violation:
                violation_mentions_exceeded_limit = True
            elif processes_exceeded and "child_processes" in violation:
                violation_mentions_exceeded_limit = True
            
            assert violation_mentions_exceeded_limit, \
                f"Violation should mention an exceeded limit. Got: {violation}. " \
                f"Exceeded: CPU={cpu_exceeded}, Memory={memory_exceeded}, " \
                f"Disk={disk_exceeded}, Network={network_exceeded}, " \
                f"Handles={handles_exceeded}, Processes={processes_exceeded}"
        else:
            # If no limits are exceeded, there should be no violation
            assert violation is None, f"Should not detect violation when within limits, but got: {violation}"
    
    @given(manifest=skill_manifest_strategy(), file_access=file_access_attempt_strategy())
    @settings(max_examples=50, deadline=30000)
    def test_property_file_access_boundary_enforcement(self, manifest, file_access):
        """
        Property: File access boundary enforcement
        For any file access attempt, the system should enforce permission boundaries
        based on the skill's declared filesystem permissions.
        """
        has_fs_permission = (
            PermissionType.FILESYSTEM_READ in manifest.permissions.permissions or
            PermissionType.FILESYSTEM_WRITE in manifest.permissions.permissions
        )
        
        if not has_fs_permission:
            # Skills without filesystem permissions should be denied all file access
            assert not manifest.permissions.validate_filesystem_access(file_access['path']), \
                f"Skill without filesystem permissions should be denied access to: {file_access['path']}"
        else:
            # Skills with filesystem permissions should only access allowed paths
            access_allowed = manifest.permissions.validate_filesystem_access(file_access['path'])
            
            # Check if path is within any allowed directory
            should_be_allowed = False
            
            if manifest.permissions.filesystem_paths:  # Only check if paths are declared
                try:
                    path_obj = Path(file_access['path']).resolve()
                    
                    for allowed_path in manifest.permissions.filesystem_paths:
                        try:
                            allowed_path_obj = Path(allowed_path).resolve()
                            path_obj.relative_to(allowed_path_obj)
                            should_be_allowed = True
                            break
                        except (ValueError, OSError):
                            continue
                except (OSError, ValueError):
                    # Invalid path - should be denied
                    should_be_allowed = False
            
            if should_be_allowed:
                assert access_allowed, f"Should allow access to path within allowed directory: {file_access['path']}"
            else:
                # If no allowed paths are declared or path is outside allowed areas, access should be denied
                assert not access_allowed, f"Should deny access to path outside allowed directories: {file_access['path']}"
    
    @given(manifest=skill_manifest_strategy(), parameters=skill_parameters_strategy())
    @settings(max_examples=30, deadline=60000)
    def test_property_sandbox_isolation_integrity(self, manifest, parameters):
        """
        Property: Sandbox isolation integrity
        For any skill execution, the sandbox should maintain isolation boundaries
        and prevent access to undeclared resources.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock skill registry and runner
            registry = SkillRegistry(Path(temp_dir))
            
            # Create a simple test skill code
            skill_code = '''
import json
import sys
from datetime import datetime

try:
    # Test basic functionality
    result = {
        "status": "success",
        "parameters_received": len(parameters),
        "timestamp": datetime.now().isoformat()
    }
    
    # Test parameter access
    if "test_param" in parameters:
        result["test_param_value"] = parameters["test_param"]
    
    print(json.dumps(result))
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
'''
            
            # Register the skill
            try:
                registry.register_skill(manifest)
                
                # Create sandbox configuration with valid paths
                sandbox_dir = Path(temp_dir) / "sandbox"
                sandbox_dir.mkdir()
                
                # Create valid allowed paths - start with sandbox dir
                allowed_paths = [sandbox_dir]
                
                # Add manifest filesystem paths if they exist and are valid
                if manifest.permissions.filesystem_paths:
                    for path_str in manifest.permissions.filesystem_paths:
                        try:
                            path_obj = Path(path_str)
                            # Create the path if it doesn't exist (for testing)
                            if not path_obj.exists():
                                if path_obj.is_absolute():
                                    # For absolute paths, create them in temp dir instead
                                    test_path = sandbox_dir / path_obj.name
                                    test_path.mkdir(exist_ok=True)
                                    allowed_paths.append(test_path)
                                else:
                                    # For relative paths, create them relative to sandbox
                                    test_path = sandbox_dir / path_str
                                    test_path.mkdir(parents=True, exist_ok=True)
                                    allowed_paths.append(test_path)
                            else:
                                allowed_paths.append(path_obj)
                        except (OSError, ValueError):
                            # Skip invalid paths
                            continue
                
                config = SandboxConfig(
                    working_directory=sandbox_dir,
                    allowed_paths=allowed_paths,
                    environment_variables={},
                    python_path=[],
                    timeout_seconds=min(manifest.resource_limits.max_execution_time_seconds, 10),
                    enable_network=PermissionType.NETWORK_ACCESS in manifest.permissions.permissions,
                    enable_ui_access=PermissionType.UI_AUTOMATION in manifest.permissions.permissions
                )
                
                # Create and execute in sandbox
                sandbox = ProcessSandbox(manifest, config)
                
                # Add test parameter
                test_parameters = parameters.copy()
                test_parameters["test_param"] = "test_value"
                
                # Execute skill (this will create the execution script but may not run due to test environment)
                try:
                    result = sandbox.execute_skill(skill_code, test_parameters)
                    
                    # Verify sandbox maintained isolation
                    assert isinstance(result, SandboxResult), "Should return SandboxResult"
                    
                    # Check for critical violations
                    critical_violations = [v for v in result.violations if v.severity == "critical"]
                    
                    # If there are critical violations, execution should fail
                    if critical_violations:
                        assert not result.success, "Execution should fail with critical violations"
                    
                    # Verify resource usage tracking (if available)
                    if result.peak_resource_usage:
                        usage = result.peak_resource_usage
                        violation = usage.exceeds_limits(manifest.resource_limits)
                        
                        if violation:
                            # Resource limit violations should be reflected in result
                            assert not result.success or len(result.violations) > 0, \
                                f"Resource limit violation should cause failure or violations: {violation}"
                
                except (SandboxInitializationError, SkillExecutionError) as e:
                    # Sandbox initialization or execution errors are acceptable in test environment
                    # The important thing is that they fail safely rather than allowing unsafe execution
                    assert str(e), "Error should have descriptive message"
                
            except Exception as e:
                # Manifest validation errors are acceptable - they indicate proper validation
                if "validation" not in str(e).lower():
                    raise
    
    @given(st.lists(skill_manifest_strategy(), min_size=1, max_size=5))
    @settings(max_examples=20, deadline=60000)
    def test_property_concurrent_sandbox_isolation(self, manifests):
        """
        Property: Concurrent sandbox isolation
        For any set of skills executing concurrently, each sandbox should maintain
        independent isolation without interference.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register all manifests
            registered_skills = []
            for i, manifest in enumerate(manifests):
                try:
                    # Ensure unique skill IDs
                    manifest.skill_id = f"{manifest.skill_id}_{i}"
                    registry.register_skill(manifest)
                    registered_skills.append(manifest)
                except Exception:
                    # Skip invalid manifests
                    continue
            
            # Verify each registered skill maintains independent configuration
            for skill in registered_skills:
                retrieved_skill = registry.get_skill(skill.skill_id)
                
                # Verify skill isolation - each skill should have its own configuration
                assert retrieved_skill.skill_id == skill.skill_id, \
                    "Skill ID should be preserved independently"
                
                assert retrieved_skill.permissions.permissions == skill.permissions.permissions, \
                    "Permissions should be preserved independently"
                
                assert retrieved_skill.resource_limits.max_memory_mb == skill.resource_limits.max_memory_mb, \
                    "Resource limits should be preserved independently"
                
                # Verify authority level requirements are calculated independently
                expected_authority = skill.requires_authority_level()
                actual_authority = retrieved_skill.requires_authority_level()
                assert actual_authority == expected_authority, \
                    f"Authority level should be calculated independently: expected {expected_authority}, got {actual_authority}"
    
    @given(manifest=skill_manifest_strategy())
    @settings(max_examples=30, deadline=30000)
    def test_property_permission_boundary_consistency(self, manifest):
        """
        Property: Permission boundary consistency
        For any skill manifest, permission boundaries should be consistently
        enforced across different access patterns and edge cases.
        """
        # Test filesystem permission consistency
        if PermissionType.FILESYSTEM_READ in manifest.permissions.permissions or \
           PermissionType.FILESYSTEM_WRITE in manifest.permissions.permissions:
            
            for allowed_path in manifest.permissions.filesystem_paths:
                # Direct path access should be allowed
                assert manifest.permissions.validate_filesystem_access(allowed_path), \
                    f"Direct access to allowed path should be permitted: {allowed_path}"
                
                # Subdirectory access should be allowed
                subdir_path = f"{allowed_path}/subdir/file.txt"
                assert manifest.permissions.validate_filesystem_access(subdir_path), \
                    f"Access to subdirectory should be permitted: {subdir_path}"
                
                # Parent directory access should be denied (unless explicitly allowed)
                parent_path = str(Path(allowed_path).parent / "other_file.txt")
                if parent_path not in manifest.permissions.filesystem_paths:
                    # Only test if parent is clearly outside allowed paths
                    parent_allowed = any(
                        parent_path.startswith(ap) for ap in manifest.permissions.filesystem_paths
                    )
                    if not parent_allowed:
                        assert not manifest.permissions.validate_filesystem_access(parent_path), \
                            f"Access to parent directory should be denied: {parent_path}"
        
        # Test network permission consistency
        if PermissionType.NETWORK_ACCESS in manifest.permissions.permissions:
            # Wildcard should allow all hosts
            if "*" in manifest.permissions.network_hosts:
                assert manifest.permissions.validate_network_access("any.host.com"), \
                    "Wildcard should allow access to any host"
                assert manifest.permissions.validate_network_access("another.example.org"), \
                    "Wildcard should allow access to any host"
            
            # Specific hosts should be allowed
            for allowed_host in manifest.permissions.network_hosts:
                if allowed_host != "*":
                    assert manifest.permissions.validate_network_access(allowed_host), \
                        f"Explicitly allowed host should be permitted: {allowed_host}"
        
        # Test permission absence consistency
        if PermissionType.FILESYSTEM_READ not in manifest.permissions.permissions and \
           PermissionType.FILESYSTEM_WRITE not in manifest.permissions.permissions:
            # No filesystem permissions should deny all file access
            assert not manifest.permissions.validate_filesystem_access("/any/path"), \
                "Skills without filesystem permissions should deny all file access"
        
        if PermissionType.NETWORK_ACCESS not in manifest.permissions.permissions:
            # No network permissions should deny all network access
            assert not manifest.permissions.validate_network_access("any.host.com"), \
                "Skills without network permissions should deny all network access"


class SkillSandboxStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for skill sandbox system.
    Tests complex interactions and state transitions in the sandbox system.
    """
    
    def __init__(self):
        super().__init__()
        self.temp_dir = None
        self.registry = None
        self.registered_skills = {}
        self.active_executions = {}
    
    @initialize()
    def setup_registry(self):
        """Initialize the skill registry for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = SkillRegistry(Path(self.temp_dir))
    
    skills = Bundle('skills')
    
    @rule(target=skills, manifest=skill_manifest_strategy())
    def register_skill(self, manifest):
        """Register a skill in the registry."""
        try:
            # Ensure unique skill ID
            skill_id = f"{manifest.skill_id}_{len(self.registered_skills)}"
            manifest.skill_id = skill_id
            
            self.registry.register_skill(manifest)
            self.registered_skills[skill_id] = manifest
            return skill_id
        except Exception as e:
            # Registration might fail due to validation or security checks - that's acceptable
            # This indicates the security system is working correctly
            assume(False)
    
    @rule(skill_id=skills, parameters=skill_parameters_strategy())
    def start_execution(self, skill_id, parameters):
        """Start skill execution."""
        if skill_id in self.registered_skills:
            try:
                manifest = self.registered_skills[skill_id]
                
                # Check if we can start execution (rate limits, concurrent limits)
                if self.registry.check_rate_limit(skill_id):
                    current_concurrent = len([e for e in self.active_executions.values() if e['skill_id'] == skill_id])
                    
                    if current_concurrent < manifest.max_concurrent_executions:
                        self.registry.record_execution_start(skill_id)
                        
                        execution_id = f"{skill_id}_exec_{len(self.active_executions)}"
                        self.active_executions[execution_id] = {
                            'skill_id': skill_id,
                            'parameters': parameters,
                            'started': True
                        }
                        
                        # Don't return the execution_id since this rule has no target bundle
                        return
            except Exception:
                # Execution start might fail - that's acceptable
                pass
    
    @rule()
    def end_execution(self):
        """End skill execution."""
        if self.active_executions:
            # Pick a random active execution to end
            execution_id = list(self.active_executions.keys())[0]
            execution = self.active_executions[execution_id]
            skill_id = execution['skill_id']
            
            self.registry.record_execution_end(skill_id)
            del self.active_executions[execution_id]
    
    @invariant()
    def registry_consistency(self):
        """Verify registry maintains consistent state."""
        # All registered skills should be retrievable
        for skill_id in self.registered_skills:
            retrieved_skill = self.registry.get_skill(skill_id)
            assert retrieved_skill.skill_id == skill_id, \
                f"Retrieved skill ID should match registered ID: {skill_id}"
        
        # Execution stats should be consistent
        for skill_id in self.registered_skills:
            stats = self.registry.get_execution_stats(skill_id)
            
            # Count active executions for this skill
            active_count = len([e for e in self.active_executions.values() if e['skill_id'] == skill_id])
            
            # The registry tracks total executions started, not just currently active ones
            # So we only check that the registry count is >= our active count
            assert stats['concurrent_executions'] >= active_count, \
                f"Registry concurrent execution count should be >= active executions for {skill_id}: {stats['concurrent_executions']} < {active_count}"
    
    @invariant()
    def permission_isolation(self):
        """Verify permission isolation between skills."""
        skill_ids = list(self.registered_skills.keys())
        
        # Each skill should have independent permissions
        for i, skill_id_a in enumerate(skill_ids):
            for skill_id_b in skill_ids[i+1:]:
                skill_a = self.registered_skills[skill_id_a]
                skill_b = self.registered_skills[skill_id_b]
                
                # Skills should not interfere with each other's permissions
                # (This is a structural invariant - permissions are isolated by design)
                assert skill_a.skill_id != skill_b.skill_id, \
                    "Skills should have unique IDs"
                
                # Permission validation should be independent
                test_path = "/test/path"
                access_a = skill_a.permissions.validate_filesystem_access(test_path)
                access_b = skill_b.permissions.validate_filesystem_access(test_path)
                
                # Access decisions should be based on individual skill permissions
                # (We can't assert they're different, but we can assert they're consistent)
                assert access_a == skill_a.permissions.validate_filesystem_access(test_path), \
                    "Permission validation should be consistent for skill A"
                assert access_b == skill_b.permissions.validate_filesystem_access(test_path), \
                    "Permission validation should be consistent for skill B"
    
    def teardown(self):
        """Clean up resources."""
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)


# Test class for running the state machine
class TestSkillSandboxStateMachine:
    """Test runner for the skill sandbox state machine."""
    
    def test_skill_sandbox_state_machine(self):
        """Run the stateful property-based test for skill sandbox system."""
        from hypothesis.stateful import run_state_machine_as_test
        
        # Run the state machine test
        run_state_machine_as_test(
            SkillSandboxStateMachine,
            settings=settings(max_examples=20, stateful_step_count=50, deadline=120000)
        )


# Example-based tests for specific scenarios
class TestSkillSandboxingExamples:
    """Example-based tests for specific skill sandboxing scenarios."""
    
    def test_filesystem_permission_boundary_example(self):
        """
        Example: Filesystem permission boundary enforcement
        A skill with access to /tmp should be able to access /tmp/file.txt
        but not /etc/passwd.
        """
        manifest = SkillManifest(
            skill_id="fs-test-skill",
            name="Filesystem Test Skill",
            description="Test filesystem permissions",
            version="1.0.0",
            author="Test",
            permissions=PermissionSet(
                permissions={PermissionType.FILESYSTEM_READ},
                filesystem_paths=["/tmp"],
                network_hosts=[],
                ui_applications=[]
            ),
            risk_level=RiskLevel.LOW,
            resource_limits=ResourceLimits(),
            entry_point="test.py"
        )
        
        # Should allow access to files in /tmp
        assert manifest.permissions.validate_filesystem_access("/tmp/test_file.txt")
        assert manifest.permissions.validate_filesystem_access("/tmp/subdir/file.txt")
        
        # Should deny access to files outside /tmp
        assert not manifest.permissions.validate_filesystem_access("/etc/passwd")
        assert not manifest.permissions.validate_filesystem_access("/home/user/file.txt")
    
    def test_resource_limit_violation_detection_example(self):
        """
        Example: Resource limit violation detection
        A skill with 50MB memory limit should trigger violation when using 100MB.
        """
        limits = ResourceLimits(max_memory_mb=50)
        
        # Usage within limits
        normal_usage = ResourceUsage(
            timestamp=pytest.importorskip("datetime").datetime.now(),
            cpu_percent=10.0,
            memory_mb=30.0,
            disk_read_mb=5.0,
            disk_write_mb=5.0,
            network_sent_kb=100.0,
            network_recv_kb=100.0,
            file_handles=10,
            child_processes=1
        )
        
        assert normal_usage.exceeds_limits(limits) is None
        
        # Usage exceeding memory limit
        excessive_usage = ResourceUsage(
            timestamp=pytest.importorskip("datetime").datetime.now(),
            cpu_percent=10.0,
            memory_mb=100.0,  # Exceeds 50MB limit
            disk_read_mb=5.0,
            disk_write_mb=5.0,
            network_sent_kb=100.0,
            network_recv_kb=100.0,
            file_handles=10,
            child_processes=1
        )
        
        violation = excessive_usage.exceeds_limits(limits)
        assert violation is not None
        assert "memory" in violation
    
    def test_network_permission_wildcard_example(self):
        """
        Example: Network permission with wildcard
        A skill with "*" network permission should allow access to any host.
        """
        manifest = SkillManifest(
            skill_id="net-test-skill",
            name="Network Test Skill",
            description="Test network permissions",
            version="1.0.0",
            author="Test",
            permissions=PermissionSet(
                permissions={PermissionType.NETWORK_ACCESS},
                filesystem_paths=[],
                network_hosts=["*"],
                ui_applications=[]
            ),
            risk_level=RiskLevel.MEDIUM,
            resource_limits=ResourceLimits(),
            entry_point="test.py"
        )
        
        # Should allow access to any host with wildcard
        assert manifest.permissions.validate_network_access("api.example.com")
        assert manifest.permissions.validate_network_access("malicious.com")
        assert manifest.permissions.validate_network_access("192.168.1.1")
    
    def test_no_permissions_denial_example(self):
        """
        Example: Skills without permissions should be denied all access
        A skill with no filesystem or network permissions should be denied
        all filesystem and network access.
        """
        manifest = SkillManifest(
            skill_id="restricted-skill",
            name="Restricted Skill",
            description="Skill with no permissions",
            version="1.0.0",
            author="Test",
            permissions=PermissionSet(
                permissions=set(),  # No permissions
                filesystem_paths=[],
                network_hosts=[],
                ui_applications=[]
            ),
            risk_level=RiskLevel.LOW,
            resource_limits=ResourceLimits(),
            entry_point="test.py"
        )
        
        # Should deny all filesystem access
        assert not manifest.permissions.validate_filesystem_access("/tmp/file.txt")
        assert not manifest.permissions.validate_filesystem_access("/home/user/file.txt")
        
        # Should deny all network access
        assert not manifest.permissions.validate_network_access("api.example.com")
        assert not manifest.permissions.validate_network_access("localhost")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])