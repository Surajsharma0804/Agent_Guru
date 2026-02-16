# Design Document: Agent Orchestration System

## Overview

The Agent Orchestration System is the central coordination layer for AGENT_GURU that transforms voice commands into executed actions. This system bridges the gap between what users say ("Hey Guru, open YouTube and play music") and what the system does (opens browser, navigates to YouTube, clicks play).

**Core Responsibilities**:
1. **Voice Command Decomposition**: Break complex voice commands into discrete sub-tasks
2. **Multi-Step Coordination**: Execute tasks in the correct order with dependency management
3. **Component Integration**: Coordinate speech, LLM, platform, policy, and memory systems
4. **Error Recovery**: Handle failures gracefully with fallback strategies
5. **Personality Coordination**: Maintain context for Guru and Maya personalities

**Voice Command Execution Flow**:
```
User: "Hey Guru, open YouTube and play music"
        ↓
1. Speech Engine: Transcribe audio → "open YouTube and play music"
2. Agent Orchestration: Decompose command
   - Sub-task 1: Open YouTube
   - Sub-task 2: Play music
3. Policy Engine: Check permissions for each sub-task
4. Platform Integration: Execute sub-tasks
   - Open browser
   - Navigate to YouTube
   - Simulate play button click
5. Memory System: Store interaction
6. Response: "YouTube opened and playing music"
```

**Multi-Step Operation Examples**:
- "Send a message to John saying I'll be late" → Open messaging app + Find contact + Type message + Send
- "Create a document called Meeting Notes and write the agenda" → Open text editor + Create file + Type content + Save
- "Search for Python tutorials and open the first result" → Open browser + Search + Click first link
- "Take a screenshot and email it to Sarah" → Capture screen + Open email + Attach file + Send

The design leverages industry-standard Python frameworks:
- **LangChain/LangGraph**: For agent coordination patterns and workflow orchestration
- **asyncio**: For concurrent task execution and non-blocking I/O
- **Pydantic**: For data validation and settings management
- **SQLite**: For persistent storage of audit trails and metrics

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Multi-Agent Orchestrator                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Agent Registry & Lifecycle                 │ │
│  │  - Agent metadata storage                              │ │
│  │  - Capability indexing                                 │ │
│  │  - Status tracking                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Task Decomposition & Assignment              │ │
│  │  - Capability-based decomposition                     │ │
│  │  - Load-balanced assignment                           │ │
│  │  - Dependency resolution                              │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Communication Layer                        │ │
│  │  - Direct messaging (asyncio queues)                  │ │
│  │  - Publish-subscribe (topic routing)                  │ │
│  │  - Message envelope handling                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │          Conflict Detection & Resolution               │ │
│  │  - Resource contention detection                      │ │
│  │  - Dependency cycle detection                         │ │
│  │  - Priority-based resolution                          │ │
│  │  - Load balancing strategies                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Resource Management & Monitoring               │ │
│  │  - Resource allocation tracking                       │ │
│  │  - Performance metrics collection                     │ │
│  │  - System health monitoring                           │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Audit Trail & Compliance                  │ │
│  │  - Event logging (SQLite)                             │ │
│  │  - Audit entry creation                               │ │
│  │  - Query interface                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │ Agent  │          │ Agent  │          │ Agent  │
    │   A    │          │   B    │          │   C    │
    └────────┘          └────────┘          └────────┘
