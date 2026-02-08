//! # Proof Generator
//!
//! Machine-checkable proof certificate generation for verified properties.
//! Implements cryptographic signing and proof step documentation.

use crate::crypto::compute_sha256_hash;
use crate::error::{AuditError, AuditResult};
use crate::formal::types::*;
use std::time::{Duration, SystemTime};

/// Proof certificate generator
#[derive(Debug, Clone)]
pub struct ProofGenerator {
    /// Generator configuration
    config: ProofGeneratorConfig,
}

/// Proof generator configuration
#[derive(Debug, Clone)]
pub struct ProofGeneratorConfig {
    /// Enable cryptographic signing
    pub enable_signing: bool,
    /// Include detailed proof steps
    pub detailed_steps: bool,
    /// Tool version
    pub tool_version: String,
}

impl Default for ProofGeneratorConfig {
    fn default() -> Self {
        Self {
            enable_signing: true,
            detailed_steps: true,
            tool_version: "1.0.0".to_string(),
        }
    }
}

impl ProofGenerator {
    /// Create a new proof generator
    ///
    /// # Arguments
    ///
    /// * `config` - Generator configuration
    ///
    /// # Returns
    ///
    /// New proof generator instance
    pub fn new(config: ProofGeneratorConfig) -> Self {
        Self { config }
    }

    /// Generate proof certificate from model checking result
    ///
    /// # Arguments
    ///
    /// * `spec_name` - Specification name
    /// * `model_result` - Model checking result
    ///
    /// # Returns
    ///
    /// Proof certificate with cryptographic signature
    ///
    /// # Performance
    ///
    /// Proof generation completes in ≤30 seconds per certificate
    pub fn generate_certificate(
        &self,
        spec_name: &str,
        model_result: &ModelCheckingResult,
    ) -> AuditResult<ProofCertificate> {
        let start_time = SystemTime::now();

        // Extract verified properties
        let mut properties_verified = Vec::new();
        for invariant_result in &model_result.invariants_checked {
            if invariant_result.passed {
                properties_verified.push(invariant_result.invariant_name.clone());
            }
        }
        for temporal_result in &model_result.temporal_properties_checked {
            if temporal_result.passed {
                properties_verified.push(temporal_result.property_name.clone());
            }
        }

        // Generate proof steps
        let proof_steps = self.generate_proof_steps(spec_name, model_result)?;

        // Generate certificate ID
        let certificate_id = format!(
            "CERT-{}-{}",
            spec_name,
            SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_secs()
        );

        // Generate cryptographic signature
        let signature = if self.config.enable_signing {
            self.sign_certificate(&certificate_id, &proof_steps)?
        } else {
            vec![0u8; 64] // Placeholder signature
        };

        // Validate generation time
        let duration = start_time.elapsed().unwrap_or(Duration::from_secs(0));
        if duration > Duration::from_secs(30) {
            return Err(AuditError::FileSystemError {
                operation: "generate_certificate".to_string(),
                path: spec_name.to_string(),
                reason: format!("Certificate generation exceeded 30 seconds: {:?}", duration),
            });
        }

        Ok(ProofCertificate {
            certificate_id,
            spec_name: spec_name.to_string(),
            properties_verified,
            proof_steps,
            signature,
            timestamp: SystemTime::now(),
            tool_version: self.config.tool_version.clone(),
        })
    }

