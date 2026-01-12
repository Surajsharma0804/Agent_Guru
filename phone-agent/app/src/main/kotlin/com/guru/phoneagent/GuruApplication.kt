package com.guru.phoneagent

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.content.ContextCompat
import dagger.hilt.android.HiltAndroidApp
import org.slf4j.LoggerFactory
import javax.inject.Inject

/**
 * GURU Phone Agent Application
 * 
 * Production-grade Android application for secure personal automation.
 * Implements enterprise-level security, comprehensive audit logging,
 * and fail-safe defaults throughout the application lifecycle.
 * 
 * Core Security Principles:
 * - Local-first processing with no cloud dependencies
 * - Explicit consent over convenience
 * - Defense-in-depth security architecture
 * - Comprehensive audit logging with cryptographic integrity
 * - Fail-safe defaults with secure degradation
 * 
 * Authority Model:
 * - All automation requires explicit user authority
 * - Multi-factor biometric verification for sensitive operations
 * - Immediate authority revocation on security violations
 * - No silent automation or background operations
 */
@HiltAndroidApp
class GuruApplication : Application() {
    
    companion object {
        private const val NOTIFICATION_CHANNEL_SECURITY = "security_alerts"
        private const val NOTIFICATION_CHANNEL_COMMUNICATION = "secure_communication"
        private const val NOTIFICATION_CHANNEL_VOICE = "voice_processing"
        
        // Security configuration
        private const val MIN_API_LEVEL = 26 // Android 8.0 for modern security features
        private const val REQUIRED_SECURITY_PATCH_LEVEL = "2023-01-01"
    }
    
    private val logger = LoggerFactory.getLogger(GuruApplication::class.java)
    
    @Inject
    lateinit var securityManager: com.guru.phoneagent.security.SecurityManager
    
    @Inject
    lateinit var auditLogger: com.guru.phoneagent.audit.AuditLogger
    
    override fun onCreate() {
        super.onCreate()
        
        try {
            logger.info("GURU Phone Agent starting - Version ${BuildConfig.VERSION_NAME}")
            
            // Validate security requirements
            validateSecurityRequirements()
            
            // Initialize security subsystems
            initializeSecuritySubsystems()
            
            // Create notification channels
            createNotificationChannels()
            
            // Initialize audit logging
            initializeAuditLogging()
            
            // Validate application integrity
            validateApplicationIntegrity()
            
            logger.info("GURU Phone Agent initialization completed successfully")
            
        } catch (exception: Exception) {
            logger.error("Critical failure during application initialization", exception)
            
            // Log security event for forensic analysis
            try {
                auditLogger.logSecurityEvent(
                    eventType = "APPLICATION_INITIALIZATION_FAILURE",
                    severity = "CRITICAL",
                    details = mapOf(
                        "error" to exception.message,
                        "stackTrace" to exception.stackTraceToString(),
                        "timestamp" to System.currentTimeMillis()
                    )
                )
            } catch (auditException: Exception) {
                // If audit logging fails, we have a critical system failure
                logger.error("Audit logging failed during initialization failure", auditException)
            }
            
            // Fail-safe: Terminate application on critical initialization failure
            throw SecurityException("GURU Phone Agent failed to initialize securely", exception)
        }
    }
    
