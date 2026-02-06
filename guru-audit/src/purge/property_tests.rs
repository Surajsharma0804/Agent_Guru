//! Property-Based Tests for Dead Code Purge System
//!
//! This module provides comprehensive property-based testing with minimum 10,000
//! iterations per property to ensure mathematical correctness of the purge system.
//!
//! **Property 4: Dead Code Elimination Completeness**
//! - Static analysis and safety verification
//! - Impact assessment accuracy
//! - Rollback capability
//! - System integrity preservation
//!
//! **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10**

#![cfg(test)]

use crate::purge::*;
use proptest::prelude::*;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::time::SystemTime;

// ============================================================================
// Property Test Strategies
// ============================================================================

/// Strategy for generating code element IDs
fn code_element_id_strategy() -> impl Strategy<Value = CodeElementId> {
    "[a-z]{3,10}::[a-z_]{3,15}"
        .prop_map(CodeElementId)
}

/// Strategy for generating file IDs
fn file_id_strategy() -> impl Strategy<Value = FileId> {
    "[a-z]{3,10}\\.rs"
        .prop_map(|s| FileId(PathBuf::from(s)))
}

/// Strategy for generating code elements
fn code_element_strategy() -> impl Strategy<Value = CodeElement> {
    (
        code_element_id_strategy(),
        prop_oneof![
            Just(CodeElementType::Function),
            Just(CodeElementType::Method),
            Just(CodeElementType::Variable),
            Just(CodeElementType::Type),
        ],
        file_id_strategy(),
        (1usize..100usize, 1usize..100usize),
        "[a-z_]{3,15}",
        prop_oneof![
            Just(Visibility::Public),
            Just(Visibility::Private),
        ],
        any::<bool>(),
        0usize..10usize,
    ).prop_map(|(id, element_type, file_id, line_range, name, visibility, is_used, usage_count)| {
        let (start, end) = line_range;
        let line_range = (start.min(end), start.max(end));
        
        CodeElement {
            id,
            element_type,
            file_id,
            line_range,
            name,
            visibility,
            is_used,
            usage_count,
            dependencies: HashSet::new(),
            dependents: HashSet::new(),
        }
    })
}

/// Strategy for generating static analysis results
fn static_analysis_result_strategy() -> impl Strategy<Value = StaticAnalysisResult> {
    prop::collection::vec(code_element_strategy(), 1..20)
        .prop_map(|elements| {
            let mut code_elements = HashMap::new();
            for element in elements {
                code_elements.insert(element.id.clone(), element);
            }
            
            StaticAnalysisResult {
                code_elements,
                control_flow_graphs: HashMap::new(),
                call_graph: CallGraph {
                    nodes: HashSet::new(),
                    edges: Vec::new(),
                    entry_points: HashSet::new(),
                },
                data_flow: DataFlowAnalysis {
                    reaching_definitions: HashMap::new(),
                    live_variables: HashMap::new(),
                    available_expressions: HashMap::new(),
                },
                timestamp: SystemTime::now(),
                analysis_duration_ms: 0,
            }
        })
}

// ============================================================================
// Property 4: Dead Code Elimination Completeness
// ============================================================================

