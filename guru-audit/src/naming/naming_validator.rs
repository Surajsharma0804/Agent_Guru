// Naming Validator for GURU Production Audit System
//
// This module provides style guide enforcement and consistency checking for file names.
// It ensures all file names follow language-specific conventions and project standards.
//
// MAXIMUM ENGINEERING MANDATE:
// - Complete style guide enforcement with comprehensive validation
// - Consistency checking across entire codebase
// - Production-grade implementation for millions of files over 20+ years

use crate::naming::types::*;
use anyhow::{Context, Result};
use regex::Regex;
use std::collections::HashMap;
use std::path::Path;
use tracing::{debug, info};

/// Naming validator with style guide enforcement
pub struct NamingValidator {
    /// Style guides for different languages
    style_guides: HashMap<ProgrammingLanguage, StyleGuide>,
    /// Compiled regex patterns for validation
    validation_patterns: HashMap<ProgrammingLanguage, Vec<Regex>>,
}

impl NamingValidator {
    /// Create a new naming validator with default style guides
    pub fn new() -> Result<Self> {
        let mut style_guides = HashMap::new();
        let mut validation_patterns = HashMap::new();
        
        // Rust style guide
        style_guides.insert(
            ProgrammingLanguage::Rust,
            StyleGuide {
                language: ProgrammingLanguage::Rust,
                naming_style: NamingStyle::SnakeCase,
                max_name_length: 64,
                min_name_length: 3,
                forbidden_prefixes: vec!["test_".to_string()],
                forbidden_suffixes: vec!["_old".to_string(), "_backup".to_string()],
                required_patterns: vec![],
            },
        );
        
        validation_patterns.insert(
            ProgrammingLanguage::Rust,
            vec![
                Regex::new(r"^[a-z][a-z0-9_]*\.rs$")?,
            ],
        );
        
        // Python style guide
        style_guides.insert(
            ProgrammingLanguage::Python,
            StyleGuide {
                language: ProgrammingLanguage::Python,
                naming_style: NamingStyle::SnakeCase,
                max_name_length: 64,
                min_name_length: 3,
                forbidden_prefixes: vec!["test_".to_string()],
                forbidden_suffixes: vec!["_old".to_string(), "_backup".to_string()],
                required_patterns: vec![],
            },
        );
        
        validation_patterns.insert(
            ProgrammingLanguage::Python,
            vec![
                Regex::new(r"^[a-z][a-z0-9_]*\.py$")?,
            ],
        );
        
        // TypeScript style guide
        style_guides.insert(
            ProgrammingLanguage::TypeScript,
            StyleGuide {
                language: ProgrammingLanguage::TypeScript,
                naming_style: NamingStyle::CamelCase,
                max_name_length: 64,
                min_name_length: 3,
                forbidden_prefixes: vec![],
                forbidden_suffixes: vec![".old".to_string(), ".backup".to_string()],
                required_patterns: vec![],
            },
        );
        
        validation_patterns.insert(
            ProgrammingLanguage::TypeScript,
            vec![
                Regex::new(r"^[a-z][a-zA-Z0-9]*\.tsx?$")?,
            ],
        );
        
        // JavaScript style guide
        style_guides.insert(
            ProgrammingLanguage::JavaScript,
            StyleGuide {
                language: ProgrammingLanguage::JavaScript,
                naming_style: NamingStyle::CamelCase,
                max_name_length: 64,
                min_name_length: 3,
                forbidden_prefixes: vec![],
                forbidden_suffixes: vec![".old".to_string(), ".backup".to_string()],
                required_patterns: vec![],
            },
        );
        
        validation_patterns.insert(
            ProgrammingLanguage::JavaScript,
            vec![
                Regex::new(r"^[a-z][a-zA-Z0-9]*\.jsx?$")?,
            ],
        );
        
        Ok(Self {
            style_guides,
            validation_patterns,
        })
    }
    
