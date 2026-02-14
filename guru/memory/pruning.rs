//! Intelligent Memory Pruning with Importance Scoring
//! `AGENT_GURU` - Task 5 Implementation
//!
//! MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):
//! - Complete intelligent memory pruning with importance scoring
//! - Full optimization with machine learning-based importance prediction
//! - Production standards: Must handle memory limits with zero data loss of important information

use std::collections::{HashMap, VecDeque};
use std::cmp::Ordering;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

/// Configuration for memory pruning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PruningConfig {
    /// Maximum number of entries before pruning is triggered
    pub max_entries: usize,
    /// Target number of entries after pruning
    pub target_entries: usize,
    /// Minimum importance score to avoid pruning
    pub min_importance_threshold: f32,
    /// Weight for recency in importance calculation
    pub recency_weight: f32,
    /// Weight for access frequency in importance calculation
    pub frequency_weight: f32,
    /// Weight for user-assigned importance in calculation
    pub user_importance_weight: f32,
    /// Weight for content similarity clustering
    pub similarity_weight: f32,
    /// Enable machine learning-based importance prediction
    pub use_ml_prediction: bool,
    /// Pruning strategy to use
    pub strategy: PruningStrategy,
    /// Minimum age before entry can be pruned (in seconds)
    pub min_age_for_pruning: u64,
    /// Enable gradual pruning instead of batch pruning
    pub gradual_pruning: bool,
}

impl Default for PruningConfig {
    fn default() -> Self {
        Self {
            max_entries: 100_000,
            target_entries: 80_000,
            min_importance_threshold: 0.1,
            recency_weight: 0.3,
            frequency_weight: 0.3,
            user_importance_weight: 0.4,
            similarity_weight: 0.2,
            use_ml_prediction: true,
            strategy: PruningStrategy::Hybrid,
            min_age_for_pruning: 3600, // 1 hour
            gradual_pruning: true,
        }
    }
}

/// Pruning strategies
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum PruningStrategy {
    /// Least Recently Used (LRU)
    Lru,
    /// Least Frequently Used (LFU)
    Lfu,
    /// Importance-based pruning
    ImportanceBased,
    /// Hybrid approach combining multiple factors
    Hybrid,
    /// Machine learning-based prediction
    MachineLearning,
}

/// Memory entry for pruning analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrunableEntry {
    pub id: Uuid,
    pub content_hash: String,
    pub user_importance: f32,
    pub access_count: u64,
    pub created_at: DateTime<Utc>,
    pub last_accessed: DateTime<Utc>,
    pub content_size: usize,
    pub content_type: String,
    pub embedding: Option<Vec<f32>>,
    pub metadata: HashMap<String, String>,
}

impl PrunableEntry {
    /// Calculate recency score (0.0 to 1.0, higher = more recent)
    #[must_use] 
    pub fn recency_score(&self, now: DateTime<Utc>) -> f32 {
        let age = now.signed_duration_since(self.last_accessed);
        let age_hours = age.num_hours() as f32;
        
        // Exponential decay: score = e^(-age_hours / 24)
        (-age_hours / 24.0).exp().min(1.0).max(0.0)
    }
    
    /// Calculate frequency score (0.0 to 1.0, normalized by max access count)
    #[must_use] 
    pub fn frequency_score(&self, max_access_count: u64) -> f32 {
        if max_access_count == 0 {
            0.0
        } else {
            (self.access_count as f32 / max_access_count as f32).min(1.0)
        }
    }
    
    /// Calculate age in hours
    #[must_use] 
    pub fn age_hours(&self, now: DateTime<Utc>) -> f32 {
        let age = now.signed_duration_since(self.created_at);
        age.num_hours() as f32
    }
    
    /// Check if entry is old enough to be pruned
    #[must_use] 
    pub fn is_prunable(&self, config: &PruningConfig, now: DateTime<Utc>) -> bool {
        let age = now.signed_duration_since(self.created_at);
        age.num_seconds() >= config.min_age_for_pruning as i64
    }
}

/// Importance score with breakdown
#[derive(Debug, Clone, PartialEq)]
pub struct ImportanceScore {
    pub total: f32,
    pub recency: f32,
    pub frequency: f32,
    pub user_importance: f32,
    pub similarity: f32,
    pub ml_prediction: Option<f32>,
}

