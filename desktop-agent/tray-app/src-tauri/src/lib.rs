use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, AppHandle, State, Emitter
};
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use log::{info, warn, error};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorityState {
    pub state: String,
    pub granted_at: Option<String>,
    pub expires_at: Option<String>,
    pub session_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemStatus {
    pub authority_state: AuthorityState,
    pub components_healthy: bool,
    pub last_updated: String,
}

impl Default for SystemStatus {
    fn default() -> Self {
        Self {
            authority_state: AuthorityState {
                state: "LOCKED_LISTEN_ONLY".to_string(),
                granted_at: None,
                expires_at: None,
                session_id: "unknown".to_string(),
            },
            components_healthy: false,
            last_updated: chrono::Utc::now().to_rfc3339(),
        }
    }
}

// Shared application state
#[derive(Debug)]
pub struct AppState {
    pub system_status: Arc<Mutex<SystemStatus>>,
    pub desktop_agent_url: String,
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

impl AppState {
    pub fn new() -> Self {
        Self {
            system_status: Arc::new(Mutex::new(SystemStatus::default())),
            desktop_agent_url: "http://localhost:8000".to_string(),
        }
    }
}

// Tauri commands for frontend communication
#[tauri::command]
async fn get_system_status(state: State<'_, AppState>) -> Result<SystemStatus, String> {
    let status = state.system_status.lock()
        .map_err(|e| format!("Failed to get system status: {}", e))?;
    Ok(status.clone())
}

#[tauri::command]
async fn revoke_authority(state: State<'_, AppState>) -> Result<String, String> {
    info!("Manual authority revocation requested");
    
    // Call the desktop agent API to revoke authority
    let client = reqwest::Client::new();
    let url = format!("{}/authority/revoke", state.desktop_agent_url);
    
    match client.post(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                info!("Authority successfully revoked");
                
                // Update local state
                if let Ok(mut status) = state.system_status.lock() {
                    status.authority_state.state = "LOCKED_LISTEN_ONLY".to_string();
                    status.authority_state.granted_at = None;
                    status.authority_state.expires_at = None;
                    status.last_updated = chrono::Utc::now().to_rfc3339();
                }
                
                Ok("Authority revoked successfully".to_string())
            } else {
                let error_msg = format!("Failed to revoke authority: HTTP {}", response.status());
                warn!("{}", error_msg);
                Err(error_msg)
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to connect to desktop agent: {}", e);
            error!("{}", error_msg);
            Err(error_msg)
        }
    }
}

#[tauri::command]
async fn emergency_lock(state: State<'_, AppState>) -> Result<String, String> {
    warn!("Emergency lock requested");
    
    // Call the desktop agent API for emergency lock
    let client = reqwest::Client::new();
    let url = format!("{}/security/lock", state.desktop_agent_url);
    
    match client.post(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                warn!("Emergency lock activated");
                
                // Update local state
                if let Ok(mut status) = state.system_status.lock() {
                    status.authority_state.state = "INTRUSION_DETECTED".to_string();
                    status.authority_state.granted_at = None;
                    status.authority_state.expires_at = None;
                    status.last_updated = chrono::Utc::now().to_rfc3339();
                }
                
                Ok("Emergency lock activated".to_string())
            } else {
                let error_msg = format!("Failed to activate emergency lock: HTTP {}", response.status());
                error!("{}", error_msg);
                Err(error_msg)
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to connect to desktop agent: {}", e);
            error!("{}", error_msg);
            Err(error_msg)
        }
    }
}

#[tauri::command]
async fn refresh_status(app_handle: AppHandle, state: State<'_, AppState>) -> Result<SystemStatus, String> {
    info!("Refreshing system status");
    
    // Fetch status from desktop agent
    let client = reqwest::Client::new();
    let url = format!("{}/authority/status", state.desktop_agent_url);
    
    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<AuthorityState>().await {
                    Ok(authority_state) => {
                        let new_status = SystemStatus {
                            authority_state,
                            components_healthy: true,
                            last_updated: chrono::Utc::now().to_rfc3339(),
                        };
                        
                        // Update local state
                        if let Ok(mut status) = state.system_status.lock() {
                            *status = new_status.clone();
                        }
                        
                        // Emit status update to frontend
                        let _ = app_handle.emit("status-updated", &new_status);
                        
                        info!("System status refreshed successfully");
                        Ok(new_status)
                    }
                    Err(e) => {
                        let error_msg = format!("Failed to parse authority status: {}", e);
                        warn!("{}", error_msg);
                        Err(error_msg)
                    }
                }
            } else {
                let error_msg = format!("Failed to get authority status: HTTP {}", response.status());
                warn!("{}", error_msg);
                
                // Update local state to indicate unhealthy
                if let Ok(mut status) = state.system_status.lock() {
                    status.components_healthy = false;
                    status.last_updated = chrono::Utc::now().to_rfc3339();
                }
                
                Err(error_msg)
            }
        }
        Err(e) => {
            let error_msg = format!("Failed to connect to desktop agent: {}", e);
            error!("{}", error_msg);
            
            // Update local state to indicate unhealthy
            if let Ok(mut status) = state.system_status.lock() {
                status.components_healthy = false;
                status.last_updated = chrono::Utc::now().to_rfc3339();
            }
            
            Err(error_msg)
        }
    }
}

