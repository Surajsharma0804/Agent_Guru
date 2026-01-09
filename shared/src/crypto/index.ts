/**
 * @fileoverview Cryptographic utilities for the Guru Personal Assistant system
 */

import { CryptographicError } from '../types/index.js';
import { CRYPTO_CONSTANTS } from '../constants/index.js';

/**
 * Generates a new Ed25519 key pair for device identity
 */
export async function generateKeyPair(): Promise<CryptoKeyPair> {
  try {
    return await crypto.subtle.generateKey(
      {
        name: 'Ed25519',
        namedCurve: 'Ed25519',
      },
      true,
      ['sign', 'verify']
    );
  } catch (error) {
    throw new CryptographicError('Failed to generate key pair', { error });
  }
}

/**
 * Exports a public key to raw bytes
 */
export async function exportPublicKey(publicKey: CryptoKey): Promise<Uint8Array> {
  try {
    const exported = await crypto.subtle.exportKey('raw', publicKey);
    return new Uint8Array(exported);
  } catch (error) {
    throw new CryptographicError('Failed to export public key', { error });
  }
}

/**
 * Imports a public key from raw bytes
 */
export async function importPublicKey(keyBytes: Uint8Array): Promise<CryptoKey> {
  try {
    return await crypto.subtle.importKey(
      'raw',
      keyBytes,
      {
        name: 'Ed25519',
        namedCurve: 'Ed25519',
      },
      false,
      ['verify']
    );
  } catch (error) {
    throw new CryptographicError('Failed to import public key', { error });
  }
}

/**
 * Signs data with a private key
 */
export async function signData(privateKey: CryptoKey, data: Uint8Array): Promise<Uint8Array> {
  try {
    const signature = await crypto.subtle.sign('Ed25519', privateKey, data);
    return new Uint8Array(signature);
  } catch (error) {
    throw new CryptographicError('Failed to sign data', { error });
  }
}

/**
 * Verifies a signature with a public key
 */
export async function verifySignature(
  publicKey: CryptoKey,
  signature: Uint8Array,
  data: Uint8Array
): Promise<boolean> {
  try {
    return await crypto.subtle.verify('Ed25519', publicKey, signature, data);
  } catch (error) {
    throw new CryptographicError('Failed to verify signature', { error });
  }
}

/**
 * Generates a secure random salt
 */
export function generateSalt(): Uint8Array {
  const salt = new Uint8Array(CRYPTO_CONSTANTS.SALT_SIZE);
  crypto.getRandomValues(salt);
  return salt;
}

/**
 * Derives a key from a password using PBKDF2
 */
export async function deriveKey(
  password: string,
  salt: Uint8Array,
  iterations: number = 100000
): Promise<CryptoKey> {
  try {
    const passwordKey = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      'PBKDF2',
      false,
      ['deriveKey']
    );

    return await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt,
        iterations,
        hash: 'SHA-256',
      },
      passwordKey,
      {
        name: 'AES-GCM',
        length: 256,
      },
      false,
      ['encrypt', 'decrypt']
    );
  } catch (error) {
    throw new CryptographicError('Failed to derive key', { error });
  }
}

/**
 * Encrypts data using AES-GCM
 */
export async function encryptData(
  key: CryptoKey,
  data: Uint8Array,
  additionalData?: Uint8Array
): Promise<{ ciphertext: Uint8Array; nonce: Uint8Array }> {
  try {
    const nonce = new Uint8Array(CRYPTO_CONSTANTS.NONCE_SIZE);
    crypto.getRandomValues(nonce);

    const ciphertext = await crypto.subtle.encrypt(
      {
        name: 'AES-GCM',
        iv: nonce,
        additionalData,
      },
      key,
      data
    );

    return {
      ciphertext: new Uint8Array(ciphertext),
      nonce,
    };
  } catch (error) {
    throw new CryptographicError('Failed to encrypt data', { error });
  }
}

/**
 * Decrypts data using AES-GCM
 */
export async function decryptData(
  key: CryptoKey,
  ciphertext: Uint8Array,
  nonce: Uint8Array,
  additionalData?: Uint8Array
): Promise<Uint8Array> {
  try {
    const plaintext = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: nonce,
        additionalData,
      },
      key,
      ciphertext
    );

    return new Uint8Array(plaintext);
  } catch (error) {
    throw new CryptographicError('Failed to decrypt data', { error });
  }
}

/**
 * Computes SHA-256 hash of data
 */
export async function hashData(data: Uint8Array): Promise<Uint8Array> {
  try {
    const hash = await crypto.subtle.digest('SHA-256', data);
    return new Uint8Array(hash);
  } catch (error) {
    throw new CryptographicError('Failed to hash data', { error });
  }
}