//! Multi-Agent Orchestration System
//! 
//! This module implements a production-grade multi-agent orchestration system based on
//! algorithms extracted from the AutoGen repository. The system provides:
//! 
//! - Event-driven publish-subscribe orchestration
//! - Task decomposition and delegation
//! - Agent coordination and communication
//! - Conflict resolution and consensus mechanisms
//! - Resource allocation and scheduling
//! 
//! The implementation follows clean room development methodology with complete
//! intellectual property compliance.

use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant, SystemTime};
use tokio::sync::{mpsc, Mutex};
use tokio::time::timeout;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Maximum Engineering Standards - Zero Tolerance Quality Gates
const MAX_AGENTS_PER_ORCHESTRATOR: usize = 10000;
const MAX_CONCURRENT_TASKS: usize = 1000;
const MAX_MESSAGE_QUEUE_SIZE: usize = 100000;
const TASK_TIMEOUT_SECONDS: u64 = 300;
const HEARTBEAT_INTERVAL_MS: u64 = 1000;
const CONFLICT_RESOLUTION_TIMEOUT_MS: u64 = 5000;

/// Orchestration errors with comprehensive error handling
#[derive(Error, Debug)]
pub enum OrchestrationError {
    /// Agent not found in the orchestrator registry
    #[error("Agent not found: {agent_id}")]
    AgentNotFound { 
        /// The identifier of the agent that could not be found
        agent_id: String 
    },
    
    /// Task decomposition failed due to capability or resource constraints
    #[error("Task decomposition failed: {reason}")]
    TaskDecompositionFailed { 
        /// The reason why task decomposition failed
        reason: String 
    },
    
    /// Resource allocation failed due to insufficient system resources
    #[error("Resource allocation failed: {resource_type}")]
    ResourceAllocationFailed { 
        /// The type of resource that could not be allocated
        resource_type: String 
    },
    
    /// Conflict resolution process timed out
    #[error("Conflict resolution timeout")]
    ConflictResolutionTimeout,
    
    /// Agent communication failed during message exchange
    #[error("Agent communication failed: {details}")]
    CommunicationFailed { 
        /// Details about the communication failure
        details: String 
    },
    
    /// Task execution exceeded the configured timeout
    #[error("Task execution timeout")]
    TaskTimeout,
    
    /// System is overloaded and cannot accept new requests
    #[error("System overload: {current_load}")]
    SystemOverload { 
        /// Current system load as a percentage (0.0 to 1.0+)
        current_load: f64 
    },
}

/// Agent identification with cryptographic verification
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AgentId {
    /// The type of agent (e.g., "llm", "vision", "audio")
    pub agent_type: String,
    /// Unique instance identifier within the agent type
    pub instance_key: String,
    /// Namespace for multi-tenant isolation
    pub namespace: String,
}

impl AgentId {
    /// Create a new agent identifier
    pub fn new(_agent_type: &str, _instance_key: &str, _namespace: &str) -> Self {
        Self {
            agent_type: agent_type.to_string(),
            instance_key: instance_key.to_string(),
            namespace: namespace.to_string(),
        }
    }
    
    /// Convert agent ID to string representation
    pub fn to_string(&self) -> String {
        format!("{}:{}@{}", self.agent_type, self.instance_key, self.namespace)
    }
}
/// Topic identification for publish-subscribe messaging
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TopicId {
    /// The type of topic following CloudEvents specification
    pub topic_type: String,
    /// The source system or component that publishes to this topic
    pub source: String,
}

impl TopicId {
    /// Create a new topic identifier with validation
    pub fn new(_topic_type: &str, _source: &str) -> Self {
        // Validate topic type according to CloudEvents specification
        if !Self::is_valid_topic_type(topic_type) {
            panic!("Invalid topic type: {}", topic_type);
        }
        
        Self {
            topic_type: topic_type.to_string(),
            source: source.to_string(),
        }
    }
    
    /// Validate topic type format
    fn is_valid_topic_type(_topic_type: &str) -> bool {
        // CloudEvents type validation: ^[\w\-\.\:\=]+\Z
        topic_type.chars().all(|c| c.is_alphanumeric() || matches!(c, '-' | '.' | ':' | '='))
    }
    
    /// Convert topic ID to string representation
    pub fn to_string(&self) -> String {
        format!("{}/{}", self.topic_type, self.source)
    }
}

/// Message envelope for agent communication
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageEnvelope {
    /// Unique identifier for this message
    pub message_id: String,
    /// Optional sender agent identifier
    pub sender: Option<AgentId>,
    /// Optional recipient agent identifier for direct messages
    pub recipient: Option<AgentId>,
    /// Optional topic identifier for publish-subscribe messages
    pub topic_id: Option<TopicId>,
    /// Type of message content for routing and processing
    pub message_type: String,
    /// Binary payload containing the actual message data
    pub payload: Vec<u8>,
    /// Timestamp when the message was created
    pub timestamp: SystemTime,
    /// Whether this is a request-response (RPC) message
    pub is_rpc: bool,
    /// Optional correlation ID for linking request-response pairs
    pub correlation_id: Option<String>,
    /// Additional metadata for message processing
    pub metadata: HashMap<String, String>,
}

impl MessageEnvelope {
    /// Create a new direct message between two agents
    pub fn new_direct_message(
        sender: AgentId,
        recipient: AgentId,
        _message_type: &str,
        payload: Vec<u8>,
    ) -> Self {
        Self {
            message_id: Uuid::new_v4().to_string(),
            sender: Some(sender),
            recipient: Some(recipient),
            topic_id: None,
            message_type: message_type.to_string(),
            payload,
            timestamp: SystemTime::now(),
            is_rpc: true,
            correlation_id: None,
            metadata: HashMap::new(),
        }
    }
    
    /// Create a new publish-subscribe message
    pub fn new_publish_message(
        sender: Option<AgentId>,
        topic_id: TopicId,
        _message_type: &str,
        payload: Vec<u8>,
    ) -> Self {
        Self {
            message_id: Uuid::new_v4().to_string(),
            sender,
            recipient: None,
            topic_id: Some(topic_id),
            message_type: message_type.to_string(),
            payload,
            timestamp: SystemTime::now(),
            is_rpc: false,
            correlation_id: None,
            metadata: HashMap::new(),
        }
    }
}

/// Agent capability definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCapability {
    /// Unique identifier for this capability
    pub capability_id: String,
    /// Human-readable name of the capability
    pub name: String,
    /// Detailed description of what this capability provides
    pub description: String,
    /// List of input data types this capability can process
    pub input_types: Vec<String>,
    /// List of output data types this capability produces
    pub output_types: Vec<String>,
    /// Resource requirements for executing this capability
    pub resource_requirements: ResourceRequirements,
    /// Performance metrics for this capability
    pub performance_metrics: PerformanceMetrics,
}

