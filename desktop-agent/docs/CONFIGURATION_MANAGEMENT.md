# Configuration Management System

## Overview

GURU uses a production-grade hierarchical configuration management system with three levels of precedence:

1. **System Defaults** (lowest priority) - Built-in defaults embedded in code
2. **User Configuration** (medium priority) - `%USERPROFILE%\.guru\config.json`
3. **Workspace Configuration** (highest priority) - `<workspace>\.guru\config.json`

Configuration is automatically merged with higher levels overriding lower levels.

## Features

- **Hierarchical Configuration**: Three-tier system with proper precedence
- **Automatic Merging**: Configurations are merged automatically with deep merge support
- **Secure Storage**: Sensitive data (API keys, biometric data) encrypted at rest
- **Configuration Validation**: All configurations validated before applying
- **Atomic Updates**: Updates are atomic with automatic rollback on failure
- **Backup Support**: Automatic backups before updates, with restore capability
- **Environment Variables**: Override configuration via `GURU_*` environment variables
- **Ollama Auto-Detection**: Automatic detection and configuration of Ollama models

## Configuration Hierarchy

### System Defaults

Built-in defaults that provide sensible configuration for all users. Cannot be modified directly.

### User Configuration

User-level configuration stored in `%USERPROFILE%\.guru\config.json`. Applies to all GURU instances for the user.

**Location**: `C:\Users\<username>\.guru\config.json`

### Workspace Configuration

Workspace-specific configuration stored in `<workspace>\.guru\config.json`. Overrides user configuration for that workspace only.

**Location**: `<workspace>\.guru\config.json`

### Environment Variables

Environment variables with `GURU_` prefix override all configuration levels.

**Format**: `GURU_SECTION_KEY=value`

**Examples**:
```bash
# Override wake word
set GURU_VOICE_WAKE_WORD="hey assistant"

# Override LLM mode
set GURU_LLM_MODE="api"

# Override authority timeout
set GURU_SECURITY_AUTHORITY_TIMEOUT_MINUTES=30
```

## Configuration Structure

```json
{
  "system": {
    "platform": "auto",
    "version": "1.0.0",
    "log_level": "INFO",
    "data_dir": "C:\\Users\\<user>\\.guru\\data",
    "enable_telemetry": false,
    "enable_crash_reporting": false
  },
  
  "voice": {
    "wake_word": "hey guru",
    "language": "en",
    "enable_wake_word": true,
    "enable_continuous_listening": true,
    "silence_timeout_seconds": 5,
    "energy_threshold": 300
  },
  
  "security": {
    "authority_timeout_minutes": 15,
    "max_failed_auth_attempts": 3,
    "lockout_duration_minutes": 5,
    "enable_biometric_auth": true,
    "enable_intrusion_detection": true,
    "enable_audit_logging": true
  },
  
  "llm": {
    "mode": "local",
    "default_provider": "ollama",
    "enable_fallback": true,
    "enable_caching": true,
    "timeout_seconds": 10,
    "providers": {
      "ollama": {
        "enabled": true,
        "base_url": "http://localhost:11434",
        "models": [],
        "default_model": null
      }
    }
  },
  
  "tts": {
    "enabled": true,
    "volume": 100,
    "rate": 0,
    "enable_priority_queue": true,
    "enable_volume_bypass": true
  },
  
  "memory": {
    "enabled": true,
    "encryption_enabled": true,
    "retention_days": 90,
    "enable_vector_search": true
  },
  
  "skills": {
    "enabled": true,
    "skills_dir": "C:\\Users\\<user>\\.guru\\skills",
    "enable_sandbox": true,
    "max_execution_time_seconds": 30
  },
  
  "ui": {
    "enable_avatar": true,
    "enable_tray_icon": true,
    "enable_notifications": true,
    "theme": "dark"
  }
}
```

## CLI Usage

### View Configuration

```bash
# View full configuration
python manage_config.py view

# View specific section
python manage_config.py view --section voice
python manage_config.py view --section security
```

### Set Configuration Value

```bash
# Set user-level configuration
python manage_config.py set voice.wake_word "hello guru"
python manage_config.py set security.authority_timeout_minutes 30
python manage_config.py set llm.mode "api"

# Set workspace-level configuration
python manage_config.py set voice.wake_word "hey assistant" --level workspace
```

### Reset Configuration

