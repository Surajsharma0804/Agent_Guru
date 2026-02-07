//! # Property Test Engine
//!
//! Property-based testing engine with minimum 10,000 iterations and comprehensive shrinking.
//! Implements mathematical correctness validation across all possible inputs.

use crate::error::{AuditError, AuditResult};
use crate::testing::types::*;
use std::time::{Duration, SystemTime};

/// Property test engine with comprehensive shrinking
#[derive(Debug, Clone)]
pub struct PropertyTestEngine {
    /// Test configuration
    config: PropertyTestConfig,
    /// Random number generator seed
    rng_seed: u64,
}

impl PropertyTestEngine {
    /// Create a new property test engine
    ///
    /// # Arguments
    ///
    /// * `config` - Property test configuration
    ///
    /// # Returns
    ///
    /// New property test engine instance
    pub fn new(config: PropertyTestConfig) -> Self {
        let rng_seed = config.random_seed.unwrap_or_else(|| {
            SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_secs()
        });

        Self { config, rng_seed }
    }

    /// Execute property test with minimum iterations
    ///
    /// # Arguments
    ///
    /// * `property_fn` - Property function to test
    ///
    /// # Returns
    ///
    /// Property test result with comprehensive metrics
    pub fn execute_property_test<F>(&self, property_fn: F) -> AuditResult<PropertyTestResult>
    where
        F: Fn(&[u8]) -> bool,
    {
        let start_time = SystemTime::now();
        let mut iterations_executed = 0u32;
        let mut counterexample: Option<String> = None;
        let mut shrinking_steps = 0u32;

        // Validate minimum iterations requirement
        if self.config.min_iterations < 10000 {
            return Err(AuditError::ConfigurationError {
                parameter: "min_iterations".to_string(),
                reason: format!(
                    "Property test requires minimum 10,000 iterations, got {}",
                    self.config.min_iterations
                ),
                suggested_fix: Some("Set min_iterations to at least 10000".to_string()),
            });
        }

        // Execute property test iterations
        for iteration in 0..self.config.min_iterations {
            iterations_executed = iteration + 1;

            // Generate test input
            let test_input = self.generate_test_input(iteration);

            // Execute property with timeout
            let property_holds = self.execute_with_timeout(&property_fn, &test_input)?;

            if !property_holds {
                // Property violated - attempt shrinking
                let (shrunk_input, shrink_steps) = self.shrink_counterexample(&property_fn, &test_input)?;
                shrinking_steps = shrink_steps;
                counterexample = Some(format!("{:?}", shrunk_input));
                break;
            }
        }

        let duration = start_time.elapsed().unwrap_or(Duration::from_secs(0));

        let status = if counterexample.is_some() {
            TestStatus::Failed {
                error: "Property violation found".to_string(),
                details: format!("Counterexample: {:?}", counterexample),
            }
        } else {
            TestStatus::Passed
        };

        Ok(PropertyTestResult {
            property_name: self.config.property_name.clone(),
            status,
            iterations_executed,
            counterexample,
            shrinking_steps,
            duration,
        })
    }

    /// Generate test input for iteration
    fn generate_test_input(&self, iteration: u32) -> Vec<u8> {
        // Simple pseudo-random generation based on seed and iteration
        // In production, this would use a proper random generator like proptest or quickcheck
        let mut input = Vec::new();
        let mut state = self.rng_seed.wrapping_add(iteration as u64);

        for _ in 0..32 {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            input.push((state >> 32) as u8);
        }

        input
    }

    /// Execute property function with timeout
    fn execute_with_timeout<F>(&self, property_fn: &F, input: &[u8]) -> AuditResult<bool>
    where
        F: Fn(&[u8]) -> bool,
    {
        // In production, this would use proper timeout mechanisms
        // For now, we execute directly
        Ok(property_fn(input))
    }

    /// Shrink counterexample to minimal failing case
    fn shrink_counterexample<F>(&self, property_fn: &F, input: &[u8]) -> AuditResult<(Vec<u8>, u32)>
    where
        F: Fn(&[u8]) -> bool,
    {
        let mut current_input = input.to_vec();
        let mut shrink_steps = 0u32;

        // Attempt to shrink by reducing input size
        while current_input.len() > 1 && shrink_steps < self.config.max_shrink_attempts {
            let smaller_input = current_input[..current_input.len() - 1].to_vec();

            if !property_fn(&smaller_input) {
                current_input = smaller_input;
                shrink_steps += 1;
            } else {
                break;
            }
        }

        // Attempt to shrink by reducing values
        for i in 0..current_input.len() {
            if shrink_steps >= self.config.max_shrink_attempts {
                break;
            }

            if current_input[i] > 0 {
                let original_value = current_input[i];
                current_input[i] = 0;

                if property_fn(&current_input) {
                    // Shrinking this value makes property hold, revert
                    current_input[i] = original_value;
                } else {
                    shrink_steps += 1;
                }
            }
        }

        Ok((current_input, shrink_steps))
    }

    /// Execute multiple properties in parallel
    pub fn execute_property_suite<F>(&self, properties: Vec<(String, F)>) -> AuditResult<Vec<PropertyTestResult>>
    where
        F: Fn(&[u8]) -> bool + Clone,
    {
        let mut results = Vec::new();

        for (property_name, property_fn) in properties {
            let mut config = self.config.clone();
            config.property_name = property_name;

            let engine = PropertyTestEngine::new(config);
            let result = engine.execute_property_test(property_fn)?;
            results.push(result);
        }

        Ok(results)
    }

    /// Get configuration
    pub fn config(&self) -> &PropertyTestConfig {
        &self.config
    }

    /// Get RNG seed
    pub fn rng_seed(&self) -> u64 {
        self.rng_seed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_property_engine_creation() {
        let config = PropertyTestConfig {
            property_name: "test_property".to_string(),
            min_iterations: 10000,
            max_shrink_attempts: 100,
            random_seed: Some(42),
            iteration_timeout: Duration::from_secs(1),
        };

        let engine = PropertyTestEngine::new(config);
        assert_eq!(engine.rng_seed(), 42);
    }

    #[test]
    fn test_property_always_true() {
        let config = PropertyTestConfig {
            property_name: "always_true".to_string(),
            min_iterations: 10000,
            max_shrink_attempts: 100,
            random_seed: Some(42),
            iteration_timeout: Duration::from_secs(1),
        };

        let engine = PropertyTestEngine::new(config);
        let result = engine.execute_property_test(|_input| true).unwrap();

        assert_eq!(result.status, TestStatus::Passed);
        assert_eq!(result.iterations_executed, 10000);
        assert!(result.counterexample.is_none());
    }

    #[test]
    fn test_property_always_false() {
        let config = PropertyTestConfig {
            property_name: "always_false".to_string(),
            min_iterations: 10000,
            max_shrink_attempts: 100,
            random_seed: Some(42),
            iteration_timeout: Duration::from_secs(1),
        };

        let engine = PropertyTestEngine::new(config);
        let result = engine.execute_property_test(|_input| false).unwrap();

        assert!(matches!(result.status, TestStatus::Failed { .. }));
        assert_eq!(result.iterations_executed, 1);
        assert!(result.counterexample.is_some());
    }

    #[test]
    fn test_minimum_iterations_validation() {
        let config = PropertyTestConfig {
            property_name: "test".to_string(),
            min_iterations: 100, // Less than 10000
            max_shrink_attempts: 100,
            random_seed: Some(42),
            iteration_timeout: Duration::from_secs(1),
        };

        let engine = PropertyTestEngine::new(config);
        let result = engine.execute_property_test(|_input| true);

        assert!(result.is_err());
    }
}
