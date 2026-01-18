/**
 * Platform constants and configuration
 */

import { 
  Platform, 
  PlatformCapabilities 
} from '../types/Common';
import { 
  PlatformRenderingConfig, 
  RenderingAPI, 
  AvatarType, 
  PlatformFeatures,
  PlatformPerformanceTargets 
} from '../types/Platform';

/**
 * All supported platforms
 */
export const SUPPORTED_PLATFORMS: readonly Platform[] = [
  'windows',
  'macos',
  'android',
  'ios',
  'web'
] as const;

/**
 * Desktop platforms (full 3D rendering)
 */
export const DESKTOP_PLATFORMS: readonly Platform[] = [
  'windows',
  'macos'
] as const;

/**
 * Mobile platforms (face-only 3D rendering)
 */
export const MOBILE_PLATFORMS: readonly Platform[] = [
  'android',
  'ios'
] as const;

/**
 * Web platforms (2.5D rendering)
 */
export const WEB_PLATFORMS: readonly Platform[] = [
  'web'
] as const;

/**
 * Default rendering APIs by platform
 */
export const DEFAULT_RENDERING_APIS: Record<Platform, RenderingAPI> = {
  'windows': 'directx12',
  'macos': 'metal',
  'android': 'vulkan',
  'ios': 'metal',
  'web': 'webgl'
};

/**
 * Fallback rendering APIs by platform
 */
export const FALLBACK_RENDERING_APIS: Record<Platform, RenderingAPI[]> = {
  'windows': ['vulkan', 'opengl_es'],
  'macos': ['opengl_es'],
  'android': ['opengl_es'],
  'ios': ['opengl_es'],
  'web': ['webgpu']
};

/**
 * Avatar types by platform
 */
export const AVATAR_TYPES_BY_PLATFORM: Record<Platform, AvatarType> = {
  'windows': 'full_body_3d',
  'macos': 'full_body_3d',
  'android': 'face_only_3d',
  'ios': 'face_only_3d',
  'web': 'upper_body_2_5d'
};

/**
 * Platform performance targets
 */
export const PLATFORM_PERFORMANCE_TARGETS: Record<Platform, PlatformPerformanceTargets> = {
  'windows': {
    platform: 'windows',
    minFPS: 60,
    maxMemoryUsage: 300 * 1024 * 1024, // 300MB
    maxCPUUsage: 15, // 15%
    maxGPUUsage: 30, // 30%
    maxStartupTime: 2000, // 2 seconds
    maxThermalImpact: 5 // 5°C increase
  },
  'macos': {
    platform: 'macos',
    minFPS: 60,
    maxMemoryUsage: 300 * 1024 * 1024, // 300MB
    maxCPUUsage: 15, // 15%
    maxGPUUsage: 30, // 30%
    maxStartupTime: 2000, // 2 seconds
    maxThermalImpact: 5 // 5°C increase
  },
  'android': {
    platform: 'android',
    minFPS: 30,
    maxMemoryUsage: 150 * 1024 * 1024, // 150MB
    maxCPUUsage: 20, // 20%
    maxGPUUsage: 25, // 25%
    maxStartupTime: 2000, // 2 seconds
    maxBatteryDrain: 5, // 5% per hour
    maxThermalImpact: 3 // 3°C increase
  },
  'ios': {
    platform: 'ios',
    minFPS: 30,
    maxMemoryUsage: 150 * 1024 * 1024, // 150MB
    maxCPUUsage: 20, // 20%
    maxGPUUsage: 25, // 25%
    maxStartupTime: 2000, // 2 seconds
    maxBatteryDrain: 5, // 5% per hour
    maxThermalImpact: 3 // 3°C increase
  },
  'web': {
    platform: 'web',
    minFPS: 30,
    maxMemoryUsage: 100 * 1024 * 1024, // 100MB
    maxCPUUsage: 25, // 25%
    maxGPUUsage: 20, // 20%
    maxStartupTime: 2000 // 2 seconds
  }
};

/**
 * Platform capabilities (baseline requirements)
 */
