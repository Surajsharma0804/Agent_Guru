/**
 * Platform Renderer Interface
 * 
 * Provides platform-optimized 3D/2.5D rendering with consistent visual quality and performance.
 * Handles cross-platform asset loading, dynamic quality adjustment, and performance monitoring.
 */

import { 
  AnimationFrame, 
  RenderingHints, 
  QualityMetrics 
} from '../types/AnimationFrame';
import { 
  AvatarAssets
} from '../types/AvatarAssets';
import { 
  Platform, 
  QualityLevel, 
  PlatformCapabilities, 
  PerformanceMetrics, 
  MemoryStats, 
  GPUStats, 
  AvatarApiResponse 
} from '../types/Common';
import { 
  PlatformRenderingConfig, 
  RenderingAPI, 
  AvatarType 
} from '../types/Platform';

/**
 * Core Platform Renderer interface for cross-platform avatar rendering
 */
export interface PlatformRenderer {
  // Rendering Pipeline
  initializeRenderer(canvas: RenderingCanvas, config: PlatformRenderingConfig): Promise<AvatarApiResponse<void>>;
  renderFrame(animationData: AnimationFrame): Promise<AvatarApiResponse<RenderResult>>;
  presentFrame(): Promise<AvatarApiResponse<void>>;
  resizeViewport(width: number, height: number): Promise<AvatarApiResponse<void>>;
  
  // Platform Optimization
  detectPlatformCapabilities(): Promise<AvatarApiResponse<PlatformCapabilities>>;
  optimizeForPlatform(platform: Platform): Promise<AvatarApiResponse<PlatformRenderingConfig>>;
  adaptToHardware(capabilities: PlatformCapabilities): Promise<AvatarApiResponse<void>>;
  
  // Quality Management
  setQualityLevel(level: QualityLevel): Promise<AvatarApiResponse<void>>;
  getQualityLevel(): Promise<AvatarApiResponse<QualityLevel>>;
  enableDynamicQuality(enabled: boolean): Promise<AvatarApiResponse<void>>;
  adjustQualityForPerformance(targetFPS: number): Promise<AvatarApiResponse<void>>;
  
  // Asset Loading and Management
  loadAvatarAssets(assets: AvatarAssets): Promise<AvatarApiResponse<void>>;
  preloadNextFrame(animationData: AnimationFrame): Promise<AvatarApiResponse<void>>;
  unloadAssets(assetIds: string[]): Promise<AvatarApiResponse<void>>;
  validateAssetCompatibility(assets: AvatarAssets): Promise<AvatarApiResponse<CompatibilityReport>>;
  
  // Rendering State Management
  setRenderingState(state: RenderingState): Promise<AvatarApiResponse<void>>;
  getRenderingState(): Promise<AvatarApiResponse<RenderingState>>;
  pauseRendering(): Promise<AvatarApiResponse<void>>;
  resumeRendering(): Promise<AvatarApiResponse<void>>;
  
  // Performance Monitoring
  getCurrentFPS(): Promise<AvatarApiResponse<number>>;
  getMemoryUsage(): Promise<AvatarApiResponse<MemoryStats>>;
  getGPUUsage(): Promise<AvatarApiResponse<GPUStats>>;
  getPerformanceMetrics(): Promise<AvatarApiResponse<PerformanceMetrics>>;
  
  // Advanced Rendering Features
  enableFeature(feature: RenderingFeature): Promise<AvatarApiResponse<void>>;
  disableFeature(feature: RenderingFeature): Promise<AvatarApiResponse<void>>;
  isFeatureSupported(feature: RenderingFeature): Promise<AvatarApiResponse<boolean>>;
  setRenderingHints(hints: RenderingHints): Promise<AvatarApiResponse<void>>;
  
  // Lighting and Environment
  setLightingConfiguration(config: LightingConfiguration): Promise<AvatarApiResponse<void>>;
  setEnvironmentMap(environmentMap: EnvironmentMap): Promise<AvatarApiResponse<void>>;
  enableShadows(enabled: boolean, quality: ShadowQuality): Promise<AvatarApiResponse<void>>;
  
  // Post-Processing Effects
  enablePostProcessing(enabled: boolean): Promise<AvatarApiResponse<void>>;
  addPostProcessEffect(effect: PostProcessEffect): Promise<AvatarApiResponse<void>>;
  removePostProcessEffect(effectId: string): Promise<AvatarApiResponse<void>>;
  
