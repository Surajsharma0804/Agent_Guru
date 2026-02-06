//! Comprehensive Dependency Tracer
//!
//! This module provides comprehensive dependency analysis with usage tracking
//! and reachability computation. Designed for production-grade dead code detection
//! with mathematical correctness guarantees.
//!
//! Performance Requirements:
//! - Dependency tracing: ≤500ms per dependency graph
//! - Reachability computation: ≤200ms per code element
//! - Usage analysis: ≤100ms per element

use crate::error::AuditError;
use crate::purge::types::*;
use std::collections::{HashMap, HashSet, VecDeque};
use std::time::{SystemTime, Instant};

/// Dependency tracer with comprehensive usage analysis
pub struct DependencyTracer {
    /// Configuration
    #[allow(dead_code)]
    config: PurgeConfig,
}

impl DependencyTracer {
    /// Create a new dependency tracer
    pub fn new(config: PurgeConfig) -> Self {
        Self { config }
    }

    /// Trace dependencies from entry points to identify reachable code
    ///
    /// Performs comprehensive dependency analysis including:
    /// - Reachability analysis from entry points
    /// - Transitive dependency computation
    /// - Unused code identification
    /// - Unused import detection
    ///
    /// # Performance
    /// - Target: ≤500ms per dependency graph
    /// - Optimized graph traversal algorithms
    /// - Parallel analysis where possible
    pub fn trace_dependencies(
        &self,
        analysis_result: &StaticAnalysisResult,
    ) -> Result<DependencyTraceResult, AuditError> {
        let start_time = Instant::now();
        
        // Start from entry points in call graph
        let entry_points = &analysis_result.call_graph.entry_points;
        
        // Perform reachability analysis
        let reachable_elements = self.compute_reachable_elements(
            entry_points,
            &analysis_result.code_elements,
            &analysis_result.call_graph,
        )?;
        
        // Identify unreachable elements (dead code)
        let unreachable_elements = self.identify_unreachable_elements(
            &analysis_result.code_elements,
            &reachable_elements,
        );
        
        // Compute dependency chains for debugging
        let dependency_chains = self.compute_dependency_chains(
            &analysis_result.code_elements,
            &reachable_elements,
        )?;
        
        // Identify unused files
        let unused_files = self.identify_unused_files(
            &analysis_result.code_elements,
            &unreachable_elements,
        );
        
        // Identify unused imports
        let unused_imports = self.identify_unused_imports(
            &analysis_result.code_elements,
            &reachable_elements,
        )?;
        
        let tracing_duration_ms = start_time.elapsed().as_millis() as u64;
        
        Ok(DependencyTraceResult {
            reachable_elements,
            unreachable_elements,
            dependency_chains,
            unused_files,
            unused_imports,
            timestamp: SystemTime::now(),
            tracing_duration_ms,
        })
    }

    /// Compute reachable code elements from entry points
    ///
    /// Uses breadth-first search to traverse the call graph and dependency graph
    /// to identify all code elements reachable from entry points.
    fn compute_reachable_elements(
        &self,
        entry_points: &HashSet<CodeElementId>,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        call_graph: &CallGraph,
    ) -> Result<HashSet<CodeElementId>, AuditError> {
        let mut reachable = HashSet::new();
        let mut worklist = VecDeque::new();
        
        // Initialize with entry points
        for entry_point in entry_points {
            reachable.insert(entry_point.clone());
            worklist.push_back(entry_point.clone());
        }
        
        // BFS traversal of call graph
        while let Some(current_id) = worklist.pop_front() {
            // Find all functions called by current function
            for edge in &call_graph.edges {
                if edge.caller == current_id && !reachable.contains(&edge.callee) {
                    reachable.insert(edge.callee.clone());
                    worklist.push_back(edge.callee.clone());
                }
            }
            
            // Also follow dependency edges
            if let Some(element) = code_elements.get(&current_id) {
                for dep_id in &element.dependencies {
                    if !reachable.contains(dep_id) {
                        reachable.insert(dep_id.clone());
                        worklist.push_back(dep_id.clone());
                    }
                }
            }
        }
        
        // Mark all public API elements as reachable (they might be used externally)
        for (id, element) in code_elements {
            if element.visibility == Visibility::Public && !reachable.contains(id) {
                reachable.insert(id.clone());
            }
        }
        
        Ok(reachable)
    }

