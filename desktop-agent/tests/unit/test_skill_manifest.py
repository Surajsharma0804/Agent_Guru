"""
Unit tests for skill manifest system.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.skills.manifest import (
    SkillManifest, PermissionSet, PermissionType, RiskLevel,
    ResourceLimits, RollbackStrategy
)
from src.skills.exceptions import ManifestValidationError


class TestPermissionSet:
    """Test PermissionSet functionality."""
    
    def test_has_permission(self):
        """Test permission checking."""
        permissions = PermissionSet(
            permissions={PermissionType.FILESYSTEM_READ, PermissionType.NETWORK_ACCESS}
        )
        
        assert permissions.has_permission(PermissionType.FILESYSTEM_READ)
        assert permissions.has_permission(PermissionType.NETWORK_ACCESS)
        assert not permissions.has_permission(PermissionType.FILESYSTEM_WRITE)
    
    def test_validate_filesystem_access_allowed(self):
        """Test filesystem access validation for allowed paths."""
        permissions = PermissionSet(
            permissions={PermissionType.FILESYSTEM_READ},
            filesystem_paths=["/home/user/documents", "/tmp"]
        )
        
        assert permissions.validate_filesystem_access("/home/user/documents/file.txt")
        assert permissions.validate_filesystem_access("/tmp/temp_file")
    
    def test_validate_filesystem_access_denied(self):
        """Test filesystem access validation for denied paths."""
        permissions = PermissionSet(
            permissions={PermissionType.FILESYSTEM_READ},
            filesystem_paths=["/home/user/documents"]
        )
        
        assert not permissions.validate_filesystem_access("/etc/passwd")
        assert not permissions.validate_filesystem_access("/home/other/file.txt")
    
    def test_validate_filesystem_access_no_permission(self):
        """Test filesystem access validation without permission."""
        permissions = PermissionSet(permissions=set())
        
        assert not permissions.validate_filesystem_access("/home/user/file.txt")
    
    def test_validate_filesystem_access_no_paths(self):
        """Test filesystem access validation with no allowed paths."""
        permissions = PermissionSet(
            permissions={PermissionType.FILESYSTEM_READ},
            filesystem_paths=[]
        )
        
        assert not permissions.validate_filesystem_access("/home/user/file.txt")
    
    def test_validate_network_access_allowed(self):
        """Test network access validation for allowed hosts."""
        permissions = PermissionSet(
            permissions={PermissionType.NETWORK_ACCESS},
            network_hosts=["api.example.com", "*.github.com"]
        )
        
        assert permissions.validate_network_access("api.example.com")
        assert permissions.validate_network_access("*.github.com")
    
    def test_validate_network_access_wildcard(self):
        """Test network access validation with wildcard."""
        permissions = PermissionSet(
            permissions={PermissionType.NETWORK_ACCESS},
            network_hosts=["*"]
        )
        
        assert permissions.validate_network_access("any.host.com")
    
    def test_validate_network_access_denied(self):
        """Test network access validation for denied hosts."""
        permissions = PermissionSet(
            permissions={PermissionType.NETWORK_ACCESS},
            network_hosts=["api.example.com"]
        )
        
        assert not permissions.validate_network_access("malicious.com")
    
    def test_validate_network_access_no_permission(self):
        """Test network access validation without permission."""
        permissions = PermissionSet(permissions=set())
        
        assert not permissions.validate_network_access("api.example.com")


class TestResourceLimits:
    """Test ResourceLimits functionality."""
    
    def test_default_values(self):
        """Test default resource limit values."""
        limits = ResourceLimits()
        
        assert limits.max_cpu_percent == 25.0
        assert limits.max_memory_mb == 256
        assert limits.max_disk_mb == 100
        assert limits.max_network_kb == 1024
        assert limits.max_execution_time_seconds == 30
        assert limits.max_file_handles == 50
        assert limits.max_processes == 1
    
    def test_custom_values(self):
        """Test custom resource limit values."""
        limits = ResourceLimits(
            max_cpu_percent=50.0,
            max_memory_mb=512,
            max_execution_time_seconds=60
        )
        
        assert limits.max_cpu_percent == 50.0
        assert limits.max_memory_mb == 512
        assert limits.max_execution_time_seconds == 60


class TestRollbackStrategy:
    """Test RollbackStrategy functionality."""
    
    def test_can_rollback_none(self):
        """Test rollback capability for 'none' strategy."""
        strategy = RollbackStrategy("none")
        assert not strategy.can_rollback()
    
    def test_can_rollback_file_restore(self):
        """Test rollback capability for 'file_restore' strategy."""
        strategy = RollbackStrategy("file_restore")
        assert strategy.can_rollback()
    
    def test_rollback_data(self):
        """Test rollback data storage."""
        rollback_data = {"backup_location": "/tmp/backups"}
        cleanup_commands = ["rm -rf /tmp/temp"]
        
        strategy = RollbackStrategy(
            "custom",
            rollback_data=rollback_data,
            cleanup_commands=cleanup_commands
        )
        
        assert strategy.rollback_data == rollback_data
        assert strategy.cleanup_commands == cleanup_commands


class TestSkillManifest:
    """Test SkillManifest functionality."""
    
    def create_valid_manifest(self) -> SkillManifest:
        """Create a valid skill manifest for testing."""
        return SkillManifest(
            skill_id="test-skill",
            name="Test Skill",
            description="A test skill",
            version="1.0.0",
            author="Test Author",
            permissions=PermissionSet(
                permissions={PermissionType.FILESYSTEM_READ},
                filesystem_paths=["/tmp"]
            ),
            risk_level=RiskLevel.LOW,
            resource_limits=ResourceLimits(),
            entry_point="test_skill.py"
        )
    
    def test_valid_manifest_creation(self):
        """Test creation of valid manifest."""
        manifest = self.create_valid_manifest()
        
        assert manifest.skill_id == "test-skill"
        assert manifest.name == "Test Skill"
        assert manifest.version == "1.0.0"
        assert manifest.risk_level == RiskLevel.LOW
        assert "windows" in manifest.supported_platforms
    
    def test_manifest_validation_success(self):
        """Test successful manifest validation."""
        manifest = self.create_valid_manifest()
        errors = manifest.validate()
        
        assert len(errors) == 0
    
    def test_manifest_validation_invalid_skill_id(self):
        """Test manifest validation with invalid skill ID."""
        manifest = self.create_valid_manifest()
        manifest.skill_id = "invalid skill id!"
        
        errors = manifest.validate()
        assert len(errors) > 0
        assert any("skill_id" in error for error in errors)
    
    def test_manifest_validation_empty_name(self):
        """Test manifest validation with empty name."""
        manifest = self.create_valid_manifest()
        manifest.name = ""
        
        errors = manifest.validate()
        assert len(errors) > 0
        assert any("name" in error for error in errors)
    
    def test_manifest_validation_invalid_version(self):
        """Test manifest validation with invalid version."""
        manifest = self.create_valid_manifest()
        manifest.version = "invalid"
        
        errors = manifest.validate()
        assert len(errors) > 0
        assert any("version" in error for error in errors)
    
    def test_manifest_validation_invalid_entry_point(self):
        """Test manifest validation with invalid entry point."""
        manifest = self.create_valid_manifest()
        manifest.entry_point = "test_skill.txt"
        
        errors = manifest.validate()
        assert len(errors) > 0
        assert any("entry_point" in error for error in errors)
    
    def test_manifest_validation_invalid_resource_limits(self):
        """Test manifest validation with invalid resource limits."""
        manifest = self.create_valid_manifest()
        manifest.resource_limits.max_cpu_percent = -10
        manifest.resource_limits.max_memory_mb = 0
        
        errors = manifest.validate()
        assert len(errors) >= 2
        assert any("max_cpu_percent" in error for error in errors)
        assert any("max_memory_mb" in error for error in errors)
    
    def test_manifest_validation_invalid_rate_limits(self):
        """Test manifest validation with invalid rate limits."""
        manifest = self.create_valid_manifest()
        manifest.max_calls_per_minute = 0
        manifest.max_calls_per_hour = -1
        
        errors = manifest.validate()
        assert len(errors) >= 2
        assert any("max_calls_per_minute" in error for error in errors)
        assert any("max_calls_per_hour" in error for error in errors)
    
    def test_requires_authority_level_low(self):
        """Test authority level requirement for low risk."""
        manifest = self.create_valid_manifest()
        manifest.risk_level = RiskLevel.LOW
        
        assert manifest.requires_authority_level() == "low_risk"
    
    def test_requires_authority_level_medium(self):
        """Test authority level requirement for medium risk."""
        manifest = self.create_valid_manifest()
        manifest.risk_level = RiskLevel.MEDIUM
        
        assert manifest.requires_authority_level() == "medium_risk"
    
    def test_requires_authority_level_high(self):
        """Test authority level requirement for high risk."""
        manifest = self.create_valid_manifest()
        manifest.risk_level = RiskLevel.HIGH
        
        assert manifest.requires_authority_level() == "high_risk"
    
    def test_requires_authority_level_critical(self):
        """Test authority level requirement for critical risk."""
        manifest = self.create_valid_manifest()
        manifest.risk_level = RiskLevel.CRITICAL
        
        assert manifest.requires_authority_level() == "high_risk"
    
    def test_to_dict_conversion(self):
        """Test manifest to dictionary conversion."""
        manifest = self.create_valid_manifest()
        data = manifest.to_dict()
        
        assert data["skill_id"] == "test-skill"
        assert data["name"] == "Test Skill"
        assert data["version"] == "1.0.0"
        assert data["risk_level"] == "low"
        assert "permissions" in data
        assert "resource_limits" in data
    
    def test_from_dict_creation(self):
        """Test manifest creation from dictionary."""
        data = {
            "skill_id": "test-skill",
            "name": "Test Skill",
            "description": "A test skill",
            "version": "1.0.0",
            "author": "Test Author",
            "permissions": {
                "permissions": ["filesystem_read"],
                "filesystem_paths": ["/tmp"],
                "network_hosts": [],
                "ui_applications": []
            },
            "risk_level": "low",
            "resource_limits": {
                "max_cpu_percent": 25.0,
                "max_memory_mb": 256,
                "max_disk_mb": 100,
                "max_network_kb": 1024,
                "max_execution_time_seconds": 30,
                "max_file_handles": 50,
                "max_processes": 1
            },
            "entry_point": "test_skill.py"
        }
        
        manifest = SkillManifest.from_dict(data)
        
        assert manifest.skill_id == "test-skill"
        assert manifest.name == "Test Skill"
        assert manifest.risk_level == RiskLevel.LOW
        assert PermissionType.FILESYSTEM_READ in manifest.permissions.permissions
    
    def test_from_dict_invalid_data(self):
        """Test manifest creation from invalid dictionary."""
        data = {
            "skill_id": "test-skill",
            # Missing required fields
        }
        
        with pytest.raises(ManifestValidationError):
            SkillManifest.from_dict(data)
    
    def test_from_file_success(self):
        """Test manifest loading from file."""
        manifest_data = {
            "skill_id": "test-skill",
            "name": "Test Skill",
            "description": "A test skill",
            "version": "1.0.0",
            "author": "Test Author",
            "permissions": {
                "permissions": ["filesystem_read"],
                "filesystem_paths": ["/tmp"],
                "network_hosts": [],
                "ui_applications": []
            },
            "risk_level": "low",
            "resource_limits": {},
            "entry_point": "test_skill.py"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_data, f)
            temp_path = Path(f.name)
        
        try:
            manifest = SkillManifest.from_file(temp_path)
            assert manifest.skill_id == "test-skill"
            assert manifest.name == "Test Skill"
        finally:
            temp_path.unlink()
    
    def test_from_file_not_found(self):
        """Test manifest loading from non-existent file."""
        with pytest.raises(ManifestValidationError):
            SkillManifest.from_file(Path("/non/existent/file.json"))
    
    def test_from_file_invalid_json(self):
        """Test manifest loading from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ManifestValidationError):
                SkillManifest.from_file(temp_path)
        finally:
            temp_path.unlink()
    
    def test_is_valid_version(self):
        """Test version validation."""
        manifest = self.create_valid_manifest()
        
        assert manifest._is_valid_version("1.0.0")
        assert manifest._is_valid_version("10.20.30")
        assert not manifest._is_valid_version("1.0")
        assert not manifest._is_valid_version("1.0.0.0")
        assert not manifest._is_valid_version("invalid")
        assert not manifest._is_valid_version("1.0.a")