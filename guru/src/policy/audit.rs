//! Audit Log
//! Immutable append-only audit trail.

use std::fs::{File, OpenOptions};
use std::io::{self, Write};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct AuditLog {
    path: String,
}

impl AuditLog {
    pub fn new(path: &str) -> Self {
        Self {
            path: path.to_string(),
        }
    }

    pub fn log(&self, event: &str, agent_id: &str, details: &str) -> io::Result<()> {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let entry = format!("[{}] {} | {} | {}\n", timestamp, agent_id, event, details);

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;

        file.write_all(entry.as_bytes())?;
        file.sync_all()?; // Ensure written to disk

        Ok(())
    }

    pub fn read_all(&self) -> io::Result<String> {
        std::fs::read_to_string(&self.path)
    }
}
