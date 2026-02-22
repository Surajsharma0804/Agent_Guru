# API Usage Guide

Complete guide for using the Agent Guru Reasoning Engine API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Processing Requests](#processing-requests)
4. [Managing Conversations](#managing-conversations)
5. [Tracking Tasks](#tracking-tasks)
6. [Real-time Updates](#real-time-updates)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Performance Optimization](#performance-optimization)
10. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- Python 3.11+
- FastAPI and dependencies installed
- Running API server

### Starting the Server

```bash
# Development mode with auto-reload
uvicorn Agent_Guru.reasoning.api.app:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn Agent_Guru.reasoning.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Verify Server is Running

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

## Authentication

### Creating Tokens

```python
from Agent_Guru.reasoning.api.auth import create_access_token

# Create token for a user
token = create_access_token("user_123")
print(f"Token: {token}")

# Token is valid for 24 hours by default
```

### Using Tokens

Include the token in the `Authorization` header with `Bearer` prefix:

```python
import requests

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

response = requests.get(
    "http://localhost:8000/v1/stats",
    headers=headers,
)
```

### Token Expiration

Tokens expire after 24 hours. When a token expires:
- API returns HTTP 401 Unauthorized
- Error message: "Token has expired"
- Solution: Generate a new token

## Processing Requests

### Basic Request

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/process",
    json={
        "text": "set a timer for 5 minutes",
        "user_id": "user_123",
        "source": "text",
    },
    headers={"Authorization": f"Bearer {token}"},
)

result = response.json()
print(f"Response: {result['response']}")
print(f"Confidence: {result['confidence']}")
print(f"Latency: {result['latency_ms']}ms")
```

### With Conversation Context

```python
response = requests.post(
    "http://localhost:8000/v1/process",
    json={
        "text": "make it 10 minutes instead",
        "user_id": "user_123",
        "conversation_id": "conv_456",  # Provide context
        "source": "text",
    },
    headers={"Authorization": f"Bearer {token}"},
)
```

### With Metadata

```python
response = requests.post(
    "http://localhost:8000/v1/process",
    json={
        "text": "set a timer for 5 minutes",
        "user_id": "user_123",
        "source": "voice",  # Voice input
        "metadata": {
            "device_id": "device_789",
            "location": "home",
            "language": "en-US",
        },
    },
    headers={"Authorization": f"Bearer {token}"},
)
```

### Understanding the Response

```python
{
    "response": "Timer set for 5 minutes",  # Natural language response
    "confidence": 0.98,  # Confidence score (0.0-1.0)
    "intent_type": "set_timer",  # Detected intent
    "success": true,  # Whether processing succeeded
    "fast_path": true,  # Whether fast-path was used
    "latency_ms": 234.5,  # Total latency
    "stage_latencies": {  # Per-stage latencies
        "intent_detection": 50.2,
        "tool_selection": 12.3,
        "response_generation": 15.0
    },
    "trace_id": "abc123",  # For debugging
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## Managing Conversations

### Get Conversation State

```python
response = requests.get(
    "http://localhost:8000/v1/conversations/conv_456",
    headers={"Authorization": f"Bearer {token}"},
)

conversation = response.json()
print(f"Turn count: {conversation['turn_count']}")
print(f"Recent turns: {conversation['recent_turns']}")
print(f"Tracked entities: {conversation['entities']}")
```

### List All Conversations

```python
response = requests.get(
    "http://localhost:8000/v1/conversations?limit=20",
    headers={"Authorization": f"Bearer {token}"},
)

conversations = response.json()
for conv in conversations:
    print(f"Conversation {conv['conversation_id']}: {conv['turn_count']} turns")
```

### Conversation Context Benefits

When you provide a `conversation_id`:
- System remembers previous turns
- Entities are tracked across turns
- References are resolved ("it", "that", "tomorrow")
- Context improves intent detection accuracy

## Tracking Tasks

### Get Task Status

```python
response = requests.get(
    "http://localhost:8000/v1/tasks/task_789",
    headers={"Authorization": f"Bearer {token}"},
)

task = response.json()
print(f"Status: {task['status']}")
print(f"Progress: {task['progress'] * 100}%")

if task['status'] == 'completed':
    print(f"Result: {task['result']}")
elif task['status'] == 'failed':
    print(f"Error: {task['error']}")
```

### Polling for Completion

```python
import time

task_id = "task_789"

while True:
    response = requests.get(
        f"http://localhost:8000/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    
    task = response.json()
    status = task['status']
    
    if status in ['completed', 'failed']:
        break
    
    print(f"Progress: {task['progress'] * 100}%")
    time.sleep(1)

if status == 'completed':
    print(f"Result: {task['result']}")
else:
    print(f"Failed: {task['error']}")
```

## Real-time Updates

### WebSocket Connection

```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/v1/ws?user_id=user_123"
    
    async with websockets.connect(uri) as websocket:
        # Wait for connected message
        message = await websocket.recv()
        print(f"Connected: {message}")
        
        # Send request
        await websocket.send(json.dumps({
            "type": "request",
            "data": {
                "text": "set a timer for 5 minutes",
            },
            "request_id": "req_123",
        }))
        
        # Receive messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data['type'] == 'response':
                print(f"Response: {data['data']}")
                break
            elif data['type'] == 'progress':
                print(f"Progress: {data['data']['progress'] * 100}%")
            elif data['type'] == 'ping':
                # Respond to heartbeat
                await websocket.send(json.dumps({"type": "pong"}))

asyncio.run(connect())
```

### JavaScript WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/v1/ws?user_id=user_123');

ws.onopen = () => {
    console.log('Connected');
    
    // Send request
    ws.send(JSON.stringify({
        type: 'request',
        data: {
            text: 'set a timer for 5 minutes',
        },
        request_id: 'req_123',
    }));
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
        case 'connected':
            console.log('Connection established');
            break;
        
        case 'progress':
            console.log(`Progress: ${message.data.progress * 100}%`);
            break;
        
        case 'response':
            console.log('Response:', message.data);
            break;
        
        case 'error':
            console.error('Error:', message.data.error);
            break;
        
        case 'ping':
            ws.send(JSON.stringify({type: 'pong'}));
            break;
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected');
};
```

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Fix request format |
| 401 | Unauthorized | Check token |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Check resource ID |
| 429 | Rate Limit | Wait and retry |
| 500 | Server Error | Report issue |

### Handling Errors

```python
try:
    response = requests.post(
        "http://localhost:8000/v1/process",
        json=request_data,
        headers=headers,
    )
    response.raise_for_status()  # Raise exception for 4xx/5xx
    
    result = response.json()
    print(f"Success: {result['response']}")
    
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Token expired, please refresh")
    elif e.response.status_code == 429:
        print("Rate limit exceeded, please wait")
    else:
        error = e.response.json()
        print(f"Error: {error['error']}")
        print(f"Code: {error['error_code']}")

except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
```

### Retry Logic

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)

# Use session for requests
response = session.post(
    "http://localhost:8000/v1/process",
    json=request_data,
    headers=headers,
)
```

## Best Practices

### 1. Reuse Connections

```python
# Good: Reuse session
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}"})

for i in range(100):
    response = session.post(
        "http://localhost:8000/v1/process",
        json={"text": f"request {i}", "user_id": "user_123"},
    )
```

### 2. Use Conversation Context

```python
# Good: Maintain conversation context
conversation_id = "conv_456"

for user_input in ["set a timer", "for 5 minutes", "cancel it"]:
    response = requests.post(
        "http://localhost:8000/v1/process",
        json={
            "text": user_input,
            "user_id": "user_123",
            "conversation_id": conversation_id,
        },
        headers=headers,
    )
```

### 3. Handle Rate Limits

```python
def make_request_with_backoff(url, data, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 429:
            # Rate limited, wait and retry
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited, waiting {retry_after}s")
            time.sleep(retry_after)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

### 4. Monitor Performance

```python
import time

start = time.time()
response = requests.post(url, json=data, headers=headers)
latency = (time.time() - start) * 1000

print(f"Request latency: {latency:.1f}ms")
print(f"Processing latency: {response.json()['latency_ms']:.1f}ms")
```

### 5. Use WebSocket for Real-time

```python
# Good: Use WebSocket for streaming/progress
# Bad: Poll REST API repeatedly

# WebSocket provides:
# - Lower latency
# - Real-time updates
# - Reduced server load
# - Better user experience
```

## Performance Optimization

### Batch Requests

```python
# Process multiple requests efficiently
import asyncio
import aiohttp

async def process_batch(texts):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for text in texts:
            task = session.post(
                "http://localhost:8000/v1/process",
                json={"text": text, "user_id": "user_123"},
                headers=headers,
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        return [await r.json() for r in responses]

texts = ["set a timer", "query weather", "play music"]
results = asyncio.run(process_batch(texts))
```

### Connection Pooling

```python
from requests.adapters import HTTPAdapter

session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

### Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_response(text_hash):
    response = requests.post(
        "http://localhost:8000/v1/process",
        json={"text": text, "user_id": "user_123"},
        headers=headers,
    )
    return response.json()

# Use cache
text = "set a timer for 5 minutes"
text_hash = hashlib.sha256(text.encode()).hexdigest()
result = get_cached_response(text_hash)
```

## Troubleshooting

### Connection Refused

**Problem**: Cannot connect to API server

**Solutions**:
1. Check server is running: `curl http://localhost:8000/health`
2. Check port is correct (default: 8000)
3. Check firewall settings
4. Check server logs for errors

### Token Expired

**Problem**: HTTP 401 with "Token has expired"

**Solution**:
```python
# Regenerate token
token = create_access_token("user_123")
headers["Authorization"] = f"Bearer {token}"
```

### Rate Limit Exceeded

**Problem**: HTTP 429 Too Many Requests

**Solutions**:
1. Wait for rate limit window to reset (60 seconds)
2. Implement exponential backoff
3. Reduce request frequency
4. Contact support for higher limits

### Slow Response Times

**Problem**: Requests taking >2 seconds

**Solutions**:
1. Check server resources (CPU, memory)
2. Check network latency
3. Use fast-path eligible intents
4. Enable caching
5. Check `/v1/stats` for performance metrics

### WebSocket Disconnects

**Problem**: WebSocket connection drops frequently

**Solutions**:
1. Implement reconnection logic
2. Respond to ping messages with pong
3. Check network stability
4. Increase heartbeat interval

### Invalid Response Format

**Problem**: Cannot parse JSON response

**Solutions**:
1. Check API version compatibility
2. Verify request format
3. Check server logs for errors
4. Update client library

## Support

For additional help:
- Documentation: https://docs.agent-guru.com
- GitHub Issues: https://github.com/agent-guru/reasoning-engine/issues
- Email: support@agent-guru.com
