# LLM Runtime and Provider Switching

## System Overview

AGENT_GURU implements a production-grade multi-provider LLM runtime system with strict architectural separation between intelligence and execution. This document describes the technical architecture, security model, and operational procedures.

### Core Principles

1. **Models are replaceable. Authority is sacred. Execution is earned.**
2. No LLM directly controls keyboard, mouse, filesystem, or OS operations
3. All execution passes through the Authority State Machine
4. All failures fail closed (LOCKED_LISTEN_ONLY state)
5. API keys are never logged, never stored in code
6. All operations are audited with metadata only (no content logging)

### Why Multiple Models Exist

The system uses multiple models for different responsibilities to optimize for:

- **Performance**: Fast models (≤ 200ms) for simple queries
- **Quality**: Larger models for complex reasoning
- **Reliability**: Fallback chains for high availability
- **Cost**: Local models for privacy-sensitive operations
- **Flexibility**: Runtime switching without system restart

### Why Models Are Isolated

Each model serves a specific, non-overlapping function:

| Responsibility | Model Type | Rationale |
|---|---|---|
| Speech-to-Text | Local only | Privacy, latency, offline operation |
| Language Detection | Local only | Deterministic, no external dependency |
| Intent Extraction | Local or API | Configurable based on requirements |
| Intent Structuring | Local or API | JSON generation, validation |
| Deep Reasoning | Local or API | Optional, non-executing analysis |
| Language Help | Local or API | Non-executing assistance |
| Validation | Rules Engine | Deterministic, no LLM involvement |
| Authority Decisions | State Machine | Deterministic, no LLM involvement |
| Execution | Deterministic Code | No LLM involvement |

## Architecture

### Layer Separation (Mandatory)

```
Audio Input
  ↓
Speech-to-Text (Local)
  ↓
Language Detection (Local, Deterministic)
  ↓
Intent Extraction (LLM – Local or API)
  ↓
Intent Structuring (LLM – Local or API)
  ↓
Rule Validator (NO LLM)
  ↓
Authority State Machine
  ↓
Execution Engine (Keyboard / Mouse / Skills)
  ↓
Audit Logger (Cryptographically Signed)
```

No shortcuts. No merged layers. No shared responsibilities.

### Provider Types

#### Local (Ollama)
- Runs entirely offline
- No external network calls
- Full privacy control
- Requires local compute resources
- Models: mistral:7b-instruct, qwen2.5:7b-instruct, qwen2.5:14b-instruct

#### OpenAI API
- Cloud-based inference
- Requires API key and internet connection
- Subject to OpenAI terms of service
- Pay-per-use pricing
- Models: gpt-3.5-turbo, gpt-4, gpt-4-turbo

#### Google Gemini API
- Cloud-based inference
- Requires API key and internet connection
- Subject to Google terms of service
- Free tier available with limits
- Models: gemini-pro, gemini-pro-vision

## Local vs API Comparison

### Security Implications

| Aspect | Local | API |
|---|---|---|
| Data Privacy | Complete | Shared with provider |
| Network Dependency | None | Required |
| API Key Management | Not needed | Required, sensitive |
| Audit Trail | Local only | Local + provider logs |
| Offline Operation | Full | None |
| Regulatory Compliance | Easier | Complex |

### Performance Implications

| Aspect | Local | API |
|---|---|---|
| Latency | 50-500ms | 200-2000ms |
| Throughput | Hardware limited | Rate limited |
| Cost | Hardware + electricity | Per-token pricing |
| Scalability | Fixed capacity | Elastic |
| Reliability | Local hardware | Network + service |

### Recommendation Matrix

| Use Case | Recommended Provider |
|---|---|
| Privacy-sensitive operations | Local only |
| Offline environments | Local only |
| High-volume operations | Local (cost) |
| Complex reasoning | API (quality) |
| Rapid prototyping | API (convenience) |
| Production deployment | Hybrid (reliability) |

## Configuration

### Configuration File Structure

Location: `.kiro/llm_config.yaml`

```yaml
llm:
  mode: local  # local | api | hybrid
  default_provider: ollama
  require_user_confirmation_for_api: true
  log_metadata_only: true
  
  tasks:
    intent_extraction:
      provider: ollama
      model: qwen2.5:7b-instruct
      fallback_provider: null
      fallback_model: null
    
    intent_structuring:
      provider: ollama
      model: mistral:7b-instruct
      fallback_provider: null
      fallback_model: null
    
    deep_reasoning:
      provider: disabled
      model: ""
      fallback_provider: null
      fallback_model: null
    
    language_help:
      provider: ollama
      model: qwen2.5:14b-instruct
      fallback_provider: null
      fallback_model: null
```

### Configuration Modes

#### Local Only
```yaml
llm:
  mode: local
  default_provider: ollama
```

All tasks use local Ollama models. No API calls are made.

#### API Only
```yaml
llm:
  mode: api
  default_provider: openai
  require_user_confirmation_for_api: true
  
  tasks:
    intent_extraction:
      provider: openai
      model: gpt-3.5-turbo
```

All tasks use cloud APIs. Requires API keys and confirmation.

