//! Structured Logger
//! Logging system with multiple severity levels.

use std::io::{self, Write};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum LogLevel {
    Debug,
    Info,
    Warning,
    Error,
    Critical,
}

pub struct Logger {
    min_level: LogLevel,
}

impl Logger {
    pub fn new(min_level: LogLevel) -> Self {
        Self { min_level }
    }

    pub fn log(&self, level: LogLevel, message: &str) {
        if level >= self.min_level {
            let level_str = match level {
                LogLevel::Debug => "DEBUG",
                LogLevel::Info => "INFO",
                LogLevel::Warning => "WARN",
                LogLevel::Error => "ERROR",
                LogLevel::Critical => "CRIT",
            };

            let timestamp = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs();

            let log_line = format!("[{}] [{}] {}\n", timestamp, level_str, message);
            
            // Write to stderr for errors, stdout otherwise
            if level >= LogLevel::Error {
                let _ = io::stderr().write_all(log_line.as_bytes());
            } else {
                let _ = io::stdout().write_all(log_line.as_bytes());
            }
        }
    }

    pub fn debug(&self, message: &str) {
        self.log(LogLevel::Debug, message);
    }

    pub fn info(&self, message: &str) {
        self.log(LogLevel::Info, message);
    }

    pub fn warning(&self, message: &str) {
        self.log(LogLevel::Warning, message);
    }

    pub fn error(&self, message: &str) {
        self.log(LogLevel::Error, message);
    }

    pub fn critical(&self, message: &str) {
        self.log(LogLevel::Critical, message);
    }
}
