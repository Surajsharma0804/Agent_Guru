//! Type definitions for the Dead Code Purge System
//!
//! This module provides comprehensive type definitions for static analysis,
//! dependency tracing, safety verification, and secure deletion operations.
//! All types are designed for production-grade dead code elimination with
//! mathematical correctness guarantees and cryptographic verification.

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::time::SystemTime;

/// Unique identifier for a code element (function, variable, type, etc.)
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CodeElementId(pub String);

/// Unique identifier for a file in the codebase
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct FileId(pub PathBuf);

/// Unique identifier for a deletion operation
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DeletionId(pub String);

/// Result of static analysis on the codebase
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaticAnalysisResult {
    /// All code elements discovered during analysis
    pub code_elements: HashMap<CodeElementId, CodeElement>,
    /// Control flow graphs for all functions
    pub control_flow_graphs: HashMap<CodeElementId, ControlFlowGraph>,
    /// Call graph showing function invocations
    pub call_graph: CallGraph,
    /// Data flow analysis results
    pub data_flow: DataFlowAnalysis,
    /// Analysis timestamp
    pub timestamp: SystemTime,
    /// Analysis duration in milliseconds
    pub analysis_duration_ms: u64,
}

/// Represents a code element (function, variable, type, module, etc.)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeElement {
    /// Unique identifier
    pub id: CodeElementId,
    /// Element type (function, variable, type, etc.)
    pub element_type: CodeElementType,
    /// Source file location
    pub file_id: FileId,
    /// Line number range
    pub line_range: (usize, usize),
    /// Element name
    pub name: String,
    /// Visibility (public, private, etc.)
    pub visibility: Visibility,
    /// Whether element is used
    pub is_used: bool,
    /// Usage count
    pub usage_count: usize,
    /// Dependencies on other elements
    pub dependencies: HashSet<CodeElementId>,
    /// Elements that depend on this element
    pub dependents: HashSet<CodeElementId>,
}

/// Type of code element
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CodeElementType {
    Function,
    Method,
    Variable,
    Constant,
    Type,
    Trait,
    Module,
    Import,
    Macro,
}

/// Visibility level of code element
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Visibility {
    Public,
    Private,
    Crate,
    Module,
}

/// Control flow graph for a function
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlFlowGraph {
    /// Function identifier
    pub function_id: CodeElementId,
    /// Basic blocks in the CFG
    pub basic_blocks: Vec<BasicBlock>,
    /// Edges between basic blocks
    pub edges: Vec<CfgEdge>,
    /// Entry block
    pub entry_block: usize,
    /// Exit blocks
    pub exit_blocks: Vec<usize>,
}

/// Basic block in control flow graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BasicBlock {
    /// Block identifier
    pub id: usize,
    /// Instructions in the block
    pub instructions: Vec<Instruction>,
    /// Whether block is reachable
    pub is_reachable: bool,
}

/// Instruction in a basic block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Instruction {
    /// Instruction type
    pub instruction_type: InstructionType,
    /// Source location
    pub line_number: usize,
}

/// Type of instruction
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum InstructionType {
    Assignment,
    FunctionCall,
    Return,
    Branch,
    Jump,
    Other,
}

/// Edge in control flow graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CfgEdge {
    /// Source block
    pub from: usize,
    /// Target block
    pub to: usize,
    /// Edge type (conditional, unconditional)
    pub edge_type: EdgeType,
}

/// Type of control flow edge
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum EdgeType {
    Unconditional,
    ConditionalTrue,
    ConditionalFalse,
}

/// Call graph showing function invocations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallGraph {
    /// Nodes in the call graph (functions)
    pub nodes: HashSet<CodeElementId>,
    /// Edges showing function calls
    pub edges: Vec<CallEdge>,
    /// Entry points (main, tests, public APIs)
    pub entry_points: HashSet<CodeElementId>,
}

