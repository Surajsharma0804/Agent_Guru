/**
 * Property-based tests for avatar identity persistence and synchronization
 * 
 * Feature: humanized-avatar-system, Property 1: Avatar Identity Persistence and Synchronization
 * Validates: Requirements 1.2, 1.3, 15.5
 */

import * as fc from 'fast-check';
import { 
  IdentityManagerImpl,
  IdentityManagerFactory,
  CryptoServiceImpl,
  ValidationServiceImpl,
  StorageServiceImpl,
  SyncServiceImpl,
  AssetServiceImpl
} from '../implementations';
import { 
  AvatarIdentity,
  AvatarIdentityConfig
} from '../types/AvatarIdentity';
import { 
  Platform,
  AvatarApiResponse,
  Gender,
  VoiceStyle,
  PersonalityTone,
  VoicePersonality,
  ExpressivenessLevel,
  GestureIntensity
} from '../types/Common';
import { 
  IdentityManagerConfig
} from '../interfaces/IdentityManager';

// Test configuration for Identity Manager
const testConfig: IdentityManagerConfig = {
  storageProvider: 'local',
  encryptionEnabled: true,
  compressionEnabled: false,
  autoSync: true,
  syncInterval: 5000,
  conflictResolution: 'merge',
  cacheSize: 1024 * 1024, // 1MB
  preloadAssets: false,
  backgroundSync: false,
  signatureValidation: true,
  integrityChecks: true,
  secureDelete: true,
  platformOptimizations: {
    windows: { assetCompression: true, lodOptimization: true, textureCompression: 'dxt', meshOptimization: true, shaderOptimization: true, memoryOptimization: true },
    macos: { assetCompression: true, lodOptimization: true, textureCompression: 'astc', meshOptimization: true, shaderOptimization: true, memoryOptimization: true },
    android: { assetCompression: true, lodOptimization: true, textureCompression: 'etc2', meshOptimization: true, shaderOptimization: false, memoryOptimization: true },
    ios: { assetCompression: true, lodOptimization: true, textureCompression: 'astc', meshOptimization: true, shaderOptimization: false, memoryOptimization: true },
    web: { assetCompression: true, lodOptimization: true, textureCompression: 'webp', meshOptimization: false, shaderOptimization: false, memoryOptimization: true }
  }
};

// Generators for property-based testing
const genderArb = fc.constantFrom<Gender>('male', 'female', 'non-binary');
const voiceStyleArb = fc.constantFrom<VoiceStyle>('calm', 'friendly', 'professional', 'energetic');
const personalityToneArb = fc.constantFrom<PersonalityTone>('co-worker', 'best-friend', 'assistant', 'mentor');
const voicePersonalityArb = fc.constantFrom<VoicePersonality>('formal', 'friendly', 'casual');
const expressivenessArb = fc.constantFrom<ExpressivenessLevel>('low', 'medium', 'high');
const gestureIntensityArb = fc.constantFrom<GestureIntensity>('subtle', 'natural', 'expressive');
const platformArb = fc.constantFrom<Platform>('windows', 'macos', 'android', 'ios', 'web');

const avatarIdentityConfigArb = fc.record({
  gender: genderArb,
  voiceStyle: voiceStyleArb,
  personalityTone: personalityToneArb,
  accent: fc.option(fc.string({ minLength: 2, maxLength: 10 }).filter(s => /^[a-z]{2}-[a-z]{2,}$/i.test(s))),
  expressiveness: expressivenessArb,
  gestureIntensity: gestureIntensityArb,
  voicePersonality: voicePersonalityArb,
  minimalMode: fc.boolean(),
  facialFeatures: fc.option(fc.record({
    faceShape: fc.record({
      oval: fc.float({ min: -1.0, max: 1.0 }),
      round: fc.float({ min: -1.0, max: 1.0 }),
      square: fc.float({ min: -1.0, max: 1.0 })
    }),
    eyeShape: fc.record({
      almond: fc.float({ min: -1.0, max: 1.0 }),
      round: fc.float({ min: -1.0, max: 1.0 })
    })
  }))
});

