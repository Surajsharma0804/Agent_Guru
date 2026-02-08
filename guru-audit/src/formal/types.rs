//! # Formal Verification Types
//!
//! Core data structures for formal verification with TLA+ integration.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// TLA+ specification representation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaSpecification {
    /// Specification name
    pub name: String,
    /// Specification file path
    pub file_path: PathBuf,
    /// Module declarations
    pub modules: Vec<TlaModule>,
    /// Constants defined
    pub constants: Vec<TlaConstant>,
    /// Variables defined
    pub variables: Vec<TlaVariable>,
    /// Operators defined
    pub operators: Vec<TlaOperator>,
    /// Invariants to check
    pub invariants: Vec<TlaInvariant>,
    /// Temporal properties
    pub temporal_properties: Vec<TlaTemporalProperty>,
}

/// TLA+ module
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaModule {
    /// Module name
    pub name: String,
    /// Module extends
    pub extends: Vec<String>,
    /// Module instances
    pub instances: Vec<String>,
}

/// TLA+ constant
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaConstant {
    /// Constant name
    pub name: String,
    /// Constant type
    pub constant_type: String,
    /// Constant value (if assigned)
    pub value: Option<String>,
}

/// TLA+ variable
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaVariable {
    /// Variable name
    pub name: String,
    /// Variable type
    pub variable_type: String,
    /// Initial value expression
    pub initial_value: String,
}

/// TLA+ operator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaOperator {
    /// Operator name
    pub name: String,
    /// Operator parameters
    pub parameters: Vec<String>,
    /// Operator definition
    pub definition: String,
}

/// TLA+ invariant
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaInvariant {
    /// Invariant name
    pub name: String,
    /// Invariant expression
    pub expression: String,
    /// Invariant description
    pub description: String,
}

/// TLA+ temporal property
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlaTemporalProperty {
    /// Property name
    pub name: String,
    /// Property expression
    pub expression: String,
    /// Property type
    pub property_type: TemporalPropertyType,
    /// Property description
    pub description: String,
}

/// Temporal property type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TemporalPropertyType {
    /// Safety property ([]P - always P)
    Safety,
    /// Liveness property (<>P - eventually P)
    Liveness,
    /// Fairness property (WF/SF)
    Fairness,
    /// General temporal formula
    General,
}

/// Model checking configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCheckingConfig {
    /// Maximum state space depth
    pub max_depth: u32,
    /// Maximum number of states to explore
    pub max_states: u64,
    /// Timeout for model checking
    pub timeout: Duration,
    /// Symmetry reduction enabled
    pub symmetry_reduction: bool,
    /// Partial order reduction enabled
    pub partial_order_reduction: bool,
    /// State space exploration strategy
    pub exploration_strategy: ExplorationStrategy,
}

/// State space exploration strategy
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExplorationStrategy {
    /// Breadth-first search
    BreadthFirst,
    /// Depth-first search
    DepthFirst,
    /// Random exploration
    Random,
    /// Guided exploration with heuristics
    Guided,
}

/// Model checking result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCheckingResult {
    /// Specification name
    pub spec_name: String,
    /// Verification status
    pub status: VerificationStatus,
    /// States explored
    pub states_explored: u64,
    /// Distinct states
    pub distinct_states: u64,
    /// Exploration depth reached
    pub depth_reached: u32,
    /// Invariants checked
    pub invariants_checked: Vec<InvariantCheckResult>,
    /// Temporal properties checked
    pub temporal_properties_checked: Vec<TemporalPropertyCheckResult>,
    /// Counterexamples found
    pub counterexamples: Vec<Counterexample>,
    /// Execution duration
    pub duration: Duration,
}

/// Verification status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerificationStatus {
    /// All properties verified successfully
    Verified,
    /// Verification failed with counterexample
    Failed,
    /// Verification timed out
    Timeout,
    /// Verification error occurred
    Error { message: String },
    /// Verification in progress
    InProgress { progress_percentage: u8 },
}

/// Invariant check result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvariantCheckResult {
    /// Invariant name
    pub invariant_name: String,
    /// Check passed
    pub passed: bool,
    /// Violation state (if failed)
    pub violation_state: Option<State>,
    /// Violation trace (if failed)
    pub violation_trace: Option<Vec<State>>,
}

/// Temporal property check result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalPropertyCheckResult {
    /// Property name
    pub property_name: String,
    /// Property type
    pub property_type: TemporalPropertyType,
    /// Check passed
    pub passed: bool,
    /// Counterexample (if failed)
    pub counterexample: Option<Counterexample>,
}

/// State in the state space
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct State {
    /// State identifier
    pub id: u64,
    /// Variable assignments
    pub variables: HashMap<String, StateValue>,
    /// State hash for deduplication
    pub hash: u64,
}