```

### Design Principles

1. **Asynchronous-First**: All I/O operations use asyncio for non-blocking execution
2. **Type Safety**: Pydantic models for all data structures with runtime validation
3. **Immutable Messages**: Message envelopes are immutable after creation
4. **Event-Driven**: Publish-subscribe pattern for loose coupling between agents
5. **Fail-Fast**: Validate inputs early and provide clear error messages
6. **Observable**: Comprehensive metrics and audit trail for debugging and monitoring

## Components and Interfaces

### Core Data Models

All data models use Pydantic for validation and serialization:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class AgentId(BaseModel):
    """Unique identifier for an agent."""
    agent_type: str = Field(..., min_length=1)
    instance_key: str = Field(..., min_length=1)
    namespace: str = Field(default="default")
    
    def to_string(self) -> str:
        return f"{self.agent_type}:{self.instance_key}@{self.namespace}"
    
    class Config:
        frozen = True  # Immutable

class TopicId(BaseModel):
    """Identifier for publish-subscribe topics."""
    topic_type: str = Field(..., regex=r'^[\w\-\.\:\=]+$')
    source: str = Field(..., min_length=1)
    
    def to_string(self) -> str:
        return f"{self.topic_type}/{self.source}"
    
    class Config:
        frozen = True

class ResourceRequirements(BaseModel):
    """Resource requirements for agent operations."""
    cpu_cores: float = Field(default=0.1, ge=0.0)
    memory_mb: int = Field(default=100, ge=0)
    disk_mb: int = Field(default=50, ge=0)
    network_bandwidth_mbps: float = Field(default=1.0, ge=0.0)
    gpu_memory_mb: Optional[int] = Field(default=None, ge=0)
    specialized_hardware: List[str] = Field(default_factory=list)

class PerformanceMetrics(BaseModel):
    """Performance metrics for monitoring."""
    average_response_time_ms: float = Field(default=0.0, ge=0.0)
    throughput_per_second: float = Field(default=0.0, ge=0.0)
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    resource_utilization: float = Field(default=0.0, ge=0.0)
    last_updated: datetime = Field(default_factory=datetime.now)

class AgentStatus(str, Enum):
    """Agent operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    ERROR = "error"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"

class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class ConflictType(str, Enum):
    """Types of agent conflicts."""
    RESOURCE_CONTENTION = "resource_contention"
    TASK_DEPENDENCY = "task_dependency"
    PRIORITY_CONFLICT = "priority_conflict"
    CAPABILITY_OVERLAP = "capability_overlap"
    COMMUNICATION_DEADLOCK = "communication_deadlock"

class ResolutionStrategy(str, Enum):
    """Conflict resolution strategies."""
    PRIORITY_BASED = "priority_based"
    RESOURCE_REALLOCATION = "resource_reallocation"
    TASK_RESCHEDULING = "task_rescheduling"
    AGENT_REASSIGNMENT = "agent_reassignment"
    LOAD_BALANCING = "load_balancing"
```

### MultiAgentOrchestrator Class

The main orchestrator class manages all coordination:

