// Conflict Resolver for GURU Production Audit System
//
// This module provides naming conflict resolution with hierarchical naming conventions
// and disambiguation strategies.
//
// MAXIMUM ENGINEERING MANDATE:
// - Complete conflict detection and resolution
// - Hierarchical naming with semantic preservation
// - Production-grade implementation for millions of files over 20+ years

use crate::naming::types::*;
use anyhow::Result;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use tracing::{info, warn};

/// Conflict resolver with hierarchical naming support
pub struct ConflictResolver {
    /// Cache of existing file names for conflict detection
    existing_names: HashSet<String>,
    /// Conflict resolution strategies by priority
    resolution_strategies: Vec<ConflictResolutionStrategy>,
}

impl ConflictResolver {
    /// Create a new conflict resolver
    pub fn new() -> Self {
        Self {
            existing_names: HashSet::new(),
            resolution_strategies: vec![
                ConflictResolutionStrategy::UseHierarchicalNaming,
                ConflictResolutionStrategy::AddSuffix,
                ConflictResolutionStrategy::AddPrefix,
                ConflictResolutionStrategy::ManualIntervention,
            ],
        }
    }
    
    /// Initialize the resolver with existing file names from a directory
    pub fn initialize_from_directory(&mut self, directory: &Path) -> Result<()> {
        info!("Initializing conflict resolver from: {}", directory.display());
        
        self.existing_names.clear();
        
        if !directory.exists() {
            return Ok(());
        }
        
        for entry in std::fs::read_dir(directory)? {
            let entry = entry?;
            if entry.path().is_file() {
                if let Some(name) = entry.file_name().to_str() {
                    self.existing_names.insert(name.to_string());
                }
            }
        }
        
        info!("Loaded {} existing file names", self.existing_names.len());
        Ok(())
    }
    
    /// Check if a name conflicts with existing files
    pub fn has_conflict(&self, proposed_name: &str) -> bool {
        self.existing_names.contains(proposed_name)
    }
    
    /// Resolve a naming conflict
    pub fn resolve_conflict(
        &self,
        proposed_name: &str,
        file_path: &Path,
        semantic_context: Option<&str>,
    ) -> Result<String> {
        if !self.has_conflict(proposed_name) {
            return Ok(proposed_name.to_string());
        }
        
        info!("Resolving naming conflict for: {}", proposed_name);
        
        // Try each resolution strategy in order
        for strategy in &self.resolution_strategies {
            match strategy {
                ConflictResolutionStrategy::UseHierarchicalNaming => {
                    if let Some(resolved) = self.try_hierarchical_naming(
                        proposed_name,
                        file_path,
                        semantic_context,
                    ) {
                        if !self.has_conflict(&resolved) {
                            info!("Resolved using hierarchical naming: {}", resolved);
                            return Ok(resolved);
                        }
                    }
                }
                ConflictResolutionStrategy::AddSuffix => {
                    if let Some(resolved) = self.try_add_suffix(proposed_name) {
                        if !self.has_conflict(&resolved) {
                            info!("Resolved by adding suffix: {}", resolved);
                            return Ok(resolved);
                        }
                    }
                }
                ConflictResolutionStrategy::AddPrefix => {
                    if let Some(resolved) = self.try_add_prefix(proposed_name, file_path) {
                        if !self.has_conflict(&resolved) {
                            info!("Resolved by adding prefix: {}", resolved);
                            return Ok(resolved);
                        }
                    }
                }
                ConflictResolutionStrategy::ManualIntervention => {
                    warn!("Manual intervention required for: {}", proposed_name);
                    return Err(anyhow::anyhow!(
                        "Naming conflict requires manual intervention: {}",
                        proposed_name
                    ));
                }
            }
        }
        
        Err(anyhow::anyhow!(
            "Failed to resolve naming conflict for: {}",
            proposed_name
        ))
    }
    
    /// Try hierarchical naming based on directory structure
    fn try_hierarchical_naming(
        &self,
        proposed_name: &str,
        file_path: &Path,
        semantic_context: Option<&str>,
    ) -> Option<String> {
        // Get parent directory name
        let parent_name = file_path
            .parent()?
            .file_name()?
            .to_str()?;
        
        // Split name into stem and extension
        let (stem, ext) = self.split_name(proposed_name)?;
        
        // Try adding parent directory as prefix
        let hierarchical_name = format!("{}_{}{}", parent_name, stem, ext);
        
        if !self.has_conflict(&hierarchical_name) {
            return Some(hierarchical_name);
        }
        
        // Try adding semantic context if available
        if let Some(context) = semantic_context {
            let contextual_name = format!("{}_{}{}", context, stem, ext);
            if !self.has_conflict(&contextual_name) {
                return Some(contextual_name);
            }
        }
        
        None
    }
    
