//! Windows Platform Bridge
//! Direct FFI to User32.dll and Kernel32.dll.

use super::os_bridge::{OSBridge, MouseButton};
use std::ffi::{c_void, CString};
use std::ptr::null_mut;

// Minimal FFI definitions
#[link(name = "user32")]
unsafe extern "system" {
    fn SendInput(cInputs: u32, pInputs: *mut INPUT, cbSize: i32) -> u32;
    fn GetSystemMetrics(nIndex: i32) -> i32;
    
    // Clipboard
    fn OpenClipboard(hWnd: *mut c_void) -> i32;
    fn CloseClipboard() -> i32;
    fn EmptyClipboard() -> i32;
    fn SetClipboardData(uFormat: u32, hMem: *mut c_void) -> *mut c_void;
    fn GetClipboardData(uFormat: u32) -> *mut c_void;
    fn IsClipboardFormatAvailable(format: u32) -> i32;
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GlobalAlloc(uFlags: u32, dwBytes: usize) -> *mut c_void;
    fn GlobalLock(hMem: *mut c_void) -> *mut c_void;
    fn GlobalUnlock(hMem: *mut c_void) -> i32;
    fn GlobalFree(hMem: *mut c_void) -> *mut c_void;
}

// Structs
#[repr(C)]
struct INPUT {
    type_: u32, // 0=MOUSE, 1=KEYBOARD
    u: INPUT_UNION,
}

#[repr(C)]
union INPUT_UNION {
    mi: MOUSEINPUT,
    ki: KEYBDINPUT,
    hi: HARDWAREINPUT,
}

#[derive(Clone, Copy)]
#[repr(C)]
struct MOUSEINPUT {
    dx: i32,
    dy: i32,
    mouseData: u32,
    dwFlags: u32,
    time: u32,
    dwExtraInfo: usize,
}

#[derive(Clone, Copy)]
#[repr(C)]
struct KEYBDINPUT {
    wVk: u16,
    wScan: u16,
    dwFlags: u32,
    time: u32,
    dwExtraInfo: usize,
}

#[derive(Clone, Copy)]
#[repr(C)]
struct HARDWAREINPUT {
    uMsg: u32,
    wParamL: u16,
    wParamH: u16,
}

const INPUT_MOUSE: u32 = 0;
const INPUT_KEYBOARD: u32 = 1;
const KEYEVENTF_KEYUP: u32 = 0x0002;
const KEYEVENTF_UNICODE: u32 = 0x0004;

const MOUSEEVENTF_MOVE: u32 = 0x0001;
const MOUSEEVENTF_LEFTDOWN: u32 = 0x0002;
const MOUSEEVENTF_LEFTUP: u32 = 0x0004;
const MOUSEEVENTF_RIGHTDOWN: u32 = 0x0008;
const MOUSEEVENTF_RIGHTUP: u32 = 0x0010;
const MOUSEEVENTF_MIDDLEDOWN: u32 = 0x0020;
const MOUSEEVENTF_MIDDLEUP: u32 = 0x0040;
const MOUSEEVENTF_ABSOLUTE: u32 = 0x8000;

const CF_TEXT: u32 = 1;

pub struct WindowsBridge;

impl WindowsBridge {
    pub fn new() -> Self {
        Self
    }
}

