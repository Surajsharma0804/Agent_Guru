//! Law Engine
//! Constitutional policy enforcement system.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

#[derive(Debug, Clone)]
pub struct PolicyContext {
    pub operation: String,
    pub agent_id: String,
    pub metadata: HashMap<String, String>,
}

pub trait Law: Send + Sync {
    fn name(&self) -> &str;
    fn validate(&self, context: &PolicyContext) -> Result<(), String>;
    fn enforce(&self, context: &PolicyContext) -> Result<(), String> {
        self.validate(context)
    }
}

pub struct LawEngine {
    laws: Arc<RwLock<Vec<Arc<dyn Law>>>>,
}

impl LawEngine {
    pub fn new() -> Self {
        Self {
            laws: Arc::new(RwLock::new(Vec::new())),
        }
    }

    pub fn register_law(&self, law: Arc<dyn Law>) {
        let mut laws = self.laws.write().unwrap();
        laws.push(law);
    }

    pub fn validate_all(&self, context: &PolicyContext) -> Result<(), Vec<String>> {
        let laws = self.laws.read().unwrap();
        let mut errors = Vec::new();

        for law in laws.iter() {
            if let Err(e) = law.validate(context) {
                errors.push(format!("{}: {}", law.name(), e));
            }
        }

        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }

    pub fn enforce_all(&self, context: &PolicyContext) -> Result<(), String> {
        match self.validate_all(context) {
            Ok(_) => Ok(()),
            Err(errors) => Err(format!("Policy violations: {}", errors.join("; "))),
        }
    }
}

impl Default for LawEngine {
    fn default() -> Self {
        Self::new()
    }
}
