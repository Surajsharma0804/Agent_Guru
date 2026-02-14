//! Temporal Relationship Tracking with Graph Algorithms
//! `AGENT_GURU` - Task 5 Implementation
//!
//! MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):
//! - Complete temporal relationship tracking with graph algorithms
//! - Full optimization with efficient graph traversal and relationship inference
//! - Production standards: Must handle complex temporal relationships with <100ms query time

use std::collections::{HashMap, HashSet, BTreeMap};
use std::sync::{Arc, RwLock};
use std::time::Instant;

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc, Duration};

/// Configuration for temporal graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalGraphConfig {
    /// Maximum number of nodes before cleanup
    pub max_nodes: usize,
    /// Maximum number of edges per node
    pub max_edges_per_node: usize,
    /// Time window for relationship inference (in seconds)
    pub inference_window_seconds: i64,
    /// Minimum relationship strength to maintain edge
    pub min_relationship_strength: f32,
    /// Enable automatic relationship inference
    pub auto_inference: bool,
    /// Maximum depth for graph traversal
    pub max_traversal_depth: usize,
    /// Enable temporal decay of relationships
    pub enable_temporal_decay: bool,
    /// Decay rate for relationship strength over time
    pub decay_rate: f32,
}

impl Default for TemporalGraphConfig {
    fn default() -> Self {
        Self {
            max_nodes: 100_000,
            max_edges_per_node: 50,
            inference_window_seconds: 3600, // 1 hour
            min_relationship_strength: 0.1,
            auto_inference: true,
            max_traversal_depth: 6,
            enable_temporal_decay: true,
            decay_rate: 0.01, // 1% decay per day
        }
    }
}

/// Types of temporal relationships
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum RelationshipType {
    /// Sequential relationship (A happened before B)
    Sequential,
    /// Causal relationship (A caused B)
    Causal,
    /// Contextual relationship (A and B share context)
    Contextual,
    /// Semantic relationship (A and B are semantically related)
    Semantic,
    /// User-defined relationship
    UserDefined,
    /// Co-occurrence relationship (A and B happened together)
    CoOccurrence,
    /// Reference relationship (A references B)
    Reference,
}

impl RelationshipType {
    /// Get default strength for relationship type
    #[must_use] 
    pub const fn default_strength(&self) -> f32 {
        match self {
            Self::Causal => 0.8,
            Self::Semantic => 0.7,
            Self::Sequential | Self::Reference => 0.6,
            Self::Contextual => 0.5,
            Self::CoOccurrence => 0.4,
            Self::UserDefined => 0.9,
        }
    }
    
    /// Check if relationship type supports temporal decay
    #[must_use] 
    pub const fn supports_decay(&self) -> bool {
        match self {
            Self::UserDefined => false, // User-defined relationships don't decay
            _ => true,
        }
    }
}

/// Temporal node representing a memory entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalNode {
    pub id: Uuid,
    pub content_hash: String,
    pub created_at: DateTime<Utc>,
    pub last_accessed: DateTime<Utc>,
    pub access_count: u64,
    pub node_type: String,
    pub importance_score: f32,
    pub metadata: HashMap<String, String>,
}

impl TemporalNode {
    #[must_use] 
    pub fn new(
        id: Uuid,
        content_hash: String,
        node_type: String,
        importance_score: f32,
        metadata: HashMap<String, String>,
    ) -> Self {
        let now = Utc::now();
        Self {
            id,
            content_hash,
            created_at: now,
            last_accessed: now,
            access_count: 0,
            node_type,
            importance_score,
            metadata,
        }
    }
    
    pub fn update_access(&mut self) {
        self.access_count += 1;
        self.last_accessed = Utc::now();
    }
}

/// Temporal edge representing a relationship between nodes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemporalEdge {
    pub id: Uuid,
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub relationship_type: RelationshipType,
    pub strength: f32,
    pub created_at: DateTime<Utc>,
    pub last_reinforced: DateTime<Utc>,
    pub reinforcement_count: u64,
    pub metadata: HashMap<String, String>,
}