/// Edge in call graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallEdge {
    /// Caller function
    pub caller: CodeElementId,
    /// Callee function
    pub callee: CodeElementId,
    /// Call site location
    pub call_site: (FileId, usize),
}

/// Data flow analysis results
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataFlowAnalysis {
    /// Reaching definitions for each program point
    pub reaching_definitions: HashMap<CodeElementId, HashSet<CodeElementId>>,
    /// Live variables at each program point
    pub live_variables: HashMap<CodeElementId, HashSet<CodeElementId>>,
    /// Available expressions
    pub available_expressions: HashMap<CodeElementId, HashSet<String>>,
}

/// Result of dependency tracing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyTraceResult {
    /// Reachable code elements from entry points
    pub reachable_elements: HashSet<CodeElementId>,
    /// Unreachable code elements (dead code)
    pub unreachable_elements: HashSet<CodeElementId>,
    /// Dependency chains for each element
    pub dependency_chains: HashMap<CodeElementId, Vec<Vec<CodeElementId>>>,
    /// Unused files
    pub unused_files: HashSet<FileId>,
    /// Unused imports
    pub unused_imports: Vec<UnusedImport>,
    /// Tracing timestamp
    pub timestamp: SystemTime,
    /// Tracing duration in milliseconds
    pub tracing_duration_ms: u64,
}

/// Unused import information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnusedImport {
    /// File containing the import
    pub file_id: FileId,
    /// Line number of import
    pub line_number: usize,
    /// Import statement
    pub import_statement: String,
}

/// Result of safety verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyVerificationResult {
    /// Whether deletion is safe
    pub is_safe: bool,
    /// Elements safe to delete
    pub safe_to_delete: HashSet<CodeElementId>,
    /// Elements unsafe to delete
    pub unsafe_to_delete: HashSet<CodeElementId>,
    /// Impact assessment for each element
    pub impact_assessments: HashMap<CodeElementId, ImpactAssessment>,
    /// Rollback capability verification
    pub rollback_verified: bool,
    /// Verification timestamp
    pub timestamp: SystemTime,
    /// Verification duration in milliseconds
    pub verification_duration_ms: u64,
}

/// Impact assessment for deleting a code element
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactAssessment {
    /// Element being assessed
    pub element_id: CodeElementId,
    /// Risk level of deletion
    pub risk_level: RiskLevel,
    /// Affected elements
    pub affected_elements: HashSet<CodeElementId>,
    /// Affected files
    pub affected_files: HashSet<FileId>,
    /// Breaking changes introduced
    pub breaking_changes: Vec<BreakingChange>,
    /// Recommended actions
    pub recommendations: Vec<String>,
}

/// Risk level for deletion operation
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RiskLevel {
    Safe,
    Low,
    Medium,
    High,
    Critical,
}

/// Breaking change introduced by deletion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BreakingChange {
    /// Type of breaking change
    pub change_type: BreakingChangeType,
    /// Description
    pub description: String,
    /// Affected locations
    pub affected_locations: Vec<(FileId, usize)>,
}

/// Type of breaking change
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum BreakingChangeType {
    PublicApiRemoval,
    DependencyBreak,
    CompilationFailure,
    TestFailure,
    RuntimeError,
}

/// Result of deletion execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeletionResult {
    /// Deletion operation identifier
    pub deletion_id: DeletionId,
    /// Whether deletion succeeded
    pub success: bool,
    /// Elements deleted
    pub deleted_elements: HashSet<CodeElementId>,
    /// Files deleted
    pub deleted_files: HashSet<FileId>,
    /// Files modified
    pub modified_files: HashSet<FileId>,
    /// Cryptographic audit trail
    pub audit_trail: Vec<AuditEntry>,
    /// Deletion timestamp
    pub timestamp: SystemTime,
    /// Deletion duration in milliseconds
    pub deletion_duration_ms: u64,
}