```python
class MultiAgentOrchestrator:
    """
    Production-grade multi-agent orchestration system.
    
    Provides:
    - Agent registration and lifecycle management
    - Task decomposition and assignment
    - Conflict detection and resolution
    - Performance monitoring
    - Audit trail
    """
    
    def __init__(
        self,
        max_agents: int = 10000,
        max_concurrent_tasks: int = 1000,
        task_timeout_seconds: int = 300,
        heartbeat_interval_ms: int = 1000,
        audit_db_path: str = "orchestrator_audit.db"
    ):
        """Initialize orchestrator with configuration."""
        self.max_agents = max_agents
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = timedelta(seconds=task_timeout_seconds)
        self.heartbeat_interval = timedelta(milliseconds=heartbeat_interval_ms)
        
        # Core state
        self.agents: Dict[AgentId, AgentMetadata] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.active_tasks: Dict[str, Task] = {}
        self.subtasks: Dict[str, SubTask] = {}
        
        # Communication
        self.agent_channels: Dict[AgentId, asyncio.Queue] = {}
        
        # Conflict resolution
        self.active_conflicts: Dict[str, AgentConflict] = {}
        self.resolution_history: List[ConflictResolution] = []
        
        # Resource management
        self.available_resources = ResourceRequirements()
        self.resource_allocations: Dict[AgentId, ResourceRequirements] = {}
        
        # Monitoring
        self.system_metrics = SystemMetrics()
        
        # Audit trail (SQLite)
        self.audit_db = AuditDatabase(audit_db_path)
        
        # Thread safety
        self._lock = asyncio.Lock()
    
    async def register_agent(
        self,
        agent_id: AgentId,
        capabilities: List[AgentCapability],
        resource_requirements: ResourceRequirements
    ) -> None:
        """Register a new agent with the orchestrator."""
        
    async def decompose_task(self, task: Task) -> List[SubTask]:
        """Decompose a complex task into subtasks."""
        
    async def coordinate_execution(
        self,
        subtasks: List[SubTask]
    ) -> List[TaskResult]:
        """Coordinate execution of subtasks with conflict resolution."""
        
    async def publish_message(self, message: MessageEnvelope) -> None:
        """Publish message to all subscribed agents."""
        
    async def send_message(self, message: MessageEnvelope) -> None:
        """Send direct message to specific agent."""
        
    async def detect_conflicts(
        self,
        subtasks: List[SubTask]
    ) -> List[AgentConflict]:
        """Detect conflicts between assigned subtasks."""
        
    async def resolve_conflicts(
        self,
        conflicts: List[AgentConflict]
    ) -> List[ConflictResolution]:
        """Resolve conflicts using appropriate strategies."""
        
    async def update_agent_status(
        self,
        agent_id: AgentId,
        status: AgentStatus
    ) -> None:
        """Update agent status and record in audit trail."""
        
    async def get_system_metrics(self) -> SystemMetrics:
        """Get current system performance metrics."""
        
    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator."""
```

### Agent Communication

Communication uses asyncio queues for direct messaging and topic-based routing for publish-subscribe:

```python
class MessageEnvelope(BaseModel):
    """Message envelope for agent communication."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: Optional[AgentId] = None
    recipient: Optional[AgentId] = None
    topic_id: Optional[TopicId] = None
    message_type: str
    payload: bytes
    timestamp: datetime = Field(default_factory=datetime.now)
    is_rpc: bool = False
    correlation_id: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        frozen = True  # Immutable after creation

class Subscription(BaseModel):
    """Topic subscription for an agent."""
    subscription_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: AgentId
    topic_pattern: str
    message_types: List[str]
    priority: int = 100
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    
    def matches_topic(self, topic_id: TopicId) -> bool:
        """Check if subscription matches a topic."""
        if not self.is_active:
            return False
        
        if self.topic_pattern == "*":
            return True
        
        if self.topic_pattern.endswith("*"):
            prefix = self.topic_pattern[:-1]
            return topic_id.topic_type.startswith(prefix)
        
        return self.topic_pattern == topic_id.topic_type
```

### Task Management

Task decomposition and execution coordination:

```python
class Task(BaseModel):
    """Task definition for multi-agent coordination."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    task_type: str
    priority: int = Field(default=100, ge=0)
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    input_data: Dict[str, bytes] = Field(default_factory=dict)
    expected_output_types: List[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    deadline: Optional[datetime] = None

class SubTask(BaseModel):
    """Subtask for task decomposition."""
    subtask_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str
    assigned_agent: Optional[AgentId] = None
    task_definition: Task
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    execution_start: Optional[datetime] = None
    execution_end: Optional[datetime] = None

class TaskResult(BaseModel):
    """Task execution result."""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    success: bool
    output_data: Dict[str, bytes] = Field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: int
    resource_usage: ResourceUsage
    metadata: Dict[str, str] = Field(default_factory=dict)
```

### Conflict Resolution

Conflict detection and resolution mechanisms:

