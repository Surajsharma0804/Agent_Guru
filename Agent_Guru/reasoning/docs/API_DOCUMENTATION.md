# Core Reasoning Engine - API Documentation

## Overview

The Agent Guru Core Reasoning Engine provides a RESTful API and WebSocket interface for processing user inputs, managing conversations, and executing tasks. This document provides comprehensive API documentation including endpoints, authentication, error handling, and rate limits.

## Table of Contents

1. [Base URL](#base-url)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [WebSocket API](#websocket-api)
5. [Error Codes](#error-codes)
6. [Rate Limits](#rate-limits)
7. [Examples](#examples)
8. [SDKs and Client Libraries](#sdks-and-client-libraries)

## Base URL

### Production
```
https://api.agent-guru.com/v1/reasoning
```

### Staging
```
https://api-staging.agent-guru.com/v1/reasoning
```

### Development
```
http://localhost:8000/v1/reasoning
```

## Authentication

### API Key Authentication

All API requests require authentication using an API key in the `Authorization` header.

**Header Format:**
```
Authorization: Bearer YOUR_API_KEY
```

**Example:**
```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer sk_live_abc123xyz789" \
  -H "Content-Type: application/json" \
  -d '{"input": "set a timer for 5 minutes", "user_id": "user123"}'
```

### JWT Token Authentication

For user-specific operations, JWT tokens can be used.

**Header Format:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Payload:**
```json
{
  "user_id": "user123",
  "exp": 1709251200,
  "iat": 1709164800,
  "scopes": ["reasoning:read", "reasoning:write"]
}
```

### Obtaining API Keys

1. Sign up at https://console.agent-guru.com
2. Navigate to API Keys section
3. Create new API key
4. Copy and securely store the key

**Security Best Practices:**
- Never commit API keys to version control
- Rotate keys every 90 days
- Use environment variables for key storage
- Implement key rotation without downtime

## API Endpoints

### 1. Process Request

Process a user input and return a response.

**Endpoint:** `POST /process`

**Request Body:**

```json
{
  "input": "string (required) - User input text",
  "user_id": "string (required) - Unique user identifier",
  "source": "string (optional) - Input source: 'text', 'voice', 'system_event'. Default: 'text'",
  "conversation_id": "string (optional) - Conversation ID for context. Auto-generated if not provided",
  "metadata": {
    "timestamp": "string (optional) - ISO 8601 timestamp",
    "device_id": "string (optional) - Device identifier",
    "location": "string (optional) - User location",
    "custom": "object (optional) - Custom metadata"
  }
}
```

**Response (200 OK):**

```json
{
  "response": {
    "text": "Timer set for 5 minutes",
    "modality": "text",
    "suggestions": [
      "Would you like to set another timer?",
      "Check your active timers"
    ],
    "rich_content": {
      "type": "timer_card",
      "data": {
        "duration": 300,
        "end_time": "2026-02-22T12:35:00Z"
      }
    }
  },
  "execution_result": {
    "success": true,
    "action_taken": "set_timer",
    "execution_time": 0.85
  },
  "conversation_id": "conv_abc123",
  "turn_id": "turn_xyz789",
  "metadata": {
    "intent_type": "set_timer",
    "confidence": 0.98,
    "processing_time": 0.92
  }
}
```

**Response (400 Bad Request):**

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Input text is required",
    "details": {
      "field": "input",
      "reason": "missing_required_field"
    }
  }
}
```

**Example:**

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "set a timer for 5 minutes",
    "user_id": "user123",
    "source": "text"
  }'
```

### 2. Get Conversation

Retrieve conversation history and state.

**Endpoint:** `GET /conversations/{conversation_id}`

**Path Parameters:**
- `conversation_id` (required) - Conversation identifier

**Query Parameters:**
- `include_turns` (optional) - Include conversation turns. Default: `true`
- `max_turns` (optional) - Maximum number of turns to return. Default: `20`

**Response (200 OK):**

```json
{
  "conversation_id": "conv_abc123",
  "user_id": "user123",
  "created_at": "2026-02-22T12:00:00Z",
  "updated_at": "2026-02-22T12:30:00Z",
  "turns": [
    {
      "turn_id": "turn_xyz789",
      "user_input": "set a timer for 5 minutes",
      "intent": {
        "intent_type": "set_timer",
        "entities": {
          "duration": 300
        },
        "confidence": 0.98
      },
      "response": "Timer set for 5 minutes",
      "timestamp": "2026-02-22T12:30:00Z"
    }
  ],
  "entities": {
    "last_timer_duration": 300,
    "preferred_timer_sound": "bell"
  },
  "context_summary": "User has set 3 timers today"
}
```

**Example:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/conversations/conv_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 3. List Conversations

List all conversations for a user.

**Endpoint:** `GET /conversations`

**Query Parameters:**
- `user_id` (required) - User identifier
- `limit` (optional) - Number of conversations to return. Default: `20`, Max: `100`
- `offset` (optional) - Pagination offset. Default: `0`
- `sort` (optional) - Sort order: `created_at`, `updated_at`. Default: `updated_at`
- `order` (optional) - Sort direction: `asc`, `desc`. Default: `desc`

**Response (200 OK):**

```json
{
  "conversations": [
    {
      "conversation_id": "conv_abc123",
      "user_id": "user123",
      "created_at": "2026-02-22T12:00:00Z",
      "updated_at": "2026-02-22T12:30:00Z",
      "turn_count": 5,
      "last_message": "Timer set for 5 minutes"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

**Example:**

```bash
curl -X GET "https://api.agent-guru.com/v1/reasoning/conversations?user_id=user123&limit=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 4. Delete Conversation

Delete a conversation and all associated data.

**Endpoint:** `DELETE /conversations/{conversation_id}`

**Path Parameters:**
- `conversation_id` (required) - Conversation identifier

**Response (204 No Content):**

No response body.

**Example:**

```bash
curl -X DELETE https://api.agent-guru.com/v1/reasoning/conversations/conv_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 5. Get Task Status

Get the status of an asynchronous task.

**Endpoint:** `GET /tasks/{task_id}`

**Path Parameters:**
- `task_id` (required) - Task identifier

**Response (200 OK):**

```json
{
  "task_id": "task_def456",
  "status": "running",
  "progress": 0.65,
  "created_at": "2026-02-22T12:30:00Z",
  "updated_at": "2026-02-22T12:30:45Z",
  "result": null,
  "error": null,
  "metadata": {
    "action": "send_email",
    "estimated_completion": "2026-02-22T12:31:00Z"
  }
}
```

**Task Status Values:**
- `queued` - Task is queued for execution
- `running` - Task is currently executing
- `completed` - Task completed successfully
- `failed` - Task failed with error
- `cancelled` - Task was cancelled

**Example:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/tasks/task_def456 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 6. Cancel Task

Cancel a running or queued task.

**Endpoint:** `POST /tasks/{task_id}/cancel`

**Path Parameters:**
- `task_id` (required) - Task identifier

**Response (200 OK):**

```json
{
  "task_id": "task_def456",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

**Example:**

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/tasks/task_def456/cancel \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 7. Health Check

Check service health status.

**Endpoint:** `GET /health`

**Authentication:** Not required

**Response (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-22T12:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "llm": "healthy"
  }
}
```

**Example:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/health
```

### 8. Readiness Check

Check if service is ready to accept requests.

**Endpoint:** `GET /ready`

**Authentication:** Not required

**Response (200 OK):**

```json
{
  "ready": true,
  "timestamp": "2026-02-22T12:30:00Z"
}
```

**Example:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/ready
```

### 9. Metrics

Get Prometheus metrics.

**Endpoint:** `GET /metrics`

**Authentication:** Not required (internal use)

**Response (200 OK):**

```
# HELP reasoning_requests_total Total number of reasoning requests
# TYPE reasoning_requests_total counter
reasoning_requests_total{intent_type="set_timer",status="success"} 1234

# HELP reasoning_latency_seconds Reasoning latency in seconds
# TYPE reasoning_latency_seconds histogram
reasoning_latency_seconds_bucket{le="0.5"} 850
reasoning_latency_seconds_bucket{le="1.0"} 1200
reasoning_latency_seconds_bucket{le="1.5"} 1450
reasoning_latency_seconds_bucket{le="+Inf"} 1500
reasoning_latency_seconds_sum 1250.5
reasoning_latency_seconds_count 1500
```

**Example:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/metrics
```

## WebSocket API

### Connection

**Endpoint:** `wss://api.agent-guru.com/v1/reasoning/ws`

**Authentication:** Include API key in query parameter or initial message

**Connection URL:**
```
wss://api.agent-guru.com/v1/reasoning/ws?api_key=YOUR_API_KEY
```

### Message Format

**Client → Server (Request):**

```json
{
  "type": "process",
  "request_id": "req_123",
  "data": {
    "input": "set a timer for 5 minutes",
    "user_id": "user123",
    "conversation_id": "conv_abc123"
  }
}
```

**Server → Client (Response):**

```json
{
  "type": "response",
  "request_id": "req_123",
  "data": {
    "response": {
      "text": "Timer set for 5 minutes",
      "modality": "text"
    },
    "execution_result": {
      "success": true
    }
  }
}
```

**Server → Client (Progress Update):**

```json
{
  "type": "progress",
  "request_id": "req_123",
  "data": {
    "stage": "reasoning",
    "progress": 0.5,
    "message": "Generating reasoning plan..."
  }
}
```

**Server → Client (Error):**

```json
{
  "type": "error",
  "request_id": "req_123",
  "error": {
    "code": "PROCESSING_ERROR",
    "message": "Failed to process request"
  }
}
```

### Example (JavaScript)

```javascript
const ws = new WebSocket('wss://api.agent-guru.com/v1/reasoning/ws?api_key=YOUR_API_KEY');

ws.onopen = () => {
  console.log('Connected');
  
  // Send request
  ws.send(JSON.stringify({
    type: 'process',
    request_id: 'req_123',
    data: {
      input: 'set a timer for 5 minutes',
      user_id: 'user123'
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'progress') {
    console.log('Progress:', message.data.progress);
  } else if (message.type === 'response') {
    console.log('Response:', message.data.response.text);
  } else if (message.type === 'error') {
    console.error('Error:', message.error.message);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

## Error Codes

### Client Errors (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_INPUT` | 400 | Invalid or missing input parameters |
| `AUTHENTICATION_FAILED` | 401 | Invalid or missing API key |
| `AUTHORIZATION_FAILED` | 403 | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `VALIDATION_ERROR` | 422 | Request validation failed |

### Server Errors (5xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |
| `TIMEOUT` | 504 | Request timeout |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `LLM_ERROR` | 500 | LLM service error |
| `TOOL_EXECUTION_ERROR` | 500 | Tool execution failed |

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Human-readable error message",
    "details": {
      "field": "input",
      "reason": "missing_required_field",
      "suggestion": "Provide the 'input' field in the request body"
    },
    "request_id": "req_abc123",
    "timestamp": "2026-02-22T12:30:00Z"
  }
}
```

### Error Handling Best Practices

1. **Always check HTTP status code**
2. **Parse error response for details**
3. **Implement exponential backoff for retries**
4. **Log errors with request_id for debugging**
5. **Handle rate limits gracefully**

**Example (Python):**

```python
import requests
import time

def process_with_retry(input_text, user_id, max_retries=3):
    url = "https://api.agent-guru.com/v1/reasoning/process"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "input": input_text,
        "user_id": user_id
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limit - exponential backoff
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            elif response.status_code >= 500:
                # Server error - retry
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Client error - don't retry
                error = response.json()
                raise Exception(f"API Error: {error['error']['message']}")
                
        except requests.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    
    raise Exception("Max retries exceeded")
```

## Rate Limits

### Default Limits

| Tier | Requests per Minute | Requests per Day | Concurrent Requests |
|------|---------------------|------------------|---------------------|
| Free | 60 | 1,000 | 5 |
| Basic | 600 | 50,000 | 20 |
| Pro | 6,000 | 500,000 | 100 |
| Enterprise | Custom | Custom | Custom |

### Rate Limit Headers

Every API response includes rate limit information:

```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 599
X-RateLimit-Reset: 1709164860
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after 60 seconds.",
    "details": {
      "limit": 600,
      "remaining": 0,
      "reset_at": "2026-02-22T12:31:00Z"
    }
  }
}
```

### Best Practices

1. **Monitor rate limit headers**
2. **Implement exponential backoff**
3. **Cache responses when possible**
4. **Batch requests when applicable**
5. **Upgrade tier if consistently hitting limits**

## Examples

### Example 1: Simple Timer Request

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "set a timer for 5 minutes",
    "user_id": "user123"
  }'
```