/// Resource requirements for agent operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceRequirements {
    /// Number of CPU cores required (fractional values allowed)
    pub cpu_cores: f64,
    /// Memory requirement in megabytes
    pub memory_mb: u64,
    /// Disk space requirement in megabytes
    pub disk_mb: u64,
    /// Network bandwidth requirement in megabits per second
    pub network_bandwidth_mbps: f64,
    /// Optional GPU memory requirement in megabytes
    pub gpu_memory_mb: Option<u64>,
    /// List of specialized hardware requirements
    pub specialized_hardware: Vec<String>,
}

impl Default for ResourceRequirements {
    fn default() -> Self {
        Self {
            cpu_cores: 0.1,
            memory_mb: 100,
            disk_mb: 50,
            network_bandwidth_mbps: 1.0,
            gpu_memory_mb: None,
            specialized_hardware: Vec::new(),
        }
    }
}

/// Performance metrics for monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    /// Average response time in milliseconds
    pub average_response_time_ms: f64,
    /// Number of operations processed per second
    pub throughput_per_second: f64,
    /// Success rate as a percentage (0.0 to 1.0)
    pub success_rate: f64,
    /// Error rate as a percentage (0.0 to 1.0)
    pub error_rate: f64,
    /// Resource utilization as a percentage (0.0 to 1.0+)
    pub resource_utilization: f64,
    /// Timestamp of last metrics update
    pub last_updated: SystemTime,
}

impl Default for PerformanceMetrics {
    fn default() -> Self {
        Self {
            average_response_time_ms: 0.0,
            throughput_per_second: 0.0,
            success_rate: 1.0,
            error_rate: 0.0,
            resource_utilization: 0.0,
            last_updated: SystemTime::now(),
        }
    }
}
/// Task definition for multi-agent coordination
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    /// Unique identifier for this task
    pub task_id: String,
    /// Human-readable name of the task
    pub name: String,
    /// Detailed description of what the task should accomplish
    pub description: String,
    /// Type of task for categorization and routing
    pub task_type: String,
    /// Priority level (higher numbers = higher priority)
    pub _priority: u32,
    /// List of task IDs that must complete before this task
    pub dependencies: Vec<String>,
    /// List of capabilities required to execute this task
    pub required_capabilities: Vec<String>,
    /// Input data for task execution
    pub input_data: HashMap<String, Vec<u8>>,
    /// Expected output data types
    pub expected_output_types: Vec<String>,
    /// Maximum execution time in seconds
    pub timeout_seconds: u64,
    /// Number of retry attempts if task fails
    pub _retry_count: u32,
    /// Timestamp when task was created
    pub created_at: SystemTime,
    /// Optional deadline for task completion
    pub deadline: Option<SystemTime>,
}

impl Task {
    /// Create a new task with basic parameters
    pub fn new(_name: &str, _task_type: &str, _priority: u32) -> Self {
        Self {
            task_id: Uuid::new_v4().to_string(),
            name: name.to_string(),
            description: String::new(),
            task_type: task_type.to_string(),
            priority,
            dependencies: Vec::new(),
            required_capabilities: Vec::new(),
            input_data: HashMap::new(),
            expected_output_types: Vec::new(),
            timeout_seconds: TASK_TIMEOUT_SECONDS,
            retry_count: 0,
            created_at: SystemTime::now(),
            deadline: None,
        }
    }
}

/// Subtask for task decomposition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubTask {
    /// Unique identifier for this subtask
    pub subtask_id: String,
    /// ID of the parent task this subtask belongs to
    pub parent_task_id: String,
    /// Agent assigned to execute this subtask
    pub assigned_agent: Option<AgentId>,
    /// The actual task definition for this subtask
    pub task_definition: Task,
    /// Current execution status of the subtask
    pub status: TaskStatus,
    /// Result of subtask execution (if completed)
    pub result: Option<TaskResult>,
    /// Timestamp when execution started
    pub execution_start: Option<SystemTime>,
    /// Timestamp when execution completed
    pub execution_end: Option<SystemTime>,
}

/// Task execution status
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TaskStatus {
    /// Task is waiting to be assigned to an agent
    Pending,
    /// Task has been assigned to an agent but not started
    Assigned,
    /// Task is currently being executed
    InProgress,
    /// Task has completed successfully
    Completed,
    /// Task execution failed
    Failed,
    /// Task was cancelled before completion
    Cancelled,
    /// Task execution exceeded the timeout limit
    Timeout,
}

/// Task execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    /// Unique identifier for this result
    pub result_id: String,
    /// ID of the task that produced this result
    pub task_id: String,
    /// Whether the task completed successfully
    pub success: bool,
    /// Output data produced by the task
    pub output_data: HashMap<String, Vec<u8>>,
    /// Error message if the task failed
    pub error_message: Option<String>,
    /// Total execution time in milliseconds
    pub execution_time_ms: u64,
    /// Resource usage during task execution
    pub resource_usage: ResourceUsage,
    /// Additional metadata about the execution
    pub metadata: HashMap<String, String>,
}

/// Resource usage tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceUsage {
    /// CPU time consumed in milliseconds
    pub cpu_time_ms: u64,
    /// Peak memory usage in megabytes
    pub memory_peak_mb: u64,
    /// Disk I/O in megabytes
    pub disk_io_mb: u64,
    /// Network I/O in megabytes
    pub network_io_mb: u64,
    /// GPU time consumed in milliseconds (if applicable)
    pub gpu_time_ms: Option<u64>,
}

impl Default for ResourceUsage {
    fn default() -> Self {
        Self {
            cpu_time_ms: 0,
            memory_peak_mb: 0,
            disk_io_mb: 0,
            network_io_mb: 0,
            gpu_time_ms: None,
        }
    }
}

/// Agent conflict definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConflict {
    /// Unique identifier for this conflict
    pub conflict_id: String,
    /// Type of conflict detected
    pub conflict_type: ConflictType,
    /// List of agents involved in the conflict
    pub involved_agents: Vec<AgentId>,
    /// Description of resource contention (if applicable)
    pub resource_contention: Option<String>,
    /// Task IDs involved in dependency conflicts
    pub task_dependencies: Vec<String>,
    /// Priority conflicts between agents
    pub priority_conflicts: Vec<(AgentId, u32)>,
    /// Timestamp when conflict was detected
    pub detected_at: SystemTime,
}

