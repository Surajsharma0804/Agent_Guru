//! Linux Platform Bridge
//! Stub implementation.

use super::os_bridge::{OSBridge, MouseButton};

pub struct LinuxBridge;

impl LinuxBridge {
    pub fn new() -> Self {
        Self
    }
}

impl OSBridge for LinuxBridge {
    fn press_key(&self, _key_code: u16) -> Result<(), String> {
        Err("Linux input not implemented yet".to_string())
    }

    fn release_key(&self, _key_code: u16) -> Result<(), String> {
        Err("Linux input not implemented yet".to_string())
    }

    fn type_text(&self, _text: &str) -> Result<(), String> {
        Err("Linux input not implemented yet".to_string())
    }

    fn move_mouse(&self, _x: i32, _y: i32) -> Result<(), String> {
        Err("Linux input not implemented yet".to_string())
    }

    fn click_mouse(&self, _button: MouseButton) -> Result<(), String> {
        Err("Linux input not implemented yet".to_string())
    }

    fn get_clipboard_text(&self) -> Result<String, String> {
        // Could use `xclip` or `wl-paste` command
        use std::process::Command;
        let output = Command::new("xclip")
            .arg("-o")
            .output()
            .map_err(|_| "xclip not found".to_string())?;
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    fn set_clipboard_text(&self, text: &str) -> Result<(), String> {
        use std::process::{Command, Stdio};
        use std::io::Write;
        
        let mut child = Command::new("xclip")
            .arg("-i")
            .stdin(Stdio::piped())
            .spawn()
            .map_err(|_| "xclip not found".to_string())?;
            
        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(text.as_bytes()).map_err(|e| e.to_string())?;
        }
        
        child.wait().map_err(|e| e.to_string())?;
        Ok(())
    }

    fn exec_command(&self, cmd: &str, args: &[&str]) -> Result<String, String> {
        use std::process::Command;
        let output = Command::new(cmd)
            .args(args)
            .output()
            .map_err(|e| e.to_string())?;
            
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }
}
