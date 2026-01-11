"""
Skill Registry

Manages skill registration, discovery, and lifecycle with comprehensive
security validation and manifest enforcement.
"""

import json
import threading
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from datetime import datetime, timedelta
import logging

from .manifest import SkillManifest, RiskLevel
from .exceptions import (
    SkillNotFoundError,
    SkillRegistrationError,
    ManifestValidationError,
    RateLimitExceededError
)


class RateLimiter:
    """Rate limiter for skill execution."""
    
    def __init__(self):
        self._call_history: Dict[str, List[datetime]] = {}
        self._lock = threading.Lock()
    
    def check_rate_limit(self, skill_id: str, max_per_minute: int, max_per_hour: int) -> bool:
        """Check if skill execution is within rate limits."""
        with self._lock:
            now = datetime.now()
            
            # Initialize history if needed
            if skill_id not in self._call_history:
                self._call_history[skill_id] = []
            
            history = self._call_history[skill_id]
            
            # Clean old entries
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)
            
            history[:] = [call_time for call_time in history if call_time > hour_ago]
            
            # Count recent calls
            calls_last_minute = sum(1 for call_time in history if call_time > minute_ago)
            calls_last_hour = len(history)
            
            # Check limits
            if calls_last_minute >= max_per_minute:
                return False
            
            if calls_last_hour >= max_per_hour:
                return False
            
            return True
    
    def record_call(self, skill_id: str) -> None:
        """Record a skill execution call."""
        with self._lock:
            if skill_id not in self._call_history:
                self._call_history[skill_id] = []
            
            self._call_history[skill_id].append(datetime.now())
    
    def get_call_stats(self, skill_id: str) -> Dict[str, int]:
        """Get call statistics for a skill."""
        with self._lock:
            if skill_id not in self._call_history:
                return {'last_minute': 0, 'last_hour': 0}
            
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)
            
            history = self._call_history[skill_id]
            
            calls_last_minute = sum(1 for call_time in history if call_time > minute_ago)
            calls_last_hour = sum(1 for call_time in history if call_time > hour_ago)
            
            return {
                'last_minute': calls_last_minute,
                'last_hour': calls_last_hour
            }