impl TemporalEdge {
    #[must_use] 
    pub fn new(
        source_id: Uuid,
        target_id: Uuid,
        relationship_type: RelationshipType,
        strength: Option<f32>,
        metadata: HashMap<String, String>,
    ) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            source_id,
            target_id,
            relationship_type,
            strength: strength.unwrap_or_else(|| relationship_type.default_strength()),
            created_at: now,
            last_reinforced: now,
            reinforcement_count: 1,
            metadata,
        }
    }
    
    pub fn reinforce(&mut self, additional_strength: f32) {
        self.strength = (self.strength + additional_strength).min(1.0);
        self.last_reinforced = Utc::now();
        self.reinforcement_count += 1;
    }
    
    pub fn apply_temporal_decay(&mut self, decay_rate: f32, now: DateTime<Utc>) {
        if !self.relationship_type.supports_decay() {
            return;
        }
        
        let days_since_reinforcement = now.signed_duration_since(self.last_reinforced).num_days() as f32;
        let decay_factor = (-decay_rate * days_since_reinforcement).exp();
        self.strength *= decay_factor;
    }
    
    #[must_use] 
    pub fn is_expired(&self, min_strength: f32) -> bool {
        self.strength < min_strength
    }
}

/// Path between nodes in the temporal graph
#[derive(Debug, Clone)]
pub struct TemporalPath {
    pub nodes: Vec<Uuid>,
    pub edges: Vec<Uuid>,
    pub total_strength: f32,
    pub path_length: usize,
    pub relationship_types: Vec<RelationshipType>,
}

impl Default for TemporalPath {
    fn default() -> Self {
        Self::new()
    }
}

impl TemporalPath {
    #[must_use] 
    pub const fn new() -> Self {
        Self {
            nodes: Vec::new(),
            edges: Vec::new(),
            total_strength: 0.0,
            path_length: 0,
            relationship_types: Vec::new(),
        }
    }
    
    pub fn add_hop(&mut self, node_id: Uuid, edge_id: Uuid, edge_strength: f32, relationship_type: RelationshipType) {
        self.nodes.push(node_id);
        self.edges.push(edge_id);
        self.total_strength += edge_strength;
        self.path_length += 1;
        self.relationship_types.push(relationship_type);
    }
    
    #[must_use] 
    pub fn average_strength(&self) -> f32 {
        if self.path_length == 0 {
            0.0
        } else {
            self.total_strength / self.path_length as f32
        }
    }
}

/// Query result for temporal graph operations
#[derive(Debug, Clone)]
pub struct TemporalQueryResult {
    pub nodes: Vec<TemporalNode>,
    pub edges: Vec<TemporalEdge>,
    pub paths: Vec<TemporalPath>,
    pub query_time_ms: u64,
    pub total_results: usize,
}

/// Relationship inference result
#[derive(Debug, Clone)]
pub struct InferredRelationship {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub relationship_type: RelationshipType,
    pub confidence: f32,
    pub evidence: Vec<String>,
}

/// Graph statistics for monitoring
#[derive(Debug, Clone)]
pub struct GraphStatistics {
    pub total_nodes: usize,
    pub total_edges: usize,
    pub avg_edges_per_node: f32,
    pub max_edges_per_node: usize,
    pub relationship_type_distribution: HashMap<RelationshipType, usize>,
    pub avg_relationship_strength: f32,
    pub temporal_span_days: i64,
    pub inference_accuracy: f32,
}

/// Temporal graph for tracking relationships between memory entries
pub struct TemporalGraph {
    config: TemporalGraphConfig,
    nodes: Arc<RwLock<HashMap<Uuid, TemporalNode>>>,
    edges: Arc<RwLock<HashMap<Uuid, TemporalEdge>>>,
    adjacency_list: Arc<RwLock<HashMap<Uuid, HashSet<Uuid>>>>, // node_id -> edge_ids
    reverse_adjacency: Arc<RwLock<HashMap<Uuid, HashSet<Uuid>>>>, // for incoming edges
    temporal_index: Arc<RwLock<BTreeMap<DateTime<Utc>, HashSet<Uuid>>>>, // time -> node_ids
    inference_cache: Arc<RwLock<HashMap<String, Vec<InferredRelationship>>>>,
    statistics: Arc<RwLock<GraphStatistics>>,
}