    /// Identify unreachable code elements (dead code)
    fn identify_unreachable_elements(
        &self,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        reachable_elements: &HashSet<CodeElementId>,
    ) -> HashSet<CodeElementId> {
        let mut unreachable = HashSet::new();
        
        for (id, element) in code_elements {
            // Skip public elements (might be used externally)
            if element.visibility == Visibility::Public {
                continue;
            }
            
            if !reachable_elements.contains(id) {
                unreachable.insert(id.clone());
            }
        }
        
        unreachable
    }

    /// Compute dependency chains for each reachable element
    ///
    /// Provides debugging information showing how each element is reached
    /// from entry points.
    fn compute_dependency_chains(
        &self,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        reachable_elements: &HashSet<CodeElementId>,
    ) -> Result<HashMap<CodeElementId, Vec<Vec<CodeElementId>>>, AuditError> {
        let mut chains = HashMap::new();
        
        // For each reachable element, compute paths from entry points
        for element_id in reachable_elements {
            let paths = self.find_paths_to_element(element_id, code_elements)?;
            chains.insert(element_id.clone(), paths);
        }
        
        Ok(chains)
    }

    /// Find all paths from entry points to a specific element
    fn find_paths_to_element(
        &self,
        target_id: &CodeElementId,
        code_elements: &HashMap<CodeElementId, CodeElement>,
    ) -> Result<Vec<Vec<CodeElementId>>, AuditError> {
        let mut paths = Vec::new();
        let mut current_path = Vec::new();
        let mut visited = HashSet::new();
        
        // DFS to find all paths
        self.dfs_find_paths(
            target_id,
            code_elements,
            &mut current_path,
            &mut visited,
            &mut paths,
        );
        
        Ok(paths)
    }

    /// Depth-first search to find paths
    fn dfs_find_paths(
        &self,
        target_id: &CodeElementId,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        current_path: &mut Vec<CodeElementId>,
        visited: &mut HashSet<CodeElementId>,
        paths: &mut Vec<Vec<CodeElementId>>,
    ) {
        // Limit path length to prevent infinite loops
        if current_path.len() > 100 {
            return;
        }
        
        if let Some(element) = code_elements.get(target_id) {
            current_path.push(target_id.clone());
            visited.insert(target_id.clone());
            
            // If this is an entry point, we found a complete path
            if element.visibility == Visibility::Public || element.name == "main" {
                paths.push(current_path.clone());
            } else {
                // Continue searching through dependents
                for dependent_id in &element.dependents {
                    if !visited.contains(dependent_id) {
                        self.dfs_find_paths(
                            dependent_id,
                            code_elements,
                            current_path,
                            visited,
                            paths,
                        );
                    }
                }
            }
            
            current_path.pop();
            visited.remove(target_id);
        }
    }

    /// Identify files that contain only unreachable code
    fn identify_unused_files(
        &self,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        unreachable_elements: &HashSet<CodeElementId>,
    ) -> HashSet<FileId> {
        let mut file_element_counts: HashMap<FileId, (usize, usize)> = HashMap::new();
        
        // Count total and unreachable elements per file
        for (id, element) in code_elements {
            let entry = file_element_counts.entry(element.file_id.clone()).or_insert((0, 0));
            entry.0 += 1; // Total elements
            
            if unreachable_elements.contains(id) {
                entry.1 += 1; // Unreachable elements
            }
        }
        
        // Files where all elements are unreachable
        let mut unused_files = HashSet::new();
        for (file_id, (total, unreachable)) in file_element_counts {
            if total > 0 && total == unreachable {
                unused_files.insert(file_id);
            }
        }
        
        unused_files
    }

    /// Identify unused import statements
    fn identify_unused_imports(
        &self,
        code_elements: &HashMap<CodeElementId, CodeElement>,
        reachable_elements: &HashSet<CodeElementId>,
    ) -> Result<Vec<UnusedImport>, AuditError> {
        let mut unused_imports = Vec::new();
        
        // Find all import elements
        for (_id, element) in code_elements {
            if element.element_type == CodeElementType::Import {
                // Check if import is used by any reachable code
                let is_used = element.dependents.iter().any(|dep_id| reachable_elements.contains(dep_id));
                
                if !is_used {
                    unused_imports.push(UnusedImport {
                        file_id: element.file_id.clone(),
                        line_number: element.line_range.0,
                        import_statement: element.name.clone(),
                    });
                }
            }
        }
        
        Ok(unused_imports)
    }

