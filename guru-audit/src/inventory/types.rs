//! Type definitions for the Inventory System
//!
//! This module defines all data structures used by the Full Inventory Generation System,
//! including file analysis results, configuration, and statistical information. All types
//! are designed for production-grade operation with comprehensive metadata and validation.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// Configuration for the inventory system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InventorySystemConfig {
    /// Paths to exclude from analysis
    pub excluded_paths: Vec<PathBuf>,
    /// File patterns to exclude (glob patterns)
    pub excluded_patterns: Vec<String>,
    /// File patterns to include (glob patterns, empty means include all)
    pub included_patterns: Vec<String>,
    /// Enable parallel processing for file analysis
    pub enable_parallel_processing: bool,
    /// Enable cryptographic checksum verification
    pub enable_checksum_verification: bool,
    /// Enable security scanning
    pub enable_security_scanning: bool,
    /// Maximum file size to analyze (in MB)
    pub max_file_size_mb: u32,
    /// Maximum files per processing batch
    pub max_files_per_batch: usize,
    /// Analysis timeout per file (in seconds)
    pub analysis_timeout_seconds: u64,
    /// Checksum algorithm to use
    pub checksum_algorithm: String,
    /// Security scan depth level
    pub security_scan_depth: SecurityScanDepth,
}

impl Default for InventorySystemConfig {
    fn default() -> Self {
        Self {
            excluded_paths: vec![
                PathBuf::from("target"),
                PathBuf::from("node_modules"),
                PathBuf::from(".git"),
                PathBuf::from(".hypothesis"),
                PathBuf::from(".pytest_cache"),
                PathBuf::from("__pycache__"),
                PathBuf::from("vendor"),
                PathBuf::from("build"),
                PathBuf::from("dist"),
            ],
            excluded_patterns: vec![
                "*.tmp".to_string(),
                "*.log".to_string(),
                "*.cache".to_string(),
                "*.lock".to_string(),
                "*.bak".to_string(),
                "*.swp".to_string(),
                "*.swo".to_string(),
                "*~".to_string(),
                ".DS_Store".to_string(),
                "Thumbs.db".to_string(),
            ],
            included_patterns: Vec::new(),
            enable_parallel_processing: true,
            enable_checksum_verification: true,
            enable_security_scanning: true,
            max_file_size_mb: 100,
            max_files_per_batch: 1000,
            analysis_timeout_seconds: 300,
            checksum_algorithm: "SHA-256".to_string(),
            security_scan_depth: SecurityScanDepth::Deep,
        }
    }
}

/// Security scan depth levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecurityScanDepth {
    /// Surface-level scanning (file extensions, basic patterns)
    Surface,
    /// Standard scanning (content analysis, known vulnerabilities)
    Standard,
    /// Deep scanning (comprehensive analysis, advanced patterns)
    Deep,
}

/// Programming language detection results
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
    /// C# programming language
    CSharp,
    /// Java programming language
    Java,
    /// Go programming language
    Go,
    /// Swift programming language
    Swift,
    /// Kotlin programming language
    Kotlin,
    /// Ruby programming language
    Ruby,
    /// PHP programming language
    Php,
    /// Shell script
    Shell,
    /// PowerShell script
    PowerShell,
    /// Batch script
    Batch,
    /// JSON data format
    Json,
    /// YAML data format
    Yaml,
    /// TOML data format
    Toml,
    /// XML data format
    Xml,
    /// HTML markup language
    Html,
    /// CSS stylesheet language
    Css,
    /// SCSS stylesheet language
    Scss,
    /// SQL database language
    Sql,
    /// Markdown documentation
    Markdown,
    /// Plain text
    Text,
    /// Binary file
    Binary,
    /// Unknown or unrecognized language
    Unknown,
}