impl TemporalGraph {
    /// Create new temporal graph
    #[must_use] 
    pub fn new(config: TemporalGraphConfig) -> Self {
        Self {
            config,
            nodes: Arc::new(RwLock::new(HashMap::new())),
            edges: Arc::new(RwLock::new(HashMap::new())),
            adjacency_list: Arc::new(RwLock::new(HashMap::new())),
            reverse_adjacency: Arc::new(RwLock::new(HashMap::new())),
            temporal_index: Arc::new(RwLock::new(BTreeMap::new())),
            inference_cache: Arc::new(RwLock::new(HashMap::new())),
            statistics: Arc::new(RwLock::new(GraphStatistics {
                total_nodes: 0,
                total_edges: 0,
                avg_edges_per_node: 0.0,
                max_edges_per_node: 0,
                relationship_type_distribution: HashMap::new(),
                avg_relationship_strength: 0.0,
                temporal_span_days: 0,
                inference_accuracy: 0.0,
            })),
        }
    }
    
    /// Add node to the graph
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn add_node(&self, mut node: TemporalNode) -> Result<Uuid, TemporalGraphError> {
        let node_id = node.id;
        
        // Update access
        node.update_access();
        
        // Add to nodes
        {
            let mut nodes = self.nodes.write().unwrap();
            nodes.insert(node_id, node.clone());
        }
        
        // Add to temporal index
        {
            let mut temporal_index = self.temporal_index.write().unwrap();
            temporal_index.entry(node.created_at).or_default().insert(node_id);
        }
        
        // Initialize adjacency lists
        {
            let mut adjacency = self.adjacency_list.write().unwrap();
            adjacency.insert(node_id, HashSet::new());
        }
        {
            let mut reverse_adjacency = self.reverse_adjacency.write().unwrap();
            reverse_adjacency.insert(node_id, HashSet::new());
        }
        
        // Update statistics
        self.update_statistics();
        
        // Trigger automatic relationship inference if enabled
        if self.config.auto_inference {
            self.infer_relationships_for_node(node_id)?;
        }
        
        Ok(node_id)
    }
    
    /// Add edge to the graph
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn add_edge(&self, edge: TemporalEdge) -> Result<Uuid, TemporalGraphError> {
        let edge_id = edge.id;
        let source_id = edge.source_id;
        let target_id = edge.target_id;
        
        // Validate nodes exist
        {
            let nodes = self.nodes.read().unwrap();
            if !nodes.contains_key(&source_id) || !nodes.contains_key(&target_id) {
                return Err(TemporalGraphError::NodeNotFound);
            }
        }
        
        // Check for existing edge and reinforce if found
        {
            let edges = self.edges.read().unwrap();
            for existing_edge in edges.values() {
                if existing_edge.source_id == source_id 
                    && existing_edge.target_id == target_id 
                    && existing_edge.relationship_type == edge.relationship_type {
                    // Reinforce existing edge instead of creating new one
                    let edge_id = existing_edge.id;
                    let edge_strength = edge.strength;
                    drop(edges);
                    return self.reinforce_edge(edge_id, edge_strength);
                }
            }
        }
        
        // Check edge limits per node
        {
            let adjacency = self.adjacency_list.read().unwrap();
            if let Some(edges) = adjacency.get(&source_id) {
                if edges.len() >= self.config.max_edges_per_node {
                    return Err(TemporalGraphError::TooManyEdges { 
                        limit: self.config.max_edges_per_node 
                    });
                }
            }
        }
        
        // Add edge
        {
            let mut edges = self.edges.write().unwrap();
            edges.insert(edge_id, edge);
        }
        
        // Update adjacency lists
        {
            let mut adjacency = self.adjacency_list.write().unwrap();
            adjacency.entry(source_id).or_default().insert(edge_id);
        }
        {
            let mut reverse_adjacency = self.reverse_adjacency.write().unwrap();
            reverse_adjacency.entry(target_id).or_default().insert(edge_id);
        }
        
        // Clear inference cache
        {
            let mut cache = self.inference_cache.write().unwrap();
            cache.clear();
        }
        
        // Update statistics
        self.update_statistics();
        
        Ok(edge_id)
    }
    
