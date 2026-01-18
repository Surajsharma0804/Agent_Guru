/**
 * Asset Service for Avatar Identity Management
 * 
 * Provides asset loading, validation, and platform-specific optimization
 * for avatar 3D models, textures, animations, and shaders.
 */

import { AvatarIdentity, PlatformAssetSet } from '../types/AvatarIdentity';
import { AvatarAssets } from '../types/AvatarAssets';
import { Platform, PlatformCapabilities } from '../types/Common';

/**
 * Asset loading progress callback
 */
export type AssetLoadingProgressCallback = (progress: {
  totalAssets: number;
  loadedAssets: number;
  failedAssets: number;
  currentAsset?: string;
  bytesLoaded: number;
  totalBytes: number;
  estimatedTimeRemaining: number;
  loadingSpeed: number;
}) => void;

/**
 * Asset service interface
 */
export interface AssetService {
  // Asset Loading
  loadAssets(identity: AvatarIdentity, platform: Platform): Promise<AvatarAssets | null>;
  preloadAssets(identity: AvatarIdentity, platform: Platform, progressCallback?: AssetLoadingProgressCallback): Promise<void>;
  
  // Asset Generation
  generatePlatformAssets(identity: AvatarIdentity, platform: Platform): Promise<PlatformAssetSet>;
  generateEmptyAssetSet(platform: Platform): Promise<PlatformAssetSet>;
  
  // Asset Validation
  validateIntegrity(assets: AvatarAssets): Promise<boolean>;
  validateAssetCompatibility(assets: PlatformAssetSet, capabilities: PlatformCapabilities): Promise<boolean>;
  
  // Platform Capabilities
  getPlatformCapabilities(platform: Platform): Promise<PlatformCapabilities>;
  
  // Asset Management
  deleteIdentityAssets(identityId: string): Promise<void>;
  cleanup(): Promise<void>;
}

/**
 * Production implementation of asset service
 */
export class AssetServiceImpl implements AssetService {
  private readonly assetCache: Map<string, AvatarAssets> = new Map();
  private readonly capabilitiesCache: Map<Platform, PlatformCapabilities> = new Map();

  async loadAssets(identity: AvatarIdentity, platform: Platform): Promise<AvatarAssets | null> {
    try {
      const cacheKey = `${identity.id}-${platform}`;
      
      // Check cache first
      if (this.assetCache.has(cacheKey)) {
        return this.assetCache.get(cacheKey) || null;
      }
      
      // Load platform-specific assets
      const platformAssets = identity.assets[platform];
      if (!platformAssets) {
        return null;
      }
      
      // Convert platform asset set to avatar assets
      const assets: AvatarAssets = {
        version: platformAssets.version,
        platform: platform,
        quality: this.determineBestQuality(platform),
        meshes: {
          head: platformAssets.meshes.head,
          body: platformAssets.meshes.body,
          hair: platformAssets.meshes.hair,
          accessories: platformAssets.meshes.accessories,
          clothing: platformAssets.meshes.clothing,
          facialRig: this.createDefaultFacialRig(),
          bodyRig: undefined,
          morphTargets: platformAssets.meshes.morphTargets || [],
          blendShapes: platformAssets.meshes.blendShapes || []
        },
        textures: this.convertTextureAssets(platformAssets.textures),
        animations: platformAssets.animations,
        rigs: {
          facial: this.createDefaultFacialRig(),
          morphTargets: platformAssets.meshes.morphTargets || []
        },
        shaders: {
          vertex: platformAssets.shaders.vertex,
          fragment: platformAssets.shaders.fragment,
          geometry: platformAssets.shaders.geometry,
          compute: platformAssets.shaders.compute,
          programs: [] // Add empty programs array
        },
        metadata: platformAssets.metadata,
        signature: platformAssets.metadata.signature,
        loadingStrategy: {
          priority: 'sequential',
          batchSize: 5,
          retryAttempts: 3,
          timeout: 30000,
          preloadCritical: true,
          backgroundLoading: false,
          compressionEnabled: true
        },
        cachePolicy: {
          maxAge: 86400000, // 24 hours
          maxSize: 100 * 1024 * 1024, // 100MB
          evictionStrategy: 'lru',
          persistToDisk: true,
          compressionEnabled: true
        }
      };
      
      // Cache assets
      this.assetCache.set(cacheKey, assets);
      
      return assets;
    } catch (error) {
      console.error('Failed to load assets:', error);
      return null;
    }
  }

