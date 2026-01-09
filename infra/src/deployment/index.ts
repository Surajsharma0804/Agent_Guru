/**
 * @fileoverview Deployment configuration interfaces
 */

export interface DeploymentConfig {
  readonly environment: 'development' | 'staging' | 'production';
  readonly region: string;
  readonly security: SecurityConfig;
  readonly monitoring: MonitoringConfig;
}

export interface SecurityConfig {
  readonly encryptionAtRest: boolean;
  readonly encryptionInTransit: boolean;
  readonly accessLogging: boolean;
  readonly auditTrail: boolean;
}

export interface MonitoringConfig {
  readonly metricsEnabled: boolean;
  readonly loggingLevel: 'debug' | 'info' | 'warn' | 'error';
  readonly alerting: AlertingConfig;
}

export interface AlertingConfig {
  readonly enabled: boolean;
  readonly channels: string[];
  readonly thresholds: Record<string, number>;
}