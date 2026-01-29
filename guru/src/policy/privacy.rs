//! Privacy Law
//! Enforces encryption and data protection requirements.

use super::law_engine::{Law, PolicyContext};

pub struct PrivacyLaw;

impl Law for PrivacyLaw {
    fn name(&self) -> &str {
        "Privacy Law"
    }

    fn validate(&self, context: &PolicyContext) -> Result<(), String> {
        // Check for unencrypted sensitive data operations
        if (context.operation.contains("store_sensitive") || context.operation.contains("transmit_sensitive")) 
            && !context.metadata.get("encrypted").map(|v| v == "true").unwrap_or(false) {
            return Err("Sensitive data must be encrypted".to_string());
        }

        // Check for PII handling
        if context.operation.contains("pii") 
            && !context.metadata.get("anonymized").map(|v| v == "true").unwrap_or(false) {
            return Err("PII must be anonymized or encrypted".to_string());
        }

        Ok(())
    }
}