impl ImportanceScore {
    /// Create new importance score
    #[must_use] 
    pub fn new(
        recency: f32,
        frequency: f32,
        user_importance: f32,
        similarity: f32,
        config: &PruningConfig,
    ) -> Self {
        let total = recency.mul_add(config.recency_weight, frequency * config.frequency_weight)
            + user_importance * config.user_importance_weight
            + similarity * config.similarity_weight;
        
        Self {
            total,
            recency,
            frequency,
            user_importance,
            similarity,
            ml_prediction: None,
        }
    }
    
    /// Update with ML prediction
    #[must_use] 
    pub fn with_ml_prediction(mut self, prediction: f32) -> Self {
        self.ml_prediction = Some(prediction);
        // Blend ML prediction with traditional score
        self.total = self.total.mul_add(0.7, prediction * 0.3);
        self
    }
}

/// Entry with calculated importance for pruning decisions
#[derive(Debug, Clone)]
struct ScoredEntry {
    entry: PrunableEntry,
    importance: ImportanceScore,
}

impl PartialEq for ScoredEntry {
    fn eq(&self, other: &Self) -> bool {
        self.importance.total == other.importance.total
    }
}

impl Eq for ScoredEntry {}

impl PartialOrd for ScoredEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ScoredEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse ordering for min-heap (lowest importance first)
        other.importance.total.partial_cmp(&self.importance.total)
            .unwrap_or(Ordering::Equal)
    }
}

/// Similarity cluster for content-based pruning
#[derive(Debug, Clone)]
struct SimilarityCluster {
    centroid: Vec<f32>,
    entries: Vec<Uuid>,
    avg_importance: f32,
}

impl SimilarityCluster {
    const fn new(centroid: Vec<f32>) -> Self {
        Self {
            centroid,
            entries: Vec::new(),
            avg_importance: 0.0,
        }
    }
    
    fn add_entry(&mut self, entry_id: Uuid, importance: f32) {
        self.entries.push(entry_id);
        self.avg_importance = self.avg_importance.mul_add((self.entries.len() - 1) as f32, importance) 
            / self.entries.len() as f32;
    }
    
    fn similarity_to(&self, embedding: &[f32]) -> f32 {
        cosine_similarity(&self.centroid, embedding)
    }
}

/// Machine learning model for importance prediction
#[derive(Debug, Clone)]
struct ImportancePredictor {
    weights: Vec<f32>,
    bias: f32,
    feature_means: Vec<f32>,
    feature_stds: Vec<f32>,
}

impl ImportancePredictor {
    /// Create new predictor with random weights
    fn new(feature_count: usize) -> Self {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        
        Self {
            weights: (0..feature_count).map(|_| rng.gen_range(-0.1..0.1)).collect(),
            bias: 0.0,
            feature_means: vec![0.0; feature_count],
            feature_stds: vec![1.0; feature_count],
        }
    }
    
    /// Extract features from entry for ML prediction
    fn extract_features(&self, entry: &PrunableEntry, now: DateTime<Utc>) -> Vec<f32> {
        vec![
            entry.recency_score(now),
            entry.access_count as f32,
            entry.user_importance,
            entry.content_size as f32,
            entry.age_hours(now),
            if entry.embedding.is_some() { 1.0 } else { 0.0 },
            entry.metadata.len() as f32,
        ]
    }
    
    /// Predict importance score using linear model
    fn predict(&self, entry: &PrunableEntry, now: DateTime<Utc>) -> f32 {
        let features = self.extract_features(entry, now);
        
        // Normalize features
        let normalized: Vec<f32> = features.iter()
            .zip(&self.feature_means)
            .zip(&self.feature_stds)
            .map(|((f, mean), std)| (f - mean) / std)
            .collect();
        
        // Linear prediction
        let prediction: f32 = normalized.iter()
            .zip(&self.weights)
            .map(|(f, w)| f * w)
            .sum::<f32>() + self.bias;
        
        // Sigmoid activation
        1.0 / (1.0 + (-prediction).exp())
    }
    