```python
class AgentConflict(BaseModel):
    """Agent conflict definition."""
    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_type: ConflictType
    involved_agents: List[AgentId]
    resource_contention: Optional[str] = None
    task_dependencies: List[str] = Field(default_factory=list)
    priority_conflicts: List[tuple[AgentId, int]] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.now)

class ConflictResolution(BaseModel):
    """Conflict resolution outcome."""
    resolution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_id: str
    strategy: ResolutionStrategy
    affected_agents: List[AgentId]
    resource_reallocation: Dict[str, AgentId] = Field(default_factory=dict)
    task_reassignments: Dict[str, AgentId] = Field(default_factory=dict)
    priority_adjustments: Dict[AgentId, int] = Field(default_factory=dict)
    resolved_at: datetime = Field(default_factory=datetime.now)
```

### Audit Trail

SQLite-based audit trail for compliance:

```python
class AuditEntry(BaseModel):
    """Audit trail entry."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    agent_id: Optional[AgentId] = None
    task_id: Optional[str] = None
    details: Dict[str, str] = Field(default_factory=dict)
    success: bool

class AuditDatabase:
    """SQLite-based audit trail storage."""
    
    def __init__(self, db_path: str):
        """Initialize audit database."""
        self.db_path = db_path
        self._init_schema()
    
    def _init_schema(self) -> None:
        """Create audit trail table schema."""
        
    async def add_entry(self, entry: AuditEntry) -> None:
        """Add audit entry to database."""
        
    async def query_entries(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        agent_id: Optional[AgentId] = None
    ) -> List[AuditEntry]:
        """Query audit entries with filters."""
```

## Data Models

### Agent Metadata

```python
class AgentCapability(BaseModel):
    """Agent capability definition."""
    capability_id: str
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    resource_requirements: ResourceRequirements
    performance_metrics: PerformanceMetrics

class AgentMetadata(BaseModel):
    """Agent metadata and state."""
    agent_id: AgentId
    capabilities: List[AgentCapability]
    current_status: AgentStatus
    performance_metrics: PerformanceMetrics
    resource_usage: ResourceUsage
    subscriptions: List[Subscription] = Field(default_factory=list)
    active_tasks: List[str] = Field(default_factory=list)
    last_heartbeat: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

class ResourceUsage(BaseModel):
    """Resource usage tracking."""
    cpu_time_ms: int = 0
    memory_peak_mb: int = 0
    disk_io_mb: int = 0
    network_io_mb: int = 0
    gpu_time_ms: Optional[int] = None
```

### System Metrics

```python
class SystemMetrics(BaseModel):
    """System-wide performance metrics."""
    total_agents: int = 0
    active_agents: int = 0
    total_tasks_processed: int = 0
    active_tasks: int = 0
    average_task_completion_time_ms: float = 0.0
    system_throughput_per_second: float = 0.0
    resource_utilization: float = 0.0
    error_rate: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.now)
```

## Correctness Properties


A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Agent Registration Validation
*For any* agent registration request, the orchestrator should validate all capability and resource requirement fields according to Pydantic schema rules, rejecting invalid registrations with descriptive errors.
**Validates: Requirements 1.1**

### Property 2: Unique Identifier Assignment
*For any* set of registered agents and subscriptions, all agent IDs and subscription IDs should be unique across the system.
**Validates: Requirements 1.2, 10.6**

### Property 3: Status Change Propagation
*For any* agent status change, the orchestrator should update both the agent metadata and create a corresponding audit trail entry with matching timestamps.
**Validates: Requirements 1.5**

### Property 4: Task Decomposition Correctness
*For any* task with required capabilities, decomposition should produce subtasks where each subtask's required capabilities are a subset of the original task's capabilities, and the union of all subtask capabilities equals the original task's capabilities.
**Validates: Requirements 2.1**

### Property 5: Capable Agent Availability
*For any* successfully decomposed task, every subtask should have at least one registered agent with matching capabilities in Ready status.
**Validates: Requirements 2.2**

### Property 6: Optimal Agent Selection
*For any* subtask assignment, the selected agent should have the lowest load score among all agents with the required capabilities.
**Validates: Requirements 2.4**

### Property 7: Load Balancing Distribution
*For any* set of subtasks with the same capability requirement and multiple capable agents, the distribution of assignments should minimize the maximum load across agents (within 20% variance).
**Validates: Requirements 2.5**