impl ProgrammingLanguage {
    /// Get the human-readable name of the programming language
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            ProgrammingLanguage::Rust => "Rust",
            ProgrammingLanguage::Python => "Python",
            ProgrammingLanguage::TypeScript => "TypeScript",
            ProgrammingLanguage::JavaScript => "JavaScript",
            ProgrammingLanguage::Cpp => "C++",
            ProgrammingLanguage::C => "C",
            ProgrammingLanguage::CSharp => "C#",
            ProgrammingLanguage::Java => "Java",
            ProgrammingLanguage::Go => "Go",
            ProgrammingLanguage::Swift => "Swift",
            ProgrammingLanguage::Kotlin => "Kotlin",
            ProgrammingLanguage::Ruby => "Ruby",
            ProgrammingLanguage::Php => "PHP",
            ProgrammingLanguage::Shell => "Shell",
            ProgrammingLanguage::PowerShell => "PowerShell",
            ProgrammingLanguage::Batch => "Batch",
            ProgrammingLanguage::Json => "JSON",
            ProgrammingLanguage::Yaml => "YAML",
            ProgrammingLanguage::Toml => "TOML",
            ProgrammingLanguage::Xml => "XML",
            ProgrammingLanguage::Html => "HTML",
            ProgrammingLanguage::Css => "CSS",
            ProgrammingLanguage::Scss => "SCSS",
            ProgrammingLanguage::Sql => "SQL",
            ProgrammingLanguage::Markdown => "Markdown",
            ProgrammingLanguage::Text => "Text",
            ProgrammingLanguage::Binary => "Binary",
            ProgrammingLanguage::Unknown => "Unknown",
        }
    }
    
    /// Check if the language is a programming language (not data format)
    #[must_use]
    pub const fn is_programming_language(self) -> bool {
        matches!(self, 
            ProgrammingLanguage::Rust | ProgrammingLanguage::Python | ProgrammingLanguage::TypeScript |
            ProgrammingLanguage::JavaScript | ProgrammingLanguage::Cpp | ProgrammingLanguage::C |
            ProgrammingLanguage::CSharp | ProgrammingLanguage::Java | ProgrammingLanguage::Go |
            ProgrammingLanguage::Swift | ProgrammingLanguage::Kotlin | ProgrammingLanguage::Ruby |
            ProgrammingLanguage::Php | ProgrammingLanguage::Shell | ProgrammingLanguage::PowerShell |
            ProgrammingLanguage::Batch | ProgrammingLanguage::Sql
        )
    }
    
    /// Check if the language is a data format
    #[must_use]
    pub const fn is_data_format(self) -> bool {
        matches!(self,
            ProgrammingLanguage::Json | ProgrammingLanguage::Yaml | ProgrammingLanguage::Toml |
            ProgrammingLanguage::Xml | ProgrammingLanguage::Html | ProgrammingLanguage::Css |
            ProgrammingLanguage::Scss
        )
    }
}

/// Security level classification for files
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SecurityLevel {
    /// Public - no security concerns
    Public,
    /// Internal - internal use only
    Internal,
    /// Confidential - sensitive information
    Confidential,
    /// Restricted - highly sensitive
    Restricted,
    /// Critical - security-critical components
    Critical,
}

impl SecurityLevel {
    /// Get the human-readable name of the security level
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            SecurityLevel::Public => "Public",
            SecurityLevel::Internal => "Internal",
            SecurityLevel::Confidential => "Confidential",
            SecurityLevel::Restricted => "Restricted",
            SecurityLevel::Critical => "Critical",
        }
    }
    
    /// Get the numeric security score (0-100)
    #[must_use]
    pub const fn score(self) -> u8 {
        match self {
            SecurityLevel::Public => 0,
            SecurityLevel::Internal => 25,
            SecurityLevel::Confidential => 50,
            SecurityLevel::Restricted => 75,
            SecurityLevel::Critical => 100,
        }
    }
}