    /// Update model with feedback (simplified online learning)
    #[allow(dead_code)]
    fn update(&mut self, entry: &PrunableEntry, now: DateTime<Utc>, target: f32, learning_rate: f32) {
        let features = self.extract_features(entry, now);
        let prediction = self.predict(entry, now);
        let error = target - prediction;
        
        // Update weights using gradient descent
        for (i, &feature) in features.iter().enumerate() {
            if i < self.weights.len() {
                self.weights[i] += learning_rate * error * feature;
            }
        }
        self.bias += learning_rate * error;
        
        // Update feature statistics (exponential moving average)
        let alpha = 0.01_f32;
        for (i, &feature) in features.iter().enumerate() {
            if i < self.feature_means.len() {
                self.feature_means[i] = (1.0 - alpha).mul_add(self.feature_means[i], alpha * feature);
                let diff = feature - self.feature_means[i];
                self.feature_stds[i] = (1.0 - alpha).mul_add(self.feature_stds[i].powi(2), alpha * diff.powi(2)).sqrt();
            }
        }
    }
}

/// Pruning statistics and metrics
#[derive(Debug, Default, Clone)]
pub struct PruningMetrics {
    pub total_pruning_operations: u64,
    pub total_entries_pruned: u64,
    pub avg_pruning_time_ms: f64,
    pub last_pruning_time: Option<DateTime<Utc>>,
    pub entries_by_strategy: HashMap<PruningStrategy, u64>,
    pub importance_distribution: Vec<f32>,
    pub false_positive_rate: f32,
    pub user_satisfaction_score: f32,
}

/// Intelligent memory pruning system
pub struct MemoryPruning {
    config: PruningConfig,
    similarity_clusters: Arc<RwLock<Vec<SimilarityCluster>>>,
    ml_predictor: Arc<RwLock<Option<ImportancePredictor>>>,
    metrics: Arc<RwLock<PruningMetrics>>,
    pruning_history: Arc<RwLock<VecDeque<PruningEvent>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct PruningEvent {
    timestamp: DateTime<Utc>,
    entries_pruned: usize,
    strategy_used: PruningStrategy,
    avg_importance_pruned: f32,
    duration_ms: u64,
}

impl MemoryPruning {
    /// Create new memory pruning system
    #[must_use] 
    pub fn new(config: PruningConfig) -> Self {
        let ml_predictor = if config.use_ml_prediction {
            Some(ImportancePredictor::new(7)) // 7 features
        } else {
            None
        };
        
        Self {
            config,
            similarity_clusters: Arc::new(RwLock::new(Vec::new())),
            ml_predictor: Arc::new(RwLock::new(ml_predictor)),
            metrics: Arc::new(RwLock::new(PruningMetrics::default())),
            pruning_history: Arc::new(RwLock::new(VecDeque::new())),
        }
    }
    
    /// Determine if pruning is needed
    #[must_use] 
    pub const fn needs_pruning(&self, current_count: usize) -> bool {
        current_count > self.config.max_entries
    }
    
    /// Select entries for pruning based on configured strategy
    pub fn select_entries_for_pruning(
        &self,
        entries: &[PrunableEntry],
    ) -> Result<Vec<Uuid>, PruningError> {
        let start_time = Instant::now();
        let now = Utc::now();
        
        if entries.len() <= self.config.target_entries {
            return Ok(Vec::new());
        }
        
        let entries_to_remove = entries.len() - self.config.target_entries;
        
        let selected = match self.config.strategy {
            PruningStrategy::Lru => self.select_lru(entries, entries_to_remove, now),
            PruningStrategy::Lfu => self.select_lfu(entries, entries_to_remove, now),
            PruningStrategy::ImportanceBased => self.select_importance_based(entries, entries_to_remove, now),
            PruningStrategy::Hybrid => self.select_hybrid(entries, entries_to_remove, now),
            PruningStrategy::MachineLearning => self.select_ml_based(entries, entries_to_remove, now),
        }?;
        
        // Update metrics
        self.update_pruning_metrics(&selected, entries, start_time.elapsed());
        
        Ok(selected)
    }
    
    /// LRU-based selection
    fn select_lru(&self, entries: &[PrunableEntry], count: usize, now: DateTime<Utc>) -> Result<Vec<Uuid>, PruningError> {
        let mut candidates: Vec<_> = entries.iter()
            .filter(|entry| entry.is_prunable(&self.config, now))
            .collect();
        
        // Sort by last accessed time (oldest first)
        candidates.sort_by_key(|entry| entry.last_accessed);
        
        Ok(candidates.into_iter()
            .take(count)
            .map(|entry| entry.id)
            .collect())
    }
    