**Response:**

```json
{
  "response": {
    "text": "Timer set for 5 minutes",
    "modality": "text"
  },
  "execution_result": {
    "success": true,
    "action_taken": "set_timer"
  },
  "conversation_id": "conv_abc123"
}
```

### Example 2: Multi-Turn Conversation

**Turn 1:**

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "what is the weather like?",
    "user_id": "user123"
  }'
```

**Response:**

```json
{
  "response": {
    "text": "Where would you like to know the weather for?"
  },
  "conversation_id": "conv_abc123"
}
```

**Turn 2:**

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "San Francisco",
    "user_id": "user123",
    "conversation_id": "conv_abc123"
  }'
```

**Response:**

```json
{
  "response": {
    "text": "The weather in San Francisco is currently 65°F and sunny."
  },
  "conversation_id": "conv_abc123"
}
```

### Example 3: Async Task Execution

**Submit Task:**

```bash
curl -X POST https://api.agent-guru.com/v1/reasoning/process \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "send an email to john@example.com with the quarterly report",
    "user_id": "user123"
  }'
```

**Response:**

```json
{
  "response": {
    "text": "I'm sending the email now. This may take a moment."
  },
  "execution_result": {
    "success": true,
    "task_id": "task_def456",
    "status": "running"
  }
}
```

