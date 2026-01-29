//! Sovereign COM Bindings
//! Manual VTable definitions for IUnknown and IUIAutomation.
//! Zero Dependency. Pure Rust.

use std::ffi::c_void;
use std::os::raw::c_int;

// GUID Structure
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct GUID {
    pub data1: u32,
    pub data2: u16,
    pub data3: u16,
    pub data4: [u8; 8],
}

// Common HRESULTs
pub const S_OK: i32 = 0;
pub const E_FAIL: i32 = -2147467259; // 0x80004005
pub const E_NOINTERFACE: i32 = -2147467262; // 0x80004002

// IUnknown Interface
// Rust implementation of VTable layout
#[repr(C)]
pub struct IUnknownVtbl {
    pub QueryInterface: unsafe extern "system" fn(
        this: *mut IUnknown,
        riid: *const GUID,
        ppvObject: *mut *mut c_void,
    ) -> i32,
    pub AddRef: unsafe extern "system" fn(this: *mut IUnknown) -> u32,
    pub Release: unsafe extern "system" fn(this: *mut IUnknown) -> u32,
}

#[repr(C)]
pub struct IUnknown {
    pub vtbl: *const IUnknownVtbl,
}

// IUIAutomation Interface (Partial Stub)
// CID: {ff48dba4-60ef-4201-aa87-54103eef594e}
// IID: {30cbe57d-d9d0-452a-ab13-7ac5ac4825ee}

#[repr(C)]
pub struct IUIAutomationVtbl {
    pub parent: IUnknownVtbl,
    // IUIAutomation methods...
    pub CompareElements: unsafe extern "system" fn(this: *mut IUIAutomation, el1: *mut IUIAutomationElement, el2: *mut IUIAutomationElement, areSame: *mut c_int) -> i32,
    pub CompareRuntimeIds: unsafe extern "system" fn(this: *mut IUIAutomation, el1: *mut IUIAutomationElement, el2: *mut IUIAutomationElement, areSame: *mut c_int) -> i32,
    pub GetRootElement: unsafe extern "system" fn(this: *mut IUIAutomation, root: *mut *mut IUIAutomationElement) -> i32,
    pub ElementFromHandle: unsafe extern "system" fn(this: *mut IUIAutomation, hwnd: *mut c_void, element: *mut *mut IUIAutomationElement) -> i32,
    pub ElementFromPoint: unsafe extern "system" fn(this: *mut IUIAutomation, pt: Point, element: *mut *mut IUIAutomationElement) -> i32,
    // ... many more methods. We only implement what we need.
    // WARNING: VTable order matters strictly! 
    // If we skip methods, we crash.
    // IUIAutomation has many methods.
    // I must look up the exact offset or define placeholders.
    // 
    // Order:
    // CompareElements
    // CompareRuntimeIds
    // GetRootElement
    // ElementFromHandle
    // ElementFromPoint
    // GetFocusedElement
    // GetRootElementBuildCache
    // ...
    
    // For "Sovereign" correctness, I'll use a `pad` for methods I don't use 
    // ONLY IF I can ensure I'm calling the right offset.
    // But Rust structs are rigid.
    // I will implement a "Safe Wrapper" that uses dynamic offset or define FULL vtable.
    // Defining full vtable for IUIAutomation (60+ methods) is verbose.
    // 
    // Alternative: `*const usize` array and cast?
    // Let's rely on standard COM layout.
    // I'll define the FIRST 6 methods which are critical.
    pub GetFocusedElement: unsafe extern "system" fn(this: *mut IUIAutomation, element: *mut *mut IUIAutomationElement) -> i32,
}

#[repr(C)]
pub struct IUIAutomation {
    pub vtbl: *const IUIAutomationVtbl,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

// IUIAutomationElement Interface
// IID: {d22108aa-8ac5-49a5-837b-37bbb3d7591e}
#[repr(C)]
pub struct IUIAutomationElementVtbl {
    pub parent: IUnknownVtbl,
    pub SetFocus: unsafe extern "system" fn(this: *mut IUIAutomationElement) -> i32,
    pub GetRuntimeId: unsafe extern "system" fn(this: *mut IUIAutomationElement, runtimeId: *mut *mut c_void) -> i32, // SafeArray stub
    pub FindFirst: unsafe extern "system" fn(this: *mut IUIAutomationElement, scope: i32, condition: *mut c_void, found: *mut *mut IUIAutomationElement) -> i32,
    pub FindAll: unsafe extern "system" fn(this: *mut IUIAutomationElement, scope: i32, condition: *mut c_void, found: *mut *mut c_void) -> i32,
    pub FindFirstBuildCache: unsafe extern "system" fn(this: *mut IUIAutomationElement, scope: i32, condition: *mut c_void, cacheRequest: *mut c_void, found: *mut *mut IUIAutomationElement) -> i32,
    pub FindAllBuildCache: unsafe extern "system" fn(this: *mut IUIAutomationElement, scope: i32, condition: *mut c_void, cacheRequest: *mut c_void, found: *mut *mut c_void) -> i32,
    pub BuildUpdatedCache: unsafe extern "system" fn(this: *mut IUIAutomationElement, cacheRequest: *mut c_void, updatedElement: *mut *mut IUIAutomationElement) -> i32,
    pub GetCurrentPropertyValue: unsafe extern "system" fn(this: *mut IUIAutomationElement, property_id: i32, value: *mut Variant) -> i32,
    pub GetCurrentPropertyValueEx: unsafe extern "system" fn(this: *mut IUIAutomationElement, property_id: i32, ignoreDefaultValue: i32, value: *mut Variant) -> i32,
    // ... Properties getters (CurrentProcessId, CurrentControlType, etc) are typically exposed via properties or distinct methods?
    // In IUIAutomationElement, properties are accessed via get_CurrentName etc.
    // Actually, the VTable has getters for EACH property.
    // This is HUNDREDS of methods.
    // 
    // We will stick to `GetCurrentPropertyValue` (Line 8 above).
    // This is generic.
}

#[repr(C)]
pub struct IUIAutomationElement {
    pub vtbl: *const IUIAutomationElementVtbl,
}

#[repr(C)]
pub struct Variant {
    pub vt: u16,
    pub wReserved1: u16,
    pub wReserved2: u16,
    pub wReserved3: u16,
    pub data: u64, // simplified union
    pub padding: u64,
}

// IDs
pub const CLSID_CUIAutomation: GUID = GUID { data1: 0xff48dba4, data2: 0x60ef, data3: 0x4201, data4: [0xaa, 0x87, 0x54, 0x10, 0x3e, 0xef, 0x59, 0x4e] };
pub const IID_IUIAutomation: GUID = GUID { data1: 0x30cbe57d, data2: 0xd9d0, data3: 0x452a, data4: [0xab, 0x13, 0x7a, 0xc5, 0xac, 0x48, 0x25, 0xee] };

pub const UIA_NamePropertyId: i32 = 30005;
pub const UIA_AutomationIdPropertyId: i32 = 30011;
pub const UIA_ControlTypePropertyId: i32 = 30003;

// FFI Imports for CoCreateInstance
#[link(name = "ole32")]
unsafe extern "system" {
    pub fn CoInitialize(pvReserved: *mut c_void) -> i32;
    pub fn CoCreateInstance(
        rclsid: *const GUID,
        pUnkOuter: *mut IUnknown,
        dwClsContext: u32,
        riid: *const GUID,
        ppv: *mut *mut c_void,
    ) -> i32;
    pub fn CoUninitialize();
}

#[link(name = "oleaut32")]
unsafe extern "system" {
    pub fn VariantClear(pvarg: *mut Variant);
}