/// Architectural patterns detected in files
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ArchitecturalPattern {
    /// Model-View-Controller pattern
    Mvc,
    /// Model-View-ViewModel pattern
    Mvvm,
    /// Repository pattern
    Repository,
    /// Factory pattern
    Factory,
    /// Singleton pattern
    Singleton,
    /// Observer pattern
    Observer,
    /// Strategy pattern
    Strategy,
    /// Command pattern
    Command,
    /// Adapter pattern
    Adapter,
    /// Decorator pattern
    Decorator,
    /// Facade pattern
    Facade,
    /// Proxy pattern
    Proxy,
    /// Builder pattern
    Builder,
    /// Dependency Injection pattern
    DependencyInjection,
    /// Event-driven architecture
    EventDriven,
    /// Microservices architecture
    Microservices,
    /// Layered architecture
    Layered,
    /// Hexagonal architecture
    Hexagonal,
    /// Clean architecture
    Clean,
    /// Domain-driven design
    DomainDriven,
    /// Test-driven development
    TestDriven,
    /// Behavior-driven development
    BehaviorDriven,
    /// Unknown or no specific pattern
    Unknown,
}

impl ArchitecturalPattern {
    /// Get the human-readable name of the architectural pattern
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            ArchitecturalPattern::Mvc => "Model-View-Controller",
            ArchitecturalPattern::Mvvm => "Model-View-ViewModel",
            ArchitecturalPattern::Repository => "Repository",
            ArchitecturalPattern::Factory => "Factory",
            ArchitecturalPattern::Singleton => "Singleton",
            ArchitecturalPattern::Observer => "Observer",
            ArchitecturalPattern::Strategy => "Strategy",
            ArchitecturalPattern::Command => "Command",
            ArchitecturalPattern::Adapter => "Adapter",
            ArchitecturalPattern::Decorator => "Decorator",
            ArchitecturalPattern::Facade => "Facade",
            ArchitecturalPattern::Proxy => "Proxy",
            ArchitecturalPattern::Builder => "Builder",
            ArchitecturalPattern::DependencyInjection => "Dependency Injection",
            ArchitecturalPattern::EventDriven => "Event-Driven",
            ArchitecturalPattern::Microservices => "Microservices",
            ArchitecturalPattern::Layered => "Layered",
            ArchitecturalPattern::Hexagonal => "Hexagonal",
            ArchitecturalPattern::Clean => "Clean Architecture",
            ArchitecturalPattern::DomainDriven => "Domain-Driven Design",
            ArchitecturalPattern::TestDriven => "Test-Driven Development",
            ArchitecturalPattern::BehaviorDriven => "Behavior-Driven Development",
            ArchitecturalPattern::Unknown => "Unknown",
        }
    }
}

/// Code complexity metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplexityMetrics {
    /// Total lines of code
    pub lines_of_code: u64,
    /// Lines of comments
    pub lines_of_comments: u64,
    /// Blank lines
    pub blank_lines: u64,
    /// Cyclomatic complexity
    pub cyclomatic_complexity: u32,
    /// Cognitive complexity
    pub cognitive_complexity: u32,
    /// Number of functions/methods
    pub function_count: u32,
    /// Number of classes/structs
    pub class_count: u32,
    /// Number of interfaces/traits
    pub interface_count: u32,
    /// Maximum nesting depth
    pub max_nesting_depth: u32,
    /// Average function length
    pub average_function_length: f64,
    /// Maintainability index (0-100)
    pub maintainability_index: f64,
    /// Technical debt ratio
    pub technical_debt_ratio: f64,
}

impl Default for ComplexityMetrics {
    fn default() -> Self {
        Self {
            lines_of_code: 0,
            lines_of_comments: 0,
            blank_lines: 0,
            cyclomatic_complexity: 1,
            cognitive_complexity: 0,
            function_count: 0,
            class_count: 0,
            interface_count: 0,
            max_nesting_depth: 0,
            average_function_length: 0.0,
            maintainability_index: 100.0,
            technical_debt_ratio: 0.0,
        }
    }
}

