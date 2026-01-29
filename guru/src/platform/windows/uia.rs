//! Windows UI Automation Driver
//! Native implementation of AccessibilityDriver using Sovereign COM.

use super::com::*;
use crate::platform::accessibility::{AccessibilityDriver, UIElement};
use std::ptr;
use std::sync::Once;
use std::ffi::c_void;

static COM_INIT: Once = Once::new();

pub struct WindowsUIADriver {
    automation: *mut IUIAutomation,
}

// Mark as Send/Sync for the trait. 
// COM pointers are generally thread-tied (STA), 
// so we must be careful. For now, we wrap in a Mutex or assume MTA?
// UIA is free-threaded mostly if initialized right.
// We strictly mark it unsafe to send unless we handle marshalling.
// For this single-threaded agent logic, we might need a dedicated UI thread/agent.
unsafe impl Send for WindowsUIADriver {}
unsafe impl Sync for WindowsUIADriver {}

impl WindowsUIADriver {
    pub fn new() -> Result<Self, String> {
        // Initialize COM
        // In a real app, this should be per-thread.
        unsafe {
            // CoInitialize(NULL) -> S_OK or S_FALSE
            let hr = CoInitialize(ptr::null_mut());
            if hr < 0 {
                // RPC_E_CHANGED_MODE (0x80010106) means already init with different mode.
                // We ignore if already init.
                if hr != -2147417850 { 
                     return Err(format!("CoInitialize failed: {:x}", hr));
                }
            }
            
            let mut automation: *mut IUIAutomation = ptr::null_mut();
            let hr = CoCreateInstance(
                &CLSID_CUIAutomation,
                ptr::null_mut(),
                1, // CLSCTX_INPROC_SERVER
                &IID_IUIAutomation,
                &mut automation as *mut *mut _ as *mut *mut c_void,
            );
            
            if hr < 0 || automation.is_null() {
                return Err(format!("Failed to create CUIAutomation: {:x}", hr));
            }
            
            Ok(Self { automation })
        }
    }
    
    fn get_property(&self, element: *mut IUIAutomationElement, prop_id: i32) -> String {
        unsafe {
             if element.is_null() { return String::new(); }
             let vtbl = (*element).vtbl;
             let mut variant = Variant { vt: 0, wReserved1: 0, wReserved2: 0, wReserved3: 0, data: 0, padding: 0 };
             
             let hr = ((*vtbl).GetCurrentPropertyValue)(element, prop_id, &mut variant);
             if hr >= 0 && variant.vt == 8 { // VT_BSTR
                 // Extract BSTR (pointer to wide string)
                 let bstr_ptr = variant.data as *const u16;
                 // Read len (stored before ptr usually, or just search null)
                 // SysStringLen?
                 // For now, assume null terminated or use a BSTR crate logic stub
                 // Standard BSTR is length prefixed.
                 // We'll read until null for safety stub.
                 let mut len = 0;
                 while *bstr_ptr.offset(len) != 0 { len += 1; }
                 
                 let slice = std::slice::from_raw_parts(bstr_ptr, len as usize);
                 let s = String::from_utf16_lossy(slice);
                 
                 VariantClear(&mut variant);
                 return s;
             }
             VariantClear(&mut variant);
             String::new()
        }
    }
}

impl AccessibilityDriver for WindowsUIADriver {
    fn inspect_at(&self, x: i32, y: i32) -> Result<UIElement, String> {
        unsafe {
            let mut element: *mut IUIAutomationElement = ptr::null_mut();
            let pt = Point { x, y };
            
            let vtbl = (*self.automation).vtbl;
            let hr = ((*vtbl).ElementFromPoint)(self.automation, pt, &mut element);
            
            if hr < 0 || element.is_null() {
                return Err("No element found at point".to_string());
            }
            
            let name = self.get_property(element, UIA_NamePropertyId);
            let id = self.get_property(element, UIA_AutomationIdPropertyId);
            let role = self.get_property(element, UIA_ControlTypePropertyId); // This returns int actually.
            // Converting int role to string needs a map.
            let role_str = format!("Type({})", role); 

            // Release element
            let el_vtbl = (*element).vtbl;
            ((*el_vtbl).parent.Release)(element.cast()); // Cast to IUnknown
            
            Ok(UIElement {
                name,
                id,
                role: role_str,
                bounding_box: (x, y, 0, 0), // Stub BB
                children: Vec::new(),
            })
        }
    }
    
    fn get_focus(&self) -> Result<UIElement, String> {
         unsafe {
            let mut element: *mut IUIAutomationElement = ptr::null_mut();
            let vtbl = (*self.automation).vtbl;
            let hr = ((*vtbl).GetFocusedElement)(self.automation, &mut element);
            
            if hr < 0 || element.is_null() {
                return Err("No element has focus".to_string());
            }
            
            let name = self.get_property(element, UIA_NamePropertyId);
            let id = self.get_property(element, UIA_AutomationIdPropertyId);
            
             // Release element
            let el_vtbl = (*element).vtbl;
            ((*el_vtbl).parent.Release)(element.cast());
            
            Ok(UIElement {
                name,
                id,
                role: "Focused".to_string(),
                bounding_box: (0, 0, 0, 0),
                children: Vec::new(),
            })
         }
    }
    
    fn invoke(&self, _element_id: &str) -> Result<(), String> {
        // Needs FindFirst logic.
        // Stub for now.
        Err("Invoke not implemented in Sovereign V0.1".to_string())
    }
}

impl Drop for WindowsUIADriver {
    fn drop(&mut self) {
        unsafe {
            if !self.automation.is_null() {
                 let vtbl = (*self.automation).vtbl;
                 ((*vtbl).parent.Release)(self.automation.cast());
            }
            // CoUninitialize(); // thread issues if we uninit and others use it.
        }
    }
}
