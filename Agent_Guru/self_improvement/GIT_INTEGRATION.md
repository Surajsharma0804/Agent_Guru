# Git Integration System

## Overview

The Git Integration system provides automated versioning of learning data by committing performance metrics, failure analyses, and improvement reports to GitHub after each task execution. This ensures all learning progress is tracked, versioned, and recoverable.

## Features

### 1. Automated Commits
- **After Each Task**: Commits execution data with performance metrics
- **Every 100 Tasks**: Commits comprehensive improvement reports
- **Meaningful Messages**: Descriptive commit messages showing what was learned
- **Selective Files**: Only commits learning data and README.md (no noise)

### 2. Authentication Support
- **SSH Keys**: Recommended for local development (uses ~/.ssh/id_rsa)
- **GitHub Tokens**: Recommended for CI/CD pipelines
- **No Auth**: For local testing without remote push

### 3. Retry Logic
- **Exponential Backoff**: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)
- **Configurable Retries**: Default 5 attempts, customizable
- **Graceful Degradation**: Queues commits if all retries fail

### 4. Offline Queue
- **Local Backup**: Commits queued locally when network unavailable
- **Persistent Storage**: Queue survives application restarts
- **Batch Processing**: Process all queued commits when back online
- **No Data Loss**: All learning data preserved even offline

## Installation

```bash
# Install GitPython dependency
pip install gitpython>=3.1.40

# Or install all requirements
pip install -r requirements.txt
```

## Quick Start

```python
from Agent_Guru.self_improvement import GitIntegration, AuthMethod

# Initialize with SSH authentication
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.SSH,
    auto_push=True
)

# Commit task execution data
git_integration.commit_execution_data(execution)

# Commit improvement report (every 100 tasks)
git_integration.commit_improvement_report(report)
```

## Usage Examples

### Basic Usage

```python
from Agent_Guru.self_improvement import GitIntegration, TaskExecution
from datetime import datetime

# Initialize
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auto_push=True
)

# Create task execution
execution = TaskExecution(
    task_id="task_001",
    task_type="code_generation",
    strategy_id="strategy_v1",
    timestamp=datetime.now(),
    success=True,
    execution_time_ms=250.5,
    failure_type=None,
    error_details=None,
    context={"language": "python"}
)

# Commit execution data
success = git_integration.commit_execution_data(execution)
```

### Authentication Methods

#### SSH Authentication (Recommended for Local)

```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.SSH
)
```

**Requirements**:
- SSH key configured: `~/.ssh/id_rsa`
- Key added to GitHub: Settings → SSH Keys
- Repository URL uses SSH: `git@github.com:user/repo.git`

#### Token Authentication (Recommended for CI/CD)

```python
import os

token = os.environ.get("GITHUB_TOKEN")

git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.TOKEN,
    auth_token=token
)
```

**Requirements**:
- GitHub Personal Access Token with `repo` scope
- Token stored securely (environment variable, secrets manager)
- Repository URL uses HTTPS: `https://github.com/user/repo.git`

**Generate Token**:
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select `repo` scope
4. Copy token (shown only once)

#### No Authentication (Local Testing)

```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.NONE,
    auto_push=False  # Don't push to remote
)
```

### Improvement Reports

```python
# Generate improvement report after 100 tasks
report = {
    "total_tasks": 100,
    "baseline_success_rate": 0.70,
    "current_success_rate": 0.88,
    "relative_improvement": 0.18,  # 18% improvement
    "execution_time_improvement": 0.12,
    "reasoning_accuracy_improvement": 0.15,
    "timestamp": datetime.now().isoformat(),
    "confidence_interval": [0.15, 0.21]
}

# Commit report
git_integration.commit_improvement_report(report)
```

**Commit Message Example**:
```
📈 Improvement Report: +18.0% after 100 tasks (Target: +15% ✅)
```

### Offline Queue Management

```python
# Check queue size
queue_size = git_integration.get_queue_size()
print(f"Pending commits: {queue_size}")

# Process queued commits when back online
processed = git_integration.process_queue()
print(f"Processed {processed} commits")

# Clear queue (use with caution)
git_integration.clear_queue()
```

### Retry Configuration

```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    max_retries=5,           # Maximum retry attempts
    initial_backoff=1.0,     # Initial delay (seconds)
    max_backoff=60.0         # Maximum delay (seconds)
)
```

