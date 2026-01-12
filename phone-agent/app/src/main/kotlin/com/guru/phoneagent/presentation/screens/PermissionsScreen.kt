package com.guru.phoneagent.presentation.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Permissions Screen for GURU Phone Agent
 * 
 * Production-grade permissions interface implementing security-first design,
 * comprehensive permission explanations, and accessibility compliance.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionsScreen(
    requiredPermissions: List<String>,
    optionalPermissions: List<String>,
    onPermissionsExplained: () -> Unit,
    onRetryPermissions: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Header
        Icon(
            imageVector = Icons.Default.Security,
            contentDescription = "Security",
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Text(
            text = "Security Permissions Required",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Text(
            text = "GURU requires specific permissions to provide secure automation while protecting your privacy and data.",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Required Permissions
        if (requiredPermissions.isNotEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Required Permissions",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Text(
                        text = "These permissions are essential for GURU's security features:",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    LazyColumn {
                        items(requiredPermissions) { permission ->
                            PermissionItem(
                                permission = permission,
                                isRequired = true
                            )
                        }
                    }
                }
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Optional Permissions
        if (optionalPermissions.isNotEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                )
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Optional Permissions",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Text(
                        text = "These permissions enable additional features:",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    LazyColumn {
                        items(optionalPermissions) { permission ->
                            PermissionItem(
                                permission = permission,
                                isRequired = false
                            )
                        }
                    }
                }
            }
        }
        
        Spacer(modifier = Modifier.weight(1f))
        
        // Action Buttons
        Button(
            onClick = onRetryPermissions,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(
                imageVector = Icons.Default.Security,
                contentDescription = null,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text("Grant Permissions")
        }
        
        Spacer(modifier = Modifier.height(8.dp))
        
        TextButton(
            onClick = onPermissionsExplained,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("I understand the security requirements")
        }
    }
}

@Composable
private fun PermissionItem(
    permission: String,
    isRequired: Boolean
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = getPermissionIcon(permission),
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = if (isRequired) 
                MaterialTheme.colorScheme.onErrorContainer 
            else 
                MaterialTheme.colorScheme.onSecondaryContainer
        )
        
        Spacer(modifier = Modifier.width(12.dp))
        
        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = getPermissionTitle(permission),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = if (isRequired) 
                    MaterialTheme.colorScheme.onErrorContainer 
                else 
                    MaterialTheme.colorScheme.onSecondaryContainer
            )
            
            Text(
                text = getPermissionDescription(permission),
                style = MaterialTheme.typography.bodySmall,
                color = if (isRequired) 
                    MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.7f)
                else 
                    MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.7f)
            )
        }
    }
}

private fun getPermissionIcon(permission: String): ImageVector {
    return when {
        permission.contains("CAMERA") -> Icons.Default.CameraAlt
        permission.contains("RECORD_AUDIO") -> Icons.Default.Mic
        permission.contains("BIOMETRIC") -> Icons.Default.Fingerprint
        permission.contains("INTERNET") -> Icons.Default.Wifi
        permission.contains("CALL_PHONE") -> Icons.Default.Phone
        permission.contains("SEND_SMS") -> Icons.Default.Message
        permission.contains("VIBRATE") -> Icons.Default.Vibration
        permission.contains("WAKE_LOCK") -> Icons.Default.PowerSettingsNew
        permission.contains("FOREGROUND_SERVICE") -> Icons.Default.PlayArrow
        permission.contains("POST_NOTIFICATIONS") -> Icons.Default.Notifications
        else -> Icons.Default.Security
    }
}

private fun getPermissionTitle(permission: String): String {
    return when {
        permission.contains("CAMERA") -> "Camera Access"
        permission.contains("RECORD_AUDIO") -> "Microphone Access"
        permission.contains("BIOMETRIC") -> "Biometric Authentication"
        permission.contains("INTERNET") -> "Network Access"
        permission.contains("CALL_PHONE") -> "Phone Calls"
        permission.contains("SEND_SMS") -> "SMS Messages"
        permission.contains("VIBRATE") -> "Haptic Feedback"
        permission.contains("WAKE_LOCK") -> "Keep Device Awake"
        permission.contains("FOREGROUND_SERVICE") -> "Background Services"
        permission.contains("POST_NOTIFICATIONS") -> "Security Notifications"
        else -> "System Permission"
    }
}

private fun getPermissionDescription(permission: String): String {
    return when {
        permission.contains("CAMERA") -> "Required for QR code scanning during secure device pairing"
        permission.contains("RECORD_AUDIO") -> "Required for voice command processing and speaker verification"
        permission.contains("BIOMETRIC") -> "Required for multi-factor authentication and security verification"
        permission.contains("INTERNET") -> "Required for secure communication with desktop agent"
        permission.contains("CALL_PHONE") -> "Optional: Enables voice-activated phone calls"
        permission.contains("SEND_SMS") -> "Optional: Enables voice-activated text messaging"
        permission.contains("VIBRATE") -> "Provides haptic feedback for security alerts and confirmations"
        permission.contains("WAKE_LOCK") -> "Maintains secure connection during voice processing"
        permission.contains("FOREGROUND_SERVICE") -> "Enables secure background communication and monitoring"
        permission.contains("POST_NOTIFICATIONS") -> "Critical security alerts and intrusion detection notifications"
        else -> "System permission required for secure operation"
    }
}