/// Dependency information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyInfo {
    /// Dependency name
    pub name: String,
    /// Dependency version (if available)
    pub version: Option<String>,
    /// Dependency type (e.g., "crate", "npm", "pip")
    pub dependency_type: String,
    /// Source location (e.g., "crates.io", "npmjs.com")
    pub source: Option<String>,
    /// License information
    pub license: Option<String>,
    /// Whether the dependency is direct or transitive
    pub is_direct: bool,
    /// Confidence score for dependency detection (0.0-1.0)
    pub confidence_score: f64,
    /// Known vulnerabilities
    pub vulnerabilities: Vec<String>,
    /// Last updated timestamp
    pub last_updated: Option<SystemTime>,
}

/// Security vulnerability information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityVulnerability {
    /// Vulnerability identifier (e.g., CVE-2023-1234)
    pub vulnerability_id: String,
    /// Vulnerability description
    pub description: String,
    /// Severity level (e.g., "Critical", "High", "Medium", "Low")
    pub severity: String,
    /// CVSS score (0.0-10.0)
    pub severity_score: f64,
    /// Affected component or dependency
    pub affected_component: String,
    /// Recommended fix or mitigation
    pub recommended_fix: Option<String>,
    /// Reference URLs for more information
    pub references: Vec<String>,
    /// Discovery timestamp
    pub discovered_at: SystemTime,
}

/// Orphaned file information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrphanedFileInfo {
    /// File path
    pub file_path: PathBuf,
    /// Reason why the file is considered orphaned
    pub orphan_reason: String,
    /// Last access time (if available)
    pub last_accessed: Option<SystemTime>,
    /// Last modification time
    pub last_modified: SystemTime,
    /// File size in bytes
    pub file_size: u64,
    /// Confidence score for orphan detection (0.0-1.0)
    pub confidence_score: f64,
    /// Recommended action (e.g., "delete", "archive", "review")
    pub recommended_action: String,
    /// Related files that might be affected
    pub related_files: Vec<PathBuf>,
}

/// Comprehensive file analysis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileAnalysisResult {
    /// File path relative to workspace root
    pub file_path: PathBuf,
    /// SHA-256 checksum of file content
    pub sha256_checksum: [u8; 32],
    /// Detected programming language
    pub programming_language: ProgrammingLanguage,
    /// File size in bytes
    pub file_size_bytes: u64,
    /// Security level classification
    pub security_level: SecurityLevel,
    /// Detected architectural patterns
    pub architectural_patterns: Vec<ArchitecturalPattern>,
    /// Code complexity metrics
    pub complexity_metrics: ComplexityMetrics,
    /// Resolved dependencies
    pub dependencies: Vec<DependencyInfo>,
    /// Security vulnerabilities found
    pub security_vulnerabilities: Vec<SecurityVulnerability>,
    /// File creation time (if available)
    pub created_at: Option<SystemTime>,
    /// Last modification time
    pub last_modified: SystemTime,
    /// Last access time (if available)
    pub last_accessed: Option<SystemTime>,
    /// File permissions (Unix-style)
    pub file_permissions: Option<u32>,
    /// File encoding (e.g., "UTF-8", "ASCII")
    pub file_encoding: String,
    /// MIME type
    pub mime_type: String,
    /// Analysis timestamp
    pub analyzed_at: SystemTime,
    /// Analysis duration
    pub analysis_duration: Duration,
    /// Author identity (from git or file metadata)
    pub author_identity: Option<String>,
}

/// Comprehensive inventory result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InventoryResult {
    /// Total number of files analyzed
    pub total_files: u64,
    /// Individual file analysis results
    pub analysis_results: Vec<FileAnalysisResult>,
    /// Comprehensive statistics
    pub statistics: InventoryStatistics,
    /// Inventory generation timestamp
    pub generation_timestamp: SystemTime,
    /// Whether checksum verification passed for all files
    pub checksum_verification_passed: bool,
    /// Whether security scanning completed successfully
    pub security_scan_completed: bool,
    /// Whether dependency resolution completed successfully
    pub dependency_resolution_completed: bool,
}

