pub mod com;
pub mod uia;
pub mod ffi_bridge;

pub use ffi_bridge::WindowsBridge;

// Re-export existing FFI (from Task 8)
// assuming we had some. Or we overwrite?
// Task 8 had `windows.rs`. It was NOT a folder `windows/mod.rs`.
// It was `platform/windows.rs`.
// I need to check `platform` structure.
// If `platform/windows.rs` exists, I cannot make `platform/windows/mod.rs` without moving code.
// I will start by checking if `platform/windows.rs` is a file.
