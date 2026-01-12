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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.guru.phoneagent.audit.AuditEntry
import com.guru.phoneagent.presentation.viewmodels.SecurityState
import java.text.SimpleDateFormat
import java.util.*

/**
 * Security and Audit Screen for GURU Phone Agent
 * 
 * Placeholder implementation for security monitoring and audit log viewing.
 * Production implementation would include comprehensive security metrics and log analysis.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SecurityScreen(
    securityState: SecurityState,
    auditEvents: List<AuditEntry>,
    onRefreshAuditLog: () -> Unit,
    onExportAuditLog: () -> Unit,
    onNavigateBack: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
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
                text = "Security & Audit",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center
            )
            
            IconButton(onClick = onRefreshAuditLog) {
                Icon(
                    imageVector = Icons.Default.Refresh,
                    contentDescription = "Refresh"
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Security Status Card
        SecurityStatusCard(securityState = securityState)
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Audit Log Section
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Recent Audit Events",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
            
            TextButton(onClick = onExportAuditLog) {
                Icon(
                    imageVector = Icons.Default.Download,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("Export")
            }
        }
        
        Spacer(modifier = Modifier.height(8.dp))
        
        // Audit Events List
        if (auditEvents.isEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        imageVector = Icons.Default.History,
                        contentDescription = "No Events",
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Text(
                        text = "No audit events available",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(auditEvents) { event ->
                    AuditEventCard(event = event)
                }
            }
        }
    }
}

@Composable
private fun SecurityStatusCard(securityState: SecurityState) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Security,
                    contentDescription = "Security Status",
                    modifier = Modifier.size(24.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                
                Spacer(modifier = Modifier.width(8.dp))
                
                Text(
                    text = "Security Status",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Security Metrics
            SecurityMetricRow(
                label = "Biometric Authentication",
                value = if (securityState.biometricAvailable) "Available" else "Not Available",
                isSecure = securityState.biometricAvailable
            )
            
            SecurityMetricRow(
                label = "Device Security",
                value = if (securityState.deviceSecure) "Secure" else "Not Secure",
                isSecure = securityState.deviceSecure
            )
            
            SecurityMetricRow(
                label = "Last Security Check",
                value = if (securityState.lastSecurityCheck > 0) {
                    SimpleDateFormat("MMM dd, HH:mm", Locale.getDefault())
                        .format(Date(securityState.lastSecurityCheck))
                } else {
                    "Never"
                },
                isSecure = securityState.lastSecurityCheck > 0
            )
            
            if (securityState.securityAlerts.isNotEmpty()) {
                Spacer(modifier = Modifier.height(12.dp))
                
                Text(
                    text = "Security Alerts",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.error
                )
                
                securityState.securityAlerts.forEach { alert ->
                    Text(
                        text = "• $alert",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(start = 8.dp, top = 4.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun SecurityMetricRow(
    label: String,
    value: String,
    isSecure: Boolean
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Row(
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (isSecure) Icons.Default.CheckCircle else Icons.Default.Warning,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
                tint = if (isSecure) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            )
            
            Spacer(modifier = Modifier.width(4.dp))
            
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = if (isSecure) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            )
        }
    }
}

@Composable
private fun AuditEventCard(event: AuditEntry) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = getEventIcon(event.category, event.severity),
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                        tint = getEventColor(event.severity)
                    )
                    
                    Spacer(modifier = Modifier.width(8.dp))
                    
                    Text(
                        text = event.eventType,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Medium
                    )
                }
                
                Text(
                    text = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
                        .format(Date(event.timestamp)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            if (event.details.isNotEmpty()) {
                Spacer(modifier = Modifier.height(4.dp))
                
                Text(
                    text = event.details.entries.joinToString(", ") { "${it.key}: ${it.value}" },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2
                )
            }
        }
    }
}

@Composable
private fun getEventIcon(category: String, severity: String) = when {
    category == "SECURITY" -> Icons.Default.Security
    category == "SYSTEM" -> Icons.Default.Computer
    category == "USER_ACTION" -> Icons.Default.Person
    category == "COMMUNICATION" -> Icons.Default.Wifi
    severity == "CRITICAL" || severity == "ERROR" -> Icons.Default.Error
    severity == "WARNING" -> Icons.Default.Warning
    else -> Icons.Default.Info
}

@Composable
private fun getEventColor(severity: String) = when (severity) {
    "CRITICAL", "ERROR" -> MaterialTheme.colorScheme.error
    "WARNING" -> MaterialTheme.colorScheme.tertiary
    "INFO" -> MaterialTheme.colorScheme.primary
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}