# LLM Runtime and Provider Switching - Production Documentation

## System Overview

The GURU AI Runtime System implements a production-grade, zero-compromise multi-provider LLM routing architecture that enables runtime switching between local models (via Ollama) and cloud APIs (Gemini/OpenAI) while maintaining strict security boundaries and authority controls.

### Why Multiple Models Exist

**Architectural Principle**: Models are replaceable. Authority is sacred. Execution is earned.

The system uses multiple models for different responsibilities to enforce security boundaries and optimize performance:

1. **Intent Extraction**: Converts natural language to structured intent (Local: `qwen2.5:7b-instruct`)
2. **Intent Structuring**: Validates and formats intent for execution (Local: `mistral:7b-instruct`)  
3. **Deep Reasoning**: Complex analysis tasks (Disabled by default, requires ARMED authority)
4. **Language Help**: Conversational assistance (Local: `qwen2.5:7b-instruct`)

### Why Models Are Isolated

**CRITICAL SECURITY INVARIANTS (NON-NEGOTIABLE)**:
- NO MODEL may directly control keyboard, mouse, filesystem, or OS
- NO LLM may execute actions
- ALL execution passes through Authority State Machine
- ALL failures MUST fail closed (LOCKED_LISTEN_ONLY)

Each model operates in a strict sandbox with defined responsibilities. No model can bypass the authority system or execute actions directly.

## Local vs API Comparison

### Local Models (Ollama)

**Advantages**:
- Complete privacy (no data leaves machine)
- No network dependency
- No API costs
- Unlimited usage
- No rate limits
- Works offline

**Requirements**:
- Ollama service running on `localhost:11434`
- Downloaded models (2-14GB each)
- Sufficient RAM (8GB+ recommended)
- CPU/GPU for inference

**Security**: Maximum privacy, local-only operation

### API Providers (OpenAI/Gemini)

**Advantages**:
- Latest model capabilities
- No local resource requirements
- Consistent performance
- Advanced reasoning capabilities

**Security Implications**:
- Data sent to external servers
- Requires API keys
- Network dependency
- Rate limits apply
- Costs per usage

**MANDATORY SECURITY CONTROLS**:
- Manual confirmation required
- Authority ARMED state required
- API keys loaded from environment only
- Never logged or stored in code
- Complete audit trail

## How to Switch Providers

### UI Steps (Production Interface)

1. **Access Provider Settings**:
   - Open GURU settings panel
   - Navigate to "Language Models" section
   - Select "Provider Configuration"

2. **Switch Task Provider**:
   - Select task type (Intent Extraction, Intent Structuring, etc.)
   - Choose new provider (Ollama, OpenAI, Gemini)
   - Select model from available list
   - Confirm security requirements

3. **API Provider Activation**:
   - Requires manual confirmation dialog
   - Authority state must be ARMED
   - API key must be configured in environment
   - Audit log entry created

### Config File Steps

**Configuration Location**: `~/.guru/config/llm_config.json`

**Example Configuration**:
```json
{
  "mode": "hybrid",
  "default_provider": "ollama",
  "cloud_disabled_completely": false,
  "tasks": {
    "intent_extraction": {
      "provider": "ollama",
      "model": "qwen2.5:7b-instruct",
      "enabled": true,
      "security_mode": "local_only",
      "requires_authority_level": "LISTEN_ONLY"
    },
    "intent_structuring": {
      "provider": "ollama", 
      "model": "mistral:7b-instruct",
      "enabled": true,
      "security_mode": "local_only",
      "requires_authority_level": "LISTEN_ONLY"
    },
    "deep_reasoning": {
      "provider": "disabled",
      "model": "",
      "enabled": false,
      "security_mode": "api_armed_authority",
      "requires_authority_level": "ARMED"
    }
  },
  "providers": {
    "ollama": {
      "provider_type": "ollama",
      "enabled": true,
      "base_url": "http://localhost:11434",
      "models": ["qwen2.5:7b-instruct", "qwen2.5:14b-instruct", "mistral:7b-instruct"],
      "default_model": "qwen2.5:7b-instruct",
      "security_mode": "local_only"
    },
    "openai": {
      "provider_type": "openai",
      "enabled": false,
      "api_key_env_var": "OPENAI_API_KEY",
      "models": ["gpt-4", "gpt-3.5-turbo"],
      "default_model": "gpt-3.5-turbo",
      "require_manual_confirmation": true,
      "require_armed_authority": true,
      "security_mode": "api_armed_authority"
    },
    "gemini": {
      "provider_type": "gemini", 
      "enabled": false,
      "api_key_env_var": "GEMINI_API_KEY",
      "models": ["gemini-pro", "gemini-1.5-pro"],
      "default_model": "gemini-pro",
      "require_manual_confirmation": true,
      "require_armed_authority": true,
      "security_mode": "api_armed_authority"
    }
  }
}
```