    /// Try adding a numeric suffix
    pub fn try_add_suffix(&self, proposed_name: &str) -> Option<String> {
        let (stem, ext) = self.split_name(proposed_name)?;
        
        // Try suffixes from 1 to 99
        for i in 1..100 {
            let suffixed_name = format!("{}_{}{}", stem, i, ext);
            if !self.has_conflict(&suffixed_name) {
                return Some(suffixed_name);
            }
        }
        
        None
    }
    
    /// Try adding a directory-based prefix
    fn try_add_prefix(&self, proposed_name: &str, file_path: &Path) -> Option<String> {
        let parent_name = file_path
            .parent()?
            .file_name()?
            .to_str()?;
        
        let (stem, ext) = self.split_name(proposed_name)?;
        
        // Try adding parent directory as prefix
        let prefixed_name = format!("{}_{}{}", parent_name, stem, ext);
        
        if !self.has_conflict(&prefixed_name) {
            Some(prefixed_name)
        } else {
            None
        }
    }
    
    /// Split a file name into stem and extension
    pub fn split_name<'a>(&self, name: &'a str) -> Option<(&'a str, &'a str)> {
        let dot_pos = name.rfind('.')?;
        Some((&name[..dot_pos], &name[dot_pos..]))
    }
    
    /// Register a new name to prevent future conflicts
    pub fn register_name(&mut self, name: String) {
        self.existing_names.insert(name);
    }
    
    /// Detect all conflicts in a set of proposed renamings
    pub fn detect_conflicts(
        &self,
        proposed_renamings: &HashMap<PathBuf, String>,
    ) -> Vec<NamingConflict> {
        let mut conflicts = Vec::new();
        let mut proposed_names: HashMap<String, Vec<PathBuf>> = HashMap::new();
        
        // Group files by proposed name
        for (path, name) in proposed_renamings {
            proposed_names
                .entry(name.clone())
                .or_default()
                .push(path.clone());
        }
        
        // Check for conflicts with existing files
        for (name, paths) in &proposed_names {
            if self.has_conflict(name) {
                for path in paths {
                    conflicts.push(NamingConflict {
                        conflicting_name: name.clone(),
                        existing_file: PathBuf::from(name),
                        proposed_file: path.clone(),
                        resolution_strategy: ConflictResolutionStrategy::UseHierarchicalNaming,
                    });
                }
            }
        }
        
        // Check for conflicts within proposed renamings
        for (name, paths) in proposed_names {
            if paths.len() > 1 {
                for i in 1..paths.len() {
                    conflicts.push(NamingConflict {
                        conflicting_name: name.clone(),
                        existing_file: paths[0].clone(),
                        proposed_file: paths[i].clone(),
                        resolution_strategy: ConflictResolutionStrategy::AddSuffix,
                    });
                }
            }
        }
        
        conflicts
    }
    
    /// Resolve all conflicts in a batch
    pub fn resolve_all_conflicts(
        &mut self,
        conflicts: &[NamingConflict],
    ) -> Result<HashMap<PathBuf, String>> {
        let mut resolutions = HashMap::new();
        
        for conflict in conflicts {
            let resolved_name = self.resolve_conflict(
                &conflict.conflicting_name,
                &conflict.proposed_file,
                None,
            )?;
            
            resolutions.insert(conflict.proposed_file.clone(), resolved_name.clone());
            self.register_name(resolved_name);
        }
        
        Ok(resolutions)
    }
}

impl Default for ConflictResolver {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_conflict_resolver_creation() {
        let resolver = ConflictResolver::new();
        assert_eq!(resolver.existing_names.len(), 0);
    }
    
    #[test]
    fn test_has_conflict() {
        let mut resolver = ConflictResolver::new();
        resolver.register_name("test.rs".to_string());
        
        assert!(resolver.has_conflict("test.rs"));
        assert!(!resolver.has_conflict("other.rs"));
    }
    
    #[test]
    fn test_split_name() {
        let resolver = ConflictResolver::new();
        
        let (stem, ext) = resolver.split_name("test.rs").unwrap();
        assert_eq!(stem, "test");
        assert_eq!(ext, ".rs");
        
        let (stem, ext) = resolver.split_name("file.test.py").unwrap();
        assert_eq!(stem, "file.test");
        assert_eq!(ext, ".py");
    }
    
    #[test]
    fn test_try_add_suffix() {
        let mut resolver = ConflictResolver::new();
        resolver.register_name("test.rs".to_string());
        
        let resolved = resolver.try_add_suffix("test.rs");
        assert_eq!(resolved, Some("test_1.rs".to_string()));
    }
    
    #[test]
    fn test_register_name() {
        let mut resolver = ConflictResolver::new();
        
        resolver.register_name("test.rs".to_string());
        assert!(resolver.has_conflict("test.rs"));
        
        resolver.register_name("other.rs".to_string());
        assert!(resolver.has_conflict("other.rs"));
    }
}