### Property 8: Dependency Order Preservation
*For any* task with dependencies, if task A depends on task B, then task B should be assigned and executed before task A in the coordination sequence.
**Validates: Requirements 2.6**

### Property 9: Direct Message Delivery
*For any* direct message with a valid recipient agent ID, the message should be delivered to that agent's communication queue.
**Validates: Requirements 3.1**

### Property 10: Publish-Subscribe Delivery
*For any* message published to a topic, all agents with active subscriptions matching that topic should receive the message.
**Validates: Requirements 3.2**

### Property 11: Subscription Routing
*For any* subscription and message, if the subscription's pattern matches the message's topic and the subscription is active, then the message should be routed to the subscribed agent.
**Validates: Requirements 3.4**

### Property 12: Unsubscribe Round Trip
*For any* agent, subscribing to a topic then immediately unsubscribing should result in no messages being routed to that agent for that topic.
**Validates: Requirements 3.5**

### Property 13: Audit Trail Completeness
*For any* orchestration event (agent registration, status change, message send/publish, conflict resolution), an audit entry should be created with event type, timestamp, involved entities, and success status.
**Validates: Requirements 3.6, 8.1, 8.2, 8.3, 8.4, 8.7**

### Property 14: Resource Contention Detection
*For any* set of subtask assignments where the sum of resource requirements for tasks assigned to a single agent exceeds that agent's capacity, a resource contention conflict should be detected.
**Validates: Requirements 4.1**

### Property 15: Deadlock Detection
*For any* set of task dependencies forming a cycle, a task dependency conflict should be detected.
**Validates: Requirements 4.2**

### Property 16: Priority Conflict Detection
*For any* set of agents with overlapping task assignments and different priority values, a priority conflict should be detected when priorities differ by more than a threshold.
**Validates: Requirements 4.3**

### Property 17: Conflict Resolution Load Balancing
*For any* resource contention conflict, the resolution should reassign tasks such that no agent exceeds its resource capacity.
**Validates: Requirements 4.5**

### Property 18: Deadlock Resolution
*For any* task dependency conflict, the resolution should reassign tasks such that the dependency graph becomes acyclic.
**Validates: Requirements 4.6**

### Property 19: Conflict Resolution History
*For any* resolved conflict, a resolution entry should be added to the history with conflict ID, strategy, affected agents, and resolution timestamp.
**Validates: Requirements 4.8**

### Property 20: Resource Allocation Tracking
*For any* set of registered agents, the sum of allocated resources across all agents should never exceed the available system resources.
**Validates: Requirements 5.1, 5.2**

### Property 21: Resource Deallocation Round Trip
*For any* agent, registering with resource requirements then deregistering should restore the available resources to their original state (within the allocated amount).
**Validates: Requirements 5.4**

### Property 22: Task Assignment Resource Verification
*For any* task assignment, the assigned agent's available resources should be sufficient for the task's resource requirements.
**Validates: Requirements 5.5**

### Property 23: Performance Metrics Update
*For any* task completion, the agent's performance metrics should be updated to reflect the execution time, success/failure status, and error rate using exponential moving average.
**Validates: Requirements 6.1, 6.4, 6.5**

### Property 24: Load Score Calculation
*For any* agent, the calculated load score should include contributions from active task count, resource utilization, average response time, and error rate.
**Validates: Requirements 6.2**

### Property 25: System Metrics Accuracy
*For any* system state, the returned system metrics should accurately reflect the current count of total agents, active agents, active tasks, and tasks processed.
**Validates: Requirements 6.3, 6.6**

### Property 26: Parallel Execution Independence
*For any* set of subtasks with no dependencies between them, they should be executed concurrently (all execution start times should be within a small time window).
**Validates: Requirements 7.1**

### Property 27: Result Collection Completeness
*For any* set of subtasks that complete successfully, all task results should be collected and returned, with each result containing execution time and resource usage data.
**Validates: Requirements 7.3, 7.6**