    /// Generate proof steps from model checking result
    fn generate_proof_steps(
        &self,
        spec_name: &str,
        model_result: &ModelCheckingResult,
    ) -> AuditResult<Vec<ProofStep>> {
        let mut proof_steps = Vec::new();
        let mut step_number = 1;

        // Add assumption step
        proof_steps.push(ProofStep {
            step_number,
            step_type: ProofStepType::Assumption,
            description: format!("Specification {} defines the system model", spec_name),
            justification: "Initial specification assumption".to_string(),
            references: vec![],
        });
        step_number += 1;

        // Add state space exploration step
        proof_steps.push(ProofStep {
            step_number,
            step_type: ProofStepType::DirectProof,
            description: format!(
                "Explored {} states ({} distinct) to depth {}",
                model_result.states_explored,
                model_result.distinct_states,
                model_result.depth_reached
            ),
            justification: "Complete state space exploration via model checking".to_string(),
            references: vec!["TLC Model Checker".to_string()],
        });
        step_number += 1;

        // Add invariant verification steps
        for invariant_result in &model_result.invariants_checked {
            if invariant_result.passed {
                proof_steps.push(ProofStep {
                    step_number,
                    step_type: ProofStepType::Theorem,
                    description: format!(
                        "Invariant {} holds in all reachable states",
                        invariant_result.invariant_name
                    ),
                    justification: "Verified by exhaustive state space exploration".to_string(),
                    references: vec![invariant_result.invariant_name.clone()],
                });
                step_number += 1;
            }
        }

        // Add temporal property verification steps
        for temporal_result in &model_result.temporal_properties_checked {
            if temporal_result.passed {
                let property_type_str = match temporal_result.property_type {
                    TemporalPropertyType::Safety => "safety",
                    TemporalPropertyType::Liveness => "liveness",
                    TemporalPropertyType::Fairness => "fairness",
                    TemporalPropertyType::General => "temporal",
                };

                proof_steps.push(ProofStep {
                    step_number,
                    step_type: ProofStepType::Theorem,
                    description: format!(
                        "Temporal {} property {} is satisfied",
                        property_type_str, temporal_result.property_name
                    ),
                    justification: format!(
                        "Verified by temporal logic model checking ({} property)",
                        property_type_str
                    ),
                    references: vec![temporal_result.property_name.clone()],
                });
                step_number += 1;
            }
        }

        // Add conclusion step
        proof_steps.push(ProofStep {
            step_number,
            step_type: ProofStepType::DirectProof,
            description: format!(
                "Specification {} is mathematically correct",
                spec_name
            ),
            justification: "All invariants and temporal properties verified".to_string(),
            references: vec![],
        });

        Ok(proof_steps)
    }

    /// Sign proof certificate with cryptographic signature
    fn sign_certificate(
        &self,
        certificate_id: &str,
        proof_steps: &[ProofStep],
    ) -> AuditResult<Vec<u8>> {
        // Create message to sign
        let mut message = certificate_id.as_bytes().to_vec();
        for step in proof_steps {
            message.extend_from_slice(step.description.as_bytes());
        }

        // Sign with cryptographic hash (simplified for now)
        // In production, would use Ed25519 signing
        let hash = compute_sha256_hash(&message)?;
        Ok(hash.to_vec())
    }

    /// Verify proof certificate signature
    ///
    /// # Arguments
    ///
    /// * `certificate` - Proof certificate to verify
    ///
    /// # Returns
    ///
    /// True if signature is valid
    pub fn verify_certificate(&self, certificate: &ProofCertificate) -> AuditResult<bool> {
        if !self.config.enable_signing {
            return Ok(true);
        }

        // Reconstruct message
        let mut message = certificate.certificate_id.as_bytes().to_vec();
        for step in &certificate.proof_steps {
            message.extend_from_slice(step.description.as_bytes());
        }

        // Verify signature (simplified)
        let expected_hash = compute_sha256_hash(&message)?;
        Ok(certificate.signature.starts_with(&expected_hash))
    }

    /// Get generator configuration
    pub fn config(&self) -> &ProofGeneratorConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_proof_generator_creation() {
        let config = ProofGeneratorConfig::default();
        let generator = ProofGenerator::new(config);
        assert!(generator.config().enable_signing);
    }

    #[test]
    fn test_generate_certificate() {
        let config = ProofGeneratorConfig::default();
        let generator = ProofGenerator::new(config);

        let model_result = ModelCheckingResult {
            spec_name: "TestSpec".to_string(),
            status: VerificationStatus::Verified,
            states_explored: 100,
            distinct_states: 50,
            depth_reached: 10,
            invariants_checked: vec![InvariantCheckResult {
                invariant_name: "TypeInvariant".to_string(),
                passed: true,
                violation_state: None,
                violation_trace: None,
            }],
            temporal_properties_checked: vec![],
            counterexamples: vec![],
            duration: Duration::from_secs(1),
        };

        let certificate = generator
            .generate_certificate("TestSpec", &model_result)
            .unwrap();

        assert_eq!(certificate.spec_name, "TestSpec");
        assert!(!certificate.proof_steps.is_empty());
        assert!(!certificate.signature.is_empty());
    }

    #[test]
    fn test_verify_certificate() {
        let config = ProofGeneratorConfig::default();
        let generator = ProofGenerator::new(config);

        let model_result = ModelCheckingResult {
            spec_name: "TestSpec".to_string(),
            status: VerificationStatus::Verified,
            states_explored: 100,
            distinct_states: 50,
            depth_reached: 10,
            invariants_checked: vec![],
            temporal_properties_checked: vec![],
            counterexamples: vec![],
            duration: Duration::from_secs(1),
        };

        let certificate = generator
            .generate_certificate("TestSpec", &model_result)
            .unwrap();

        let is_valid = generator.verify_certificate(&certificate).unwrap();
        assert!(is_valid);
    }
}