```bash
# Reset user configuration (with confirmation)
python manage_config.py reset

# Reset user configuration (no confirmation)
python manage_config.py reset --yes

# Reset workspace configuration
python manage_config.py reset --level workspace --yes

# Reset without creating backup
python manage_config.py reset --no-backup --yes
```

### Export Configuration

```bash
# Export configuration (sensitive data redacted)
python manage_config.py export config_backup.json

# Export with sensitive data (encrypted)
python manage_config.py export config_full.json --include-sensitive
```

### Import Configuration

```bash
# Import to user level (with validation)
python manage_config.py import config_backup.json

# Import to workspace level
python manage_config.py import config_backup.json --level workspace

# Import without validation (not recommended)
python manage_config.py import config_backup.json --no-validate
```

### List Backups

```bash
# List all backups
python manage_config.py backups

# List user-level backups only
python manage_config.py backups --level user

# List workspace-level backups only
python manage_config.py backups --level workspace
```

### Restore Backup

```bash
# Restore backup (with confirmation)
python manage_config.py restore config_user_2026-01-15T10-30-00.json

# Restore backup (no confirmation)
python manage_config.py restore config_user_2026-01-15T10-30-00.json --yes

# Restore to workspace level
python manage_config.py restore config_workspace_2026-01-15T10-30-00.json --level workspace --yes
```

### Auto-Detect Ollama Models

```bash
# Automatically detect Ollama models and generate configuration
python manage_config.py ollama

# Or use the dedicated script
python create_llm_config.py
```

## Programmatic Usage

### Python API

```python
from pathlib import Path
from config.configuration_manager import (
    ConfigurationManager,
    ConfigurationLevel,
    get_configuration_manager
)

# Get configuration manager instance
config_mgr = get_configuration_manager()

# Load configuration
config = config_mgr.load_configuration()

# Get specific value
wake_word = config_mgr.get_configuration_value("voice.wake_word")
timeout = config_mgr.get_configuration_value("security.authority_timeout_minutes", default=15)

# Set configuration value
config_mgr.set_configuration_value(
    "voice.wake_word",
    "hello guru",
    level=ConfigurationLevel.USER
)

# Update multiple values
config_mgr.update_configuration(
    {
        "voice": {
            "wake_word": "hello guru",
            "language": "en"
        },
        "security": {
            "authority_timeout_minutes": 30
        }
    },
    level=ConfigurationLevel.USER
)

# Reset configuration
config_mgr.reset_configuration(ConfigurationLevel.USER)

# Export configuration
config_mgr.export_configuration(Path("backup.json"))

# Import configuration
config_mgr.import_configuration(Path("backup.json"), ConfigurationLevel.USER)

# List backups
backups = config_mgr.list_backups()
for backup_file, timestamp in backups:
    print(f"{backup_file.name}: {timestamp}")

# Restore backup
config_mgr.restore_backup(backup_file, ConfigurationLevel.USER)
```

### Ollama Auto-Detection

```python
from config.ollama_detector import OllamaDetector, auto_configure_ollama

# Simple auto-configuration
success, message = auto_configure_ollama()
if success:
    print("Ollama configured successfully")
else:
    print(f"Configuration failed: {message}")

# Advanced usage
detector = OllamaDetector()

# Check if Ollama is available
if detector.is_ollama_available():
    # Detect models
    models = detector.detect_models()
    print(f"Found {len(models)} models:")
    for model in models:
        print(f"  - {model.name} ({model.parameter_count})")
    
    # Generate configuration
    config = detector.generate_llm_config(models)
    
    # Save configuration
    config_file = detector.save_llm_config(config)
    print(f"Configuration saved to {config_file}")
```

## Security

### Encryption

Sensitive data is automatically encrypted at rest using Fernet (AES-256-GCM):

- API keys (OpenAI, Gemini)
- Biometric data (fingerprint, face)
- Any field marked as sensitive

Encryption keys are stored in:
- User level: `%USERPROFILE%\.guru\config_encryption.key`
- Workspace level: `<workspace>\.guru\config_encryption.key`

### File Permissions

Configuration files have restricted permissions (best effort on Windows):
- Only the current user can read/write configuration files
- Encryption keys have even stricter permissions

### Validation

All configuration updates are validated before applying:
- Required fields must be present
- Values must be of correct type
- Ranges must be within acceptable limits
- Cross-field dependencies are checked

Invalid configurations are rejected and previous configuration is preserved.

## Backup and Recovery

### Automatic Backups

