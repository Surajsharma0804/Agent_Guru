// Diagnostic script to understand why createIdentity is failing
import { IdentityManagerFactory } from './dist/avatar/implementations/index.js';

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

async function diagnoseIdentityCreation() {
  try {
    console.log('=== DIAGNOSTIC: Identity Creation Failure Analysis ===');
    console.log('1. Creating identity manager...');
    
    const identityManager = await IdentityManagerFactory.create(testConfig);
    console.log('✓ Identity manager created successfully');
    
    console.log('2. Testing configuration validation...');
    const validationResult = await identityManager.validateConfiguration(avatarConfig);
    console.log('Validation result:', JSON.stringify(validationResult, null, 2));
    
    console.log('3. Attempting to create identity...');
    const createResult = await identityManager.createIdentity(avatarConfig);
    console.log('Create result:', JSON.stringify(createResult, null, 2));
    
    if (!createResult.success) {
      console.log('❌ IDENTITY CREATION FAILED');
      console.log('Error details:', createResult.error);
      
      // Try to get more details about what went wrong
      if (createResult.error && createResult.error.message) {
        console.log('Error message analysis:', createResult.error.message);
        
        if (createResult.error.message.includes('validation')) {
          console.log('This appears to be a validation error. Checking validation service...');
        }
      }
    } else {
      console.log('✓ Identity created successfully');
      console.log('Identity ID:', createResult.data?.id);
    }
    
  } catch (error) {
    console.error('❌ CRITICAL ERROR during diagnosis:', error);
    console.error('Stack trace:', error.stack);
  }
}

diagnoseIdentityCreation();