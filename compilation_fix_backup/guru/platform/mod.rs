//! # Platform Integration Module
//! 
//! Production-grade OS integration and hardware abstraction.
//! Provides cross-platform system control, application automation, and native API integration.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(missing_docs, dead_code)]

pub mod windows;
pub mod macos;
pub mod linux;

#[cfg(test)]
pub mod property_tests;

// Re-export platform-specific types for convenience
pub use windows::{WindowsControlBridge, WindowsError, WindowsPerformanceMetrics};
pub use macos::{MacOSControlBridge, MacOSError, MacOSPerformanceMetrics};
pub use linux::{LinuxControlBridge, LinuxError, LinuxPerformanceMetrics};

use std::time::SystemTime;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Cross-platform error types
#[derive(Error, Debug, Clone, PartialEq)]
pub enum PlatformError {
    #[error("Windows error: {0}")]
    Windows(#[from] WindowsError),
    
    #[error("macOS error: {0}")]
    MacOS(#[from] MacOSError),
    
    #[error("Linux error: {0}")]
    Linux(#[from] LinuxError),
    
    #[error("Unsupported platform: {platform}")]
    UnsupportedPlatform { platform: String },
    
    #[error("Platform detection failed")]
    PlatformDetectionFailed,
}

/// Supported operating system platforms
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum Platform {
    Windows,
    MacOS,
    Linux,
    Unknown,
}

/// Cross-platform performance metrics
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CrossPlatformMetrics {
    pub platform: Platform,
    pub application_launch_time_ms: u64,
    pub window_operation_time_ms: u64,
    pub file_operation_time_ms: u64,
    pub event_injection_time_ms: u64,
    pub ui_tree_extraction_time_ms: u64,
    pub total_operations: u64,
    pub successful_operations: u64,
    pub failed_operations: u64,
    pub average_response_time_ms: f64,
    pub last_updated: SystemTime,
}

/// Detect the current platform
pub fn detect_platform() -> Platform {
    #[cfg(target_os = "windows")]
    return Platform::Windows;
    
    #[cfg(target_os = "macos")]
    return Platform::MacOS;
    
    #[cfg(target_os = "linux")]
    return Platform::Linux;
    
    #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
    return Platform::Unknown;
}

/// Get platform-specific performance requirements
pub fn get_platform_performance_requirements(platform: &Platform) -> CrossPlatformMetrics {
    match platform {
        Platform::Windows => CrossPlatformMetrics {
            platform: platform.clone(),
            application_launch_time_ms: 2000, // ≤ 2 seconds
            window_operation_time_ms: 100,    // ≤ 100ms
            file_operation_time_ms: 500,      // ≤ 500ms
            event_injection_time_ms: 10,      // ≤ 10ms
            ui_tree_extraction_time_ms: 200,  // ≤ 200ms
            total_operations: 0,
            successful_operations: 0,
            failed_operations: 0,
            average_response_time_ms: 0.0,
            last_updated: SystemTime::now(),
        },
        Platform::MacOS => CrossPlatformMetrics {
            platform: platform.clone(),
            application_launch_time_ms: 1500, // ≤ 1.5 seconds
            window_operation_time_ms: 80,     // ≤ 80ms
            file_operation_time_ms: 300,      // ≤ 300ms
            event_injection_time_ms: 8,       // ≤ 8ms
            ui_tree_extraction_time_ms: 150,  // ≤ 150ms
            total_operations: 0,
            successful_operations: 0,
            failed_operations: 0,
            average_response_time_ms: 0.0,
            last_updated: SystemTime::now(),
        },
        Platform::Linux => CrossPlatformMetrics {
            platform: platform.clone(),
            application_launch_time_ms: 1000, // ≤ 1 second
            window_operation_time_ms: 50,     // ≤ 50ms
            file_operation_time_ms: 200,      // ≤ 200ms
            event_injection_time_ms: 5,       // ≤ 5ms
            ui_tree_extraction_time_ms: 100,  // ≤ 100ms
            total_operations: 0,
            successful_operations: 0,
            failed_operations: 0,
            average_response_time_ms: 0.0,
            last_updated: SystemTime::now(),
        },
        Platform::Unknown => CrossPlatformMetrics {
            platform: platform.clone(),
            application_launch_time_ms: 5000, // Conservative fallback
            window_operation_time_ms: 500,
            file_operation_time_ms: 1000,
            event_injection_time_ms: 50,
            ui_tree_extraction_time_ms: 1000,
            total_operations: 0,
            successful_operations: 0,
            failed_operations: 0,
            average_response_time_ms: 0.0,
            last_updated: SystemTime::now(),
        },
    }
}