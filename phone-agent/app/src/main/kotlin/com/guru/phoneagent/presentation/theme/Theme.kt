package com.guru.phoneagent.presentation.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * GURU Phone Agent Theme
 * 
 * Production-grade Material Design 3 theme with security-focused color palette.
 * Implements accessibility standards and supports dynamic theming on Android 12+.
 * 
 * Security Considerations:
 * - High contrast ratios for accessibility compliance
 * - Clear visual distinction between security states
 * - Consistent color coding for security alerts and status indicators
 * - Dark theme support for reduced eye strain during extended use
 */

// Security-focused color palette
private val GuruLightColors = lightColorScheme(
    primary = Color(0xFF1565C0),           // Deep blue for primary actions
    onPrimary = Color(0xFFFFFFFF),         // White text on primary
    primaryContainer = Color(0xFFE3F2FD),  // Light blue container
    onPrimaryContainer = Color(0xFF0D47A1), // Dark blue text
    
    secondary = Color(0xFF37474F),          // Blue grey for secondary actions
    onSecondary = Color(0xFFFFFFFF),        // White text on secondary
    secondaryContainer = Color(0xFFECEFF1), // Light grey container
    onSecondaryContainer = Color(0xFF263238), // Dark grey text
    
    tertiary = Color(0xFF6A1B9A),          // Purple for accent elements
    onTertiary = Color(0xFFFFFFFF),        // White text on tertiary
    tertiaryContainer = Color(0xFFF3E5F5), // Light purple container
    onTertiaryContainer = Color(0xFF4A148C), // Dark purple text
    
    error = Color(0xFFD32F2F),             // Red for errors and security alerts
    onError = Color(0xFFFFFFFF),           // White text on error
    errorContainer = Color(0xFFFFEBEE),    // Light red container
    onErrorContainer = Color(0xFFB71C1C),  // Dark red text
    
    background = Color(0xFFFAFAFA),        // Light grey background
    onBackground = Color(0xFF212121),      // Dark grey text
    surface = Color(0xFFFFFFFF),           // White surface
    onSurface = Color(0xFF212121),         // Dark grey text on surface
    
    surfaceVariant = Color(0xFFF5F5F5),    // Light grey variant surface
    onSurfaceVariant = Color(0xFF424242),  // Medium grey text
    
    outline = Color(0xFFBDBDBD),           // Grey outline
    outlineVariant = Color(0xFFE0E0E0),    // Light grey outline variant
    
    scrim = Color(0x80000000),             // Semi-transparent black scrim
    
    // Security-specific colors
    surfaceTint = Color(0xFF1565C0),       // Primary tint for surfaces
    inverseSurface = Color(0xFF303030),    // Dark surface for contrast
    inverseOnSurface = Color(0xFFFFFFFF),  // White text on dark surface
    inversePrimary = Color(0xFF90CAF9)     // Light blue for dark backgrounds
)

private val GuruDarkColors = darkColorScheme(
    primary = Color(0xFF90CAF9),           // Light blue for primary actions
    onPrimary = Color(0xFF0D47A1),         // Dark blue text on primary
    primaryContainer = Color(0xFF1565C0),  // Deep blue container
    onPrimaryContainer = Color(0xFFE3F2FD), // Light blue text
    
    secondary = Color(0xFFB0BEC5),         // Light blue grey for secondary
    onSecondary = Color(0xFF263238),       // Dark grey text on secondary
    secondaryContainer = Color(0xFF37474F), // Blue grey container
    onSecondaryContainer = Color(0xFFECEFF1), // Light grey text
    
    tertiary = Color(0xFFCE93D8),          // Light purple for accent
    onTertiary = Color(0xFF4A148C),        // Dark purple text on tertiary
    tertiaryContainer = Color(0xFF6A1B9A), // Purple container
    onTertiaryContainer = Color(0xFFF3E5F5), // Light purple text
    
    error = Color(0xFFEF5350),             // Light red for errors
    onError = Color(0xFFB71C1C),           // Dark red text on error
    errorContainer = Color(0xFFD32F2F),    // Red container
    onErrorContainer = Color(0xFFFFEBEE),  // Light red text
    
    background = Color(0xFF121212),        // Dark background
    onBackground = Color(0xFFE0E0E0),      // Light grey text
    surface = Color(0xFF1E1E1E),           // Dark surface
    onSurface = Color(0xFFE0E0E0),         // Light grey text on surface
    
    surfaceVariant = Color(0xFF2C2C2C),    // Dark grey variant surface
    onSurfaceVariant = Color(0xFFBDBDBD),  // Medium grey text
    
    outline = Color(0xFF616161),           // Medium grey outline
    outlineVariant = Color(0xFF424242),    // Dark grey outline variant
    
    scrim = Color(0x80000000),             // Semi-transparent black scrim
    
    // Security-specific colors for dark theme
    surfaceTint = Color(0xFF90CAF9),       // Light blue tint
    inverseSurface = Color(0xFFE0E0E0),    // Light surface for contrast
    inverseOnSurface = Color(0xFF121212),  // Dark text on light surface
    inversePrimary = Color(0xFF1565C0)     // Deep blue for light backgrounds
)

/**
 * Security status colors used throughout the application
 */
object SecurityColors {
    val secure = Color(0xFF4CAF50)         // Green for secure status
    val warning = Color(0xFFFF9800)        // Orange for warnings
    val critical = Color(0xFFD32F2F)       // Red for critical alerts
    val unknown = Color(0xFF9E9E9E)        // Grey for unknown status
    
    val secureContainer = Color(0xFFE8F5E8)     // Light green container
    val warningContainer = Color(0xFFFFF3E0)    // Light orange container
    val criticalContainer = Color(0xFFFFEBEE)   // Light red container
    val unknownContainer = Color(0xFFF5F5F5)    // Light grey container
}

/**
 * Authority state colors for visual feedback
 */
object AuthorityColors {
    val armed = Color(0xFF4CAF50)          // Green for armed state
    val locked = Color(0xFFD32F2F)         // Red for locked state
    val verification = Color(0xFFFF9800)   // Orange for verification state
    val intrusion = Color(0xFF9C27B0)      // Purple for intrusion detected
}

@Composable
fun GuruPhoneAgentTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Dynamic color is available on Android 12+
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        
        darkTheme -> GuruDarkColors
        else -> GuruLightColors
    }
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }
    
    MaterialTheme(
        colorScheme = colorScheme,
        typography = GuruTypography,
        shapes = GuruShapes,
        content = content
    )
}