  // Debug and Development
  enableDebugMode(enabled: boolean): Promise<AvatarApiResponse<void>>;
  captureFrame(): Promise<AvatarApiResponse<FrameCapture>>;
  getDebugInfo(): Promise<AvatarApiResponse<DebugInfo>>;
  validateRenderingPipeline(): Promise<AvatarApiResponse<ValidationResult>>;
  
  // Event Handling
  onFrameRendered(callback: FrameRenderedCallback): void;
  onPerformanceChanged(callback: PerformanceChangeCallback): void;
  onQualityChanged(callback: QualityChangeCallback): void;
  onError(callback: RenderingErrorCallback): void;
  
  // System Management
  cleanup(): Promise<AvatarApiResponse<void>>;
  resetRenderer(): Promise<AvatarApiResponse<void>>;
  optimizeMemory(): Promise<AvatarApiResponse<MemoryOptimizationResult>>;
}

/**
 * Rendering canvas abstraction for different platforms
 */
export interface RenderingCanvas {
  type: 'html_canvas' | 'webgl_context' | 'native_surface' | 'offscreen_buffer';
  element?: HTMLCanvasElement; // For web platforms
  context?: WebGLRenderingContext | WebGL2RenderingContext; // For WebGL
  nativeHandle?: unknown; // For native platforms
  width: number;
  height: number;
  pixelRatio: number;
}

/**
 * Render result information
 */
export interface RenderResult {
  success: boolean;
  frameTime: number; // milliseconds
  trianglesRendered: number;
  drawCalls: number;
  textureBinds: number;
  shaderSwitches: number;
  memoryUsed: number; // bytes
  quality: QualityMetrics;
}

/**
 * Asset compatibility report
 */
export interface CompatibilityReport {
  compatible: boolean;
  supportedAssets: string[];
  unsupportedAssets: UnsupportedAsset[];
  requiredConversions: AssetConversion[];
  performanceImpact: PerformanceImpact;
}

/**
 * Unsupported asset information
 */
export interface UnsupportedAsset {
  assetId: string;
  assetType: 'mesh' | 'texture' | 'shader' | 'animation';
  reason: string;
  alternatives: string[];
  conversionPossible: boolean;
}

/**
 * Asset conversion requirement
 */
export interface AssetConversion {
  assetId: string;
  fromFormat: string;
  toFormat: string;
  qualityLoss: number; // 0.0 to 1.0
  sizeChange: number; // multiplier
  conversionTime: number; // milliseconds
}

/**
 * Performance impact assessment
 */
export interface PerformanceImpact {
  fpsReduction: number; // percentage
  memoryIncrease: number; // bytes
  loadTimeIncrease: number; // milliseconds
  batteryImpact: number; // percentage per hour
}

/**
 * Rendering state configuration
 */
export interface RenderingState {
  active: boolean;
  paused: boolean;
  quality: QualityLevel;
  targetFPS: number;
  vsyncEnabled: boolean;
  fullscreen: boolean;
  antialiasing: AntialiasingMode;
  anisotropicFiltering: number; // 1x, 2x, 4x, 8x, 16x
}

/**
 * Antialiasing modes
 */
export type AntialiasingMode = 'none' | 'fxaa' | 'msaa_2x' | 'msaa_4x' | 'msaa_8x' | 'taa';

/**
 * Rendering features that can be enabled/disabled
 */
export type RenderingFeature = 
  | 'dynamic_lighting'
  | 'real_time_shadows'
  | 'reflection_probes'
  | 'ambient_occlusion'
  | 'bloom'
  | 'depth_of_field'
  | 'motion_blur'
  | 'screen_space_reflections'
  | 'volumetric_lighting'
  | 'particle_systems'
  | 'tessellation'
  | 'geometry_shaders'
  | 'compute_shaders'
  | 'instanced_rendering'
  | 'gpu_skinning'
  | 'morph_targets'
  | 'blend_shapes';

/**
 * Lighting configuration
 */
export interface LightingConfiguration {
  ambientLight: AmbientLight;
  directionalLights: DirectionalLight[];
  pointLights: PointLight[];
  spotLights: SpotLight[];
  areaLights?: AreaLight[];
  environmentLighting: EnvironmentLighting;
}

/**
 * Ambient light configuration
 */