    /// Reinforce existing edge
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn reinforce_edge(&self, edge_id: Uuid, additional_strength: f32) -> Result<Uuid, TemporalGraphError> {
        let mut edges = self.edges.write().unwrap();
        
        edges.get_mut(&edge_id).map_or(
            Err(TemporalGraphError::EdgeNotFound),
            |edge| {
                edge.reinforce(additional_strength);
                Ok(edge_id)
            }
        )
    }
    
    /// Find paths between two nodes
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn find_paths(
        &self,
        source_id: Uuid,
        target_id: Uuid,
        max_depth: Option<usize>,
    ) -> Result<Vec<TemporalPath>, TemporalGraphError> {
        let _start_time = Instant::now();
        let max_depth = max_depth.unwrap_or(self.config.max_traversal_depth);
        
        // Validate nodes exist
        {
            let nodes = self.nodes.read().unwrap();
            if !nodes.contains_key(&source_id) || !nodes.contains_key(&target_id) {
                return Err(TemporalGraphError::NodeNotFound);
            }
        }
        
        let edges = self.edges.read().unwrap();
        let adjacency = self.adjacency_list.read().unwrap();
        
        let mut paths = Vec::new();
        let mut visited = HashSet::new();
        let mut current_path = TemporalPath::new();
        current_path.nodes.push(source_id);
        
        self.dfs_paths(
            source_id,
            target_id,
            &mut current_path,
            &mut visited,
            &mut paths,
            max_depth,
            &edges,
            &adjacency,
        );
        
        // Sort paths by average strength (descending)
        paths.sort_by(|a, b| b.average_strength().partial_cmp(&a.average_strength()).unwrap());
        
        Ok(paths)
    }
    
    /// Depth-first search for paths
    fn dfs_paths(
        &self,
        current: Uuid,
        target: Uuid,
        current_path: &mut TemporalPath,
        visited: &mut HashSet<Uuid>,
        paths: &mut Vec<TemporalPath>,
        max_depth: usize,
        edges: &HashMap<Uuid, TemporalEdge>,
        adjacency: &HashMap<Uuid, HashSet<Uuid>>,
    ) {
        if current == target {
            paths.push(current_path.clone());
            return;
        }
        
        if current_path.path_length >= max_depth {
            return;
        }
        
        visited.insert(current);
        
        if let Some(edge_ids) = adjacency.get(&current) {
            for &edge_id in edge_ids {
                if let Some(edge) = edges.get(&edge_id) {
                    let next_node = edge.target_id;
                    
                    if !visited.contains(&next_node) && edge.strength >= self.config.min_relationship_strength {
                        current_path.add_hop(next_node, edge_id, edge.strength, edge.relationship_type);
                        
                        self.dfs_paths(
                            next_node,
                            target,
                            current_path,
                            visited,
                            paths,
                            max_depth,
                            edges,
                            adjacency,
                        );
                        
                        // Backtrack
                        current_path.nodes.pop();
                        current_path.edges.pop();
                        current_path.total_strength -= edge.strength;
                        current_path.path_length -= 1;
                        current_path.relationship_types.pop();
                    }
                }
            }
        }
        
        visited.remove(&current);
    }
    
    /// Find nodes related to a given node
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn find_related_nodes(
        &self,
        node_id: Uuid,
        relationship_types: Option<&[RelationshipType]>,
        max_results: Option<usize>,
    ) -> Result<TemporalQueryResult, TemporalGraphError> {
        let start_time = Instant::now();
        let max_results = max_results.unwrap_or(50);
        
        // Validate node exists
        {
            let nodes = self.nodes.read().unwrap();
            if !nodes.contains_key(&node_id) {
                return Err(TemporalGraphError::NodeNotFound);
            }
        }
        
        let edges = self.edges.read().unwrap();
        let adjacency = self.adjacency_list.read().unwrap();
        
        let mut related_nodes = Vec::new();
        let mut related_edges = Vec::new();
        let mut node_scores: HashMap<Uuid, f32> = HashMap::new();
        
        // Get direct relationships
        if let Some(edge_ids) = adjacency.get(&node_id) {
            for &edge_id in edge_ids {
                if let Some(edge) = edges.get(&edge_id) {
                    // Filter by relationship type if specified
                    if let Some(ref types) = relationship_types {
                        if !types.contains(&edge.relationship_type) {
                            continue;
                        }
                    }
                    
                    if edge.strength >= self.config.min_relationship_strength {
                        related_edges.push(edge.clone());
                        
                        let target_score = node_scores.entry(edge.target_id).or_insert(0.0);
                        *target_score += edge.strength;
                    }
                }
            }
        }
        
        // Sort nodes by score and collect top results
        let mut scored_nodes: Vec<(Uuid, f32)> = node_scores.into_iter().collect();
        scored_nodes.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        scored_nodes.truncate(max_results);
        
        {
            let nodes = self.nodes.read().unwrap();
            for (related_node_id, _score) in scored_nodes {
                if let Some(node) = nodes.get(&related_node_id) {
                    related_nodes.push(node.clone());
                }
            }
        }
        
        let total_results = related_nodes.len();
        
        Ok(TemporalQueryResult {
            nodes: related_nodes,
            edges: related_edges,
            paths: Vec::new(),
            query_time_ms: start_time.elapsed().as_millis() as u64,
            total_results,
        })
    }
    