    /// Validate a file name against style guide
    pub fn validate_name(&self, file_path: &Path) -> Result<ValidationResult> {
        let file_name = file_path
            .file_name()
            .and_then(|n| n.to_str())
            .context("Invalid file name")?;
        
        let language = self.detect_language(file_path);
        let style_guide = self.style_guides.get(&language);
        
        let mut violations = Vec::new();
        let mut suggestions = Vec::new();
        
        if let Some(guide) = style_guide {
            // Check name length
            let name_without_ext = file_path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("");
            
            if name_without_ext.len() > guide.max_name_length {
                violations.push(StyleViolation {
                    violation_type: ViolationType::NameTooLong,
                    message: format!(
                        "Name '{}' exceeds maximum length of {} characters",
                        name_without_ext, guide.max_name_length
                    ),
                    severity: Severity::Error,
                });
                suggestions.push(format!(
                    "Consider shortening to: {}",
                    &name_without_ext[..guide.max_name_length]
                ));
            }
            
            if name_without_ext.len() < guide.min_name_length {
                violations.push(StyleViolation {
                    violation_type: ViolationType::NameTooShort,
                    message: format!(
                        "Name '{}' is shorter than minimum length of {} characters",
                        name_without_ext, guide.min_name_length
                    ),
                    severity: Severity::Error,
                });
            }
            
            // Check forbidden prefixes
            for prefix in &guide.forbidden_prefixes {
                if name_without_ext.starts_with(prefix) {
                    violations.push(StyleViolation {
                        violation_type: ViolationType::ForbiddenPrefix,
                        message: format!("Name uses forbidden prefix: {}", prefix),
                        severity: Severity::Warning,
                    });
                    suggestions.push(format!(
                        "Remove prefix: {}",
                        name_without_ext.strip_prefix(prefix).unwrap_or(name_without_ext)
                    ));
                }
            }
            
            // Check forbidden suffixes
            for suffix in &guide.forbidden_suffixes {
                if name_without_ext.ends_with(suffix) {
                    violations.push(StyleViolation {
                        violation_type: ViolationType::ForbiddenSuffix,
                        message: format!("Name uses forbidden suffix: {}", suffix),
                        severity: Severity::Warning,
                    });
                    suggestions.push(format!(
                        "Remove suffix: {}",
                        name_without_ext.strip_suffix(suffix).unwrap_or(name_without_ext)
                    ));
                }
            }
            
            // Check naming style
            if let Some(patterns) = self.validation_patterns.get(&language) {
                let matches_pattern = patterns.iter().any(|p| p.is_match(file_name));
                
                if !matches_pattern {
                    violations.push(StyleViolation {
                        violation_type: ViolationType::InvalidNamingStyle,
                        message: format!(
                            "Name '{}' does not follow {:?} style",
                            file_name, guide.naming_style
                        ),
                        severity: Severity::Error,
                    });
                    
                    // Suggest correct style
                    match guide.naming_style {
                        NamingStyle::SnakeCase => {
                            suggestions.push(self.to_snake_case(name_without_ext));
                        }
                        NamingStyle::CamelCase => {
                            suggestions.push(self.to_camel_case(name_without_ext));
                        }
                        NamingStyle::PascalCase => {
                            suggestions.push(self.to_pascal_case(name_without_ext));
                        }
                        NamingStyle::KebabCase => {
                            suggestions.push(self.to_kebab_case(name_without_ext));
                        }
                    }
                }
            }
        }
        
        let is_valid = violations.is_empty();
        
        if is_valid {
            info!("File name '{}' passes validation", file_name);
        } else {
            debug!("File name '{}' has {} violations", file_name, violations.len());
        }
        
        Ok(ValidationResult {
            is_valid,
            violations,
            suggestions,
        })
    }
    
    /// Check consistency across multiple files
    pub fn check_consistency(&self, files: &[&Path]) -> Result<Vec<StyleViolation>> {
        let mut violations = Vec::new();
        let mut naming_styles: HashMap<ProgrammingLanguage, Vec<NamingStyle>> = HashMap::new();
        
        // Collect naming styles used for each language
        for file_path in files {
            let language = self.detect_language(file_path);
            let style = self.detect_naming_style(file_path)?;
            
            naming_styles
                .entry(language)
                .or_default()
                .push(style);
        }
        
        // Check for inconsistencies
        for (language, styles) in naming_styles {
            let unique_styles: std::collections::HashSet<_> = styles.iter().collect();
            
            if unique_styles.len() > 1 {
                violations.push(StyleViolation {
                    violation_type: ViolationType::InvalidNamingStyle,
                    message: format!(
                        "Inconsistent naming styles found for {:?}: {:?}",
                        language, unique_styles
                    ),
                    severity: Severity::Warning,
                });
            }
        }
        
        Ok(violations)
    }
    
