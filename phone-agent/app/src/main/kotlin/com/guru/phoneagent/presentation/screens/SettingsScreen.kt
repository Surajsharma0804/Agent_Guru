package com.guru.phoneagent.presentation.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Settings Screen for GURU Phone Agent
 * 
 * Placeholder implementation for application settings and configuration.
 * Production implementation would include comprehensive security settings and preferences.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    settings: Map<String, Any>,
    onSettingChanged: (String, Any) -> Unit,
    onResetSettings: () -> Unit,
    onNavigateBack: () -> Unit
) {
    var showResetDialog by remember { mutableStateOf(false) }
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onNavigateBack) {
                Icon(
                    imageVector = Icons.Default.ArrowBack,
                    contentDescription = "Back"
                )
            }
            
            Text(
                text = "Settings",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center
            )
            
            // Spacer to balance the back button
            Spacer(modifier = Modifier.width(48.dp))
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Security Settings Section
        SettingsSection(title = "Security") {
            SettingsItem(
                title = "Biometric Authentication",
                description = "Use fingerprint or face recognition for authentication",
                icon = Icons.Default.Fingerprint,
                trailing = {
                    Switch(
                        checked = settings["biometric_enabled"] as? Boolean ?: true,
                        onCheckedChange = { onSettingChanged("biometric_enabled", it) }
                    )
                }
            )
            
            SettingsItem(
                title = "Auto-Lock Timeout",
                description = "Automatically lock after inactivity",
                icon = Icons.Default.Timer,
                trailing = {
                    Text(
                        text = "${settings["auto_lock_timeout"] as? Int ?: 5} min",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            )
            
            SettingsItem(
                title = "Security Notifications",
                description = "Show notifications for security events",
                icon = Icons.Default.Notifications,
                trailing = {
                    Switch(
                        checked = settings["security_notifications"] as? Boolean ?: true,
                        onCheckedChange = { onSettingChanged("security_notifications", it) }
                    )
                }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Communication Settings Section
        SettingsSection(title = "Communication") {
            SettingsItem(
                title = "Connection Timeout",
                description = "Timeout for desktop agent connections",
                icon = Icons.Default.Wifi,
                trailing = {
                    Text(
                        text = "${settings["connection_timeout"] as? Int ?: 30}s",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            )
            
            SettingsItem(
                title = "Auto-Reconnect",
                description = "Automatically reconnect to desktop agent",
                icon = Icons.Default.Sync,
                trailing = {
                    Switch(
                        checked = settings["auto_reconnect"] as? Boolean ?: true,
                        onCheckedChange = { onSettingChanged("auto_reconnect", it) }
                    )
                }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Voice Settings Section
        SettingsSection(title = "Voice Processing") {
            SettingsItem(
                title = "Voice Commands",
                description = "Enable voice command processing",
                icon = Icons.Default.Mic,
                trailing = {
                    Switch(
                        checked = settings["voice_commands"] as? Boolean ?: true,
                        onCheckedChange = { onSettingChanged("voice_commands", it) }
                    )
                }
            )
            
            SettingsItem(
                title = "Voice Confidence Threshold",
                description = "Minimum confidence for voice recognition",
                icon = Icons.Default.VolumeUp,
                trailing = {
                    Text(
                        text = "${((settings["voice_confidence"] as? Float ?: 0.8f) * 100).toInt()}%",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Privacy Settings Section
        SettingsSection(title = "Privacy") {
            SettingsItem(
                title = "Audit Logging",
                description = "Log all security and user events",
                icon = Icons.Default.History,
                trailing = {
                    Switch(
                        checked = settings["audit_logging"] as? Boolean ?: true,
                        onCheckedChange = { onSettingChanged("audit_logging", it) }
                    )
                }
            )
            
            SettingsItem(
                title = "Data Retention",
                description = "How long to keep audit logs and data",
                icon = Icons.Default.Storage,
                trailing = {
                    Text(
                        text = "${settings["data_retention_days"] as? Int ?: 30} days",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            )
        }
        
        Spacer(modifier = Modifier.height(32.dp))
        
        // Reset Settings
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
                    text = "Reset Settings",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Text(
                    text = "Reset all settings to their default values. This action cannot be undone.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f)
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                OutlinedButton(
                    onClick = { showResetDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.onErrorContainer
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.RestartAlt,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Reset All Settings")
                }
            }
        }
    }
    
    // Reset Confirmation Dialog
    if (showResetDialog) {
        AlertDialog(
            onDismissRequest = { showResetDialog = false },
            title = {
                Text("Reset Settings")
            },
            text = {
                Text("Are you sure you want to reset all settings to their default values? This action cannot be undone.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onResetSettings()
                        showResetDialog = false
                    }
                ) {
                    Text("Reset")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showResetDialog = false }
                ) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
private fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        Card(
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(vertical = 8.dp)
            ) {
                content()
            }
        }
    }
}

@Composable
private fun SettingsItem(
    title: String,
    description: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    trailing: @Composable () -> Unit = {}
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Spacer(modifier = Modifier.width(16.dp))
        
        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium
            )
            
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        
        Spacer(modifier = Modifier.width(16.dp))
        
        trailing()
    }
}