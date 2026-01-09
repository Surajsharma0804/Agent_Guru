/**
 * @fileoverview Utility functions for the Guru Personal Assistant system
 */

import { GuruError } from '../types/index.js';

/**
 * Generates a cryptographically secure random identifier
 */
export function generateSecureId(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Validates a device ID format
 */
export function isValidDeviceId(deviceId: string): boolean {
  return /^[a-f0-9]{32}$/.test(deviceId);
}

/**
 * Validates a timestamp is within acceptable range
 */
export function isValidTimestamp(timestamp: number, maxAgeMs: number = 300000): boolean {
  const now = Date.now();
  const age = Math.abs(now - timestamp);
  return age <= maxAgeMs;
}

/**
 * Securely compares two byte arrays in constant time
 */
export function constantTimeEquals(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) {
    return false;
  }
  
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a[i]! ^ b[i]!;
  }
  
  return result === 0;
}

/**
 * Converts a hex string to Uint8Array
 */
export function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) {
    throw new GuruError('Invalid hex string length', 'INVALID_HEX');
  }
  
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    const byte = parseInt(hex.slice(i, i + 2), 16);
    if (isNaN(byte)) {
      throw new GuruError('Invalid hex character', 'INVALID_HEX');
    }
    bytes[i / 2] = byte;
  }
  
  return bytes;
}

/**
 * Converts Uint8Array to hex string
 */
export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Safely encodes a string to UTF-8 bytes
 */
export function encodeUtf8(str: string): Uint8Array {
  return new TextEncoder().encode(str);
}

/**
 * Safely decodes UTF-8 bytes to string
 */
export function decodeUtf8(bytes: Uint8Array): string {
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
}