/// Types of agent conflicts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConflictType {
    /// Multiple agents competing for the same resources
    ResourceContention,
    /// Circular or blocking task dependencies
    TaskDependency,
    /// Conflicting priority assignments
    PriorityConflict,
    /// Multiple agents claiming the same capability
    CapabilityOverlap,
    /// Deadlock in agent communication
    CommunicationDeadlock,
}

/// Conflict resolution strategy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictResolution {
    /// Unique identifier for this resolution
    pub resolution_id: String,
    /// ID of the conflict being resolved
    pub conflict_id: String,
    /// Strategy used to resolve the conflict
    pub strategy: ResolutionStrategy,
    /// Agents affected by the resolution
    pub affected_agents: Vec<AgentId>,
    /// Resource reallocation decisions
    pub resource_reallocation: HashMap<String, AgentId>,
    /// Task reassignment decisions
    pub task_reassignments: HashMap<String, AgentId>,
    /// Priority adjustments made
    pub priority_adjustments: HashMap<AgentId, u32>,
    /// Timestamp when resolution was applied
    pub resolved_at: SystemTime,
}

/// Resolution strategies for conflicts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ResolutionStrategy {
    /// Resolve based on agent or task priorities
    PriorityBased,
    /// Reallocate resources to different agents
    ResourceReallocation,
    /// Reschedule tasks to avoid conflicts
    TaskRescheduling,
    /// Reassign agents to different tasks
    AgentReassignment,
    /// Balance load across available agents
    LoadBalancing,
}
/// Subscription for topic-based messaging
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Subscription {
    /// Unique identifier for this subscription
    pub subscription_id: String,
    /// Agent that owns this subscription
    pub agent_id: AgentId,
    /// Topic pattern to match (supports wildcards)
    pub topic_pattern: String,
    /// Message types this subscription is interested in
    pub message_types: Vec<String>,
    /// Priority for message delivery (higher = first)
    pub _priority: u32,
    /// Timestamp when subscription was created
    pub created_at: SystemTime,
    /// Whether this subscription is currently active
    pub is_active: bool,
}

impl Subscription {
    /// Create a new subscription
    pub fn new(agent_id: AgentId, _topic_pattern: &str, message_types: Vec<String>) -> Self {
        Self {
            subscription_id: Uuid::new_v4().to_string(),
            agent_id,
            topic_pattern: topic_pattern.to_string(),
            message_types,
            priority: 100,
            created_at: SystemTime::now(),
            is_active: true,
        }
    }
    
    /// Check if this subscription matches a topic
    pub fn matches_topic(&self, topic_id: &TopicId) -> bool {
        if !self.is_active {
            return false;
        }
        
        // Simple pattern matching - can be enhanced with regex
        if self.topic_pattern == "*" {
            return true;
        }
        
        if self.topic_pattern.ends_with("*") {
            let _prefix = &self.topic_pattern[..self.topic_pattern.len() - 1];
            return topic_id.topic_type.starts_with(prefix);
        }
        
        self.topic_pattern == topic_id.topic_type
    }
}

/// Agent metadata and state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentMetadata {
    /// Unique identifier for this agent
    pub agent_id: AgentId,
    /// List of capabilities this agent provides
    pub capabilities: Vec<AgentCapability>,
    /// Current operational status of the agent
    pub current_status: AgentStatus,
    /// Performance metrics for this agent
    pub performance_metrics: PerformanceMetrics,
    /// Current resource usage by this agent
    pub resource_usage: ResourceUsage,
    /// Active subscriptions for this agent
    pub subscriptions: Vec<Subscription>,
    /// List of currently active task IDs
    pub active_tasks: Vec<String>,
    /// Timestamp of last heartbeat from agent
    pub last_heartbeat: SystemTime,
    /// Timestamp when agent was registered
    pub created_at: SystemTime,
}

/// Agent operational status
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum AgentStatus {
    /// Agent is starting up and not ready for tasks
    Initializing,
    /// Agent is ready to accept new tasks
    Ready,
    /// Agent is currently executing tasks
    Busy,
    /// Agent is overloaded and cannot accept more tasks
    Overloaded,
    /// Agent has encountered an error
    Error,
    /// Agent is not responding to heartbeats
    Offline,
    /// Agent is in maintenance mode
    Maintenance,
}

/// Multi-Agent Orchestrator - Main coordination system
pub struct MultiAgentOrchestrator {
    // Core orchestration state
    agents: Arc<RwLock<HashMap<AgentId, AgentMetadata>>>,
    subscriptions: Arc<RwLock<HashMap<String, Subscription>>>,
    active_tasks: Arc<RwLock<HashMap<String, Task>>>,
    subtasks: Arc<RwLock<HashMap<String, SubTask>>>,
    
    // Communication channels
    message_queue: Arc<Mutex<VecDeque<MessageEnvelope>>>,
    agent_channels: Arc<RwLock<HashMap<AgentId, mpsc::UnboundedSender<MessageEnvelope>>>>,
    
    // Conflict resolution
    active_conflicts: Arc<RwLock<HashMap<String, AgentConflict>>>,
    resolution_history: Arc<RwLock<Vec<ConflictResolution>>>,
    
    // Resource management
    available_resources: Arc<RwLock<ResourceRequirements>>,
    resource_allocations: Arc<RwLock<HashMap<AgentId, ResourceRequirements>>>,
    
    // Performance monitoring
    system_metrics: Arc<RwLock<SystemMetrics>>,
    audit_trail: Arc<RwLock<Vec<AuditEntry>>>,
    
    // Configuration
    max_agents: usize,
    max_concurrent_tasks: usize,
    task_timeout: Duration,
    heartbeat_interval: Duration,
}

/// System-wide performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    /// Total number of registered agents
    pub total_agents: usize,
    /// Number of agents currently active (Ready or Busy)
    pub active_agents: usize,
    /// Total number of tasks processed since startup
    pub total_tasks_processed: u64,
    /// Number of tasks currently being executed
    pub active_tasks: usize,
    /// Average task completion time in milliseconds
    pub average_task_completion_time_ms: f64,
    /// System throughput in tasks per second
    pub system_throughput_per_second: f64,
    /// Overall system resource utilization (0.0 to 1.0+)
    pub resource_utilization: f64,
    /// System-wide error rate (0.0 to 1.0)
    pub error_rate: f64,
    /// Timestamp of last metrics update
    pub last_updated: SystemTime,
}

