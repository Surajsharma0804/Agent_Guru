package com.guru.phoneagent.presentation.navigation

/**
 * Navigation destinations for GURU Phone Agent
 * 
 * Defines all application screens with secure navigation patterns.
 * Each screen implements appropriate security controls and audit logging.
 */
sealed class Screen(val route: String, val title: String) {
    
    /**
     * Permissions screen - shown when required permissions are not granted
     */
    object Permissions : Screen("permissions", "Permissions Required")
    
    /**
     * Home screen - main application interface
     */
    object Home : Screen("home", "GURU Phone Agent")
    
    /**
     * Device pairing screen - secure QR code pairing with desktop agent
     */
    object Pairing : Screen("pairing", "Device Pairing")
    
    /**
     * Security screen - audit logs and security status
     */
    object Security : Screen("security", "Security & Audit")
    
    /**
     * Settings screen - application configuration
     */
    object Settings : Screen("settings", "Settings")
    
    /**
     * Voice processing screen - voice command interface
     */
    object Voice : Screen("voice", "Voice Commands")
    
    /**
     * Emergency screen - critical security alerts
     */
    object Emergency : Screen("emergency", "Security Alert")
}

/**
 * Navigation arguments for parameterized screens
 */
object NavigationArgs {
    const val PAIRING_CODE = "pairing_code"
    const val SECURITY_EVENT_ID = "security_event_id"
    const val ERROR_MESSAGE = "error_message"
}