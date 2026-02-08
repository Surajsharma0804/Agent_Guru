//! Type definitions for the Naming System
//!
//! This module defines all data structures used throughout the naming system
//! with comprehensive type safety and serialization support.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

/// Programming language classification for naming conventions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ProgrammingLanguage {
    /// Rust programming language
    Rust,
    /// Python programming language
    Python,
    /// TypeScript programming language
    TypeScript,
    /// JavaScript programming language
    JavaScript,
    /// C++ programming language
    Cpp,
    /// C programming language
    C,
    /// Go programming language
    Go,
    /// Unknown or unsupported language
    Unknown,
}

/// File role classification for semantic understanding
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FileRole {
    /// Module root file (mod.rs, __init__.py, index.js)
    ModuleRoot,
    /// Library entry point (lib.rs, lib.py)
    LibraryEntry,
    /// Application entry point (main.rs, main.py, index.ts)
    ApplicationEntry,
    /// Implementation file with core logic
    Implementation,
    /// Interface or trait definition file
    Interface,
    /// Test file with unit or integration tests
    Test,
    /// Configuration file
    Configuration,
    /// Documentation file
    Documentation,
    /// Unknown or unclassified role
    Unknown,
}

/// Naming convention style for different languages
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum NamingStyle {
    /// snake_case naming (Rust, Python)
    SnakeCase,
    /// camelCase naming (JavaScript, TypeScript)
    CamelCase,
    /// PascalCase naming (C#, Java)
    PascalCase,
    /// kebab-case naming (CSS, HTML)
    KebabCase,
}

/// Result of a file renaming operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenamingResult {
    /// Original file path before renaming
    pub old_path: PathBuf,
    /// New file path after renaming
    pub new_path: PathBuf,
    /// Number of references updated across codebase
    pub references_updated: usize,
    /// Whether compilation was verified after renaming
    pub compilation_verified: bool,
    /// Whether rollback is available if needed
    pub rollback_available: bool,
    /// Timestamp of renaming operation
    pub timestamp: String,
}

/// Reference to a file that needs updating
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileReference {
    /// Path to file containing the reference
    pub file_path: PathBuf,
    /// Line number where reference appears
    pub line_number: usize,
    /// Column number where reference starts
    pub column_number: usize,
    /// Text content of the reference
    pub reference_text: String,
    /// Type of reference (import, path, etc.)
    pub reference_type: ReferenceType,
}

/// Type of reference found in source code
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReferenceType {
    /// Import statement (use, import, require)
    Import,
    /// Module declaration (mod, module)
    ModuleDeclaration,
    /// File path reference in code
    PathReference,
    /// String literal containing file path
    StringLiteral,
    /// Comment containing file reference
    Comment,
}

/// Naming conflict information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NamingConflict {
    /// Name that conflicts with existing file
    pub conflicting_name: String,
    /// Path to existing file with same name
    pub existing_file: PathBuf,
    /// Path to proposed file causing conflict
    pub proposed_file: PathBuf,
    /// Strategy chosen to resolve conflict
    pub resolution_strategy: ConflictResolutionStrategy,
}

/// Strategy for resolving naming conflicts
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConflictResolutionStrategy {
    /// Add numeric or descriptive suffix to name
    AddSuffix,
    /// Add descriptive prefix to name
    AddPrefix,
    /// Use hierarchical naming with module path
    UseHierarchicalNaming,
    /// Require manual intervention to resolve
    ManualIntervention,
}

/// Compilation verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationResult {
    /// Whether compilation succeeded
    pub success: bool,
    /// Compilation errors encountered
    pub errors: Vec<CompilationError>,
    /// Compilation warnings encountered
    pub warnings: Vec<CompilationWarning>,
    /// Duration of compilation in milliseconds
    pub duration_ms: u64,
}

/// Compilation error details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationError {
    /// File where error occurred
    pub file_path: PathBuf,
    /// Line number of error
    pub line_number: usize,
    /// Column number of error
    pub column_number: usize,
    /// Error message text
    pub message: String,
    /// Compiler error code if available
    pub error_code: Option<String>,
}

/// Compilation warning details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationWarning {
    /// File where warning occurred
    pub file_path: PathBuf,
    /// Line number of warning
    pub line_number: usize,
    /// Column number of warning
    pub column_number: usize,
    /// Warning message text
    pub message: String,
    /// Compiler warning code if available
    pub warning_code: Option<String>,
}

/// Style guide configuration for naming validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StyleGuide {
    /// Programming language for validation rules
    pub language: ProgrammingLanguage,
    /// Required naming style convention
    pub naming_style: NamingStyle,
    /// Maximum allowed name length
    pub max_name_length: usize,
    /// Minimum required name length
    pub min_name_length: usize,
    /// Prefixes that are forbidden
    pub forbidden_prefixes: Vec<String>,
    /// Suffixes that are forbidden
    pub forbidden_suffixes: Vec<String>,
    /// Required patterns that must be present
    pub required_patterns: Vec<String>,
}

impl Default for StyleGuide {
    fn default() -> Self {
        Self {
            language: ProgrammingLanguage::Unknown,
            naming_style: NamingStyle::SnakeCase,
            max_name_length: 64,
            min_name_length: 3,
            forbidden_prefixes: vec![],
            forbidden_suffixes: vec![],
            required_patterns: vec![],
        }
    }
}

/// Naming validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    /// Whether name passes all validation rules
    pub is_valid: bool,
    /// List of style violations found
    pub violations: Vec<StyleViolation>,
    /// Suggested alternative names
    pub suggestions: Vec<String>,
}

/// Style guide violation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StyleViolation {
    /// Type of violation encountered
    pub violation_type: ViolationType,
    /// Human-readable violation message
    pub message: String,
    /// Severity level of violation
    pub severity: Severity,
}

/// Type of style violation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ViolationType {
    /// Name doesn't follow required naming style
    InvalidNamingStyle,
    /// Name exceeds maximum length
    NameTooLong,
    /// Name is shorter than minimum length
    NameTooShort,
    /// Name uses forbidden prefix
    ForbiddenPrefix,
    /// Name uses forbidden suffix
    ForbiddenSuffix,
    /// Name missing required pattern
    MissingRequiredPattern,
    /// Name contains invalid characters
    InvalidCharacters,
}

/// Severity level for violations
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Severity {
    /// Informational message
    Info,
    /// Warning that should be addressed
    Warning,
    /// Error that must be fixed
    Error,
    /// Critical error requiring immediate attention
    Critical,
}

/// Checkpoint for rollback capability
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenameCheckpoint {
    /// Unique identifier for checkpoint
    pub checkpoint_id: String,
    /// Timestamp when checkpoint was created
    pub timestamp: String,
    /// Original file contents before modifications
    pub original_state: HashMap<PathBuf, String>,
    /// List of files modified since checkpoint
    pub modified_files: Vec<PathBuf>,
}