**To Switch Providers**:
1. Edit the `tasks` section
2. Change `provider` field to desired provider
3. Update `model` field to available model
4. Ensure security requirements are met
5. Restart GURU or use runtime switching API

## Where to Add API Keys

**CRITICAL SECURITY RULE**: API keys are NEVER stored in code or configuration files.

### Environment Variable Names

**OpenAI**: `OPENAI_API_KEY`
**Gemini**: `GEMINI_API_KEY`

### OS-Specific Instructions

#### Windows

**Method 1: System Environment Variables**
1. Open System Properties → Advanced → Environment Variables
2. Add new User Variable:
   - Name: `OPENAI_API_KEY`
   - Value: `your-api-key-here`
3. Restart GURU application

**Method 2: PowerShell (Session Only)**
```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
$env:GEMINI_API_KEY = "your-api-key-here"
```

**Method 3: Command Prompt (Session Only)**
```cmd
set OPENAI_API_KEY=your-api-key-here
set GEMINI_API_KEY=your-api-key-here
```

#### macOS/Linux

**Method 1: Shell Profile (Persistent)**
```bash
# Add to ~/.bashrc, ~/.zshrc, or ~/.profile
export OPENAI_API_KEY="your-api-key-here"
export GEMINI_API_KEY="your-api-key-here"
```

**Method 2: Session Only**
```bash
export OPENAI_API_KEY="your-api-key-here"
export GEMINI_API_KEY="your-api-key-here"
```

**Method 3: .env File (Application Directory)**
```bash
# Create .env file in GURU directory
OPENAI_API_KEY=your-api-key-here
GEMINI_API_KEY=your-api-key-here
```

### API Key Security Best Practices

1. **Never commit API keys to version control**
2. **Use environment variables only**
3. **Rotate keys regularly**
4. **Monitor API usage for anomalies**
5. **Use least-privilege API keys when possible**

## Failure Behavior

### What Happens When API Fails

**Failure Modes**:
- Network connectivity issues
- API rate limits exceeded
- Authentication failures
- Service unavailable

**System Response**:
1. **Immediate Fallback**: Switch to configured fallback provider (if enabled)
2. **Fail Closed**: If no fallback, system enters LOCKED_LISTEN_ONLY state
3. **Audit Logging**: All failures logged with metadata (no content)
4. **User Notification**: Clear error message displayed
5. **Graceful Degradation**: Core functionality remains available

**Example Failure Sequence**:
```
1. OpenAI API call fails (rate limit)
2. System attempts Ollama fallback
3. If Ollama unavailable, fail closed
4. User sees: "Language processing temporarily unavailable"
5. System continues with basic functionality
6. Audit log: "model_call_failure" with metadata
```

### What Happens When Local Model Fails

**Failure Modes**:
- Ollama service not running
- Model not downloaded
- Insufficient system resources
- Model corruption

**System Response**:
1. **Service Check**: Verify Ollama service status
2. **Model Validation**: Check if required models are available
3. **Resource Check**: Validate system has sufficient RAM/CPU
4. **Fallback**: Use API providers if configured and authorized
5. **Fail Closed**: If no alternatives, enter safe mode

**Recovery Actions**:
- Automatic Ollama service restart attempt
- Model download suggestions
- Resource optimization recommendations
- Alternative provider suggestions

## How to Disable Cloud Completely

### Configuration Method

**Set in config file**:
```json
{
  "cloud_disabled_completely": true,
  "mode": "local"
}
```

### Runtime Method