### Property 28: Task Status Lifecycle
*For any* task execution, the status transitions should follow the sequence: PENDING → ASSIGNED → IN_PROGRESS → (COMPLETED | FAILED | TIMEOUT), with no invalid transitions.
**Validates: Requirements 7.5**

### Property 29: Audit Trail Chronological Order
*For any* audit trail query, the returned entries should be ordered by timestamp in ascending order.
**Validates: Requirements 8.6**

### Property 30: Resource Configuration Storage
*For any* resource configuration set on the orchestrator, querying the available resources should return the same configuration values.
**Validates: Requirements 9.2**

### Property 31: Topic Pattern Validation
*For any* subscription creation, the topic pattern should be validated against the CloudEvents specification regex (alphanumeric plus `-`, `.`, `:`, `=`), rejecting invalid patterns.
**Validates: Requirements 10.1**

### Property 32: Wildcard Pattern Matching
*For any* subscription with a wildcard pattern (`*` or prefix with `*`), it should match all topics that fit the pattern according to the matching rules.
**Validates: Requirements 10.2, 10.5**

### Property 33: Multiple Subscriber Delivery
*For any* message published to a topic with multiple matching subscriptions, all subscribed agents should receive the message.
**Validates: Requirements 10.3**

### Property 34: Inactive Subscription Filtering
*For any* subscription marked as inactive, no messages should be delivered to that subscription regardless of topic matching.
**Validates: Requirements 10.4**

## Error Handling

### Error Types

The system defines comprehensive error types using Python exceptions:

```python
class OrchestrationError(Exception):
    """Base exception for orchestration errors."""
    pass

class AgentNotFoundError(OrchestrationError):
    """Agent not found in registry."""
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")

class TaskDecompositionError(OrchestrationError):
    """Task decomposition failed."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Task decomposition failed: {reason}")

class ResourceAllocationError(OrchestrationError):
    """Resource allocation failed."""
    def __init__(self, resource_type: str):
        self.resource_type = resource_type
        super().__init__(f"Resource allocation failed: {resource_type}")

class ConflictResolutionTimeoutError(OrchestrationError):
    """Conflict resolution timed out."""
    pass

class CommunicationError(OrchestrationError):
    """Agent communication failed."""
    def __init__(self, details: str):
        self.details = details
        super().__init__(f"Communication failed: {details}")

class TaskTimeoutError(OrchestrationError):
    """Task execution timed out."""
    pass

class SystemOverloadError(OrchestrationError):
    """System is overloaded."""
    def __init__(self, current_load: float):
        self.current_load = current_load
        super().__init__(f"System overload: {current_load:.2%}")
```

### Error Handling Strategy

1. **Validation Errors**: Caught at the Pydantic model level, raised immediately
2. **Resource Errors**: Checked before allocation, fail-fast with descriptive messages
3. **Timeout Errors**: Handled using asyncio.timeout context managers
4. **Communication Errors**: Caught at queue operations, logged and re-raised
5. **Conflict Errors**: Logged with full context, resolution attempted with timeout

### Error Recovery

- **Agent Failures**: Mark agent as offline, reassign tasks to other agents
- **Task Failures**: Record in result, update metrics, optionally retry
- **Communication Failures**: Log error, create audit entry, notify caller
- **Resource Exhaustion**: Reject new requests, trigger load balancing
- **Deadlocks**: Detect via conflict resolution, break cycles through reassignment

## Testing Strategy

### Dual Testing Approach

The system requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests** (pytest):
- Specific examples of agent registration, task decomposition, message routing
- Edge cases: maximum agent limit, resource exhaustion, timeout scenarios
- Error conditions: invalid inputs, missing agents, communication failures
- Integration points: audit database, asyncio queues, Pydantic validation
- Shutdown and cleanup behavior

