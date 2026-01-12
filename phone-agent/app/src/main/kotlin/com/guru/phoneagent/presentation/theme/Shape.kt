package com.guru.phoneagent.presentation.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * GURU Phone Agent Shape System
 * 
 * Production-grade shape system implementing Material Design 3 guidelines
 * with security-focused visual hierarchy and accessibility considerations.
 * 
 * Features:
 * - Consistent corner radius system for visual hierarchy
 * - Accessibility-compliant touch targets
 * - Security-focused visual distinction between interactive elements
 * - Responsive design support for different screen sizes
 */

/**
 * GURU Shape system based on Material Design 3
 */
val GuruShapes = Shapes(
    // Extra small shapes - for small components like chips and badges
    extraSmall = RoundedCornerShape(4.dp),
    
    // Small shapes - for buttons and small cards
    small = RoundedCornerShape(8.dp),
    
    // Medium shapes - for cards and dialogs
    medium = RoundedCornerShape(12.dp),
    
    // Large shapes - for bottom sheets and large surfaces
    large = RoundedCornerShape(16.dp),
    
    // Extra large shapes - for full-screen components
    extraLarge = RoundedCornerShape(28.dp)
)

/**
 * Extended shapes for security-specific components
 */
object SecurityShapes {
    
    /**
     * Shape for security alert cards and critical notifications
     */
    val securityAlert = RoundedCornerShape(8.dp)
    
    /**
     * Shape for status indicators and badges
     */
    val statusBadge = RoundedCornerShape(16.dp)
    
    /**
     * Shape for biometric authentication prompts
     */
    val biometricPrompt = RoundedCornerShape(
        topStart = 24.dp,
        topEnd = 24.dp,
        bottomStart = 0.dp,
        bottomEnd = 0.dp
    )
    
    /**
     * Shape for QR code scanner overlay
     */
    val qrCodeOverlay = RoundedCornerShape(12.dp)
    
    /**
     * Shape for permission explanation cards
     */
    val permissionCard = RoundedCornerShape(12.dp)
    
    /**
     * Shape for audit log entries
     */
    val auditLogEntry = RoundedCornerShape(6.dp)
    
    /**
     * Shape for emergency action buttons
     */
    val emergencyButton = RoundedCornerShape(8.dp)
    
    /**
     * Shape for connection status indicators
     */
    val connectionIndicator = RoundedCornerShape(20.dp)
}