  async preloadAssets(identity: AvatarIdentity, platform: Platform, progressCallback?: AssetLoadingProgressCallback): Promise<void> {
    try {
      const platformAssets = identity.assets[platform];
      if (!platformAssets) {
        return;
      }
      
      const totalAssets = this.countAssets(platformAssets);
      let loadedAssets = 0;
      let failedAssets = 0;
      let bytesLoaded = 0;
      const totalBytes = platformAssets.metadata.totalSize;
      const startTime = Date.now();
      
      const updateProgress = (currentAsset?: string) => {
        const elapsed = Date.now() - startTime;
        const loadingSpeed = bytesLoaded / (elapsed / 1000);
        const remainingBytes = totalBytes - bytesLoaded;
        const estimatedTimeRemaining = loadingSpeed > 0 ? (remainingBytes / loadingSpeed) * 1000 : 0;
        
        progressCallback?.({
          totalAssets,
          loadedAssets,
          failedAssets,
          currentAsset: currentAsset || 'unknown',
          bytesLoaded,
          totalBytes,
          estimatedTimeRemaining,
          loadingSpeed
        });
      };
      
      // Simulate asset loading
      for (const [assetType, assetList] of Object.entries(platformAssets.meshes)) {
        try {
          updateProgress(`Loading ${assetType} meshes`);
          // Simulate loading time based on asset count
          const assetCount = Array.isArray(assetList) ? assetList.length : 1;
          await new Promise(resolve => setTimeout(resolve, 100 * assetCount));
          loadedAssets++;
          bytesLoaded += 1024 * 100; // Simulate 100KB per asset
        } catch (error) {
          failedAssets++;
        }
      }
      
      updateProgress();
    } catch (error) {
      throw new Error(`Failed to preload assets: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async generatePlatformAssets(identity: AvatarIdentity, platform: Platform): Promise<PlatformAssetSet> {
    try {
      // Generate platform-optimized assets based on identity configuration
      const capabilities = await this.getPlatformCapabilities(platform);
      
      return {
        platform,
        version: identity.version,
        meshes: await this.generateMeshAssets(identity, capabilities),
        textures: await this.generateTextureAssets(identity, capabilities),
        animations: await this.generateAnimationAssets(identity, capabilities),
        shaders: await this.generateShaderAssets(identity, capabilities),
        metadata: {
          version: identity.version,
          created: new Date(),
          lastModified: new Date(),
          totalSize: 1024 * 1024, // 1MB placeholder
          assetCount: 10,
          signature: identity.signature,
          dependencies: [],
          compatibility: [platform]
        }
      };
    } catch (error) {
      throw new Error(`Failed to generate platform assets: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async generateEmptyAssetSet(platform: Platform): Promise<PlatformAssetSet> {
    return {
      platform,
      version: '1.0.0',
      meshes: {
        head: this.createEmptyMeshAsset('head'),
        hair: this.createEmptyMeshAsset('hair'),
        morphTargets: []
      },
      textures: {
        diffuse: [],
        normal: [],
        specular: []
      },
      animations: {
        idle: [],
        expressions: [],
        gestures: [],
        transitions: [],
        breathing: this.createEmptyAnimationAsset('breathing'),
        blinking: this.createEmptyAnimationAsset('blinking')
      },
      shaders: {
        vertex: [],
        fragment: []
      },
      metadata: {
        version: '1.0.0',
        created: new Date(),
        lastModified: new Date(),
        totalSize: 0,
        assetCount: 0,
        signature: {
          algorithm: 'ECDSA',
          signature: '',
          publicKey: '',
          timestamp: Date.now()
        },
        dependencies: [],
        compatibility: [platform]
      }
    };
  }

  async validateIntegrity(assets: AvatarAssets): Promise<boolean> {
    try {
      // Validate checksums and signatures
      const calculatedChecksum = await this.calculateAssetChecksum(assets);
      const expectedChecksum = assets.metadata.checksum || assets.signature.signature;
      return calculatedChecksum === expectedChecksum;
    } catch (error) {
      console.error('Asset integrity validation failed:', error);
      return false;
    }
  }

  async validateAssetCompatibility(assets: PlatformAssetSet, capabilities: PlatformCapabilities): Promise<boolean> {
    try {
      // Check texture size limits
      for (const textureArray of Object.values(assets.textures)) {
        for (const texture of textureArray) {
          if (texture.resolution > capabilities.maxTextureSize) {
            return false;
          }
        }
      }
      
      // Check vertex count limits
      for (const mesh of Object.values(assets.meshes)) {
        if (Array.isArray(mesh)) {
          for (const m of mesh) {
            if (m.vertexCount > capabilities.maxVertexCount) {
              return false;
            }
          }
        } else if (mesh && mesh.vertexCount > capabilities.maxVertexCount) {
          return false;
        }
      }
      
      return true;
    } catch (error) {
      console.error('Asset compatibility validation failed:', error);
      return false;
    }
  }

  async getPlatformCapabilities(platform: Platform): Promise<PlatformCapabilities> {
    if (this.capabilitiesCache.has(platform)) {
      return this.capabilitiesCache.get(platform)!;
    }
    
    const capabilities = this.getDefaultCapabilities(platform);
    this.capabilitiesCache.set(platform, capabilities);
    return capabilities;
  }

  async deleteIdentityAssets(identityId: string): Promise<void> {
    // Remove from cache
    for (const key of this.assetCache.keys()) {
      if (key.startsWith(identityId)) {
        this.assetCache.delete(key);
      }
    }
  }

  async cleanup(): Promise<void> {
    this.assetCache.clear();
    this.capabilitiesCache.clear();
  }
  // Private helper methods
  private determineBestQuality(platform: Platform): 'low' | 'medium' | 'high' | 'ultra' {
    switch (platform) {
      case 'windows':
      case 'macos':
        return 'high';
      case 'android':
      case 'ios':
        return 'medium';
      case 'web':
        return 'low';
      default:
        return 'medium';
    }
  }

  private createDefaultFacialRig(): any {
    return {
      bones: [],
      morphTargets: [],
      constraints: []
    };
  }

  private async calculateAssetChecksum(assets: any): Promise<string> {
    const jsonData = JSON.stringify(assets);
    const encoder = new TextEncoder();
    const data = encoder.encode(jsonData);
    
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } else {
      // Fallback for environments without crypto.subtle
      return 'checksum-placeholder';
    }
  }

  private countAssets(platformAssets: PlatformAssetSet): number {
    let count = 0;
    
    // Count meshes
    for (const mesh of Object.values(platformAssets.meshes)) {
      if (Array.isArray(mesh)) {
        count += mesh.length;
      } else if (mesh) {
        count += 1;
      }
    }
    
    // Count textures
    for (const textureArray of Object.values(platformAssets.textures)) {
      count += textureArray.length;
    }
    
    // Count animations
    for (const animationArray of Object.values(platformAssets.animations)) {
      if (Array.isArray(animationArray)) {
        count += animationArray.length;
      } else if (animationArray) {
        count += 1;
      }
    }
    
    // Count shaders
    for (const shaderArray of Object.values(platformAssets.shaders)) {
      if (shaderArray) {
        count += shaderArray.length;
      }
    }
    
    return count;
  }

  private async generateMeshAssets(identity: AvatarIdentity, capabilities: PlatformCapabilities): Promise<any> {
    // Generate optimized meshes based on platform capabilities and identity
    const maxVertexCount = capabilities.maxVertexCount;
    const identityId = identity.id;
    
    return {
      head: this.createEmptyMeshAsset(`${identityId}-head`),
      hair: this.createEmptyMeshAsset(`${identityId}-hair`),
      body: capabilities.supportsFullBody ? this.createEmptyMeshAsset(`${identityId}-body`) : undefined,
      morphTargets: [],
      blendShapes: []
    };
  }

  private async generateTextureAssets(identity: AvatarIdentity, capabilities: PlatformCapabilities): Promise<any> {
    // Generate optimized textures based on platform capabilities and identity
    const maxTextureSize = capabilities.maxTextureSize;
    const identityId = identity.id;
    
    return {
      diffuse: [this.createEmptyTextureAsset(`${identityId}-diffuse`, maxTextureSize)],
      normal: [this.createEmptyTextureAsset(`${identityId}-normal`, maxTextureSize)],
      specular: [this.createEmptyTextureAsset(`${identityId}-specular`, maxTextureSize)],
      roughness: [this.createEmptyTextureAsset(`${identityId}-roughness`, maxTextureSize)],
      metallic: [this.createEmptyTextureAsset(`${identityId}-metallic`, maxTextureSize)],
      emission: [],
      occlusion: []
    };
  }

  private async generateAnimationAssets(identity: AvatarIdentity, capabilities: PlatformCapabilities): Promise<any> {
    // Generate optimized animations based on platform capabilities and identity
    const identityId = identity.id;
    const supportsFullBody = capabilities.supportsFullBody;
    
    return {
      idle: [this.createEmptyAnimationAsset(`${identityId}-idle`)],
      expressions: [this.createEmptyAnimationAsset(`${identityId}-smile`)],
      gestures: supportsFullBody ? [this.createEmptyAnimationAsset(`${identityId}-wave`)] : [],
      transitions: [],
      breathing: this.createEmptyAnimationAsset(`${identityId}-breathing`),
      blinking: this.createEmptyAnimationAsset(`${identityId}-blinking`)
    };
  }

  private async generateShaderAssets(identity: AvatarIdentity, capabilities: PlatformCapabilities): Promise<any> {
    // Generate optimized shaders based on platform capabilities and identity
    const shaderComplexity = capabilities.shaderComplexity;
    const identityId = identity.id;
    
    return {
      vertex: [`// Vertex shader for identity ${identityId} with ${shaderComplexity} complexity`],
      fragment: [`// Fragment shader for identity ${identityId} with ${shaderComplexity} complexity`],
      geometry: shaderComplexity === 'advanced' ? [`// Geometry shader for ${identityId}`] : [],
      compute: shaderComplexity === 'compute' ? [`// Compute shader for ${identityId}`] : []
    };
  }

  /**
   * Convert texture assets from AvatarIdentity format to AvatarAssets format
   */
  private convertTextureAssets(identityTextures: import('../types/AvatarIdentity').TextureAssetCollection): import('../types/AvatarAssets').TextureAssetCollection {
    return {
      diffuse: identityTextures.diffuse.map(tex => this.convertTextureAsset(tex)),
      normal: identityTextures.normal.map(tex => this.convertTextureAsset(tex)),
      specular: identityTextures.specular.map(tex => this.convertTextureAsset(tex)),
      roughness: identityTextures.roughness.map(tex => this.convertTextureAsset(tex)),
      metallic: identityTextures.metallic.map(tex => this.convertTextureAsset(tex)),
      emission: identityTextures.emission?.map(tex => this.convertTextureAsset(tex)),
      occlusion: identityTextures.occlusion?.map(tex => this.convertTextureAsset(tex)),
      height: undefined,
      subsurface: undefined
    };
  }

  /**
   * Convert individual texture asset from AvatarIdentity to AvatarAssets format
   */
  private convertTextureAsset(identityTexture: import('../types/AvatarIdentity').TextureAsset): import('../types/AvatarAssets').TextureAsset {
    return {
      id: identityTexture.id,
      name: `texture_${identityTexture.id}`,
      type: identityTexture.type as import('../types/AvatarAssets').TextureType,
      format: identityTexture.format as import('../types/AvatarAssets').TextureFormat,
      resolution: {
        width: identityTexture.resolution,
        height: identityTexture.resolution,
        aspectRatio: 1.0
      },
      mipmaps: identityTexture.mipmaps,
      compression: {
        algorithm: identityTexture.compression,
        quality: 0.8,
        enabled: true
      },
      url: identityTexture.url,
      localPath: undefined,
      checksum: identityTexture.checksum,
      size: identityTexture.size,
      wrapMode: 'repeat',
      filterMode: 'linear',
      anisotropy: 4,
      platformVariants: undefined
    };
  }

  private createEmptyMeshAsset(name: string): any {
    return {
      id: `${name}-mesh`,
      name: name,
      format: 'gltf' as const,
      lodLevels: [],
      vertexCount: 0,
      triangleCount: 0,
      boundingBox: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 1, y: 1, z: 1 }
      },
      url: `assets/meshes/${name}.gltf`,
      localPath: undefined,
      checksum: 'placeholder-checksum',
      size: 1024,
      materials: [],
      uvChannels: 1,
      vertexColors: false,
      skinned: true,
      compressionLevel: 0.8,
      optimizationFlags: ['vertex_cache_optimization']
    };
  }