/// Comprehensive inventory statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InventoryStatistics {
    /// Total files analyzed
    pub total_files_analyzed: u64,
    /// Total lines of code across all files
    pub total_lines_of_code: u64,
    /// Programming languages detected with counts
    pub programming_languages_detected: HashMap<ProgrammingLanguage, u64>,
    /// Security vulnerabilities found
    pub security_vulnerabilities_found: u64,
    /// Dependencies resolved
    pub dependencies_resolved: u64,
    /// Orphaned files detected
    pub orphaned_files_detected: u64,
    /// Duplicate files found
    pub duplicate_files_found: u64,
    /// Average file size in bytes
    pub average_file_size_bytes: u64,
    /// Largest file size in bytes
    pub largest_file_size_bytes: u64,
    /// Total analysis duration
    pub analysis_duration: Duration,
    /// Peak memory usage during analysis
    pub memory_usage_peak: u64,
    /// Average CPU utilization during analysis
    pub cpu_utilization_average: f64,
    /// Errors encountered during analysis
    pub errors_encountered: u64,
    /// Warnings generated during analysis
    pub warnings_generated: u64,
}

impl Default for InventoryStatistics {
    fn default() -> Self {
        Self {
            total_files_analyzed: 0,
            total_lines_of_code: 0,
            programming_languages_detected: HashMap::new(),
            security_vulnerabilities_found: 0,
            dependencies_resolved: 0,
            orphaned_files_detected: 0,
            duplicate_files_found: 0,
            average_file_size_bytes: 0,
            largest_file_size_bytes: 0,
            analysis_duration: Duration::ZERO,
            memory_usage_peak: 0,
            cpu_utilization_average: 0.0,
            errors_encountered: 0,
            warnings_generated: 0,
        }
    }
}

/// File type classification based on extension and content
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum FileType {
    /// Source code file
    SourceCode,
    /// Configuration file
    Configuration,
    /// Documentation file
    Documentation,
    /// Test file
    Test,
    /// Build script or configuration
    Build,
    /// Data file
    Data,
    /// Asset file (images, fonts, etc.)
    Asset,
    /// Log file
    Log,
    /// Temporary file
    Temporary,
    /// Binary executable
    Binary,
    /// Library or archive
    Library,
    /// Unknown file type
    Unknown,
}

impl FileType {
    /// Get the human-readable name of the file type
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            FileType::SourceCode => "Source Code",
            FileType::Configuration => "Configuration",
            FileType::Documentation => "Documentation",
            FileType::Test => "Test",
            FileType::Build => "Build",
            FileType::Data => "Data",
            FileType::Asset => "Asset",
            FileType::Log => "Log",
            FileType::Temporary => "Temporary",
            FileType::Binary => "Binary",
            FileType::Library => "Library",
            FileType::Unknown => "Unknown",
        }
    }
}

/// Dependency relationship types
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DependencyRelationship {
    /// Direct dependency (explicitly declared)
    Direct,
    /// Transitive dependency (dependency of a dependency)
    Transitive,
    /// Development dependency (only needed for development)
    Development,
    /// Optional dependency (can be excluded)
    Optional,
    /// Peer dependency (expected to be provided by parent)
    Peer,
    /// Build dependency (only needed for building)
    Build,
    /// Runtime dependency (needed at runtime)
    Runtime,
}

impl DependencyRelationship {
    /// Get the human-readable name of the dependency relationship
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            DependencyRelationship::Direct => "Direct",
            DependencyRelationship::Transitive => "Transitive",
            DependencyRelationship::Development => "Development",
            DependencyRelationship::Optional => "Optional",
            DependencyRelationship::Peer => "Peer",
            DependencyRelationship::Build => "Build",
            DependencyRelationship::Runtime => "Runtime",
        }
    }
}