    /// Compute transitive closure of dependencies
    pub fn compute_transitive_dependencies(
        &self,
        element_id: &CodeElementId,
        code_elements: &HashMap<CodeElementId, CodeElement>,
    ) -> HashSet<CodeElementId> {
        let mut transitive_deps = HashSet::new();
        let mut worklist = VecDeque::new();
        
        worklist.push_back(element_id.clone());
        
        while let Some(current_id) = worklist.pop_front() {
            if let Some(element) = code_elements.get(&current_id) {
                for dep_id in &element.dependencies {
                    if !transitive_deps.contains(dep_id) {
                        transitive_deps.insert(dep_id.clone());
                        worklist.push_back(dep_id.clone());
                    }
                }
            }
        }
        
        transitive_deps
    }

    /// Compute reverse dependencies (dependents)
    pub fn compute_reverse_dependencies(
        &self,
        element_id: &CodeElementId,
        code_elements: &HashMap<CodeElementId, CodeElement>,
    ) -> HashSet<CodeElementId> {
        let mut reverse_deps = HashSet::new();
        
        for (_id, element) in code_elements {
            if element.dependencies.contains(element_id) {
                reverse_deps.insert(element.id.clone());
            }
        }
        
        reverse_deps
    }

    /// Check if element is transitively reachable from entry points
    pub fn is_reachable_from_entry_points(
        &self,
        element_id: &CodeElementId,
        entry_points: &HashSet<CodeElementId>,
        code_elements: &HashMap<CodeElementId, CodeElement>,
    ) -> bool {
        let mut visited = HashSet::new();
        let mut worklist = VecDeque::new();
        
        // Start from entry points
        for entry_point in entry_points {
            worklist.push_back(entry_point.clone());
            visited.insert(entry_point.clone());
        }
        
        // BFS to check reachability
        while let Some(current_id) = worklist.pop_front() {
            if &current_id == element_id {
                return true;
            }
            
            if let Some(element) = code_elements.get(&current_id) {
                for dep_id in &element.dependencies {
                    if !visited.contains(dep_id) {
                        visited.insert(dep_id.clone());
                        worklist.push_back(dep_id.clone());
                    }
                }
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
    fn test_dependency_tracer_creation() {
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config);
        assert!(tracer.config.enable_dependency_tracing);
    }

    #[test]
    fn test_identify_unreachable_elements() {
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config);
        
        let mut code_elements = HashMap::new();
        let reachable = HashSet::new();
        
        // Add a private unreachable element
        let element = CodeElement {
            id: CodeElementId("test::unused".to_string()),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (1, 10),
            name: "unused".to_string(),
            visibility: Visibility::Private,
            is_used: false,
            usage_count: 0,
            dependencies: HashSet::new(),
            dependents: HashSet::new(),
        };
        
        code_elements.insert(element.id.clone(), element);
        
        let unreachable = tracer.identify_unreachable_elements(&code_elements, &reachable);
        assert_eq!(unreachable.len(), 1);
    }

    #[test]
    fn test_compute_transitive_dependencies() {
        let config = PurgeConfig::default();
        let tracer = DependencyTracer::new(config);
        
        let mut code_elements = HashMap::new();
        
        // Create dependency chain: A -> B -> C
        let mut deps_b = HashSet::new();
        deps_b.insert(CodeElementId("C".to_string()));
        
        let mut deps_a = HashSet::new();
        deps_a.insert(CodeElementId("B".to_string()));
        
        let element_c = CodeElement {
            id: CodeElementId("C".to_string()),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (1, 5),
            name: "c".to_string(),
            visibility: Visibility::Private,
            is_used: false,
            usage_count: 0,
            dependencies: HashSet::new(),
            dependents: HashSet::new(),
        };
        
        let element_b = CodeElement {
            id: CodeElementId("B".to_string()),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (6, 10),
            name: "b".to_string(),
            visibility: Visibility::Private,
            is_used: false,
            usage_count: 0,
            dependencies: deps_b,
            dependents: HashSet::new(),
        };
        
        let element_a = CodeElement {
            id: CodeElementId("A".to_string()),
            element_type: CodeElementType::Function,
            file_id: FileId(PathBuf::from("test.rs")),
            line_range: (11, 15),
            name: "a".to_string(),
            visibility: Visibility::Private,
            is_used: false,
            usage_count: 0,
            dependencies: deps_a,
            dependents: HashSet::new(),
        };
        
        code_elements.insert(element_a.id.clone(), element_a);
        code_elements.insert(element_b.id.clone(), element_b);
        code_elements.insert(element_c.id.clone(), element_c);
        
        let transitive = tracer.compute_transitive_dependencies(
            &CodeElementId("A".to_string()),
            &code_elements,
        );
        
        assert!(transitive.contains(&CodeElementId("B".to_string())));
        assert!(transitive.contains(&CodeElementId("C".to_string())));
    }
}
