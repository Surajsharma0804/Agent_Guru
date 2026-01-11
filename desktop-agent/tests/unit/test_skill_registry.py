"""
Unit tests for skill registry system.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.skills.registry import SkillRegistry, RateLimiter
from src.skills.manifest import (
    SkillManifest, PermissionSet, PermissionType, RiskLevel,
    ResourceLimits, RollbackStrategy
)
from src.skills.exceptions import (
    SkillNotFoundError, SkillRegistrationError, RateLimitExceededError,
    ManifestValidationError
)


class TestRateLimiter:
    """Test RateLimiter functionality."""
    
    def test_check_rate_limit_within_limits(self):
        """Test rate limit checking within limits."""
        limiter = RateLimiter()
        
        # Should be within limits initially
        assert limiter.check_rate_limit("test-skill", 10, 100)
    
    def test_check_rate_limit_exceeded_minute(self):
        """Test rate limit checking when minute limit exceeded."""
        limiter = RateLimiter()
        skill_id = "test-skill"
        
        # Record calls up to the limit
        for _ in range(5):
            limiter.record_call(skill_id)
        
        # Should still be within limits
        assert limiter.check_rate_limit(skill_id, 10, 100)
        
        # Record more calls to exceed minute limit
        for _ in range(6):
            limiter.record_call(skill_id)
        
        # Should exceed minute limit
        assert not limiter.check_rate_limit(skill_id, 10, 100)
    
    def test_check_rate_limit_exceeded_hour(self):
        """Test rate limit checking when hour limit exceeded."""
        limiter = RateLimiter()
        skill_id = "test-skill"
        
        # Record calls up to hour limit
        for _ in range(50):
            limiter.record_call(skill_id)
        
        # Should exceed hour limit
        assert not limiter.check_rate_limit(skill_id, 100, 50)
    
    def test_record_call(self):
        """Test call recording."""
        limiter = RateLimiter()
        skill_id = "test-skill"
        
        # Record a call
        limiter.record_call(skill_id)
        
        # Check stats
        stats = limiter.get_call_stats(skill_id)
        assert stats['last_minute'] == 1
        assert stats['last_hour'] == 1
    
    def test_get_call_stats_no_history(self):
        """Test getting call stats with no history."""
        limiter = RateLimiter()
        
        stats = limiter.get_call_stats("unknown-skill")
        assert stats['last_minute'] == 0
        assert stats['last_hour'] == 0
    
    def test_call_history_cleanup(self):
        """Test that old call history is cleaned up."""
        limiter = RateLimiter()
        skill_id = "test-skill"
        
        # Mock datetime to simulate old calls
        with patch('src.skills.registry.datetime') as mock_datetime:
            # Set initial time
            old_time = datetime.now() - timedelta(hours=2)
            mock_datetime.now.return_value = old_time
            
            # Record old calls
            for _ in range(5):
                limiter.record_call(skill_id)
            
            # Move to current time
            current_time = datetime.now()
            mock_datetime.now.return_value = current_time
            
            # Check rate limit (should clean up old entries)
            assert limiter.check_rate_limit(skill_id, 10, 100)
            
            # Stats should show no recent calls
            stats = limiter.get_call_stats(skill_id)
            assert stats['last_minute'] == 0
            assert stats['last_hour'] == 0


class TestSkillRegistry:
    """Test SkillRegistry functionality."""
    
    def create_test_manifest(self, skill_id: str = "test-skill") -> SkillManifest:
        """Create a test skill manifest."""
        return SkillManifest(
            skill_id=skill_id,
            name=f"Test Skill {skill_id}",
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
    
    def test_registry_initialization(self):
        """Test registry initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            assert registry.skills_directory == Path(temp_dir)
            assert len(registry.list_skills()) == 0
    
    def test_register_skill_success(self):
        """Test successful skill registration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            
            # Verify skill is registered
            registered_skill = registry.get_skill("test-skill")
            assert registered_skill.skill_id == "test-skill"
            assert registered_skill.name == "Test Skill test-skill"
    
    def test_register_skill_duplicate(self):
        """Test registering duplicate skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            # Register skill first time
            registry.register_skill(manifest)
            
            # Try to register same skill again
            with pytest.raises(SkillRegistrationError):
                registry.register_skill(manifest)
    
    def test_register_skill_version_update(self):
        """Test registering skill with version update."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register initial version
            manifest_v1 = self.create_test_manifest()
            registry.register_skill(manifest_v1)
            
            # Register updated version
            manifest_v2 = self.create_test_manifest()
            manifest_v2.version = "2.0.0"
            registry.register_skill(manifest_v2)
            
            # Verify updated version is registered
            registered_skill = registry.get_skill("test-skill")
            assert registered_skill.version == "2.0.0"
    
    def test_register_skill_invalid_manifest(self):
        """Test registering skill with invalid manifest."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            manifest.skill_id = ""  # Invalid skill ID
            
            with pytest.raises(ManifestValidationError):
                registry.register_skill(manifest)
    
    def test_unregister_skill_success(self):
        """Test successful skill unregistration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            # Register and then unregister
            registry.register_skill(manifest)
            result = registry.unregister_skill("test-skill")
            
            assert result is True
            
            # Verify skill is no longer registered
            with pytest.raises(SkillNotFoundError):
                registry.get_skill("test-skill")
    
    def test_unregister_skill_not_found(self):
        """Test unregistering non-existent skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            result = registry.unregister_skill("non-existent")
            assert result is False
    
    def test_unregister_skill_active_execution(self):
        """Test unregistering skill with active execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            # Register skill and start execution
            registry.register_skill(manifest)
            registry.record_execution_start("test-skill")
            
            # Try to unregister while execution is active
            with pytest.raises(SkillRegistrationError):
                registry.unregister_skill("test-skill")
    
    def test_get_skill_success(self):
        """Test getting registered skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            retrieved_skill = registry.get_skill("test-skill")
            
            assert retrieved_skill.skill_id == "test-skill"
    
    def test_get_skill_not_found(self):
        """Test getting non-existent skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            with pytest.raises(SkillNotFoundError):
                registry.get_skill("non-existent")
    
    def test_list_skills_all(self):
        """Test listing all skills."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register multiple skills
            for i in range(3):
                manifest = self.create_test_manifest(f"skill-{i}")
                registry.register_skill(manifest)
            
            skills = registry.list_skills()
            assert len(skills) == 3
            skill_ids = [s.skill_id for s in skills]
            assert "skill-0" in skill_ids
            assert "skill-1" in skill_ids
            assert "skill-2" in skill_ids
    
    def test_list_skills_by_risk_level(self):
        """Test listing skills filtered by risk level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register skills with different risk levels
            low_risk = self.create_test_manifest("low-risk")
            low_risk.risk_level = RiskLevel.LOW
            
            high_risk = self.create_test_manifest("high-risk")
            high_risk.risk_level = RiskLevel.HIGH
            
            registry.register_skill(low_risk)
            registry.register_skill(high_risk)
            
            # Filter by risk level
            low_skills = registry.list_skills(risk_level=RiskLevel.LOW)
            high_skills = registry.list_skills(risk_level=RiskLevel.HIGH)
            
            assert len(low_skills) == 1
            assert len(high_skills) == 1
            assert low_skills[0].skill_id == "low-risk"
            assert high_skills[0].skill_id == "high-risk"
    
    def test_list_skills_by_permission(self):
        """Test listing skills filtered by permission."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register skills with different permissions
            fs_skill = self.create_test_manifest("fs-skill")
            fs_skill.permissions.permissions = {PermissionType.FILESYSTEM_READ}
            
            net_skill = self.create_test_manifest("net-skill")
            net_skill.permissions.permissions = {PermissionType.NETWORK_ACCESS}
            
            registry.register_skill(fs_skill)
            registry.register_skill(net_skill)
            
            # Filter by permission
            fs_skills = registry.list_skills(has_permission="filesystem_read")
            net_skills = registry.list_skills(has_permission="network_access")
            
            assert len(fs_skills) == 1
            assert len(net_skills) == 1
            assert fs_skills[0].skill_id == "fs-skill"
            assert net_skills[0].skill_id == "net-skill"
    
    def test_check_execution_permission_allowed(self):
        """Test execution permission check for allowed authority level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            manifest.risk_level = RiskLevel.LOW  # Requires low_risk authority
            
            registry.register_skill(manifest)
            
            # Should allow medium_risk authority for low_risk skill
            assert registry.check_execution_permission("test-skill", "medium_risk")
            assert registry.check_execution_permission("test-skill", "high_risk")
    
    def test_check_execution_permission_denied(self):
        """Test execution permission check for insufficient authority level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            manifest.risk_level = RiskLevel.HIGH  # Requires high_risk authority
            
            registry.register_skill(manifest)
            
            # Should deny low_risk authority for high_risk skill
            assert not registry.check_execution_permission("test-skill", "low_risk")
            assert not registry.check_execution_permission("test-skill", "medium_risk")
    
    def test_check_execution_permission_not_found(self):
        """Test execution permission check for non-existent skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            assert not registry.check_execution_permission("non-existent", "high_risk")
    
    def test_check_rate_limit_success(self):
        """Test rate limit check within limits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            
            assert registry.check_rate_limit("test-skill")
    
    def test_check_rate_limit_not_found(self):
        """Test rate limit check for non-existent skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            assert not registry.check_rate_limit("non-existent")
    
    def test_record_execution_start_success(self):
        """Test recording execution start."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            registry.record_execution_start("test-skill")
            
            # Check execution stats
            stats = registry.get_execution_stats("test-skill")
            assert stats['concurrent_executions'] == 1
            assert stats['calls_last_minute'] == 1
    
    def test_record_execution_start_concurrent_limit(self):
        """Test recording execution start with concurrent limit exceeded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            manifest.max_concurrent_executions = 1
            
            registry.register_skill(manifest)
            
            # Start first execution
            registry.record_execution_start("test-skill")
            
            # Try to start second execution (should fail)
            with pytest.raises(RateLimitExceededError):
                registry.record_execution_start("test-skill")
    
    def test_record_execution_start_rate_limit(self):
        """Test recording execution start with rate limit exceeded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            manifest.max_calls_per_minute = 1
            
            registry.register_skill(manifest)
            
            # Start first execution
            registry.record_execution_start("test-skill")
            registry.record_execution_end("test-skill")
            
            # Try to start second execution immediately (should fail)
            with pytest.raises(RateLimitExceededError):
                registry.record_execution_start("test-skill")
    
    def test_record_execution_end(self):
        """Test recording execution end."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            registry.record_execution_start("test-skill")
            registry.record_execution_end("test-skill")
            
            # Check execution stats
            stats = registry.get_execution_stats("test-skill")
            assert stats['concurrent_executions'] == 0
    
    def test_get_execution_stats_success(self):
        """Test getting execution statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            registry.record_execution_start("test-skill")
            
            stats = registry.get_execution_stats("test-skill")
            
            assert stats['skill_id'] == "test-skill"
            assert stats['concurrent_executions'] == 1
            assert stats['max_concurrent'] == manifest.max_concurrent_executions
            assert stats['max_per_minute'] == manifest.max_calls_per_minute
            assert stats['max_per_hour'] == manifest.max_calls_per_hour
    
    def test_get_execution_stats_not_found(self):
        """Test getting execution statistics for non-existent skill."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            with pytest.raises(SkillNotFoundError):
                registry.get_execution_stats("non-existent")
    
    def test_export_registry_info(self):
        """Test exporting registry information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            
            # Register skills with different risk levels
            low_risk = self.create_test_manifest("low-risk")
            low_risk.risk_level = RiskLevel.LOW
            
            high_risk = self.create_test_manifest("high-risk")
            high_risk.risk_level = RiskLevel.HIGH
            
            registry.register_skill(low_risk)
            registry.register_skill(high_risk)
            
            info = registry.export_registry_info()
            
            assert info['total_skills'] == 2
            assert info['skills_by_risk_level']['low'] == 1
            assert info['skills_by_risk_level']['high'] == 1
            assert len(info['skills']) == 2
    
    def test_clear_registry(self):
        """Test clearing registry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = SkillRegistry(Path(temp_dir))
            manifest = self.create_test_manifest()
            
            registry.register_skill(manifest)
            assert len(registry.list_skills()) == 1
            
            registry.clear_registry()
            assert len(registry.list_skills()) == 0