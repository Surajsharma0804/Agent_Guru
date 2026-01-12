package com.guru.phoneagent.presentation.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.guru.phoneagent.presentation.theme.AuthorityColors
import com.guru.phoneagent.presentation.theme.SecurityColors
import com.guru.phoneagent.presentation.viewmodels.AuthorityState
import com.guru.phoneagent.presentation.viewmodels.ConnectionState

/**
 * Home Screen for GURU Phone Agent
 * 
 * Production-grade main interface implementing security-focused design,
 * real-time status monitoring, and comprehensive control capabilities.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    connectionState: ConnectionState,
    authorityState: AuthorityState,
    onNavigateToSettings: () -> Unit,
    onNavigateToSecurity: () -> Unit,
    onNavigateToPairing: () -> Unit,
    onEmergencyStop: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "GURU",
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    text = "Phone Agent",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            IconButton(onClick = onNavigateToSettings) {
                Icon(
                    imageVector = Icons.Default.Settings,
                    contentDescription = "Settings"
                )
            }
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Connection Status Card
        ConnectionStatusCard(
            connectionState = connectionState,
            onNavigateToPairing = onNavigateToPairing
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Authority Status Card
        AuthorityStatusCard(
            authorityState = authorityState
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Quick Actions
        Text(
            text = "Quick Actions",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(12.dp))
        
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            QuickActionCard(
                title = "Security",
                description = "View audit logs and security status",
                icon = Icons.Default.Security,
                onClick = onNavigateToSecurity,
                modifier = Modifier.weight(1f)
            )
            
            QuickActionCard(
                title = "Pairing",
                description = "Manage device connections",
                icon = Icons.Default.QrCodeScanner,
                onClick = onNavigateToPairing,
                modifier = Modifier.weight(1f)
            )
        }
        
        Spacer(modifier = Modifier.height(32.dp))
        
        // Emergency Stop
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer
            )
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    imageVector = Icons.Default.Emergency,
                    contentDescription = "Emergency Stop",
                    modifier = Modifier.size(32.dp),
                    tint = MaterialTheme.colorScheme.onErrorContainer
                )
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Text(
                    text = "Emergency Stop",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
                
                Text(
                    text = "Immediately disable all automation and secure the system",
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f)
                )
                
                Spacer(modifier = Modifier.height(12.dp))
                
                Button(
                    onClick = onEmergencyStop,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(
                        imageVector = Icons.Default.Stop,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("EMERGENCY STOP")
                }
            }
        }
    }
}

@Composable
private fun ConnectionStatusCard(
    connectionState: ConnectionState,
    onNavigateToPairing: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = when (connectionState) {
                ConnectionState.CONNECTED -> SecurityColors.secureContainer
                ConnectionState.CONNECTING -> SecurityColors.warningContainer
                ConnectionState.ERROR -> SecurityColors.criticalContainer
                ConnectionState.DISCONNECTED -> SecurityColors.unknownContainer
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = when (connectionState) {
                    ConnectionState.CONNECTED -> Icons.Default.Wifi
                    ConnectionState.CONNECTING -> Icons.Default.WifiFind
                    ConnectionState.ERROR -> Icons.Default.WifiOff
                    ConnectionState.DISCONNECTED -> Icons.Default.WifiOff
                },
                contentDescription = "Connection Status",
                modifier = Modifier.size(32.dp),
                tint = when (connectionState) {
                    ConnectionState.CONNECTED -> SecurityColors.secure
                    ConnectionState.CONNECTING -> SecurityColors.warning
                    ConnectionState.ERROR -> SecurityColors.critical
                    ConnectionState.DISCONNECTED -> SecurityColors.unknown
                }
            )
            
            Spacer(modifier = Modifier.width(16.dp))
            
            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = when (connectionState) {
                        ConnectionState.CONNECTED -> "Connected to Desktop"
                        ConnectionState.CONNECTING -> "Connecting..."
                        ConnectionState.ERROR -> "Connection Error"
                        ConnectionState.DISCONNECTED -> "Not Connected"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                
                Text(
                    text = when (connectionState) {
                        ConnectionState.CONNECTED -> "Secure communication established"
                        ConnectionState.CONNECTING -> "Establishing secure connection"
                        ConnectionState.ERROR -> "Failed to connect to desktop agent"
                        ConnectionState.DISCONNECTED -> "No desktop agent paired"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            if (connectionState != ConnectionState.CONNECTED) {
                TextButton(onClick = onNavigateToPairing) {
                    Text("Pair Device")
                }
            }
        }
    }
}

@Composable
private fun AuthorityStatusCard(
    authorityState: AuthorityState
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = when (authorityState) {
                AuthorityState.ARMED -> SecurityColors.secureContainer
                AuthorityState.VERIFICATION -> SecurityColors.warningContainer
                AuthorityState.LOCKED -> SecurityColors.unknownContainer
                AuthorityState.INTRUSION_DETECTED -> SecurityColors.criticalContainer
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = when (authorityState) {
                    AuthorityState.ARMED -> Icons.Default.Security
                    AuthorityState.VERIFICATION -> Icons.Default.Fingerprint
                    AuthorityState.LOCKED -> Icons.Default.Lock
                    AuthorityState.INTRUSION_DETECTED -> Icons.Default.Warning
                },
                contentDescription = "Authority Status",
                modifier = Modifier.size(32.dp),
                tint = when (authorityState) {
                    AuthorityState.ARMED -> AuthorityColors.armed
                    AuthorityState.VERIFICATION -> AuthorityColors.verification
                    AuthorityState.LOCKED -> AuthorityColors.locked
                    AuthorityState.INTRUSION_DETECTED -> AuthorityColors.intrusion
                }
            )
            
            Spacer(modifier = Modifier.width(16.dp))
            
            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = when (authorityState) {
                        AuthorityState.ARMED -> "Authority Granted"
                        AuthorityState.VERIFICATION -> "Verifying Identity"
                        AuthorityState.LOCKED -> "Authority Locked"
                        AuthorityState.INTRUSION_DETECTED -> "Intrusion Detected"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                
                Text(
                    text = when (authorityState) {
                        AuthorityState.ARMED -> "Automation enabled with full authority"
                        AuthorityState.VERIFICATION -> "Multi-factor authentication in progress"
                        AuthorityState.LOCKED -> "No automation authority granted"
                        AuthorityState.INTRUSION_DETECTED -> "Security breach detected - system locked"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun QuickActionCard(
    title: String,
    description: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onClick,
        modifier = modifier
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = title,
                modifier = Modifier.size(32.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            
            Spacer(modifier = Modifier.height(4.dp))
            
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}