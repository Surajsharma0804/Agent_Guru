use app_lib::{AppState, SystemStatus};

#[test]
fn test_app_state_creation() {
    let app_state = AppState::new();
    assert_eq!(app_state.desktop_agent_url, "http://localhost:8000");
}

#[test]
fn test_system_status_default() {
    let status = SystemStatus::default();
    assert_eq!(status.authority_state.state, "LOCKED_LISTEN_ONLY");
    assert!(!status.components_healthy);
}