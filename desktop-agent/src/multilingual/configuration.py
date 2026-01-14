"""
Multilingual Configuration Management

Production-grade configuration system for multilingual understanding that integrates
with existing GURU configuration framework while providing language-specific settings,
model management, and security controls.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime

from .exceptions import ConfigurationError, UnsupportedLanguageError


class LanguageScript(Enum):
    """Supported writing scripts for multilingual text rendering."""
    
    LATIN = "latin"
    DEVANAGARI = "devanagari"  # Hindi, Marathi, Sanskrit
    TAMIL = "tamil"
    TELUGU = "telugu"
    BENGALI = "bengali"
    GUJARATI = "gujarati"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    GURMUKHI = "gurmukhi"  # Punjabi
    CHINESE_SIMPLIFIED = "chinese_simplified"
    CHINESE_TRADITIONAL = "chinese_traditional"
    JAPANESE = "japanese"
    ARABIC = "arabic"
    CYRILLIC = "cyrillic"


class ModelType(Enum):
    """Types of language models used in multilingual processing."""
    
    FASTTEXT_DETECTION = "fasttext_detection"
    WHISPER_STT = "whisper_stt"
    WHISPER_LANGUAGE_ID = "whisper_language_id"
    SPEAKER_VERIFICATION = "speaker_verification"
    INTENT_MAPPING = "intent_mapping"


@dataclass
class LanguageConfig:
    """Configuration for a specific language."""
    
    # Basic language information
    language_code: str  # ISO 639-1 code (e.g., 'en', 'hi', 'ta')
    language_name: str  # Human-readable name
    native_name: str    # Name in native script
    script: LanguageScript
    
    # Model configuration
    whisper_model: str  # Whisper model identifier
    fasttext_model: Optional[str] = None
    
    # Processing settings
    enabled: bool = True
    confidence_threshold: float = 0.85
    speaker_verification_threshold: float = 0.75
    
    # Performance settings
    max_detection_time_ms: int = 150  # With hardware acceleration
    max_detection_time_fallback_ms: int = 300  # Software only
    
    # Regional settings
    region_code: Optional[str] = None  # e.g., 'IN', 'US', 'CN'
    locale: Optional[str] = None       # e.g., 'hi-IN', 'en-US'
    
    # Input method integration
    input_method_id: Optional[str] = None
    keyboard_layout: Optional[str] = None
    
    # Quality settings
    audio_quality_threshold: float = 0.7
    noise_tolerance: float = 0.3
    
    def __post_init__(self):
        """Validate language configuration after initialization."""
        if not self.language_code or len(self.language_code) not in [2, 3]:
            raise ConfigurationError(
                f"Invalid language code: {self.language_code}",
                config_section="language",
                config_key="language_code",
                expected_type="2 or 3-character ISO 639 code"
            )
            
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ConfigurationError(
                f"Confidence threshold must be between 0.0 and 1.0: {self.confidence_threshold}",
                config_section="language",
                config_key="confidence_threshold"
            )
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert language config to dictionary."""
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LanguageConfig':
        """Create language config from dictionary."""
        # Convert script string to enum
        if 'script' in data and isinstance(data['script'], str):
            data['script'] = LanguageScript(data['script'])
            
        return cls(**data)


