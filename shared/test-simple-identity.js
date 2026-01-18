// Simple test to verify identity creation works
const { IdentityManagerSimple } = require('./src/avatar/implementations/IdentityManagerSimple.ts');

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
    windows: { assetCompression: true, lodOptimization: true, textureCompression: 'dxt', meshOptimization: true, shaderOptimization: true, memoryOptimization: true }
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

async function testSimpleIdentityCreation() {
  try {
    console.log('=== SIMPLE IDENTITY CREATION TEST ===');
    
    const identityManager = new IdentityManagerSimple(testConfig);
    console.log('✓ Simple identity manager created');
    
    const result = await identityManager.createIdentity(avatarConfig);
    console.log('Create result:', JSON.stringify(result, null, 2));
    
    if (result.success) {
      console.log('✓ SUCCESS: Identity created successfully!');
      console.log('Identity ID:', result.data.id);
      
      // Test retrieval
      const getResult = await identityManager.getActiveIdentity();
      if (getResult.success) {
        console.log('✓ SUCCESS: Identity retrieved successfully!');
        console.log('Retrieved identity matches:', getResult.data.id === result.data.id);
      } else {
        console.log('❌ FAILED: Could not retrieve identity');
      }
    } else {
      console.log('❌ FAILED: Identity creation failed');
      console.log('Error:', result.error);
    }
    
  } catch (error) {
    console.error('❌ CRITICAL ERROR:', error);
  }
}

testSimpleIdentityCreation();