fn create_tray_menu(app: &AppHandle) -> tauri::menu::Menu<tauri::Wry> {
    use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
    
    let menu = Menu::new(app).unwrap();
    
    let show_status = MenuItem::with_id(app, "show_status", "Show Status", true, None::<&str>).unwrap();
    let separator1 = PredefinedMenuItem::separator(app).unwrap();
    let revoke_authority = MenuItem::with_id(app, "revoke_authority", "Revoke Authority", true, None::<&str>).unwrap();
    let emergency_lock = MenuItem::with_id(app, "emergency_lock", "Emergency Lock", true, None::<&str>).unwrap();
    let separator2 = PredefinedMenuItem::separator(app).unwrap();
    let refresh_status = MenuItem::with_id(app, "refresh_status", "Refresh Status", true, None::<&str>).unwrap();
    let separator3 = PredefinedMenuItem::separator(app).unwrap();
    let quit = PredefinedMenuItem::quit(app, Some("Quit GURU")).unwrap();
    
    menu.append_items(&[
        &show_status,
        &separator1,
        &revoke_authority,
        &emergency_lock,
        &separator2,
        &refresh_status,
        &separator3,
        &quit,
    ]).unwrap();
    
    menu
}

fn handle_tray_event(app: &AppHandle, event: TrayIconEvent) {
    match event {
        TrayIconEvent::Click {
            button: MouseButton::Left,
            button_state: MouseButtonState::Up,
            ..
        } => {
            info!("Tray icon left-clicked - showing status window");
            
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        TrayIconEvent::Click {
            button: MouseButton::Right,
            button_state: MouseButtonState::Up,
            ..
        } => {
            info!("Tray icon right-clicked - showing context menu");
            // Context menu is handled automatically by Tauri
        }
        _ => {}
    }
}

fn handle_menu_event(app: &AppHandle, event: tauri::menu::MenuEvent) {
    info!("Tray menu item clicked: {:?}", event.id());
    
    match event.id().as_ref() {
        "show_status" => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        "revoke_authority" => {
            let app_handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state = app_handle.state::<AppState>();
                match revoke_authority(state).await {
                    Ok(msg) => {
                        info!("Authority revoked: {}", msg);
                        let _ = app_handle.emit("authority-revoked", msg);
                    }
                    Err(e) => {
                        error!("Failed to revoke authority: {}", e);
                        let _ = app_handle.emit("error", e);
                    }
                }
            });
        }
        "emergency_lock" => {
            let app_handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state = app_handle.state::<AppState>();
                match emergency_lock(state).await {
                    Ok(msg) => {
                        warn!("Emergency lock activated: {}", msg);
                        let _ = app_handle.emit("emergency-lock-activated", msg);
                    }
                    Err(e) => {
                        error!("Failed to activate emergency lock: {}", e);
                        let _ = app_handle.emit("error", e);
                    }
                }
            });
        }
        "refresh_status" => {
            let app_handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state = app_handle.state::<AppState>();
                match refresh_status(app_handle.clone(), state).await {
                    Ok(_) => {
                        info!("Status refreshed successfully");
                    }
                    Err(e) => {
                        error!("Failed to refresh status: {}", e);
                        let _ = app_handle.emit("error", e);
                    }
                }
            });
        }
        _ => {}
    }
}

async fn setup_periodic_status_refresh(app_handle: AppHandle) {
    let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(30));
    
    loop {
        interval.tick().await;
        
        let state = app_handle.state::<AppState>();
        if let Err(e) = refresh_status(app_handle.clone(), state).await {
            warn!("Periodic status refresh failed: {}", e);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::new())
        .setup(|app| {
            info!("Setting up GURU System Tray application");
            
            // Create system tray
            let tray_menu = create_tray_menu(app.handle());
            let _tray = TrayIconBuilder::new()
                .menu(&tray_menu)
                .tooltip("GURU Personal Assistant")
                .icon(app.default_window_icon().unwrap().clone())
                .on_tray_icon_event(|tray, event| {
                    if let Some(app) = tray.app_handle().get_webview_window("main") {
                        handle_tray_event(app.app_handle(), event);
                    }
                })
                .on_menu_event(|app, event| handle_menu_event(app, event))
                .build(app)?;
            
            info!("System tray created successfully");
            
            // Hide the main window initially (tray-only mode)
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }
            
            // Start periodic status refresh
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                setup_periodic_status_refresh(app_handle).await;
            });
            
            info!("GURU System Tray setup completed");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_system_status,
            revoke_authority,
            emergency_lock,
            refresh_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