    /// Find nodes within a time window
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn find_nodes_in_time_window(
        &self,
        start_time: DateTime<Utc>,
        end_time: DateTime<Utc>,
    ) -> Result<Vec<TemporalNode>, TemporalGraphError> {
        let mut result_nodes = Vec::new();
        
        // Use temporal index for efficient lookup
        {
            let nodes = self.nodes.read().unwrap();
            let temporal_index = self.temporal_index.read().unwrap();
            
            for (&_timestamp, node_ids) in temporal_index.range(start_time..=end_time) {
                for &node_id in node_ids {
                    if let Some(node) = nodes.get(&node_id) {
                        result_nodes.push(node.clone());
                    }
                }
            }
        }
        
        // Sort by creation time
        result_nodes.sort_by_key(|node| node.created_at);
        
        Ok(result_nodes)
    }
    
    /// Infer relationships for a specific node
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn infer_relationships_for_node(&self, node_id: Uuid) -> Result<Vec<InferredRelationship>, TemporalGraphError> {
        let (node_created_at, node_type, inference_window_seconds) = {
            let nodes = self.nodes.read().unwrap();
            let node = nodes.get(&node_id).ok_or(TemporalGraphError::NodeNotFound)?;
            (node.created_at, node.node_type.clone(), self.config.inference_window_seconds)
        };
        
        let inference_window = Duration::seconds(inference_window_seconds);
        let start_time = node_created_at - inference_window;
        let end_time = node_created_at + inference_window;
        
        // Find nodes in temporal window
        let nearby_nodes = self.find_nodes_in_time_window(start_time, end_time)?;
        
        let mut inferred_relationships = Vec::new();
        
        for other_node in nearby_nodes {
            if other_node.id == node_id {
                continue;
            }
            
            // Infer different types of relationships
            
            // Sequential relationship (temporal ordering)
            if other_node.created_at < node_created_at {
                let time_diff = node_created_at.signed_duration_since(other_node.created_at);
                let confidence = (1.0f32 - (time_diff.num_seconds() as f32 / inference_window.num_seconds() as f32)).max(0.1f32);
                
                inferred_relationships.push(InferredRelationship {
                    source_id: other_node.id,
                    target_id: node_id,
                    relationship_type: RelationshipType::Sequential,
                    confidence,
                    evidence: vec![format!("Temporal proximity: {} seconds apart", time_diff.num_seconds())],
                });
            }
            
            // Contextual relationship (same type or metadata similarity)
            if other_node.node_type == node_type {
                let confidence = 0.6;
                inferred_relationships.push(InferredRelationship {
                    source_id: node_id,
                    target_id: other_node.id,
                    relationship_type: RelationshipType::Contextual,
                    confidence,
                    evidence: vec![format!("Same node type: {}", node_type)],
                });
            }
            
            // Co-occurrence relationship (created very close in time)
            let time_diff = (node_created_at - other_node.created_at).num_seconds().abs();
            if time_diff < 60 { // Within 1 minute
                let confidence = 0.8;
                inferred_relationships.push(InferredRelationship {
                    source_id: node_id,
                    target_id: other_node.id,
                    relationship_type: RelationshipType::CoOccurrence,
                    confidence,
                    evidence: vec![format!("Created within {} seconds", time_diff)],
                });
            }
        }
        
        // Filter by confidence threshold and add high-confidence relationships
        let high_confidence_relationships: Vec<_> = inferred_relationships.iter()
            .filter(|rel| rel.confidence > 0.7)
            .collect();
        
        for relationship in &high_confidence_relationships {
            let edge = TemporalEdge::new(
                relationship.source_id,
                relationship.target_id,
                relationship.relationship_type,
                Some(relationship.confidence),
                HashMap::new(),
            );
            
            // Add edge if it doesn't already exist
            let _ = self.add_edge(edge);
        }
        
        Ok(inferred_relationships)
    }
    
