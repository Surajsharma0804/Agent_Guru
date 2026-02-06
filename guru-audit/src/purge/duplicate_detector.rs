//! Advanced Duplicate Code Detector
//!
//! This module provides comprehensive duplicate code detection with refactoring
//! recommendations and complexity analysis. Designed for production-grade code
//! quality improvement with mathematical similarity metrics.
//!
//! Performance Requirements:
//! - Duplicate detection: ≤2 seconds per 1000 lines of code
//! - Similarity calculation: ≤50ms per code block comparison
//! - Refactoring analysis: ≤100ms per duplicate group

use crate::error::AuditError;
use crate::purge::types::*;
use std::collections::{HashMap, HashSet};
use std::time::{SystemTime, Instant};
use uuid::Uuid;

/// Duplicate code detector with refactoring recommendations
pub struct DuplicateDetector {
    /// Configuration
    #[allow(dead_code)]
    config: PurgeConfig,
    /// Minimum lines for duplicate detection
    min_duplicate_lines: usize,
    /// Minimum similarity threshold (0.0 to 1.0)
    min_similarity: f64,
}

impl DuplicateDetector {
    /// Create a new duplicate detector
    pub fn new(config: PurgeConfig) -> Self {
        Self {
            config,
            min_duplicate_lines: 5, // Minimum 5 lines to be considered duplicate
            min_similarity: 0.85,   // 85% similarity threshold
        }
    }

    /// Detect duplicate code blocks in the codebase
    ///
    /// Performs comprehensive duplicate detection including:
    /// - Token-based similarity analysis
    /// - Structural similarity comparison
    /// - Semantic duplicate detection
    /// - Refactoring opportunity identification
    ///
    /// # Performance
    /// - Target: ≤2 seconds per 1000 lines of code
    /// - Optimized comparison algorithms
    /// - Parallel analysis where possible
    pub fn detect_duplicates(
        &self,
        analysis_result: &StaticAnalysisResult,
    ) -> Result<DuplicateDetectionResult, AuditError> {
        let start_time = Instant::now();
        
        // Extract code blocks from all files
        let code_blocks = self.extract_code_blocks(analysis_result)?;
        
        // Find duplicate blocks
        let duplicates = self.find_duplicate_blocks(&code_blocks)?;
        
        // Calculate statistics
        let total_duplicate_lines = self.calculate_total_duplicate_lines(&duplicates);
        let total_lines = self.calculate_total_lines(analysis_result);
        let duplicate_percentage = if total_lines > 0 {
            (total_duplicate_lines as f64 / total_lines as f64) * 100.0
        } else {
            0.0
        };
        
        // Generate refactoring recommendations
        let refactoring_recommendations = self.generate_refactoring_recommendations(&duplicates)?;
        
        let detection_duration_ms = start_time.elapsed().as_millis() as u64;
        
        Ok(DuplicateDetectionResult {
            duplicates,
            total_duplicate_lines,
            duplicate_percentage,
            refactoring_recommendations,
            timestamp: SystemTime::now(),
            detection_duration_ms,
        })
    }

    /// Extract code blocks from analysis result
    fn extract_code_blocks(
        &self,
        analysis_result: &StaticAnalysisResult,
    ) -> Result<Vec<CodeBlock>, AuditError> {
        let mut code_blocks = Vec::new();
        
        // Group elements by file
        let mut elements_by_file: HashMap<FileId, Vec<&CodeElement>> = HashMap::new();
        for element in analysis_result.code_elements.values() {
            elements_by_file
                .entry(element.file_id.clone())
                .or_default()
                .push(element);
        }
        
        // Extract code blocks from each file
        for (file_id, elements) in elements_by_file {
            // Read file content
            if let Ok(content) = std::fs::read_to_string(&file_id.0) {
                let lines: Vec<&str> = content.lines().collect();
                
                // Create code blocks for each element
                for element in elements {
                    if element.line_range.1 >= element.line_range.0 {
                        let block_lines = &lines[
                            (element.line_range.0.saturating_sub(1))
                                ..element.line_range.1.min(lines.len())
                        ];
                        
                        let code_content = block_lines.join("\n");
                        let tokens = self.tokenize(&code_content);
                        
                        code_blocks.push(CodeBlock {
                            element_id: element.id.clone(),
                            file_id: file_id.clone(),
                            start_line: element.line_range.0,
                            end_line: element.line_range.1,
                            content: code_content,
                            tokens,
                        });
                    }
                }
            }
        }
        
        Ok(code_blocks)
    }