**Property-Based Tests** (hypothesis):
- Universal properties across all inputs using randomized test data
- Minimum 100 iterations per property test
- Each property test references its design document property number
- Tag format: `# Feature: guru-agent-orchestration, Property N: <property_text>`

### Property-Based Testing Configuration

Using the `hypothesis` library for Python:

```python
from hypothesis import given, settings, strategies as st
import pytest

# Configure hypothesis for production-grade testing
@settings(max_examples=100, deadline=None)
@given(
    agent_id=st.builds(AgentId, ...),
    capabilities=st.lists(st.builds(AgentCapability, ...), min_size=1),
    resources=st.builds(ResourceRequirements, ...)
)
async def test_property_1_agent_registration_validation(
    orchestrator, agent_id, capabilities, resources
):
    """
    Feature: guru-agent-orchestration, Property 1: Agent Registration Validation
    
    For any agent registration request, the orchestrator should validate
    all capability and resource requirement fields according to Pydantic
    schema rules, rejecting invalid registrations with descriptive errors.
    """
    # Test implementation
```

### Test Organization

```
tests/
├── unit/
│   ├── test_agent_registration.py
│   ├── test_task_decomposition.py
│   ├── test_communication.py
│   ├── test_conflict_resolution.py
│   ├── test_resource_management.py
│   ├── test_performance_monitoring.py
│   └── test_audit_trail.py
├── property/
│   ├── test_properties_agent_lifecycle.py
│   ├── test_properties_task_management.py
│   ├── test_properties_communication.py
│   ├── test_properties_conflict_resolution.py
│   ├── test_properties_resource_management.py
│   └── test_properties_monitoring.py
└── integration/
    ├── test_end_to_end_orchestration.py
    └── test_multi_agent_scenarios.py
```

### Testing Tools

- **pytest**: Test framework and runner
- **pytest-asyncio**: Async test support
- **hypothesis**: Property-based testing
- **pytest-cov**: Code coverage measurement (target: 90%+)
- **pytest-benchmark**: Performance benchmarking
- **pytest-timeout**: Test timeout enforcement

### Quality Gates

All tests must pass before code is committed:
- Unit tests: 100% pass rate
- Property tests: 100% pass rate (100 iterations each)
- Code coverage: ≥90%
- Type checking: mypy strict mode, zero errors
- Linting: flake8 zero errors, pylint ≥9.0/10
- Formatting: black, zero changes needed

## Implementation Notes

### Python-Specific Considerations

1. **Asyncio**: All I/O operations use async/await for non-blocking execution
2. **Type Hints**: Full type annotations using Python 3.10+ syntax
3. **Pydantic**: Data validation and serialization for all models
4. **SQLite**: Lightweight, embedded database for audit trail
5. **Threading**: Use asyncio.Lock for thread-safe operations on shared state

### Performance Optimizations

1. **Connection Pooling**: Reuse SQLite connections for audit trail
2. **Batch Operations**: Batch audit entries for database writes
3. **Lazy Loading**: Load agent metadata only when needed
4. **Caching**: Cache capability lookups and load scores
5. **Async Execution**: Parallel subtask execution using asyncio.gather

### Migration from Rust

Key differences from the Rust implementation:

1. **Memory Management**: Python's GC vs Rust's ownership (no manual Arc/RwLock)
2. **Concurrency**: asyncio vs tokio (similar patterns, different syntax)
3. **Error Handling**: Exceptions vs Result types (more Pythonic)
4. **Type Safety**: Runtime validation (Pydantic) vs compile-time (Rust)
5. **Performance**: Acceptable for AI workloads, profile if needed

### Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.10"
pydantic = "^2.0"
langchain = "^0.1.0"
langgraph = "^0.0.20"
aiosqlite = "^0.19.0"
hypothesis = "^6.92"
pytest = "^7.4"
pytest-asyncio = "^0.21"
pytest-cov = "^4.1"
mypy = "^1.7"
black = "^23.12"
flake8 = "^6.1"
pylint = "^3.0"
```
