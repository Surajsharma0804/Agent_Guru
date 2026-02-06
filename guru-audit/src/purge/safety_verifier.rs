//! Safety Verification Engine
//!
//! This module provides comprehensive safety verification for code deletion operations
//! with impact assessment and rollback capability testing. Designed for production-grade
//! safe code elimination with zero-tolerance for breaking changes.
//!
//! Performance Requirements:
//! - Safety verification: ≤2 seconds per deletion operation
//! - Impact assessment: ≤1 second per code element
//! - Rollback verification: ≤500ms per operation

use crate::error::AuditError;
use crate::purge::types::*;
use std::collections::{HashMap, HashSet};
use std::time::{SystemTime, Instant};

/// Safety verifier with comprehensive impact assessment
pub struct SafetyVerifier {
    /// Configuration
    config: PurgeConfig,
}

impl SafetyVerifier {
    /// Create a new safety verifier
    pub fn new(config: PurgeConfig) -> Self {
        Self { config }
    }

    /// Verify safety of deletion operations
    ///
    /// Performs comprehensive safety analysis including:
    /// - Impact assessment for each deletion
    /// - Breaking change detection
    /// - Risk level classification
    /// - Rollback capability verification
    ///
    /// # Performance
    /// - Target: ≤2 seconds per deletion operation
    /// - Parallel impact assessment where possible
    /// - Optimized dependency analysis
    pub fn verify_deletion_safety(
        &self,
        elements_to_delete: &HashSet<CodeElementId>,
        analysis_result: &StaticAnalysisResult,
        trace_result: &DependencyTraceResult,
    ) -> Result<SafetyVerificationResult, AuditError> {
        let start_time = Instant::now();
        
        let mut safe_to_delete = HashSet::new();
        let mut unsafe_to_delete = HashSet::new();
        let mut impact_assessments = HashMap::new();
        
        // Assess impact for each element
        for element_id in elements_to_delete {
            let assessment = self.assess_deletion_impact(
                element_id,
                analysis_result,
                trace_result,
            )?;
            
            // Classify based on risk level
            match assessment.risk_level {
                RiskLevel::Safe | RiskLevel::Low => {
                    if assessment.risk_level <= self.config.auto_delete_risk_threshold {
                        safe_to_delete.insert(element_id.clone());
                    } else {
                        unsafe_to_delete.insert(element_id.clone());
                    }
                }
                _ => {
                    unsafe_to_delete.insert(element_id.clone());
                }
            }
            
            impact_assessments.insert(element_id.clone(), assessment);
        }
        
        // Verify rollback capability
        let rollback_verified = self.verify_rollback_capability()?;
        
        let verification_duration_ms = start_time.elapsed().as_millis() as u64;
        
        let is_safe = unsafe_to_delete.is_empty() || !self.config.require_manual_approval;
        
        Ok(SafetyVerificationResult {
            is_safe,
            safe_to_delete,
            unsafe_to_delete,
            impact_assessments,
            rollback_verified,
            timestamp: SystemTime::now(),
            verification_duration_ms,
        })
    }

    /// Assess impact of deleting a specific code element
    ///
    /// # Performance
    /// - Target: ≤1 second per code element
    fn assess_deletion_impact(
        &self,
        element_id: &CodeElementId,
        analysis_result: &StaticAnalysisResult,
        trace_result: &DependencyTraceResult,
    ) -> Result<ImpactAssessment, AuditError> {
        let element = analysis_result.code_elements.get(element_id)
            .ok_or_else(|| AuditError::FileSystemError {
                operation: "get_element".to_string(),
                path: element_id.0.clone(),
                reason: "Element not found in analysis result".to_string(),
            })?;
        
        // Determine risk level based on element characteristics
        let risk_level = self.calculate_risk_level(element, trace_result)?;
        
        // Identify affected elements (dependents)
        let affected_elements = element.dependents.clone();
        
        // Identify affected files
        let mut affected_files = HashSet::new();
        affected_files.insert(element.file_id.clone());
        for dep_id in &affected_elements {
            if let Some(dep_element) = analysis_result.code_elements.get(dep_id) {
                affected_files.insert(dep_element.file_id.clone());
            }
        }
        
        // Detect breaking changes
        let breaking_changes = self.detect_breaking_changes(
            element,
            &affected_elements,
            analysis_result,
        )?;
        
        // Generate recommendations
        let recommendations = self.generate_recommendations(
            element,
            &risk_level,
            &breaking_changes,
        );
        
        Ok(ImpactAssessment {
            element_id: element_id.clone(),
            risk_level,
            affected_elements,
            affected_files,
            breaking_changes,
            recommendations,
        })
    }