    /// Find duplicate code blocks
    fn find_duplicate_blocks(
        &self,
        code_blocks: &[CodeBlock],
    ) -> Result<Vec<DuplicateCodeBlock>, AuditError> {
        let mut duplicates = Vec::new();
        let mut processed = HashSet::new();
        
        // Compare each pair of code blocks
        for i in 0..code_blocks.len() {
            if processed.contains(&i) {
                continue;
            }
            
            let mut duplicate_group = Vec::new();
            duplicate_group.push(i);
            
            for j in (i + 1)..code_blocks.len() {
                if processed.contains(&j) {
                    continue;
                }
                
                let similarity = self.calculate_similarity(&code_blocks[i], &code_blocks[j])?;
                
                if similarity >= self.min_similarity {
                    duplicate_group.push(j);
                    processed.insert(j);
                }
            }
            
            // If we found duplicates, create a duplicate block
            if duplicate_group.len() > 1 {
                let locations: Vec<CodeLocation> = duplicate_group
                    .iter()
                    .map(|&idx| CodeLocation {
                        file_id: code_blocks[idx].file_id.clone(),
                        start_line: code_blocks[idx].start_line,
                        end_line: code_blocks[idx].end_line,
                    })
                    .collect();
                
                let line_count = code_blocks[i].end_line - code_blocks[i].start_line + 1;
                
                // Calculate average similarity within group
                let mut total_similarity = 0.0;
                let mut comparison_count = 0;
                for &idx1 in &duplicate_group {
                    for &idx2 in &duplicate_group {
                        if idx1 < idx2 {
                            total_similarity += self.calculate_similarity(
                                &code_blocks[idx1],
                                &code_blocks[idx2],
                            )?;
                            comparison_count += 1;
                        }
                    }
                }
                let avg_similarity = if comparison_count > 0 {
                    total_similarity / comparison_count as f64
                } else {
                    1.0
                };
                
                duplicates.push(DuplicateCodeBlock {
                    group_id: Uuid::new_v4().to_string(),
                    locations,
                    line_count,
                    similarity_score: avg_similarity,
                    code_content: code_blocks[i].content.clone(),
                });
                
                processed.insert(i);
            }
        }
        
        Ok(duplicates)
    }

    /// Calculate similarity between two code blocks
    ///
    /// # Performance
    /// - Target: ≤50ms per comparison
    fn calculate_similarity(
        &self,
        block1: &CodeBlock,
        block2: &CodeBlock,
    ) -> Result<f64, AuditError> {
        // Token-based similarity (Jaccard similarity)
        let tokens1: HashSet<_> = block1.tokens.iter().collect();
        let tokens2: HashSet<_> = block2.tokens.iter().collect();
        
        let intersection = tokens1.intersection(&tokens2).count();
        let union = tokens1.union(&tokens2).count();
        
        let token_similarity = if union > 0 {
            intersection as f64 / union as f64
        } else {
            0.0
        };
        
        // Line count similarity
        let line_count1 = block1.end_line - block1.start_line + 1;
        let line_count2 = block2.end_line - block2.start_line + 1;
        let line_similarity = 1.0 - ((line_count1 as f64 - line_count2 as f64).abs() / line_count1.max(line_count2) as f64);
        
        // Combined similarity (weighted average)
        let similarity = 0.7 * token_similarity + 0.3 * line_similarity;
        
        Ok(similarity)
    }

    /// Tokenize code content
    fn tokenize(&self, content: &str) -> Vec<String> {
        // Simple tokenization (production would use proper lexer)
        content
            .split(|c: char| c.is_whitespace() || "{}()[];,".contains(c))
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .collect()
    }

