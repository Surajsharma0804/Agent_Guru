/**
 * @fileoverview Network utilities for the Guru Personal Assistant system
 */

import { NetworkError } from '../types/index.js';
import { NETWORK_CONSTANTS } from '../constants/index.js';

/**
 * Validates a network address format
 */
export function isValidAddress(address: string): boolean {
  // IPv4 pattern
  const ipv4Pattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  
  // IPv6 pattern (simplified)
  const ipv6Pattern = /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/;
  
  // Hostname pattern
  const hostnamePattern = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
  
  return ipv4Pattern.test(address) || ipv6Pattern.test(address) || hostnamePattern.test(address);
}

/**
 * Validates a port number
 */
export function isValidPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

/**
 * Creates a network endpoint string
 */
export function createEndpoint(address: string, port: number): string {
  if (!isValidAddress(address)) {
    throw new NetworkError('Invalid address format', { address });
  }
  
  if (!isValidPort(port)) {
    throw new NetworkError('Invalid port number', { port });
  }
  
  // Handle IPv6 addresses
  if (address.includes(':') && !address.startsWith('[')) {
    return `[${address}]:${port}`;
  }
  
  return `${address}:${port}`;
}

/**
 * Parses a network endpoint string
 */
export function parseEndpoint(endpoint: string): { address: string; port: number } {
  let address: string;
  let portStr: string;
  
  // Handle IPv6 addresses in brackets
  if (endpoint.startsWith('[')) {
    const closeBracket = endpoint.indexOf(']');
    if (closeBracket === -1 || endpoint[closeBracket + 1] !== ':') {
      throw new NetworkError('Invalid IPv6 endpoint format', { endpoint });
    }
    address = endpoint.slice(1, closeBracket);
    portStr = endpoint.slice(closeBracket + 2);
  } else {
    const lastColon = endpoint.lastIndexOf(':');
    if (lastColon === -1) {
      throw new NetworkError('Invalid endpoint format', { endpoint });
    }
    address = endpoint.slice(0, lastColon);
    portStr = endpoint.slice(lastColon + 1);
  }
  
  const port = parseInt(portStr, 10);
  
  if (!isValidAddress(address)) {
    throw new NetworkError('Invalid address in endpoint', { address });
  }
  
  if (!isValidPort(port)) {
    throw new NetworkError('Invalid port in endpoint', { port });
  }
  
  return { address, port };
}

/**
 * Creates a timeout promise that rejects after the specified duration
 */
export function createTimeout(ms: number): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => {
      reject(new NetworkError('Operation timed out', { timeout: ms }));
    }, ms);
  });
}

/**
 * Wraps a promise with a timeout
 */
export async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number = NETWORK_CONSTANTS.CONNECTION_TIMEOUT
): Promise<T> {
  return Promise.race([promise, createTimeout(timeoutMs)]);
}

/**
 * Validates message size
 */
export function validateMessageSize(size: number): void {
  if (size > NETWORK_CONSTANTS.MAX_MESSAGE_SIZE) {
    throw new NetworkError('Message too large', { 
      size, 
      maxSize: NETWORK_CONSTANTS.MAX_MESSAGE_SIZE 
    });
  }
}

/**
 * Encodes a message with length prefix
 */
export function encodeMessage(data: Uint8Array): Uint8Array {
  validateMessageSize(data.length);
  
  const lengthBuffer = new ArrayBuffer(4);
  const lengthView = new DataView(lengthBuffer);
  lengthView.setUint32(0, data.length, false); // Big-endian
  
  const result = new Uint8Array(4 + data.length);
  result.set(new Uint8Array(lengthBuffer), 0);
  result.set(data, 4);
  
  return result;
}

/**
 * Decodes a message with length prefix
 */
export function decodeMessage(data: Uint8Array): { message: Uint8Array; remaining: Uint8Array } {
  if (data.length < 4) {
    throw new NetworkError('Insufficient data for message length', { available: data.length });
  }
  
  const lengthView = new DataView(data.buffer, data.byteOffset, 4);
  const messageLength = lengthView.getUint32(0, false); // Big-endian
  
  validateMessageSize(messageLength);
  
  if (data.length < 4 + messageLength) {
    throw new NetworkError('Insufficient data for complete message', { 
      available: data.length - 4, 
      required: messageLength 
    });
  }
  
  const message = data.slice(4, 4 + messageLength);
  const remaining = data.slice(4 + messageLength);
  
  return { message, remaining };
}