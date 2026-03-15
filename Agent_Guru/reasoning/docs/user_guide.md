# Agent Guru Reasoning Engine - User Guide

## Overview

The Agent Guru Reasoning Engine is a production-grade AI assistant that understands natural language, executes tasks, and maintains conversational context. This guide covers common usage scenarios, configuration, and troubleshooting.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Common Scenarios](#common-scenarios)
3. [Multi-Turn Conversations](#multi-turn-conversations)
4. [Async Tasks](#async-tasks)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Quick Start

```python
import requests

API_BASE = "http://localhost:8000"
API_KEY = "your-api-key"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def ask(text: str, user_id: str, conversation_id: str = None) -> dict:
    payload = {"text": text, "user_id": user_id}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    response = requests.post(f"{API_BASE}/v1/process", json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()

# Simple request
result = ask("set a timer for 5 minutes", user_id="user_123")
print(result["response"])  # "Timer set for 5 minutes"
```

### Authentication

All requests require a Bearer token in the `Authorization` header:

```bash
curl -X POST http://localhost:8000/v1/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "hello", "user_id": "user_123"}'
```

---

## Common Scenarios

### Scenario 1: Voice Commands (Timers)

**Use case:** User says "Hey Guru, set a timer for 10 minutes"

```python
result = ask("set a timer for 10 minutes", user_id="user_123", source="voice")
# Response: "Timer set for 10 minutes. I'll notify you when it's done."
```

**What happens internally:**
1. Input normalized from voice source
2. Fast-path router matches `set_timer` intent in <50ms
3. Timer tool executes
4. Response generated and returned

---

### Scenario 2: Weather Queries

**Use case:** "What's the weather in London?"

```python
result = ask("what's the weather in London?", user_id="user_123")
# Response: "It's currently 15°C and cloudy in London."
```

**With follow-up (context preserved):**

```python
# Turn 1
r1 = ask("what's the weather in London?", user_id="user_123")
conv_id = r1["conversation_id"]

# Turn 2 - references previous context
r2 = ask("what about tomorrow?", user_id="user_123", conversation_id=conv_id)
# Response: "Tomorrow in London: 18°C and partly sunny."
```

---

### Scenario 3: Sending Messages

**Use case:** "Send a message to Alice saying I'll be late"

```python
result = ask(
    "send a message to Alice saying I'll be 10 minutes late",
    user_id="user_123"
)
# Response: "Message sent to Alice: 'I'll be 10 minutes late'"
```

**Note:** Messaging is a sensitive action. The safety gate may require confirmation:

```python
result = ask("send an email to all contacts", user_id="user_123")
# Response: "This will send an email to 47 contacts. Please confirm: yes or no."

# Confirm
result2 = ask("yes", user_id="user_123", conversation_id=result["conversation_id"])
# Response: "Email sent to 47 contacts."
```

---

### Scenario 4: Multi-Step Tasks

**Use case:** "Book a meeting with Bob tomorrow at 2pm and send him the agenda"

```python
result = ask(
    "schedule a meeting with bob@example.com tomorrow at 2pm and send him the agenda",
    user_id="user_123"
)
# The engine decomposes this into:
# Step 1: Create calendar event
# Step 2: Send email with agenda
# Response: "Meeting scheduled for tomorrow at 2pm. Agenda sent to bob@example.com."
```

**Checking multi-step progress:**

```python
# For long-running multi-step tasks, a task_id is returned
if result.get("task_id"):
    task_id = result["task_id"]
    
    # Poll for completion
    import time
    while True:
        status = requests.get(
            f"{API_BASE}/v1/tasks/{task_id}",
            headers=HEADERS
        ).json()
        
        if status["status"] in ("completed", "failed"):
            break
        
        print(f"Progress: {status['progress'] * 100:.0f}%")
        time.sleep(1)
    
    print(f"Result: {status['result']}")
```

---

### Scenario 5: Knowledge Queries

**Use case:** "What apps do I use most on Monday mornings?"

```python
result = ask("what apps do I use most on Monday mornings?", user_id="user_123")
# Response: "On Monday mornings you typically use: Slack (45 min), 
#            Gmail (30 min), and Calendar (15 min)."
```

**Temporal queries:**

```python
result = ask("how many timers did I set last week?", user_id="user_123")
# Response: "You set 12 timers last week, mostly for cooking (8) and meetings (4)."
```

---

## Multi-Turn Conversations

The engine maintains context across turns within a conversation. Always pass `conversation_id` to continue a conversation.

```python
# Start conversation
r1 = ask("remind me to call mom", user_id="user_123")
conv_id = r1["conversation_id"]

# Follow-up using context
r2 = ask("make it for 6pm", user_id="user_123", conversation_id=conv_id)
# Engine resolves "it" → "reminder to call mom"
# Response: "Reminder set for 6pm: call mom."

# Another follow-up
r3 = ask("also add a note to buy flowers", user_id="user_123", conversation_id=conv_id)
# Response: "Note added: buy flowers."
```

**Conversation limits:**
- Maximum 20 turns per conversation
- Conversations expire after 1 hour of inactivity
- Start a new conversation by omitting `conversation_id`

---

## Async Tasks

Long-running operations (>300ms expected duration) execute asynchronously.

```python
# Submit async task
result = ask("download and summarize the quarterly report from my email", user_id="user_123")

task_id = result.get("task_id")
if task_id:
    # Poll status
    while True:
        status_resp = requests.get(
            f"{API_BASE}/v1/tasks/{task_id}",
            headers=HEADERS
        ).json()
        
        print(f"Status: {status_resp['status']}, Progress: {status_resp['progress']:.0%}")
        
        if status_resp["status"] == "completed":
            print("Summary:", status_resp["result"]["summary"])
            break
        elif status_resp["status"] == "failed":
            print("Error:", status_resp["error"])
            break
        
        time.sleep(2)
```

**Cancel a task:**

```python
requests.post(
    f"{API_BASE}/v1/tasks/{task_id}/cancel",
    headers=HEADERS
)
```

---

## WebSocket API

For real-time streaming responses, use the WebSocket API:

```javascript
const ws = new WebSocket(
  `ws://localhost:8000/v1/ws?user_id=user_123`,
  [],
  { headers: { Authorization: "Bearer YOUR_API_KEY" } }
);

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "request",
    request_id: "req_001",
    data: { text: "set a timer for 5 minutes" }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  switch (msg.type) {
    case "progress":
      console.log(`Stage: ${msg.data.stage}, Progress: ${msg.data.progress}`);
      break;
    case "response":
      console.log("Response:", msg.data.response);
      break;
    case "error":
      console.error("Error:", msg.error.message);
      break;
    case "ping":
      ws.send(JSON.stringify({ type: "pong" }));
      break;
  }
};
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `LLM_BACKEND` | LLM backend (local/cloud/hybrid) | `hybrid` |
| `MAX_REASONING_STEPS` | Max steps in multi-step tasks | `5` |
| `INTENT_CONFIDENCE_THRESHOLD` | Min confidence for intent acceptance | `0.8` |
| `FAST_PATH_ENABLED` | Enable fast-path rule-based routing | `true` |
| `ASYNC_EXECUTION_THRESHOLD_MS` | Duration threshold for async execution | `300` |
| `MAX_CONVERSATION_TURNS` | Max turns per conversation | `20` |
| `CONVERSATION_TTL_SECONDS` | Conversation expiry time | `3600` |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `OPENAI_API_KEY` | OpenAI API key (for cloud LLM) | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key (for cloud LLM) | Optional |

### LLM Backend Selection

```bash
# Use local Ollama (free, private, requires GPU)
LLM_BACKEND=local

# Use cloud APIs (requires API keys)
LLM_BACKEND=cloud

# Hybrid: local for simple tasks, cloud for complex (recommended)
LLM_BACKEND=hybrid
```

### Sensitive Action Categories

By default, these action categories require user confirmation:

- `file_deletion` - Deleting files
- `financial_transaction` - Payments and transfers
- `system_modification` - System settings changes
- `external_communication` - Emails, SMS, messages
- `smart_home_control` - IoT device control
- `data_export` - Exporting user data

To customize, set `SENSITIVE_CATEGORIES` environment variable:

```bash
SENSITIVE_CATEGORIES=file_deletion,financial_transaction,data_export
```

---

## Troubleshooting

### Issue: "Intent not recognized"

**Symptom:** Response says "I'm not sure what you mean"

**Solutions:**
1. Rephrase the request more clearly
2. Break complex requests into simpler steps
3. Check if the required tool is registered

```python
# Check available tools
result = requests.get(f"{API_BASE}/v1/stats", headers=HEADERS).json()
print("Available tools:", result.get("registered_tools", []))
```

---

### Issue: Slow responses (>2 seconds)

**Symptom:** Requests taking longer than expected

**Diagnosis:**

```python
result = ask("set a timer for 5 minutes", user_id="user_123")
print(f"Total latency: {result['latency_ms']}ms")
print(f"Stage latencies: {result['stage_latencies']}")
print(f"Fast path used: {result['fast_path']}")
```

**Solutions:**
- If `fast_path=False` for simple commands, check intent patterns config
- If LLM stage is slow, switch to `LLM_BACKEND=local` for simple tasks
- Check system resources: `GET /metrics` for CPU/memory usage

---

### Issue: Conversation context lost

**Symptom:** Engine doesn't remember previous turns

**Solutions:**
1. Always pass `conversation_id` in follow-up requests
2. Check conversation hasn't expired (1 hour TTL)
3. Verify `conversation_id` matches the one returned in the first response

```python
# Correct: pass conversation_id
r1 = ask("what's the weather?", user_id="user_123")
r2 = ask("what about tomorrow?", user_id="user_123", conversation_id=r1["conversation_id"])

# Wrong: missing conversation_id starts a new conversation
r2_wrong = ask("what about tomorrow?", user_id="user_123")  # No context!
```

---

### Issue: Safety gate blocking actions

**Symptom:** "This action requires confirmation" for non-sensitive requests

**Solutions:**
1. Confirm the action by responding "yes" in the same conversation
2. Check if the tool is incorrectly marked as sensitive
3. Review `SENSITIVE_CATEGORIES` configuration

---

### Issue: Rate limit exceeded

**Symptom:** HTTP 429 response

**Solutions:**
1. Implement exponential backoff in your client
2. Cache responses for identical requests
3. Upgrade API tier if consistently hitting limits

```python
import time

def ask_with_backoff(text, user_id, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(
            f"{API_BASE}/v1/process",
            json={"text": text, "user_id": user_id},
            headers=HEADERS
        )
        if response.status_code == 429:
            wait = 2 ** attempt
            print(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise Exception("Max retries exceeded")
```

---

## Performance Tips

1. **Use fast-path commands** - Common commands (timers, weather, music) are processed in <50ms via the rule-based fast router.

2. **Reuse conversation IDs** - Maintaining conversation context avoids re-establishing state on each request.

3. **Batch independent requests** - Use the WebSocket API to send multiple requests concurrently.

4. **Cache deterministic responses** - Weather, time, and factual queries can be cached client-side for short periods.

5. **Use voice source for voice input** - Setting `source=voice` enables voice-optimized response formatting.

---

## Support

- **API Reference:** [api_reference.md](./api_reference.md)
- **Deployment Guide:** [deployment_guide.md](./deployment_guide.md)
- **Operations Runbook:** [operations_runbook.md](./operations_runbook.md)
- **GitHub Issues:** https://github.com/agent-guru/reasoning-engine/issues
- **Email:** support@agent-guru.com
