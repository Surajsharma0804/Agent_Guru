//! OS Bridge Trait
//! Abstract interface for operating system interactions.

pub trait OSBridge: Send + Sync {
    // Input Simulation
    fn press_key(&self, key_code: u16) -> Result<(), String>;
    fn release_key(&self, key_code: u16) -> Result<(), String>;
    fn type_text(&self, text: &str) -> Result<(), String>;
    fn move_mouse(&self, x: i32, y: i32) -> Result<(), String>;
    fn click_mouse(&self, button: MouseButton) -> Result<(), String>;
    
    // Clipboard
    fn get_clipboard_text(&self) -> Result<String, String>;
    fn set_clipboard_text(&self, text: &str) -> Result<(), String>;
    
    // Process
    fn exec_command(&self, cmd: &str, args: &[&str]) -> Result<String, String>;
}

#[derive(Debug, Clone, Copy)]
pub enum MouseButton {
    Left,
    Right,
    Middle,
}