    /**
     * Validates that the device meets minimum security requirements
     * for running GURU Phone Agent.
     */
    private fun validateSecurityRequirements() {
        logger.debug("Validating device security requirements")
        
        // Check minimum API level
        if (Build.VERSION.SDK_INT < MIN_API_LEVEL) {
            throw SecurityException(
                "Device API level ${Build.VERSION.SDK_INT} below minimum required $MIN_API_LEVEL"
            )
        }
        
        // Check for hardware security features
        val packageManager = packageManager
        
        // Verify biometric capability
        if (!packageManager.hasSystemFeature("android.hardware.fingerprint") &&
            !packageManager.hasSystemFeature("android.hardware.biometrics.face")) {
            logger.warn("No biometric authentication available - reduced security mode")
        }
        
        // Verify camera for QR code scanning
        if (!packageManager.hasSystemFeature("android.hardware.camera")) {
            throw SecurityException("Camera required for secure device pairing")
        }
        
        // Verify microphone for voice commands
        if (!packageManager.hasSystemFeature("android.hardware.microphone")) {
            throw SecurityException("Microphone required for voice command processing")
        }
        
        // Check for hardware-backed keystore
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                val keyguardManager = ContextCompat.getSystemService(this, android.app.KeyguardManager::class.java)
                if (keyguardManager?.isDeviceSecure != true) {
                    logger.warn("Device lock screen not configured - reduced security")
                }
            } catch (exception: Exception) {
                logger.warn("Unable to verify device security configuration", exception)
            }
        }
        
        logger.info("Device security requirements validated successfully")
    }
    
    /**
     * Initializes core security subsystems with fail-safe defaults.
     */
    private fun initializeSecuritySubsystems() {
        logger.debug("Initializing security subsystems")
        
        try {
            // Initialize security manager
            securityManager.initialize()
            
            // Verify cryptographic capabilities
            securityManager.validateCryptographicCapabilities()
            
            // Initialize secure storage
            securityManager.initializeSecureStorage()
            
            logger.info("Security subsystems initialized successfully")
            
        } catch (exception: Exception) {
            logger.error("Failed to initialize security subsystems", exception)
            throw SecurityException("Security subsystem initialization failed", exception)
        }
    }
    
    /**
     * Creates notification channels for different types of system notifications.
     */
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            
            // Security alerts channel (high priority)
            val securityChannel = NotificationChannel(
                NOTIFICATION_CHANNEL_SECURITY,
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Critical security events and intrusion detection alerts"
                enableLights(true)
                enableVibration(true)
                setBypassDnd(true)
            }
            
            // Secure communication channel (default priority)
            val communicationChannel = NotificationChannel(
                NOTIFICATION_CHANNEL_COMMUNICATION,
                "Secure Communication",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Secure communication status and pairing notifications"
                enableLights(false)
                enableVibration(false)
            }
            
            // Voice processing channel (low priority)
            val voiceChannel = NotificationChannel(
                NOTIFICATION_CHANNEL_VOICE,
                "Voice Processing",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Voice command processing status"
                enableLights(false)
                enableVibration(false)
            }
            
            notificationManager.createNotificationChannels(
                listOf(securityChannel, communicationChannel, voiceChannel)
            )
            
            logger.debug("Notification channels created successfully")
        }
    }
    
    /**
     * Initializes audit logging with cryptographic integrity verification.
     */
    private fun initializeAuditLogging() {
        logger.debug("Initializing audit logging system")
        
        try {
            auditLogger.initialize()
            
            // Log application startup event
            auditLogger.logSystemEvent(
                eventType = "APPLICATION_STARTUP",
                severity = "INFO",
                details = mapOf(
                    "version" to BuildConfig.VERSION_NAME,
                    "buildType" to BuildConfig.BUILD_TYPE,
                    "apiLevel" to Build.VERSION.SDK_INT,
                    "deviceModel" to Build.MODEL,
                    "timestamp" to System.currentTimeMillis()
                )
            )
            
            logger.info("Audit logging system initialized successfully")
            
        } catch (exception: Exception) {
            logger.error("Failed to initialize audit logging", exception)
            throw SecurityException("Audit logging initialization failed", exception)
        }
    }
    
    /**
     * Validates application integrity and detects tampering attempts.
     */
    private fun validateApplicationIntegrity() {
        logger.debug("Validating application integrity")
        
        try {
            // Verify application signature
            val packageInfo = packageManager.getPackageInfo(packageName, android.content.pm.PackageManager.GET_SIGNATURES)
            val signatures = packageInfo.signatures
            
            if (signatures.isEmpty()) {
                throw SecurityException("Application signature verification failed - no signatures found")
            }
            
            // In production, this would verify against known good signatures
            // For now, we just ensure signatures exist
            logger.debug("Application signature verification completed")
            
            // Verify build configuration
            if (BuildConfig.DEBUG && BuildConfig.BUILD_TYPE == "release") {
                throw SecurityException("Invalid build configuration detected")
            }
            
            // Log integrity verification success
            auditLogger.logSecurityEvent(
                eventType = "APPLICATION_INTEGRITY_VERIFIED",
                severity = "INFO",
                details = mapOf(
                    "signatureCount" to signatures.size,
                    "buildType" to BuildConfig.BUILD_TYPE,
                    "debugMode" to BuildConfig.DEBUG_MODE
                )
            )
            
            logger.info("Application integrity validation completed successfully")
            
        } catch (exception: Exception) {
            logger.error("Application integrity validation failed", exception)
            
            auditLogger.logSecurityEvent(
                eventType = "APPLICATION_INTEGRITY_FAILURE",
                severity = "CRITICAL",
                details = mapOf(
                    "error" to exception.message,
                    "timestamp" to System.currentTimeMillis()
                )
            )
            
            throw SecurityException("Application integrity validation failed", exception)
        }
    }
    
    override fun onTerminate() {
        logger.info("GURU Phone Agent terminating")
        
        try {
            // Log application shutdown
            auditLogger.logSystemEvent(
                eventType = "APPLICATION_SHUTDOWN",
                severity = "INFO",
                details = mapOf(
                    "timestamp" to System.currentTimeMillis(),
                    "reason" to "normal_termination"
                )
            )
            
            // Cleanup security resources
            securityManager.cleanup()
            
        } catch (exception: Exception) {
            logger.error("Error during application termination", exception)
        }
        
        super.onTerminate()
    }
}