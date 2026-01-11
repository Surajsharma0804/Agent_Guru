"""
Skill Manifest System

Defines skill manifests that declare permissions, resource requirements,
side effects, and rollback strategies. All skills must have valid manifests
before execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import json
from pathlib import Path

from .exceptions import ManifestValidationError


class PermissionType(Enum):
    """Types of permissions a skill can request."""
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    NETWORK_ACCESS = "network_access"
    UI_AUTOMATION = "ui_automation"
    SYSTEM_INFO = "system_info"
    PROCESS_CONTROL = "process_control"
    REGISTRY_READ = "registry_read"
    REGISTRY_WRITE = "registry_write"
    AUDIO_CAPTURE = "audio_capture"
    SCREEN_CAPTURE = "screen_capture"


class RiskLevel(Enum):
    """Risk levels for skill operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceLimits:
    """Resource limits for skill execution."""
    max_cpu_percent: float = 25.0  # Maximum CPU usage percentage
    max_memory_mb: int = 256       # Maximum memory in MB
    max_disk_mb: int = 100         # Maximum disk usage in MB
    max_network_kb: int = 1024     # Maximum network usage in KB
    max_execution_time_seconds: int = 30  # Maximum execution time
    max_file_handles: int = 50     # Maximum open file handles
    max_processes: int = 1         # Maximum child processes


@dataclass
class PermissionSet:
    """Set of permissions requested by a skill."""
    permissions: Set[PermissionType] = field(default_factory=set)
    filesystem_paths: List[str] = field(default_factory=list)  # Allowed filesystem paths
    network_hosts: List[str] = field(default_factory=list)     # Allowed network hosts
    ui_applications: List[str] = field(default_factory=list)   # Allowed UI applications
    
    def has_permission(self, permission: PermissionType) -> bool:
        """Check if permission set includes specific permission."""
        return permission in self.permissions
    
    def validate_filesystem_access(self, path: str) -> bool:
        """Validate if filesystem path is allowed."""
        if PermissionType.FILESYSTEM_READ not in self.permissions and \
           PermissionType.FILESYSTEM_WRITE not in self.permissions:
            return False
        
        # If no specific paths defined, deny access (fail-safe)
        if not self.filesystem_paths:
            return False
        
        path_obj = Path(path).resolve()
        for allowed_path in self.filesystem_paths:
            allowed_path_obj = Path(allowed_path).resolve()
            try:
                path_obj.relative_to(allowed_path_obj)
                return True
            except ValueError:
                continue
        return False
    
    def validate_network_access(self, host: str) -> bool:
        """Validate if network host is allowed."""
        if PermissionType.NETWORK_ACCESS not in self.permissions:
            return False
        
        # If no specific hosts defined, deny access (fail-safe)
        if not self.network_hosts:
            return False
        
        return host in self.network_hosts or "*" in self.network_hosts


@dataclass
class RollbackStrategy:
    """Defines how to rollback skill actions."""
    strategy_type: str  # "none", "file_restore", "registry_restore", "process_kill", "custom"
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    cleanup_commands: List[str] = field(default_factory=list)
    
    def can_rollback(self) -> bool:
        """Check if rollback is possible."""
        return self.strategy_type != "none"


