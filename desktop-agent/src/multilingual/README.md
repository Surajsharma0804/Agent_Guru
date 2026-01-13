# GURU Multilingual Understanding

Production-grade multilingual understanding capabilities for the GURU Personal Assistant system. This module extends GURU's existing voice processing pipeline to support natural interaction in 15 languages while maintaining strict security boundaries and user control.

## Overview

The multilingual understanding system provides:

- **Local Language Detection**: Deterministic language identification using FastText and Whisper
- **Intent Normalization**: Language-neutral command mapping that preserves security boundaries
- **Multilingual Voice Processing**: Language-aware speech recognition with speaker verification
- **Mode Classification**: Consistent command/dictation mode detection across languages
- **Comprehensive Audit Logging**: Privacy-preserving multilingual event tracking
- **Seamless Integration**: Drop-in replacement for existing GURU voice processing

## Supported Languages

### Global Languages
- English (en)
- German (de) 
- French (fr)
- Chinese Mandarin (zh)
- Japanese (ja)

### Indian Languages
- Hindi (hi) - हिन्दी
- Tamil (ta) - தமிழ்
- Telugu (te) - తెలుగు
- Bengali (bn) - বাংলা
- Marathi (mr) - मराठी
- Gujarati (gu) - ગુજરાતી
- Kannada (kn) - ಕನ್ನಡ
- Malayalam (ml) - മലയാളം
- Punjabi (pa) - ਪੰਜਾਬੀ
- Bhojpuri (bho) - भोजपुरी

## Architecture

```
Audio Input → Language Detection → Speech-to-Text → Mode Classification → Intent Normalization → Authority Gate → Execution
```

### Core Components

1. **Language Detection Engine** (`language_detection.py`)
   - FastText-based primary detection (≤150ms p95)
   - Whisper-based secondary validation
   - Mixed-language utterance support
   - Session-based caching

2. **Intent Normalization Layer** (`intent_normalization.py`)
   - Language-specific pattern matching
   - Canonical intent generation
   - Security boundary enforcement
   - Deterministic normalization

3. **Voice Processing** (`voice_processing.py`)
   - Language-aware Whisper integration
   - Language-independent speaker verification
   - Mixed-language speech handling

4. **Mode Classification** (`mode_classification.py`)
   - Command vs dictation detection
   - Explicit mode switching support
   - Session context tracking

5. **Pipeline Integration** (`pipeline.py`)
   - Secure processing pipeline
   - Authority integration
   - Performance monitoring
   - Failure handling

## Security Invariants

The multilingual system maintains all existing GURU security invariants:

- **Local-first processing**: No cloud dependency for core language detection
- **Identical security enforcement**: Same authority requirements across all languages
- **No security bypasses**: Language processing cannot override security gates
- **Comprehensive audit logging**: All multilingual decisions are logged
- **Privacy by design**: No sensitive content logging, local processing only

## Quick Start

### 1. Setup

```python
from multilingual.setup import setup_guru_multilingual

# Setup with basic languages
success, integration = setup_guru_multilingual(
    enabled_languages=["en", "hi", "ta"],
    primary_language="en"
)
```

### 2. Process Voice Input

```python
# Process multilingual voice command
result = integration.process_voice_input(
    audio=audio_bytes,
    session_id="user_session",
    expected_speaker_id="authorized_user"
)

# Result contains GURU-compatible command
print(f"Action: {result['action']}")
print(f"Language: {result['metadata']['detected_language']}")
```

### 3. Configuration

```python
from multilingual.configuration import MultilingualConfig, ConfigurationManager

# Load configuration
config_manager = ConfigurationManager()
config = config_manager.load_configuration()

# Update settings
config.detection_threshold = 0.9
config.enabled_languages.append("de")
config_manager.save_configuration()
```

## Configuration

### Basic Configuration

```json
{
  "enabled_languages": ["en", "hi", "ta"],
  "primary_language": "en",
  "fallback_language": "en",
  "detection_threshold": 0.85,
  "speaker_verification_threshold": 0.75,
  "mixed_language_support": true,
  "cache_language_context": true
}
```

### Performance Settings