/// State value
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum StateValue {
    /// Boolean value
    Boolean(bool),
    /// Integer value
    Integer(i64),
    /// String value
    String(String),
    /// Set value
    Set(Vec<StateValue>),
    /// Sequence value
    Sequence(Vec<StateValue>),
    /// Record value
    Record(HashMap<String, StateValue>),
}

/// Counterexample for property violation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Counterexample {
    /// Property name that was violated
    pub property_name: String,
    /// Trace of states leading to violation
    pub trace: Vec<State>,
    /// Violation description
    pub description: String,
    /// Loop start index (for liveness violations)
    pub loop_start: Option<usize>,
}

/// Proof certificate for verified properties
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofCertificate {
    /// Certificate identifier
    pub certificate_id: String,
    /// Specification name
    pub spec_name: String,
    /// Properties verified
    pub properties_verified: Vec<String>,
    /// Proof steps
    pub proof_steps: Vec<ProofStep>,
    /// Cryptographic signature
    pub signature: Vec<u8>,
    /// Generation timestamp
    pub timestamp: SystemTime,
    /// Verification tool version
    pub tool_version: String,
}

/// Proof step in certificate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofStep {
    /// Step number
    pub step_number: u32,
    /// Step type
    pub step_type: ProofStepType,
    /// Step description
    pub description: String,
    /// Logical justification
    pub justification: String,
    /// Referenced lemmas or theorems
    pub references: Vec<String>,
}

/// Proof step type
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProofStepType {
    /// Assumption
    Assumption,
    /// Axiom application
    Axiom,
    /// Theorem application
    Theorem,
    /// Lemma application
    Lemma,
    /// Induction step
    Induction,
    /// Case analysis
    CaseAnalysis,
    /// Direct proof
    DirectProof,
    /// Contradiction
    Contradiction,
}

/// Invariant validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvariantValidationResult {
    /// Invariant name
    pub invariant_name: String,
    /// Validation status
    pub status: ValidationStatus,
    /// States checked
    pub states_checked: u64,
    /// Violations found
    pub violations: Vec<InvariantViolation>,
    /// Execution duration
    pub duration: Duration,
}

/// Validation status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ValidationStatus {
    /// Validation passed
    Valid,
    /// Validation failed
    Invalid,
    /// Validation incomplete
    Incomplete,
    /// Validation error
    Error { message: String },
}

/// Invariant violation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvariantViolation {
    /// Violation identifier
    pub id: String,
    /// State where violation occurred
    pub state: State,
    /// Trace leading to violation
    pub trace: Vec<State>,
    /// Violation description
    pub description: String,
}

/// Temporal logic verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalLogicResult {
    /// Property name
    pub property_name: String,
    /// Property type
    pub property_type: TemporalPropertyType,
    /// Verification status
    pub status: VerificationStatus,
    /// Counterexample (if failed)
    pub counterexample: Option<Counterexample>,
    /// Witness trace (if liveness property satisfied)
    pub witness_trace: Option<Vec<State>>,
    /// Execution duration
    pub duration: Duration,
}

impl Default for ModelCheckingConfig {
    fn default() -> Self {
        Self {
            max_depth: 100,
            max_states: 1_000_000,
            timeout: Duration::from_secs(600), // 10 minutes
            symmetry_reduction: true,
            partial_order_reduction: true,
            exploration_strategy: ExplorationStrategy::BreadthFirst,
        }
    }
}

impl State {
    /// Create a new state
    pub fn new(id: u64) -> Self {
        Self {
            id,
            variables: HashMap::new(),
            hash: 0,
        }
    }

    /// Add variable assignment
    pub fn add_variable(&mut self, name: String, value: StateValue) {
        self.variables.insert(name, value);
        self.recompute_hash();
    }

    /// Recompute state hash
    fn recompute_hash(&mut self) {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        self.id.hash(&mut hasher);
        // In production, would hash all variables
        self.hash = hasher.finish();
    }
}

impl StateValue {
    /// Check if value is boolean
    pub fn is_boolean(&self) -> bool {
        matches!(self, StateValue::Boolean(_))
    }

    /// Check if value is integer
    pub fn is_integer(&self) -> bool {
        matches!(self, StateValue::Integer(_))
    }

    /// Get boolean value
    pub fn as_boolean(&self) -> Option<bool> {
        if let StateValue::Boolean(b) = self {
            Some(*b)
        } else {
            None
        }
    }

    /// Get integer value
    pub fn as_integer(&self) -> Option<i64> {
        if let StateValue::Integer(i) = self {
            Some(*i)
        } else {
            None
        }
    }
}