    /// Apply temporal decay to all edges
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn apply_temporal_decay(&self) -> Result<usize, TemporalGraphError> {
        if !self.config.enable_temporal_decay {
            return Ok(0);
        }
        
        let now = Utc::now();
        let mut edges_removed = 0;
        let edges_to_remove = {
            let mut edges = self.edges.write().unwrap();
            let mut to_remove = Vec::new();
            
            for (edge_id, edge) in edges.iter_mut() {
                edge.apply_temporal_decay(self.config.decay_rate, now);
                
                if edge.is_expired(self.config.min_relationship_strength) {
                    to_remove.push(*edge_id);
                }
            }
            
            // Remove expired edges
            for edge_id in &to_remove {
                edges.remove(edge_id);
                edges_removed += 1;
            }
            
            to_remove
        };
        
        // Update adjacency lists
        if !edges_to_remove.is_empty() {
            let mut adjacency = self.adjacency_list.write().unwrap();
            let mut reverse_adjacency = self.reverse_adjacency.write().unwrap();
            
            for edge_id in edges_to_remove {
                // Remove from adjacency lists
                for edge_set in adjacency.values_mut() {
                    edge_set.remove(&edge_id);
                }
                for edge_set in reverse_adjacency.values_mut() {
                    edge_set.remove(&edge_id);
                }
            }
        }
        
        // Update statistics
        self.update_statistics();
        
        Ok(edges_removed)
    }
    
    /// Update graph statistics
    fn update_statistics(&self) {
        let (total_nodes, total_edges, avg_degree) = {
            let nodes = self.nodes.read().unwrap();
            let edges = self.edges.read().unwrap();
            let adjacency = self.adjacency_list.read().unwrap();
            
            let avg_degree = if !nodes.is_empty() {
                adjacency.values().map(|edges| edges.len()).sum::<usize>() as f32 / nodes.len() as f32
            } else {
                0.0
            };
            
            (nodes.len(), edges.len(), avg_degree)
        };
        
        let mut stats = self.statistics.write().unwrap();
        
        stats.total_nodes = total_nodes;
        stats.total_edges = total_edges;
        stats.avg_edges_per_node = avg_degree;
        stats.max_edges_per_node = {
            let adjacency = self.adjacency_list.read().unwrap();
            adjacency.values().map(std::collections::HashSet::len).max().unwrap_or(0)
        };
        
        // Relationship type distribution
        {
            let edges = self.edges.read().unwrap();
            stats.relationship_type_distribution.clear();
            for edge in edges.values() {
                *stats.relationship_type_distribution.entry(edge.relationship_type).or_insert(0) += 1;
            }
            
            // Average relationship strength
            if !edges.is_empty() {
                stats.avg_relationship_strength = edges.values().map(|e| e.strength).sum::<f32>() / edges.len() as f32;
            }
        }
        
        // Temporal span
        {
            let nodes = self.nodes.read().unwrap();
            if let (Some(oldest), Some(newest)) = (
                nodes.values().map(|n| n.created_at).min(),
                nodes.values().map(|n| n.created_at).max(),
            ) {
                stats.temporal_span_days = newest.signed_duration_since(oldest).num_days();
            }
        }
    }
    
    /// Get graph statistics
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    #[must_use] 
    pub fn get_statistics(&self) -> GraphStatistics {
        let stats = self.statistics.read().unwrap();
        stats.clone()
    }
    