export const PLATFORM_CAPABILITIES: Record<Platform, PlatformCapabilities> = {
  'windows': {
    maxTextureSize: 4096,
    supportedFormats: ['gltf', 'glb', 'fbx', 'obj'],
    hardwareAcceleration: true,
    maxVertexCount: 100000,
    shaderComplexity: 'compute',
    memoryLimit: 300 * 1024 * 1024, // 300MB
    supportsFullBody: true,
    supportsFaceOnly: true,
    supports2D: true,
    maxFPS: 120,
    batteryOptimized: false
  },
  'macos': {
    maxTextureSize: 4096,
    supportedFormats: ['gltf', 'glb', 'usdz', 'obj'],
    hardwareAcceleration: true,
    maxVertexCount: 100000,
    shaderComplexity: 'compute',
    memoryLimit: 300 * 1024 * 1024, // 300MB
    supportsFullBody: true,
    supportsFaceOnly: true,
    supports2D: true,
    maxFPS: 120,
    batteryOptimized: false
  },
  'android': {
    maxTextureSize: 2048,
    supportedFormats: ['gltf', 'glb'],
    hardwareAcceleration: true,
    maxVertexCount: 50000,
    shaderComplexity: 'advanced',
    memoryLimit: 150 * 1024 * 1024, // 150MB
    supportsFullBody: false,
    supportsFaceOnly: true,
    supports2D: true,
    maxFPS: 60,
    batteryOptimized: true
  },
  'ios': {
    maxTextureSize: 2048,
    supportedFormats: ['gltf', 'glb', 'usdz'],
    hardwareAcceleration: true,
    maxVertexCount: 50000,
    shaderComplexity: 'advanced',
    memoryLimit: 150 * 1024 * 1024, // 150MB
    supportsFullBody: false,
    supportsFaceOnly: true,
    supports2D: true,
    maxFPS: 60,
    batteryOptimized: true
  },
  'web': {
    maxTextureSize: 2048,
    supportedFormats: ['gltf', 'glb'],
    hardwareAcceleration: false, // varies by browser
    maxVertexCount: 30000,
    shaderComplexity: 'basic',
    memoryLimit: 100 * 1024 * 1024, // 100MB
    supportsFullBody: false,
    supportsFaceOnly: false,
    supports2D: true,
    maxFPS: 60,
    batteryOptimized: true
  }
};

/**
 * Platform features support matrix
 */
export const PLATFORM_FEATURES: Record<Platform, PlatformFeatures> = {
  'windows': {
    dynamicLighting: true,
    realTimeShadows: true,
    textureCompression: true,
    morphTargets: true,
    proceduralAnimation: true,
    audioProcessing: true,
    cameraAccess: true,
    backgroundProcessing: true,
    pushNotifications: true,
    fileSystemAccess: true
  },
  'macos': {
    dynamicLighting: true,
    realTimeShadows: true,
    textureCompression: true,
    morphTargets: true,
    proceduralAnimation: true,
    audioProcessing: true,
    cameraAccess: true,
    backgroundProcessing: true,
    pushNotifications: true,
    fileSystemAccess: true
  },
  'android': {
    dynamicLighting: true,
    realTimeShadows: false,
    textureCompression: true,
    morphTargets: true,
    proceduralAnimation: true,
    audioProcessing: true,
    cameraAccess: true,
    backgroundProcessing: false,
    pushNotifications: true,
    fileSystemAccess: false
  },
  'ios': {
    dynamicLighting: true,
    realTimeShadows: false,
    textureCompression: true,
    morphTargets: true,
    proceduralAnimation: true,
    audioProcessing: true,
    cameraAccess: true,
    backgroundProcessing: false,
    pushNotifications: true,
    fileSystemAccess: false
  },
  'web': {
    dynamicLighting: false,
    realTimeShadows: false,
    textureCompression: true,
    morphTargets: true,
    proceduralAnimation: true,
    audioProcessing: true,
    cameraAccess: true,
    backgroundProcessing: false,
    pushNotifications: true,
    fileSystemAccess: false
  }
};

/**
 * Default platform rendering configurations
 */
export const DEFAULT_PLATFORM_CONFIGS: Record<Platform, PlatformRenderingConfig> = {
  'windows': {
    platform: 'windows',
    quality: 'high',
    targetFPS: 60,
    memoryLimit: 300 * 1024 * 1024, // 300MB
    renderingAPI: 'directx12',
    avatarType: 'full_body_3d',
    features: PLATFORM_FEATURES.windows
  },
  'macos': {
    platform: 'macos',
    quality: 'high',
    targetFPS: 60,
    memoryLimit: 300 * 1024 * 1024, // 300MB
    renderingAPI: 'metal',
    avatarType: 'full_body_3d',
    features: PLATFORM_FEATURES.macos
  },
  'android': {
    platform: 'android',
    quality: 'medium',
    targetFPS: 30,
    memoryLimit: 150 * 1024 * 1024, // 150MB
    renderingAPI: 'vulkan',
    avatarType: 'face_only_3d',
    features: PLATFORM_FEATURES.android
  },
  'ios': {
    platform: 'ios',
    quality: 'medium',
    targetFPS: 30,
    memoryLimit: 150 * 1024 * 1024, // 150MB
    renderingAPI: 'metal',
    avatarType: 'face_only_3d',
    features: PLATFORM_FEATURES.ios
  },
  'web': {
    platform: 'web',
    quality: 'medium',
    targetFPS: 30,
    memoryLimit: 100 * 1024 * 1024, // 100MB
    renderingAPI: 'webgl',
    avatarType: 'upper_body_2_5d',
    features: PLATFORM_FEATURES.web
  }
};

/**
 * Platform-specific optimization flags
 */