export interface AmbientLight {
  color: import('../types/Common').ColorValue;
  intensity: number; // 0.0 to 1.0
  enabled: boolean;
}

/**
 * Directional light configuration
 */
export interface DirectionalLight {
  id: string;
  direction: import('../types/Common').Vector3;
  color: import('../types/Common').ColorValue;
  intensity: number; // 0.0 to 1.0
  castShadows: boolean;
  shadowMapSize: number;
  enabled: boolean;
}

/**
 * Point light configuration
 */
export interface PointLight {
  id: string;
  position: import('../types/Common').Vector3;
  color: import('../types/Common').ColorValue;
  intensity: number; // 0.0 to 1.0
  range: number; // meters
  attenuation: AttenuationCurve;
  castShadows: boolean;
  enabled: boolean;
}

/**
 * Spot light configuration
 */
export interface SpotLight {
  id: string;
  position: import('../types/Common').Vector3;
  direction: import('../types/Common').Vector3;
  color: import('../types/Common').ColorValue;
  intensity: number; // 0.0 to 1.0
  range: number; // meters
  innerConeAngle: number; // degrees
  outerConeAngle: number; // degrees
  attenuation: AttenuationCurve;
  castShadows: boolean;
  enabled: boolean;
}

/**
 * Area light configuration (advanced platforms only)
 */
export interface AreaLight {
  id: string;
  position: import('../types/Common').Vector3;
  rotation: import('../types/Common').Vector3;
  size: import('../types/Common').Vector2;
  color: import('../types/Common').ColorValue;
  intensity: number; // 0.0 to 1.0
  shape: 'rectangle' | 'circle';
  enabled: boolean;
}

/**
 * Light attenuation curve
 */
export interface AttenuationCurve {
  constant: number;
  linear: number;
  quadratic: number;
}

/**
 * Environment lighting configuration
 */
export interface EnvironmentLighting {
  skybox?: Skybox;
  environmentMap?: EnvironmentMap;
  irradianceMap?: IrradianceMap;
  reflectionProbes: ReflectionProbe[];
  globalIllumination: GlobalIllumination;
}

/**
 * Skybox configuration
 */
export interface Skybox {
  type: 'cubemap' | 'equirectangular' | 'procedural';
  textures: string[]; // texture asset IDs
  rotation: import('../types/Common').Vector3;
  exposure: number;
  tint: import('../types/Common').ColorValue;
}

/**
 * Environment map configuration
 */
export interface EnvironmentMap {
  textureId: string;
  intensity: number; // 0.0 to 1.0
  rotation: import('../types/Common').Vector3;
  blurLevel: number; // 0.0 to 1.0
}

/**
 * Irradiance map for global illumination
 */
export interface IrradianceMap {
  textureId: string;
  intensity: number; // 0.0 to 1.0
  samples: number;
}

/**
 * Reflection probe configuration
 */
export interface ReflectionProbe {
  id: string;
  position: import('../types/Common').Vector3;
  size: import('../types/Common').Vector3;
  resolution: number;
  updateFrequency: 'static' | 'realtime' | 'on_demand';
  importance: number; // 0.0 to 1.0
}

/**
 * Global illumination settings
 */
export interface GlobalIllumination {
  enabled: boolean;
  technique: 'lightmaps' | 'light_probes' | 'screen_space' | 'ray_tracing';
  quality: 'low' | 'medium' | 'high' | 'ultra';
  bounces: number;
  intensity: number; // 0.0 to 1.0
}

/**
 * Shadow quality settings
 */
export type ShadowQuality = 'disabled' | 'low' | 'medium' | 'high' | 'ultra';

/**
 * Post-processing effect configuration
 */
export interface PostProcessEffect {
  id: string;
  type: PostProcessEffectType;
  enabled: boolean;
  parameters: Record<string, unknown>;
  order: number; // rendering order
}

/**
 * Post-processing effect types
 */
export type PostProcessEffectType = 
  | 'tone_mapping'
  | 'color_grading'
  | 'bloom'
  | 'depth_of_field'
  | 'motion_blur'
  | 'screen_space_ambient_occlusion'
  | 'screen_space_reflections'
  | 'temporal_anti_aliasing'
  | 'chromatic_aberration'
  | 'vignette'
  | 'film_grain'
  | 'lens_distortion';

/**
 * Frame capture for debugging
 */