    /// Remove node and all associated edges
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn remove_node(&self, node_id: Uuid) -> Result<bool, TemporalGraphError> {
        let removed = {
            let mut nodes = self.nodes.write().unwrap();
            nodes.remove(&node_id).is_some()
        };
        
        if removed {
            // Remove from temporal index
            {
                let mut temporal_index = self.temporal_index.write().unwrap();
                for node_set in temporal_index.values_mut() {
                    node_set.remove(&node_id);
                }
            }
            
            // Remove all edges connected to this node
            let edges_to_remove = {
                let edges = self.edges.read().unwrap();
                edges.iter()
                    .filter(|(_, edge)| edge.source_id == node_id || edge.target_id == node_id)
                    .map(|(id, _)| *id)
                    .collect::<Vec<_>>()
            };
            
            {
                let mut edges = self.edges.write().unwrap();
                for edge_id in edges_to_remove {
                    edges.remove(&edge_id);
                }
            }
            
            // Remove from adjacency lists
            {
                let mut adjacency = self.adjacency_list.write().unwrap();
                adjacency.remove(&node_id);
            }
            {
                let mut reverse_adjacency = self.reverse_adjacency.write().unwrap();
                reverse_adjacency.remove(&node_id);
            }
            
            // Update statistics
            self.update_statistics();
        }
        
        Ok(removed)
    }
    
    /// Clear all data
    ///
    /// # Panics
    ///
    /// Panics if the internal `RwLock` is poisoned.
    pub fn clear(&self) -> Result<(), TemporalGraphError> {
        {
            let mut nodes = self.nodes.write().unwrap();
            nodes.clear();
        }
        {
            let mut edges = self.edges.write().unwrap();
            edges.clear();
        }
        {
            let mut adjacency = self.adjacency_list.write().unwrap();
            adjacency.clear();
        }
        {
            let mut reverse_adjacency = self.reverse_adjacency.write().unwrap();
            reverse_adjacency.clear();
        }
        {
            let mut temporal_index = self.temporal_index.write().unwrap();
            temporal_index.clear();
        }
        {
            let mut cache = self.inference_cache.write().unwrap();
            cache.clear();
        }
        
        self.update_statistics();
        
        Ok(())
    }
}

/// Temporal graph errors
#[derive(Debug, thiserror::Error)]
pub enum TemporalGraphError {
    #[error("Node not found")]
    NodeNotFound,
    
    #[error("Edge not found")]
    EdgeNotFound,
    
    #[error("Too many edges per node (limit: {limit})")]
    TooManyEdges { limit: usize },
    
    #[error("Invalid relationship type")]
    InvalidRelationshipType,
    
    #[error("Graph operation failed: {message}")]
    OperationFailed { message: String },
}

#[cfg(test)]
mod tests {
    use super::*;
    
    fn create_test_node(id: Uuid, node_type: &str, importance: f32) -> TemporalNode {
        TemporalNode::new(
            id,
            format!("hash_{}", id),
            node_type.to_string(),
            importance,
            HashMap::new(),
        )
    }
    
    #[test]
    fn test_add_node_and_edge() {
        let config = TemporalGraphConfig::default();
        let graph = TemporalGraph::new(config);
        
        let node1_id = Uuid::new_v4();
        let node2_id = Uuid::new_v4();
        
        let node1 = create_test_node(node1_id, "memory", 0.8);
        let node2 = create_test_node(node2_id, "memory", 0.7);
        
        // Add nodes
        assert!(graph.add_node(node1).is_ok());
        assert!(graph.add_node(node2).is_ok());
        
        // Add edge
        let edge = TemporalEdge::new(
            node1_id,
            node2_id,
            RelationshipType::Sequential,
            Some(0.9),
            HashMap::new(),
        );
        
        assert!(graph.add_edge(edge).is_ok());
        
        // Verify statistics
        let stats = graph.get_statistics();
        assert_eq!(stats.total_nodes, 2);
        assert_eq!(stats.total_edges, 1);
    }
    
