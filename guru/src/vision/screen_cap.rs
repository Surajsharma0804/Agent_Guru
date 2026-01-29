//! Screen Capture
//! Sovereign implementation of screen grabbing.

use super::image_processing::ImageBuffer;

pub trait ScreenCapturer {
    fn capture_screen(&self) -> Result<ImageBuffer, String>;
}

#[cfg(target_os = "windows")]
pub struct WindowsCapturer;

#[cfg(target_os = "windows")]
impl ScreenCapturer for WindowsCapturer {
    fn capture_screen(&self) -> Result<ImageBuffer, String> {
        // We need to access crate::platform::windows::WindowsBridge
        // Ideally WindowsBridge should be used here.
        use crate::platform::windows::WindowsBridge;
        let bridge = WindowsBridge::new();
        let (w, h, pixels) = bridge.capture_full_screen()?;
        Ok(ImageBuffer::new(w, h, pixels))
    }
}

#[cfg(target_os = "linux")]
pub struct LinuxCapturer;

#[cfg(target_os = "linux")]
impl LinuxCapturer {
    pub fn new() -> Self { Self }
}

#[cfg(target_os = "linux")]
impl ScreenCapturer for LinuxCapturer {
    fn capture_screen(&self) -> Result<ImageBuffer, String> {
        Err("Linux capture not implemented".to_string())
    }
}