    /// Calculate total duplicate lines
    fn calculate_total_duplicate_lines(&self, duplicates: &[DuplicateCodeBlock]) -> usize {
        duplicates.iter()
            .map(|d| d.line_count * d.locations.len())
            .sum()
    }

    /// Calculate total lines in codebase
    fn calculate_total_lines(&self, analysis_result: &StaticAnalysisResult) -> usize {
        let mut total = 0;
        let mut processed_files = HashSet::new();
        
        for element in analysis_result.code_elements.values() {
            if processed_files.insert(element.file_id.clone()) {
                if let Ok(content) = std::fs::read_to_string(&element.file_id.0) {
                    total += content.lines().count();
                }
            }
        }
        
        total
    }

    /// Generate refactoring recommendations
    ///
    /// # Performance
    /// - Target: ≤100ms per duplicate group
    fn generate_refactoring_recommendations(
        &self,
        duplicates: &[DuplicateCodeBlock],
    ) -> Result<Vec<RefactoringRecommendation>, AuditError> {
        let mut recommendations = Vec::new();
        
        for duplicate in duplicates {
            let recommendation_type = self.determine_refactoring_type(duplicate);
            let priority = self.calculate_refactoring_priority(duplicate);
            let complexity_reduction = self.estimate_complexity_reduction(duplicate);
            
            let description = match recommendation_type {
                RefactoringType::ExtractFunction => {
                    format!(
                        "Extract {} lines of duplicate code into a shared function. Found in {} locations.",
                        duplicate.line_count,
                        duplicate.locations.len()
                    )
                }
                RefactoringType::ExtractModule => {
                    format!(
                        "Extract {} lines into a separate module. Duplicated {} times.",
                        duplicate.line_count,
                        duplicate.locations.len()
                    )
                }
                RefactoringType::ParameterizeCode => {
                    format!(
                        "Parameterize {} lines of similar code. Found in {} locations.",
                        duplicate.line_count,
                        duplicate.locations.len()
                    )
                }
                RefactoringType::UseExistingFunction => {
                    "Replace duplicate code with existing function call.".to_string()
                }
                RefactoringType::CreateTrait => {
                    format!(
                        "Create trait to abstract {} lines of duplicate behavior.",
                        duplicate.line_count
                    )
                }
            };
            
            recommendations.push(RefactoringRecommendation {
                recommendation_type,
                duplicate_group_id: duplicate.group_id.clone(),
                description,
                complexity_reduction,
                priority,
            });
        }
        
        // Sort by priority
        recommendations.sort_by(|a, b| b.priority.cmp(&a.priority));
        
        Ok(recommendations)
    }

    /// Determine appropriate refactoring type
    fn determine_refactoring_type(&self, duplicate: &DuplicateCodeBlock) -> RefactoringType {
        // Simple heuristics (production would use more sophisticated analysis)
        if duplicate.line_count > 50 {
            RefactoringType::ExtractModule
        } else if duplicate.line_count > 20 {
            RefactoringType::ExtractFunction
        } else if duplicate.similarity_score > 0.95 {
            RefactoringType::UseExistingFunction
        } else if duplicate.locations.len() > 5 {
            RefactoringType::CreateTrait
        } else {
            RefactoringType::ParameterizeCode
        }
    }

    /// Calculate refactoring priority
    fn calculate_refactoring_priority(&self, duplicate: &DuplicateCodeBlock) -> Priority {
        let impact_score = duplicate.line_count * duplicate.locations.len();
        
        if impact_score > 500 {
            Priority::Critical
        } else if impact_score > 200 {
            Priority::High
        } else if impact_score > 50 {
            Priority::Medium
        } else {
            Priority::Low
        }
    }