#### Hybrid
```yaml
llm:
  mode: hybrid
  default_provider: ollama
  
  tasks:
    intent_extraction:
      provider: ollama
      model: qwen2.5:7b-instruct
    
    deep_reasoning:
      provider: openai
      model: gpt-4
      fallback_provider: ollama
      fallback_model: qwen2.5:14b-instruct
```

Mix of local and API providers with fallback chains.

## How to Switch Providers

### Method 1: Configuration File

1. Stop AGENT_GURU if running
2. Edit `.kiro/llm_config.yaml`
3. Change `provider` field for desired tasks
4. Save file
5. Restart AGENT_GURU
6. System validates configuration on startup

### Method 2: Runtime Command (Future)

```
GURU> config llm provider intent_extraction openai gpt-3.5-turbo
```

Requires:
- Manual confirmation
- Authority ARMED state
- Audit log entry

### Method 3: UI Panel (Future)

1. Open Settings → LLM Configuration
2. Select task type
3. Choose provider from dropdown
4. Enter model name
5. Configure fallback (optional)
6. Click "Apply" (requires confirmation)
7. System validates and applies changes

## API Key Management

### Where to Add API Keys

API keys are loaded from environment variables only. Never store keys in code or configuration files.

#### Windows

**PowerShell (Session):**
```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:GEMINI_API_KEY = "..."
```