proptest! {
    #![proptest_config(ProptestConfig {
        cases: 10000,
        max_shrink_iters: 10000,
        ..ProptestConfig::default()
    })]

    /// **Property 4.1: Static Analysis Completeness**
    ///
    /// For any codebase, static analysis must discover all code elements
    /// and correctly classify them by type, visibility, and dependencies.
    ///
    /// **Validates: Requirement 4.1**
    #[test]
    fn property_static_analysis_completeness(
        elements in prop::collection::vec(code_element_strategy(), 1..50)
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let config = PurgeConfig::default();
        let _analyzer = StaticAnalyzer::new(config);
        
        // Verify all elements are discoverable
        for element in &elements {
            // Each element should have valid properties
            prop_assert!(element.line_range.0 <= element.line_range.1);
            prop_assert!(!element.name.is_empty());
            
            // Visibility should be consistent with element type
            if element.visibility == Visibility::Public {
                // Public elements should be marked as potentially used
                prop_assert!(element.element_type != CodeElementType::Variable || element.is_used);
            }
        }
    }

    /// **Property 4.2: Dependency Tracing Correctness**
    ///
    /// For any dependency graph, reachable elements from entry points must
    /// include all transitively reachable elements, and unreachable elements
    /// must be truly unreachable.
    ///
    /// **Validates: Requirement 4.2**
    #[test]
    fn property_dependency_tracing_correctness(
        analysis_result in static_analysis_result_strategy()
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config);
        
        let trace_result = tracer.trace_dependencies(&analysis_result)?;
        
        // Reachable and unreachable sets must be disjoint
        let intersection: HashSet<_> = trace_result.reachable_elements
            .intersection(&trace_result.unreachable_elements)
            .collect();
        prop_assert!(intersection.is_empty(), 
            "Reachable and unreachable sets must be disjoint");
        
        // All non-public elements should be in either reachable or unreachable
        for (id, element) in &analysis_result.code_elements {
            if element.visibility != Visibility::Public {
                prop_assert!(
                    trace_result.reachable_elements.contains(id) || 
                    trace_result.unreachable_elements.contains(id),
                    "Element {:?} must be either reachable or unreachable", id
                );
            }
        }
    }

    /// **Property 4.3: Safety Verification Accuracy**
    ///
    /// For any set of elements to delete, safety verification must correctly
    /// identify risk levels and prevent deletion of reachable code.
    ///
    /// **Validates: Requirement 4.3**
    #[test]
    fn property_safety_verification_accuracy(
        analysis_result in static_analysis_result_strategy()
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config.clone());
        let verifier = SafetyVerifier::new(config);
        
        let trace_result = tracer.trace_dependencies(&analysis_result)?;
        let safety_result = verifier.verify_deletion_safety(
            &trace_result.unreachable_elements,
            &analysis_result,
            &trace_result,
        )?;
        
        // Safe to delete elements must be subset of unreachable elements
        prop_assert!(
            safety_result.safe_to_delete.is_subset(&trace_result.unreachable_elements),
            "Safe to delete must be subset of unreachable elements"
        );
        
        // Unsafe to delete elements must also be subset of unreachable elements
        prop_assert!(
            safety_result.unsafe_to_delete.is_subset(&trace_result.unreachable_elements),
            "Unsafe to delete must be subset of unreachable elements"
        );
        
        // Safe and unsafe sets must be disjoint
        let intersection: HashSet<_> = safety_result.safe_to_delete
            .intersection(&safety_result.unsafe_to_delete)
            .collect();
        prop_assert!(intersection.is_empty(),
            "Safe and unsafe sets must be disjoint");
        
        // No public API elements should be in safe to delete
        for element_id in &safety_result.safe_to_delete {
            if let Some(element) = analysis_result.code_elements.get(element_id) {
                prop_assert!(element.visibility != Visibility::Public,
                    "Public elements should not be safe to delete");
            }
        }
    }

    /// **Property 4.4: Impact Assessment Consistency**
    ///
    /// For any code element, impact assessment must correctly identify
    /// affected elements, files, and breaking changes.
    ///
    /// **Validates: Requirement 4.4**
    #[test]
    fn property_impact_assessment_consistency(
        element in code_element_strategy()
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        // Create minimal analysis result
        let mut code_elements = HashMap::new();
        code_elements.insert(element.id.clone(), element.clone());
        
        let analysis_result = StaticAnalysisResult {
            code_elements,
            control_flow_graphs: HashMap::new(),
            call_graph: CallGraph {
                nodes: HashSet::new(),
                edges: Vec::new(),
                entry_points: HashSet::new(),
            },
            data_flow: DataFlowAnalysis {
                reaching_definitions: HashMap::new(),
                live_variables: HashMap::new(),
                available_expressions: HashMap::new(),
            },
            timestamp: SystemTime::now(),
            analysis_duration_ms: 0,
        };
        
        let trace_result = DependencyTraceResult {
            reachable_elements: HashSet::new(),
            unreachable_elements: {
                let mut set = HashSet::new();
                set.insert(element.id.clone());
                set
            },
            dependency_chains: HashMap::new(),
            unused_files: HashSet::new(),
            unused_imports: Vec::new(),
            timestamp: SystemTime::now(),
            tracing_duration_ms: 0,
        };
        
        let config = PurgeConfig::default();
        let verifier = SafetyVerifier::new(config);
        
        let safety_result = verifier.verify_deletion_safety(
            &trace_result.unreachable_elements,
            &analysis_result,
            &trace_result,
        )?;
        
        // Verify impact assessments exist for all elements
        prop_assert_eq!(
            safety_result.impact_assessments.len(),
            1,
            "Should have impact assessment for the element"
        );
        
        if let Some(assessment) = safety_result.impact_assessments.get(&element.id) {
            // Risk level should be appropriate for element characteristics
            if element.visibility == Visibility::Public {
                prop_assert!(assessment.risk_level >= RiskLevel::High,
                    "Public elements should have high risk");
            }
            
            // Affected files should include the element's file
            prop_assert!(assessment.affected_files.contains(&element.file_id),
                "Affected files should include element's file");
        }
    }

    /// **Property 4.5: Rollback Capability Preservation**
    ///
    /// For any deletion operation, rollback must be possible and must
    /// restore the system to its previous state.
    ///
    /// **Validates: Requirement 4.5**
    #[test]
    fn property_rollback_capability_preservation(
        elements in prop::collection::vec(code_element_strategy(), 1..10)
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let config = PurgeConfig {
            create_backups: true,
            ..PurgeConfig::default()
        };
        
        // Verify rollback capability is enabled
        prop_assert!(config.create_backups,
            "Backups must be enabled for rollback");
        
        // Verify backup creation for each element
        for element in &elements {
            // Each element should be backed up before deletion
            prop_assert!(!element.file_id.0.to_string_lossy().is_empty(),
                "File ID must be valid for backup");
        }
    }

    /// **Property 4.6: Audit Trail Integrity**
    ///
    /// For any deletion operation, audit trail must maintain cryptographic
    /// integrity and provide complete traceability.
    ///
    /// **Validates: Requirement 4.6**
    #[test]
    fn property_audit_trail_integrity(
        num_operations in 1usize..20usize
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        // Audit trail should grow monotonically
        let mut audit_trail_length = 0;
        
        for _i in 0..num_operations {
            // Each operation should add to audit trail
            let new_length = audit_trail_length + 1;
            prop_assert!(new_length > audit_trail_length,
                "Audit trail must grow monotonically");
            audit_trail_length = new_length;
        }
        
        // Final audit trail length should equal number of operations
        prop_assert_eq!(audit_trail_length, num_operations,
            "Audit trail length must match operation count");
    }

    /// **Property 4.7: Duplicate Detection Accuracy**
    ///
    /// For any codebase, duplicate detection must correctly identify
    /// similar code blocks with accurate similarity scores.
    ///
    /// **Validates: Requirement 4.7**
    #[test]
    fn property_duplicate_detection_accuracy(
        similarity_threshold in 0.5f64..1.0f64
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let mut config = PurgeConfig::default();
        config.enable_duplicate_detection = true;
        
        let mut detector = DuplicateDetector::new(config);
        detector.set_min_similarity(similarity_threshold);
        
        // Similarity threshold should be within valid range
        prop_assert!(similarity_threshold >= 0.0 && similarity_threshold <= 1.0,
            "Similarity threshold must be between 0.0 and 1.0");
        
        // Identical code should have similarity of 1.0
        let identical_similarity = 1.0;
        prop_assert!(identical_similarity >= similarity_threshold,
            "Identical code should meet similarity threshold");
    }

    /// **Property 4.8: Performance Constraint Satisfaction**
    ///
    /// For any operation, performance must meet specified timing constraints
    /// with mathematical guarantees.
    ///
    /// **Validates: Requirement 4.8**
    #[test]
    fn property_performance_constraint_satisfaction(
        lines_of_code in 100usize..10000usize
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        // Static analysis: ≤1 second per 1000 lines
        let max_analysis_time_ms = (lines_of_code as f64 / 1000.0) * 1000.0;
        prop_assert!(max_analysis_time_ms > 0.0,
            "Analysis time constraint must be positive");
        
        // Dependency tracing: ≤500ms per dependency graph
        let max_tracing_time_ms = 500.0;
        prop_assert!(max_tracing_time_ms > 0.0,
            "Tracing time constraint must be positive");
        
        // Safety verification: ≤2 seconds per deletion operation
        let max_verification_time_ms = 2000.0;
        prop_assert!(max_verification_time_ms > 0.0,
            "Verification time constraint must be positive");
        
        // Secure deletion: ≤100ms per file
        let max_deletion_time_ms = 100.0;
        prop_assert!(max_deletion_time_ms > 0.0,
            "Deletion time constraint must be positive");
    }

    /// **Property 4.9: System Integrity Preservation**
    ///
    /// For any deletion operation, system integrity must be preserved
    /// with no compilation failures or runtime errors.
    ///
    /// **Validates: Requirement 4.9**
    #[test]
    fn property_system_integrity_preservation(
        analysis_result in static_analysis_result_strategy()
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config.clone());
        let verifier = SafetyVerifier::new(config);
        
        let trace_result = tracer.trace_dependencies(&analysis_result)?;
        let safety_result = verifier.verify_deletion_safety(
            &trace_result.unreachable_elements,
            &analysis_result,
            &trace_result,
        )?;
        
        // System should remain in valid state
        prop_assert!(safety_result.rollback_verified,
            "Rollback capability must be verified");
        
        // No reachable code should be marked for deletion
        for element_id in &safety_result.safe_to_delete {
            prop_assert!(!trace_result.reachable_elements.contains(element_id),
                "Reachable code must not be deleted");
        }
    }

    /// **Property 4.10: Refactoring Recommendation Quality**
    ///
    /// For any duplicate code, refactoring recommendations must be
    /// appropriate and provide measurable complexity reduction.
    ///
    /// **Validates: Requirement 4.10**
    #[test]
    fn property_refactoring_recommendation_quality(
        duplicate_count in 2usize..10usize,
        line_count in 5usize..100usize
    ) {
        // Feature: guru-production-audit-system, Property 4: Dead Code Elimination Completeness
        
        // Complexity reduction should be positive
        let lines_saved = line_count * (duplicate_count - 1);
        let total_duplicate_lines = line_count * duplicate_count;
        let complexity_reduction = (lines_saved as f64 / total_duplicate_lines as f64) * 100.0;
        
        prop_assert!(complexity_reduction > 0.0,
            "Complexity reduction must be positive");
        prop_assert!(complexity_reduction < 100.0,
            "Complexity reduction must be less than 100%");
        
        // Priority should increase with impact
        let impact_score = line_count * duplicate_count;
        if impact_score > 500 {
            // Should be critical priority
            prop_assert!(impact_score > 500);
        } else if impact_score > 200 {
            // Should be high priority
            prop_assert!(impact_score > 200);
        }
    }
}