export const PLATFORM_OPTIMIZATIONS = {
  WINDOWS: {
    USE_DIRECTX12: true,
    ENABLE_HARDWARE_ACCELERATION: true,
    USE_COMPUTE_SHADERS: true,
    ENABLE_MULTITHREADING: true,
    USE_MEMORY_POOLS: true
  },
  MACOS: {
    USE_METAL: true,
    ENABLE_HARDWARE_ACCELERATION: true,
    USE_COMPUTE_SHADERS: true,
    OPTIMIZE_FOR_RETINA: true,
    USE_UNIFIED_MEMORY: true
  },
  ANDROID: {
    USE_VULKAN: true,
    ENABLE_BATTERY_OPTIMIZATION: true,
    USE_TEXTURE_COMPRESSION: true,
    LIMIT_DRAW_CALLS: true,
    REDUCE_MEMORY_FOOTPRINT: true
  },
  IOS: {
    USE_METAL: true,
    ENABLE_BATTERY_OPTIMIZATION: true,
    USE_TEXTURE_COMPRESSION: true,
    OPTIMIZE_FOR_THERMAL: true,
    USE_TILE_BASED_RENDERING: true
  },
  WEB: {
    USE_WEBGL2: true,
    ENABLE_INSTANCING: true,
    USE_TEXTURE_ATLASING: true,
    MINIMIZE_STATE_CHANGES: true,
    OPTIMIZE_FOR_BANDWIDTH: true
  }
} as const;

/**
 * Platform detection patterns
 */
export const PLATFORM_DETECTION_PATTERNS = {
  USER_AGENTS: {
    WINDOWS: /Windows NT/i,
    MACOS: /Mac OS X/i,
    ANDROID: /Android/i,
    IOS: /iPhone|iPad|iPod/i,
    WEB: /Mozilla|Chrome|Safari|Firefox|Edge/i
  },
  FEATURES: {
    WEBGL: 'WebGLRenderingContext',
    WEBGL2: 'WebGL2RenderingContext',
    WEBGPU: 'GPUDevice',
    TOUCH: 'ontouchstart',
    ORIENTATION: 'onorientationchange'
  }
} as const;

/**
 * Platform-specific asset formats
 */
export const PLATFORM_ASSET_FORMATS = {
  WINDOWS: {
    MESH: ['gltf', 'glb', 'fbx', 'obj'],
    TEXTURE: ['png', 'jpg', 'dds', 'ktx2'],
    AUDIO: ['wav', 'mp3', 'ogg']
  },
  MACOS: {
    MESH: ['gltf', 'glb', 'usdz', 'obj'],
    TEXTURE: ['png', 'jpg', 'ktx2'],
    AUDIO: ['wav', 'mp3', 'aac']
  },
  ANDROID: {
    MESH: ['gltf', 'glb'],
    TEXTURE: ['png', 'jpg', 'webp', 'ktx2', 'astc'],
    AUDIO: ['wav', 'mp3', 'ogg', 'aac']
  },
  IOS: {
    MESH: ['gltf', 'glb', 'usdz'],
    TEXTURE: ['png', 'jpg', 'ktx2'],
    AUDIO: ['wav', 'mp3', 'aac']
  },
  WEB: {
    MESH: ['gltf', 'glb'],
    TEXTURE: ['png', 'jpg', 'webp'],
    AUDIO: ['wav', 'mp3', 'ogg']
  }
} as const;

/**
 * Platform memory limits by device class
 */
export const MEMORY_LIMITS_BY_DEVICE_CLASS = {
  HIGH_END: {
    DESKTOP: 500 * 1024 * 1024, // 500MB
    MOBILE: 200 * 1024 * 1024,  // 200MB
    WEB: 150 * 1024 * 1024      // 150MB
  },
  MID_RANGE: {
    DESKTOP: 300 * 1024 * 1024, // 300MB
    MOBILE: 150 * 1024 * 1024,  // 150MB
    WEB: 100 * 1024 * 1024      // 100MB
  },
  LOW_END: {
    DESKTOP: 200 * 1024 * 1024, // 200MB
    MOBILE: 100 * 1024 * 1024,  // 100MB
    WEB: 75 * 1024 * 1024       // 75MB
  }
} as const;

/**
 * Platform-specific quality presets
 */
export const QUALITY_PRESETS_BY_PLATFORM = {
  DESKTOP: {
    ULTRA: { textureSize: 4096, meshComplexity: 1.0, effectsQuality: 1.0 },
    HIGH: { textureSize: 2048, meshComplexity: 0.8, effectsQuality: 0.8 },
    MEDIUM: { textureSize: 1024, meshComplexity: 0.6, effectsQuality: 0.6 },
    LOW: { textureSize: 512, meshComplexity: 0.4, effectsQuality: 0.4 }
  },
  MOBILE: {
    HIGH: { textureSize: 1024, meshComplexity: 0.7, effectsQuality: 0.6 },
    MEDIUM: { textureSize: 512, meshComplexity: 0.5, effectsQuality: 0.4 },
    LOW: { textureSize: 256, meshComplexity: 0.3, effectsQuality: 0.2 }
  },
  WEB: {
    HIGH: { textureSize: 1024, meshComplexity: 0.6, effectsQuality: 0.5 },
    MEDIUM: { textureSize: 512, meshComplexity: 0.4, effectsQuality: 0.3 },
    LOW: { textureSize: 256, meshComplexity: 0.2, effectsQuality: 0.1 }
  }
} as const;