@dataclass
class SkillManifest:
    """Complete skill manifest defining all aspects of skill execution."""
    
    # Basic identification
    skill_id: str
    name: str
    description: str
    version: str
    author: str
    
    # Security and permissions
    permissions: PermissionSet
    risk_level: RiskLevel
    resource_limits: ResourceLimits
    
    # Execution details
    entry_point: str  # Python module or script path
    supported_platforms: List[str] = field(default_factory=lambda: ["windows"])
    dependencies: List[str] = field(default_factory=list)
    
    # Side effects and rollback
    side_effects: List[str] = field(default_factory=list)
    rollback_strategy: RollbackStrategy = field(default_factory=lambda: RollbackStrategy("none"))
    
    # Rate limiting
    max_calls_per_minute: int = 10
    max_calls_per_hour: int = 100
    max_concurrent_executions: int = 1
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, manifest_path: Path) -> 'SkillManifest':
        """Load manifest from JSON file."""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            raise ManifestValidationError(
                skill_id=str(manifest_path.stem),
                validation_errors=[f"Failed to load manifest: {str(e)}"]
            )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillManifest':
        """Create manifest from dictionary."""
        try:
            # Parse permissions
            permissions_data = data.get('permissions', {})
            permissions = PermissionSet(
                permissions={PermissionType(p) for p in permissions_data.get('permissions', [])},
                filesystem_paths=permissions_data.get('filesystem_paths', []),
                network_hosts=permissions_data.get('network_hosts', []),
                ui_applications=permissions_data.get('ui_applications', [])
            )
            
            # Parse resource limits
            limits_data = data.get('resource_limits', {})
            resource_limits = ResourceLimits(**limits_data)
            
            # Parse rollback strategy
            rollback_data = data.get('rollback_strategy', {})
            rollback_strategy = RollbackStrategy(
                strategy_type=rollback_data.get('strategy_type', 'none'),
                rollback_data=rollback_data.get('rollback_data', {}),
                cleanup_commands=rollback_data.get('cleanup_commands', [])
            )
            
            return cls(
                skill_id=data['skill_id'],
                name=data['name'],
                description=data['description'],
                version=data['version'],
                author=data['author'],
                permissions=permissions,
                risk_level=RiskLevel(data.get('risk_level', 'medium')),
                resource_limits=resource_limits,
                entry_point=data['entry_point'],
                supported_platforms=data.get('supported_platforms', ['windows']),
                dependencies=data.get('dependencies', []),
                side_effects=data.get('side_effects', []),
                rollback_strategy=rollback_strategy,
                max_calls_per_minute=data.get('max_calls_per_minute', 10),
                max_calls_per_hour=data.get('max_calls_per_hour', 100),
                max_concurrent_executions=data.get('max_concurrent_executions', 1),
                metadata=data.get('metadata', {})
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ManifestValidationError(
                skill_id=data.get('skill_id', 'unknown'),
                validation_errors=[f"Manifest parsing error: {str(e)}"]
            )
    
    def validate(self) -> List[str]:
        """Validate manifest for completeness and security."""
        errors = []
        
        # Basic validation
        if not self.skill_id or not self.skill_id.replace('-', '').replace('_', '').isalnum():
            errors.append("skill_id must be non-empty and alphanumeric (with hyphens/underscores)")
        
        if not self.name or len(self.name.strip()) == 0:
            errors.append("name must be non-empty")
        
        if not self.version or not self._is_valid_version(self.version):
            errors.append("version must be valid semantic version (e.g., 1.0.0)")
        
        if not self.entry_point or not self.entry_point.endswith('.py'):
            errors.append("entry_point must be a Python file (.py)")
        
        # Security validation
        if self.risk_level == RiskLevel.CRITICAL and not self.permissions.permissions:
            errors.append("Critical risk skills must declare explicit permissions")
        
        # Resource limits validation
        if self.resource_limits.max_cpu_percent <= 0 or self.resource_limits.max_cpu_percent > 100:
            errors.append("max_cpu_percent must be between 0 and 100")
        
        if self.resource_limits.max_memory_mb <= 0:
            errors.append("max_memory_mb must be positive")
        
        if self.resource_limits.max_execution_time_seconds <= 0:
            errors.append("max_execution_time_seconds must be positive")
        
        # Rate limiting validation
        if self.max_calls_per_minute <= 0:
            errors.append("max_calls_per_minute must be positive")
        
        if self.max_calls_per_hour <= 0:
            errors.append("max_calls_per_hour must be positive")
        
        if self.max_concurrent_executions <= 0:
            errors.append("max_concurrent_executions must be positive")
        
        # Platform validation
        if "windows" not in self.supported_platforms:
            errors.append("Skills must support Windows platform")
        
        return errors
    
    def _is_valid_version(self, version: str) -> bool:
        """Check if version string is valid semantic version."""
        parts = version.split('.')
        if len(parts) != 3:
            return False
        
        try:
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False
    
    def requires_authority_level(self) -> str:
        """Determine required authority level based on permissions and risk."""
        if self.risk_level == RiskLevel.CRITICAL:
            return "high_risk"
        elif self.risk_level == RiskLevel.HIGH:
            return "high_risk"
        elif self.risk_level == RiskLevel.MEDIUM:
            return "medium_risk"
        else:
            return "low_risk"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary for serialization."""
        return {
            'skill_id': self.skill_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'permissions': {
                'permissions': [p.value for p in self.permissions.permissions],
                'filesystem_paths': self.permissions.filesystem_paths,
                'network_hosts': self.permissions.network_hosts,
                'ui_applications': self.permissions.ui_applications
            },
            'risk_level': self.risk_level.value,
            'resource_limits': {
                'max_cpu_percent': self.resource_limits.max_cpu_percent,
                'max_memory_mb': self.resource_limits.max_memory_mb,
                'max_disk_mb': self.resource_limits.max_disk_mb,
                'max_network_kb': self.resource_limits.max_network_kb,
                'max_execution_time_seconds': self.resource_limits.max_execution_time_seconds,
                'max_file_handles': self.resource_limits.max_file_handles,
                'max_processes': self.resource_limits.max_processes
            },
            'entry_point': self.entry_point,
            'supported_platforms': self.supported_platforms,
            'dependencies': self.dependencies,
            'side_effects': self.side_effects,
            'rollback_strategy': {
                'strategy_type': self.rollback_strategy.strategy_type,
                'rollback_data': self.rollback_strategy.rollback_data,
                'cleanup_commands': self.rollback_strategy.cleanup_commands
            },
            'max_calls_per_minute': self.max_calls_per_minute,
            'max_calls_per_hour': self.max_calls_per_hour,
            'max_concurrent_executions': self.max_concurrent_executions,
            'metadata': self.metadata
        }