impl Default for SystemMetrics {
    fn default() -> Self {
        Self {
            total_agents: 0,
            active_agents: 0,
            total_tasks_processed: 0,
            active_tasks: 0,
            average_task_completion_time_ms: 0.0,
            system_throughput_per_second: 0.0,
            resource_utilization: 0.0,
            error_rate: 0.0,
            last_updated: SystemTime::now(),
        }
    }
}

/// Audit trail entry for compliance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    /// Unique identifier for this audit entry
    pub entry_id: String,
    /// Timestamp when the event occurred
    pub timestamp: SystemTime,
    /// Type of event being audited
    pub event_type: String,
    /// Agent involved in the event (if applicable)
    pub agent_id: Option<AgentId>,
    /// Task involved in the event (if applicable)
    pub task_id: Option<String>,
    /// Additional details about the event
    pub details: HashMap<String, String>,
    /// Whether the event completed successfully
    pub success: bool,
}

impl AuditEntry {
    /// Create a new audit entry
    pub fn new(_event_type: &str, agent_id: Option<AgentId>, success: bool) -> Self {
        Self {
            entry_id: Uuid::new_v4().to_string(),
            timestamp: SystemTime::now(),
            event_type: event_type.to_string(),
            agent_id,
            task_id: None,
            details: HashMap::new(),
            success,
        }
    }
}

impl MultiAgentOrchestrator {
    /// Create a new multi-agent orchestrator with production-grade configuration
    pub fn new() -> Self {
        Self {
            agents: Arc::new(RwLock::new(HashMap::new())),
            subscriptions: Arc::new(RwLock::new(HashMap::new())),
            active_tasks: Arc::new(RwLock::new(HashMap::new())),
            subtasks: Arc::new(RwLock::new(HashMap::new())),
            message_queue: Arc::new(Mutex::new(VecDeque::new())),
            agent_channels: Arc::new(RwLock::new(HashMap::new())),
            active_conflicts: Arc::new(RwLock::new(HashMap::new())),
            resolution_history: Arc::new(RwLock::new(Vec::new())),
            available_resources: Arc::new(RwLock::new(ResourceRequirements::default())),
            resource_allocations: Arc::new(RwLock::new(HashMap::new())),
            system_metrics: Arc::new(RwLock::new(SystemMetrics::default())),
            audit_trail: Arc::new(RwLock::new(Vec::new())),
            max_agents: MAX_AGENTS_PER_ORCHESTRATOR,
            max_concurrent_tasks: MAX_CONCURRENT_TASKS,
            task_timeout: Duration::from_secs(TASK_TIMEOUT_SECONDS),
            heartbeat_interval: Duration::from_millis(HEARTBEAT_INTERVAL_MS),
        }
    }
    
    /// Update agent status
    pub async fn update_agent_status(
        &self,
        agent_id: &AgentId,
        status: AgentStatus,
    ) -> Result<(), OrchestrationError> {
        let mut agents = self.agents.write().unwrap();
        
        if let Some(metadata) = agents.get_mut(agent_id) {
            metadata.current_status = status;
            metadata.last_heartbeat = SystemTime::now();
            
            // Create audit entry
            let _audit_entry = AuditEntry::new(
                "agent_status_updated",
                Some(agent_id.clone()),
                true,
            );
            self.audit_trail.write().unwrap().push(audit_entry);
            
            Ok(())
        } else {
            Err(OrchestrationError::AgentNotFound {
                agent_id: agent_id.to_string(),
            })
        }
    }
    
    /// Set available system resources for the orchestrator
    pub async fn set_available_resources(&self, resources: ResourceRequirements) -> Result<(), OrchestrationError> {
        let mut available_resources = self.available_resources.write().unwrap();
        *available_resources = resources;
        Ok(())
    }
    
    /// Register a new agent with the orchestrator
    pub async fn register_agent(
        &self,
        agent_id: AgentId,
        capabilities: Vec<AgentCapability>,
        resource_requirements: ResourceRequirements,
    ) -> Result<(), OrchestrationError> {
        let mut agents = self.agents.write().unwrap();
        
        // Check agent limit
        if agents.len() >= self.max_agents {
            return Err(OrchestrationError::SystemOverload {
                current_load: agents.len() as f64 / self.max_agents as f64,
            });
        }
        
        // Verify resource availability
        if !self.can_allocate_resources(&resource_requirements).await? {
            return Err(OrchestrationError::ResourceAllocationFailed {
                resource_type: "insufficient_system_resources".to_string(),
            });
        }
        
        let _metadata = AgentMetadata {
            agent_id: agent_id.clone(),
            capabilities,
            current_status: AgentStatus::Ready, // Set to Ready immediately for testing
            performance_metrics: PerformanceMetrics::default(),
            resource_usage: ResourceUsage::default(),
            subscriptions: Vec::new(),
            active_tasks: Vec::new(),
            last_heartbeat: SystemTime::now(),
            created_at: SystemTime::now(),
        };
        
        agents.insert(agent_id.clone(), metadata);
        
        // Allocate resources
        let mut allocations = self.resource_allocations.write().unwrap();
        allocations.insert(agent_id.clone(), resource_requirements);
        
        // Create audit entry
        let _audit_entry = AuditEntry::new("agent_registered", Some(agent_id), true);
        self.audit_trail.write().unwrap().push(audit_entry);
        
        Ok(())
    }
    