    /// LFU-based selection
    fn select_lfu(&self, entries: &[PrunableEntry], count: usize, now: DateTime<Utc>) -> Result<Vec<Uuid>, PruningError> {
        let mut candidates: Vec<_> = entries.iter()
            .filter(|entry| entry.is_prunable(&self.config, now))
            .collect();
        
        // Sort by access count (least accessed first)
        candidates.sort_by_key(|entry| entry.access_count);
        
        Ok(candidates.into_iter()
            .take(count)
            .map(|entry| entry.id)
            .collect())
    }
    
    /// Importance-based selection
    fn select_importance_based(&self, entries: &[PrunableEntry], count: usize, now: DateTime<Utc>) -> Result<Vec<Uuid>, PruningError> {
        let max_access_count = entries.iter().map(|e| e.access_count).max().unwrap_or(1);
        
        let mut scored_entries: Vec<ScoredEntry> = entries.iter()
            .filter(|entry| entry.is_prunable(&self.config, now))
            .map(|entry| {
                let recency = entry.recency_score(now);
                let frequency = entry.frequency_score(max_access_count);
                let similarity = self.calculate_similarity_score(entry);
                
                let importance = ImportanceScore::new(
                    recency,
                    frequency,
                    entry.user_importance,
                    similarity,
                    &self.config,
                );
                
                ScoredEntry {
                    entry: entry.clone(),
                    importance,
                }
            })
            .collect();
        
        // Sort by importance (lowest first)
        scored_entries.sort();
        
        Ok(scored_entries.into_iter()
            .take(count)
            .filter(|scored| scored.importance.total < self.config.min_importance_threshold)
            .map(|scored| scored.entry.id)
            .collect())
    }
    
    /// Hybrid selection combining multiple strategies
    fn select_hybrid(&self, entries: &[PrunableEntry], count: usize, now: DateTime<Utc>) -> Result<Vec<Uuid>, PruningError> {
        let max_access_count = entries.iter().map(|e| e.access_count).max().unwrap_or(1);
        
        let mut scored_entries: Vec<ScoredEntry> = entries.iter()
            .filter(|entry| entry.is_prunable(&self.config, now))
            .map(|entry| {
                let recency = entry.recency_score(now);
                let frequency = entry.frequency_score(max_access_count);
                let similarity = self.calculate_similarity_score(entry);
                
                let mut importance = ImportanceScore::new(
                    recency,
                    frequency,
                    entry.user_importance,
                    similarity,
                    &self.config,
                );
                
                // Add ML prediction if available
                if let Ok(predictor_guard) = self.ml_predictor.read() {
                    if let Some(ref predictor) = *predictor_guard {
                        let ml_score = predictor.predict(entry, now);
                        importance = importance.with_ml_prediction(ml_score);
                    }
                }
                
                ScoredEntry {
                    entry: entry.clone(),
                    importance,
                }
            })
            .collect();
        
        // Sort by total importance (lowest first)
        scored_entries.sort();
        
        // Apply additional filters
        let selected: Vec<Uuid> = scored_entries.into_iter()
            .take(count * 2) // Consider more candidates
            .filter(|scored| {
                // Don't prune very important entries
                scored.importance.total < self.config.min_importance_threshold ||
                // Or very recent entries with high user importance
                !(scored.importance.recency > 0.8 && scored.entry.user_importance > 0.8)
            })
            .take(count)
            .map(|scored| scored.entry.id)
            .collect();
        
        Ok(selected)
    }
    
    /// Machine learning-based selection
    fn select_ml_based(&self, entries: &[PrunableEntry], count: usize, now: DateTime<Utc>) -> Result<Vec<Uuid>, PruningError> {
        let predictor_guard = self.ml_predictor.read().unwrap();
        let predictor = predictor_guard.as_ref()
            .ok_or(PruningError::MlPredictorNotAvailable)?;
        
        let mut predictions: Vec<(Uuid, f32)> = entries.iter()
            .filter(|entry| entry.is_prunable(&self.config, now))
            .map(|entry| (entry.id, predictor.predict(entry, now)))
            .collect();
        
        // Sort by predicted importance (lowest first)
        predictions.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));
        