export interface FrameCapture {
  timestamp: number;
  frameNumber: number;
  imageData: ImageData | ArrayBuffer;
  format: 'png' | 'jpg' | 'raw';
  metadata: FrameCaptureMetadata;
}

/**
 * Frame capture metadata
 */
export interface FrameCaptureMetadata {
  resolution: import('../types/Common').Vector2;
  renderTime: number; // milliseconds
  triangleCount: number;
  drawCalls: number;
  memoryUsage: number; // bytes
  quality: QualityMetrics;
}

/**
 * Debug information for development
 */
export interface DebugInfo {
  renderer: RendererInfo;
  performance: PerformanceDebugInfo;
  resources: ResourceDebugInfo;
  pipeline: PipelineDebugInfo;
  errors: RenderingError[];
}

/**
 * Renderer information
 */
export interface RendererInfo {
  api: RenderingAPI;
  version: string;
  vendor: string;
  device: string;
  driverVersion: string;
  extensions: string[];
  limits: RendererLimits;
}

/**
 * Renderer limits and capabilities
 */
export interface RendererLimits {
  maxTextureSize: number;
  maxTextures: number;
  maxVertexAttributes: number;
  maxUniformBuffers: number;
  maxDrawBuffers: number;
  maxSamples: number;
  maxViewportSize: import('../types/Common').Vector2;
}

/**
 * Performance debug information
 */
export interface PerformanceDebugInfo {
  currentFPS: number;
  averageFPS: number;
  frameTime: FrameTimeBreakdown;
  memoryUsage: DetailedMemoryUsage;
  gpuUsage: DetailedGPUUsage;
  bottlenecks: PerformanceBottleneck[];
}

/**
 * Frame time breakdown
 */
export interface FrameTimeBreakdown {
  total: number; // milliseconds
  cpu: number; // milliseconds
  gpu: number; // milliseconds
  geometry: number; // milliseconds
  shading: number; // milliseconds
  postProcessing: number; // milliseconds
  present: number; // milliseconds
}

/**
 * Detailed memory usage
 */
export interface DetailedMemoryUsage {
  total: number; // bytes
  textures: number; // bytes
  meshes: number; // bytes
  shaders: number; // bytes
  buffers: number; // bytes
  framebuffers: number; // bytes
  other: number; // bytes
}

/**
 * Detailed GPU usage
 */
export interface DetailedGPUUsage {
  utilization: number; // percentage
  memoryUsed: number; // bytes
  memoryTotal: number; // bytes
  temperature: number; // celsius
  clockSpeed: number; // MHz
  powerDraw: number; // watts
}

/**
 * Performance bottleneck identification
 */
export interface PerformanceBottleneck {
  type: 'cpu' | 'gpu' | 'memory' | 'bandwidth' | 'fillrate' | 'vertex_processing';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  suggestion: string;
  impact: number; // percentage performance loss
}

/**
 * Resource debug information
 */
export interface ResourceDebugInfo {
  loadedAssets: LoadedAssetInfo[];
  textureMemory: TextureMemoryInfo;
  meshMemory: MeshMemoryInfo;
  shaderCompilation: ShaderCompilationInfo;
  cacheStatistics: CacheStatistics;
}

/**
 * Loaded asset information
 */
export interface LoadedAssetInfo {
  id: string;
  type: 'mesh' | 'texture' | 'shader' | 'animation';
  size: number; // bytes
  loadTime: number; // milliseconds
  lastUsed: number; // timestamp
  referenceCount: number;
}

/**
 * Texture memory information
 */
export interface TextureMemoryInfo {
  totalUsed: number; // bytes
  count: number;
  largestTexture: number; // bytes
  compressionRatio: number;
  mipmapUsage: number; // percentage
}

/**
 * Mesh memory information
 */
export interface MeshMemoryInfo {
  totalUsed: number; // bytes
  vertexBuffers: number; // bytes
  indexBuffers: number; // bytes
  totalVertices: number;
  totalTriangles: number;
}

/**
 * Shader compilation information
 */
export interface ShaderCompilationInfo {
  compiledShaders: number;
  compilationTime: number; // milliseconds
  cacheHits: number;
  cacheMisses: number;
  errors: ShaderError[];
}

/**
 * Shader compilation error
 */
