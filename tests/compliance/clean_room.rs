//! # Clean Room Compliance Verification System
//! 
//! Comprehensive clean room development methodology compliance verification
//! with intellectual property validation and legal compliance enforcement.
//! 
//! ## MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE)
//! - **NO MINIMALISM:** Complete IP compliance with comprehensive validation
//! - **NO SHORTCUTS:** Full clean room methodology verification
//! - **PRODUCTION STANDARDS:** Legal compliance for millions of users over 20+ years

use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::SystemTime;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

/// Clean room compliance verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceResult {
    pub test_id: String,
    pub timestamp: SystemTime,
    pub overall_compliance: bool,
    pub violations: Vec<ComplianceViolation>,
    pub verification_results: Vec<VerificationResult>,
    pub attribution_status: AttributionStatus,
    pub clean_room_score: f64,
}

/// Compliance violation details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceViolation {
    pub violation_type: ViolationType,
    pub severity: ViolationSeverity,
    pub file_path: String,
    pub description: String,
    pub recommendation: String,
}

/// Types of compliance violations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ViolationType {
    ForeignCodeResidue,
    MissingAttribution,
    IncorrectAttribution,
    UnauthorizedDependency,
    LicenseViolation,
    CopyrightViolation,
    PatentViolation,
    TrademarkViolation,
}

/// Severity levels for violations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ViolationSeverity {
    Critical,
    High,
    Medium,
    Low,
    Info,
}

/// Verification result for specific compliance check
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    pub check_name: String,
    pub passed: bool,
    pub details: String,
    pub evidence: Vec<String>,
}

/// Attribution status summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttributionStatus {
    pub attribution_file_exists: bool,
    pub attribution_complete: bool,
    pub missing_attributions: Vec<String>,
    pub incorrect_attributions: Vec<String>,
}

/// Clean room compliance verifier
pub struct CleanRoomVerifier {
    project_root: PathBuf,
    excluded_paths: HashSet<String>,
    known_repositories: HashMap<String, RepositoryInfo>,
}

/// Repository information for compliance tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepositoryInfo {
    pub name: String,
    pub url: String,
    pub license: String,
    pub extracted_files: Vec<String>,
    pub attribution_required: bool,
}

impl CleanRoomVerifier {
    /// Create a new clean room verifier
    pub fn new(project_root: PathBuf) -> Self {
        let mut excluded_paths = HashSet::new();
        excluded_paths.insert("target".to_string());
        excluded_paths.insert(".git".to_string());
        excluded_paths.insert("node_modules".to_string());
        excluded_paths.insert("build".to_string());
        excluded_paths.insert("dist".to_string());
        
        Self {
            project_root,
            excluded_paths,
            known_repositories: HashMap::new(),
        }
    }
    
    /// Run comprehensive clean room compliance verification
    pub fn verify_compliance(&self) -> Result<ComplianceResult, Box<dyn std::error::Error>> {
        let test_id = format!("clean_room_{}", SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)?
            .as_secs());
        
        println!("🔍 Starting clean room compliance verification...");
        
        let mut violations = Vec::new();
        let mut verification_results = Vec::new();
        
        // Check for foreign code residue
        let foreign_code_result = self.check_foreign_code_residue()?;
        verification_results.push(foreign_code_result.clone());
        if !foreign_code_result.passed {
            violations.push(ComplianceViolation {
                violation_type: ViolationType::ForeignCodeResidue,
                severity: ViolationSeverity::Critical,
                file_path: "multiple".to_string(),
                description: "Foreign code residue detected".to_string(),
                recommendation: "Remove all foreign code and reimplement cleanly".to_string(),
            });
        }
        
        // Verify attribution completeness
        let attribution_result = self.verify_attribution_completeness()?;
        verification_results.push(attribution_result.clone());
        
        // Check license compliance
        let license_result = self.check_license_compliance()?;
        verification_results.push(license_result.clone());
        
        // Verify repository cleanup
        let cleanup_result = self.verify_repository_cleanup()?;
        verification_results.push(cleanup_result.clone());
        
        // Check dependency compliance
        let dependency_result = self.check_dependency_compliance()?;
        verification_results.push(dependency_result.clone());
        