Backups are automatically created before:
- Configuration updates
- Configuration resets
- Configuration imports

Backups are stored in `%USERPROFILE%\.guru\backups\`

### Backup Retention

- Last 10 backups are kept per configuration level
- Older backups are automatically deleted
- Manual backups (via export) are never deleted

### Recovery

If configuration becomes corrupted:

1. List available backups:
   ```bash
   python manage_config.py backups
   ```

2. Restore most recent backup:
   ```bash
   python manage_config.py restore <backup-file> --yes
   ```

3. If all backups are corrupted, reset to defaults:
   ```bash
   python manage_config.py reset --yes
   ```

## Ollama Model Auto-Detection

### Overview

GURU can automatically detect installed Ollama models and generate optimized configuration.

### Detection Strategy

1. Query Ollama API for installed models
2. Analyze model names and sizes
3. Select appropriate models for each task:
   - **Conversation**: Fast, general-purpose (7B)
   - **Intent Extraction**: Fast, instruction-following (7B)
   - **Intent Structuring**: Fast, structured output (7B)
   - **Deep Reasoning**: Slow, high-quality (14B+)
4. Generate optimized configuration with appropriate timeouts

### Model Selection Criteria

**Conversation**:
- Preference: qwen2.5:7b-instruct > mistral:7b-instruct > llama2:7b
- Timeout: 30 seconds

**Intent Extraction**:
- Preference: qwen2.5:7b-instruct > mistral:7b-instruct > llama2:7b
- Timeout: 30 seconds

**Intent Structuring**:
- Preference: mistral:7b-instruct > qwen2.5:7b-instruct > llama2:7b
- Timeout: 30 seconds

**Deep Reasoning** (optional):
- Preference: qwen2.5:14b-instruct > mixtral:8x7b > llama2:13b
- Timeout: 180 seconds (3 minutes)

### Usage

```bash
# Auto-detect and configure
python create_llm_config.py

# Or via CLI
python manage_config.py ollama
```

### Recommended Models

For optimal performance, install these models:

```bash
# Required (fast models for real-time interaction)
ollama pull qwen2.5:7b-instruct
ollama pull mistral:7b-instruct

# Optional (large model for deep reasoning)
ollama pull qwen2.5:14b-instruct
```

## Troubleshooting

### Configuration Not Loading

1. Check file permissions on configuration directory
2. Check for syntax errors in JSON files
3. Check encryption key is present and readable
4. Reset configuration to defaults

### Ollama Detection Fails

1. Ensure Ollama is running: `ollama list`
2. Check Ollama is accessible: `curl http://localhost:11434/api/tags`
3. Install models if none found: `ollama pull qwen2.5:7b-instruct`

### Configuration Validation Fails

1. Check required fields are present
2. Check values are of correct type
3. Check for typos in configuration keys
4. Export current configuration to see structure

### Backup Restore Fails

1. Verify backup file exists and is readable
2. Check backup file is valid JSON
3. Try importing backup instead of restoring
4. Reset to defaults if all backups are corrupted

## Best Practices

1. **Use Workspace Configuration for Project-Specific Settings**
   - Keep user configuration for global preferences
   - Use workspace configuration for project-specific overrides

2. **Always Create Backups Before Major Changes**
   - Export configuration before making significant changes
   - Keep backups in version control for team projects

3. **Use Environment Variables for Temporary Overrides**
   - Don't modify configuration files for temporary changes
   - Use environment variables instead

4. **Validate Configuration After Changes**
   - Always test configuration after manual edits
   - Use `manage_config.py view` to verify changes

5. **Keep Sensitive Data Encrypted**
   - Never disable encryption for production use
   - Don't commit encryption keys to version control

6. **Regular Configuration Audits**
   - Periodically review configuration for unused settings
   - Remove deprecated configuration keys
   - Update to latest configuration schema

## Migration

When upgrading GURU versions, configuration may need migration:

1. Export current configuration:
   ```bash
   python manage_config.py export config_backup.json
   ```

2. Upgrade GURU

3. Import configuration (validation will migrate if needed):
   ```bash
   python manage_config.py import config_backup.json
   ```

4. Verify configuration:
   ```bash
   python manage_config.py view
   ```

## Support

For configuration issues:

1. Check this documentation
2. Check GURU logs in `%USERPROFILE%\.guru\logs\`
3. Reset configuration to defaults
4. Report issue with configuration export (sensitive data redacted)