class SkillRegistry:
    """Registry for managing skills with security and lifecycle management."""
    
    def __init__(self, skills_directory: Optional[Path] = None):
        self.skills_directory = skills_directory or Path("skills")
        self.logger = logging.getLogger(__name__)
        
        # Registry state
        self._skills: Dict[str, SkillManifest] = {}
        self._skill_files: Dict[str, Path] = {}  # skill_id -> manifest file path
        self._concurrent_executions: Dict[str, int] = {}  # skill_id -> current count
        self._lock = threading.RLock()
        
        # Rate limiting
        self._rate_limiter = RateLimiter()
        
        # Registry metadata
        self._last_scan_time: Optional[datetime] = None
        self._auto_scan_enabled = True
        
        # Initialize registry
        self._ensure_skills_directory()
        self.scan_for_skills()
    
    def _ensure_skills_directory(self) -> None:
        """Ensure skills directory exists."""
        try:
            self.skills_directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Skills directory initialized: {self.skills_directory}")
        except Exception as e:
            self.logger.error(f"Failed to create skills directory: {e}")
            raise SkillRegistrationError("registry", f"Failed to create skills directory: {e}")
    
    def register_skill(self, manifest: SkillManifest, skill_file_path: Optional[Path] = None) -> None:
        """Register a skill with comprehensive validation."""
        with self._lock:
            self.logger.info(f"Registering skill: {manifest.skill_id}")
            
            # Validate manifest
            validation_errors = manifest.validate()
            if validation_errors:
                raise ManifestValidationError(manifest.skill_id, validation_errors)
            
            # Check for duplicate registration
            if manifest.skill_id in self._skills:
                existing_version = self._skills[manifest.skill_id].version
                if existing_version == manifest.version:
                    raise SkillRegistrationError(
                        manifest.skill_id,
                        f"Skill already registered with version {existing_version}"
                    )
                else:
                    self.logger.info(f"Updating skill {manifest.skill_id} from {existing_version} to {manifest.version}")
            
            # Validate skill file exists if provided
            if skill_file_path:
                if not skill_file_path.exists():
                    raise SkillRegistrationError(
                        manifest.skill_id,
                        f"Skill file not found: {skill_file_path}"
                    )
                
                # Validate entry point exists
                entry_point_path = skill_file_path.parent / manifest.entry_point
                if not entry_point_path.exists():
                    raise SkillRegistrationError(
                        manifest.skill_id,
                        f"Entry point not found: {entry_point_path}"
                    )
            
            # Security validation
            self._validate_skill_security(manifest)
            
            # Register skill
            self._skills[manifest.skill_id] = manifest
            if skill_file_path:
                self._skill_files[manifest.skill_id] = skill_file_path
            
            # Initialize execution tracking
            self._concurrent_executions[manifest.skill_id] = 0
            
            self.logger.info(f"Successfully registered skill: {manifest.skill_id} v{manifest.version}")
    
    def unregister_skill(self, skill_id: str) -> bool:
        """Unregister a skill."""
        with self._lock:
            if skill_id not in self._skills:
                return False
            
            # Check if skill is currently executing
            if self._concurrent_executions.get(skill_id, 0) > 0:
                raise SkillRegistrationError(
                    skill_id,
                    f"Cannot unregister skill while {self._concurrent_executions[skill_id]} executions are active"
                )
            
            # Remove skill
            del self._skills[skill_id]
            self._skill_files.pop(skill_id, None)
            self._concurrent_executions.pop(skill_id, None)
            
            self.logger.info(f"Unregistered skill: {skill_id}")
            return True
    
    def get_skill(self, skill_id: str) -> SkillManifest:
        """Get skill manifest by ID."""
        with self._lock:
            if skill_id not in self._skills:
                raise SkillNotFoundError(skill_id)
            
            return self._skills[skill_id]
    
    def list_skills(self, risk_level: Optional[RiskLevel] = None, 
                   has_permission: Optional[str] = None) -> List[SkillManifest]:
        """List skills with optional filtering."""
        with self._lock:
            skills = list(self._skills.values())
            
            # Filter by risk level
            if risk_level:
                skills = [s for s in skills if s.risk_level == risk_level]
            
            # Filter by permission
            if has_permission:
                skills = [s for s in skills if has_permission in [p.value for p in s.permissions.permissions]]
            
            return skills
    
    def get_skill_file_path(self, skill_id: str) -> Optional[Path]:
        """Get the file path for a skill."""
        with self._lock:
            return self._skill_files.get(skill_id)
    
    def check_execution_permission(self, skill_id: str, authority_level: str) -> bool:
        """Check if skill can be executed with given authority level."""
        with self._lock:
            if skill_id not in self._skills:
                return False
            
            manifest = self._skills[skill_id]
            required_level = manifest.requires_authority_level()
            
            # Define authority hierarchy
            authority_hierarchy = {
                "low_risk": 1,
                "medium_risk": 2,
                "high_risk": 3,
                "admin": 4
            }
            
            current_level = authority_hierarchy.get(authority_level, 0)
            required_level_value = authority_hierarchy.get(required_level, 999)
            
            return current_level >= required_level_value
    
    def check_rate_limit(self, skill_id: str) -> bool:
        """Check if skill execution is within rate limits."""
        with self._lock:
            if skill_id not in self._skills:
                return False
            
            manifest = self._skills[skill_id]
            return self._rate_limiter.check_rate_limit(
                skill_id,
                manifest.max_calls_per_minute,
                manifest.max_calls_per_hour
            )
    
    def record_execution_start(self, skill_id: str) -> None:
        """Record the start of skill execution."""
        with self._lock:
            if skill_id not in self._skills:
                raise SkillNotFoundError(skill_id)
            
            manifest = self._skills[skill_id]
            
            # Check concurrent execution limit
            current_count = self._concurrent_executions.get(skill_id, 0)
            if current_count >= manifest.max_concurrent_executions:
                raise RateLimitExceededError(
                    skill_id,
                    "concurrent_executions",
                    current_count,
                    manifest.max_concurrent_executions
                )
            
            # Check rate limits
            if not self.check_rate_limit(skill_id):
                stats = self._rate_limiter.get_call_stats(skill_id)
                raise RateLimitExceededError(
                    skill_id,
                    "rate_limit",
                    max(stats['last_minute'], stats['last_hour']),
                    max(manifest.max_calls_per_minute, manifest.max_calls_per_hour)
                )
            
            # Record execution
            self._concurrent_executions[skill_id] = current_count + 1
            self._rate_limiter.record_call(skill_id)
            
            self.logger.debug(f"Started execution for skill {skill_id} (concurrent: {current_count + 1})")
    
    def record_execution_end(self, skill_id: str) -> None:
        """Record the end of skill execution."""
        with self._lock:
            if skill_id in self._concurrent_executions:
                current_count = self._concurrent_executions[skill_id]
                self._concurrent_executions[skill_id] = max(0, current_count - 1)
                
                self.logger.debug(f"Ended execution for skill {skill_id} (concurrent: {current_count - 1})")
    
    def get_execution_stats(self, skill_id: str) -> Dict[str, Any]:
        """Get execution statistics for a skill."""
        with self._lock:
            if skill_id not in self._skills:
                raise SkillNotFoundError(skill_id)
            
            rate_stats = self._rate_limiter.get_call_stats(skill_id)
            concurrent_count = self._concurrent_executions.get(skill_id, 0)
            
            return {
                'skill_id': skill_id,
                'concurrent_executions': concurrent_count,
                'calls_last_minute': rate_stats['last_minute'],
                'calls_last_hour': rate_stats['last_hour'],
                'max_concurrent': self._skills[skill_id].max_concurrent_executions,
                'max_per_minute': self._skills[skill_id].max_calls_per_minute,
                'max_per_hour': self._skills[skill_id].max_calls_per_hour
            }
    
    def scan_for_skills(self) -> int:
        """Scan skills directory for new or updated skills."""
        if not self.skills_directory.exists():
            self.logger.warning(f"Skills directory does not exist: {self.skills_directory}")
            return 0
        
        skills_found = 0
        
        try:
            # Look for manifest files
            for manifest_file in self.skills_directory.rglob("manifest.json"):
                try:
                    manifest = SkillManifest.from_file(manifest_file)
                    
                    # Check if skill needs updating
                    if (manifest.skill_id not in self._skills or 
                        self._skills[manifest.skill_id].version != manifest.version):
                        
                        self.register_skill(manifest, manifest_file)
                        skills_found += 1
                
                except Exception as e:
                    self.logger.error(f"Failed to load skill from {manifest_file}: {e}")
            
            self._last_scan_time = datetime.now()
            self.logger.info(f"Skill scan completed: {skills_found} skills found/updated")
            
        except Exception as e:
            self.logger.error(f"Error during skill scan: {e}")
        
        return skills_found
    
    def _validate_skill_security(self, manifest: SkillManifest) -> None:
        """Validate skill security requirements."""
        # Check for dangerous permission combinations
        dangerous_combinations = [
            # Network + File write access
            ({"network_access", "filesystem_write"}, "Network and file write access"),
            # UI automation + Network access
            ({"ui_automation", "network_access"}, "UI automation and network access"),
            # Process control + Network access
            ({"process_control", "network_access"}, "Process control and network access")
        ]
        
        skill_permissions = {p.value for p in manifest.permissions.permissions}
        
        for dangerous_perms, description in dangerous_combinations:
            if dangerous_perms.issubset(skill_permissions):
                if manifest.risk_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    raise SkillRegistrationError(
                        manifest.skill_id,
                        f"Dangerous permission combination ({description}) requires HIGH or CRITICAL risk level"
                    )
        
        # Validate resource limits are reasonable
        if manifest.resource_limits.max_memory_mb > 1024:  # 1GB limit
            if manifest.risk_level != RiskLevel.CRITICAL:
                raise SkillRegistrationError(
                    manifest.skill_id,
                    "High memory usage (>1GB) requires CRITICAL risk level"
                )
        
        if manifest.resource_limits.max_execution_time_seconds > 300:  # 5 minute limit
            if manifest.risk_level not in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                raise SkillRegistrationError(
                    manifest.skill_id,
                    "Long execution time (>5min) requires HIGH or CRITICAL risk level"
                )
    
    def export_registry_info(self) -> Dict[str, Any]:
        """Export registry information for debugging/monitoring."""
        with self._lock:
            return {
                'total_skills': len(self._skills),
                'skills_by_risk_level': {
                    level.value: len([s for s in self._skills.values() if s.risk_level == level])
                    for level in RiskLevel
                },
                'skills_directory': str(self.skills_directory),
                'last_scan_time': self._last_scan_time.isoformat() if self._last_scan_time else None,
                'concurrent_executions': dict(self._concurrent_executions),
                'skills': [
                    {
                        'skill_id': manifest.skill_id,
                        'name': manifest.name,
                        'version': manifest.version,
                        'risk_level': manifest.risk_level.value,
                        'permissions': [p.value for p in manifest.permissions.permissions]
                    }
                    for manifest in self._skills.values()
                ]
            }
    
    def clear_registry(self) -> None:
        """Clear all registered skills (for testing)."""
        with self._lock:
            self._skills.clear()
            self._skill_files.clear()
            self._concurrent_executions.clear()
            self.logger.info("Registry cleared")