        // Verify build reproducibility
        let reproducibility_result = self.verify_build_reproducibility()?;
        verification_results.push(reproducibility_result.clone());
        
        // Calculate compliance score
        let clean_room_score = self.calculate_compliance_score(&verification_results);
        
        // Determine overall compliance
        let overall_compliance = violations.is_empty() && 
            verification_results.iter().all(|r| r.passed) &&
            clean_room_score >= 95.0;
        
        let attribution_status = self.analyze_attribution_status()?;
        
        Ok(ComplianceResult {
            test_id,
            timestamp: SystemTime::now(),
            overall_compliance,
            violations,
            verification_results,
            attribution_status,
            clean_room_score,
        })
    }
}
    
    /// Check for foreign code residue
    fn check_foreign_code_residue(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Checking for foreign code residue...");
        
        let mut evidence = Vec::new();
        let mut foreign_patterns_found = 0;
        
        // Patterns that indicate foreign code residue
        let foreign_patterns = vec![
            // Common foreign repository indicators
            r"github\.com/(?!your-org/)",
            r"gitlab\.com/(?!your-org/)",
            r"bitbucket\.org/(?!your-org/)",
            
            // Foreign copyright notices
            r"Copyright.*(?:Google|Microsoft|Facebook|Apple|Amazon|Netflix|Uber)",
            r"Licensed under.*(?:MIT|Apache|BSD|GPL).*(?:Google|Microsoft|Facebook)",
            
            // Foreign author information
            r"Author:.*@(?:google|microsoft|facebook|apple|amazon)\.com",
            r"Maintainer:.*@(?:google|microsoft|facebook|apple|amazon)\.com",
            
            // Foreign project references
            r"Original.*(?:implementation|code|project).*from",
            r"Adapted.*from.*(?:github|gitlab|bitbucket)",
            r"Based.*on.*(?:github|gitlab|bitbucket)",
            
            // Foreign license headers
            r"Licensed under the Apache License, Version 2\.0",
            r"MIT License.*Permission is hereby granted",
            r"BSD.*Redistribution and use in source and binary forms",
        ];
        
        for entry in WalkDir::new(&self.project_root)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
        {
            let path = entry.path();
            
            // Skip excluded directories
            if self.should_skip_path(path) {
                continue;
            }
            
            // Only check text files
            if let Some(extension) = path.extension() {
                let ext = extension.to_string_lossy().to_lowercase();
                if !matches!(ext.as_str(), "rs" | "py" | "cpp" | "c" | "h" | "js" | "ts" | "md" | "txt" | "toml" | "yaml" | "yml" | "json") {
                    continue;
                }
            }
            
            if let Ok(content) = fs::read_to_string(path) {
                for pattern in &foreign_patterns {
                    if let Ok(regex) = regex::Regex::new(pattern) {
                        if regex.is_match(&content) {
                            foreign_patterns_found += 1;
                            evidence.push(format!("Foreign pattern found in {}: {}", 
                                path.display(), pattern));
                        }
                    }
                }
            }
        }
        
        let passed = foreign_patterns_found == 0;
        let details = if passed {
            "No foreign code residue detected".to_string()
        } else {
            format!("Found {} instances of potential foreign code residue", foreign_patterns_found)
        };
        
        Ok(VerificationResult {
            check_name: "Foreign Code Residue Check".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Verify attribution completeness
    fn verify_attribution_completeness(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Verifying attribution completeness...");
        
        let mut evidence = Vec::new();
        let attribution_file = self.project_root.join("vendor").join("ATTRIBUTION.md");
        
        let attribution_exists = attribution_file.exists();
        evidence.push(format!("Attribution file exists: {}", attribution_exists));
        
        if !attribution_exists {
            return Ok(VerificationResult {
                check_name: "Attribution Completeness".to_string(),
                passed: false,
                details: "ATTRIBUTION.md file not found in vendor directory".to_string(),
                evidence,
            });
        }
        
        // Read and analyze attribution file
        let attribution_content = fs::read_to_string(&attribution_file)?;
        
        // Check for required sections
        let required_sections = vec![
            "# Attribution",
            "## Third-Party Libraries",
            "## Algorithm Sources",
            "## Clean Room Implementation",
        ];
        
        let mut missing_sections = Vec::new();
        for section in &required_sections {
            if !attribution_content.contains(section) {
                missing_sections.push(section.to_string());
            }
        }
        
        if !missing_sections.is_empty() {
            evidence.push(format!("Missing sections: {:?}", missing_sections));
        }
        
        // Check for proper attribution format
        let has_proper_format = attribution_content.contains("License:") && 
                               attribution_content.contains("Source:") &&
                               attribution_content.contains("Usage:");
        
        evidence.push(format!("Proper attribution format: {}", has_proper_format));
        
        let passed = missing_sections.is_empty() && has_proper_format;
        let details = if passed {
            "Attribution file is complete and properly formatted".to_string()
        } else {
            format!("Attribution issues found: missing sections or improper format")
        };
        
        Ok(VerificationResult {
            check_name: "Attribution Completeness".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Check license compliance
    fn check_license_compliance(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Checking license compliance...");
        
        let mut evidence = Vec::new();
        let mut license_issues = 0;
        
        // Check Cargo.toml for license information
        let cargo_toml = self.project_root.join("Cargo.toml");
        if cargo_toml.exists() {
            let content = fs::read_to_string(&cargo_toml)?;
            
            if content.contains("license = ") {
                evidence.push("License specified in Cargo.toml".to_string());
            } else {
                license_issues += 1;
                evidence.push("No license specified in Cargo.toml".to_string());
            }
        }
        
        // Check for LICENSE file
        let license_files = vec!["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"];
        let mut license_file_found = false;
        
        for license_file in &license_files {
            let license_path = self.project_root.join(license_file);
            if license_path.exists() {
                license_file_found = true;
                evidence.push(format!("License file found: {}", license_file));
                break;
            }
        }
        
        if !license_file_found {
            license_issues += 1;
            evidence.push("No LICENSE file found".to_string());
        }
        
        // Check for consistent license headers
        let mut files_without_headers = 0;
        let mut total_source_files = 0;
        
        for entry in WalkDir::new(&self.project_root)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
        {
            let path = entry.path();
            
            if self.should_skip_path(path) {
                continue;
            }
            
            if let Some(extension) = path.extension() {
                let ext = extension.to_string_lossy().to_lowercase();
                if matches!(ext.as_str(), "rs" | "py" | "cpp" | "c" | "h") {
                    total_source_files += 1;
                    
                    if let Ok(content) = fs::read_to_string(path) {
                        if !content.contains("Copyright") && !content.contains("SPDX-License-Identifier") {
                            files_without_headers += 1;
                        }
                    }
                }
            }
        }
        
        evidence.push(format!("Source files without license headers: {}/{}", 
            files_without_headers, total_source_files));
        
        if files_without_headers > total_source_files / 10 {  // Allow 10% without headers
            license_issues += 1;
        }
        
        let passed = license_issues == 0;
        let details = if passed {
            "License compliance verified".to_string()
        } else {
            format!("Found {} license compliance issues", license_issues)
        };
        
        Ok(VerificationResult {
            check_name: "License Compliance".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Verify repository cleanup (no foreign repositories remain)
    fn verify_repository_cleanup(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Verifying repository cleanup...");
        
        let mut evidence = Vec::new();
        let mut foreign_repos_found = 0;
        
        // Check for .git directories (other than the main one)
        for entry in WalkDir::new(&self.project_root)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_dir())
        {
            let path = entry.path();
            
            if path.file_name() == Some(std::ffi::OsStr::new(".git")) && 
               path != self.project_root.join(".git") {
                foreign_repos_found += 1;
                evidence.push(format!("Foreign .git directory found: {}", path.display()));
            }
        }
        
        // Check for common repository indicators
        let repo_indicators = vec![
            ".gitmodules",
            ".gitignore_foreign",
            "README_original.md",
            "LICENSE_original",
        ];
        
        for indicator in &repo_indicators {
            let indicator_path = self.project_root.join(indicator);
            if indicator_path.exists() {
                foreign_repos_found += 1;
                evidence.push(format!("Repository indicator found: {}", indicator));
            }
        }
        
        // Check for foreign remote URLs in git config
        if let Ok(output) = Command::new("git")
            .args(&["remote", "-v"])
            .current_dir(&self.project_root)
            .output()
        {
            let remotes = String::from_utf8_lossy(&output.stdout);
            let foreign_remotes = vec![
                "github.com/google/",
                "github.com/microsoft/",
                "github.com/facebook/",
                "github.com/apple/",
                "github.com/amazon/",
                "gitlab.com/",
                "bitbucket.org/",
            ];
            
            for foreign_remote in &foreign_remotes {
                if remotes.contains(foreign_remote) {
                    foreign_repos_found += 1;
                    evidence.push(format!("Foreign remote URL found: {}", foreign_remote));
                }
            }
        }
        
        let passed = foreign_repos_found == 0;
        let details = if passed {
            "Repository cleanup verified - no foreign repositories found".to_string()
        } else {
            format!("Found {} foreign repository indicators", foreign_repos_found)
        };
        
        Ok(VerificationResult {
            check_name: "Repository Cleanup".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Check dependency compliance
    fn check_dependency_compliance(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Checking dependency compliance...");
        
        let mut evidence = Vec::new();
        let mut compliance_issues = 0;
        
        // Check Cargo.toml dependencies
        let cargo_toml = self.project_root.join("Cargo.toml");
        if cargo_toml.exists() {
            let content = fs::read_to_string(&cargo_toml)?;
            
            // Parse dependencies (simplified)
            let lines: Vec<&str> = content.lines().collect();
            let mut in_dependencies = false;
            let mut dependencies = Vec::new();
            
            for line in lines {
                if line.trim() == "[dependencies]" {
                    in_dependencies = true;
                    continue;
                }
                
                if line.starts_with('[') && line != "[dependencies]" {
                    in_dependencies = false;
                }
                
                if in_dependencies && line.contains('=') {
                    if let Some(dep_name) = line.split('=').next() {
                        dependencies.push(dep_name.trim().to_string());
                    }
                }
            }
            
            evidence.push(format!("Found {} dependencies in Cargo.toml", dependencies.len()));
            
            // Check for problematic dependencies
            let problematic_deps = vec![
                "openssl-sys",  // May have licensing issues
                "ring",         // May have patent issues
                "webpki",       // May have licensing issues
            ];
            
            for dep in &dependencies {
                if problematic_deps.contains(&dep.as_str()) {
                    compliance_issues += 1;
                    evidence.push(format!("Potentially problematic dependency: {}", dep));
                }
            }
        }
        
        // Check for Python dependencies
        let requirements_txt = self.project_root.join("requirements.txt");
        if requirements_txt.exists() {
            let content = fs::read_to_string(&requirements_txt)?;
            let python_deps: Vec<&str> = content.lines()
                .filter(|line| !line.trim().is_empty() && !line.starts_with('#'))
                .collect();
            
            evidence.push(format!("Found {} Python dependencies", python_deps.len()));
            
            // Check for GPL dependencies (may be problematic)
            let gpl_deps = vec!["mysql-python", "psycopg2"];
            for dep_line in &python_deps {
                let dep_name = dep_line.split("==").next().unwrap_or(dep_line).trim();
                if gpl_deps.contains(&dep_name) {
                    compliance_issues += 1;
                    evidence.push(format!("GPL dependency found: {}", dep_name));
                }
            }
        }
        
        let passed = compliance_issues == 0;
        let details = if passed {
            "All dependencies are compliant".to_string()
        } else {
            format!("Found {} dependency compliance issues", compliance_issues)
        };
        
        Ok(VerificationResult {
            check_name: "Dependency Compliance".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Verify build reproducibility
    fn verify_build_reproducibility(&self) -> Result<VerificationResult, Box<dyn std::error::Error>> {
        println!("🔍 Verifying build reproducibility...");
        
        let mut evidence = Vec::new();
        let mut reproducibility_score = 100.0;
        
        // Check for deterministic build configuration
        let cargo_toml = self.project_root.join("Cargo.toml");
        if cargo_toml.exists() {
            let content = fs::read_to_string(&cargo_toml)?;
            
            // Check for version pinning
            if content.contains("version = \"") {
                evidence.push("Version specified in Cargo.toml".to_string());
            } else {
                reproducibility_score -= 10.0;
                evidence.push("No version specified in Cargo.toml".to_string());
            }
            
            // Check for edition specification
            if content.contains("edition = ") {
                evidence.push("Rust edition specified".to_string());
            } else {
                reproducibility_score -= 5.0;
                evidence.push("No Rust edition specified".to_string());
            }
        }
        
        // Check for Cargo.lock file
        let cargo_lock = self.project_root.join("Cargo.lock");
        if cargo_lock.exists() {
            evidence.push("Cargo.lock file present for reproducible builds".to_string());
        } else {
            reproducibility_score -= 20.0;
            evidence.push("Cargo.lock file missing".to_string());
        }
        
        // Check for build scripts
        let build_script = self.project_root.join("build.rs");
        if build_script.exists() {
            evidence.push("Build script found - checking for determinism".to_string());
            
            let content = fs::read_to_string(&build_script)?;
            
            // Check for non-deterministic operations
            let non_deterministic_patterns = vec![
                "SystemTime::now()",
                "rand::",
                "thread_rng()",
                "std::env::var(\"HOME\")",
                "std::env::var(\"USER\")",
            ];
            
            for pattern in &non_deterministic_patterns {
                if content.contains(pattern) {
                    reproducibility_score -= 15.0;
                    evidence.push(format!("Non-deterministic pattern in build.rs: {}", pattern));
                }
            }
        }
        
        let passed = reproducibility_score >= 80.0;
        let details = format!("Build reproducibility score: {:.1}%", reproducibility_score);
        
        Ok(VerificationResult {
            check_name: "Build Reproducibility".to_string(),
            passed,
            details,
            evidence,
        })
    }
    
    /// Calculate overall compliance score
    fn calculate_compliance_score(&self, results: &[VerificationResult]) -> f64 {
        if results.is_empty() {
            return 0.0;
        }
        
        let passed_count = results.iter().filter(|r| r.passed).count();
        (passed_count as f64 / results.len() as f64) * 100.0
    }
    
    /// Analyze attribution status
    fn analyze_attribution_status(&self) -> Result<AttributionStatus, Box<dyn std::error::Error>> {
        let attribution_file = self.project_root.join("vendor").join("ATTRIBUTION.md");
        let attribution_file_exists = attribution_file.exists();
        
        if !attribution_file_exists {
            return Ok(AttributionStatus {
                attribution_file_exists: false,
                attribution_complete: false,
                missing_attributions: vec!["ATTRIBUTION.md file not found".to_string()],
                incorrect_attributions: vec![],
            });
        }
        
        let content = fs::read_to_string(&attribution_file)?;
        
        // Simple analysis - in production, this would be more sophisticated
        let attribution_complete = content.len() > 100 && 
                                 content.contains("License:") &&
                                 content.contains("Source:");
        
        Ok(AttributionStatus {
            attribution_file_exists: true,
            attribution_complete,
            missing_attributions: vec![],
            incorrect_attributions: vec![],
        })
    }
    
    /// Check if a path should be skipped during verification
    fn should_skip_path(&self, path: &Path) -> bool {
        for component in path.components() {
            if let Some(component_str) = component.as_os_str().to_str() {
                if self.excluded_paths.contains(component_str) {
                    return true;
                }
            }
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    
    #[test]
    fn test_clean_room_verifier_creation() {
        let current_dir = env::current_dir().unwrap();
        let verifier = CleanRoomVerifier::new(current_dir);
        assert!(!verifier.excluded_paths.is_empty());
    }
    
    #[test]
    fn test_should_skip_path() {
        let current_dir = env::current_dir().unwrap();
        let verifier = CleanRoomVerifier::new(current_dir.clone());
        
        let target_path = current_dir.join("target").join("debug");
        assert!(verifier.should_skip_path(&target_path));
        
        let src_path = current_dir.join("src").join("main.rs");
        assert!(!verifier.should_skip_path(&src_path));
    }
    
    #[test]
    fn test_compliance_score_calculation() {
        let current_dir = env::current_dir().unwrap();
        let verifier = CleanRoomVerifier::new(current_dir);
        
        let results = vec![
            VerificationResult {
                check_name: "Test 1".to_string(),
                passed: true,
                details: "Passed".to_string(),
                evidence: vec![],
            },
            VerificationResult {
                check_name: "Test 2".to_string(),
                passed: false,
                details: "Failed".to_string(),
                evidence: vec![],
            },
        ];
        
        let score = verifier.calculate_compliance_score(&results);
        assert_eq!(score, 50.0);
    }
}