**API Call**:
```python
adapter = get_production_adapter()
await adapter.disable_cloud_completely()
```

**UI Method**:
1. Open GURU Settings
2. Navigate to Privacy Settings
3. Enable "Local Only Mode"
4. Confirm "Disable All Cloud Providers"

### Effects of Cloud Disable

**Immediate Changes**:
- All API providers shut down
- API keys cleared from memory
- Tasks reconfigured to local-only
- Network calls to AI services blocked
- Audit log entry created

**Permanent Changes**:
- Configuration updated to local-only
- Cloud provider tasks disabled
- Fallback chains updated
- Security mode enforced

## Audit & Compliance Notes

### What Gets Logged

**Metadata Only (No Content)**:
- Task type and provider used
- Start/end timestamps
- Success/failure status
- Authority level at time of call
- Fallback usage
- Error types (not messages)

**Security Events**:
- Provider switches
- Authority level changes
- API key loading attempts
- Security violations
- Configuration changes

### Compliance Features

**Data Privacy**:
- No prompt content logged
- No model responses logged
- API keys never logged
- Local-first by default

**Audit Trail**:
- Cryptographically signed logs
- Tamper-evident chain
- Complete operation history
- Security event tracking

**Authority Controls**:
- All operations validated
- Authority state enforced
- Manual confirmation required
- Fail-closed security

## Troubleshooting Matrix

### Local Model Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Ollama not running | "Provider ollama not available" | Start Ollama service: `ollama serve` |
| Model not found | "Model qwen2.5:7b-instruct not found" | Download model: `ollama pull qwen2.5:7b-instruct` |
| Insufficient RAM | Slow responses, timeouts | Use smaller model or increase RAM |
| Port conflict | Connection refused | Check port 11434, restart Ollama |

### API Provider Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Missing API key | "Authentication failed" | Set environment variable correctly |
| Invalid API key | "API key invalid" | Verify key in provider dashboard |
| Rate limit | "Rate limit exceeded" | Wait or upgrade API plan |
| Network issues | "Connection timeout" | Check internet connectivity |

### Authority Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Insufficient authority | "Security validation failed" | Authenticate to ARMED state |
| Manual confirmation | "Requires manual confirmation" | Confirm in UI dialog |
| Cloud disabled | "Cloud providers disabled" | Enable in privacy settings |

### Configuration Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Invalid config | "Configuration validation failed" | Check JSON syntax |
| Missing task config | "Task not configured" | Add task to config file |
| Provider mismatch | "Provider not available" | Verify provider is enabled |

### Performance Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Slow responses | High latency | Use faster model or API |
| Memory usage | System slowdown | Reduce concurrent requests |
| CPU usage | High CPU load | Use GPU acceleration if available |

## Advanced Configuration

### Custom Model Routing

```json
{
  "tasks": {
    "intent_extraction": {
      "provider": "ollama",
      "model": "custom-model:latest",
      "fallback_provider": "openai",
      "fallback_model": "gpt-3.5-turbo"
    }
  }
}
```

### Security Policies

```json
{
  "providers": {
    "openai": {
      "require_manual_confirmation": true,
      "require_armed_authority": true,
      "max_concurrent_requests": 1,
      "timeout_seconds": 10
    }
  }
}
```

### Performance Tuning

```json
{
  "tasks": {
    "intent_extraction": {
      "timeout_seconds": 5,
      "max_retries": 1
    }
  }
}
```

## Security Architecture Summary

**Defense in Depth**:
1. **Model Isolation**: Each model operates in defined boundaries
2. **Authority Validation**: All operations require appropriate authority level
3. **API Key Security**: Environment-only loading, never logged
4. **Audit Logging**: Complete metadata trail, no content logging
5. **Fail Closed**: System fails to safe state on errors
6. **Manual Controls**: API activation requires explicit confirmation
7. **Local First**: Privacy-preserving local models by default

**Zero Trust Principles**:
- Never trust model outputs directly
- Always validate through authority system
- Assume network and API failures
- Verify all security boundaries
- Audit all operations

This architecture ensures that while models are replaceable and can be switched at runtime, the core security principles remain inviolate: Authority is sacred, and execution is earned through proper validation and authorization.