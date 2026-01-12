package com.guru.phoneagent.presentation

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.guru.phoneagent.presentation.navigation.Screen
import com.guru.phoneagent.presentation.screens.HomeScreen
import com.guru.phoneagent.presentation.screens.PairingScreen
import com.guru.phoneagent.presentation.screens.PermissionsScreen
import com.guru.phoneagent.presentation.screens.SecurityScreen
import com.guru.phoneagent.presentation.screens.SettingsScreen
import com.guru.phoneagent.presentation.theme.GuruPhoneAgentTheme
import com.guru.phoneagent.presentation.viewmodels.MainViewModel
import dagger.hilt.android.AndroidEntryPoint
import org.slf4j.LoggerFactory

/**
 * Main Activity for GURU Phone Agent
 * 
 * Production-grade Android activity implementing secure navigation,
 * comprehensive permission management, and enterprise-level security controls.
 * 
 * Security Features:
 * - Runtime permission validation with security-first defaults
 * - Secure navigation with state preservation
 * - Biometric authentication integration
 * - Comprehensive audit logging of user interactions
 * - Fail-safe error handling with graceful degradation
 * 
 * UI Architecture:
 * - Jetpack Compose with Material Design 3
 * - MVVM pattern with Hilt dependency injection
 * - Reactive state management with StateFlow
 * - Accessibility compliance with semantic descriptions
 * - Dark/light theme support with system integration
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    
    companion object {
        private val REQUIRED_PERMISSIONS = arrayOf(
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.USE_BIOMETRIC,
            Manifest.permission.INTERNET,
            Manifest.permission.ACCESS_NETWORK_STATE,
            Manifest.permission.VIBRATE,
            Manifest.permission.WAKE_LOCK,
            Manifest.permission.FOREGROUND_SERVICE,
            Manifest.permission.POST_NOTIFICATIONS
        )
        
        private val OPTIONAL_PERMISSIONS = arrayOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.SEND_SMS,
            Manifest.permission.USE_FINGERPRINT
        )
    }
    
    private val logger = LoggerFactory.getLogger(MainActivity::class.java)
    private val viewModel: MainViewModel by viewModels()
    
    // Permission request launcher
    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        handlePermissionResults(permissions)
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        logger.info("MainActivity onCreate - initializing secure UI")
        
        try {
            // Initialize security context
            initializeSecurityContext()
            
            // Check and request permissions
            checkAndRequestPermissions()
            
            // Set up secure UI
            setContent {
                GuruPhoneAgentTheme {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background
                    ) {
                        GuruPhoneAgentApp(viewModel = viewModel)
                    }
                }
            }
            
            logger.info("MainActivity initialization completed successfully")
            
        } catch (exception: Exception) {
            logger.error("Critical failure during MainActivity initialization", exception)
            
            // Log security event
            viewModel.logSecurityEvent(
                eventType = "ACTIVITY_INITIALIZATION_FAILURE",
                severity = "CRITICAL",
                details = mapOf(
                    "error" to exception.message,
                    "activity" to "MainActivity",
                    "timestamp" to System.currentTimeMillis()
                )
            )
            
            // Fail-safe: Show error screen and prevent further execution
            showCriticalErrorScreen(exception)
        }
    }
    
    /**
     * Initializes security context for the main activity.
     */
    private fun initializeSecurityContext() {
        logger.debug("Initializing activity security context")
        
        // Prevent screenshots in production builds
        if (!com.guru.phoneagent.BuildConfig.DEBUG) {
            window.setFlags(
                android.view.WindowManager.LayoutParams.FLAG_SECURE,
                android.view.WindowManager.LayoutParams.FLAG_SECURE
            )
        }
        
        // Set secure window flags
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        
        // Initialize biometric authentication
        viewModel.initializeBiometricAuthentication()
        
        logger.debug("Activity security context initialized")
    }
    
    /**
     * Checks current permissions and requests missing ones.
     */
    private fun checkAndRequestPermissions() {
        logger.debug("Checking application permissions")
        
        val missingPermissions = REQUIRED_PERMISSIONS.filter { permission ->
            ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED
        }
        
        if (missingPermissions.isNotEmpty()) {
            logger.info("Requesting missing permissions: ${missingPermissions.joinToString()}")
            
            // Update UI state to show permission screen
            viewModel.setPermissionState(
                requiredPermissions = missingPermissions,
                optionalPermissions = OPTIONAL_PERMISSIONS.toList()
            )
            
            // Request permissions
            permissionLauncher.launch(missingPermissions.toTypedArray())
        } else {
            logger.info("All required permissions granted")
            viewModel.setPermissionsGranted(true)
        }
    }
    
    /**
     * Handles permission request results with security validation.
     */
    private fun handlePermissionResults(permissions: Map<String, Boolean>) {
        logger.debug("Processing permission results")
        
        val grantedPermissions = permissions.filterValues { it }.keys
        val deniedPermissions = permissions.filterValues { !it }.keys
        
        // Log permission results for audit
        viewModel.logSecurityEvent(
            eventType = "PERMISSION_REQUEST_RESULT",
            severity = "INFO",
            details = mapOf(
                "grantedPermissions" to grantedPermissions.toList(),
                "deniedPermissions" to deniedPermissions.toList(),
                "timestamp" to System.currentTimeMillis()
            )
        )
        
        // Check if all required permissions are granted
        val allRequiredGranted = REQUIRED_PERMISSIONS.all { permission ->
            ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
        }
        
        if (allRequiredGranted) {
            logger.info("All required permissions granted - enabling full functionality")
            viewModel.setPermissionsGranted(true)
        } else {
            logger.warn("Required permissions denied - operating in restricted mode")
            viewModel.setPermissionsGranted(false)
            
            // Show permission explanation screen
            viewModel.showPermissionExplanation(deniedPermissions.toList())
        }
        
        // Handle optional permissions
        val optionalGranted = OPTIONAL_PERMISSIONS.filter { permission ->
            ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
        }
        
        viewModel.setOptionalPermissions(optionalGranted)
    }
    
    /**
     * Shows critical error screen when initialization fails.
     */
    private fun showCriticalErrorScreen(exception: Exception) {
        setContent {
            GuruPhoneAgentTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.errorContainer
                ) {
                    CriticalErrorScreen(
                        error = exception.message ?: "Unknown critical error",
                        onRetry = { recreate() },
                        onExit = { finishAffinity() }
                    )
                }
            }
        }
    }
    
    override fun onResume() {
        super.onResume()
        logger.debug("MainActivity onResume")
        
        // Verify security state on resume
        viewModel.verifySecurityState()
        
        // Check for security policy changes
        viewModel.checkSecurityPolicyUpdates()
    }
    
    override fun onPause() {
        super.onPause()
        logger.debug("MainActivity onPause")
        
        // Log activity pause for audit
        viewModel.logSystemEvent(
            eventType = "ACTIVITY_PAUSED",
            severity = "DEBUG",
            details = mapOf(
                "activity" to "MainActivity",
                "timestamp" to System.currentTimeMillis()
            )
        )
    }
    
    override fun onDestroy() {
        logger.info("MainActivity onDestroy")
        
        // Cleanup security resources
        viewModel.cleanup()
        
        super.onDestroy()
    }
}

