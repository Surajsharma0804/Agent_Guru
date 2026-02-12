//! # Security Audit Module
//! 
//! Immutable audit logging and cryptographic trail management.

pub mod immutable_log;

// Re-export main types
pub use immutable_log::{
    ImmutableAuditLog as ImmutableLog,
    AuditLogError as AuditError,
};

// Placeholder types until full implementation
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogger {
    log: ImmutableLog,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub event_type: String,
    pub timestamp: u64,
    pub data: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AuditLevel {
    Info,
    Warning,
    Error,
    Critical,
}