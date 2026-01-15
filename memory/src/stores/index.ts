/**
 * @fileoverview Memory store implementations
 */

import { MemoryStore } from '../interfaces/index.js';

export class InMemoryStore<T = unknown> implements MemoryStore<T> {
  private data = new Map<string, T>();
  
  async get(key: string): Promise<T | null> {
    return this.data.get(key) ?? null;
  }
  
  async set(key: string, value: T): Promise<void> {
    this.data.set(key, value);
  }
  
  async delete(key: string): Promise<boolean> {
    return this.data.delete(key);
  }
  
  async has(key: string): Promise<boolean> {
    return this.data.has(key);
  }
  
  async keys(): Promise<string[]> {
    return Array.from(this.data.keys());
  }
  
  async clear(): Promise<void> {
    this.data.clear();
  }
}

export class PersistentStore<T = unknown> implements MemoryStore<T> {
  private readonly path: string;
  
  constructor(storePath: string) {
    this.path = storePath;
  }
  
  async get(_key: string): Promise<T | null> {
    // Implementation would use file system or database at this.path
    console.log(`PersistentStore: Would load from ${this.path}`);
    throw new Error('Not implemented');
  }
  
  async set(_key: string, _value: T): Promise<void> {
    // Implementation would use file system or database
    throw new Error('Not implemented');
  }
  
  async delete(_key: string): Promise<boolean> {
    // Implementation would use file system or database
    throw new Error('Not implemented');
  }
  
  async has(_key: string): Promise<boolean> {
    // Implementation would use file system or database
    throw new Error('Not implemented');
  }
  
  async keys(): Promise<string[]> {
    // Implementation would use file system or database
    throw new Error('Not implemented');
  }
  
  async clear(): Promise<void> {
    // Implementation would use file system or database
    throw new Error('Not implemented');
  }
}