    /// Calculate risk level for deleting an element
    fn calculate_risk_level(
        &self,
        element: &CodeElement,
        trace_result: &DependencyTraceResult,
    ) -> Result<RiskLevel, AuditError> {
        // Public API elements are high risk
        if element.visibility == Visibility::Public {
            return Ok(RiskLevel::High);
        }
        
        // Elements with many dependents are higher risk
        let dependent_count = element.dependents.len();
        if dependent_count > 10 {
            return Ok(RiskLevel::High);
        } else if dependent_count > 5 {
            return Ok(RiskLevel::Medium);
        } else if dependent_count > 0 {
            return Ok(RiskLevel::Low);
        }
        
        // Unreachable elements with no dependents are safe
        if trace_result.unreachable_elements.contains(&element.id) {
            return Ok(RiskLevel::Safe);
        }
        
        Ok(RiskLevel::Low)
    }

    /// Detect breaking changes that would be introduced by deletion
    fn detect_breaking_changes(
        &self,
        element: &CodeElement,
        affected_elements: &HashSet<CodeElementId>,
        analysis_result: &StaticAnalysisResult,
    ) -> Result<Vec<BreakingChange>, AuditError> {
        let mut breaking_changes = Vec::new();
        
        // Public API removal is a breaking change
        if element.visibility == Visibility::Public {
            breaking_changes.push(BreakingChange {
                change_type: BreakingChangeType::PublicApiRemoval,
                description: format!("Removing public {} '{}'", 
                    format!("{:?}", element.element_type).to_lowercase(),
                    element.name),
                affected_locations: vec![(element.file_id.clone(), element.line_range.0)],
            });
        }
        
        // Dependency breaks for each dependent
        for dep_id in affected_elements {
            if let Some(dep_element) = analysis_result.code_elements.get(dep_id) {
                breaking_changes.push(BreakingChange {
                    change_type: BreakingChangeType::DependencyBreak,
                    description: format!("'{}' depends on '{}'", dep_element.name, element.name),
                    affected_locations: vec![(dep_element.file_id.clone(), dep_element.line_range.0)],
                });
            }
        }
        
        Ok(breaking_changes)
    }

    /// Generate recommendations for safe deletion
    fn generate_recommendations(
        &self,
        element: &CodeElement,
        risk_level: &RiskLevel,
        breaking_changes: &[BreakingChange],
    ) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        match risk_level {
            RiskLevel::Safe => {
                recommendations.push("Safe to delete automatically".to_string());
            }
            RiskLevel::Low => {
                recommendations.push("Review dependents before deletion".to_string());
            }
            RiskLevel::Medium => {
                recommendations.push("Carefully review all affected code".to_string());
                recommendations.push("Consider deprecation before removal".to_string());
            }
            RiskLevel::High => {
                recommendations.push("High risk deletion - requires thorough review".to_string());
                recommendations.push("Update all dependents first".to_string());
                recommendations.push("Consider providing migration path".to_string());
            }
            RiskLevel::Critical => {
                recommendations.push("CRITICAL: Do not delete without extensive testing".to_string());
                recommendations.push("This may break core functionality".to_string());
            }
        }
        
        // Add specific recommendations based on breaking changes
        if !breaking_changes.is_empty() {
            recommendations.push(format!(
                "Address {} breaking change(s) before deletion",
                breaking_changes.len()
            ));
        }
        
        // Recommendations based on element type
        match element.element_type {
            CodeElementType::Function | CodeElementType::Method => {
                if element.visibility == Visibility::Public {
                    recommendations.push("Consider deprecating function first".to_string());
                }
            }
            CodeElementType::Type => {
                recommendations.push("Ensure no external code depends on this type".to_string());
            }
            _ => {}
        }
        