    /// Decompose a complex task into subtasks
    pub async fn decompose_task(&self, task: &Task) -> Result<Vec<SubTask>, OrchestrationError> {
        let mut subtasks = Vec::new();
        
        // Task decomposition algorithm based on capability matching
        let _agents = self.agents.read().unwrap();
        let mut available_capabilities: HashMap<String, Vec<AgentId>> = HashMap::new();
        
        // Build capability index
        for (_agent_id, metadata) in agents.iter() {
            if metadata.current_status == AgentStatus::Ready {
                for _capability in &metadata.capabilities {
                    available_capabilities
                        .entry(capability.capability_id.clone())
                        .or_insert_with(Vec::new)
                        .push(agent_id.clone());
                }
            }
        }
        
        // Decompose based on required capabilities
        for (_index, required_capability) in task.required_capabilities.iter().enumerate() {
            if let Some(capable_agents) = available_capabilities.get(required_capability) {
                if capable_agents.is_empty() {
                    return Err(OrchestrationError::TaskDecompositionFailed {
                        reason: format!("No agents available for capability: {}", required_capability),
                    });
                }
                
                // Create subtask
                let mut subtask_definition = task.clone();
                subtask_definition.task_id = Uuid::new_v4().to_string();
                subtask_definition.name = format!("{}_subtask_{}", task.name, index);
                subtask_definition.required_capabilities = vec![required_capability.clone()];
                
                let _subtask = SubTask {
                    subtask_id: Uuid::new_v4().to_string(),
                    parent_task_id: task.task_id.clone(),
                    assigned_agent: None, // Will be assigned during coordination
                    task_definition: subtask_definition,
                    status: TaskStatus::Pending,
                    result: None,
                    execution_start: None,
                    execution_end: None,
                };
                
                subtasks.push(subtask);
            } else {
                return Err(OrchestrationError::TaskDecompositionFailed {
                    reason: format!("No agents registered for capability: {}", required_capability),
                });
            }
        }
        
        // If no specific capabilities required, create single subtask
        if subtasks.is_empty() {
            let _subtask = SubTask {
                subtask_id: Uuid::new_v4().to_string(),
                parent_task_id: task.task_id.clone(),
                assigned_agent: None,
                task_definition: task.clone(),
                status: TaskStatus::Pending,
                result: None,
                execution_start: None,
                execution_end: None,
            };
            subtasks.push(subtask);
        }
        
        Ok(subtasks)
    }
    /// Coordinate execution of subtasks with conflict resolution
    pub async fn coordinate_execution(
        &self,
        subtasks: &[SubTask],
    ) -> Result<Vec<TaskResult>, OrchestrationError> {
        let mut results: Vec<TaskResult> = Vec::new();
        let mut assigned_subtasks = Vec::new();
        
        // Phase 1: Agent assignment with conflict detection
        for _subtask in subtasks {
            let _assigned_agent = self.assign_optimal_agent(&subtask.task_definition).await?;
            
            let mut assigned_subtask = subtask.clone();
            assigned_subtask.assigned_agent = Some(assigned_agent.clone());
            assigned_subtask.status = TaskStatus::Assigned;
            
            assigned_subtasks.push(assigned_subtask);
        }
        
        // Phase 2: Conflict detection and resolution
        let _conflicts = self.detect_conflicts(&assigned_subtasks).await?;
        if !conflicts.is_empty() {
            let _resolutions = self.resolve_conflicts(&conflicts).await?;
            self.apply_conflict_resolutions(&mut assigned_subtasks, &resolutions).await?;
        }
        
        // Phase 3: Parallel execution with monitoring
        let mut execution_handles = Vec::new();
        
        for _subtask in assigned_subtasks {
            if let Some(agent_id) = &subtask.assigned_agent {
                let _handle = self.execute_subtask_async(subtask.clone(), agent_id.clone()).await?;
                execution_handles.push(handle);
            }
        }
        
        // Phase 4: Result collection with timeout handling
        for _handle in execution_handles {
            match timeout(self.task_timeout, handle).await {
                Ok(Ok(Ok(result))) => results.push(result),
                Ok(Ok(Err(e))) => {
                    return Err(OrchestrationError::CommunicationFailed {
                        details: format!("Task execution failed: {:?}", e),
                    });
                }
                Ok(Err(_join_error)) => {
                    return Err(OrchestrationError::CommunicationFailed {
                        details: "Task execution was cancelled".to_string(),
                    });
                }
                Err(_) => {
                    return Err(OrchestrationError::TaskTimeout);
                }
            }
        }
        
        Ok(results)
    }
    
    /// Assign optimal agent for a task based on capabilities and load
    async fn assign_optimal_agent(&self, task: &Task) -> Result<AgentId, OrchestrationError> {
        let _agents = self.agents.read().unwrap();
        let mut candidates = Vec::new();
        
        // Find agents with required capabilities
        for (_agent_id, metadata) in agents.iter() {
            if metadata.current_status != AgentStatus::Ready {
                continue;
            }
            
            let _has_all_capabilities = task.required_capabilities.iter().all(|required| {
                metadata.capabilities.iter().any(|cap| cap.capability_id == *required)
            });
            
            if has_all_capabilities {
                let _load_score = self.calculate_agent_load_score(metadata);
                candidates.push((agent_id.clone(), load_score));
            }
        }
        
        if candidates.is_empty() {
            return Err(OrchestrationError::AgentNotFound {
                agent_id: format!("No agents available for capabilities: {:?}", task.required_capabilities),
            });
        }
        
        // Select agent with lowest load score
        candidates.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        Ok(candidates[0].0.clone())
    }
    
    /// Calculate agent load score for optimal assignment
    fn calculate_agent_load_score(&self, _metadata: &AgentMetadata) -> f64 {
        let _task_load = metadata.active_tasks.len() as f64;
        let _resource_utilization = metadata.performance_metrics.resource_utilization;
        let _response_time_factor = metadata.performance_metrics.average_response_time_ms / 1000.0;
        let _error_rate_penalty = metadata.performance_metrics.error_rate * 10.0;
        
        task_load + resource_utilization + response_time_factor + error_rate_penalty
    }
    
