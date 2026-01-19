/**
 * Mock Identity Manager Factory for Testing
 * 
 * Creates IdentityManager instances with mock services for reliable testing.
 * Ensures complete test isolation and deterministic behavior for property-based testing.
 */

import { IdentityManagerImpl } from '../../implementations/IdentityManager';
import { IdentityManager, IdentityManagerConfig } from '../../interfaces/IdentityManager';
import {
  MockCryptoService,
  MockValidationService,
  MockStorageService,
  MockSyncService,
  MockAssetService
} from './MockServices';

export class MockIdentityManagerFactory {
  private static instanceCounter = 0;
  private static globalMockServices: {
    cryptoService: MockCryptoService;
    storageService: MockStorageService;
    validationService: MockValidationService;
    syncService: MockSyncService;
    assetService: MockAssetService;
  } | null = null;

  static async create(config: IdentityManagerConfig): Promise<IdentityManager> {
    // PRODUCTION-GRADE DETERMINISTIC TESTING: Use singleton mock services for signature consistency
    // while maintaining test isolation through proper cleanup
    if (!this.globalMockServices) {
      this.globalMockServices = {
        cryptoService: new MockCryptoService(),
        storageService: new MockStorageService(),
        validationService: new MockValidationService(),
        syncService: new MockSyncService(),
        assetService: new MockAssetService()
      };
    }

    // CRYPTOGRAPHIC CONSISTENCY: Clean up services without recreating them
    await this.globalMockServices.cryptoService.cleanup();
    await this.globalMockServices.storageService.cleanup();
    await this.globalMockServices.syncService.cleanup();
    await this.globalMockServices.assetService.cleanup();
    
    // Generate unique instance ID for test tracking
    const instanceId = ++this.instanceCounter;
    
    // DETERMINISTIC CONFIGURATION: Use provided storage provider or create deterministic one
    const isolatedConfig: IdentityManagerConfig = {
      ...config,
      storageProvider: config.storageProvider || `test-instance-${instanceId.toString().padStart(3, '0')}`,
      cacheSize: config.cacheSize || 1024 * 1024,
      syncInterval: config.syncInterval || 5000
    };
    
    return new IdentityManagerImpl(
      isolatedConfig,
      this.globalMockServices.cryptoService,
      this.globalMockServices.storageService,
      this.globalMockServices.validationService,
      this.globalMockServices.syncService,
      this.globalMockServices.assetService
    );
  }

  static async cleanup(): Promise<void> {
    // COMPLETE CLEANUP: Reset all global state for test isolation
    this.instanceCounter = 0;
    
    if (this.globalMockServices) {
      await this.globalMockServices.cryptoService.cleanup();
      await this.globalMockServices.storageService.cleanup();
      await this.globalMockServices.syncService.cleanup();
      await this.globalMockServices.assetService.cleanup();
    }
    
    // Reset mock service global state
    MockCryptoService.resetGlobalState();
    MockStorageService.resetGlobalState();
  }
}