```json
{
  "max_detection_time_ms": 150,
  "max_detection_time_fallback_ms": 300,
  "enable_hardware_acceleration": true,
  "performance_monitoring": true
}
```

### Security Settings

```json
{
  "require_speaker_verification": true,
  "log_language_detection": true,
  "log_intent_normalization": true,
  "log_sensitive_content": false,
  "maintain_existing_security_boundaries": true
}
```

## Integration with Existing GURU

The multilingual system integrates seamlessly with existing GURU components:

```python
from multilingual.integration import integrate_with_existing_guru

# Integrate with existing voice processor
integration = integrate_with_existing_guru(
    existing_voice_processor=guru_voice_processor,
    multilingual_config=config
)

# Existing GURU code continues to work unchanged
result = integration.process_voice_input(audio)
```

## Command Examples

### English
```
"open calculator" → OPEN_APPLICATION(application="calculator")
"type hello world" → TYPE_TEXT(text="hello world")
"dictation mode" → SWITCH_TO_DICTATION()
```

### Hindi
```
"कैलकुलेटर खोलो" → OPEN_APPLICATION(application="कैलकुलेटर")
"हैलो वर्ल्ड टाइप करो" → TYPE_TEXT(text="हैलो वर्ल्ड")
"डिक्टेशन मोड" → SWITCH_TO_DICTATION()
```

### Tamil
```
"கால்குலேட்டர் ஓபன் பண்ணு" → OPEN_APPLICATION(application="கால்குலேட்டர்")
"ஹலோ வர்ல்ட் டைப் பண்ணு" → TYPE_TEXT(text="ஹலோ வர்ல்ட்")
"டிக்டேஷன் மோட்" → SWITCH_TO_DICTATION()
```

## Testing

### Unit Tests
```bash
cd desktop-agent
python -m pytest tests/multilingual/ -v
```

### Property-Based Tests
```bash
# Run property tests for correctness validation
python -m pytest tests/multilingual/test_properties.py -v
```

### Integration Tests
```bash
# Test with existing GURU components
python -m pytest tests/multilingual/test_integration.py -v
```

## Performance

### Benchmarks (Hardware Accelerated)
- Language Detection: ≤150ms p95
- Speech-to-Text: ≤300ms p95
- Intent Normalization: ≤50ms p95
- Total Pipeline: ≤500ms p95

### Memory Usage
- Base System: ~200MB
- Per Language Model: ~50MB
- Session Cache: ~10MB

## Troubleshooting

### Common Issues

1. **Language Detection Fails**
   ```python
   # Check model availability
   config = ConfigurationManager().load_configuration()
   issues = ConfigurationManager().validate_configuration()
   print(f"Configuration issues: {issues}")
   ```

2. **Performance Issues**
   ```python
   # Check hardware acceleration
   stats = integration.get_integration_status()
   print(f"Processing time: {stats['pipeline_statistics']['average_processing_time_ms']}ms")
   ```

3. **Security Validation Errors**
   ```python
   # Review audit logs
   from multilingual.audit_logging import MultilingualAuditLogger
   logger = MultilingualAuditLogger(config)
   stats = logger.get_audit_statistics()
   ```

### Debug Mode

```python
import logging
logging.getLogger('multilingual').setLevel(logging.DEBUG)

# Enable debug logging in configuration
config.enable_debug_logging = True
```

## Development

### Adding New Languages

1. Add language configuration to `SupportedLanguages`
2. Add intent patterns to `IntentMappingRegistry`
3. Add mode patterns to `ModePatternRegistry`
4. Install language models
5. Update tests

### Custom Intent Patterns

```python
from multilingual.intent_normalization import IntentPattern, IntentAction

# Add custom pattern
pattern = IntentPattern(
    pattern=r"custom\s+command\s+(.+)",
    action=IntentAction.CUSTOM_ACTION,
    parameter_groups={"target": 1}
)

normalizer.add_custom_pattern("en", pattern)
```

## License

This multilingual understanding system is part of the GURU Personal Assistant project and follows the same licensing terms.

## Security

For security issues related to multilingual processing, please follow the GURU security reporting guidelines. The multilingual system maintains the same security standards as the core GURU system.