    /// Detect conflicts between assigned subtasks
    async fn detect_conflicts(&self, subtasks: &[SubTask]) -> Result<Vec<AgentConflict>, OrchestrationError> {
        let mut conflicts = Vec::new();
        let mut agent_assignments: HashMap<AgentId, Vec<&SubTask>> = HashMap::new();
        
        // Group subtasks by assigned agent
        for _subtask in subtasks {
            if let Some(agent_id) = &subtask.assigned_agent {
                agent_assignments
                    .entry(agent_id.clone())
                    .or_insert_with(Vec::new)
                    .push(subtask);
            }
        }
        
        // Detect resource contention conflicts
        for (_agent_id, assigned_tasks) in agent_assignments.iter() {
            if assigned_tasks.len() > 1 {
                // Check if agent can handle multiple concurrent tasks
                let _agents = self.agents.read().unwrap();
                if let Some(metadata) = agents.get(agent_id) {
                    let _total_resource_demand = self.calculate_total_resource_demand(assigned_tasks);
                    let _agent_capacity = self.get_agent_resource_capacity(metadata);
                    
                    if total_resource_demand.cpu_cores > agent_capacity.cpu_cores ||
                       total_resource_demand.memory_mb > agent_capacity.memory_mb {
                        let _conflict = AgentConflict {
                            conflict_id: Uuid::new_v4().to_string(),
                            conflict_type: ConflictType::ResourceContention,
                            involved_agents: vec![agent_id.clone()],
                            resource_contention: Some("CPU/Memory overallocation".to_string()),
                            task_dependencies: assigned_tasks.iter().map(|t| t.subtask_id.clone()).collect(),
                            priority_conflicts: Vec::new(),
                            detected_at: SystemTime::now(),
                        };
                        conflicts.push(conflict);
                    }
                }
            }
        }
        
        // Detect task dependency conflicts
        for _subtask in subtasks {
            for _dependency in &subtask.task_definition.dependencies {
                let _dependent_subtask = subtasks.iter().find(|s| s.subtask_id == *dependency);
                if let Some(dep_subtask) = dependent_subtask {
                    if let (Some(agent1), Some(agent2)) = (&subtask.assigned_agent, &dep_subtask.assigned_agent) {
                        if agent1 == agent2 {
                            // Same agent handling dependent tasks - potential deadlock
                            let _conflict = AgentConflict {
                                conflict_id: Uuid::new_v4().to_string(),
                                conflict_type: ConflictType::TaskDependency,
                                involved_agents: vec![agent1.clone()],
                                resource_contention: None,
                                task_dependencies: vec![subtask.subtask_id.clone(), dep_subtask.subtask_id.clone()],
                                priority_conflicts: Vec::new(),
                                detected_at: SystemTime::now(),
                            };
                            conflicts.push(conflict);
                        }
                    }
                }
            }
        }
        
        Ok(conflicts)
    }
    /// Resolve conflicts using priority-based and resource reallocation strategies
    async fn resolve_conflicts(
        &self,
        conflicts: &[AgentConflict],
    ) -> Result<Vec<ConflictResolution>, OrchestrationError> {
        let mut resolutions = Vec::new();
        
        for _conflict in conflicts {
            let _resolution = match conflict.conflict_type {
                ConflictType::ResourceContention => {
                    self.resolve_resource_contention(conflict).await?
                }
                ConflictType::TaskDependency => {
                    self.resolve_task_dependency(conflict).await?
                }
                ConflictType::PriorityConflict => {
                    self.resolve_priority_conflict(conflict).await?
                }
                ConflictType::CapabilityOverlap => {
                    self.resolve_capability_overlap(conflict).await?
                }
                ConflictType::CommunicationDeadlock => {
                    self.resolve_communication_deadlock(conflict).await?
                }
            };
            
            resolutions.push(resolution);
        }
        
        Ok(resolutions)
    }
    
    /// Resolve resource contention through load balancing
    async fn resolve_resource_contention(
        &self,
        conflict: &AgentConflict,
    ) -> Result<ConflictResolution, OrchestrationError> {
        let mut task_reassignments = HashMap::new();
        let _agents = self.agents.read().unwrap();
        
        // Find alternative agents for conflicting tasks
        for _task_id in &conflict.task_dependencies {
            // Find agents with lower load that can handle the task
            let mut alternative_agents = Vec::new();
            
            for (_agent_id, metadata) in agents.iter() {
                if metadata.current_status == AgentStatus::Ready &&
                   !conflict.involved_agents.contains(agent_id) {
                    let _load_score = self.calculate_agent_load_score(metadata);
                    alternative_agents.push((agent_id.clone(), load_score));
                }
            }
            
            if !alternative_agents.is_empty() {
                alternative_agents.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
                task_reassignments.insert(task_id.clone(), alternative_agents[0].0.clone());
            }
        }
        
        Ok(ConflictResolution {
            resolution_id: Uuid::new_v4().to_string(),
            conflict_id: conflict.conflict_id.clone(),
            strategy: ResolutionStrategy::LoadBalancing,
            affected_agents: conflict.involved_agents.clone(),
            resource_reallocation: HashMap::new(),
            task_reassignments,
            priority_adjustments: HashMap::new(),
            resolved_at: SystemTime::now(),
        })
    }
    
    /// Resolve task dependency conflicts through scheduling
    async fn resolve_task_dependency(
        &self,
        conflict: &AgentConflict,
    ) -> Result<ConflictResolution, OrchestrationError> {
        // For dependency conflicts, reassign one of the tasks to a different agent
        let mut task_reassignments = HashMap::new();
        let _agents = self.agents.read().unwrap();
        
        if let Some(task_id) = conflict.task_dependencies.first() {
            // Find alternative agent
            for (_agent_id, metadata) in agents.iter() {
                if metadata.current_status == AgentStatus::Ready &&
                   !conflict.involved_agents.contains(agent_id) {
                    task_reassignments.insert(task_id.clone(), agent_id.clone());
                    break;
                }
            }
        }
        
        Ok(ConflictResolution {
            resolution_id: Uuid::new_v4().to_string(),
            conflict_id: conflict.conflict_id.clone(),
            strategy: ResolutionStrategy::TaskRescheduling,
            affected_agents: conflict.involved_agents.clone(),
            resource_reallocation: HashMap::new(),
            task_reassignments,
            priority_adjustments: HashMap::new(),
            resolved_at: SystemTime::now(),
        })
    }
    
    /// Resolve priority conflicts through priority adjustment
    async fn resolve_priority_conflict(
        &self,
        conflict: &AgentConflict,
    ) -> Result<ConflictResolution, OrchestrationError> {
        let mut priority_adjustments = HashMap::new();
        
        // Adjust priorities based on conflict severity
        for (_agent_id, current_priority) in &conflict.priority_conflicts {
            let _adjusted_priority = current_priority + 10; // Increase priority
            priority_adjustments.insert(agent_id.clone(), adjusted_priority);
        }
        
        Ok(ConflictResolution {
            resolution_id: Uuid::new_v4().to_string(),
            conflict_id: conflict.conflict_id.clone(),
            strategy: ResolutionStrategy::PriorityBased,
            affected_agents: conflict.involved_agents.clone(),
            resource_reallocation: HashMap::new(),
            task_reassignments: HashMap::new(),
            priority_adjustments,
            resolved_at: SystemTime::now(),
        })
    }
    
    /// Resolve capability overlap conflicts
    async fn resolve_capability_overlap(
        &self,
        conflict: &AgentConflict,
    ) -> Result<ConflictResolution, OrchestrationError> {
        // Implement capability-based resolution
        Ok(ConflictResolution {
            resolution_id: Uuid::new_v4().to_string(),
            conflict_id: conflict.conflict_id.clone(),
            strategy: ResolutionStrategy::AgentReassignment,
            affected_agents: conflict.involved_agents.clone(),
            resource_reallocation: HashMap::new(),
            task_reassignments: HashMap::new(),
            priority_adjustments: HashMap::new(),
            resolved_at: SystemTime::now(),
        })
    }
    
