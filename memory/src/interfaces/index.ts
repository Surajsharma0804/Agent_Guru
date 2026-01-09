/**
 * @fileoverview Memory system interfaces
 */

export interface MemoryStore<T = unknown> {
  get(key: string): Promise<T | null>;
  set(key: string, value: T): Promise<void>;
  delete(key: string): Promise<boolean>;
  has(key: string): Promise<boolean>;
  keys(): Promise<string[]>;
  clear(): Promise<void>;
}

export interface EncryptedMemoryStore<T = unknown> extends MemoryStore<T> {
  setEncryptionKey(key: CryptoKey): Promise<void>;
  rotateEncryptionKey(newKey: CryptoKey): Promise<void>;
}

export interface SyncableMemoryStore<T = unknown> extends MemoryStore<T> {
  getLastModified(key: string): Promise<number | null>;
  sync(remoteStore: MemoryStore<T>): Promise<void>;
}