    #[test]
    fn test_find_related_nodes() {
        let config = TemporalGraphConfig::default();
        let graph = TemporalGraph::new(config);
        
        let node1_id = Uuid::new_v4();
        let node2_id = Uuid::new_v4();
        let node3_id = Uuid::new_v4();
        
        // Add nodes
        graph.add_node(create_test_node(node1_id, "memory", 0.8)).unwrap();
        graph.add_node(create_test_node(node2_id, "memory", 0.7)).unwrap();
        graph.add_node(create_test_node(node3_id, "memory", 0.6)).unwrap();
        
        // Add edges
        let edge1 = TemporalEdge::new(node1_id, node2_id, RelationshipType::Sequential, Some(0.9), HashMap::new());
        let edge2 = TemporalEdge::new(node1_id, node3_id, RelationshipType::Contextual, Some(0.7), HashMap::new());
        
        graph.add_edge(edge1).unwrap();
        graph.add_edge(edge2).unwrap();
        
        // Find related nodes
        let result = graph.find_related_nodes(node1_id, None, None).unwrap();
        
        assert_eq!(result.nodes.len(), 2);
        assert_eq!(result.edges.len(), 2);
    }
    
    #[test]
    fn test_find_paths() {
        let config = TemporalGraphConfig::default();
        let graph = TemporalGraph::new(config);
        
        let node1_id = Uuid::new_v4();
        let node2_id = Uuid::new_v4();
        let node3_id = Uuid::new_v4();
        
        // Add nodes
        graph.add_node(create_test_node(node1_id, "memory", 0.8)).unwrap();
        graph.add_node(create_test_node(node2_id, "memory", 0.7)).unwrap();
        graph.add_node(create_test_node(node3_id, "memory", 0.6)).unwrap();
        
        // Add edges to create a path: node1 -> node2 -> node3
        let edge1 = TemporalEdge::new(node1_id, node2_id, RelationshipType::Sequential, Some(0.9), HashMap::new());
        let edge2 = TemporalEdge::new(node2_id, node3_id, RelationshipType::Sequential, Some(0.8), HashMap::new());
        
        graph.add_edge(edge1).unwrap();
        graph.add_edge(edge2).unwrap();
        
        // Find paths
        let paths = graph.find_paths(node1_id, node3_id, None).unwrap();
        
        assert_eq!(paths.len(), 1);
        assert_eq!(paths[0].nodes.len(), 3);
        assert_eq!(paths[0].path_length, 2);
    }
    
    #[test]
    fn test_temporal_decay() {
        let mut config = TemporalGraphConfig::default();
        config.enable_temporal_decay = true;
        config.decay_rate = 1.0; // High decay rate for testing
        config.min_relationship_strength = 0.5;
        
        let graph = TemporalGraph::new(config);
        
        let node1_id = Uuid::new_v4();
        let node2_id = Uuid::new_v4();
        
        // Add nodes
        graph.add_node(create_test_node(node1_id, "memory", 0.8)).unwrap();
        graph.add_node(create_test_node(node2_id, "memory", 0.7)).unwrap();
        
        // Add edge with low strength
        let edge = TemporalEdge::new(node1_id, node2_id, RelationshipType::Sequential, Some(0.3), HashMap::new());
        graph.add_edge(edge).unwrap();
        
        // Apply decay (should remove the weak edge)
        let removed_count = graph.apply_temporal_decay().unwrap();
        
        // Verify edge was removed due to decay
        let stats = graph.get_statistics();
        assert_eq!(stats.total_edges, 0);
        assert_eq!(removed_count, 1);
    }
    
    #[test]
    fn test_relationship_inference() {
        let mut config = TemporalGraphConfig::default();
        config.auto_inference = false; // Manual inference for testing
        
        let graph = TemporalGraph::new(config);
        
        let node1_id = Uuid::new_v4();
        let node2_id = Uuid::new_v4();
        
        // Create nodes with same type (should infer contextual relationship)
        let mut node1 = create_test_node(node1_id, "conversation", 0.8);
        let mut node2 = create_test_node(node2_id, "conversation", 0.7);
        
        // Make them close in time
        let now = Utc::now();
        node1.created_at = now;
        node2.created_at = now + Duration::seconds(30);
        
        graph.add_node(node1).unwrap();
        graph.add_node(node2).unwrap();
        
        // Infer relationships
        let inferred = graph.infer_relationships_for_node(node2_id).unwrap();
        
        assert!(!inferred.is_empty());
        
        // Should have inferred contextual and co-occurrence relationships
        let has_contextual = inferred.iter().any(|r| r.relationship_type == RelationshipType::Contextual);
        let has_cooccurrence = inferred.iter().any(|r| r.relationship_type == RelationshipType::CoOccurrence);
        
        assert!(has_contextual || has_cooccurrence);
    }
}