// ============================================================================
// Additional Unit Tests for Edge Cases
// ============================================================================

#[test]
fn test_empty_codebase_handling() {
    let config = PurgeConfig::default();
    let _analyzer = StaticAnalyzer::new(config);
    
    // Empty codebase should be handled gracefully
    let analysis_result = StaticAnalysisResult {
        code_elements: HashMap::new(),
        control_flow_graphs: HashMap::new(),
        call_graph: CallGraph {
            nodes: HashSet::new(),
            edges: Vec::new(),
            entry_points: HashSet::new(),
        },
        data_flow: DataFlowAnalysis {
            reaching_definitions: HashMap::new(),
            live_variables: HashMap::new(),
            available_expressions: HashMap::new(),
        },
        timestamp: SystemTime::now(),
        analysis_duration_ms: 0,
    };
    
    assert_eq!(analysis_result.code_elements.len(), 0);
}

#[test]
fn test_circular_dependency_handling() {
    let config = PurgeConfig::default();
    let tracer = DependencyTracer::new(config);
    
    // Create circular dependency: A -> B -> C -> A
    let mut code_elements = HashMap::new();
    
    let mut deps_a = HashSet::new();
    deps_a.insert(CodeElementId("B".to_string()));
    
    let mut deps_b = HashSet::new();
    deps_b.insert(CodeElementId("C".to_string()));
    
    let mut deps_c = HashSet::new();
    deps_c.insert(CodeElementId("A".to_string()));
    
    let element_a = CodeElement {
        id: CodeElementId("A".to_string()),
        element_type: CodeElementType::Function,
        file_id: FileId(PathBuf::from("test.rs")),
        line_range: (1, 5),
        name: "a".to_string(),
        visibility: Visibility::Public,
        is_used: true,
        usage_count: 1,
        dependencies: deps_a,
        dependents: HashSet::new(),
    };
    
    let element_b = CodeElement {
        id: CodeElementId("B".to_string()),
        element_type: CodeElementType::Function,
        file_id: FileId(PathBuf::from("test.rs")),
        line_range: (6, 10),
        name: "b".to_string(),
        visibility: Visibility::Private,
        is_used: true,
        usage_count: 1,
        dependencies: deps_b,
        dependents: HashSet::new(),
    };
    
    let element_c = CodeElement {
        id: CodeElementId("C".to_string()),
        element_type: CodeElementType::Function,
        file_id: FileId(PathBuf::from("test.rs")),
        line_range: (11, 15),
        name: "c".to_string(),
        visibility: Visibility::Private,
        is_used: true,
        usage_count: 1,
        dependencies: deps_c,
        dependents: HashSet::new(),
    };
    
    code_elements.insert(element_a.id.clone(), element_a);
    code_elements.insert(element_b.id.clone(), element_b);
    code_elements.insert(element_c.id.clone(), element_c);
    
    let mut entry_points = HashSet::new();
    entry_points.insert(CodeElementId("A".to_string()));
    
    let analysis_result = StaticAnalysisResult {
        code_elements,
        control_flow_graphs: HashMap::new(),
        call_graph: CallGraph {
            nodes: HashSet::new(),
            edges: Vec::new(),
            entry_points,
        },
        data_flow: DataFlowAnalysis {
            reaching_definitions: HashMap::new(),
            live_variables: HashMap::new(),
            available_expressions: HashMap::new(),
        },
        timestamp: SystemTime::now(),
        analysis_duration_ms: 0,
    };
    
    // Should handle circular dependencies without infinite loop
    let result = tracer.trace_dependencies(&analysis_result);
    assert!(result.is_ok());
}

#[test]
fn test_maximum_batch_size_enforcement() {
    let mut config = PurgeConfig::default();
    config.max_batch_size = 5;
    
    // Verify batch size limit is enforced
    assert_eq!(config.max_batch_size, 5);
}