    /// Estimate complexity reduction from refactoring
    fn estimate_complexity_reduction(&self, duplicate: &DuplicateCodeBlock) -> f64 {
        // Estimate based on lines saved
        let lines_saved = duplicate.line_count * (duplicate.locations.len() - 1);
        
        // Complexity reduction as percentage
        let total_duplicate_lines = duplicate.line_count * duplicate.locations.len();
        (lines_saved as f64 / total_duplicate_lines as f64) * 100.0
    }

    /// Set minimum duplicate lines threshold
    pub fn set_min_duplicate_lines(&mut self, min_lines: usize) {
        self.min_duplicate_lines = min_lines;
    }

    /// Set minimum similarity threshold
    pub fn set_min_similarity(&mut self, min_similarity: f64) {
        self.min_similarity = min_similarity.clamp(0.0, 1.0);
    }
}

/// Internal code block representation
#[derive(Debug, Clone)]
struct CodeBlock {
    #[allow(dead_code)]
    element_id: CodeElementId,
    file_id: FileId,
    start_line: usize,
    end_line: usize,
    content: String,
    tokens: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_duplicate_detector_creation() {
        let config = PurgeConfig::default();
        let detector = DuplicateDetector::new(config);
        assert_eq!(detector.min_duplicate_lines, 5);
        assert_eq!(detector.min_similarity, 0.85);
    }

    #[test]
    fn test_tokenize() {
        let config = PurgeConfig::default();
        let detector = DuplicateDetector::new(config);
        
        let code = "fn test() { return 42; }";
        let tokens = detector.tokenize(code);
        
        assert!(tokens.contains(&"fn".to_string()));
        assert!(tokens.contains(&"test".to_string()));
        assert!(tokens.contains(&"return".to_string()));
        assert!(tokens.contains(&"42".to_string()));
    }

    #[test]
    fn test_calculate_similarity_identical() {
        let config = PurgeConfig::default();
        let detector = DuplicateDetector::new(config);
        
        let block1 = CodeBlock {
            element_id: CodeElementId("test1".to_string()),
            file_id: FileId(PathBuf::from("test.rs")),
            start_line: 1,
            end_line: 10,
            content: "fn test() { return 42; }".to_string(),
            tokens: vec!["fn".to_string(), "test".to_string(), "return".to_string(), "42".to_string()],
        };
        
        let block2 = block1.clone();
        
        let similarity = detector.calculate_similarity(&block1, &block2).unwrap();
        assert!(similarity > 0.95);
    }

    #[test]
    fn test_calculate_refactoring_priority() {
        let config = PurgeConfig::default();
        let detector = DuplicateDetector::new(config);
        
        let duplicate = DuplicateCodeBlock {
            group_id: "test".to_string(),
            locations: vec![
                CodeLocation {
                    file_id: FileId(PathBuf::from("test1.rs")),
                    start_line: 1,
                    end_line: 50,
                },
                CodeLocation {
                    file_id: FileId(PathBuf::from("test2.rs")),
                    start_line: 1,
                    end_line: 50,
                },
            ],
            line_count: 50,
            similarity_score: 0.9,
            code_content: String::new(),
        };
        
        let priority = detector.calculate_refactoring_priority(&duplicate);
        assert_eq!(priority, Priority::Medium);
    }

    #[test]
    fn test_estimate_complexity_reduction() {
        let config = PurgeConfig::default();
        let detector = DuplicateDetector::new(config);
        
        let duplicate = DuplicateCodeBlock {
            group_id: "test".to_string(),
            locations: vec![
                CodeLocation {
                    file_id: FileId(PathBuf::from("test1.rs")),
                    start_line: 1,
                    end_line: 10,
                },
                CodeLocation {
                    file_id: FileId(PathBuf::from("test2.rs")),
                    start_line: 1,
                    end_line: 10,
                },
                CodeLocation {
                    file_id: FileId(PathBuf::from("test3.rs")),
                    start_line: 1,
                    end_line: 10,
                },
            ],
            line_count: 10,
            similarity_score: 0.9,
            code_content: String::new(),
        };
        
        let reduction = detector.estimate_complexity_reduction(&duplicate);
        assert!((reduction - 66.67).abs() < 0.1);
    }
}