**Backoff Progression**:
- Retry 1: 1.0s
- Retry 2: 2.0s
- Retry 3: 4.0s
- Retry 4: 8.0s
- Retry 5: 16.0s
- After max retries: Queued for later

### Online Status Check

```python
# Check if remote is accessible
if git_integration.is_online():
    print("✅ Remote accessible, safe to push")
    git_integration.process_queue()
else:
    print("❌ Remote not accessible, commits will be queued")
```

## Commit Message Format

### Successful Execution
```
✅ Task code_generation succeeded (250ms) using strategy_v1
```

### Failed Execution
```
❌ Task complex_reasoning failed (reasoning_error) using strategy_v2
```

### Improvement Report (Target Met)
```
📈 Improvement Report: +18.0% after 100 tasks (Target: +15% ✅)
```

### Improvement Report (Target Not Met)
```
📊 Improvement Report: +10.0% after 100 tasks (Target: +15% ⚠️)
```

## File Structure

```
repo/
├── learning_data/
│   ├── executions.json          # Task execution history
│   ├── improvement_reports.json # Improvement reports
│   ├── strategies.json          # Strategy performance
│   └── failures.json            # Failure analysis
├── README.md                    # Updated with latest metrics
└── .git/
    └── commit_queue/
        └── pending_commits.json # Offline queue
```

## Configuration

### Environment Variables

```bash
# GitHub token for authentication
export GITHUB_TOKEN="ghp_your_token_here"

# Repository path
export AGENT_GURU_REPO="/path/to/repo"
```

### Configuration File

```python
# config.py
GIT_CONFIG = {
    "repo_path": "/path/to/repo",
    "auth_method": "ssh",  # or "token", "none"
    "auth_token": None,    # or token string
    "max_retries": 5,
    "initial_backoff": 1.0,
    "max_backoff": 60.0,
    "auto_push": True
}
```

## Performance Characteristics

- **Time Complexity**: O(1) for queue operations, O(n) for batch commits
- **Space Complexity**: O(n) for offline queue storage
- **Commit Latency**: <5s for normal operation
- **Retry Overhead**: Exponential backoff with max 60s delay
- **Queue Persistence**: Disk-based, survives restarts

## Error Handling

### Network Failures
```python
try:
    git_integration.commit_execution_data(execution)
except Exception as e:
    # Commit automatically queued for retry
    print(f"Commit queued due to: {e}")
```

### Authentication Failures
```python
# Check authentication before operations
if git_integration.auth_method == AuthMethod.TOKEN:
    if not git_integration.auth_token:
        raise ValueError("Token required for TOKEN auth")
```

### Repository Errors
```python
from git import InvalidGitRepositoryError

try:
    git_integration = GitIntegration("/invalid/path")
except InvalidGitRepositoryError:
    print("Not a valid Git repository")
```

## Best Practices

### 1. Use SSH for Local Development
```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.SSH
)
```

### 2. Use Tokens for CI/CD
```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auth_method=AuthMethod.TOKEN,
    auth_token=os.environ["GITHUB_TOKEN"]
)
```

### 3. Process Queue Periodically
```python
# Every hour or when back online
if git_integration.is_online():
    git_integration.process_queue()
```

### 4. Monitor Queue Size
```python
queue_size = git_integration.get_queue_size()
if queue_size > 100:
    print(f"Warning: Large queue ({queue_size} commits)")
```

### 5. Disable Auto-Push for Testing
```python
git_integration = GitIntegration(
    repo_path="/path/to/repo",
    auto_push=False  # Manual push control
)
```

## Troubleshooting

### Issue: Commits Not Pushing

**Check 1: Authentication**
```python
# Verify auth method and credentials
print(f"Auth method: {git_integration.auth_method}")
print(f"Has token: {git_integration.auth_token is not None}")
```

**Check 2: Remote Configuration**
```bash
# Verify remote URL
git remote -v

# Should show:
# origin  git@github.com:user/repo.git (fetch)  # SSH
# or
# origin  https://github.com/user/repo.git (fetch)  # HTTPS
```

**Check 3: Network Connectivity**
```python
if not git_integration.is_online():
    print("Remote not accessible")
```

### Issue: Queue Growing Large

**Solution 1: Process Queue**
```python
processed = git_integration.process_queue()
print(f"Processed {processed} commits")
```

**Solution 2: Check Network**
```python
if git_integration.is_online():
    git_integration.process_queue()
else:
    print("Still offline, queue will grow")
```

### Issue: Permission Denied