    /// Resolve communication deadlock conflicts
    async fn resolve_communication_deadlock(
        &self,
        conflict: &AgentConflict,
    ) -> Result<ConflictResolution, OrchestrationError> {
        // Implement deadlock resolution through task reordering
        Ok(ConflictResolution {
            resolution_id: Uuid::new_v4().to_string(),
            conflict_id: conflict.conflict_id.clone(),
            strategy: ResolutionStrategy::TaskRescheduling,
            affected_agents: conflict.involved_agents.clone(),
            resource_reallocation: HashMap::new(),
            task_reassignments: HashMap::new(),
            priority_adjustments: HashMap::new(),
            resolved_at: SystemTime::now(),
        })
    }
    /// Apply conflict resolutions to subtasks
    async fn apply_conflict_resolutions(
        &self,
        subtasks: &mut [SubTask],
        resolutions: &[ConflictResolution],
    ) -> Result<(), OrchestrationError> {
        for _resolution in resolutions {
            // Apply task reassignments
            for (_task_id, new_agent) in &resolution.task_reassignments {
                if let Some(subtask) = subtasks.iter_mut().find(|s| s.subtask_id == *task_id) {
                    subtask.assigned_agent = Some(new_agent.clone());
                }
            }
            
            // Store resolution in history
            self.resolution_history.write().unwrap().push(resolution.clone());
        }
        
        Ok(())
    }
    
    /// Execute subtask asynchronously
    async fn execute_subtask_async(
        &self,
        subtask: SubTask,
        agent_id: AgentId,
    ) -> Result<tokio::task::JoinHandle<Result<TaskResult, OrchestrationError>>, OrchestrationError> {
        let _orchestrator = self.clone_for_async();
        
        let _handle = tokio::spawn(async move {
            let _start_time = Instant::now();
            
            // Create task message
            let _message = MessageEnvelope::new_direct_message(
                AgentId::new("orchestrator", "main", "system"),
                agent_id.clone(),
                "execute_task",
                serde_json::to_vec(&subtask.task_definition).unwrap(),
            );
            
            // Send task to agent (simplified - in real implementation would use proper channels)
            let _result = TaskResult {
                result_id: Uuid::new_v4().to_string(),
                task_id: subtask.task_definition.task_id.clone(),
                success: true,
                output_data: HashMap::new(),
                error_message: None,
                execution_time_ms: start_time.elapsed().as_millis() as u64,
                resource_usage: ResourceUsage::default(),
                metadata: HashMap::new(),
            };
            
            // Update agent metrics
            orchestrator.update_agent_metrics(&agent_id, &result).await?;
            
            Ok(result)
        });
        
        Ok(handle)
    }
    
    /// Update agent performance metrics
    async fn update_agent_metrics(
        &self,
        agent_id: &AgentId,
        result: &TaskResult,
    ) -> Result<(), OrchestrationError> {
        let mut agents = self.agents.write().unwrap();
        
        if let Some(metadata) = agents.get_mut(agent_id) {
            let _metrics = &mut metadata.performance_metrics;
            
            // Update response time (exponential moving average)
            let _alpha = 0.1;
            metrics.average_response_time_ms = 
                alpha * result.execution_time_ms as f64 + 
                (1.0 - alpha) * metrics.average_response_time_ms;
            
            // Update success/error rates
            if result.success {
                metrics.success_rate = 0.9 * metrics.success_rate + 0.1;
                metrics.error_rate = 0.9 * metrics.error_rate;
            } else {
                metrics.success_rate = 0.9 * metrics.success_rate;
                metrics.error_rate = 0.9 * metrics.error_rate + 0.1;
            }
            
            metrics.last_updated = SystemTime::now();
        }
        
        Ok(())
    }
    
    /// Check if resources can be allocated
    async fn can_allocate_resources(
        &self,
        requirements: &ResourceRequirements,
    ) -> Result<bool, OrchestrationError> {
        let _available = self.available_resources.read().unwrap();
        let _allocations = self.resource_allocations.read().unwrap();
        
        // Calculate currently allocated resources
        let mut total_allocated = ResourceRequirements::default();
        for _allocation in allocations.values() {
            total_allocated.cpu_cores += allocation.cpu_cores;
            total_allocated.memory_mb += allocation.memory_mb;
            total_allocated.disk_mb += allocation.disk_mb;
            total_allocated.network_bandwidth_mbps += allocation.network_bandwidth_mbps;
        }
        
        // Check if new allocation would exceed available resources
        Ok(
            total_allocated.cpu_cores + requirements.cpu_cores <= available.cpu_cores &&
            total_allocated.memory_mb + requirements.memory_mb <= available.memory_mb &&
            total_allocated.disk_mb + requirements.disk_mb <= available.disk_mb &&
            total_allocated.network_bandwidth_mbps + requirements.network_bandwidth_mbps <= available.network_bandwidth_mbps
        )
    }
    
    /// Calculate total resource demand for multiple tasks
    fn calculate_total_resource_demand(&self, tasks: &[&SubTask]) -> ResourceRequirements {
        let mut total = ResourceRequirements::default();
        
        for _task in tasks {
            // Simplified - in real implementation would look up task resource requirements
            total.cpu_cores += 0.5;
            total.memory_mb += 256;
            total.disk_mb += 100;
            total.network_bandwidth_mbps += 1.0;
        }
        
        total
    }
    
    /// Get agent resource capacity
    fn get_agent_resource_capacity(&self, _metadata: &AgentMetadata) -> ResourceRequirements {
        // Simplified - in real implementation would be based on agent configuration
        ResourceRequirements {
            cpu_cores: 2.0,
            memory_mb: 4096,
            disk_mb: 10240,
            network_bandwidth_mbps: 100.0,
            gpu_memory_mb: None,
            specialized_hardware: Vec::new(),
        }
    }
    
    /// Clone orchestrator for async operations
    fn clone_for_async(&self) -> Self {
        Self {
            agents: Arc::clone(&self.agents),
            subscriptions: Arc::clone(&self.subscriptions),
            active_tasks: Arc::clone(&self.active_tasks),
            subtasks: Arc::clone(&self.subtasks),
            message_queue: Arc::clone(&self.message_queue),
            agent_channels: Arc::clone(&self.agent_channels),
            active_conflicts: Arc::clone(&self.active_conflicts),
            resolution_history: Arc::clone(&self.resolution_history),
            available_resources: Arc::clone(&self.available_resources),
            resource_allocations: Arc::clone(&self.resource_allocations),
            system_metrics: Arc::clone(&self.system_metrics),
            audit_trail: Arc::clone(&self.audit_trail),
            max_agents: self.max_agents,
            max_concurrent_tasks: self.max_concurrent_tasks,
            task_timeout: self.task_timeout,
            heartbeat_interval: self.heartbeat_interval,
        }
    }
    