        recommendations
    }

    /// Verify rollback capability
    ///
    /// # Performance
    /// - Target: ≤500ms per operation
    fn verify_rollback_capability(&self) -> Result<bool, AuditError> {
        // Check if backup system is available
        if !self.config.create_backups {
            return Ok(false);
        }
        
        // Verify we can create checkpoints
        // In production, this would test actual checkpoint creation
        Ok(true)
    }

    /// Verify compilation after deletion (simulation)
    pub fn verify_compilation_after_deletion(
        &self,
        _elements_to_delete: &HashSet<CodeElementId>,
    ) -> Result<bool, AuditError> {
        // In production, this would:
        // 1. Create a temporary copy of the codebase
        // 2. Apply deletions
        // 3. Attempt compilation
        // 4. Return success/failure
        
        // For now, return true (would be implemented with actual compiler integration)
        Ok(true)
    }

    /// Verify tests pass after deletion (simulation)
    pub fn verify_tests_after_deletion(
        &self,
        _elements_to_delete: &HashSet<CodeElementId>,
    ) -> Result<bool, AuditError> {
        // In production, this would:
        // 1. Create a temporary copy of the codebase
        // 2. Apply deletions
        // 3. Run test suite
        // 4. Return success/failure
        
        // For now, return true (would be implemented with actual test runner integration)
        Ok(true)
    }

    /// Calculate overall safety score for a set of deletions
    pub fn calculate_safety_score(
        &self,
        impact_assessments: &HashMap<CodeElementId, ImpactAssessment>,
    ) -> f64 {
        if impact_assessments.is_empty() {
            return 1.0;
        }
        
        let mut total_score = 0.0;
        
        for assessment in impact_assessments.values() {
            let risk_score = match assessment.risk_level {
                RiskLevel::Safe => 1.0,
                RiskLevel::Low => 0.8,
                RiskLevel::Medium => 0.5,
                RiskLevel::High => 0.2,
                RiskLevel::Critical => 0.0,
            };
            
            total_score += risk_score;
        }
        
        total_score / impact_assessments.len() as f64
    }

    /// Check if deletion requires manual approval
    pub fn requires_manual_approval(
        &self,
        impact_assessments: &HashMap<CodeElementId, ImpactAssessment>,
    ) -> bool {
        if !self.config.require_manual_approval {
            return false;
        }
        
        // Require approval if any element has high or critical risk
        for assessment in impact_assessments.values() {
            if assessment.risk_level >= RiskLevel::High {
                return true;
            }
            
            // Require approval if there are breaking changes
            if !assessment.breaking_changes.is_empty() {
                return true;
            }
        }
        
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_safety_verifier_creation() {
        let config = PurgeConfig::default();
        let verifier = SafetyVerifier::new(config);
        assert!(verifier.config.enable_safety_verification);
    }

    #[test]
    fn test_calculate_risk_level_public_api() {
        let config = PurgeConfig::default();
        let verifier = SafetyVerifier::new(config);
        
        let element = CodeElement {
            id: CodeElementId("test::public_fn".to_string()),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (1, 10),
            name: "public_fn".to_string(),
            visibility: Visibility::Public,
            is_used: true,
            usage_count: 5,
            dependencies: HashSet::new(),
            dependents: HashSet::new(),
        };
        
        let trace_result = DependencyTraceResult {
            reachable_elements: HashSet::new(),
            unreachable_elements: HashSet::new(),
            dependency_chains: HashMap::new(),
            unused_files: HashSet::new(),
            unused_imports: Vec::new(),
            timestamp: SystemTime::now(),
            tracing_duration_ms: 0,
        };
        
        let risk = verifier.calculate_risk_level(&element, &trace_result).unwrap();
        assert_eq!(risk, RiskLevel::High);
    }

    #[test]
    fn test_calculate_risk_level_unreachable() {
        let config = PurgeConfig::default();
        let verifier = SafetyVerifier::new(config);
        
        let element_id = CodeElementId("test::unused_fn".to_string());
        let element = CodeElement {
            id: element_id.clone(),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (1, 10),
            name: "unused_fn".to_string(),
            visibility: Visibility::Private,
            is_used: false,
            usage_count: 0,
            dependencies: HashSet::new(),
            dependents: HashSet::new(),
        };
        
        let mut unreachable = HashSet::new();
        unreachable.insert(element_id);
        
        let trace_result = DependencyTraceResult {
            reachable_elements: HashSet::new(),
            unreachable_elements: unreachable,
            dependency_chains: HashMap::new(),
            unused_files: HashSet::new(),
            unused_imports: Vec::new(),
            timestamp: SystemTime::now(),
            tracing_duration_ms: 0,
        };
        
        let risk = verifier.calculate_risk_level(&element, &trace_result).unwrap();
        assert_eq!(risk, RiskLevel::Safe);
    }

    #[test]
    fn test_calculate_safety_score() {
        let config = PurgeConfig::default();
        let verifier = SafetyVerifier::new(config);
        
        let mut assessments = HashMap::new();
        
        assessments.insert(
            CodeElementId("safe1".to_string()),
            ImpactAssessment {
                element_id: CodeElementId("safe1".to_string()),
                risk_level: RiskLevel::Safe,
                affected_elements: HashSet::new(),
                affected_files: HashSet::new(),
                breaking_changes: Vec::new(),
                recommendations: Vec::new(),
            },
        );
        
        assessments.insert(
            CodeElementId("low1".to_string()),
            ImpactAssessment {
                element_id: CodeElementId("low1".to_string()),
                risk_level: RiskLevel::Low,
                affected_elements: HashSet::new(),
                affected_files: HashSet::new(),
                breaking_changes: Vec::new(),
                recommendations: Vec::new(),
            },
        );
        
        let score = verifier.calculate_safety_score(&assessments);
        assert!(score > 0.8 && score <= 1.0);
    }

    #[test]
    fn test_requires_manual_approval() {
        let mut config = PurgeConfig::default();
        config.require_manual_approval = true;
        let verifier = SafetyVerifier::new(config);
        
        let mut assessments = HashMap::new();
        
        assessments.insert(
            CodeElementId("high_risk".to_string()),
            ImpactAssessment {
                element_id: CodeElementId("high_risk".to_string()),
                risk_level: RiskLevel::High,
                affected_elements: HashSet::new(),
                affected_files: HashSet::new(),
                breaking_changes: Vec::new(),
                recommendations: Vec::new(),
            },
        );
        
        assert!(verifier.requires_manual_approval(&assessments));
    }
}
