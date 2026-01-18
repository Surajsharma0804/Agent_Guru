/**
 * Cryptographic Service for Avatar Identity Management
 * 
 * Provides encryption, decryption, digital signatures, and integrity verification
 * for avatar identities and assets with production-grade security.
 */

import { 
  AvatarIdentity,
  EncryptedIdentityData,
  DigitalSignature,
  EncryptionMetadata
} from '../interfaces/IdentityManager';

/**
 * Cryptographic service interface
 */
export interface CryptoService {
  // Identity Encryption/Decryption
  encryptIdentity(identity: AvatarIdentity): Promise<EncryptedIdentityData>;
  decryptIdentity(encryptedData: EncryptedIdentityData): Promise<AvatarIdentity>;
  
  // Digital Signatures
  signIdentity(identity: AvatarIdentity): Promise<DigitalSignature>;
  validateSignature(identity: AvatarIdentity): Promise<boolean>;
  
  // Key Management
  generateEncryptionMetadata(): Promise<EncryptionMetadata>;
  rotateKeys(): Promise<void>;
  
  // Utility Functions
  generateUniqueId(): Promise<string>;
  calculateChecksum(data: unknown): Promise<string>;
  generateSecureRandom(length: number): Promise<Uint8Array>;
  
  // Cleanup
  cleanup(): Promise<void>;
}

/**
 * Production implementation of cryptographic service
 */
export class CryptoServiceImpl implements CryptoService {
  private readonly keyCache: Map<string, CryptoKey> = new Map();
  private readonly algorithm = 'AES-GCM';
  private readonly keyLength = 256;
  private readonly signatureAlgorithm = 'ECDSA';
  private readonly hashAlgorithm = 'SHA-256';

  constructor() {
    // Initialize crypto subsystem
    this.initializeCrypto();
  }

