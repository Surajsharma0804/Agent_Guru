# Agent Guru Reasoning Engine - API Reference

> For the full API documentation including SDKs, rate limits, and detailed examples, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## Base URLs

| Environment | URL |
|-------------|-----|
| Production | `https://api.agent-guru.com/v1/reasoning` |
| Staging | `https://api-staging.agent-guru.com/v1/reasoning` |
| Development | `http://localhost:8000` |

## Authentication

All endpoints (except `/health`, `/ready`, `/metrics`) require:

```
Authorization: Bearer <API_KEY_OR_JWT_TOKEN>
```

---

## Endpoints

### POST /v1/process

Process user input through the reasoning pipeline.

**Request:**

```json
{
  "text": "set a timer for 5 minutes",
  "user_id": "user_123",
  "source": "text",
  "conversation_id": "conv_abc123",
  "metadata": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | User input text |
| `user_id` | string | Yes | Unique user identifier |
| `source` | string | No | `text`, `voice`, or `system_event`. Default: `text` |
| `conversation_id` | string | No | Existing conversation ID for context |
| `metadata` | object | No | Additional metadata |

**Response (200):**

```json
{
  "response": "Timer set for 5 minutes",
  "confidence": 0.98,
  "intent_type": "set_timer",
  "success": true,
  "fast_path": true,
  "latency_ms": 45.2,
  "stage_latencies": {
    "input_normalization": 2.1,
    "intent_detection": 38.5,
    "tool_selection": 3.2,
    "safety_validation": 1.4
  },
  "conversation_id": "conv_abc123",
  "trace_id": "trace_xyz789",
  "timestamp": "2026-02-22T12:30:00Z"
}
```

**Error (400):**

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Input text is required",
    "details": {"field": "text", "reason": "missing_required_field"}
  }
}
```

---

### GET /v1/conversations/{conversation_id}

Retrieve conversation history and state.

**Path Parameters:**
- `conversation_id` (required) - Conversation identifier

**Query Parameters:**
- `include_turns` (optional, default: `true`) - Include conversation turns
- `max_turns` (optional, default: `20`) - Maximum turns to return

**Response (200):**

```json
{
  "conversation_id": "conv_abc123",
  "user_id": "user_123",
  "turn_count": 5,
  "recent_turns": [
    {
      "turn_id": "turn_xyz789",
      "user_input": "set a timer for 5 minutes",
      "response": "Timer set for 5 minutes",
      "timestamp": "2026-02-22T12:30:00Z"
    }
  ],
  "entities": {
    "last_timer_duration": {"entity_type": "duration", "value": 300, "mention_count": 1}
  },
  "created_at": "2026-02-22T12:00:00Z",
  "updated_at": "2026-02-22T12:30:00Z"
}
```

---

### GET /v1/conversations

List conversations for the authenticated user.

**Query Parameters:**
- `limit` (optional, default: `10`, max: `100`) - Number of conversations
- `offset` (optional, default: `0`) - Pagination offset

**Response (200):**

```json
{
  "conversations": [...],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

---

### DELETE /v1/conversations/{conversation_id}

Delete a conversation and all associated data.

**Response:** `204 No Content`

---

### GET /v1/tasks/{task_id}

Get the status of an asynchronous task.

**Response (200):**

```json
{
  "task_id": "task_def456",
  "status": "running",
  "progress": 0.65,
  "result": null,
  "error": null,
  "created_at": "2026-02-22T12:30:00Z",
  "updated_at": "2026-02-22T12:30:45Z"
}
```

**Task status values:** `queued`, `running`, `completed`, `failed`, `cancelled`

---

### POST /v1/tasks/{task_id}/cancel

Cancel a running or queued task.

**Response (200):**

```json
{
  "task_id": "task_def456",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

---

### GET /health

Health check (no authentication required).

**Response (200):**

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

---

### GET /ready

Readiness check (no authentication required).

**Response (200):**

```json
{"ready": true, "timestamp": "2026-02-22T12:30:00Z"}
```

---

### GET /metrics

Prometheus metrics (no authentication required).

Returns metrics in Prometheus text format. Key metrics:

```
reasoning_requests_total{intent_type="set_timer",status="success"} 1234
reasoning_latency_seconds_bucket{le="1.0"} 1200
reasoning_errors_total{error_type="llm_timeout"} 5
```

---

## WebSocket API

**Endpoint:** `wss://api.agent-guru.com/v1/ws?user_id=<user_id>`

**Client → Server:**

```json
{
  "type": "request",
  "request_id": "req_123",
  "data": {
    "text": "set a timer for 5 minutes",
    "conversation_id": "conv_abc123"
  }
}
```

**Server → Client (progress):**

```json
{
  "type": "progress",
  "request_id": "req_123",
  "data": {"stage": "reasoning", "progress": 0.5}
}
```

**Server → Client (response):**

```json
{
  "type": "response",
  "request_id": "req_123",
  "data": {"response": "Timer set for 5 minutes", "success": true}
}
```

**Server → Client (error):**

```json
{
  "type": "error",
  "request_id": "req_123",
  "error": {"code": "PROCESSING_ERROR", "message": "Failed to process request"}
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_INPUT` | 400 | Invalid or missing input parameters |
| `AUTHENTICATION_FAILED` | 401 | Invalid or missing API key |
| `AUTHORIZATION_FAILED` | 403 | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |
| `TIMEOUT` | 504 | Request timeout |
| `LLM_ERROR` | 500 | LLM service error |
| `TOOL_EXECUTION_ERROR` | 500 | Tool execution failed |

---

## Rate Limits

| Tier | Requests/min | Requests/day | Concurrent |
|------|-------------|--------------|------------|
| Free | 60 | 1,000 | 5 |
| Basic | 600 | 50,000 | 20 |
| Pro | 6,000 | 500,000 | 100 |
| Enterprise | Custom | Custom | Custom |

Rate limit headers in every response:

```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 599
X-RateLimit-Reset: 1709164860
```

---

## Related Documentation

- [User Guide](./user_guide.md) - Common usage scenarios
- [Deployment Guide](./deployment_guide.md) - Kubernetes deployment
- [Operations Runbook](./operations_runbook.md) - Monitoring and incident response
- [Full API Documentation](./API_DOCUMENTATION.md) - Complete reference with SDK examples
