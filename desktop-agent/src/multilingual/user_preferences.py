"""
User Preferences for Multilingual Configuration

Production-grade user preference management system that provides granular control
over multilingual behavior, language priorities, detection sensitivity, and
customization options while maintaining security boundaries.

Requirements: 15.1, 15.2, 15.3
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from threading import Lock

from .configuration import (
    LanguageConfig,
    SupportedLanguages,
    MultilingualConfig,
    ConfigurationError
)
from .exceptions import UnsupportedLanguageError


class DetectionSensitivity(Enum):
    """Language detection sensitivity levels."""
    
    VERY_LOW = 0.70   # Accept lower confidence, more permissive
    LOW = 0.75        # Slightly relaxed detection
    NORMAL = 0.85     # Default balanced detection
    HIGH = 0.90       # Stricter detection requirements
    VERY_HIGH = 0.95  # Maximum strictness, highest confidence required
    
    @property
    def threshold(self) -> float:
        """Get confidence threshold for this sensitivity level."""
        return self.value
        
    @property
    def description(self) -> str:
        """Get human-readable description."""
        descriptions = {
            DetectionSensitivity.VERY_LOW: "Very permissive - accepts lower confidence detections",
            DetectionSensitivity.LOW: "Permissive - slightly relaxed detection",
            DetectionSensitivity.NORMAL: "Balanced - recommended for most users",
            DetectionSensitivity.HIGH: "Strict - requires high confidence",
            DetectionSensitivity.VERY_HIGH: "Very strict - maximum confidence required"
        }
        return descriptions[self]


class MixedLanguageStrategy(Enum):
    """Strategy for handling mixed-language utterances."""
    
    AUTO_DETECT = "auto_detect"           # Automatically detect and segment
    PRIMARY_ONLY = "primary_only"         # Use only primary language
    REJECT = "reject"                     # Reject mixed-language input
    PROMPT_USER = "prompt_user"           # Ask user for clarification
    SEGMENT_AND_PROCESS = "segment_and_process"  # Process each segment separately


class FallbackBehavior(Enum):
    """Behavior when language detection fails."""
    
    USE_PRIMARY = "use_primary"           # Fall back to primary language
    USE_LAST_DETECTED = "use_last_detected"  # Use last successfully detected language
    PROMPT_USER = "prompt_user"           # Ask user to specify language
    REJECT = "reject"                     # Reject the input
    USE_FALLBACK_LANGUAGE = "use_fallback_language"  # Use configured fallback


@dataclass
class LanguagePriority:
    """Priority configuration for a specific language."""
    
    language_code: str
    priority: int  # Lower number = higher priority (1 is highest)
    enabled: bool = True
    custom_threshold: Optional[float] = None
    custom_sensitivity: Optional[DetectionSensitivity] = None
    
    # Language-specific preferences
    prefer_for_dictation: bool = False
    prefer_for_commands: bool = False
    
    # Performance preferences
    preload_models: bool = False
    cache_aggressively: bool = False
    
    def __post_init__(self):
        """Validate priority configuration."""
        if self.priority < 1:
            raise ConfigurationError(
                f"Priority must be >= 1, got {self.priority}",
                config_key="priority"
            )
            
        if self.custom_threshold is not None:
            if not 0.0 <= self.custom_threshold <= 1.0:
                raise ConfigurationError(
                    f"Custom threshold must be between 0.0 and 1.0: {self.custom_threshold}",
                    config_key="custom_threshold"
                )
                
    def get_effective_threshold(self, default: float) -> float:
        """Get effective threshold considering custom settings."""
        if self.custom_threshold is not None:
            return self.custom_threshold
        elif self.custom_sensitivity is not None:
            return self.custom_sensitivity.threshold
        else:
            return default
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'language_code': self.language_code,
            'priority': self.priority,
            'enabled': self.enabled,
            'custom_threshold': self.custom_threshold,
            'custom_sensitivity': self.custom_sensitivity.name if self.custom_sensitivity else None,
            'prefer_for_dictation': self.prefer_for_dictation,
            'prefer_for_commands': self.prefer_for_commands,
            'preload_models': self.preload_models,
            'cache_aggressively': self.cache_aggressively
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LanguagePriority':
        """Create from dictionary."""
        if 'custom_sensitivity' in data and data['custom_sensitivity']:
            data['custom_sensitivity'] = DetectionSensitivity[data['custom_sensitivity']]
        return cls(**data)


@dataclass
class UserPreferences:
    """
    Comprehensive user preferences for multilingual configuration.
    
    Provides granular control over language detection, processing behavior,
    and customization options while maintaining security boundaries.
    """
    
    # User identification
    user_id: str
    profile_name: str = "default"
    
    # Language priorities (ordered list)
    language_priorities: List[LanguagePriority] = field(default_factory=list)
    
    # Global detection settings
    global_sensitivity: DetectionSensitivity = DetectionSensitivity.NORMAL
    mixed_language_strategy: MixedLanguageStrategy = MixedLanguageStrategy.AUTO_DETECT
    fallback_behavior: FallbackBehavior = FallbackBehavior.USE_PRIMARY
    
    # Session behavior
    remember_last_language: bool = True
    session_language_persistence_minutes: int = 30
    auto_switch_on_detection: bool = True
    
    # Dictation preferences
    dictation_auto_punctuation: bool = False  # Never modify dictation by default
    dictation_auto_capitalization: bool = False
    dictation_preserve_exact: bool = True  # Hard invariant
    
    # Command preferences
    command_confirmation_required: bool = False
    command_language_hints: bool = True
    command_fuzzy_matching: bool = True
    
    # Performance preferences
    preload_preferred_languages: bool = True
    aggressive_caching: bool = True
    hardware_acceleration_preference: bool = True
    
    # Privacy preferences
    log_language_detection_events: bool = True
    log_command_normalization: bool = True
    log_dictation_metadata: bool = True  # Metadata only, never content
    
    # Notification preferences
    notify_on_language_switch: bool = True
    notify_on_low_confidence: bool = True
    notify_on_fallback: bool = True
    audio_feedback_enabled: bool = True
    
    # Advanced settings
    enable_experimental_features: bool = False
    custom_intent_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    
    def __post_init__(self):
        """Validate preferences after initialization."""
        self._validate_language_priorities()
        self._validate_session_settings()
        self._enforce_security_invariants()
        
    def _validate_language_priorities(self):
        """Validate language priority configuration."""
        if not self.language_priorities:
            # Create default priority list with primary language
            self.language_priorities = [
                LanguagePriority(language_code="en", priority=1, enabled=True)
            ]
            
        # Check for duplicate priorities
        priorities = [lp.priority for lp in self.language_priorities]
        if len(priorities) != len(set(priorities)):
            raise ConfigurationError(
                "Duplicate priority values found in language priorities",
                config_section="user_preferences",
                config_key="language_priorities"
            )
            
        # Validate all language codes are supported
        for lp in self.language_priorities:
            if not SupportedLanguages.is_supported(lp.language_code):
                raise UnsupportedLanguageError(
                    f"Language code '{lp.language_code}' in priorities is not supported",
                    requested_language=lp.language_code,
                    supported_languages=SupportedLanguages.get_language_codes()
                )
                
    def _validate_session_settings(self):
        """Validate session-related settings."""
        if self.session_language_persistence_minutes < 0:
            raise ConfigurationError(
                f"Session persistence must be >= 0: {self.session_language_persistence_minutes}",
                config_key="session_language_persistence_minutes"
            )
            
    def _enforce_security_invariants(self):
        """Enforce security invariants that cannot be changed."""
        # Dictation must always preserve exact text (hard invariant)
        if not self.dictation_preserve_exact:
            logging.warning(
                "Attempting to disable dictation_preserve_exact - this is a security invariant. "
                "Forcing to True."
            )
            self.dictation_preserve_exact = True
            
        # Auto-punctuation and capitalization must be disabled for exact preservation
        if self.dictation_preserve_exact:
            if self.dictation_auto_punctuation or self.dictation_auto_capitalization:
                logging.warning(
                    "Auto-punctuation/capitalization conflicts with exact preservation. "
                    "Disabling auto-modifications."
                )
                self.dictation_auto_punctuation = False
                self.dictation_auto_capitalization = False
                
    def get_language_priority(self, language_code: str) -> Optional[LanguagePriority]:
        """Get priority configuration for a specific language."""
        for lp in self.language_priorities:
            if lp.language_code == language_code:
                return lp
        return None
        
    def get_ordered_languages(self, enabled_only: bool = True) -> List[str]:
        """Get languages ordered by priority."""
        priorities = self.language_priorities
        if enabled_only:
            priorities = [lp for lp in priorities if lp.enabled]
            
        # Sort by priority (lower number = higher priority)
        sorted_priorities = sorted(priorities, key=lambda lp: lp.priority)
        return [lp.language_code for lp in sorted_priorities]
        
    def set_language_priority(self, language_code: str, priority: int) -> bool:
        """Set priority for a language."""
        if not SupportedLanguages.is_supported(language_code):
            return False
            
        # Find existing priority config
        existing = self.get_language_priority(language_code)
        
        if existing:
            # Update existing priority
            old_priority = existing.priority
            existing.priority = priority
            
            # Adjust other priorities if needed
            self._adjust_priorities_after_change(language_code, old_priority, priority)
        else:
            # Add new priority config
            self.language_priorities.append(
                LanguagePriority(language_code=language_code, priority=priority)
            )
            
        self.updated_at = datetime.utcnow()
        return True
        
    def _adjust_priorities_after_change(self, changed_lang: str, old_priority: int, new_priority: int):
        """Adjust other language priorities after a change to maintain uniqueness."""
        if old_priority == new_priority:
            return
            
        # Shift priorities to make room
        for lp in self.language_priorities:
            if lp.language_code == changed_lang:
                continue
                
            if old_priority < new_priority:
                # Moving down in priority
                if old_priority < lp.priority <= new_priority:
                    lp.priority -= 1
            else:
                # Moving up in priority
                if new_priority <= lp.priority < old_priority:
                    lp.priority += 1
                    
    def enable_language(self, language_code: str) -> bool:
        """Enable a language."""
        lp = self.get_language_priority(language_code)
        if lp:
            lp.enabled = True
            self.updated_at = datetime.utcnow()
            return True
        return False
        
    def disable_language(self, language_code: str) -> bool:
        """Disable a language."""
        lp = self.get_language_priority(language_code)
        if lp:
            lp.enabled = False
            self.updated_at = datetime.utcnow()
            return True
        return False
        
    def set_language_threshold(self, language_code: str, threshold: float) -> bool:
        """Set custom detection threshold for a language."""
        if not 0.0 <= threshold <= 1.0:
            return False
            
        lp = self.get_language_priority(language_code)
        if lp:
            lp.custom_threshold = threshold
            self.updated_at = datetime.utcnow()
            return True
        return False
        
    def set_language_sensitivity(self, language_code: str, sensitivity: DetectionSensitivity) -> bool:
        """Set detection sensitivity for a language."""
        lp = self.get_language_priority(language_code)
        if lp:
            lp.custom_sensitivity = sensitivity
            self.updated_at = datetime.utcnow()
            return True
        return False
        
    def get_effective_threshold(self, language_code: str, default: float) -> float:
        """Get effective detection threshold for a language."""
        lp = self.get_language_priority(language_code)
        if lp:
            return lp.get_effective_threshold(default)
        return default
        
    def add_custom_intent_mapping(self, language: str, pattern: str, intent: str) -> bool:
        """Add custom intent mapping for a language."""
        if language not in self.custom_intent_mappings:
            self.custom_intent_mappings[language] = {}
            
        self.custom_intent_mappings[language][pattern] = intent
        self.updated_at = datetime.utcnow()
        return True
        
    def remove_custom_intent_mapping(self, language: str, pattern: str) -> bool:
        """Remove custom intent mapping."""
        if language in self.custom_intent_mappings:
            if pattern in self.custom_intent_mappings[language]:
                del self.custom_intent_mappings[language][pattern]
                self.updated_at = datetime.utcnow()
                return True
        return False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            'user_id': self.user_id,
            'profile_name': self.profile_name,
            'language_priorities': [lp.to_dict() for lp in self.language_priorities],
            'global_sensitivity': self.global_sensitivity.name,
            'mixed_language_strategy': self.mixed_language_strategy.value,
            'fallback_behavior': self.fallback_behavior.value,
            'remember_last_language': self.remember_last_language,
            'session_language_persistence_minutes': self.session_language_persistence_minutes,
            'auto_switch_on_detection': self.auto_switch_on_detection,
            'dictation_auto_punctuation': self.dictation_auto_punctuation,
            'dictation_auto_capitalization': self.dictation_auto_capitalization,
            'dictation_preserve_exact': self.dictation_preserve_exact,
            'command_confirmation_required': self.command_confirmation_required,
            'command_language_hints': self.command_language_hints,
            'command_fuzzy_matching': self.command_fuzzy_matching,
            'preload_preferred_languages': self.preload_preferred_languages,
            'aggressive_caching': self.aggressive_caching,
            'hardware_acceleration_preference': self.hardware_acceleration_preference,
            'log_language_detection_events': self.log_language_detection_events,
            'log_command_normalization': self.log_command_normalization,
            'log_dictation_metadata': self.log_dictation_metadata,
            'notify_on_language_switch': self.notify_on_language_switch,
            'notify_on_low_confidence': self.notify_on_low_confidence,
            'notify_on_fallback': self.notify_on_fallback,
            'audio_feedback_enabled': self.audio_feedback_enabled,
            'enable_experimental_features': self.enable_experimental_features,
            'custom_intent_mappings': self.custom_intent_mappings,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferences':
        """Create preferences from dictionary."""
        # Convert enum strings to enums
        if 'global_sensitivity' in data:
            data['global_sensitivity'] = DetectionSensitivity[data['global_sensitivity']]
        if 'mixed_language_strategy' in data:
            data['mixed_language_strategy'] = MixedLanguageStrategy(data['mixed_language_strategy'])
        if 'fallback_behavior' in data:
            data['fallback_behavior'] = FallbackBehavior(data['fallback_behavior'])
            
        # Convert language priorities
        if 'language_priorities' in data:
            data['language_priorities'] = [
                LanguagePriority.from_dict(lp) for lp in data['language_priorities']
            ]
            
        # Convert datetime strings
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)


class UserPreferencesPersistence:
    """
    Persistent storage and retrieval of user preferences across sessions.
    
    Provides thread-safe preference persistence with automatic validation,
    caching, and integration with multilingual configuration system.
    
    This persistence layer handles:
    - Preference loading and saving to disk
    - Thread-safe cache management
    - Validation and migration
    - Default preference creation
    - Runtime preference updates
    """
    
    def __init__(self, preferences_dir: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.preferences_dir = preferences_dir or Path("config/user_preferences")
        self.preferences_dir.mkdir(parents=True, exist_ok=True)
        
        self._preferences_cache: Dict[str, UserPreferences] = {}
        self._cache_lock = Lock()
        
    def load_preferences(self, user_id: str, profile_name: str = "default") -> UserPreferences:
        """Load user preferences from file or create default."""
        cache_key = f"{user_id}:{profile_name}"
        
        with self._cache_lock:
            # Check cache first
            if cache_key in self._preferences_cache:
                return self._preferences_cache[cache_key]
                
            # Load from file
            prefs_file = self._get_preferences_file(user_id, profile_name)
            
            if prefs_file.exists():
                try:
                    with open(prefs_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    preferences = UserPreferences.from_dict(data)
                    self._preferences_cache[cache_key] = preferences
                    
                    self.logger.info(f"Loaded preferences for user {user_id}, profile {profile_name}")
                    return preferences
                    
                except Exception as e:
                    self.logger.error(f"Failed to load preferences: {e}")
                    # Fall through to create default
                    
            # Create default preferences
            preferences = self._create_default_preferences(user_id, profile_name)
            self._preferences_cache[cache_key] = preferences
            self.save_preferences(preferences)
            
            return preferences
            
    def save_preferences(self, preferences: UserPreferences) -> bool:
        """Save user preferences to file."""
        try:
            prefs_file = self._get_preferences_file(preferences.user_id, preferences.profile_name)
            prefs_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update timestamp
            preferences.updated_at = datetime.utcnow()
            
            # Save to file
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(preferences.to_dict(), f, indent=2, ensure_ascii=False)
                
            # Update cache
            cache_key = f"{preferences.user_id}:{preferences.profile_name}"
            with self._cache_lock:
                self._preferences_cache[cache_key] = preferences
                
            self.logger.info(f"Saved preferences for user {preferences.user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save preferences: {e}")
            return False
            
    def update_preferences(self, user_id: str, profile_name: str, updates: Dict[str, Any]) -> bool:
        """Update user preferences with new values."""
        try:
            preferences = self.load_preferences(user_id, profile_name)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(preferences, key):
                    setattr(preferences, key, value)
                else:
                    self.logger.warning(f"Unknown preference key: {key}")
                    
            # Re-validate after updates
            preferences.__post_init__()
            
            # Save updated preferences
            return self.save_preferences(preferences)
            
        except Exception as e:
            self.logger.error(f"Failed to update preferences: {e}")
            return False
            
    def get_preferences(self, user_id: str, profile_name: str = "default") -> UserPreferences:
        """Get user preferences, loading if necessary."""
        return self.load_preferences(user_id, profile_name)
        
    def delete_preferences(self, user_id: str, profile_name: str = "default") -> bool:
        """Delete user preferences."""
        try:
            prefs_file = self._get_preferences_file(user_id, profile_name)
            
            if prefs_file.exists():
                prefs_file.unlink()
                
            # Remove from cache
            cache_key = f"{user_id}:{profile_name}"
            with self._cache_lock:
                if cache_key in self._preferences_cache:
                    del self._preferences_cache[cache_key]
                    
            self.logger.info(f"Deleted preferences for user {user_id}, profile {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete preferences: {e}")
            return False
            
    def list_profiles(self, user_id: str) -> List[str]:
        """List all preference profiles for a user."""
        user_dir = self.preferences_dir / user_id
        
        if not user_dir.exists():
            return []
            
        profiles = []
        for prefs_file in user_dir.glob("*.json"):
            profile_name = prefs_file.stem
            profiles.append(profile_name)
            
        return sorted(profiles)
        
    def _get_preferences_file(self, user_id: str, profile_name: str) -> Path:
        """Get path to preferences file."""
        return self.preferences_dir / user_id / f"{profile_name}.json"
        
    def _create_default_preferences(self, user_id: str, profile_name: str) -> UserPreferences:
        """Create default user preferences."""
        return UserPreferences(
            user_id=user_id,
            profile_name=profile_name,
            language_priorities=[
                LanguagePriority(language_code="en", priority=1, enabled=True, preload_models=True)
            ],
            global_sensitivity=DetectionSensitivity.NORMAL,
            mixed_language_strategy=MixedLanguageStrategy.AUTO_DETECT,
            fallback_behavior=FallbackBehavior.USE_PRIMARY,
            remember_last_language=True,
            session_language_persistence_minutes=30,
            dictation_preserve_exact=True,  # Hard invariant
            preload_preferred_languages=True,
            aggressive_caching=True,
            log_language_detection_events=True,
            log_command_normalization=True,
            notify_on_language_switch=True,
            notify_on_low_confidence=True
        )
        
    def validate_preferences(self, preferences: UserPreferences) -> List[str]:
        """Validate preferences and return any issues."""
        issues = []
        
        try:
            # Validate language priorities
            for lp in preferences.language_priorities:
                if not SupportedLanguages.is_supported(lp.language_code):
                    issues.append(f"Unsupported language in priorities: {lp.language_code}")
                    
            # Check for security invariant violations
            if not preferences.dictation_preserve_exact:
                issues.append("CRITICAL: dictation_preserve_exact must be True (security invariant)")
                
            # Validate thresholds
            for lp in preferences.language_priorities:
                if lp.custom_threshold is not None:
                    if not 0.0 <= lp.custom_threshold <= 1.0:
                        issues.append(f"Invalid threshold for {lp.language_code}: {lp.custom_threshold}")
                        
        except Exception as e:
            issues.append(f"Validation error: {str(e)}")
            
        return issues
