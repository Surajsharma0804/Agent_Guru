/**
 * @fileoverview Security configuration and utilities
 */

export interface SecurityPolicy {
  readonly allowedOrigins: string[];
  readonly maxRequestSize: number;
  readonly rateLimiting: RateLimitConfig;
  readonly authentication: AuthConfig;
  readonly encryption: EncryptionConfig;
}

export interface RateLimitConfig {
  readonly enabled: boolean;
  readonly maxRequests: number;
  readonly windowMs: number;
  readonly skipSuccessfulRequests: boolean;
}

export interface AuthConfig {
  readonly required: boolean;
  readonly methods: AuthMethod[];
  readonly sessionTimeout: number;
  readonly maxFailedAttempts: number;
}

export type AuthMethod = 'biometric' | 'password' | 'certificate' | 'token';

export interface EncryptionConfig {
  readonly algorithm: string;
  readonly keySize: number;
  readonly rotationInterval: number;
}

export class SecurityValidator {
  constructor(private readonly policy: SecurityPolicy) {}
  
  validateOrigin(origin: string): boolean {
    return this.policy.allowedOrigins.includes('*') || 
           this.policy.allowedOrigins.includes(origin);
  }
  
  validateRequestSize(size: number): boolean {
    return size <= this.policy.maxRequestSize;
  }
  
  validateAuthMethod(method: AuthMethod): boolean {
    return this.policy.authentication.methods.includes(method);
  }
  
  isRateLimitEnabled(): boolean {
    return this.policy.rateLimiting.enabled;
  }
  
  getRateLimitConfig(): RateLimitConfig {
    return this.policy.rateLimiting;
  }
}

export const DEFAULT_SECURITY_POLICY: SecurityPolicy = {
  allowedOrigins: ['localhost', '127.0.0.1'],
  maxRequestSize: 1024 * 1024, // 1MB
  rateLimiting: {
    enabled: true,
    maxRequests: 100,
    windowMs: 60000, // 1 minute
    skipSuccessfulRequests: false,
  },
  authentication: {
    required: true,
    methods: ['biometric', 'certificate'],
    sessionTimeout: 3600000, // 1 hour
    maxFailedAttempts: 3,
  },
  encryption: {
    algorithm: 'AES-256-GCM',
    keySize: 256,
    rotationInterval: 86400000, // 24 hours
  },
};