impl OSBridge for WindowsBridge {
    fn press_key(&self, key_code: u16) -> Result<(), String> {
        let mut input = INPUT {
            type_: INPUT_KEYBOARD,
            u: INPUT_UNION {
                ki: KEYBDINPUT {
                    wVk: key_code,
                    wScan: 0,
                    dwFlags: 0, // Key Down
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        
        unsafe {
            if SendInput(1, &mut input, std::mem::size_of::<INPUT>() as i32) == 1 {
                Ok(())
            } else {
                Err("SendInput failed".to_string())
            }
        }
    }

    fn release_key(&self, key_code: u16) -> Result<(), String> {
        let mut input = INPUT {
            type_: INPUT_KEYBOARD,
            u: INPUT_UNION {
                ki: KEYBDINPUT {
                    wVk: key_code,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP, 
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        
        unsafe {
            if SendInput(1, &mut input, std::mem::size_of::<INPUT>() as i32) == 1 {
                Ok(())
            } else {
                Err("SendInput failed".to_string())
            }
        }
    }

    fn type_text(&self, text: &str) -> Result<(), String> {
        // Simple iteration, doesn't handle shift states or unicode properly in this basic version
        // Ideally should use uScan with UNICODE flag for robust typing
        for c in text.encode_utf16() {
            let mut input = INPUT {
                 type_: INPUT_KEYBOARD,
                 u: INPUT_UNION {
                     ki: KEYBDINPUT {
                         wVk: 0,
                         wScan: c,
                         dwFlags: KEYEVENTF_UNICODE,
                         time: 0,
                         dwExtraInfo: 0,
                     }
                 }
            };
            unsafe { SendInput(1, &mut input, std::mem::size_of::<INPUT>() as i32); }
            
            // Key Up
             input.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
             unsafe { SendInput(1, &mut input, std::mem::size_of::<INPUT>() as i32); }
        }
        Ok(())
    }

    fn move_mouse(&self, x: i32, y: i32) -> Result<(), String> {
         let mut input = INPUT {
             type_: INPUT_MOUSE,
             u: INPUT_UNION {
                 mi: MOUSEINPUT {
                     dx: x, // TODO: Map to absolute coords if needed (0-65535)
                     dy: y,
                     mouseData: 0,
                     dwFlags: MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                     time: 0,
                     dwExtraInfo: 0,
                 }
             }
         };
         
         // Absolute mapping:
         // 65535 / ScreenWidth * x
         unsafe {
             let w = GetSystemMetrics(0); // SM_CXSCREEN
             let h = GetSystemMetrics(1); // SM_CYSCREEN
             
             input.u.mi.dx = (x as f32 * (65535.0 / w as f32)) as i32;
             input.u.mi.dy = (y as f32 * (65535.0 / h as f32)) as i32;
             
             if SendInput(1, &mut input, std::mem::size_of::<INPUT>() as i32) == 1 {
                 Ok(())
             } else {
                 Err("SendInput failed".to_string())
             }
         }
    }

    fn click_mouse(&self, button: MouseButton) -> Result<(), String> {
        let (down, up) = match button {
            MouseButton::Left => (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            MouseButton::Right => (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            MouseButton::Middle => (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        };
        
        // Click = Down + Up
        let mut inputs = [
            INPUT {
                 type_: INPUT_MOUSE,
                 u: INPUT_UNION {
                     mi: MOUSEINPUT {
                         dx: 0, dy: 0, mouseData: 0,
                         dwFlags: down, time: 0, dwExtraInfo: 0,
                     }
                 }
            },
            INPUT {
                 type_: INPUT_MOUSE,
                 u: INPUT_UNION {
                     mi: MOUSEINPUT {
                         dx: 0, dy: 0, mouseData: 0,
                         dwFlags: up, time: 0, dwExtraInfo: 0,
                     }
                 }
            }
        ];
        
        unsafe {
             if SendInput(2, inputs.as_mut_ptr(), std::mem::size_of::<INPUT>() as i32) == 2 {
                 Ok(())
             } else {
                 Err("SendInput failed".to_string())
             }
        }
    }

    fn get_clipboard_text(&self) -> Result<String, String> {
        unsafe {
             if OpenClipboard(null_mut()) == 0 { return Err("OpenClipboard failed".to_string()); }
             
             let h_mem = GetClipboardData(CF_TEXT);
             if h_mem.is_null() {
                 CloseClipboard();
                 return Err("No text in clipboard".to_string());
             }
             
             let p_data = GlobalLock(h_mem);
             if p_data.is_null() {
                 CloseClipboard();
                 return Err("Lock failed".to_string());
             }
             
             let c_str = std::ffi::CStr::from_ptr(p_data as *const i8);
             let s = c_str.to_string_lossy().into_owned();
             
             GlobalUnlock(h_mem);
             CloseClipboard();
             
             Ok(s)
        }
    }

    fn set_clipboard_text(&self, text: &str) -> Result<(), String> {
        // Convert to CString
        let c_str = CString::new(text).map_err(|_| "Invalid string".to_string())?;
        let len = c_str.as_bytes_with_nul().len();
        
        unsafe {
            if OpenClipboard(null_mut()) == 0 { return Err("OpenClipboard failed".to_string()); }
            EmptyClipboard();
            
            // GMEM_MOVEABLE = 0x0002
            let h_mem = GlobalAlloc(0x0002, len);
            if h_mem.is_null() {
                CloseClipboard();
                return Err("Alloc failed".to_string());
            }
            
            let p_data = GlobalLock(h_mem);
            std::ptr::copy_nonoverlapping(c_str.as_ptr(), p_data as *mut i8, len);
            GlobalUnlock(h_mem);
            
            SetClipboardData(CF_TEXT, h_mem);
            CloseClipboard();
        }
        
        Ok(())
    }

    fn exec_command(&self, cmd: &str, args: &[&str]) -> Result<String, String> {
        use std::process::Command;
        // Basic wrapper, no FFI needed for this part
        let output = Command::new(cmd)
            .args(args)
            .output()
            .map_err(|e| e.to_string())?;
            
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }
}
