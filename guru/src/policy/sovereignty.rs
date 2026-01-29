//! Sovereignty Law
//! Enforces no external dependencies and offline-first operation.

use super::law_engine::{Law, PolicyContext};

pub struct SovereigntyLaw;

impl Law for SovereigntyLaw {
    fn name(&self) -> &str {
        "Sovereignty Law"
    }

    fn validate(&self, context: &PolicyContext) -> Result<(), String> {
        // Check for network operations
        if (context.operation.contains("network") || context.operation.contains("http")) 
            && !context.metadata.get("user_consent").map(|v| v == "true").unwrap_or(false) {
            return Err("Network operation requires explicit user consent".to_string());
        }

        // Check for external dependencies (runtime check)
        if context.operation.contains("external_call") {
            return Err("External dependencies are prohibited".to_string());
        }

        Ok(())
    }
}