  private createEmptyAnimationAsset(name: string): any {
    return {
      id: `${name}-animation`,
      name: name,
      duration: 1.0,
      fps: 30,
      looping: true,
      blendable: true,
      priority: 1,
      tags: [name],
      keyframes: []
    };
  }

  private createEmptyTextureAsset(name: string, maxSize: number): any {
    const size = Math.min(1024, maxSize);
    return {
      id: `${name}-texture`,
      name: name,
      type: 'diffuse',
      format: 'png',
      resolution: size,
      mipmaps: true,
      compression: 'none',
      url: `assets/textures/${name}.png`,
      checksum: 'placeholder-checksum',
      size: size * size * 4 // RGBA
    };
  }

  private getDefaultCapabilities(platform: Platform): PlatformCapabilities {
    switch (platform) {
      case 'windows':
        return {
          maxTextureSize: 4096,
          supportedFormats: ['gltf', 'fbx', 'obj'],
          hardwareAcceleration: true,
          maxVertexCount: 100000,
          shaderComplexity: 'advanced',
          memoryLimit: 300 * 1024 * 1024, // 300MB
          supportsFullBody: true,
          supportsFaceOnly: true,
          supports2D: true,
          maxFPS: 60,
          batteryOptimized: false
        };
      
      case 'macos':
        return {
          maxTextureSize: 4096,
          supportedFormats: ['gltf', 'usdz', 'obj'],
          hardwareAcceleration: true,
          maxVertexCount: 100000,
          shaderComplexity: 'advanced',
          memoryLimit: 300 * 1024 * 1024, // 300MB
          supportsFullBody: true,
          supportsFaceOnly: true,
          supports2D: true,
          maxFPS: 60,
          batteryOptimized: false
        };
      
      case 'android':
        return {
          maxTextureSize: 2048,
          supportedFormats: ['gltf', 'obj'],
          hardwareAcceleration: true,
          maxVertexCount: 50000,
          shaderComplexity: 'basic',
          memoryLimit: 150 * 1024 * 1024, // 150MB
          supportsFullBody: false,
          supportsFaceOnly: true,
          supports2D: true,
          maxFPS: 30,
          batteryOptimized: true
        };
      
      case 'ios':
        return {
          maxTextureSize: 2048,
          supportedFormats: ['gltf', 'usdz'],
          hardwareAcceleration: true,
          maxVertexCount: 50000,
          shaderComplexity: 'basic',
          memoryLimit: 150 * 1024 * 1024, // 150MB
          supportsFullBody: false,
          supportsFaceOnly: true,
          supports2D: true,
          maxFPS: 30,
          batteryOptimized: true
        };
      
      case 'web':
        return {
          maxTextureSize: 1024,
          supportedFormats: ['gltf'],
          hardwareAcceleration: false,
          maxVertexCount: 25000,
          shaderComplexity: 'basic',
          memoryLimit: 100 * 1024 * 1024, // 100MB
          supportsFullBody: false,
          supportsFaceOnly: false,
          supports2D: true,
          maxFPS: 30,
          batteryOptimized: true
        };
      
      default:
        return {
          maxTextureSize: 1024,
          supportedFormats: ['gltf'],
          hardwareAcceleration: false,
          maxVertexCount: 25000,
          shaderComplexity: 'basic',
          memoryLimit: 100 * 1024 * 1024,
          supportsFullBody: false,
          supportsFaceOnly: false,
          supports2D: true,
          maxFPS: 30,
          batteryOptimized: true
        };
    }
  }
}