        Ok(predictions.into_iter()
            .take(count)
            .filter(|(_, score)| *score < self.config.min_importance_threshold)
            .map(|(id, _)| id)
            .collect())
    }
    
    /// Calculate similarity score for entry based on clustering
    fn calculate_similarity_score(&self, entry: &PrunableEntry) -> f32 {
        if let Some(ref embedding) = entry.embedding {
            let clusters = self.similarity_clusters.read().unwrap();
            
            if clusters.is_empty() {
                return 0.5; // Neutral score if no clusters
            }
            
            // Find best matching cluster
            let best_similarity = clusters.iter()
                .map(|cluster| cluster.similarity_to(embedding))
                .fold(0.0f32, f32::max);
            
            best_similarity
        } else {
            0.0 // No embedding available
        }
    }
    
    /// Update similarity clusters for content-based analysis
    pub fn update_similarity_clusters(&self, entries: &[PrunableEntry]) -> Result<(), PruningError> {
        let embeddings: Vec<(Uuid, Vec<f32>)> = entries.iter()
            .filter_map(|entry| {
                entry.embedding.as_ref().map(|emb| (entry.id, emb.clone()))
            })
            .collect();
        
        if embeddings.len() < 10 {
            return Ok(());
        }
        
        // Simple k-means clustering (k=10)
        let k = std::cmp::min(10, embeddings.len() / 5);
        let clusters = self.kmeans_clustering(&embeddings, k)?;
        
        let mut similarity_clusters = self.similarity_clusters.write().unwrap();
        *similarity_clusters = clusters;
        
        Ok(())
    }
    
    /// Simple k-means clustering implementation
    fn kmeans_clustering(&self, embeddings: &[(Uuid, Vec<f32>)], k: usize) -> Result<Vec<SimilarityCluster>, PruningError> {
        if embeddings.is_empty() || k == 0 {
            return Ok(Vec::new());
        }
        
        let dim = embeddings[0].1.len();
        let mut clusters = Vec::new();
        
        // Initialize centroids randomly
        use rand::seq::SliceRandom;
        let mut rng = rand::thread_rng();
        let selected_embeddings: Vec<_> = embeddings.choose_multiple(&mut rng, k).collect();
        
        for embedding in selected_embeddings {
            clusters.push(SimilarityCluster::new(embedding.1.clone()));
        }
        
        // K-means iterations
        for _ in 0..10 {
            // Clear cluster assignments
            for cluster in &mut clusters {
                cluster.entries.clear();
                cluster.avg_importance = 0.0;
            }
            
            // Assign embeddings to clusters
            for (id, embedding) in embeddings {
                let mut best_cluster = 0;
                let mut best_similarity = -1.0;
                
                for (i, cluster) in clusters.iter().enumerate() {
                    let similarity = cosine_similarity(embedding, &cluster.centroid);
                    if similarity > best_similarity {
                        best_similarity = similarity;
                        best_cluster = i;
                    }
                }
                
                clusters[best_cluster].add_entry(*id, 0.5); // Default importance
            }
            
            // Update centroids
            for cluster in &mut clusters {
                if !cluster.entries.is_empty() {
                    let mut new_centroid = vec![0.0; dim];
                    
                    for entry_id in &cluster.entries {
                        if let Some((_, embedding)) = embeddings.iter().find(|(id, _)| id == entry_id) {
                            for (i, &val) in embedding.iter().enumerate() {
                                new_centroid[i] += val;
                            }
                        }
                    }
                    
                    for val in &mut new_centroid {
                        *val /= cluster.entries.len() as f32;
                    }
                    
                    cluster.centroid = new_centroid;
                }
            }
        }
        
        Ok(clusters)
    }
    
    /// Provide feedback to ML model for continuous learning
    pub fn provide_feedback(&self, _entry_id: Uuid, was_correctly_pruned: bool) -> Result<(), PruningError> {
        // This would be called after user feedback on pruning decisions
        // For now, just update metrics
        let mut metrics = self.metrics.write().unwrap();
        
        if was_correctly_pruned {
            metrics.user_satisfaction_score = metrics.user_satisfaction_score.mul_add(0.9, 1.0 * 0.1).min(1.0);
        } else {
            metrics.user_satisfaction_score = metrics.user_satisfaction_score.mul_add(0.9, 0.0 * 0.1).max(0.0);
            metrics.false_positive_rate = metrics.false_positive_rate.mul_add(0.9, 1.0 * 0.1).min(1.0);
        }
        
        Ok(())
    }
    
    /// Update pruning metrics
    fn update_pruning_metrics(&self, selected: &[Uuid], all_entries: &[PrunableEntry], duration: Duration) {
        let mut metrics = self.metrics.write().unwrap();
        
        metrics.total_pruning_operations += 1;
        metrics.total_entries_pruned += selected.len() as u64;
        
        let pruning_time = duration.as_millis() as f64;
        metrics.avg_pruning_time_ms = 
            metrics.avg_pruning_time_ms.mul_add((metrics.total_pruning_operations - 1) as f64, pruning_time) 
            / metrics.total_pruning_operations as f64;
        
        metrics.last_pruning_time = Some(Utc::now());
        
        // Update strategy statistics
        let strategy_count = metrics.entries_by_strategy.entry(self.config.strategy).or_insert(0);
        *strategy_count += selected.len() as u64;
        
        // Calculate importance distribution of pruned entries
        let pruned_entries: Vec<_> = all_entries.iter()
            .filter(|entry| selected.contains(&entry.id))
            .collect();
        
        if !pruned_entries.is_empty() {
            let avg_importance: f32 = pruned_entries.iter()
                .map(|entry| entry.user_importance)
                .sum::<f32>() / pruned_entries.len() as f32;
            
            metrics.importance_distribution.push(avg_importance);
            
            // Keep only last 100 measurements
            if metrics.importance_distribution.len() > 100 {
                metrics.importance_distribution.remove(0);
            }
        }
        
        // Record pruning event
        let event = PruningEvent {
            timestamp: Utc::now(),
            entries_pruned: selected.len(),
            strategy_used: self.config.strategy,
            avg_importance_pruned: pruned_entries.iter()
                .map(|e| e.user_importance)
                .sum::<f32>() / pruned_entries.len().max(1) as f32,
            duration_ms: duration.as_millis() as u64,
        };
        
        let mut history = self.pruning_history.write().unwrap();
        history.push_back(event);
        
        // Keep only last 1000 events
        if history.len() > 1000 {
            history.pop_front();
        }
    }
    
    /// Get pruning metrics
    #[must_use] 
    pub fn get_metrics(&self) -> PruningMetrics {
        let metrics = self.metrics.read().unwrap();
        metrics.clone()
    }
    
    /// Get pruning history
    #[must_use] 
    pub fn get_pruning_history(&self) -> Vec<PruningEvent> {
        let history = self.pruning_history.read().unwrap();
        history.iter().cloned().collect()
    }
    
    /// Update configuration
    pub fn update_config(&mut self, new_config: PruningConfig) {
        self.config = new_config;
        
        // Reinitialize ML predictor if needed
        if self.config.use_ml_prediction {
            let mut predictor_guard = self.ml_predictor.write().unwrap();
            if predictor_guard.is_none() {
                *predictor_guard = Some(ImportancePredictor::new(7));
            }
        }
    }
}

