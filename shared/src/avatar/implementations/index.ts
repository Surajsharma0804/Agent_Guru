/**
 * Avatar System Implementations
 * 
 * Production-grade implementations of all avatar system interfaces.
 */

// Core Implementation
export { IdentityManagerImpl } from './IdentityManager';

// Service Implementations
export type { CryptoService } from './CryptoService';
export { CryptoServiceImpl } from './CryptoService';
export type { ValidationService } from './ValidationService';
export { ValidationServiceImpl } from './ValidationService';
export type { StorageService } from './StorageService';
export { StorageServiceImpl } from './StorageService';
export type { SyncService } from './SyncService';
export { SyncServiceImpl } from './SyncService';
export type { AssetService } from './AssetService';
export { AssetServiceImpl } from './AssetService';
export type { 
  UserControlManager,
  UserControlSettings,
  ControlOverrideResult,
  SafetyBoundaryViolation,
  UserControlPreset,
  ControlChangeCallback,
  SafetyBoundaryCallback
} from './UserControlManager';
export { UserControlManagerImpl } from './UserControlManager';

// Factory for creating Identity Manager with all dependencies
export class IdentityManagerFactory {
  static async create(config: import('../interfaces/IdentityManager').IdentityManagerConfig): Promise<import('../interfaces/IdentityManager').IdentityManager> {
    const { IdentityManagerImpl } = await import('./IdentityManager');
    const { CryptoServiceImpl } = await import('./CryptoService');
    const { ValidationServiceImpl } = await import('./ValidationService');
    const { StorageServiceImpl } = await import('./StorageService');
    const { SyncServiceImpl } = await import('./SyncService');
    const { AssetServiceImpl } = await import('./AssetService');
    
    const cryptoService = new CryptoServiceImpl();
    const storageService = new StorageServiceImpl();
    const validationService = new ValidationServiceImpl();
    const syncService = new SyncServiceImpl();
    const assetService = new AssetServiceImpl();
    
    return new IdentityManagerImpl(
      config,
      cryptoService,
      storageService,
      validationService,
      syncService,
      assetService
    );
  }
}