/// License classification for dependencies and files
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum LicenseType {
    /// MIT License
    Mit,
    /// Apache License 2.0
    Apache2,
    /// GNU General Public License v3
    Gpl3,
    /// GNU Lesser General Public License v3
    Lgpl3,
    /// BSD 3-Clause License
    Bsd3Clause,
    /// BSD 2-Clause License
    Bsd2Clause,
    /// Mozilla Public License 2.0
    Mpl2,
    /// ISC License
    Isc,
    /// Unlicense
    Unlicense,
    /// Creative Commons licenses
    CreativeCommons,
    /// Proprietary license
    Proprietary,
    /// Unknown or unrecognized license
    Unknown,
}

impl LicenseType {
    /// Get the human-readable name of the license
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            LicenseType::Mit => "MIT License",
            LicenseType::Apache2 => "Apache License 2.0",
            LicenseType::Gpl3 => "GNU General Public License v3.0",
            LicenseType::Lgpl3 => "GNU Lesser General Public License v3.0",
            LicenseType::Bsd3Clause => "BSD 3-Clause License",
            LicenseType::Bsd2Clause => "BSD 2-Clause License",
            LicenseType::Mpl2 => "Mozilla Public License 2.0",
            LicenseType::Isc => "ISC License",
            LicenseType::Unlicense => "The Unlicense",
            LicenseType::CreativeCommons => "Creative Commons License",
            LicenseType::Proprietary => "Proprietary License",
            LicenseType::Unknown => "Unknown License",
        }
    }
    
    /// Check if the license is copyleft
    #[must_use]
    pub const fn is_copyleft(self) -> bool {
        matches!(self, LicenseType::Gpl3 | LicenseType::Lgpl3 | LicenseType::Mpl2)
    }
    
    /// Check if the license is permissive
    #[must_use]
    pub const fn is_permissive(self) -> bool {
        matches!(self, 
            LicenseType::Mit | LicenseType::Apache2 | LicenseType::Bsd3Clause |
            LicenseType::Bsd2Clause | LicenseType::Isc | LicenseType::Unlicense
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_programming_language_classification() {
        assert!(ProgrammingLanguage::Rust.is_programming_language());
        assert!(ProgrammingLanguage::Python.is_programming_language());
        assert!(!ProgrammingLanguage::Json.is_programming_language());
        assert!(ProgrammingLanguage::Json.is_data_format());
        assert!(!ProgrammingLanguage::Rust.is_data_format());
    }
    
    #[test]
    fn test_security_level_ordering() {
        assert!(SecurityLevel::Public < SecurityLevel::Critical);
        assert!(SecurityLevel::Internal < SecurityLevel::Confidential);
        assert_eq!(SecurityLevel::Critical.score(), 100);
        assert_eq!(SecurityLevel::Public.score(), 0);
    }
    
    #[test]
    fn test_license_type_classification() {
        assert!(LicenseType::Mit.is_permissive());
        assert!(!LicenseType::Mit.is_copyleft());
        assert!(LicenseType::Gpl3.is_copyleft());
        assert!(!LicenseType::Gpl3.is_permissive());
    }
    
    #[test]
    fn test_complexity_metrics_default() {
        let metrics = ComplexityMetrics::default();
        assert_eq!(metrics.cyclomatic_complexity, 1);
        assert_eq!(metrics.maintainability_index, 100.0);
        assert_eq!(metrics.technical_debt_ratio, 0.0);
    }
    
    #[test]
    fn test_inventory_config_default() {
        let config = InventorySystemConfig::default();
        assert!(config.enable_parallel_processing);
        assert!(config.enable_checksum_verification);
        assert!(config.enable_security_scanning);
        assert_eq!(config.checksum_algorithm, "SHA-256");
        assert!(!config.excluded_paths.is_empty());
    }
}