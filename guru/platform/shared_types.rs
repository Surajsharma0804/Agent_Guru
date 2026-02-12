//! Shared platform types to eliminate duplication across OS implementations.
//!
//! This module provides common types used across Windows, macOS, and Linux
//! platform integrations, ensuring consistency and maintainability.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Process identifier (platform-agnostic)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ProcessId(pub u32);

/// Window identifier (platform-agnostic)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct WindowId(pub u64);

/// Process information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    pub process_id: ProcessId,
    pub name: String,
    pub executable_path: PathBuf,
    pub memory_usage_bytes: u64,
    pub cpu_usage_percent: f64,
}

/// Window information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowInfo {
    pub window_id: WindowId,
    pub title: String,
    pub process_id: ProcessId,
    pub workspace: Option<String>,
    pub is_visible: bool,
    pub is_minimized: bool,
}

/// Rectangle for window positioning
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rectangle {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

/// UI element for accessibility
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UIElement {
    pub element_id: String,
    pub element_type: String,
    pub label: Option<String>,
    pub value: Option<String>,
    pub is_enabled: bool,
}

/// File attributes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileAttributes {
    pub is_directory: bool,
    pub is_readonly: bool,
    pub is_hidden: bool,
    pub size_bytes: u64,
    pub modified_timestamp: u64,
}

/// Mouse button enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MouseButton {
    Left,
    Right,
    Middle,
    Other(u8),
}

/// Input event types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InputEvent {
    KeyPress { key_code: u32, modifiers: u32 },
    KeyRelease { key_code: u32, modifiers: u32 },
    MouseMove { x: i32, y: i32 },
    MouseClick { button: MouseButton, x: i32, y: i32 },
    MouseScroll { delta_x: i32, delta_y: i32 },
}

/// Window actions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WindowAction {
    Minimize { window_id: WindowId },
    Maximize { window_id: WindowId },
    Restore { window_id: WindowId },
    Close { window_id: WindowId },
    Focus { window_id: WindowId },
    Move { window_id: WindowId, x: i32, y: i32 },
    Resize { window_id: WindowId, width: u32, height: u32 },
}

/// File operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FileOperation {
    Read { path: PathBuf },
    Write { path: PathBuf, content: Vec<u8> },
    Delete { path: PathBuf },
    Move { from: PathBuf, to: PathBuf },
    Copy { from: PathBuf, to: PathBuf },
    CreateDirectory { path: PathBuf },
    SetPermissions { path: PathBuf, mode: u32 },
    SetOwnership { path: PathBuf, uid: u32, gid: u32 },
}

/// File operation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FileResult {
    Success,
    Error { reason: String },
    Data { content: Vec<u8> },
    Attributes { attrs: FileAttributes },
}

/// System settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SystemSetting {
    Volume { level: u8 },
    Brightness { level: u8 },
    DisplayResolution { width: u32, height: u32, refresh_rate: u32 },
    NetworkEnabled { enabled: bool },
    BluetoothEnabled { enabled: bool },
}