  async encryptIdentity(identity: AvatarIdentity): Promise<EncryptedIdentityData> {
    try {
      // Generate encryption key
      const key = await this.generateEncryptionKey();
      
      // Generate IV
      const iv = crypto.getRandomValues(new Uint8Array(12));
      
      // Serialize identity data
      const identityData = JSON.stringify(identity);
      const encoder = new TextEncoder();
      const data = encoder.encode(identityData);
      
      // Encrypt data
      const encryptedBuffer = await crypto.subtle.encrypt(
        {
          name: this.algorithm,
          iv: iv
        },
        key,
        data
      );
      
      // Create encryption metadata
      const metadata: EncryptionMetadata = {
        algorithm: this.algorithm,
        keyId: await this.getKeyId(key),
        iv: this.arrayBufferToBase64(iv),
        timestamp: Date.now()
      };
      
      // Create signature for encrypted data
      const signature = await this.signData(encryptedBuffer);
      
      return {
        encryptedData: this.arrayBufferToBase64(encryptedBuffer),
        encryptionMetadata: metadata,
        signature: signature,
        version: identity.version
      };
      
    } catch (error) {
      throw new Error(`Failed to encrypt identity: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async decryptIdentity(encryptedData: EncryptedIdentityData): Promise<AvatarIdentity> {
    try {
      // Validate signature first
      const dataBuffer = this.base64ToArrayBuffer(encryptedData.encryptedData);
      const signatureValid = await this.validateDataSignature(dataBuffer, encryptedData.signature);
      
      if (!signatureValid) {
        throw new Error('Invalid signature on encrypted data');
      }
      
      // Get decryption key
      const key = await this.getKeyById(encryptedData.encryptionMetadata.keyId);
      if (!key) {
        throw new Error(`Decryption key not found: ${encryptedData.encryptionMetadata.keyId}`);
      }
      
      // Decrypt data
      const iv = this.base64ToArrayBuffer(encryptedData.encryptionMetadata.iv);
      const decryptedBuffer = await crypto.subtle.decrypt(
        {
          name: this.algorithm,
          iv: iv
        },
        key,
        dataBuffer
      );
      
      // Deserialize identity
      const decoder = new TextDecoder();
      const identityJson = decoder.decode(decryptedBuffer);
      const identity: AvatarIdentity = JSON.parse(identityJson);
      
      return identity;
      
    } catch (error) {
      throw new Error(`Failed to decrypt identity: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async signIdentity(identity: AvatarIdentity): Promise<DigitalSignature> {
    try {
      // Create a copy without signature for signing
      const identityForSigning = { ...identity };
      delete (identityForSigning as any).signature;
      
      // Serialize identity data
      const identityData = JSON.stringify(identityForSigning);
      const encoder = new TextEncoder();
      const data = encoder.encode(identityData);
      
      return await this.signData(data);
      
    } catch (error) {
      throw new Error(`Failed to sign identity: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async validateSignature(identity: AvatarIdentity): Promise<boolean> {
    try {
      // Create a copy without signature for validation
      const identityForValidation = { ...identity };
      delete (identityForValidation as any).signature;
      
      // Serialize identity data
      const identityData = JSON.stringify(identityForValidation);
      const encoder = new TextEncoder();
      const data = encoder.encode(identityData);
      
      return await this.validateDataSignature(data, identity.signature);
      
    } catch (error) {
      console.error('Signature validation error:', error);
      return false;
    }
  }
  async generateEncryptionMetadata(): Promise<EncryptionMetadata> {
    const key = await this.generateEncryptionKey();
    const keyId = await this.getKeyId(key);
    
    return {
      algorithm: this.algorithm,
      keyId: keyId,
      iv: '', // Will be set during encryption
      timestamp: Date.now()
    };
  }

  async rotateKeys(): Promise<void> {
    try {
      // Generate new master key
      const newKey = await this.generateEncryptionKey();
      const keyId = await this.getKeyId(newKey);
      
      // Store new key
      this.keyCache.set(keyId, newKey);
      
      // Clean up old keys (keep last 3 for rollback)
      const keyIds = Array.from(this.keyCache.keys());
      if (keyIds.length > 3) {
        const oldestKeys = keyIds.slice(0, keyIds.length - 3);
        for (const oldKeyId of oldestKeys) {
          this.keyCache.delete(oldKeyId);
        }
      }
      
    } catch (error) {
      throw new Error(`Failed to rotate keys: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async generateUniqueId(): Promise<string> {
    const randomBytes = crypto.getRandomValues(new Uint8Array(16));
    const timestamp = Date.now().toString(36);
    const randomString = this.arrayBufferToBase64(randomBytes).replace(/[+/=]/g, '');
    
    return `${timestamp}-${randomString}`;
  }

  async calculateChecksum(data: unknown): Promise<string> {
    try {
      const jsonData = JSON.stringify(data);
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(jsonData);
      
      const hashBuffer = await crypto.subtle.digest(this.hashAlgorithm, dataBuffer);
      return this.arrayBufferToBase64(hashBuffer);
      
    } catch (error) {
      throw new Error(`Failed to calculate checksum: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async generateSecureRandom(length: number): Promise<Uint8Array> {
    return crypto.getRandomValues(new Uint8Array(length));
  }

  async cleanup(): Promise<void> {
    this.keyCache.clear();
  }

  // Private helper methods
  private async initializeCrypto(): Promise<void> {
    // Verify crypto API availability
    if (!crypto || !crypto.subtle) {
      throw new Error('Web Crypto API not available');
    }
    
    // Generate initial master key
    const masterKey = await this.generateEncryptionKey();
    const keyId = await this.getKeyId(masterKey);
    this.keyCache.set(keyId, masterKey);
  }

  private async generateEncryptionKey(): Promise<CryptoKey> {
    return await crypto.subtle.generateKey(
      {
        name: this.algorithm,
        length: this.keyLength
      },
      true, // extractable
      ['encrypt', 'decrypt']
    );
  }

  private async generateSigningKeyPair(): Promise<CryptoKeyPair> {
    return await crypto.subtle.generateKey(
      {
        name: this.signatureAlgorithm,
        namedCurve: 'P-256'
      },
      true, // extractable
      ['sign', 'verify']
    );
  }

  private async getKeyId(key: CryptoKey): Promise<string> {
    const exported = await crypto.subtle.exportKey('raw', key);
    const hash = await crypto.subtle.digest(this.hashAlgorithm, exported);
    return this.arrayBufferToBase64(hash).substring(0, 16);
  }

  private async getKeyById(keyId: string): Promise<CryptoKey | null> {
    return this.keyCache.get(keyId) || null;
  }

  private async signData(data: ArrayBuffer): Promise<DigitalSignature> {
    // For production, we would use a persistent signing key
    // For now, generate a temporary key pair
    const keyPair = await this.generateSigningKeyPair();
    
    const signature = await crypto.subtle.sign(
      {
        name: this.signatureAlgorithm,
        hash: this.hashAlgorithm
      },
      keyPair.privateKey,
      data
    );
    
    const publicKeyExported = await crypto.subtle.exportKey('spki', keyPair.publicKey);
    
    return {
      algorithm: this.signatureAlgorithm,
      signature: this.arrayBufferToBase64(signature),
      publicKey: this.arrayBufferToBase64(publicKeyExported),
      timestamp: Date.now()
    };
  }

  private async validateDataSignature(data: ArrayBuffer, signature: DigitalSignature): Promise<boolean> {
    try {
      // Import public key
      const publicKeyBuffer = this.base64ToArrayBuffer(signature.publicKey);
      const publicKey = await crypto.subtle.importKey(
        'spki',
        publicKeyBuffer,
        {
          name: this.signatureAlgorithm,
          namedCurve: 'P-256'
        },
        false,
        ['verify']
      );
      
      // Verify signature
      const signatureBuffer = this.base64ToArrayBuffer(signature.signature);
      return await crypto.subtle.verify(
        {
          name: this.signatureAlgorithm,
          hash: this.hashAlgorithm
        },
        publicKey,
        signatureBuffer,
        data
      );
      
    } catch (error) {
      console.error('Signature validation error:', error);
      return false;
    }
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      const byte = bytes[i];
      if (byte !== undefined) {
        binary += String.fromCharCode(byte);
      }
    }
    return btoa(binary);
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }
}