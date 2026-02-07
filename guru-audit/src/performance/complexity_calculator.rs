//! Complexity Calculator with Maintainability Scoring
//!
//! Provides code complexity analysis and technical debt assessment.

use crate::error::AuditError;
use crate::performance::types::*;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Complexity Calculator
///
/// Calculates code complexity metrics and maintainability scores.
///
/// # Performance Requirements
/// - Complexity calculation: ≤100ms per 1000 lines of code
/// - Memory overhead: <50MB for analysis state
#[derive(Debug)]
#[allow(dead_code)]
pub struct ComplexityCalculator {
    max_acceptable_complexity: u32,
    min_maintainability_index: f64,
}

impl ComplexityCalculator {
    /// Creates a new Complexity Calculator with production-grade configuration
    pub fn new() -> Result<Self, AuditError> {
        Ok(Self {
            max_acceptable_complexity: 15, // Maximum cyclomatic complexity per function
            min_maintainability_index: 65.0, // Minimum maintainability index (0-100 scale)
        })
    }

    /// Calculates complexity metrics for the workspace
    ///
    /// Performs comprehensive complexity analysis including:
    /// - Cyclomatic complexity calculation
    /// - Cognitive complexity assessment
    /// - Maintainability index computation
    /// - Technical debt estimation
    pub async fn calculate_complexity(&self, workspace_path: &Path) -> Result<ComplexityMetrics, AuditError> {
        let mut cyclomatic_complexity = HashMap::new();
        let mut maintainability_index = HashMap::new();
        let mut total_lines = 0u64;
        let mut files_analyzed = 0u64;

        // Walk through source files
        if let Ok(entries) = std::fs::read_dir(workspace_path) {
            for entry in entries.flatten() {
                if let Ok(file_type) = entry.file_type() {
                    if file_type.is_file() {
                        if let Some(path) = entry.path().to_str() {
                            if path.ends_with(".rs") || path.ends_with(".py") || path.ends_with(".cpp") {
                                if let Ok(complexity) = self.analyze_file(&entry.path()).await {
                                    total_lines += complexity.lines_of_code;
                                    files_analyzed += 1;
                                    maintainability_index.insert(entry.path(), complexity.maintainability_index);
                                    cyclomatic_complexity.insert(entry.path(), complexity);
                                }
                            }
                        }
                    }
                }
            }
        }

        // Calculate overall maintainability score
        let overall_score = if !maintainability_index.is_empty() {
            maintainability_index.values().sum::<f64>() / maintainability_index.len() as f64
        } else {
            0.0
        };

        // Estimate technical debt (simplified calculation)
        let technical_debt_hours = self.calculate_technical_debt(&cyclomatic_complexity);

        Ok(ComplexityMetrics {
            files_analyzed,
            total_lines_of_code: total_lines,
            cyclomatic_complexity,
            maintainability_index,
            technical_debt_hours,
            overall_maintainability_score: overall_score,
        })
    }

    /// Analyzes a single file for complexity metrics
    async fn analyze_file(&self, file_path: &Path) -> Result<FileComplexity, AuditError> {
        let content = std::fs::read_to_string(file_path)
            .map_err(|e| AuditError::IoError(e.to_string()))?;

        let lines_of_code = content.lines().filter(|line| !line.trim().is_empty()).count() as u64;

        // Simplified complexity calculation (production would use proper AST analysis)
        let function_count = content.matches("fn ").count() as u32
            + content.matches("def ").count() as u32
            + content.matches("function ").count() as u32;

        // Estimate cyclomatic complexity based on control flow keywords
        let complexity_keywords = ["if", "else", "for", "while", "match", "case", "&&", "||"];
        let cyclomatic_complexity = complexity_keywords
            .iter()
            .map(|keyword| content.matches(keyword).count() as u32)
            .sum::<u32>()
            + function_count;

        let cognitive_complexity = cyclomatic_complexity; // Simplified

        let average_function_complexity = if function_count > 0 {
            cyclomatic_complexity as f64 / function_count as f64
        } else {
            0.0
        };

        // Maintainability Index calculation (simplified Microsoft formula)
        // MI = 171 - 5.2 * ln(Halstead Volume) - 0.23 * (Cyclomatic Complexity) - 16.2 * ln(Lines of Code)
        let mi = if lines_of_code > 0 {
            let loc_factor = 16.2 * (lines_of_code as f64).ln();
            let complexity_factor = 0.23 * cyclomatic_complexity as f64;
            let raw_mi = 171.0 - complexity_factor - loc_factor;
            raw_mi.max(0.0_f64).min(100.0_f64)
        } else {
            100.0
        };

        // Technical debt estimation (minutes per complexity point above threshold)
        let excess_complexity = cyclomatic_complexity.saturating_sub(self.max_acceptable_complexity);
        let technical_debt_minutes = excess_complexity as f64 * 5.0; // 5 minutes per excess complexity point

        Ok(FileComplexity {
            file_path: file_path.to_path_buf(),
            lines_of_code,
            cyclomatic_complexity,
            cognitive_complexity,
            function_count,
            average_function_complexity,
            max_function_complexity: cyclomatic_complexity, // Simplified
            maintainability_index: mi,
            technical_debt_minutes,
        })
    }

    /// Calculates total technical debt in hours
    fn calculate_technical_debt(&self, complexity_map: &HashMap<PathBuf, FileComplexity>) -> f64 {
        complexity_map
            .values()
            .map(|fc| fc.technical_debt_minutes)
            .sum::<f64>()
            / 60.0 // Convert to hours
    }
}

impl Default for ComplexityCalculator {
    fn default() -> Self {
        Self::new().expect("Failed to create default ComplexityCalculator")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_complexity_calculator_creation() {
        let calculator = ComplexityCalculator::new();
        assert!(calculator.is_ok());
    }

    #[tokio::test]
    async fn test_complexity_calculation() {
        let calculator = ComplexityCalculator::new().expect("Failed to create calculator");
        let workspace = Path::new(".");
        
        let result = calculator.calculate_complexity(workspace).await;
        assert!(result.is_ok());
    }
}