/**
 * Main Compose application with secure navigation.
 */
@Composable
fun GuruPhoneAgentApp(viewModel: MainViewModel) {
    val navController = rememberNavController()
    val uiState by viewModel.uiState.collectAsState()
    
    // Handle navigation based on application state
    LaunchedEffect(uiState.currentScreen) {
        if (navController.currentDestination?.route != uiState.currentScreen.route) {
            navController.navigate(uiState.currentScreen.route) {
                // Clear back stack for security screens
                if (uiState.currentScreen in listOf(Screen.Permissions, Screen.Security)) {
                    popUpTo(0) { inclusive = true }
                }
            }
        }
    }
    
    NavHost(
        navController = navController,
        startDestination = if (uiState.permissionsGranted) Screen.Home.route else Screen.Permissions.route
    ) {
        composable(Screen.Permissions.route) {
            PermissionsScreen(
                requiredPermissions = uiState.requiredPermissions,
                optionalPermissions = uiState.optionalPermissions,
                onPermissionsExplained = viewModel::onPermissionsExplained,
                onRetryPermissions = viewModel::retryPermissions
            )
        }
        
        composable(Screen.Home.route) {
            HomeScreen(
                connectionState = uiState.connectionState,
                authorityState = uiState.authorityState,
                onNavigateToSettings = { viewModel.navigateTo(Screen.Settings) },
                onNavigateToSecurity = { viewModel.navigateTo(Screen.Security) },
                onNavigateToPairing = { viewModel.navigateTo(Screen.Pairing) },
                onEmergencyStop = viewModel::emergencyStop
            )
        }
        
        composable(Screen.Pairing.route) {
            PairingScreen(
                pairingState = uiState.pairingState,
                onStartPairing = viewModel::startPairing,
                onCancelPairing = viewModel::cancelPairing,
                onQRCodeScanned = viewModel::onQRCodeScanned,
                onNavigateBack = { viewModel.navigateTo(Screen.Home) }
            )
        }
        
        composable(Screen.Security.route) {
            SecurityScreen(
                securityState = uiState.securityState,
                auditEvents = uiState.recentAuditEvents,
                onRefreshAuditLog = viewModel::refreshAuditLog,
                onExportAuditLog = viewModel::exportAuditLog,
                onNavigateBack = { viewModel.navigateTo(Screen.Home) }
            )
        }
        
        composable(Screen.Settings.route) {
            SettingsScreen(
                settings = uiState.settings,
                onSettingChanged = viewModel::updateSetting,
                onResetSettings = viewModel::resetSettings,
                onNavigateBack = { viewModel.navigateTo(Screen.Home) }
            )
        }
    }
}

/**
 * Critical error screen shown when the application fails to initialize securely.
 */
@Composable
fun CriticalErrorScreen(
    error: String,
    onRetry: () -> Unit,
    onExit: () -> Unit
) {
    // Implementation would show error details and recovery options
    // This is a placeholder for the actual error screen implementation
}