/**
 * @fileoverview Core type definitions for the Guru Personal Assistant system
 */

// Device and identity types
export interface DeviceIdentity {
  readonly deviceId: string;
  readonly publicKey: Uint8Array;
  readonly deviceType: 'desktop' | 'mobile' | 'server';
  readonly capabilities: DeviceCapabilities;
}

export interface DeviceCapabilities {
  readonly biometric: BiometricCapabilities;
  readonly crypto: CryptoCapabilities;
  readonly network: NetworkCapabilities;
}

export interface BiometricCapabilities {
  readonly fingerprint: boolean;
  readonly faceId: boolean;
  readonly voiceId: boolean;
  readonly touchId: boolean;
}

export interface CryptoCapabilities {
  readonly keyGeneration: boolean;
  readonly signing: boolean;
  readonly encryption: boolean;
  readonly secureStorage: boolean;
}

export interface NetworkCapabilities {
  readonly bluetooth: boolean;
  readonly wifi: boolean;
  readonly cellular: boolean;
  readonly nfc: boolean;
}

// Authentication and authorization types
export interface AuthenticationRequest {
  readonly requestId: string;
  readonly deviceId: string;
  readonly command: string;
  readonly timestamp: number;
  readonly signature: Uint8Array;
}

export interface AuthenticationResponse {
  readonly requestId: string;
  readonly approved: boolean;
  readonly timestamp: number;
  readonly signature?: Uint8Array;
  readonly reason?: string;
}

// Communication protocol types
export interface SecureMessage {
  readonly messageId: string;
  readonly senderId: string;
  readonly recipientId: string;
  readonly payload: Uint8Array;
  readonly signature: Uint8Array;
  readonly timestamp: number;
}

// Error types
export class GuruError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'GuruError';
  }
}

export class AuthenticationError extends GuruError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'AUTHENTICATION_ERROR', details);
    this.name = 'AuthenticationError';
  }
}

export class CryptographicError extends GuruError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'CRYPTOGRAPHIC_ERROR', details);
    this.name = 'CryptographicError';
  }
}

export class NetworkError extends GuruError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'NETWORK_ERROR', details);
    this.name = 'NetworkError';
  }
}