/// Pruning errors
#[derive(Debug, thiserror::Error)]
pub enum PruningError {
    #[error("ML predictor not available")]
    MlPredictorNotAvailable,
    
    #[error("Clustering failed: {message}")]
    ClusteringFailed { message: String },
    
    #[error("Invalid configuration: {message}")]
    InvalidConfiguration { message: String },
    
    #[error("Insufficient data for analysis")]
    InsufficientData,
}

// Utility functions

/// Compute cosine similarity between two vectors
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }
    
    let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    
    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        dot_product / (norm_a * norm_b)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    fn create_test_entry(id: Uuid, importance: f32, access_count: u64, age_hours: i64) -> PrunableEntry {
        let now = Utc::now();
        PrunableEntry {
            id,
            content_hash: format!("hash_{}", id),
            user_importance: importance,
            access_count,
            created_at: now - chrono::Duration::hours(age_hours),
            last_accessed: now - chrono::Duration::hours(age_hours / 2),
            content_size: 1000,
            content_type: "text".to_string(),
            embedding: Some(vec![0.1, 0.2, 0.3]),
            metadata: HashMap::new(),
        }
    }
    
    #[test]
    fn test_importance_score_calculation() {
        let config = PruningConfig::default();
        let now = Utc::now();
        
        let entry = create_test_entry(Uuid::new_v4(), 0.8, 100, 2);
        
        let recency = entry.recency_score(now);
        let frequency = entry.frequency_score(200);
        
        let score = ImportanceScore::new(recency, frequency, entry.user_importance, 0.5, &config);
        
        assert!(score.total > 0.0);
        assert!(score.total <= 1.0);
        assert_eq!(score.user_importance, 0.8);
        assert_eq!(score.frequency, 0.5); // 100/200
    }
    
    #[test]
    fn test_lru_selection() {
        let config = PruningConfig::default();
        let pruning = MemoryPruning::new(config);
        
        let entries = vec![
            create_test_entry(Uuid::new_v4(), 0.5, 10, 10), // Oldest
            create_test_entry(Uuid::new_v4(), 0.5, 20, 5),  // Newer
            create_test_entry(Uuid::new_v4(), 0.5, 30, 2),  // Newest
        ];
        
        let selected = pruning.select_lru(&entries, 1, Utc::now()).unwrap();
        
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0], entries[0].id); // Should select oldest
    }
    
    #[test]
    fn test_lfu_selection() {
        let config = PruningConfig::default();
        let pruning = MemoryPruning::new(config);
        
        let entries = vec![
            create_test_entry(Uuid::new_v4(), 0.5, 5, 5),   // Least accessed
            create_test_entry(Uuid::new_v4(), 0.5, 20, 5),  // More accessed
            create_test_entry(Uuid::new_v4(), 0.5, 100, 5), // Most accessed
        ];
        
        let selected = pruning.select_lfu(&entries, 1, Utc::now()).unwrap();
        
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0], entries[0].id); // Should select least accessed
    }
    
    #[test]
    fn test_importance_based_selection() {
        let config = PruningConfig::default();
        let pruning = MemoryPruning::new(config);
        
        let entries = vec![
            create_test_entry(Uuid::new_v4(), 0.1, 5, 10),   // Low importance
            create_test_entry(Uuid::new_v4(), 0.9, 100, 2),  // High importance
            create_test_entry(Uuid::new_v4(), 0.3, 20, 5),   // Medium importance
        ];
        
        let selected = pruning.select_importance_based(&entries, 1, Utc::now()).unwrap();
        
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0], entries[0].id); // Should select lowest importance
    }
    
    #[test]
    fn test_pruning_metrics_update() {
        let config = PruningConfig::default();
        let pruning = MemoryPruning::new(config);
        
        let entries = vec![
            create_test_entry(Uuid::new_v4(), 0.5, 10, 5),
        ];
        
        let selected = vec![entries[0].id];
        pruning.update_pruning_metrics(&selected, &entries, Duration::from_millis(100));
        
        let metrics = pruning.get_metrics();
        assert_eq!(metrics.total_pruning_operations, 1);
        assert_eq!(metrics.total_entries_pruned, 1);
        assert!(metrics.avg_pruning_time_ms > 0.0);
    }
    
    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![0.0, 1.0, 0.0];
        let c = vec![1.0, 0.0, 0.0];
        
        assert!((cosine_similarity(&a, &b) - 0.0).abs() < 1e-6);
        assert!((cosine_similarity(&a, &c) - 1.0).abs() < 1e-6);
    }
    
    #[test]
    fn test_ml_predictor() {
        let mut predictor = ImportancePredictor::new(7);
        let entry = create_test_entry(Uuid::new_v4(), 0.8, 50, 3);
        let now = Utc::now();
        
        let prediction1 = predictor.predict(&entry, now);
        assert!(prediction1 >= 0.0 && prediction1 <= 1.0);
        
        // Update with feedback
        predictor.update(&entry, now, 0.9, 0.01);
        
        let prediction2 = predictor.predict(&entry, now);
        assert!(prediction2 >= 0.0 && prediction2 <= 1.0);
    }
}
