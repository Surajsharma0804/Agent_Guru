//! Accessibility Abstraction
//! Unifies Inspection and Interaction across OS platforms.



#[derive(Debug, Clone)]
pub struct UIElement {
    pub name: String,
    pub role: String, // e.g., "Button", "Window"
    pub id: String,   // Automation ID
    pub bounding_box: (i32, i32, i32, i32), // x, y, w, h
    pub children: Vec<UIElement>,
}

pub trait AccessibilityDriver: Send + Sync {
    /// Inspect the element at the given screen coordinates
    fn inspect_at(&self, x: i32, y: i32) -> Result<UIElement, String>;
    
    /// Get the currently focused element
    fn get_focus(&self) -> Result<UIElement, String>;
    
    /// Perform the default action on the element (e.g., Click)
    fn invoke(&self, element_id: &str) -> Result<(), String>;
}
