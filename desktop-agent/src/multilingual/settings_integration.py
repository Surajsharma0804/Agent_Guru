"""
GURU Settings Management Integration

Production-grade integration layer that connects multilingual configuration
with existing GURU settings management, providing secure storage, validation,
migration support, and unified configuration access.

Requirements: 15.4
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from .configuration import ConfigurationManager, MultilingualConfig
from .user_preferences import UserPreferences, UserPreferencesManager
from .voice_training import VoiceTrainingManager


class SettingsScope(Enum):
    """Scope of settings application."""

    SYSTEM = "system"  # System-wide settings
    USER = "user"  # User-specific settings
    SESSION = "session"  # Session-specific settings
    TEMPORARY = "temporary"  # Temporary overrides


class MigrationStatus(Enum):
    """Status of configuration migration."""

    NOT_NEEDED = "not_needed"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class SettingsSnapshot:
    """Snapshot of settings for backup and rollback."""

    snapshot_id: str
    timestamp: datetime
    scope: SettingsScope

    # Configuration data
    multilingual_config: Dict[str, Any]
    user_preferences: Optional[Dict[str, Any]] = None
    voice_profiles: Optional[Dict[str, Any]] = None

    # Metadata
    reason: str = "manual_backup"
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "scope": self.scope.value,
            "multilingual_config": self.multilingual_config,
            "user_preferences": self.user_preferences,
            "voice_profiles": self.voice_profiles,
            "reason": self.reason,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettingsSnapshot":
        """Create from dictionary."""
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if "scope" in data:
            data["scope"] = SettingsScope(data["scope"])
        return cls(**data)


@dataclass
class MigrationPlan:
    """Plan for migrating configuration."""

    migration_id: str
    from_version: str
    to_version: str

    # Migration steps
    steps: List[str] = field(default_factory=list)

    # Status
    status: MigrationStatus = MigrationStatus.PENDING

    # Backup
    backup_snapshot_id: Optional[str] = None

    # Results
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "migration_id": self.migration_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "steps": self.steps,
            "status": self.status.value,
            "backup_snapshot_id": self.backup_snapshot_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class GuruSettingsIntegration:
    """
    Integration layer for GURU settings management.

    Provides unified access to multilingual configuration, user preferences,
    and voice profiles while maintaining compatibility with existing GURU
    settings infrastructure. Includes secure storage, validation, migration
    support, and configuration versioning.
    """

    def __init__(self, config_dir: Optional[Path] = None, guru_config_path: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)

        # Configuration directories
        self.config_dir = config_dir or Path("config")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.guru_config_path = guru_config_path or Path("config/guru_settings.json")

        # Component managers
        self.config_manager = ConfigurationManager(config_path=self.config_dir / "multilingual.json")
        self.preferences_manager = UserPreferencesManager(preferences_dir=self.config_dir / "user_preferences")
        self.training_manager = VoiceTrainingManager(profiles_dir=self.config_dir / "voice_profiles")

        # Snapshot management
        self.snapshots_dir = self.config_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Migration tracking
        self.migrations_dir = self.config_dir / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Thread safety
        self._lock = Lock()

        # Current version
        self.current_version = "1.0.0"

    def initialize(self) -> bool:
        """Initialize settings integration and load configurations."""
        try:
            self.logger.info("Initializing GURU settings integration")

            # Load multilingual configuration
            self.config_manager.load_configuration()

            # Validate configuration
            issues = self.config_manager.validate_configuration()
            if issues:
                self.logger.warning(f"Configuration validation issues: {issues}")

            # Check for pending migrations
            self._check_migrations()

            # Integrate with existing GURU settings
            self._integrate_with_guru_settings()

            self.logger.info("Settings integration initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize settings integration: {e}")
            return False

    def get_unified_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get unified settings combining multilingual config and user preferences.

        Returns a complete settings dictionary that includes:
        - System-wide multilingual configuration
        - User-specific preferences
        - Voice profile status
        - Integration settings
        """
        try:
            with self._lock:
                # Get multilingual configuration
                config = self.config_manager.get_configuration()

                # Get user preferences
                preferences = self.preferences_manager.get_preferences(user_id)

                # Get voice profile status
                voice_profile = self.training_manager.load_profile(user_id)

                # Combine into unified settings
                unified = {
                    "version": self.current_version,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    # System configuration
                    "system": {
                        "enabled_languages": config.enabled_languages,
                        "primary_language": config.primary_language,
                        "fallback_language": config.fallback_language,
                        "detection_threshold": config.detection_threshold,
                        "mixed_language_support": config.mixed_language_support,
                        "hardware_acceleration": config.enable_hardware_acceleration,
                        "performance_monitoring": config.performance_monitoring,
                    },
                    # User preferences
                    "preferences": {
                        "language_priorities": preferences.get_ordered_languages(),
                        "global_sensitivity": preferences.global_sensitivity.name,
                        "mixed_language_strategy": preferences.mixed_language_strategy.value,
                        "fallback_behavior": preferences.fallback_behavior.value,
                        "remember_last_language": preferences.remember_last_language,
                        "session_persistence_minutes": preferences.session_language_persistence_minutes,
                        "dictation_preserve_exact": preferences.dictation_preserve_exact,
                        "command_confirmation": preferences.command_confirmation_required,
                        "notifications": {
                            "language_switch": preferences.notify_on_language_switch,
                            "low_confidence": preferences.notify_on_low_confidence,
                            "fallback": preferences.notify_on_fallback,
                            "audio_feedback": preferences.audio_feedback_enabled,
                        },
                    },
                    # Voice profile status
                    "voice_profile": {
                        "overall_status": voice_profile.get_overall_calibration_status().value,
                        "calibrated_languages": voice_profile.get_calibrated_languages(),
                        "languages_needing_calibration": voice_profile.get_languages_needing_calibration(),
                        "global_threshold": voice_profile.global_verification_threshold,
                        "adaptive_threshold": voice_profile.adaptive_threshold_enabled,
                    },
                    # Integration status
                    "integration": {
                        "guru_integration_enabled": config.integrate_with_existing_voice_pipeline,
                        "security_boundaries_maintained": config.maintain_existing_security_boundaries,
                        "audit_logging_preserved": config.preserve_existing_audit_logging,
                    },
                }

                return unified

        except Exception as e:
            self.logger.error(f"Failed to get unified settings: {e}")
            return {}

    def update_settings(
        self, user_id: str, updates: Dict[str, Any], scope: SettingsScope = SettingsScope.USER
    ) -> Tuple[bool, Optional[str]]:
        """
        Update settings with validation and backup.

        Args:
            user_id: User identifier
            updates: Dictionary of settings to update
            scope: Scope of settings update

        Returns:
            Tuple of (success, error_message)
        """
        try:
            with self._lock:
                # Create backup snapshot before changes
                _snapshot_id = self._create_snapshot(user_id=user_id, scope=scope, reason="pre_update_backup")

                # Apply updates based on scope
                if scope == SettingsScope.SYSTEM:
                    success = self._update_system_settings(updates)
                elif scope == SettingsScope.USER:
                    success = self._update_user_settings(user_id, updates)
                else:
                    return False, f"Unsupported settings scope: {scope}"

                if not success:
                    # Rollback on failure
                    self._restore_snapshot(snapshot_id)
                    return False, "Failed to apply settings updates"

                self.logger.info(f"Updated settings for user {user_id}, scope {scope.value}")
                return True, None

        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")
            return False, str(e)

    def validate_settings(self, user_id: str) -> List[str]:
        """
        Validate all settings for a user.

        Returns list of validation issues (empty if valid).
        """
        issues = []

        try:
            # Validate multilingual configuration
            config_issues = self.config_manager.validate_configuration()
            issues.extend(config_issues)

            # Validate user preferences
            preferences = self.preferences_manager.get_preferences(user_id)
            pref_issues = self.preferences_manager.validate_preferences(preferences)
            issues.extend(pref_issues)

            # Validate voice profiles
            self.training_manager.load_profile(user_id)

            # Check for languages in preferences but not in config
            config = self.config_manager.get_configuration()
            for lang in preferences.get_ordered_languages():
                if not config.is_language_enabled(lang):
                    issues.append(f"Language '{lang}' in user preferences but not enabled in system config")

        except Exception as e:
            issues.append(f"Validation error: {str(e)}")

        return issues

    def migrate_configuration(
        self, from_version: str, to_version: str, user_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Migrate configuration from one version to another.

        Args:
            from_version: Source version
            to_version: Target version
            user_id: Optional user ID for user-specific migration

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Create migration plan
            migration_id = self._generate_migration_id(from_version, to_version)
            plan = MigrationPlan(
                migration_id=migration_id,
                from_version=from_version,
                to_version=to_version,
                steps=self._get_migration_steps(from_version, to_version),
            )

            # Create backup snapshot
            _snapshot_id = self._create_snapshot(
                user_id=user_id,
                scope=SettingsScope.SYSTEM if not user_id else SettingsScope.USER,
                reason=f"pre_migration_{from_version}_to_{to_version}",
            )
            plan.backup_snapshot_id = snapshot_id

            # Execute migration
            plan.status = MigrationStatus.IN_PROGRESS
            plan.started_at = datetime.utcnow()
            self._save_migration_plan(plan)

            # Perform migration steps
            for step in plan.steps:
                self.logger.info(f"Executing migration step: {step}")
                success = self._execute_migration_step(step, user_id)

                if not success:
                    plan.status = MigrationStatus.FAILED
                    plan.error_message = f"Failed at step: {step}"
                    self._save_migration_plan(plan)

                    # Rollback
                    self._restore_snapshot(snapshot_id)
                    plan.status = MigrationStatus.ROLLED_BACK
                    self._save_migration_plan(plan)

                    return False, plan.error_message

            # Migration successful
            plan.status = MigrationStatus.COMPLETED
            plan.completed_at = datetime.utcnow()
            self._save_migration_plan(plan)

            self.logger.info(f"Migration completed: {from_version} -> {to_version}")
            return True, None

        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False, str(e)

    def export_settings(self, user_id: str, export_path: Path) -> bool:
        """Export all settings for a user to a file."""
        try:
            unified_settings = self.get_unified_settings(user_id)

            export_path.parent.mkdir(parents=True, exist_ok=True)

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(unified_settings, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Exported settings for user {user_id} to {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export settings: {e}")
            return False

    def import_settings(self, user_id: str, import_path: Path) -> Tuple[bool, Optional[str]]:
        """Import settings for a user from a file."""
        try:
            if not import_path.exists():
                return False, f"Import file not found: {import_path}"

            # Create backup before import
            _snapshot_id = self._create_snapshot(user_id=user_id, scope=SettingsScope.USER, reason="pre_import_backup")

            # Load settings from file
            with open(import_path, "r", encoding="utf-8") as f:
                imported_settings = json.load(f)

            # Validate imported settings
            if "version" not in imported_settings:
                return False, "Invalid settings file: missing version"

            # Check if migration needed
            imported_version = imported_settings["version"]
            if imported_version != self.current_version:
                success, error = self.migrate_configuration(
                    from_version=imported_version, to_version=self.current_version, user_id=user_id
                )
                if not success:
                    return False, f"Migration failed: {error}"

            # Apply imported settings
            if "preferences" in imported_settings:
                self._update_user_settings(user_id, imported_settings["preferences"])

            self.logger.info(f"Imported settings for user {user_id} from {import_path}")
            return True, None

        except Exception as e:
            self.logger.error(f"Failed to import settings: {e}")
            return False, str(e)

    def _integrate_with_guru_settings(self) -> bool:
        """Integrate multilingual settings with existing GURU settings."""
        try:
            # Check if GURU settings file exists
            if not self.guru_config_path.exists():
                self.logger.info("GURU settings file not found, skipping integration")
                return True

            # Load GURU settings
            with open(self.guru_config_path, "r", encoding="utf-8") as f:
                guru_settings = json.load(f)

            # Add multilingual section if not present
            if "multilingual" not in guru_settings:
                guru_settings["multilingual"] = {
                    "enabled": True,
                    "config_path": str(self.config_dir / "multilingual.json"),
                    "version": self.current_version,
                }

                # Save updated GURU settings
                with open(self.guru_config_path, "w", encoding="utf-8") as f:
                    json.dump(guru_settings, f, indent=2, ensure_ascii=False)

                self.logger.info("Integrated multilingual settings with GURU configuration")

            return True

        except Exception as e:
            self.logger.error(f"Failed to integrate with GURU settings: {e}")
            return False

    def _create_snapshot(self, user_id: Optional[str], scope: SettingsScope, reason: str) -> str:
        """Create a snapshot of current settings."""
        try:
            _snapshot_id = self._generate_snapshot_id()

            # Collect configuration data
            config = self.config_manager.get_configuration()
            multilingual_config = config.to_dict()

            user_preferences = None
            voice_profiles = None

            if user_id:
                preferences = self.preferences_manager.get_preferences(user_id)
                user_preferences = preferences.to_dict()

                voice_profile = self.training_manager.load_profile(user_id)
                voice_profiles = voice_profile.to_dict()

            # Create snapshot
            snapshot = SettingsSnapshot(
                _snapshot_id=snapshot_id,
                timestamp=datetime.utcnow(),
                scope=scope,
                multilingual_config=multilingual_config,
                user_preferences=user_preferences,
                voice_profiles=voice_profiles,
                reason=reason,
                user_id=user_id,
            )

            # Save snapshot
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)

            self.logger.info(f"Created settings snapshot: {snapshot_id}")
            return snapshot_id

        except Exception as e:
            self.logger.error(f"Failed to create snapshot: {e}")
            return ""

    def _restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore settings from a snapshot."""
        try:
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"

            if not snapshot_file.exists():
                self.logger.error(f"Snapshot not found: {snapshot_id}")
                return False

            # Load snapshot
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)

            snapshot = SettingsSnapshot.from_dict(snapshot_data)

            # Restore multilingual configuration
            config = MultilingualConfig.from_dict(snapshot.multilingual_config)
            self.config_manager._config = config
            self.config_manager.save_configuration()

            # Restore user preferences if present
            if snapshot.user_preferences and snapshot.user_id:
                preferences = UserPreferences.from_dict(snapshot.user_preferences)
                self.preferences_manager.save_preferences(preferences)

            self.logger.info(f"Restored settings from snapshot: {snapshot_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to restore snapshot: {e}")
            return False

    def _update_system_settings(self, updates: Dict[str, Any]) -> bool:
        """Update system-wide settings."""
        return self.config_manager.update_configuration(updates)

    def _update_user_settings(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user-specific settings."""
        return self.preferences_manager.update_preferences(user_id, "default", updates)

    def _check_migrations(self):
        """Check for pending migrations."""
        # Placeholder - would check for pending migrations and execute them

    def _get_migration_steps(self, from_version: str, to_version: str) -> List[str]:
        """Get migration steps for version transition."""
        # Placeholder - would return actual migration steps
        return [
            "validate_source_configuration",
            "backup_existing_settings",
            "transform_configuration_schema",
            "validate_target_configuration",
            "update_version_metadata",
        ]

    def _execute_migration_step(self, step: str, user_id: Optional[str]) -> bool:
        """Execute a single migration step."""
        # Placeholder - would execute actual migration logic
        self.logger.info(f"Executing migration step: {step}")
        return True

    def _save_migration_plan(self, plan: MigrationPlan):
        """Save migration plan to file."""
        try:
            plan_file = self.migrations_dir / f"{plan.migration_id}.json"
            with open(plan_file, "w", encoding="utf-8") as f:
                json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save migration plan: {e}")

    def _generate_snapshot_id(self) -> str:
        """Generate unique snapshot ID."""
        timestamp = datetime.utcnow().isoformat()
        data = f"snapshot:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_migration_id(self, from_version: str, to_version: str) -> str:
        """Generate unique migration ID."""
        timestamp = datetime.utcnow().isoformat()
        data = f"migration:{from_version}:{to_version}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