**PowerShell (Permanent):**
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-...', 'User')
[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', '...', 'User')
```

**Command Prompt (Session):**
```cmd
set OPENAI_API_KEY=sk-...
set GEMINI_API_KEY=...
```

**System Environment Variables:**
1. Open System Properties → Advanced → Environment Variables
2. Under "User variables", click "New"
3. Variable name: `OPENAI_API_KEY`
4. Variable value: `sk-...`
5. Click OK
6. Repeat for `GEMINI_API_KEY`

#### Linux / macOS

**Bash (Session):**
```bash
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."
```

**Bash (Permanent):**
Add to `~/.bashrc` or `~/.bash_profile`:
```bash
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."
```

**Zsh (Permanent):**
Add to `~/.zshrc`:
```zsh
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."
```

### API Key Security

1. **Never commit keys to version control**
2. **Never log keys** (system enforces this)
3. **Rotate keys regularly**
4. **Use separate keys for development and production**
5. **Revoke keys immediately if compromised**
6. **Use environment-specific key management** (e.g., AWS Secrets Manager, Azure Key Vault)

### Obtaining API Keys

#### OpenAI
1. Visit https://platform.openai.com/api-keys
2. Sign in or create account
3. Click "Create new secret key"
4. Copy key immediately (shown once)
5. Set environment variable

#### Google Gemini
1. Visit https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API key"
4. Copy key
5. Set environment variable

## Failure Behavior

### API Failure Scenarios

| Scenario | Behavior | Fallback |
|---|---|---|
| API key missing | Fail at startup | Use local if configured |
| API key invalid | Fail at startup | Use local if configured |
| Network unavailable | Fail request | Use fallback provider |
| Rate limit exceeded | Fail request | Use fallback provider |
| API service down | Fail request | Use fallback provider |
| Timeout | Fail request | Use fallback provider |

### Local Model Failure Scenarios

| Scenario | Behavior | Fallback |
|---|---|---|
| Ollama not running | Fail at startup | None (hard requirement) |
| Model not pulled | Fail at startup | None (hard requirement) |
| Out of memory | Fail request | Use smaller model if configured |
| Model crash | Fail request | Restart Ollama, retry |

### Failure Handling Rules

1. **All failures fail closed**: System returns to LOCKED_LISTEN_ONLY state
2. **No silent fallbacks**: All fallback usage is logged and reported
3. **No partial execution**: LLM failure never executes partial actions
4. **Explicit error messages**: User is informed of failure reason
5. **Audit trail**: All failures are logged with metadata

### Recovery Procedures

#### API Provider Failure
1. Check network connectivity
2. Verify API key is set correctly
3. Check provider status page
4. Switch to local provider if urgent
5. Review audit log for patterns

#### Local Provider Failure
1. Verify Ollama is running: `ollama serve`
2. Check model is pulled: `ollama list`
3. Pull missing model: `ollama pull <model>`
4. Check system resources (RAM, disk)
5. Restart Ollama service

## How to Disable Cloud Entirely

### Method 1: Configuration File

Set all tasks to use local provider:

```yaml
llm:
  mode: local
  default_provider: ollama
  require_user_confirmation_for_api: true
  
  tasks:
    intent_extraction:
      provider: ollama
      model: qwen2.5:7b-instruct
    
    intent_structuring:
      provider: ollama
      model: mistral:7b-instruct
    
    deep_reasoning:
      provider: disabled
      model: ""
    
    language_help:
      provider: ollama
      model: qwen2.5:14b-instruct
```

### Method 2: Remove API Keys

Unset environment variables:

**Windows PowerShell:**
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $null, 'User')
[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $null, 'User')
```

**Linux / macOS:**
```bash
unset OPENAI_API_KEY
unset GEMINI_API_KEY
```

Remove from shell configuration files (`~/.bashrc`, `~/.zshrc`, etc.)

### Method 3: Network Isolation

For maximum security, run AGENT_GURU in a network-isolated environment:

1. Disable network adapter
2. Use firewall rules to block outbound HTTPS
3. Run in air-gapped environment
4. Use local models only

### Verification

Confirm cloud is disabled:

```
GURU> status
```

Output should show:
```
Mode: Local Only
API Providers: Disabled
Network Calls: None
```

## Audit & Compliance Notes

### Audit Log Location

Default: `.kiro/logs/llm_audit.jsonl`

### Audit Log Format

Each line is a JSON object:

```json
{
  "timestamp": "2026-02-12T10:30:45.123Z",
  "task_type": "intent_extraction",
  "provider": "ollama",
  "model_name": "qwen2.5:7b-instruct",
  "success": true,
  "latency_ms": 145,
  "fallback_used": false,
  "error_type": null
}
```

### What Is Logged

- Timestamp (UTC)
- Task type
- Provider used
- Model name
- Success/failure status
- Latency in milliseconds
- Whether fallback was used
- Error type (if failed)

### What Is NOT Logged

- User input content
- Model output content
- API keys
- Personal information
- Conversation history

### Compliance Considerations

#### GDPR
- No personal data in audit logs
- User can request audit log deletion
- Local-only mode for EU users

#### HIPAA
- Use local-only mode for healthcare data
- No PHI sent to cloud providers
- Audit logs for compliance reporting

#### SOC 2
- Comprehensive audit trail
- Access control enforcement
- Cryptographic verification (future)

### Audit Log Analysis

View statistics:

```
GURU> audit stats
```

Output:
```
Total Operations:     1,234
Successful:           1,198 (97.1%)
Failed:               36 (2.9%)
Fallback Used:        12 (1.0%)
Average Latency:      187ms
```

Export audit log:

```bash
# Copy to secure location
cp .kiro/logs/llm_audit.jsonl /secure/backup/
```

## Troubleshooting Matrix

| Problem | Symptoms | Solution |
|---|---|---|
| "Ollama not available" | Startup failure | Run `ollama serve` |
| "Model not found" | Startup failure | Run `ollama pull <model>` |
| "API key missing" | Startup failure | Set environment variable |
| "API key invalid" | Startup failure | Check key, regenerate if needed |
| "Network timeout" | Request failure | Check internet, switch to local |
| "Rate limit exceeded" | Request failure | Wait, or switch to local |
| "Out of memory" | Request failure | Close apps, use smaller model |
| "Slow responses" | High latency | Use faster model, check resources |
| "API not confirmed" | Request blocked | Confirm API usage in settings |
| "Provider disabled" | Request blocked | Enable provider in config |

### Debug Mode

Enable verbose logging:

**Windows:**
```powershell
$env:RUST_LOG = "agent_guru=debug"
```

**Linux / macOS:**
```bash
export RUST_LOG=agent_guru=debug
```

Run AGENT_GURU and check output for detailed error messages.

### Support Resources

- Ollama Documentation: https://ollama.ai/docs
- OpenAI API Reference: https://platform.openai.com/docs
- Gemini API Reference: https://ai.google.dev/docs
- AGENT_GURU Issues: [Repository URL]

## Security Checklist

Before deploying to production:

- [ ] API keys stored in environment variables only
- [ ] API keys not in version control
- [ ] `require_user_confirmation_for_api` enabled
- [ ] `log_metadata_only` enabled
- [ ] Audit log location secured
- [ ] Network isolation configured (if required)
- [ ] Fallback chains tested
- [ ] Failure scenarios tested
- [ ] Audit log rotation configured
- [ ] Key rotation schedule established

## Performance Tuning

### Local Models

- Use smaller models for simple tasks (mistral:7b)
- Use larger models for complex reasoning (qwen2.5:14b)
- Ensure sufficient RAM (8GB minimum, 16GB recommended)
- Use SSD for model storage
- Close unnecessary applications

### API Models

- Use gpt-3.5-turbo for speed
- Use gpt-4 for quality
- Implement request batching (future)
- Monitor rate limits
- Cache responses when appropriate (future)

### Hybrid Strategy

```yaml
tasks:
  intent_extraction:
    provider: ollama  # Fast, local
    model: mistral:7b-instruct
  
  intent_structuring:
    provider: ollama  # Fast, local
    model: mistral:7b-instruct
  
  deep_reasoning:
    provider: openai  # Quality, cloud
    model: gpt-4
    fallback_provider: ollama
    fallback_model: qwen2.5:14b-instruct
  
  language_help:
    provider: ollama  # Privacy, local
    model: qwen2.5:14b-instruct
```

This configuration optimizes for:
- Speed: Local models for frequent operations
- Quality: Cloud models for complex reasoning
- Reliability: Fallback chains for high availability
- Privacy: Local models for sensitive operations

---

**Document Version:** 1.0.0  
**Last Updated:** 2026-02-12  
**Maintained By:** AGENT_GURU Development Team
