// Debug script to test identity creation
import { IdentityManagerFactory } from './src/avatar/implementations/index.js';

const testConfig = {
  storageProvider: 'local',
  encryptionEnabled: true,
  compressionEnabled: false,
  autoSync: true,
  syncInterval: 5000,
  conflictResolution: 'merge',
  cacheSize: 1024 * 1024,
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

const avatarConfig = {
  gender: 'male',
  voiceStyle: 'calm',
  personalityTone: 'co-worker',
  accent: null,
  expressiveness: 'low',
  gestureIntensity: 'subtle',
  voicePersonality: 'formal',
  minimalMode: false,
  facialFeatures: null
};

async function testIdentityCreation() {
  try {
    console.log('Creating identity manager...');
    const identityManager = await IdentityManagerFactory.create(testConfig);
    
    console.log('Creating identity with config:', JSON.stringify(avatarConfig, null, 2));
    const result = await identityManager.createIdentity(avatarConfig);
    
    console.log('Result:', JSON.stringify(result, null, 2));
    
    if (!result.success) {
      console.error('Identity creation failed:', result.error);
    }
  } catch (error) {
    console.error('Error during test:', error);
  }
}

testIdentityCreation();