export interface ShaderError {
  shaderId: string;
  type: 'vertex' | 'fragment' | 'geometry' | 'compute';
  line: number;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * Cache statistics
 */
export interface CacheStatistics {
  hitRate: number; // 0.0 to 1.0
  size: number; // bytes
  maxSize: number; // bytes
  evictions: number;
  lookups: number;
}

/**
 * Pipeline debug information
 */
export interface PipelineDebugInfo {
  renderPasses: RenderPassInfo[];
  drawCalls: DrawCallInfo[];
  stateChanges: StateChangeInfo[];
  cullingStatistics: CullingStatistics;
}

/**
 * Render pass information
 */
export interface RenderPassInfo {
  name: string;
  duration: number; // milliseconds
  drawCalls: number;
  triangles: number;
  pixelsShaded: number;
}

/**
 * Draw call information
 */
export interface DrawCallInfo {
  id: number;
  shader: string;
  mesh: string;
  triangles: number;
  vertices: number;
  renderTime: number; // microseconds
}

/**
 * State change information
 */
export interface StateChangeInfo {
  type: 'shader' | 'texture' | 'buffer' | 'render_target' | 'blend_state';
  count: number;
  cost: number; // microseconds
}

/**
 * Culling statistics
 */
export interface CullingStatistics {
  totalObjects: number;
  culledObjects: number;
  frustumCulled: number;
  occlusionCulled: number;
  distanceCulled: number;
  cullingTime: number; // microseconds
}

/**
 * Rendering error information
 */
export interface RenderingError {
  type: 'shader_error' | 'resource_error' | 'api_error' | 'performance_error';
  message: string;
  timestamp: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  context: Record<string, unknown>;
  recoverable: boolean;
}

/**
 * Validation result for rendering pipeline
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  performance: PerformanceValidation;
}

/**
 * Validation error
 */
export interface ValidationError {
  component: string;
  message: string;
  severity: 'error' | 'warning';
  suggestedFix?: string;
}

/**
 * Validation warning
 */
export interface ValidationWarning {
  component: string;
  message: string;
  impact: 'performance' | 'quality' | 'compatibility';
  recommendation?: string;
}

/**
 * Performance validation
 */
export interface PerformanceValidation {
  meetsTargets: boolean;
  fpsTarget: number;
  actualFPS: number;
  memoryTarget: number; // bytes
  actualMemory: number; // bytes
  recommendations: string[];
}

/**
 * Memory optimization result
 */
export interface MemoryOptimizationResult {
  bytesFreed: number;
  assetsUnloaded: number;
  cacheCleared: boolean;
  compressionApplied: boolean;
  optimizationTime: number; // milliseconds
}

/**
 * Frame rendered callback
 */
export type FrameRenderedCallback = (
  frameNumber: number,
  renderTime: number,
  quality: QualityMetrics
) => void;

/**
 * Performance change callback
 */
export type PerformanceChangeCallback = (
  oldMetrics: PerformanceMetrics,
  newMetrics: PerformanceMetrics,
  trend: 'improving' | 'degrading' | 'stable'
) => void;

/**
 * Quality change callback
 */
export type QualityChangeCallback = (
  oldQuality: QualityLevel,
  newQuality: QualityLevel,
  reason: 'manual' | 'automatic' | 'performance'
) => void;

/**
 * Rendering error callback
 */
export type RenderingErrorCallback = (
  error: RenderingError,
  context: Record<string, unknown>
) => void;

/**
 * Platform Renderer factory for creating platform-specific implementations
 */
export interface PlatformRendererFactory {
  createRenderer(platform: Platform, config: RendererConfig): Promise<PlatformRenderer>;
  getSupportedPlatforms(): Platform[];
  getDefaultConfig(platform: Platform): RendererConfig;
  validateConfig(config: RendererConfig): ValidationResult;
}

/**
 * Renderer configuration
 */
export interface RendererConfig {
  // Platform settings
  platform: Platform;
  renderingAPI: RenderingAPI;
  avatarType: AvatarType;
  
  // Quality settings
  defaultQuality: QualityLevel;
  dynamicQuality: boolean;
  targetFPS: number;
  
  // Performance settings
  memoryLimit: number; // bytes
  optimizeForBattery: boolean;
  backgroundRendering: boolean;
  
  // Feature settings
  enabledFeatures: RenderingFeature[];
  lightingQuality: 'low' | 'medium' | 'high';
  shadowQuality: ShadowQuality;
  
  // Debug settings
  debugMode: boolean;
  captureFrames: boolean;
  validatePipeline: boolean;
}