**SSH**: Add key to GitHub
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and paste to GitHub → Settings → SSH Keys
```

**Token**: Check token scope
- Token must have `repo` scope
- Token must not be expired
- Token must be for correct account

## Testing

```python
# Run tests
pytest Agent_Guru/self_improvement/tests/test_git_integration.py

# Run with coverage
pytest --cov=Agent_Guru.self_improvement.git_integration \
       Agent_Guru/self_improvement/tests/test_git_integration.py

# Run specific test
pytest Agent_Guru/self_improvement/tests/test_git_integration.py::TestGitIntegrationInitialization
```

## API Reference

### GitIntegration

```python
class GitIntegration:
    def __init__(
        self,
        repo_path: str,
        auth_method: AuthMethod = AuthMethod.SSH,
        auth_token: Optional[str] = None,
        max_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        queue_path: Optional[str] = None,
        auto_push: bool = True
    )
```

**Methods**:
- `commit_execution_data(execution, push=True) -> bool`
- `commit_improvement_report(report, push=True) -> bool`
- `process_queue() -> int`
- `get_queue_size() -> int`
- `clear_queue() -> None`
- `is_online() -> bool`

### AuthMethod

```python
class AuthMethod(Enum):
    SSH = "ssh"      # Use SSH keys
    TOKEN = "token"  # Use GitHub token
    NONE = "none"    # No authentication
```

### CommitData

```python
@dataclass
class CommitData:
    commit_id: str
    timestamp: datetime
    message: str
    files: List[str]
    data: Dict[str, Any]
    retry_count: int = 0
    last_retry: Optional[datetime] = None
```

## Integration with Self-Improvement Engine

```python
from Agent_Guru.self_improvement import (
    SelfImprovementEngine,
    GitIntegration
)

# Initialize engine with Git integration
engine = SelfImprovementEngine(
    storage_path="learning.db",
    git_repo_path="/path/to/repo"
)

# Git integration is automatically used
engine.record_task_execution(
    task_id="task_001",
    task_type="code_generation",
    strategy_used="strategy_v1",
    success=True,
    execution_time_ms=250.5
)
# → Automatically commits to Git
```

## Security Considerations

### 1. Token Storage
- **Never** commit tokens to repository
- Use environment variables or secrets manager
- Rotate tokens regularly

### 2. SSH Keys
- Use passphrase-protected keys
- Restrict key permissions: `chmod 600 ~/.ssh/id_rsa`
- Use separate keys for different purposes

### 3. Repository Access
- Use least-privilege principle
- Limit token scope to `repo` only
- Review repository access regularly

### 4. Commit Content
- Only commit learning data (no secrets)
- Sanitize error messages (no PII)
- Review commit content before push

## Performance Optimization

### 1. Batch Commits
```python
# Instead of committing each execution individually
for execution in executions:
    git_integration.commit_execution_data(execution, push=False)

# Push all at once
git_integration.process_queue()
```

### 2. Async Processing
```python
import asyncio

async def commit_async(execution):
    # Run commit in background
    await asyncio.to_thread(
        git_integration.commit_execution_data,
        execution
    )
```

### 3. Queue Management
```python
# Process queue during idle time
if git_integration.get_queue_size() > 0:
    if git_integration.is_online():
        git_integration.process_queue()
```

## Monitoring

### Metrics to Track
- Queue size over time
- Commit success rate
- Average retry count
- Push latency
- Network availability

### Example Monitoring
```python
import time

def monitor_git_integration(git_integration):
    while True:
        metrics = {
            "queue_size": git_integration.get_queue_size(),
            "is_online": git_integration.is_online(),
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"Git Integration Metrics: {metrics}")
        
        # Process queue if online
        if metrics["is_online"] and metrics["queue_size"] > 0:
            processed = git_integration.process_queue()
            print(f"Processed {processed} commits")
        
        time.sleep(3600)  # Check every hour
```

## Future Enhancements

- [ ] Support for multiple remotes
- [ ] Compression for large learning data
- [ ] Automatic conflict resolution
- [ ] Git LFS for large files
- [ ] Webhook notifications on commit
- [ ] Dashboard for commit history
- [ ] Automatic README.md generation

## References

- [GitPython Documentation](https://gitpython.readthedocs.io/)
- [GitHub Authentication](https://docs.github.com/en/authentication)
- [Git Best Practices](https://git-scm.com/book/en/v2)
- [Exponential Backoff](https://en.wikipedia.org/wiki/Exponential_backoff)