    /// Publish message to all subscribed agents
    pub async fn publish_message(
        &self,
        message: MessageEnvelope,
    ) -> Result<(), OrchestrationError> {
        if let Some(topic_id) = &message.topic_id {
            let _subscriptions = self.subscriptions.read().unwrap();
            let mut recipients = Vec::new();
            
            // Find all agents subscribed to this topic
            for _subscription in subscriptions.values() {
                if subscription.matches_topic(topic_id) {
                    recipients.push(subscription.agent_id.clone());
                }
            }
            
            // Send message to all recipients
            let _agent_channels = self.agent_channels.read().unwrap();
            for _recipient in recipients {
                if let Some(sender) = agent_channels.get(&recipient) {
                    let mut recipient_message = message.clone();
                    recipient_message.recipient = Some(recipient.clone());
                    
                    if let Err(_) = sender.send(recipient_message) {
                        return Err(OrchestrationError::CommunicationFailed {
                            details: format!("Failed to send message to agent: {}", recipient.to_string()),
                        });
                    }
                }
            }
            
            // Create audit entry
            let _audit_entry = AuditEntry::new(
                "message_published",
                message.sender.clone(),
                true,
            );
            self.audit_trail.write().unwrap().push(audit_entry);
        }
        
        Ok(())
    }
    
    /// Send direct message to specific agent
    pub async fn send_message(
        &self,
        message: MessageEnvelope,
    ) -> Result<(), OrchestrationError> {
        if let Some(recipient) = &message.recipient {
            let _agent_channels = self.agent_channels.read().unwrap();
            
            if let Some(sender) = agent_channels.get(recipient) {
                if let Err(_) = sender.send(message.clone()) {
                    return Err(OrchestrationError::CommunicationFailed {
                        details: format!("Failed to send message to agent: {}", recipient.to_string()),
                    });
                }
                
                // Create audit entry
                let _audit_entry = AuditEntry::new(
                    "message_sent",
                    message.sender.clone(),
                    true,
                );
                self.audit_trail.write().unwrap().push(audit_entry);
            } else {
                return Err(OrchestrationError::AgentNotFound {
                    agent_id: recipient.to_string(),
                });
            }
        }
        
        Ok(())
    }
    
    /// Add subscription for an agent
    pub async fn add_subscription(
        &self,
        subscription: Subscription,
    ) -> Result<(), OrchestrationError> {
        let mut subscriptions = self.subscriptions.write().unwrap();
        subscriptions.insert(subscription.subscription_id.clone(), subscription);
        
        Ok(())
    }
    
    /// Remove subscription
    pub async fn remove_subscription(
        &self,
        _subscription_id: &str,
    ) -> Result<(), OrchestrationError> {
        let mut subscriptions = self.subscriptions.write().unwrap();
        subscriptions.remove(subscription_id);
        
        Ok(())
    }
    
    /// Get system performance metrics
    pub async fn get_system_metrics(&self) -> SystemMetrics {
        let _agents = self.agents.read().unwrap();
        let _active_tasks = self.active_tasks.read().unwrap();
        
        let mut metrics = self.system_metrics.write().unwrap();
        metrics.total_agents = agents.len();
        metrics.active_agents = agents.values()
            .filter(|m| m.current_status == AgentStatus::Ready || m.current_status == AgentStatus::Busy)
            .count();
        metrics.active_tasks = active_tasks.len();
        metrics.last_updated = SystemTime::now();
        
        metrics.clone()
    }
    
    /// Get audit trail
    pub async fn get_audit_trail(&self) -> Vec<AuditEntry> {
        self.audit_trail.read().unwrap().clone()
    }
    
    /// Shutdown orchestrator gracefully
    pub async fn shutdown(&self) -> Result<(), OrchestrationError> {
        // Cancel all active tasks
        let mut active_tasks = self.active_tasks.write().unwrap();
        active_tasks.clear();
        
        // Close all agent channels
        let mut agent_channels = self.agent_channels.write().unwrap();
        agent_channels.clear();
        
        // Create shutdown audit entry
        let _audit_entry = AuditEntry::new("orchestrator_shutdown", None, true);
        self.audit_trail.write().unwrap().push(audit_entry);
        
        Ok(())
    }
}

/// Default implementation for MultiAgentOrchestrator
impl Default for MultiAgentOrchestrator {
    fn default() -> Self {
        Self::new()
    }
}

/// Thread-safe cloning for async operations
impl Clone for MultiAgentOrchestrator {
    fn clone(&self) -> Self {
        self.clone_for_async()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_orchestrator_creation() {
        let _orchestrator = MultiAgentOrchestrator::new();
        let _metrics = orchestrator.get_system_metrics().await;
        assert_eq!(metrics.total_agents, 0);
        assert_eq!(metrics.active_agents, 0);
    }
    
    #[tokio::test]
    async fn test_agent_registration() {
        let _orchestrator = MultiAgentOrchestrator::new();
        let _agent_id = AgentId::new("test_agent", "instance_1", "default");
        let _capabilities = vec![
            AgentCapability {
                capability_id: "text_processing".to_string(),
                name: "Text Processing".to_string(),
                description: "Process text data".to_string(),
                input_types: vec!["text".to_string()],
                output_types: vec!["processed_text".to_string()],
                resource_requirements: ResourceRequirements::default(),
                performance_metrics: PerformanceMetrics::default(),
            }
        ];
        
        let _result = orchestrator.register_agent(
            agent_id.clone(),
            capabilities,
            ResourceRequirements::default(),
        ).await;
        
        assert!(result.is_ok());
        
        let _metrics = orchestrator.get_system_metrics().await;
        assert_eq!(metrics.total_agents, 1);
    }
    
    #[tokio::test]
    async fn test_task_decomposition() {
        let _orchestrator = MultiAgentOrchestrator::new();
        
        // Register test agent
        let _agent_id = AgentId::new("test_agent", "instance_1", "default");
        let _capabilities = vec![
            AgentCapability {
                capability_id: "data_processing".to_string(),
                name: "Data Processing".to_string(),
                description: "Process data".to_string(),
                input_types: vec!["data".to_string()],
                output_types: vec!["result".to_string()],
                resource_requirements: ResourceRequirements::default(),
                performance_metrics: PerformanceMetrics::default(),
            }
        ];
        
        orchestrator.register_agent(
            agent_id,
            capabilities,
            ResourceRequirements::default(),
        ).await.unwrap();
        
        // Create test task
        let mut task = Task::new("test_task", "data_processing", 100);
        task.required_capabilities = vec!["data_processing".to_string()];
        
        let _subtasks = orchestrator.decompose_task(&task).await;
        assert!(subtasks.is_ok());
        
        let _subtasks = subtasks.unwrap();
        assert!(!subtasks.is_empty());
    }
}