/// Audit entry for deletion operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    /// Entry timestamp
    pub timestamp: SystemTime,
    /// Operation type
    pub operation: DeletionOperation,
    /// File affected
    pub file_id: FileId,
    /// SHA-256 checksum before operation
    pub checksum_before: [u8; 32],
    /// SHA-256 checksum after operation
    pub checksum_after: [u8; 32],
    /// Cryptographic signature (serialized as hex string)
    #[serde(with = "signature_hex")]
    pub signature: [u8; 64],
}

mod signature_hex {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &[u8; 64], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex::encode(bytes))
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<[u8; 64], D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: String = Deserialize::deserialize(deserializer)?;
        let bytes = hex::decode(&s).map_err(serde::de::Error::custom)?;
        bytes.try_into().map_err(|_| serde::de::Error::custom("Invalid signature length"))
    }
}

/// Type of deletion operation
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DeletionOperation {
    FileDeleted,
    ElementRemoved,
    ImportRemoved,
    CodeModified,
}

/// Result of duplicate code detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuplicateDetectionResult {
    /// Duplicate code blocks found
    pub duplicates: Vec<DuplicateCodeBlock>,
    /// Total duplicate lines
    pub total_duplicate_lines: usize,
    /// Percentage of codebase that is duplicate
    pub duplicate_percentage: f64,
    /// Refactoring recommendations
    pub refactoring_recommendations: Vec<RefactoringRecommendation>,
    /// Detection timestamp
    pub timestamp: SystemTime,
    /// Detection duration in milliseconds
    pub detection_duration_ms: u64,
}

/// Duplicate code block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuplicateCodeBlock {
    /// Unique identifier for this duplicate group
    pub group_id: String,
    /// Locations where this code appears
    pub locations: Vec<CodeLocation>,
    /// Number of lines in the duplicate block
    pub line_count: usize,
    /// Similarity score (0.0 to 1.0)
    pub similarity_score: f64,
    /// Code content (for analysis)
    pub code_content: String,
}

/// Location of code in the codebase
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeLocation {
    /// File identifier
    pub file_id: FileId,
    /// Starting line number
    pub start_line: usize,
    /// Ending line number
    pub end_line: usize,
}

/// Refactoring recommendation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RefactoringRecommendation {
    /// Recommendation type
    pub recommendation_type: RefactoringType,
    /// Duplicate group this applies to
    pub duplicate_group_id: String,
    /// Description of recommended refactoring
    pub description: String,
    /// Estimated complexity reduction
    pub complexity_reduction: f64,
    /// Priority level
    pub priority: Priority,
}

/// Type of refactoring
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum RefactoringType {
    ExtractFunction,
    ExtractModule,
    ParameterizeCode,
    UseExistingFunction,
    CreateTrait,
}

/// Priority level for refactoring
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    Low,
    Medium,
    High,
    Critical,
}

/// Configuration for purge system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PurgeConfig {
    /// Whether to perform static analysis
    pub enable_static_analysis: bool,
    /// Whether to perform dependency tracing
    pub enable_dependency_tracing: bool,
    /// Whether to perform safety verification
    pub enable_safety_verification: bool,
    /// Whether to perform duplicate detection
    pub enable_duplicate_detection: bool,
    /// Minimum risk level for automatic deletion
    pub auto_delete_risk_threshold: RiskLevel,
    /// Whether to require manual approval for high-risk deletions
    pub require_manual_approval: bool,
    /// Whether to create backups before deletion
    pub create_backups: bool,
    /// Maximum deletion batch size
    pub max_batch_size: usize,
}

impl Default for PurgeConfig {
    fn default() -> Self {
        Self {
            enable_static_analysis: true,
            enable_dependency_tracing: true,
            enable_safety_verification: true,
            enable_duplicate_detection: true,
            auto_delete_risk_threshold: RiskLevel::Low,
            require_manual_approval: true,
            create_backups: true,
            max_batch_size: 100,
        }
    }
}
