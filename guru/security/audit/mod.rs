//! # Security Audit Module
//! 
//! Immutable audit logging and cryptographic trail management.

pub mod immutable_log;

pub use immutable_log::{
    ImmutableAuditLog,
    ImmutableLogEntry, 
    AuditLogError,
    AuditLevel,
};