    /// Detect the naming style used in a file name
    fn detect_naming_style(&self, file_path: &Path) -> Result<NamingStyle> {
        let name = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .context("Invalid file name")?;
        
        if name.contains('_') {
            Ok(NamingStyle::SnakeCase)
        } else if name.contains('-') {
            Ok(NamingStyle::KebabCase)
        } else if name.chars().next().map_or(false, |c| c.is_uppercase()) {
            Ok(NamingStyle::PascalCase)
        } else {
            Ok(NamingStyle::CamelCase)
        }
    }
    
    /// Detect programming language from file extension
    pub fn detect_language(&self, path: &Path) -> ProgrammingLanguage {
        match path.extension().and_then(|s| s.to_str()) {
            Some("rs") => ProgrammingLanguage::Rust,
            Some("py") => ProgrammingLanguage::Python,
            Some("ts") | Some("tsx") => ProgrammingLanguage::TypeScript,
            Some("js") | Some("jsx") => ProgrammingLanguage::JavaScript,
            Some("cpp") | Some("cc") | Some("cxx") | Some("hpp") => ProgrammingLanguage::Cpp,
            Some("c") | Some("h") => ProgrammingLanguage::C,
            Some("go") => ProgrammingLanguage::Go,
            _ => ProgrammingLanguage::Unknown,
        }
    }
    
    /// Convert name to snake_case
    pub fn to_snake_case(&self, name: &str) -> String {
        let mut result = String::new();
        let mut prev_lowercase = false;
        
        for (i, ch) in name.chars().enumerate() {
            if ch.is_uppercase() {
                if i > 0 && prev_lowercase {
                    result.push('_');
                }
                result.push(ch.to_lowercase().next().unwrap());
                prev_lowercase = false;
            } else if ch == '-' || ch == ' ' {
                result.push('_');
                prev_lowercase = false;
            } else {
                result.push(ch);
                prev_lowercase = ch.is_lowercase();
            }
        }
        
        result
    }
    
    /// Convert name to camelCase
    pub fn to_camel_case(&self, name: &str) -> String {
        let mut result = String::new();
        let mut capitalize_next = false;
        
        for (i, ch) in name.chars().enumerate() {
            if ch == '_' || ch == '-' || ch == ' ' {
                capitalize_next = true;
            } else if capitalize_next {
                result.push(ch.to_uppercase().next().unwrap());
                capitalize_next = false;
            } else if i == 0 {
                result.push(ch.to_lowercase().next().unwrap());
            } else {
                result.push(ch);
            }
        }
        
        result
    }
    
    /// Convert name to PascalCase
    pub fn to_pascal_case(&self, name: &str) -> String {
        let camel = self.to_camel_case(name);
        let mut chars = camel.chars();
        match chars.next() {
            None => String::new(),
            Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
        }
    }
    
    /// Convert name to kebab-case
    pub fn to_kebab_case(&self, name: &str) -> String {
        self.to_snake_case(name).replace('_', "-")
    }
}

impl Default for NamingValidator {
    fn default() -> Self {
        Self::new().expect("Failed to create NamingValidator")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_naming_validator_creation() {
        let validator = NamingValidator::new();
        assert!(validator.is_ok());
    }
    
    #[test]
    fn test_to_snake_case() {
        let validator = NamingValidator::new().unwrap();
        
        assert_eq!(validator.to_snake_case("CamelCase"), "camel_case");
        assert_eq!(validator.to_snake_case("PascalCase"), "pascal_case");
        assert_eq!(validator.to_snake_case("kebab-case"), "kebab_case");
        assert_eq!(validator.to_snake_case("already_snake"), "already_snake");
    }
    
    #[test]
    fn test_to_camel_case() {
        let validator = NamingValidator::new().unwrap();
        
        assert_eq!(validator.to_camel_case("snake_case"), "snakeCase");
        assert_eq!(validator.to_camel_case("kebab-case"), "kebabCase");
        assert_eq!(validator.to_camel_case("PascalCase"), "pascalCase");
    }
    
    #[test]
    fn test_to_pascal_case() {
        let validator = NamingValidator::new().unwrap();
        
        assert_eq!(validator.to_pascal_case("snake_case"), "SnakeCase");
        assert_eq!(validator.to_pascal_case("camelCase"), "CamelCase");
        assert_eq!(validator.to_pascal_case("kebab-case"), "KebabCase");
    }
    
    #[test]
    fn test_to_kebab_case() {
        let validator = NamingValidator::new().unwrap();
        
        assert_eq!(validator.to_kebab_case("snake_case"), "snake-case");
        assert_eq!(validator.to_kebab_case("CamelCase"), "camel-case");
        assert_eq!(validator.to_kebab_case("PascalCase"), "pascal-case");
    }
}
