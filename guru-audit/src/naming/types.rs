// Type definitions for the Naming System
//
// This module defines all data structures used throughout the naming system
// with comprehensive type safety and serialization support.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

/// Programming language classification for naming conventions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ProgrammingLanguage {
    Rust,
    Python,
    TypeScript,
    JavaScript,
    Cpp,
    C,
    Go,
    Unknown,
}

/// File role classification for semantic understanding
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FileRole {
    ModuleRoot,
    LibraryEntry,
    ApplicationEntry,
    Implementation,
    Interface,
    Test,
    Configuration,
    Documentation,
    Unknown,
}

/// Naming convention style for different languages
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum NamingStyle {
    SnakeCase,
    CamelCase,
    PascalCase,
    KebabCase,
}

/// Result of a file renaming operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenamingResult {
    pub old_path: PathBuf,
    pub new_path: PathBuf,
    pub references_updated: usize,
    pub compilation_verified: bool,
    pub rollback_available: bool,
    pub timestamp: String,
}

/// Reference to a file that needs updating
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileReference {
    pub file_path: PathBuf,
    pub line_number: usize,
    pub column_number: usize,
    pub reference_text: String,
    pub reference_type: ReferenceType,
}

/// Type of reference found in source code
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReferenceType {
    Import,
    ModuleDeclaration,
    PathReference,
    StringLiteral,
    Comment,
}

/// Naming conflict information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NamingConflict {
    pub conflicting_name: String,
    pub existing_file: PathBuf,
    pub proposed_file: PathBuf,
    pub resolution_strategy: ConflictResolutionStrategy,
}

/// Strategy for resolving naming conflicts
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConflictResolutionStrategy {
    AddSuffix,
    AddPrefix,
    UseHierarchicalNaming,
    ManualIntervention,
}

/// Compilation verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationResult {
    pub success: bool,
    pub errors: Vec<CompilationError>,
    pub warnings: Vec<CompilationWarning>,
    pub duration_ms: u64,
}

/// Compilation error details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationError {
    pub file_path: PathBuf,
    pub line_number: usize,
    pub column_number: usize,
    pub message: String,
    pub error_code: Option<String>,
}

/// Compilation warning details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilationWarning {
    pub file_path: PathBuf,
    pub line_number: usize,
    pub column_number: usize,
    pub message: String,
    pub warning_code: Option<String>,
}

/// Style guide configuration for naming validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StyleGuide {
    pub language: ProgrammingLanguage,
    pub naming_style: NamingStyle,
    pub max_name_length: usize,
    pub min_name_length: usize,
    pub forbidden_prefixes: Vec<String>,
    pub forbidden_suffixes: Vec<String>,
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
    pub is_valid: bool,
    pub violations: Vec<StyleViolation>,
    pub suggestions: Vec<String>,
}

/// Style guide violation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StyleViolation {
    pub violation_type: ViolationType,
    pub message: String,
    pub severity: Severity,
}

/// Type of style violation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ViolationType {
    InvalidNamingStyle,
    NameTooLong,
    NameTooShort,
    ForbiddenPrefix,
    ForbiddenSuffix,
    MissingRequiredPattern,
    InvalidCharacters,
}

/// Severity level for violations
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Severity {
    Info,
    Warning,
    Error,
    Critical,
}

/// Checkpoint for rollback capability
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenameCheckpoint {
    pub checkpoint_id: String,
    pub timestamp: String,
    pub original_state: HashMap<PathBuf, String>,
    pub modified_files: Vec<PathBuf>,
}