class SupportedLanguages:
    """Registry of supported languages with their configurations."""
    
    # Global languages
    ENGLISH = LanguageConfig(
        language_code="en",
        language_name="English",
        native_name="English",
        script=LanguageScript.LATIN,
        whisper_model="en",
        fasttext_model="lid.176.bin",
        region_code="US",
        locale="en-US"
    )
    
    GERMAN = LanguageConfig(
        language_code="de",
        language_name="German",
        native_name="Deutsch",
        script=LanguageScript.LATIN,
        whisper_model="de",
        region_code="DE",
        locale="de-DE"
    )
    
    FRENCH = LanguageConfig(
        language_code="fr",
        language_name="French",
        native_name="Français",
        script=LanguageScript.LATIN,
        whisper_model="fr",
        region_code="FR",
        locale="fr-FR"
    )
    
    CHINESE = LanguageConfig(
        language_code="zh",
        language_name="Chinese (Mandarin)",
        native_name="中文",
        script=LanguageScript.CHINESE_SIMPLIFIED,
        whisper_model="zh",
        region_code="CN",
        locale="zh-CN"
    )
    
    JAPANESE = LanguageConfig(
        language_code="ja",
        language_name="Japanese",
        native_name="日本語",
        script=LanguageScript.JAPANESE,
        whisper_model="ja",
        region_code="JP",
        locale="ja-JP"
    )
    
    # Indian languages
    HINDI = LanguageConfig(
        language_code="hi",
        language_name="Hindi",
        native_name="हिन्दी",
        script=LanguageScript.DEVANAGARI,
        whisper_model="hi",
        region_code="IN",
        locale="hi-IN",
        input_method_id="hi-IN-devanagari"
    )
    
    TAMIL = LanguageConfig(
        language_code="ta",
        language_name="Tamil",
        native_name="தமிழ்",
        script=LanguageScript.TAMIL,
        whisper_model="ta",
        region_code="IN",
        locale="ta-IN",
        input_method_id="ta-IN-tamil"
    )
    
    TELUGU = LanguageConfig(
        language_code="te",
        language_name="Telugu",
        native_name="తెలుగు",
        script=LanguageScript.TELUGU,
        whisper_model="te",
        region_code="IN",
        locale="te-IN",
        input_method_id="te-IN-telugu"
    )
    
    BENGALI = LanguageConfig(
        language_code="bn",
        language_name="Bengali",
        native_name="বাংলা",
        script=LanguageScript.BENGALI,
        whisper_model="bn",
        region_code="IN",
        locale="bn-IN",
        input_method_id="bn-IN-bengali"
    )
    
    MARATHI = LanguageConfig(
        language_code="mr",
        language_name="Marathi",
        native_name="मराठी",
        script=LanguageScript.DEVANAGARI,
        whisper_model="mr",
        region_code="IN",
        locale="mr-IN",
        input_method_id="mr-IN-devanagari"
    )
    
    GUJARATI = LanguageConfig(
        language_code="gu",
        language_name="Gujarati",
        native_name="ગુજરાતી",
        script=LanguageScript.GUJARATI,
        whisper_model="gu",
        region_code="IN",
        locale="gu-IN",
        input_method_id="gu-IN-gujarati"
    )
    
    KANNADA = LanguageConfig(
        language_code="kn",
        language_name="Kannada",
        native_name="ಕನ್ನಡ",
        script=LanguageScript.KANNADA,
        whisper_model="kn",
        region_code="IN",
        locale="kn-IN",
        input_method_id="kn-IN-kannada"
    )
    
    MALAYALAM = LanguageConfig(
        language_code="ml",
        language_name="Malayalam",
        native_name="മലയാളം",
        script=LanguageScript.MALAYALAM,
        whisper_model="ml",
        region_code="IN",
        locale="ml-IN",
        input_method_id="ml-IN-malayalam"
    )
    
    PUNJABI = LanguageConfig(
        language_code="pa",
        language_name="Punjabi",
        native_name="ਪੰਜਾਬੀ",
        script=LanguageScript.GURMUKHI,
        whisper_model="pa",
        region_code="IN",
        locale="pa-IN",
        input_method_id="pa-IN-gurmukhi"
    )
    
    BHOJPURI = LanguageConfig(
        language_code="bho",
        language_name="Bhojpuri",
        native_name="भोजपुरी",
        script=LanguageScript.DEVANAGARI,
        whisper_model="bho",
        region_code="IN",
        locale="bho-IN",
        input_method_id="bho-IN-devanagari"
    )
    
    @classmethod
    def get_all_languages(cls) -> Dict[str, LanguageConfig]:
        """Get all supported language configurations."""
        return {
            "en": cls.ENGLISH,
            "de": cls.GERMAN,
            "fr": cls.FRENCH,
            "zh": cls.CHINESE,
            "ja": cls.JAPANESE,
            "hi": cls.HINDI,
            "ta": cls.TAMIL,
            "te": cls.TELUGU,
            "bn": cls.BENGALI,
            "mr": cls.MARATHI,
            "gu": cls.GUJARATI,
            "kn": cls.KANNADA,
            "ml": cls.MALAYALAM,
            "pa": cls.PUNJABI,
            "bho": cls.BHOJPURI
        }
        
    @classmethod
    def get_language_codes(cls) -> List[str]:
        """Get list of all supported language codes."""
        return list(cls.get_all_languages().keys())
        
    @classmethod
    def get_language_by_code(cls, code: str) -> LanguageConfig:
        """Get language configuration by code."""
        languages = cls.get_all_languages()
        if code not in languages:
            raise UnsupportedLanguageError(
                f"Language code '{code}' is not supported",
                requested_language=code,
                supported_languages=list(languages.keys())
            )
        return languages[code]
        
    @classmethod
    def is_supported(cls, code: str) -> bool:
        """Check if language code is supported."""
        return code in cls.get_all_languages()