const avatarIdentityConfigUpdateArb = fc.record({
  gender: fc.option(genderArb),
  voiceStyle: fc.option(voiceStyleArb),
  personalityTone: fc.option(personalityToneArb),
  expressiveness: fc.option(expressivenessArb),
  gestureIntensity: fc.option(gestureIntensityArb),
  voicePersonality: fc.option(voicePersonalityArb),
  minimalMode: fc.option(fc.boolean())
}, { requiredKeys: [] });

describe('Avatar Identity Persistence and Synchronization Property Tests', () => {
  let identityManager: IdentityManagerImpl;

  beforeEach(async () => {
    // Clear localStorage before each test
    if (typeof localStorage !== 'undefined') {
      localStorage.clear();
    }
    
    // Create fresh identity manager instance
    identityManager = await IdentityManagerFactory.create(testConfig) as IdentityManagerImpl;
  });

  afterEach(async () => {
    await identityManager.cleanup();
  });

  describe('Property 1: Avatar Identity Persistence and Synchronization', () => {
    test('Identity persistence round-trip: store then retrieve should produce equivalent configuration', async () => {
      await fc.assert(
        fc.asyncProperty(avatarIdentityConfigArb, async (config) => {
          // Create identity
          const createResponse = await identityManager.createIdentity(config);
          expect(createResponse.success).toBe(true);
          expect(createResponse.data).toBeDefined();
          
          const createdIdentity = createResponse.data!;
          
          // Retrieve the same identity
          const retrieveResponse = await identityManager.getActiveIdentity();
          expect(retrieveResponse.success).toBe(true);
          expect(retrieveResponse.data).toBeDefined();
          
          const retrievedIdentity = retrieveResponse.data!;
          
          // Validate persistence: core configuration should match
          expect(retrievedIdentity.id).toBe(createdIdentity.id);
          expect(retrievedIdentity.appearance.gender).toBe(config.gender);
          expect(retrievedIdentity.personality.voiceStyle).toBe(config.voiceStyle);
          expect(retrievedIdentity.personality.tone).toBe(config.personalityTone);
          expect(retrievedIdentity.personality.voicePersonality).toBe(config.voicePersonality);
          expect(retrievedIdentity.personality.expressiveness.expressiveness).toBe(config.expressiveness);
          expect(retrievedIdentity.personality.gestureStyle.intensity).toBe(config.gestureIntensity);
          expect(retrievedIdentity.preferences.minimalMode).toBe(config.minimalMode);
          
          // Validate metadata integrity
          expect(retrievedIdentity.version).toBe(createdIdentity.version);
          expect(retrievedIdentity.created).toEqual(createdIdentity.created);
          expect(retrievedIdentity.signature).toEqual(createdIdentity.signature);
          
          return true;
        }),
        { numRuns: 100 }
      );
    });

    test('Identity updates should persist correctly and maintain version history', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.tuple(avatarIdentityConfigArb, avatarIdentityConfigUpdateArb),
          async ([initialConfig, updates]) => {
            // Create initial identity
            const createResponse = await identityManager.createIdentity(initialConfig);
            expect(createResponse.success).toBe(true);
            const originalIdentity = createResponse.data!;
            const originalVersion = originalIdentity.version;
            
            // Apply updates
            const updateResponse = await identityManager.updateIdentity(originalIdentity, updates);
            expect(updateResponse.success).toBe(true);
            
            // Retrieve updated identity
            const retrieveResponse = await identityManager.getActiveIdentity();
            expect(retrieveResponse.success).toBe(true);
            const updatedIdentity = retrieveResponse.data!;
            
            // Validate version increment
            expect(updatedIdentity.version).not.toBe(originalVersion);
            expect(updatedIdentity.lastModified.getTime()).toBeGreaterThan(originalIdentity.lastModified.getTime());
            
            // Validate updates were applied correctly
            if (updates.gender !== undefined) {
              expect(updatedIdentity.appearance.gender).toBe(updates.gender);
            } else {
              expect(updatedIdentity.appearance.gender).toBe(initialConfig.gender);
            }
            
            if (updates.voiceStyle !== undefined) {
              expect(updatedIdentity.personality.voiceStyle).toBe(updates.voiceStyle);
            } else {
              expect(updatedIdentity.personality.voiceStyle).toBe(initialConfig.voiceStyle);
            }
            
            if (updates.minimalMode !== undefined) {
              expect(updatedIdentity.preferences.minimalMode).toBe(updates.minimalMode);
            } else {
              expect(updatedIdentity.preferences.minimalMode).toBe(initialConfig.minimalMode);
            }
            
            // Validate signature was updated
            expect(updatedIdentity.signature).not.toEqual(originalIdentity.signature);
            
            return true;
          }
        ),
        { numRuns: 50 }
      );
    });

    test('Multiple identities should be stored and retrieved independently', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(avatarIdentityConfigArb, { minLength: 2, maxLength: 5 }),
          async (configs) => {
            const createdIdentities: AvatarIdentity[] = [];
            
            // Create multiple identities
            for (const config of configs) {
              const response = await identityManager.createIdentity(config);
              expect(response.success).toBe(true);
              createdIdentities.push(response.data!);
            }
            
            // Retrieve all identities
            const allIdentitiesResponse = await identityManager.getAllIdentities();
            expect(allIdentitiesResponse.success).toBe(true);
            const retrievedIdentities = allIdentitiesResponse.data!;
            
            // Validate count
            expect(retrievedIdentities.length).toBe(configs.length);
            
            // Validate each identity is unique and matches its configuration
            const retrievedIds = new Set(retrievedIdentities.map(id => id.id));
            expect(retrievedIds.size).toBe(configs.length); // All IDs should be unique
            
            // Validate each identity can be retrieved individually
            for (let i = 0; i < createdIdentities.length; i++) {
              const identity = createdIdentities[i];
              const config = configs[i];
              
              // Set as active and retrieve
              const setActiveResponse = await identityManager.setActiveIdentity(identity.id);
              expect(setActiveResponse.success).toBe(true);
              
              const getActiveResponse = await identityManager.getActiveIdentity();
              expect(getActiveResponse.success).toBe(true);
              
              const activeIdentity = getActiveResponse.data!;
              expect(activeIdentity.id).toBe(identity.id);
              expect(activeIdentity.appearance.gender).toBe(config.gender);
              expect(activeIdentity.personality.voiceStyle).toBe(config.voiceStyle);
            }
            
            return true;
          }
        ),
        { numRuns: 20 }
      );
    });

    test('Cross-platform synchronization should maintain identity consistency within time limits', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.tuple(avatarIdentityConfigArb, fc.array(platformArb, { minLength: 2, maxLength: 4 })),
          async ([config, platforms]) => {
            // Create identity
            const createResponse = await identityManager.createIdentity(config);
            expect(createResponse.success).toBe(true);
            const identity = createResponse.data!;
            
            // Test synchronization across platforms
            const syncStartTime = Date.now();
            const syncResponse = await identityManager.syncIdentityAcrossDevices(identity);
            const syncEndTime = Date.now();
            
            expect(syncResponse.success).toBe(true);
            
            // Validate sync completed within reasonable time (Requirement 15.5)
            const syncDuration = syncEndTime - syncStartTime;
            expect(syncDuration).toBeLessThan(5000); // Should complete within 5 seconds
            
            // Validate platform compatibility for each target platform
            for (const platform of platforms) {
              const compatibilityResponse = await identityManager.validateIdentityCompatibility(identity, platform);
              expect(compatibilityResponse.success).toBe(true);
              
              // If not compatible, should be able to migrate
              if (!compatibilityResponse.data) {
                const migrationResponse = await identityManager.migrateIdentityToPlatform(identity, platform);
                expect(migrationResponse.success).toBe(true);
                
                const migratedIdentity = migrationResponse.data!;
                expect(migratedIdentity.id).toBe(identity.id);
                expect(migratedIdentity.appearance.gender).toBe(identity.appearance.gender);
                expect(migratedIdentity.personality.voiceStyle).toBe(identity.personality.voiceStyle);
              }
            }
            
            return true;
          }
        ),
        { numRuns: 30 }
      );
    });

    test('Identity encryption and decryption should preserve data integrity', async () => {
      await fc.assert(
        fc.asyncProperty(avatarIdentityConfigArb, async (config) => {
          // Create identity
          const createResponse = await identityManager.createIdentity(config);
          expect(createResponse.success).toBe(true);
          const originalIdentity = createResponse.data!;
          
          // Encrypt identity
          const encryptResponse = await identityManager.encryptIdentityData(originalIdentity);
          expect(encryptResponse.success).toBe(true);
          const encryptedData = encryptResponse.data!;
          
          // Validate encrypted data structure
          expect(encryptedData.encryptedData).toBeDefined();
          expect(encryptedData.encryptionMetadata).toBeDefined();
          expect(encryptedData.signature).toBeDefined();
          expect(encryptedData.version).toBe(originalIdentity.version);
          
          // Decrypt identity
          const decryptResponse = await identityManager.decryptIdentityData(encryptedData);
          expect(decryptResponse.success).toBe(true);
          const decryptedIdentity = decryptResponse.data!;
          
          // Validate round-trip integrity
          expect(decryptedIdentity.id).toBe(originalIdentity.id);
          expect(decryptedIdentity.version).toBe(originalIdentity.version);
          expect(decryptedIdentity.appearance.gender).toBe(originalIdentity.appearance.gender);
          expect(decryptedIdentity.personality.voiceStyle).toBe(originalIdentity.personality.voiceStyle);
          expect(decryptedIdentity.personality.tone).toBe(originalIdentity.personality.tone);
          expect(decryptedIdentity.preferences.minimalMode).toBe(originalIdentity.preferences.minimalMode);
          
          return true;
        }),
        { numRuns: 50 }
      );
    });

    test('Identity signature validation should detect tampering', async () => {
      await fc.assert(
        fc.asyncProperty(avatarIdentityConfigArb, async (config) => {
          // Create identity
          const createResponse = await identityManager.createIdentity(config);
          expect(createResponse.success).toBe(true);
          const identity = createResponse.data!;
          
          // Validate original signature
          const validationResponse = await identityManager.validateIdentitySignature(identity);
          expect(validationResponse.success).toBe(true);
          expect(validationResponse.data).toBe(true);
          
          // Tamper with identity data
          const tamperedIdentity = { 
            ...identity, 
            appearance: { 
              ...identity.appearance, 
              gender: identity.appearance.gender === 'male' ? 'female' : 'male' 
            } 
          };
          
          // Signature validation should fail for tampered data
          const tamperedValidationResponse = await identityManager.validateIdentitySignature(tamperedIdentity);
          expect(tamperedValidationResponse.success).toBe(true);
          expect(tamperedValidationResponse.data).toBe(false);
          
          return true;
        }),
        { numRuns: 30 }
      );
    });

    test('Storage optimization should not corrupt identity data', async () => {
      await fc.assert(
        fc.asyncProperty(
          fc.array(avatarIdentityConfigArb, { minLength: 3, maxLength: 8 }),
          async (configs) => {
            const identityIds: string[] = [];
            
            // Create multiple identities
            for (const config of configs) {
              const response = await identityManager.createIdentity(config);
              expect(response.success).toBe(true);
              identityIds.push(response.data!.id);
            }
            
            // Delete some identities to create optimization opportunities
            const toDelete = identityIds.slice(0, Math.floor(identityIds.length / 2));
            for (const id of toDelete) {
              await identityManager.deleteIdentity(id);
            }
            
            // Optimize storage
            const optimizeResponse = await identityManager.optimizeStorage();
            expect(optimizeResponse.success).toBe(true);
            
            // Validate remaining identities are still intact
            const remainingIds = identityIds.slice(Math.floor(identityIds.length / 2));
            const allIdentitiesResponse = await identityManager.getAllIdentities();
            expect(allIdentitiesResponse.success).toBe(true);
            
            const retrievedIdentities = allIdentitiesResponse.data!;
            expect(retrievedIdentities.length).toBe(remainingIds.length);
            
            // Validate each remaining identity is still valid
            for (const identity of retrievedIdentities) {
              expect(remainingIds).toContain(identity.id);
              
              const signatureResponse = await identityManager.validateIdentitySignature(identity);
              expect(signatureResponse.success).toBe(true);
              expect(signatureResponse.data).toBe(true);
            }
            
            return true;
          }
        ),
        { numRuns: 15 }
      );
    });
  });
});