**Check Task Status:**

```bash
curl -X GET https://api.agent-guru.com/v1/reasoning/tasks/task_def456 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**

```json
{
  "task_id": "task_def456",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "email_sent": true,
    "message_id": "msg_xyz789"
  }
}
```

## SDKs and Client Libraries

### Official SDKs

- **Python:** `pip install agent-guru-sdk`
- **JavaScript/TypeScript:** `npm install @agent-guru/sdk`
- **Go:** `go get github.com/agent-guru/go-sdk`
- **Java:** Maven/Gradle available

### Python SDK Example

```python
from agent_guru import ReasoningClient

client = ReasoningClient(api_key="YOUR_API_KEY")

# Process request
response = client.process(
    input="set a timer for 5 minutes",
    user_id="user123"
)

print(response.text)  # "Timer set for 5 minutes"

# Get conversation
conversation = client.get_conversation(response.conversation_id)
print(f"Turns: {len(conversation.turns)}")

# Async task
response = client.process(
    input="send an email to john@example.com",
    user_id="user123"
)

if response.task_id:
    # Wait for completion
    result = client.wait_for_task(response.task_id, timeout=60)
    print(f"Task completed: {result.success}")
```

### JavaScript SDK Example

```javascript
import { ReasoningClient } from '@agent-guru/sdk';