@dataclass
class ModelConfiguration:
    """Configuration for language models."""
    
    model_type: ModelType
    model_path: Path
    language: Optional[str] = None
    checksum: Optional[str] = None
    version: Optional[str] = None
    size_mb: Optional[float] = None
    loaded: bool = False
    load_time_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model config to dictionary."""
        return {
            'model_type': self.model_type.value,
            'model_path': str(self.model_path),
            'language': self.language,
            'checksum': self.checksum,
            'version': self.version,
            'size_mb': self.size_mb,
            'loaded': self.loaded,
            'load_time_ms': self.load_time_ms
        }


@dataclass
class MultilingualConfig:
    """Main multilingual configuration."""
    
    # Language settings
    enabled_languages: List[str] = field(default_factory=lambda: ["en"])
    primary_language: str = "en"
    fallback_language: str = "en"
    
    # Detection settings
    detection_threshold: float = 0.85
    mixed_language_support: bool = True
    cache_language_context: bool = True
    session_language_persistence: bool = True
    
    # Performance settings
    max_detection_time_ms: int = 150  # Hardware accelerated
    max_detection_time_fallback_ms: int = 300  # Software only
    enable_hardware_acceleration: bool = True
    
    # Security settings
    require_speaker_verification: bool = True
    speaker_verification_threshold: float = 0.75
    log_language_detection: bool = True
    log_intent_normalization: bool = True
    log_sensitive_content: bool = False  # Never log actual content
    
    # Model paths
    model_directory: Path = field(default_factory=lambda: Path("models/multilingual"))
    fasttext_model_path: Optional[Path] = None
    whisper_models_path: Optional[Path] = None
    
    # Integration settings
    integrate_with_existing_voice_pipeline: bool = True
    maintain_existing_security_boundaries: bool = True
    preserve_existing_audit_logging: bool = True
    
    # Advanced settings
    enable_debug_logging: bool = False
    performance_monitoring: bool = True
    automatic_model_updates: bool = False
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_languages()
        self._validate_thresholds()
        self._validate_paths()
        
    def _validate_languages(self):
        """Validate language configuration."""
        # Check primary language is supported
        if not SupportedLanguages.is_supported(self.primary_language):
            raise ConfigurationError(
                f"Primary language '{self.primary_language}' is not supported",
                config_section="languages",
                config_key="primary_language",
                expected_type="supported language code"
            )
            
        # Check fallback language is supported
        if not SupportedLanguages.is_supported(self.fallback_language):
            raise ConfigurationError(
                f"Fallback language '{self.fallback_language}' is not supported",
                config_section="languages",
                config_key="fallback_language"
            )
            
        # Check all enabled languages are supported
        unsupported = [lang for lang in self.enabled_languages 
                      if not SupportedLanguages.is_supported(lang)]
        if unsupported:
            raise ConfigurationError(
                f"Unsupported languages in enabled list: {unsupported}",
                config_section="languages",
                config_key="enabled_languages",
                supported_languages=SupportedLanguages.get_language_codes()
            )
            
        # Ensure primary language is in enabled languages
        if self.primary_language not in self.enabled_languages:
            self.enabled_languages.insert(0, self.primary_language)
            
    def _validate_thresholds(self):
        """Validate threshold values."""
        if not 0.0 <= self.detection_threshold <= 1.0:
            raise ConfigurationError(
                f"Detection threshold must be between 0.0 and 1.0: {self.detection_threshold}",
                config_key="detection_threshold"
            )
            
        if not 0.0 <= self.speaker_verification_threshold <= 1.0:
            raise ConfigurationError(
                f"Speaker verification threshold must be between 0.0 and 1.0: {self.speaker_verification_threshold}",
                config_key="speaker_verification_threshold"
            )
            
    def _validate_paths(self):
        """Validate model paths."""
        if not self.model_directory.exists():
            try:
                self.model_directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ConfigurationError(
                    f"Cannot create model directory: {self.model_directory}",
                    config_key="model_directory",
                    context={'error': str(e)}
                )
                
    def get_enabled_language_configs(self) -> Dict[str, LanguageConfig]:
        """Get configurations for all enabled languages."""
        return {
            code: SupportedLanguages.get_language_by_code(code)
            for code in self.enabled_languages
        }
        
    def is_language_enabled(self, language_code: str) -> bool:
        """Check if a language is enabled."""
        return language_code in self.enabled_languages
        
    def add_language(self, language_code: str) -> bool:
        """Add a language to enabled languages."""
        if not SupportedLanguages.is_supported(language_code):
            return False
            
        if language_code not in self.enabled_languages:
            self.enabled_languages.append(language_code)
            
        return True
        
    def remove_language(self, language_code: str) -> bool:
        """Remove a language from enabled languages."""
        if language_code == self.primary_language:
            return False  # Cannot remove primary language
            
        if language_code in self.enabled_languages:
            self.enabled_languages.remove(language_code)
            
        return True
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'enabled_languages': self.enabled_languages,
            'primary_language': self.primary_language,
            'fallback_language': self.fallback_language,
            'detection_threshold': self.detection_threshold,
            'mixed_language_support': self.mixed_language_support,
            'cache_language_context': self.cache_language_context,
            'session_language_persistence': self.session_language_persistence,
            'max_detection_time_ms': self.max_detection_time_ms,
            'max_detection_time_fallback_ms': self.max_detection_time_fallback_ms,
            'enable_hardware_acceleration': self.enable_hardware_acceleration,
            'require_speaker_verification': self.require_speaker_verification,
            'speaker_verification_threshold': self.speaker_verification_threshold,
            'log_language_detection': self.log_language_detection,
            'log_intent_normalization': self.log_intent_normalization,
            'log_sensitive_content': self.log_sensitive_content,
            'model_directory': str(self.model_directory),
            'fasttext_model_path': str(self.fasttext_model_path) if self.fasttext_model_path else None,
            'whisper_models_path': str(self.whisper_models_path) if self.whisper_models_path else None,
            'integrate_with_existing_voice_pipeline': self.integrate_with_existing_voice_pipeline,
            'maintain_existing_security_boundaries': self.maintain_existing_security_boundaries,
            'preserve_existing_audit_logging': self.preserve_existing_audit_logging,
            'enable_debug_logging': self.enable_debug_logging,
            'performance_monitoring': self.performance_monitoring,
            'automatic_model_updates': self.automatic_model_updates
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultilingualConfig':
        """Create configuration from dictionary."""
        # Convert path strings to Path objects
        if 'model_directory' in data:
            data['model_directory'] = Path(data['model_directory'])
        if 'fasttext_model_path' in data and data['fasttext_model_path']:
            data['fasttext_model_path'] = Path(data['fasttext_model_path'])
        if 'whisper_models_path' in data and data['whisper_models_path']:
            data['whisper_models_path'] = Path(data['whisper_models_path'])
            
        return cls(**data)


class ConfigurationController:
    """
    Direct control of multilingual configuration loading, validation, and runtime updates.
    
    Controls configuration lifecycle including loading, validation, hot-reloading,
    and integration with existing GURU configuration system.
    
    This controller manages:
    - Configuration file loading and parsing
    - Schema validation and constraint checking
    - Runtime configuration updates
    - Configuration persistence
    - Integration with GURU config system
    - Configuration change notifications
    
    Provides configuration loading, validation, persistence, and runtime updates
    while maintaining compatibility with existing GURU configuration systems.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path or Path("config/multilingual.json")
        self._config: Optional[MultilingualConfig] = None
        self._models: Dict[str, ModelConfiguration] = {}
        
    def load_configuration(self) -> MultilingualConfig:
        """Load multilingual configuration from file or create default."""
        try:
            if self.config_path.exists():
                self.logger.info(f"Loading multilingual configuration from {self.config_path}")
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                self._config = MultilingualConfig.from_dict(config_data)
                self.logger.info(f"Loaded configuration with {len(self._config.enabled_languages)} enabled languages")
                
            else:
                self.logger.info("Creating default multilingual configuration")
                self._config = self._create_default_configuration()
                self.save_configuration()
                
            return self._config
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load multilingual configuration: {str(e)}",
                config_section="configuration_manager",
                context={'config_path': str(self.config_path), 'error': str(e)}
            )
            
    def save_configuration(self) -> bool:
        """Save current configuration to file."""
        if not self._config:
            return False
            
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save configuration
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Saved multilingual configuration to {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
            
    def get_configuration(self) -> MultilingualConfig:
        """Get current configuration, loading if necessary."""
        if not self._config:
            return self.load_configuration()
        return self._config
        
    def update_configuration(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with new values."""
        try:
            config = self.get_configuration()
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    self.logger.warning(f"Unknown configuration key: {key}")
                    
            # Validate updated configuration
            config.__post_init__()
            
            # Save updated configuration
            return self.save_configuration()
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            return False
            
    def register_model(self, model_config: ModelConfiguration) -> bool:
        """Register a language model configuration."""
        try:
            model_key = f"{model_config.model_type.value}_{model_config.language or 'global'}"
            self._models[model_key] = model_config
            
            self.logger.info(f"Registered model: {model_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register model: {e}")
            return False
            
    def get_model_config(self, model_type: ModelType, language: Optional[str] = None) -> Optional[ModelConfiguration]:
        """Get model configuration by type and language."""
        model_key = f"{model_type.value}_{language or 'global'}"
        return self._models.get(model_key)
        
    def get_language_config(self, language_code: str) -> LanguageConfig:
        """Get configuration for a specific language."""
        return SupportedLanguages.get_language_by_code(language_code)
        
    def _create_default_configuration(self) -> MultilingualConfig:
        """Create default multilingual configuration."""
        return MultilingualConfig(
            enabled_languages=["en"],  # Start with English only
            primary_language="en",
            fallback_language="en",
            detection_threshold=0.85,
            mixed_language_support=True,
            cache_language_context=True,
            max_detection_time_ms=150,
            max_detection_time_fallback_ms=300,
            require_speaker_verification=True,
            speaker_verification_threshold=0.75,
            log_language_detection=True,
            log_intent_normalization=True,
            log_sensitive_content=False,
            integrate_with_existing_voice_pipeline=True,
            maintain_existing_security_boundaries=True,
            preserve_existing_audit_logging=True
        )
        
    def validate_configuration(self) -> List[str]:
        """Validate current configuration and return any issues."""
        issues = []
        
        try:
            config = self.get_configuration()
            
            # Check model directory
            if not config.model_directory.exists():
                issues.append(f"Model directory does not exist: {config.model_directory}")
                
            # Check enabled languages have required models
            for lang_code in config.enabled_languages:
                lang_config = SupportedLanguages.get_language_by_code(lang_code)
                
                # Check Whisper model
                if config.whisper_models_path:
                    whisper_path = config.whisper_models_path / f"{lang_config.whisper_model}.bin"
                    if not whisper_path.exists():
                        issues.append(f"Missing Whisper model for {lang_code}: {whisper_path}")
                        
            # Check FastText model
            if config.fasttext_model_path and not config.fasttext_model_path.exists():
                issues.append(f"FastText model not found: {config.fasttext_model_path}")
                
        except Exception as e:
            issues.append(f"Configuration validation error: {str(e)}")
            
        return issues