const client = new ReasoningClient({ apiKey: 'YOUR_API_KEY' });

// Process request
const response = await client.process({
  input: 'set a timer for 5 minutes',
  userId: 'user123'
});

console.log(response.text);  // "Timer set for 5 minutes"

// WebSocket streaming
const stream = client.processStream({
  input: 'set a timer for 5 minutes',
  userId: 'user123'
});

stream.on('progress', (data) => {
  console.log('Progress:', data.progress);
});

stream.on('response', (data) => {
  console.log('Response:', data.text);
});

stream.on('error', (error) => {
  console.error('Error:', error);
});
```

## Support

### Documentation

- **API Reference:** https://docs.agent-guru.com/api
- **Guides:** https://docs.agent-guru.com/guides
- **Examples:** https://github.com/agent-guru/examples

### Support Channels

- **Email:** support@agent-guru.com
- **Discord:** https://discord.gg/agent-guru
- **GitHub Issues:** https://github.com/agent-guru/reasoning-engine/issues

### Status Page

Monitor API status and incidents: https://status.agent-guru.com

## Changelog

### v1.0.0 (2026-02-22)

- Initial production release
- REST API with 9 endpoints
- WebSocket API for real-time updates
- Rate limiting and authentication
- Comprehensive error handling

## License

API usage is subject to the Agent Guru Terms of Service: https://agent-guru.com/terms
